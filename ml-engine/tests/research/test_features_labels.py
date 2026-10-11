"""Features fv1, labels and factor profile (spec 4.1, 4.2, 4.8, 11.1; package ml-features-labels)."""

from __future__ import annotations

import math
import time
from datetime import date

import numpy as np
import pandas as pd
import pytest
from scipy.stats import rankdata

from research import config
from research.contract import FAMILY_LABELS, FactorProfile
from research.factor_profile import METRICS, display_value, factor_profile
from research.features import (
    DISPLAY_ORIENTATION,
    FEATURES,
    _rsi_wilder,
    cached_raw,
    compute_raw,
    rank,
)
from research.labels import make_labels

N_ENT = 30
N_DAYS = 420


def _chain_px(frame: pd.DataFrame) -> pd.Series:
    """3.4 forward chain per entity: px_t = px_p * close_t / prev_close_t, 1.0 on the first valid row."""
    out = pd.Series(np.nan, index=frame.index)
    for _, g in frame.groupby("entity_id", sort=False):
        px = math.nan
        for i, c, pc in zip(g.index, g["close"], g["prev_close"]):
            if not np.isfinite(c):
                continue
            px = 1.0 if math.isnan(px) else px * c / pc
            out[i] = px
    return out


def _finish(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["entity_id", "date"], kind="mergesort").reset_index(drop=True)
    traded = df["close"].notna()
    # prev_close is the entity's previous traded close (bhavcopy PREVCLOSE).
    df["prev_close"] = df["close"].where(traded).groupby(df["entity_id"]).transform(lambda s: s.ffill().shift(1))
    df["turnover_inr"] = (df["close"] * df["volume"]).where(traded)
    df["px_idx"] = _chain_px(df)
    return df


def make_panel(seed: int = 7, n_ent: int = N_ENT, n_days: int = N_DAYS) -> pd.DataFrame:
    """Synthetic 3.3 panel: market factor, non-traded days, a late listing and a delisting."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-01", periods=n_days)
    mkt = rng.normal(0.0003, 0.01, n_days)
    rows = []
    for k in range(n_ent):
        eid = f"E{k:03d}"
        beta = 0.5 + rng.random()
        r = beta * mkt + rng.normal(0, 0.015, n_days)
        close = 100.0 * (1 + k) * np.exp(np.cumsum(r))
        volume = rng.lognormal(12, 0.5, n_days) * (1 + k)
        close[rng.random(n_days) < 0.02] = np.nan  # non-traded days
        start, end = (60, n_days) if k == 1 else (0, n_days - 80) if k == 2 else (0, n_days)
        for i in range(start, end):
            rows.append({
                "date": dates[i], "entity_id": eid, "isin": f"INE{k:06d}", "symbol": f"S{k}",
                "close": close[i], "volume": volume[i] if np.isfinite(close[i]) else np.nan,
                "event": "", "quality_flags": "" if np.isfinite(close[i]) else "zero_volume",
                "source": "nse_bhavcopy",
            })
    return _finish(pd.DataFrame(rows))


def make_membership(panel: pd.DataFrame, seed: int = 3) -> pd.DataFrame:
    """Monthly-varying membership: about 80% of entities each month."""
    rng = np.random.default_rng(seed)
    keys = panel.loc[:, ["date", "entity_id"]].copy()
    month = keys["date"].dt.to_period("M").astype(str)
    draws = {(m, e): rng.random() < 0.8 for m in month.unique() for e in keys["entity_id"].unique()}
    keys["in_universe"] = [draws[(m, e)] for m, e in zip(month, keys["entity_id"])]
    keys["turnover_rank"] = 1
    return keys


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    return make_panel()


@pytest.fixture(scope="module")
def membership(panel: pd.DataFrame) -> pd.DataFrame:
    return make_membership(panel)


@pytest.fixture(scope="module")
def raw(panel: pd.DataFrame, membership: pd.DataFrame) -> pd.DataFrame:
    return compute_raw(panel, membership)


# ── features ────────────────────────────────────────────────────────────────


def test_feature_catalogue() -> None:
    assert len(FEATURES) == 19
    assert config.FEATURE_VERSION == "fv1"
    assert set(FEATURES.values()) == set(FAMILY_LABELS)
    flipped = {f for f, o in DISPLAY_ORIENTATION.items() if o == -1}
    assert flipped == {"amihud_63", "rev_5", "rev_21"}
    assert all(DISPLAY_ORIENTATION[f] == 1 for f in FEATURES if f not in flipped)


def test_no_look_ahead(panel: pd.DataFrame, membership: pd.DataFrame, raw: pd.DataFrame) -> None:
    """200 random (entity_id, t): bit-identical after truncating after t, and after
    scaling every later price (prev_close included) by 1.5 with random volumes and returns."""
    rng = np.random.default_rng(11)
    dates = pd.DatetimeIndex(panel["date"].unique()).sort_values()
    cuts = rng.choice(dates[260:-5], size=8, replace=False)
    checked = 0
    for t in cuts:
        t = pd.Timestamp(t)
        later = panel["date"] > t
        variants = [(panel.loc[~later], membership.loc[membership["date"] <= t])]
        scaled = panel.copy()
        noise = rng.lognormal(0, 0.03, later.sum())
        for col in ("close",):
            scaled.loc[later, col] = scaled.loc[later, col] * 1.5 * noise
        scaled.loc[later, "volume"] = rng.lognormal(12, 1.0, later.sum())
        scaled = _finish(scaled.drop(columns=["prev_close", "turnover_inr", "px_idx"]))
        # prev_close of the first later row is the (unscaled) close at t; rescale it too.
        first_later = scaled[scaled["date"] > t].groupby("entity_id").head(1).index
        scaled.loc[first_later, "prev_close"] *= 1.5
        scaled["px_idx"] = _chain_px(scaled)
        assert not np.allclose(scaled.loc[scaled["date"] > t, "px_idx"].fillna(0),
                               panel.loc[later, "px_idx"].fillna(0))
        variants.append((scaled, membership))
        at_t = raw.xs(t, level="date")
        sample = rng.choice(at_t.index.to_numpy(), size=25, replace=False)
        for p, mem in variants:
            got = compute_raw(p, mem).xs(t, level="date")
            for eid in sample:
                np.testing.assert_array_equal(got.loc[eid].to_numpy(), at_t.loc[eid].to_numpy())
        checked += len(sample)
    assert checked == 200
    assert at_t.notna().to_numpy().mean() > 0.8  # the check is not vacuous


def test_nan_never_zero(panel: pd.DataFrame, membership: pd.DataFrame) -> None:
    p = panel.copy()
    p.loc[p["entity_id"] == "E005", "turnover_inr"] = np.nan
    gap_day = p.loc[(p["entity_id"] == "E006") & p["px_idx"].notna(), "date"].iloc[300]
    p.loc[(p["entity_id"] == "E006") & (p["date"] == gap_day), "px_idx"] = np.nan
    raw = compute_raw(p, membership)
    for f in ("log_adv_63", "amihud_63", "turnover_ratio_21_126"):
        assert bool(raw.xs("E005", level="entity_id")[f].isna().all())
    assert np.isnan(raw.loc[(gap_day, "E006"), "rev_5"])
    first = raw.groupby(level="entity_id").head(14)  # under 15 observations
    assert np.isnan(first[["vol_21", "vol_63", "rsi_14", "mom_3_1", "beta_252"]].to_numpy()).all()
    ranked = rank(raw, membership)
    assert bool(ranked.xs("E005", level="entity_id")["log_adv_63"].isna().all())
    assert ranked.isna().equals(raw.isna())


def _wilder_reference(px: list[float], period: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(px)
    gains = [max(b - a, 0.0) for a, b in zip(px, px[1:])]
    losses = [max(a - b, 0.0) for a, b in zip(px, px[1:])]
    if len(gains) < period:
        return out
    ag, al = sum(gains[:period]) / period, sum(losses[:period]) / period
    for k in range(period, len(gains) + 1):
        if k > period:
            ag = (ag * (period - 1) + gains[k - 1]) / period
            al = (al * (period - 1) + losses[k - 1]) / period
        out[k] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return out


def test_rsi_wilder() -> None:
    rng = np.random.default_rng(5)
    px = list(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 120))))
    got = _rsi_wilder(pd.DataFrame({"a": px}))["a"].to_numpy()
    ref = _wilder_reference(px)
    assert all(math.isnan(g) for g, r in zip(got, ref) if r is None)
    assert max(abs(g - r) for g, r in zip(got, ref) if r is not None) < 1e-9
    # Below 15 observations: None (NaN); exactly 15: a value.
    assert np.isnan(_rsi_wilder(pd.DataFrame({"a": px[:14]}))["a"]).all()
    assert np.isfinite(_rsi_wilder(pd.DataFrame({"a": px[:15]}))["a"].iloc[-1])
    # No losses: 100.
    assert (_rsi_wilder(pd.DataFrame({"a": np.linspace(1, 2, 40)}))["a"].dropna() == 100.0).all()
    # NaN days are skipped: equals the reference on the valid sequence.
    gapped = px.copy()
    gapped[30] = gapped[31] = np.nan
    got_gap = _rsi_wilder(pd.DataFrame({"a": gapped}))["a"].dropna().to_numpy()
    ref_gap = [r for r in _wilder_reference([x for x in gapped if np.isfinite(x)]) if r is not None]
    assert np.max(np.abs(got_gap - np.array(ref_gap))) < 1e-9


def test_rsi_via_compute_raw_none_below_15(panel: pd.DataFrame, membership: pd.DataFrame,
                                           raw: pd.DataFrame) -> None:
    late = raw.xs("E001", level="entity_id")["rsi_14"].to_numpy()  # listed on session 60
    valid_px = panel.loc[panel["entity_id"] == "E001", "px_idx"].notna().cumsum().to_numpy()
    assert np.isnan(late[valid_px < 15]).all()
    assert np.isfinite(late[valid_px >= 15]).any()


def test_ranks_per_date_only(raw: pd.DataFrame, membership: pd.DataFrame) -> None:
    ranked = rank(raw, membership)
    d = pd.Timestamp(raw.index.get_level_values("date").unique().to_numpy()[300])
    mem_d = membership[(membership["date"] == d) & membership["in_universe"]]["entity_id"]
    day = raw.xs(d, level="date")
    vals = day.loc[day.index.isin(mem_d), "vol_63"].dropna()
    expected = 2 * (rankdata(vals.to_numpy()) - 0.5) / len(vals) - 1
    np.testing.assert_allclose(ranked.xs(d, level="date").loc[vals.index, "vol_63"], expected, rtol=0, atol=1e-12)
    # Changing every other date leaves this date's ranks unchanged.
    other = raw.copy()
    other.loc[other.index.get_level_values("date") != d] *= -3.0
    pd.testing.assert_frame_equal(rank(other, membership).xs(d, level="date"), ranked.xs(d, level="date"))
    # Off-universe rows are placed against the universe distribution.
    off = day.index[~day.index.isin(mem_d)]
    assert len(off) > 0
    ref = day.loc[day.index.isin(mem_d), "vol_63"].dropna().to_numpy()
    for eid in off:
        x = day.at[eid, "vol_63"]
        if np.isfinite(x):
            pct = ((ref < x).sum() + 0.5 * (ref == x).sum()) / ref.size
            assert ranked.loc[(d, eid), "vol_63"] == pytest.approx(2 * pct - 1)


def test_feature_cache(tmp_path, panel: pd.DataFrame, membership: pd.DataFrame, raw: pd.DataFrame) -> None:
    sha = "ab12cd34" + "0" * 56
    first = cached_raw(panel, membership, sha, data_dir=tmp_path)
    assert (tmp_path / "features" / "ab12cd34_fv1.parquet").exists()
    second = cached_raw(panel.iloc[:0], membership, sha, data_dir=tmp_path)  # served from cache
    pd.testing.assert_frame_equal(first, raw)
    pd.testing.assert_frame_equal(second, raw, check_freq=False)


def test_local_csv_speed() -> None:
    path = config.LOCAL_CSV
    if not path.exists():
        pytest.skip("local CSV absent")
    df = pd.read_csv(path, parse_dates=["date"]).rename(columns={"symbol": "entity_id"})
    df = df.sort_values(["entity_id", "date"]).reset_index(drop=True)
    traded = df["volume"] > 0
    df["volume"] = df["volume"].where(traded)
    df["px_idx"] = (df["close"] / df.groupby("entity_id")["close"].transform("first")).where(traded)
    df["turnover_inr"] = (df["close"] * df["volume"]).where(traded)
    mem = df[["date", "entity_id"]].assign(in_universe=True, turnover_rank=1)
    t0 = time.perf_counter()
    feats = compute_raw(df, mem)
    elapsed = time.perf_counter() - t0
    assert len(feats) == len(df)
    assert elapsed < 10.0, f"compute_raw took {elapsed:.1f}s"


# ── labels ──────────────────────────────────────────────────────────────────


def _ramp_panel(n_ent: int = 9, n_days: int = 120, delist: dict[str, int] | None = None) -> pd.DataFrame:
    dates = pd.bdate_range("2022-01-03", periods=n_days)
    rows = []
    for k in range(n_ent):
        stop = (delist or {}).get(f"E{k}", n_days)
        for i in range(stop):
            rows.append({"date": dates[i], "entity_id": f"E{k}", "px_idx": 1.0 + (0.001 + 0.002 * k) * i,
                         "quality_flags": "", "event": ""})
    return pd.DataFrame(rows)


def _all_in(p: pd.DataFrame) -> pd.DataFrame:
    return p[["date", "entity_id"]].assign(in_universe=True, turnover_rank=1)


def test_labels_ramp_equal_px_ratio() -> None:
    p = _ramp_panel()
    lab = make_labels(p, _all_in(p))
    wide = p.pivot(index="date", columns="entity_id", values="px_idx")
    for h in (21, 63):
        expected = (wide.shift(-h) / wide - 1.0).stack().rename(f"ret_{h}")
        got = lab[f"ret_{h}"].dropna()
        np.testing.assert_array_equal(got.to_numpy(), expected.loc[got.index].to_numpy())
        assert got.size == expected.dropna().size
        dates = [pd.Timestamp(x) for x in wide.index.to_numpy()]
        last = lab.xs(dates[-h - 1], level="date")
        assert bool(last[f"label_end_{h}"].eq(dates[-1]).all())
        assert bool(lab.xs(dates[-h], level="date")[f"ret_{h}"].isna().all())  # t+h past the panel end
        assert not bool(lab[f"stale_exit_{h}"].dropna().any())
        # Steeper ramps rose more: ranks follow the entity order; centred uniform target.
        day = lab.xs(dates[0], level="date")
        np.testing.assert_allclose(day[f"rank_{h}"], (np.arange(1, 10) - 0.5) / 9 - 0.5)
        np.testing.assert_allclose(day[f"xs_{h}"], np.log1p(day[f"ret_{h}"]) - np.median(np.log1p(day[f"ret_{h}"])))


def test_labels_delisting_stale_exit() -> None:
    p = _ramp_panel(delist={"E3": 50})
    lab = make_labels(p, _all_in(p))
    dates = pd.bdate_range("2022-01-03", periods=120)
    last_px = 1.0 + 0.007 * 49
    t = 20  # t + 21 = 41 < 50: normal exit
    assert lab.loc[(dates[t], "E3"), "stale_exit_21"] == False  # noqa: E712
    t = 40  # exit row 49, t + 21 = 61: 12 sessions old
    row = lab.loc[(dates[t], "E3")]
    assert row["ret_21"] == pytest.approx(last_px / (1.0 + 0.007 * t) - 1.0, rel=0, abs=1e-15)
    assert row["stale_exit_21"] == True  # noqa: E712
    t = 30  # t + 21 = 51, exit row 49: 2 sessions old, not stale
    assert lab.loc[(dates[t], "E3"), "stale_exit_21"] == False  # noqa: E712


def test_labels_suspect_start_is_nan() -> None:
    p = _ramp_panel()
    p.loc[(p["entity_id"] == "E2") & (p["date"] == p["date"].unique()[10]), "quality_flags"] = "suspect"
    lab = make_labels(p, _all_in(p))
    d = p["date"].unique()[10]
    assert lab.loc[(d, "E2"), ["ret_21", "xs_21", "top_21", "rank_21"]].isna().all()


def test_labels_ignore_dividends(panel: pd.DataFrame, membership: pd.DataFrame) -> None:
    with_div = panel.copy()
    idx = with_div.sample(40, random_state=1).index
    with_div.loc[idx, "event"] = "dividend"
    no_div = with_div.assign(event="")
    pd.testing.assert_frame_equal(make_labels(with_div, membership), make_labels(no_div, membership))


def test_top_half_base_rate(panel: pd.DataFrame, membership: pd.DataFrame) -> None:
    lab = make_labels(panel, membership)
    for h in (21, 63):
        by_day = lab[f"top_{h}"].dropna().groupby(level="date")
        stats = pd.DataFrame({"rate": by_day.mean(), "n": by_day.size()})
        assert len(stats) > 100
        assert ((stats["rate"] - 0.5).abs() <= 1.0 / stats["n"] + 1e-12).all()
    # Only universe members carry labels.
    keys = pd.MultiIndex.from_frame(membership.loc[membership["in_universe"], ["date", "entity_id"]])
    assert lab.index.isin(keys).all()


# ── factor profile ──────────────────────────────────────────────────────────


def test_metric_formats_match_contract_fixtures() -> None:
    from research.export_contract import _FEATURES

    assert list(METRICS) == list(FEATURES)
    for fid, fam, label, unit, decimals, signed, _, _ in _FEATURES:
        assert FEATURES[fid] == fam
        assert METRICS[fid][:4] == (label, unit, decimals, signed)


def test_display_conversions() -> None:
    assert display_value("rev_21", -math.log(1.1)) == pytest.approx(10.0)
    assert display_value("mom_12_1", math.log(1.25)) == pytest.approx(25.0)
    assert display_value("log_adv_63", math.log(4.126e9)) == pytest.approx(412.6)
    assert display_value("amihud_63", math.log(1e9 * 0.0042 / 1e9)) == pytest.approx(0.42)
    assert display_value("vol_63", 0.241) == pytest.approx(24.1)
    assert display_value("rsi_14", 46.0) == 46.0


def _profile_panel() -> pd.DataFrame:
    rng = np.random.default_rng(21)
    dates = pd.bdate_range("2022-01-03", periods=320)
    rows = []
    for k in range(40):
        r = rng.normal(0, 0.004, len(dates))
        if k == 0:  # up exactly 10% over the last 21 sessions
            r[-21:] = math.log(1.1) / 21
        close = 100.0 * np.exp(np.cumsum(r))
        scale = 1000.0 if k == 1 else 1.0  # very high ADV, hence low Amihud
        vol = rng.lognormal(12, 0.3, len(dates)) * scale
        for i, d in enumerate(dates):
            rows.append({"date": d, "entity_id": f"E{k:02d}", "close": close[i], "volume": vol[i],
                         "event": "", "quality_flags": ""})
    return _finish(pd.DataFrame(rows))


def test_factor_profile() -> None:
    p = _profile_panel()
    mem = _all_in(p)
    mem.loc[mem["entity_id"] == "E39", "in_universe"] = False  # one off-universe stock
    raw = compute_raw(p, mem)
    as_of = p["date"].max().date()

    fp = factor_profile(raw, mem, "E01", as_of)
    FactorProfile.model_validate(fp.model_dump())
    assert [f.family for f in fp.families] == list(FAMILY_LABELS)
    assert [f.label for f in fp.families] == list(FAMILY_LABELS.values())
    fam = {f.family: f for f in fp.families}
    assert (fam["liquidity"].pctl.value or 0.0) >= 80.0
    assert fam["liquidity"].pctl.id == "factor.liquidity.pctl"
    adv = next(m for m in fam["liquidity"].metrics if m.feature_id == "log_adv_63")
    assert adv.value.id == "factor.log_adv_63.value" and adv.value.unit == "inr_cr"
    assert adv.pctl.id == "factor.log_adv_63.pctl" and (adv.pctl.value or 0.0) > 95
    amihud = next(m for m in fam["liquidity"].metrics if m.feature_id == "amihud_63")
    assert (amihud.pctl.value or 0.0) > 95  # low Amihud reads as high liquidity
    assert [m.feature_id for f in fp.families for m in f.metrics] == list(FEATURES)

    up = factor_profile(raw, mem, "E00", as_of)
    rev21 = next(m for f in up.families for m in f.metrics if m.feature_id == "rev_21")
    assert rev21.value.value == pytest.approx(10.0, abs=1e-9)
    assert rev21.value.display == "+10.0%"
    assert (rev21.pctl.value or 0.0) > 50

    off = factor_profile(raw, mem, "E39", as_of)
    assert all(f.pctl.status == "ok" for f in off.families)

    missing = factor_profile(raw, mem, "NOPE", as_of)
    for f in missing.families:
        assert f.pctl.status == "unavailable" and f.pctl.reason == "source_unavailable"
        assert all(m.value.value is None and m.pctl.display is None for m in f.metrics)

    early = factor_profile(raw, mem, "E01", p["date"].min().date())
    mom = next(f for f in early.families if f.family == "momentum")
    assert mom.pctl.status == "unavailable" and mom.pctl.reason == "insufficient_history"


def test_factor_profile_date_type_accepts_date() -> None:
    p = _profile_panel()
    raw = compute_raw(p, _all_in(p))
    fp = factor_profile(raw, _all_in(p), "E05", date(2099, 1, 1))  # no rows that day
    assert all(f.pctl.reason == "source_unavailable" for f in fp.families)
