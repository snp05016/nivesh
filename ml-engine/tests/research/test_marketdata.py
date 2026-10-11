"""Market-data tests (spec 3, 11.1; package ml-marketdata). Offline: tiny zips, synthetic panels."""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import date

import numpy as np
import pandas as pd
import pytest

from research.marketdata import adjust as adj
from research.marketdata import bhavcopy, store, universe

LEGACY_HEADER = "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN,"
UDIFF_HEADER = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,FininstrmActlXpryDt,StrkPric,"
    "OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,"
    "ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4"
)
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_a, **_k):
        raise AssertionError("network access in a unit test")

    monkeypatch.setattr(bhavcopy.urllib.request, "urlopen", refuse)
    monkeypatch.setattr(store.YFinance, "__init__", refuse)


# ── synthetic data ──────────────────────────────────────────────────────────


def bdays(n: int, start: date = date(2023, 6, 1)) -> list[date]:
    return [ts.date() for ts in pd.bdate_range(start, periods=n)]


def bar(sym: str, isin: str, d: date, close: float, prev: float | None, vol: float = 10_000, series: str = "EQ") -> dict:
    return {"symbol": sym, "isin": isin, "series": series, "date": d, "open": close, "high": close * 1.01,
            "low": close * 0.99, "close": close, "prev_close": close if prev is None else prev, "volume": vol}


def series_bars(sym: str, isin: str, days: list[date], closes: list[float], vol: float = 10_000) -> list[dict]:
    return [bar(sym, isin, d, c, closes[i - 1] if i else None, vol) for i, (d, c) in enumerate(zip(days, closes))]


def _zip(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("bhav.csv", text)
    return buf.getvalue()


def legacy_bytes(bars: list[dict]) -> bytes:
    lines = [LEGACY_HEADER]
    for b in bars:
        d = b["date"]
        stamp = f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year}"
        lines.append(f"{b['symbol']},{b['series']},{b['open']},{b['high']},{b['low']},{b['close']},{b['close']},"
                     f"{b['prev_close']},{b['volume']:.0f},{b['close'] * b['volume']},{stamp},{int(b['volume'] // 10)},{b['isin']},")
    return _zip("\n".join(lines) + "\n")


def udiff_bytes(bars: list[dict]) -> bytes:
    lines = [UDIFF_HEADER]
    for b in bars:
        d = f"{b['date']:%Y-%m-%d}"
        lines.append(
            f"{d},{d},CM,NSE,STK,1,{b['isin']},{b['symbol']},{b['series']},,,,,{b['symbol']} LTD,{b['open']},{b['high']},"
            f"{b['low']},{b['close']},{b['close']},{b['prev_close']},,{b['close']},,,{b['volume']:.0f},{b['close'] * b['volume']},"
            f"{int(b['volume'] // 10)},F1,1,,,,,"
        )
    return _zip("\n".join(lines) + "\n")


def bhav_for(bars: list[dict]) -> dict[date, bytes]:
    by_day: dict[date, list[dict]] = {}
    for b in bars:
        by_day.setdefault(b["date"], []).append(b)
    return {d: (legacy_bytes(v) if d <= bhavcopy.LEGACY_LAST else udiff_bytes(v)) for d, v in by_day.items()}


def fake_fetch(book: dict[date, bytes], fail: frozenset[date] = frozenset()):
    def fetch(d: date) -> bytes | None:
        if d in fail:
            raise OSError("connection reset")
        return book.get(d)

    return fetch


def build_panel(bars: list[dict], **adjust_kw) -> pd.DataFrame:
    """Rows -> quality filter -> linking -> adjustment (the store's curation, in memory)."""
    rows = pd.DataFrame(bars)
    rows["date"] = pd.to_datetime(rows["date"]).astype("datetime64[ns]")
    rows["turnover_inr"] = rows["close"] * rows["volume"]
    rows["trades"] = rows["volume"] // 10
    rows["source"] = rows.get("source", "nse_bhavcopy")
    kept, _ = adj.quality_filter(rows.loc[:, store._RAW_COLUMNS])
    linked, _ = store.link_entities(kept)
    return adj.adjust(linked, **adjust_kw)


def entity_rows(panel: pd.DataFrame, entity_id: str) -> pd.DataFrame:
    return panel.loc[panel["entity_id"] == entity_id].sort_values("date").reset_index(drop=True)


def implied_f(p: pd.DataFrame, i: int) -> float:
    """f from the index: px_t / px_p = close_t / (close_p * f)."""
    return (p.loc[i, "close"] / p.loc[i - 1, "close"]) / (p.loc[i, "px_idx"] / p.loc[i - 1, "px_idx"])


# ── parsing ─────────────────────────────────────────────────────────────────

D0 = date(2024, 7, 12)
PARSE_BARS = [
    bar("RELIANCE", "INE002A01018", D0, 2875.4, 2860.0, 1_234_567),
    bar("TCS", "INE467B01029", D0, 4100.0, 4120.5, 345_678),
    bar("TCS", "INE467B01029", D0, 4099.0, 4100.0, 1_000, series="BL"),
]


def test_legacy_and_udiff_parse_identically() -> None:
    a = bhavcopy.parse_bhavcopy(legacy_bytes(PARSE_BARS))
    b = bhavcopy.parse_bhavcopy(udiff_bytes(PARSE_BARS))
    pd.testing.assert_frame_equal(a, b)
    assert list(a.columns) == list(bhavcopy.COMMON_COLUMNS)
    assert bool(a["series"].eq("EQ").all()) and len(a) == 2
    assert a["date"].dtype == "datetime64[ns]" and a["volume"].dtype == "float64"
    assert a.loc[a.symbol == "RELIANCE", "prev_close"].item() == 2860.0


@pytest.mark.parametrize("make,column", [(legacy_bytes, "PREVCLOSE"), (udiff_bytes, "PrvsClsgPric")])
def test_missing_column_raises(make, column: str) -> None:
    text = zipfile.ZipFile(io.BytesIO(make(PARSE_BARS))).read("bhav.csv").decode()
    broken = _zip(text.replace(column, "Something", 1))
    with pytest.raises(bhavcopy.BhavcopySchemaError, match=column):
        bhavcopy.parse_bhavcopy(broken)


def test_html_page_is_a_bad_file_not_a_schema_change() -> None:
    with pytest.raises(bhavcopy.BadBhavcopyFile):
        bhavcopy.parse_bhavcopy(b"<html><body>Not found</body></html>")


def test_urls_switch_format_on_2024_07_08() -> None:
    assert bhavcopy.bhavcopy_url(date(2024, 7, 5)).endswith("/EQUITIES/2024/JUL/cm05JUL2024bhav.csv.zip")
    assert bhavcopy.bhavcopy_url(date(2024, 7, 8)).endswith("/BhavCopy_NSE_CM_0_0_0_20240708_F_0000.csv.zip")


def test_downloader_needs_an_honest_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RESEARCH_HTTP_CONTACT", raising=False)
    with pytest.raises(RuntimeError):
        bhavcopy.Downloader()
    monkeypatch.setenv("RESEARCH_HTTP_CONTACT", "https://example.org/contact")
    assert bhavcopy.Downloader().user_agent == "NiveshResearch/1.0 (+https://example.org/contact)"


# ── adjustments and quality ─────────────────────────────────────────────────


def _bonus_bars() -> list[dict]:
    days = bdays(4)
    bars = series_bars("RELIANCE", "INE002A01018", days[:2], [100.0, 100.0])
    bars.append(bar("RELIANCE", "INE002A01018", days[2], 51.0, 50.0))  # 1:1 bonus: PREVCLOSE halved
    bars.append(bar("RELIANCE", "INE002A01018", days[3], 52.0, 51.0))
    return bars


def test_bonus_one_for_one_gives_half_factor() -> None:
    p = entity_rows(build_panel(_bonus_bars()), "EINE002A01018")
    assert implied_f(p, 2) == pytest.approx(0.5)
    assert p["px_idx"].tolist() == pytest.approx([1.0, 1.0, 1.02, 1.04])
    assert p.loc[2, "event"] == "ca_unverified" and p.loc[2, "quality_flags"] == "ca_unverified"
    actions = pd.DataFrame({"symbol": ["RELIANCE"], "date": [pd.Timestamp(bdays(4)[2])], "split": [2.0], "dividend": [np.nan]})
    q = entity_rows(build_panel(_bonus_bars(), actions=actions), "EINE002A01018")
    assert q.loc[2, "event"] == "split" and q.loc[2, "quality_flags"] == ""
    assert q["px_idx"].tolist() == pytest.approx(p["px_idx"].tolist())


def test_override_wins_and_dividend_is_classified_not_added() -> None:
    bars = _bonus_bars()
    ov = pd.DataFrame({"isin": ["INE002A01018"], "ex_date": [pd.Timestamp(bdays(4)[2])], "factor": [0.4], "note": ["x"]})
    p = entity_rows(build_panel(bars, overrides=ov), "EINE002A01018")
    assert implied_f(p, 2) == pytest.approx(0.4) and p.loc[2, "event"] == "override"

    days = bdays(3)
    div = series_bars("ITC", "INE154A01025", days[:2], [100.0, 100.0]) + [bar("ITC", "INE154A01025", days[2], 99.0, 99.0)]
    actions = pd.DataFrame({"symbol": ["ITC"], "date": [pd.Timestamp(days[2])], "split": [np.nan], "dividend": [1.0]})
    d = entity_rows(build_panel(div, actions=actions), "EINE154A01025")
    assert d.loc[2, "event"] == "dividend"
    assert implied_f(d, 2) == pytest.approx(0.99)  # the PREVCLOSE factor is applied regardless (D34)


def test_zero_volume_is_nan_and_skipped_by_the_index() -> None:
    days = bdays(4)
    bars = series_bars("ABC", "INE111A01011", days, [100.0, 101.0, 101.0, 102.0])
    bars[2]["volume"] = 0
    p = entity_rows(build_panel(bars), "EINE111A01011")
    assert np.isnan(p.loc[2, ["volume", "turnover_inr", "trades", "px_idx"]].astype(float)).all()
    assert p.loc[2, "quality_flags"] == "zero_volume"
    assert p.loc[3, "px_idx"] == pytest.approx(1.02)


def _jump_bars(path: list[float]) -> list[dict]:
    days = bdays(len(path))
    return series_bars("JMP", "INE222A01011", days, path)


def test_persisting_crash_is_valid() -> None:
    path = [100.0] * 5 + [72.0] * 6  # -28% and it stays
    p = entity_rows(build_panel(_jump_bars(path)), "EINE222A01011")
    assert not bool(p["quality_flags"].eq("suspect").any())
    assert p.loc[5, "px_idx"] == pytest.approx(0.72)


def test_spike_and_reversal_is_suspect_and_skipped() -> None:
    path = [100.0] * 5 + [160.0, 64.0] + [64.0] * 4  # +60% then -60%
    p = entity_rows(build_panel(_jump_bars(path)), "EINE222A01011")
    assert p["quality_flags"].tolist().count("suspect") == 1 and p.loc[5, "quality_flags"] == "suspect"
    assert np.isnan(p.loc[5, "px_idx"])
    assert p.loc[6, "px_idx"] == pytest.approx(0.64)  # chained over the skipped close


def test_reversal_rule_applies_retroactively() -> None:
    path = [100.0] * 5 + [160.0]
    early = entity_rows(build_panel(_jump_bars(path)), "EINE222A01011")
    assert early.loc[5, "quality_flags"] == "" and early.loc[5, "px_idx"] == pytest.approx(1.6)
    late = entity_rows(build_panel(_jump_bars(path + [101.0, 100.0])), "EINE222A01011")
    assert late.loc[5, "quality_flags"] == "suspect"


def test_second_source_mismatch_marks_suspect() -> None:
    path = [100.0] * 5 + [140.0] * 4
    day = pd.Timestamp(bdays(len(path))[5])
    other = pd.DataFrame({"symbol": ["JMP"], "date": [day], "close": [100.5]})
    bad = entity_rows(build_panel(_jump_bars(path), second_source=other), "EINE222A01011")
    assert bad.loc[5, "quality_flags"] == "suspect"
    agree = other.assign(close=140.2)
    ok = entity_rows(build_panel(_jump_bars(path), second_source=agree), "EINE222A01011")
    assert ok.loc[5, "quality_flags"] == "" and ok.loc[5, "px_idx"] == pytest.approx(1.4)


def test_demerger_factor_applied_and_flagged_unverified() -> None:
    days = bdays(6)
    bars = series_bars("CONG", "INE333A01011", days[:3], [200.0, 200.0, 200.0])
    bars += [bar("CONG", "INE333A01011", days[3], 141.0, 140.0), bar("CONG", "INE333A01011", days[4], 142.0, 141.0),
             bar("CONG", "INE333A01011", days[5], 140.0, 142.0)]
    p = entity_rows(build_panel(bars), "EINE333A01011")
    assert implied_f(p, 3) == pytest.approx(0.7)
    assert p.loc[3, "event"] == "ca_unverified" and p.loc[3, "quality_flags"] == "ca_unverified"
    assert not bool(p["quality_flags"].eq("suspect").any())
    assert p.loc[3, "px_idx"] == pytest.approx(141.0 / 140.0)


def test_row_accounting() -> None:
    assert adj.check_drops("ok", 1000, 980) == pytest.approx(0.02)
    with pytest.raises(adj.RowAccountingError):
        adj.check_drops("bad", 1000, 979)
    rows = pd.DataFrame([bar("A", "I1", date(2024, 1, 1), 10.0, 10.0), bar("B", "I2", date(2024, 1, 1), 10.0, 10.0)])
    rows.loc[1, "high"] = 5.0  # high below close
    rows = rows.assign(turnover_inr=1.0, trades=1.0, source="nse_bhavcopy")
    kept, dropped = adj.quality_filter(rows)
    assert dropped == 1 and kept["symbol"].tolist() == ["A"]


# ── linking, store and gap-fill ─────────────────────────────────────────────

DAYS = bdays(300)  # 2023-06-01 .. 2024-07; crosses the UDiFF switch
SPLIT_AT = 270  # mid-June 2024
RENAME_AT = 150


def _three_entities(days: list[date] = DAYS) -> list[dict]:
    rng = np.random.default_rng(7)
    n = len(days)
    aaa = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    bars = series_bars("AAA", "INE000A01011", days, aaa.tolist(), vol=50_000)
    spl = 500 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    for i, d in enumerate(days):
        if i < SPLIT_AT:
            bars.append(bar("SPL", "INE000B01011", d, spl[i], spl[i - 1] if i else None, 20_000))
        else:  # 10:1 face-value split: new ISIN, same symbol, PREVCLOSE / 10
            prev = spl[i - 1] / 10
            bars.append(bar("SPL", "INE000B01029", d, spl[i] / 10, prev, 200_000))
    ren = 300 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    for i, d in enumerate(days):
        sym = "OLDNAME" if i < RENAME_AT else "NEWNAME"
        bars.append(bar(sym, "INE000C01011", d, ren[i], ren[i - 1] if i else None, 30_000))
    return bars


@pytest.fixture(scope="module")
def backfilled(tmp_path_factory: pytest.TempPathFactory):
    root = tmp_path_factory.mktemp("store")
    book = bhav_for(_three_entities())
    store.backfill(DAYS[0], DAYS[-1], data_dir=root, fetch=fake_fetch(book))
    return root, store.load_panel(source="store", data_dir=root)


def test_face_value_split_is_one_continuous_entity(backfilled) -> None:
    root, panel = backfilled
    assert sorted(panel["entity_id"].unique()) == ["EINE000A01011", "EINE000B01011", "EINE000C01011"]
    spl = entity_rows(panel, "EINE000B01011")
    assert len(spl) == len(DAYS) and bool(spl["isin"].eq("INE000B01029").all())
    assert implied_f(spl, SPLIT_AT) == pytest.approx(0.1)
    assert bool(spl["px_idx"].notna().all()) and spl.loc[SPLIT_AT, "event"] == "ca_unverified"
    assert not bool(panel["quality_flags"].isin(["delisted", "suspect"]).any())
    # continuous index: the split day's index return equals the raw split-adjusted return
    assert spl.loc[SPLIT_AT, "px_idx"] / spl.loc[SPLIT_AT - 1, "px_idx"] == pytest.approx(
        spl.loc[SPLIT_AT, "close"] / spl.loc[SPLIT_AT, "prev_close"])
    ep = store.load_entities(root)
    assert ep.loc[ep["isin"] == "INE000B01029", "link_reason"].item() == "isin_change"
    mem = universe.membership(panel)
    july = mem[(mem["entity_id"] == "EINE000B01011") & (mem["date"] >= "2024-07-01")]
    assert len(july) > 0 and bool(july["in_universe"].all())
    assert mem.attrs["universe_quality"] == "pit"


def test_rename_is_one_entity(backfilled) -> None:
    root, panel = backfilled
    ren = entity_rows(panel, "EINE000C01011")
    assert len(ren) == len(DAYS) and bool(ren["symbol"].eq("NEWNAME").all())
    assert store.resolve_entity(symbol="OLDNAME", data_dir=root) == "EINE000C01011"
    assert store.resolve_entity(symbol="newname.ns", data_dir=root) == "EINE000C01011"
    assert store.resolve_entity(isin="INE000B01011", as_of=DAYS[10], data_dir=root) == "EINE000B01011"
    assert store.resolve_entity(symbol="NOPE", data_dir=root) is None
    ep = store.load_entities(root)
    assert ep.loc[ep["symbol"] == "NEWNAME", "link_reason"].item() == "symbol_change"


def test_both_identifiers_changing_starts_a_new_entity() -> None:
    days = bdays(4)
    bars = series_bars("XOLD", "INE444A01011", days[:2], [50.0, 50.0])
    bars += series_bars("XNEW", "INE444A01029", days[2:], [50.0, 51.0])
    panel = build_panel(bars)
    assert panel["entity_id"].nunique() == 2


def test_manifest_has_sha256(backfilled) -> None:
    root, _ = backfilled
    entries = store.read_manifest(root)
    assert len(entries) == len(DAYS)
    for e in entries[:5] + entries[-5:]:
        assert e["sha256"] == hashlib.sha256((root / e["path"]).read_bytes()).hexdigest()


class FakeYF:
    def __init__(self, closes: dict[tuple[str, date], float]) -> None:
        self.closes = closes

    def bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        c = self.closes.get((symbol, start))
        if c is None:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        return pd.DataFrame({"date": [pd.Timestamp(start)], "open": [c], "high": [c], "low": [c], "close": [c], "volume": [1e4]})

    def actions(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame(columns=["date", "dividend", "split"])


def test_gap_fill_repairs_middle_date_and_replaces_fallback(tmp_path) -> None:
    days = bdays(6, start=date(2024, 9, 2))
    bars = series_bars("AAA", "INE000A01011", days, [100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
    bars += series_bars("BBB", "INE000D01011", days, [50.0, 50.5, 51.0, 51.5, 52.0, 52.5])
    book = bhav_for(bars)
    first = {d: book[d] for d in (days[0], days[2])}
    r1 = store.ensure_sessions(days[2], data_dir=tmp_path, fetch=fake_fetch(first), min_eq_rows=1)
    assert r1.added == [days[0], days[2]] and not r1.failed
    r2 = store.ensure_sessions(days[2], data_dir=tmp_path, fetch=fake_fetch(book), min_eq_rows=1)
    assert r2.added == [days[1]]
    panel = store.load_panel(source="store", data_dir=tmp_path)
    assert sorted(panel["date"].dt.date.unique()) == days[:3]
    assert entity_rows(panel, "EINE000A01011")["px_idx"].tolist() == pytest.approx([1.0, 1.01, 1.02])

    added = store.add_fallback(days[3], ["AAA", "BBB.NS"], data_dir=tmp_path, yf=FakeYF({("AAA", days[3]): 103.2}))
    assert added == ["AAA"]
    fb = store.load_panel(days[3], days[3], data_dir=tmp_path)
    assert fb["source"].tolist() == ["yfinance"] and bool(fb["prev_close"].isna().all())
    assert fb["quality_flags"].tolist() == ["fallback"]

    r3 = store.ensure_sessions(days[3], data_dir=tmp_path, fetch=fake_fetch(book), min_eq_rows=1)
    assert r3.added == [days[3]] and r3.replaced_fallback == [days[3]]
    real = store.load_panel(days[3], days[3], data_dir=tmp_path)
    assert bool(real["source"].eq("nse_bhavcopy").all()) and bool(real["prev_close"].notna().all()) and len(real) == 2

    r4 = store.ensure_sessions(days[5], data_dir=tmp_path, fetch=fake_fetch(book, fail=frozenset({days[4]})), min_eq_rows=1)
    assert r4.added == [days[5]] and list(r4.failed) == [days[4]] and r4.incomplete
    assert days[4] not in r4.no_session


def test_gap_fill_too_many_bad_rows_raises(tmp_path) -> None:
    d = date(2024, 9, 2)
    bars = [bar(f"S{i:03d}", f"INE{i:03d}A01011", d, 100.0, 100.0) for i in range(100)]
    for b in bars[:3]:
        b["high"] = 1.0  # 3% of the file fails the OHLC check
    with pytest.raises(adj.RowAccountingError):
        store.ensure_sessions(d, data_dir=tmp_path, fetch=fake_fetch(bhav_for(bars)), min_eq_rows=1)



class CountingEmptyYF(FakeYF):
    def __init__(self) -> None:
        super().__init__({})
        self.calls: list[tuple[str, date]] = []

    def bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        self.calls.append((symbol, start))
        return super().bars(symbol, start, end)


def test_cross_check_caches_misses_and_reaches_every_candidate(tmp_path) -> None:
    days = bdays(150)
    cands = pd.DataFrame({"symbol": [f"S{i:03d}" for i in range(150)],
                          "date": pd.to_datetime(days).astype("datetime64[ns]")})
    yf1, yf2, yf3 = CountingEmptyYF(), CountingEmptyYF(), CountingEmptyYF()
    store._refresh_second(tmp_path, cands, yf1)
    store._refresh_second(tmp_path, cands, yf2)
    store._refresh_second(tmp_path, cands, yf3)
    assert len(yf1.calls) == store._YF_CAP_PER_RUN and len(yf2.calls) == 50 and not yf3.calls
    assert set(yf1.calls).isdisjoint(yf2.calls) and len(set(yf1.calls) | set(yf2.calls)) == 150
    cache = store._load_second(tmp_path)
    assert len(cache) == 150 and bool(cache["close"].isna().all()) and bool(cache["fetched_at"].notna().all())
    # a cached miss never marks a row suspect
    assert adj._lookup(cands, cache, ["symbol", "date"], "close").isna().all()


def test_backfill_skips_a_bad_file_and_fails_closed_on_schema(tmp_path) -> None:
    days = bdays(5, start=date(2024, 9, 2))
    bars = series_bars("AAA", "INE000A01011", days, [100.0, 101.0, 102.0, 103.0, 104.0])
    book = bhav_for(bars)
    book[days[2]] = b"<html><body>Service unavailable</body></html>"
    panel = store.backfill(days[0], days[-1], data_dir=tmp_path, fetch=fake_fetch(book))
    assert sorted(panel["date"].dt.date.unique()) == [d for i, d in enumerate(days) if i != 2]
    assert list(panel.attrs["backfill_failed"]) == [days[2]]
    assert "BadBhavcopyFile" in panel.attrs["backfill_failed"][days[2]]

    text = zipfile.ZipFile(io.BytesIO(bhav_for(bars)[days[2]])).read("bhav.csv").decode()
    book[days[2]] = _zip(text.replace("PrvsClsgPric", "Something", 1))
    with pytest.raises(bhavcopy.BhavcopySchemaError):
        store.backfill(days[0], days[-1], data_dir=tmp_path, fetch=fake_fetch(book))

def test_data_sha256_tracks_content(backfilled) -> None:
    _, panel = backfilled
    h = store.data_sha256(panel)
    assert h == store.data_sha256(panel.sample(frac=1.0, random_state=1))
    changed = panel.copy()
    changed.loc[0, "close"] += 1
    assert store.data_sha256(changed) != h
    assert len(store.sessions(panel)) == len(DAYS)


# ── universe ────────────────────────────────────────────────────────────────


def test_select_members_buffer() -> None:
    ranks = pd.Series({f"E{i:03d}": float(i) for i in range(1, 261)})
    prev = {f"E{i:03d}" for i in range(1, 200)} | {"E241"}
    out = universe.select_members(ranks, prev, 200, 240)
    assert len(out) == 200 and "E241" not in out and "E200" in out
    # a member ranked 230 stays when fewer than 200 members rank above it
    prev = {f"E{i:03d}" for i in range(1, 150)} | {"E230"}
    out = universe.select_members(ranks, prev, 200, 240)
    assert len(out) == 200 and "E230" in out and "E201" not in out


def _liquid_panel(n_ent: int = 230, n_days: int = 320, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.DatetimeIndex(pd.bdate_range("2022-01-03", periods=n_days)).astype("datetime64[ns]")
    ent = np.repeat([f"E{i:03d}" for i in range(n_ent)], n_days)
    level = np.repeat(rng.lognormal(16, 1, n_ent), n_days)
    turnover = level * rng.lognormal(0, 0.3, n_ent * n_days)
    return pd.DataFrame({
        "date": np.tile(days, n_ent), "entity_id": ent, "close": 100.0, "volume": turnover / 100.0,
        "turnover_inr": turnover, "source": "nse_bhavcopy",
    })


def test_universe_is_exactly_200_and_point_in_time() -> None:
    panel = _liquid_panel()
    mem = universe.membership(panel)
    counts = pd.Series(mem.loc[mem["date"] >= "2023-02-01"].groupby("date")["in_universe"].sum())
    assert len(counts) > 0 and bool((counts == 200).all())
    assert not mem.loc[mem["date"] < "2022-12-01", "in_universe"].any()  # under 252 sessions of history

    cut = pd.Timestamp("2023-02-28")  # last session of February: the March universe uses data up to here
    rng = np.random.default_rng(11)
    later = panel["date"] > cut
    shocked = panel.copy()
    shocked.loc[later, "turnover_inr"] *= rng.uniform(0.01, 100.0, later.sum())
    shocked.loc[later, "volume"] = rng.integers(0, 2, later.sum()) * 1000.0
    shocked.loc[later, "close"] *= 1.5
    march = (mem["date"] >= "2023-03-01") & (mem["date"] <= "2023-03-31")
    mem2 = universe.membership(shocked)
    pd.testing.assert_frame_equal(mem[march].reset_index(drop=True), mem2[march].reset_index(drop=True))


def test_crash_keeps_membership() -> None:
    bars = _three_entities()
    for b in bars:  # AAA falls 28% on the split day and stays down
        if b["symbol"] == "AAA" and b["date"] >= DAYS[SPLIT_AT]:
            for k in ("open", "high", "low", "close", "prev_close"):
                b[k] *= 0.72
    bars[SPLIT_AT]["prev_close"] /= 0.72  # PREVCLOSE is the real pre-crash close
    panel = build_panel(bars)
    aaa = entity_rows(panel, "EINE000A01011")
    assert not bool(aaa["quality_flags"].eq("suspect").any()) and bool(aaa["px_idx"].notna().all())
    assert aaa.loc[SPLIT_AT, "px_idx"] / aaa.loc[SPLIT_AT - 1, "px_idx"] == pytest.approx(
        aaa.loc[SPLIT_AT, "close"] / aaa.loc[SPLIT_AT, "prev_close"])
    assert aaa.loc[SPLIT_AT, "close"] / aaa.loc[SPLIT_AT, "prev_close"] < 0.75
    mem = universe.membership(panel)
    july = mem[(mem["entity_id"] == "EINE000A01011") & (mem["date"] >= "2024-07-01")]
    assert len(july) > 0 and bool(july["in_universe"].all())


def test_local_csv_is_survivorship_biased(tmp_path) -> None:
    days = bdays(30)
    bars = series_bars("AAA", "x", days, list(np.linspace(100, 110, 30))) + series_bars("BBB", "x", days, [20.0] * 30)
    csv = pd.DataFrame(bars)[["symbol", "date", "open", "high", "low", "close", "volume"]]
    path = tmp_path / "local.csv"
    csv.to_csv(path, index=False)
    panel = store.load_local_csv(path)
    assert list(panel.columns) == store.PANEL_COLUMNS
    assert bool(panel["entity_id"].eq(panel["symbol"]).all()) and bool(panel["isin"].eq(panel["symbol"]).all())
    assert panel.attrs["row_accounting"]["dropped"] == 0
    aaa = entity_rows(panel, "AAA")
    assert aaa["px_idx"].iloc[-1] == pytest.approx(1.1) and aaa["turnover_inr"].iloc[0] == pytest.approx(100.0 * 10_000)
    mem = universe.membership(panel)
    assert mem.attrs["universe_quality"] == "survivorship_biased" and bool(mem["in_universe"].all())
