"""Nivesh FDL: parser safety, CSE, fingerprint, values, warm-up, availability, truncation parity."""
import numpy as np
import pandas as pd
import pytest
from lab.featurelang import FDLError, compile_program, panel_schema


def schema(**extra):
    s = panel_schema()
    s["delivery_ratio"] = {"dtype": "float", "available": "close"}
    s["ret_fwd_5"] = {"dtype": "float", "available": "close", "future": True}
    s.update(extra)
    return s


def make_panel(seed: int = 0, n_days: int = 300, symbols=("AAA", "BBB", "CCC"), drop: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=n_days)
    frames = []
    for i, sym in enumerate(symbols):
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n_days)))
        frames.append(pd.DataFrame({
            "date": dates, "symbol": sym, "close": close,
            "open": close * np.exp(rng.normal(0, 0.005, n_days)),
            "volume": rng.lognormal(13, 0.5, n_days),
            "delivery_ratio": rng.uniform(0.2, 0.8, n_days),
            "ret_fwd_5": rng.normal(0, 0.05, n_days),
        }).iloc[i * 7:])  # staggered listings
    panel = pd.concat(frames, ignore_index=True)
    if drop:
        panel = panel.drop(panel.sample(frac=drop, random_state=seed).index)
    return panel.sample(frac=1.0, random_state=seed).reset_index(drop=True)  # order must not matter


SPEC_PROGRAM = """
ret_1 = close / lag(close, 1) - 1
ret_5 = close / lag(close, 5) - 1
ret_20 = close / lag(close, 20) - 1
delivery_momentum_5d = mean(delivery_ratio, 5) / mean(delivery_ratio, 20)
vol_20 = std(log(close / lag(close, 1)), 20)
rel_strength = rank(ret_20) - 0.5
z_vol = zscore(volume, 60)
gap = open / lag(close, 1) - 1
ema_12 = ewm(close, 12)
dd_252 = close / max(close, 252) - 1
up = where(ret_1 > 0, 1, -1) * clip(abs(ret_1), 0, 0.05)
mix = demean(ret_5) + cs_zscore(sqrt(volume)) + sign(diff(close, 3)) + corr(ret_1, lag(ret_1, 1), 30)
tail = sum(ret_1 <= -0.02, 10) + min(close, 5) ** 0.5
"""


@pytest.mark.parametrize("src, needle", [
    ("x = __import__('os')", "unknown function '__import__'"),
    ("x = close.shift(-1)", "plain calls"),
    ("x = close.values", "Attribute"),
    ("x = foo(close)", "unknown function 'foo'"),
    ("x = lag(close, 0)", "lag 0 is not a lag"),
    ("x = lag(close, -1)", "negative lags look ahead"),
    ("x = lag(close, 757)", "in [1, 756]"),
    ("x = mean(close, n)", "integer literal"),
    ("x = mean(close, 2.5)", "integer literal"),
    ("x = mean(close, True)", "integer literal"),
    ("x = std(close, 1)", "in [2, 756]"),
    ("x = close[1]", "Subscript"),
    ("x = (lambda: close)()", "plain calls"),
    ("x = lag(x=close, n=1)", "positional"),
    ("x = 'close'", "numeric literal"),
    ("x = close // 2", "BinOp"),
    ("x = close < open < high", "single comparisons"),
    ("import os", "single `name = expression`"),
    ("x = y = close", "single `name = expression`"),
    ("close = open", "shadows a schema field"),
    ("x = close\nx = open", "already defined"),
    ("x = clip(close, 2, 1)", "lo <= hi"),
    ("x = (close", "syntax error"),
])
def test_parser_rejects_unsafe_or_invalid(src, needle):
    with pytest.raises(FDLError) as exc:
        compile_program(src, schema())
    assert needle in str(exc.value)
    assert exc.value.line >= 1


def test_undefined_name_reports_line_and_col():
    src = "a = close / lag(close, 1)\nb = mean(a, 5)\nc = b - ret_99"
    with pytest.raises(FDLError) as exc:
        compile_program(src, schema())
    assert (exc.value.line, exc.value.col) == (3, 9)
    assert "ret_99" in exc.value.message
    with pytest.raises(FDLError) as exc:
        compile_program("a = b + 1\nb = close", schema())
    assert exc.value.line == 1 and "before its definition on line 2" in exc.value.message


def test_cse_dedups_shared_subtrees():
    prog = compile_program(
        "a = lag(close, 1)\nb = close / lag(close, 1) - 1\nc = log(close / lag(close,1))\n"
        "d = close + open\ne = open + close",
        schema(),
    )
    ops = [n.op for n in prog.nodes]
    assert ops.count("lag") == 1 and ops.count("div") == 1 and ops.count("field") == 2 and ops.count("add") == 1
    # close, lag, div, 1, sub, log, open, add
    assert len(prog.nodes) == 8
    assert prog.outputs["d"] == prog.outputs["e"]
    assert all(a < n.id for n in prog.nodes for a in n.args)  # topological


def test_fingerprint_stable_under_formatting_and_semantic():
    a = compile_program("r5 = close / lag(close, 5) - 1\nm = mean(r5, 20)", schema())
    b = compile_program(
        "# momentum\n\nm   =   mean( (close/lag(close,5)) - 1 , 20 )   # same\nr5=(close)/lag(close , 5)-1\n", schema()
    )
    assert a.fingerprint == b.fingerprint
    for other in ("r5 = close / lag(close, 6) - 1\nm = mean(r5, 20)",
                  "r5 = close / lag(close, 5) - 1\nm = mean(r5, 21)",
                  "r5 = close / lag(close, 5) - 1\nm2 = mean(r5, 20)",
                  "r5 = lag(close, 5) / close - 1\nm = mean(r5, 20)"):
        assert compile_program(other, schema()).fingerprint != a.fingerprint


def test_values_match_pandas():
    panel = make_panel(seed=1)
    prog = compile_program(
        "ret_5 = close / lag(close, 5) - 1\nma_10 = mean(close, 10)\nsd_20 = std(ret_5, 20)\n"
        "rel = rank(ret_5)\nema = ewm(close, 12)\nzv = zscore(volume, 60)\nhi = max(close, 30)",
        schema(),
    )
    out = prog.run(panel)
    ref = panel.sort_values(["date", "symbol"]).reset_index(drop=True)
    g = ref.groupby("symbol")["close"]
    ref["ret_5"] = ref["close"] / g.shift(5) - 1
    ref["ma_10"] = g.transform(lambda s: s.rolling(10).mean())
    ref["sd_20"] = ref.groupby("symbol")["ret_5"].transform(lambda s: s.rolling(20).std())
    ref["rel"] = ref.groupby("date")["ret_5"].rank(pct=True)
    ref["ema"] = g.transform(lambda s: s.ewm(span=12, min_periods=12).mean())
    gv = ref.groupby("symbol")["volume"]
    ref["zv"] = (ref["volume"] - gv.transform(lambda s: s.rolling(60).mean())) / gv.transform(lambda s: s.rolling(60).std())
    ref["hi"] = g.transform(lambda s: s.rolling(30).max())
    assert (out["symbol"].to_numpy() == ref["symbol"].to_numpy()).all()
    for col in prog.outputs:
        np.testing.assert_allclose(out[col], ref[col], rtol=1e-9, atol=1e-12, equal_nan=True, err_msg=col)


def test_warmup_counts_and_nans():
    prog = compile_program(
        "m = mean(lag(close, 5), 20)\nvol_20 = std(log(close / lag(close, 1)), 20)\nr = rank(close)\n"
        "dd = close / max(close, 252) - 1\nc = corr(close, lag(volume, 3), 10)",
        schema(),
    )
    assert [prog.warmup(k) for k in ("m", "vol_20", "r", "dd", "c")] == [25, 21, 1, 252, 13]
    out = prog.run(make_panel(seed=2))
    for _, grp in out.groupby("symbol"):
        for name in ("m", "vol_20", "dd", "c"):
            w = prog.warmup(name)
            assert grp[name].iloc[: w - 1].isna().all() and grp[name].iloc[w - 1:].notna().all(), name
    assert prog.lineage("c") == {"close", "volume"}
    assert compile_program("r20 = close / lag(close, 20)\nrs = rank(r20) - 0.5", schema()).lineage("rs") == {"close"}


def test_future_and_late_fields_rejected():
    for src in ("y = ret_fwd_5", "y = lag(ret_fwd_5, 5)", "y = close + 0 * ret_fwd_5"):
        with pytest.raises(FDLError, match="future"):
            compile_program(src, schema())
    late = schema(delivery_ratio={"dtype": "float", "available": "close", "available_lag": 1})
    with pytest.raises(FDLError, match="close of t\\+1") as exc:
        compile_program("x = close\ndm = mean(delivery_ratio, 5) / mean(delivery_ratio, 20)", late)
    assert exc.value.line == 2
    ok = compile_program("dm = mean(lag(delivery_ratio, 1), 5)", late)
    assert ok.availability("dm") == "close of t"
    with pytest.raises(FDLError, match="known at the close of t"):
        compile_program("d = delivery_ratio - lag(delivery_ratio, 1)", late)
    with pytest.raises(FDLError, match="next_open|open of t\\+1"):
        compile_program("x = nxt", schema(nxt={"dtype": "float", "available": "next_open"}))
    assert compile_program("x = lag(nxt, 1)", schema(nxt={"dtype": "float", "available": "next_open"}))
    with pytest.raises(FDLError):  # at the open, today's close is not known yet
        compile_program("r = close / lag(close, 1)", schema(), decision="open")
    assert compile_program("gap = open / lag(close, 1) - 1", schema(), decision="open")
    with pytest.raises(FDLError, match="available_lag"):
        compile_program("x = close", schema(close={"dtype": "float", "available": "close", "available_lag": -1}))


@pytest.mark.parametrize("seed, drop", [(0, 0.0), (1, 0.02), (2, 0.02)])
def test_truncation_parity(seed, drop):
    prog = compile_program(SPEC_PROGRAM, schema())
    panel = make_panel(seed=seed, drop=drop)  # drops = suspended days / gaps
    full = prog.run(panel)
    dates = np.sort(panel["date"].unique())
    rng = np.random.default_rng(seed)
    for cut in [dates[30], dates[260], *rng.choice(dates[1:], 3, replace=False)]:
        part = prog.run(panel[panel["date"] <= cut])
        expect = full[full["date"] <= cut].reset_index(drop=True)
        pd.testing.assert_frame_equal(part, expect, check_exact=True)
    assert full["mix"].notna().any() and (drop or full["dd_252"].notna().any())


def test_cross_sectional_ops_use_same_date_rows_only():
    panel = make_panel(seed=3)
    prog = compile_program("r = rank(close)\nd = demean(close)", schema())
    base = prog.run(panel)
    # Changing one date's prices leaves every other date's ranks untouched.
    day = panel["date"].sort_values().unique()[100]
    bumped = panel.copy()
    bumped.loc[bumped["date"] == day, "close"] *= np.array([1.0, 3.0, 0.1])[: (bumped["date"] == day).sum()]
    other = prog.run(bumped)
    keep = base["date"] != day
    pd.testing.assert_frame_equal(base[keep], other[keep])
    assert not base.loc[~keep, "d"].equals(other.loc[~keep, "d"])


def test_run_rejects_bad_panels():
    prog = compile_program("x = close", schema())
    with pytest.raises(KeyError):
        prog.run(pd.DataFrame({"date": [], "symbol": []}))
    p = make_panel(n_days=5)
    with pytest.raises(ValueError, match="duplicate"):
        prog.run(pd.concat([p, p.head(1)]))
