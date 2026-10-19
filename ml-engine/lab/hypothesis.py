"""Hypothesis Lab: test whether a cross-sectional relationship in Indian equities is real.

A hypothesis is an FDL program plus a `score` output: "stocks with a higher score
outperform the universe over the next `horizon` sessions". The lab
1. computes features point-in-time (FDL rejects anything known after the decision close),
2. labels each row with the forward return from the NEXT close (a full session of delay),
3. evaluates on non-overlapping rebalance dates inside a liquidity-ranked universe chosen
   with past data only, against three simple baselines and a permutation null,
4. lets a panel of deterministic skeptics try to knock the result down,
5. keeps the last `holdout_months` untouched unless the caller explicitly spends it.
The default answer is "not supported": a result has to survive every critical check.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date

import numpy as np
import pandas as pd
from research.validation import metrics as rm
from scipy import stats as st

from . import stats as ls
from .costs import charges
from .featurelang import FDLError, compile_program, panel_schema

BASELINES = """
base_mom_20 = px_idx / lag(px_idx, 20) - 1
base_rev_5 = -(px_idx / lag(px_idx, 5) - 1)
base_lowvol_20 = -std(log(px_idx / lag(px_idx, 1)), 20)
base_liq_60 = mean(turnover_inr, 60)
"""
BASE_NAMES = ["base_mom_20", "base_rev_5", "base_lowvol_20"]

# Starting points drawn from published anomalies. Each is a hypothesis to test on Indian data,
# not a claim that it works here.
TEMPLATES = [
    {"id": "momentum_12_1", "title": "12-1 month momentum", "score": "mom_12_1", "horizon": 20,
     "program": "mom_12_1 = lag(px_idx, 21) / lag(px_idx, 252) - 1", "reference": "Jegadeesh & Titman (1993)"},
    {"id": "short_reversal", "title": "One-week reversal", "score": "rev_5", "horizon": 5,
     "program": "rev_5 = -(px_idx / lag(px_idx, 5) - 1)", "reference": "Jegadeesh (1990); Lehmann (1990)"},
    {"id": "low_volatility", "title": "Low volatility", "score": "lowvol_60", "horizon": 20,
     "program": "lowvol_60 = -std(log(px_idx / lag(px_idx, 1)), 60)", "reference": "Ang, Hodrick, Xing & Zhang (2006)"},
    {"id": "near_52w_high", "title": "Nearness to 52-week high", "score": "near_high", "horizon": 20,
     "program": "near_high = px_idx / max(px_idx, 252)", "reference": "George & Hwang (2004)"},
    {"id": "amihud_illiquidity", "title": "Amihud illiquidity", "score": "illiq_20", "horizon": 20,
     "program": "illiq_20 = mean(abs(px_idx / lag(px_idx, 1) - 1) / turnover_inr, 20) * 1000000000", "reference": "Amihud (2002)"},
    {"id": "abnormal_volume", "title": "High-volume return premium", "score": "abn_vol", "horizon": 20,
     "program": "abn_vol = volume / mean(volume, 60)", "reference": "Gervais, Kaniel & Mingelgrin (2001)"},
    {"id": "max_effect", "title": "Lottery-like stocks (MAX)", "score": "neg_max", "horizon": 20,
     "program": "neg_max = -max(px_idx / lag(px_idx, 1) - 1, 20)", "reference": "Bali, Cakici & Whitelaw (2011)"},
]
SLIPPAGE_BPS_PER_SIDE = 10.0  # assumption for liquid large caps; shown in the report


@dataclass
class Spec:
    question: str
    program: str
    score: str
    start: date
    end: date
    horizon: int = 5
    direction: int = 1  # +1: higher score expected to outperform; -1: lower score
    universe_n: int = 50
    min_names: int = 15
    n_quantiles: int = 5
    filter: str | None = None  # an FDL output; rows with filter <= 0 are excluded
    holdout_months: int = 12
    use_holdout: bool = False
    trials_so_far: int = 1  # experiments this researcher has already run (multiple testing)
    permutations: int = 300
    seed: int = 7

    def validate(self) -> None:
        if self.horizon not in (1, 5, 10, 20, 60):
            raise ValueError("horizon must be one of 1, 5, 10, 20, 60 sessions")
        if self.direction not in (1, -1):
            raise ValueError("direction must be 1 or -1")
        if not (5 <= self.universe_n <= 500 and 5 <= self.min_names <= self.universe_n):
            raise ValueError("universe_n in [5, 500] and min_names in [5, universe_n]")
        if self.end <= self.start:
            raise ValueError("end must be after start")


@dataclass
class Finding:
    agent: str
    status: str  # pass | warn | fail
    finding: str
    evidence: dict = field(default_factory=dict)
    critical: bool = False


# ---------------------------------------------------------------- core evaluation
def _evaluate(df: pd.DataFrame, col: str, spec: Spec, rt_cost: float) -> dict:
    """Per-rebalance IC, top-quantile excess and turnover for one score column."""
    rows, prev_top = [], None
    for d, g in df.groupby("date", sort=True):
        g = g.dropna(subset=[col, "fwd_x"])
        if len(g) < spec.min_names:
            continue
        s = g[col] * (spec.direction if col == "score" else 1)
        ic = st.spearmanr(s, g["fwd_x"]).statistic
        q = pd.qcut(s.rank(method="first"), spec.n_quantiles, labels=False)
        top = set(g.loc[q == spec.n_quantiles - 1, "ent"])
        bot_x = float(g.loc[q == 0, "fwd_x"].mean())
        top_x = float(g.loc[q == spec.n_quantiles - 1, "fwd_x"].mean())
        turn = 1.0 if prev_top is None else len(top - prev_top) / max(len(top), 1)
        prev_top = top
        rows.append({"date": d, "ic": float(ic), "top_x": top_x, "spread": top_x - bot_x, "turnover": turn,
                     "top_net": top_x - turn * rt_cost, "n": len(g)})
    return {"rows": pd.DataFrame(rows)}


def _summary(ev: pd.DataFrame, spec: Spec) -> dict:
    if ev.empty:
        return {"periods": 0}
    ppy = 252 / spec.horizon
    ic = ev["ic"].to_numpy()
    net = ev["top_net"].to_numpy()
    block = max(2, round(len(ic) ** (1 / 3)))
    sr = float(net.mean() / net.std(ddof=1)) if len(net) > 2 and net.std(ddof=1) > 0 else math.nan
    return {
        "periods": len(ev), "mean_names": round(float(ev["n"].mean()), 1),
        "mean_ic": round(float(ic.mean()), 4), "ic_hac_t": _r(rm.hac_t(ic, 1)),
        "ic_ci95": [_r(x) for x in rm.block_bootstrap_ci(ic, block, reps=2000, seed=spec.seed)],
        "ic_positive_share": round(float((ic > 0).mean()), 3),
        "top_excess_gross_per_period": round(float(ev["top_x"].mean()), 5),
        "top_excess_net_per_period": round(float(net.mean()), 5),
        "top_minus_bottom_per_period": round(float(ev["spread"].mean()), 5),
        "avg_turnover": round(float(ev["turnover"].mean()), 3),
        "net_sharpe_ann": _r(sr * math.sqrt(ppy)) if not math.isnan(sr) else None,
        "net_sharpe_ci95": _ci(ls.sharpe_ci(net, periods_per_year=int(round(ppy)))) if len(net) > 5 else None,
        "_sr_period": sr,
    }


def _permutation_p(df: pd.DataFrame, spec: Spec, observed: float) -> float:
    rng = np.random.default_rng(spec.seed)
    groups = [g.dropna(subset=["score", "fwd_x"]) for _, g in df.groupby("date", sort=True)]
    groups = [(g["score"].to_numpy() * spec.direction, g["fwd_x"].rank().to_numpy()) for g in groups if len(g) >= spec.min_names]
    if not groups:
        return math.nan
    ranked = [(st.rankdata(s), y) for s, y in groups if np.ptp(s) > 0 and np.ptp(y) > 0]
    if not ranked:
        return math.nan
    null = np.empty(spec.permutations)
    for i in range(spec.permutations):
        null[i] = np.mean([np.corrcoef(rng.permutation(s), y)[0, 1] for s, y in ranked])
    return float((1 + (null >= observed).sum()) / (1 + spec.permutations))


# ---------------------------------------------------------------- driver
def run_experiment(spec: Spec, panel: pd.DataFrame, provenance: dict | None = None) -> dict:
    spec.validate()
    provenance = provenance or {}
    try:
        prog = compile_program(spec.program + "\n" + BASELINES, panel_schema())
    except FDLError as e:
        return {"status": "invalid", "error": str(e), "available_fields": sorted(panel_schema())}
    if spec.score not in prog.outputs:
        return {"status": "invalid", "error": f"score {spec.score!r} is not defined by the program", "available_fields": sorted(panel_schema())}
    if spec.filter and spec.filter not in prog.outputs:
        return {"status": "invalid", "error": f"filter {spec.filter!r} is not defined by the program"}

    ent = "entity_id" if "entity_id" in panel.columns else "symbol"
    lo = pd.Timestamp(spec.start) - pd.Timedelta(days=550)
    p = panel.loc[(panel["date"] >= lo) & (panel["date"] <= pd.Timestamp(spec.end)) & (panel["volume"].fillna(0) > 0)].copy()
    feats = prog.run(p, entity=ent)
    p = p.sort_values([ent, "date"])
    g = p.groupby(ent)["px_idx"]
    p["fwd"] = g.shift(-(spec.horizon + 1)) / g.shift(-1) - 1  # enter at the next close, hold `horizon` sessions
    df = feats.merge(p[["date", ent, "fwd"]], on=["date", ent], how="left").rename(columns={ent: "ent", spec.score: "score"})
    df = df.loc[df["date"] >= pd.Timestamp(spec.start)]
    if spec.filter:
        df = df.loc[df[spec.filter] > 0]

    sessions = np.sort(df["date"].unique())
    holdout_from = pd.Timestamp(spec.end) - pd.DateOffset(months=spec.holdout_months)
    reb = set(sessions[:: spec.horizon])
    df = df.loc[df["date"].isin(reb)]
    # Point-in-time liquid universe per rebalance date (trailing 60-session traded value).
    df["liq_rank"] = df.groupby("date")["base_liq_60"].rank(ascending=False)
    df = df.loc[df["liq_rank"] <= spec.universe_n]
    df["fwd_x"] = df["fwd"] - df.groupby("date")["fwd"].transform("mean")
    research, holdout = df.loc[df["date"] < holdout_from], df.loc[df["date"] >= holdout_from]

    rt_cost = _round_trip_cost(spec.end)
    ev = _evaluate(research, "score", spec, rt_cost)["rows"]
    summ = _summary(ev, spec)
    report: dict = {
        "status": "ok", "spec": {**asdict(spec), "start": spec.start.isoformat(), "end": spec.end.isoformat()},
        "fingerprint": prog.fingerprint, "lineage": sorted(prog.lineage(spec.score)), "warmup_bars": prog.warmup(spec.score),
        "availability": prog.availability(spec.score),
        "research_window": [str(pd.Timestamp(sessions[0]).date()) if len(sessions) else None, str(holdout_from.date())],
        "holdout_window": [str(holdout_from.date()), spec.end.isoformat()],
        "costs": {"round_trip": round(rt_cost, 5), "slippage_bps_per_side": SLIPPAGE_BPS_PER_SIDE, "note": "Statutory charges from the dated schedule plus an assumed slippage."},
        "result": summ, "provenance": provenance,
        "series": [{"date": str(pd.Timestamp(d).date()), "ic": round(float(i), 4), "top_net": round(float(n), 5)}
                   for d, i, n in zip(ev.get("date", []), ev.get("ic", []), ev.get("top_net", []))],
    }
    if summ.get("periods", 0) < 12:
        report["status"] = "insufficient_data"
        report["verdict"] = {"label": "insufficient_data", "text": f"Only {summ.get('periods', 0)} usable rebalance dates; at least 12 are needed to say anything."}
        return report

    perm_p = _permutation_p(research, spec, float(ev["ic"].mean()))
    base = {}
    for b in BASE_NAMES:
        bev = _evaluate(research, b, spec, rt_cost)["rows"]
        joined = ev.set_index("date")["ic"].align(bev.set_index("date")["ic"], join="inner")
        diff = (joined[0] - joined[1]).to_numpy()
        base[b] = {"mean_ic": round(float(bev["ic"].mean()), 4), "top_excess_net_per_period": round(float(bev["top_net"].mean()), 5),
                   "ic_diff_mean": round(float(diff.mean()), 4), "ic_diff_t": _r(rm.hac_t(diff, 1))}
    incr = _incremental_ic(research, spec)
    years = ev.assign(y=pd.to_datetime(ev["date"]).dt.year).groupby("y")["ic"].mean()
    regime = _regime_split(research, ev, spec)
    n_trials = max(spec.trials_so_far, 1)
    T = summ["periods"]
    sr = summ["_sr_period"]
    sr0 = rm.expected_max_sr(1.0 / T, max(n_trials, 2)) if n_trials > 1 else 0.0
    dsr = ls.probabilistic_sharpe(sr, sr0, T) if not math.isnan(sr) else math.nan
    parity = _parity(prog, p, ent, spec)

    report["result"].pop("_sr_period", None)
    report.update({
        "permutation_p": _r(perm_p), "baselines": base, "incremental_ic": incr,
        "ic_by_year": {int(k): round(float(v), 4) for k, v in years.items()}, "regimes": regime,
        "deflated_sharpe": {"value": _r(dsr), "trials": n_trials, "note": "Probability the net Sharpe beats the best of N unskilled trials (Bailey & Lopez de Prado 2014); trial variance taken as the null sampling variance 1/T."},
    })
    findings = _skeptics(spec, summ, perm_p, base, incr, years, regime, dsr, parity, provenance, rt_cost)
    report["skeptics"] = [asdict(f) for f in findings]
    report["verdict"] = _verdict(findings)
    if spec.use_holdout:
        hev = _evaluate(holdout, "score", spec, rt_cost)["rows"]
        hs = _summary(hev, spec)
        hs.pop("_sr_period", None)
        report["holdout"] = {"result": hs, "note": "The holdout is single-use: any change to the hypothesis after looking at it turns it into in-sample data."}
    return report


def _round_trip_cost(d: date) -> float:
    notional = 1_00_000.0
    c = charges("BUY", notional, d)["total"] + charges("SELL", notional, d)["total"]
    return c / notional + 2 * SLIPPAGE_BPS_PER_SIDE / 1e4


def _incremental_ic(df: pd.DataFrame, spec: Spec) -> dict:
    """IC of the score after removing what the three baselines already explain, date by date."""
    ics = []
    for _, g in df.groupby("date"):
        g = g.dropna(subset=["score", "fwd_x", *BASE_NAMES])
        if len(g) < spec.min_names:
            continue
        X = np.column_stack([np.ones(len(g))] + [st.rankdata(g[b]) for b in BASE_NAMES])
        y = st.rankdata(g["score"] * spec.direction)
        resid = y - X @ np.linalg.lstsq(X, y, rcond=None)[0]
        if resid.std() > 0:
            ics.append(st.spearmanr(resid, g["fwd_x"]).statistic)
    if len(ics) < 5:
        return {"periods": len(ics)}
    a = np.asarray(ics)
    return {"periods": len(a), "mean_ic": round(float(a.mean()), 4), "hac_t": _r(rm.hac_t(a, 1)),
            "ci95": [_r(x) for x in rm.block_bootstrap_ci(a, max(2, round(len(a) ** (1 / 3))), reps=2000, seed=spec.seed)]}


def _regime_split(df: pd.DataFrame, ev: pd.DataFrame, spec: Spec) -> dict:
    """IC when the equal-weight universe had risen vs fallen over the previous 20 sessions."""
    mkt = df.groupby("date")["base_mom_20"].mean()
    e = ev.set_index("date")["ic"]
    up = e[mkt.reindex(e.index) > 0]
    dn = e[mkt.reindex(e.index) <= 0]
    return {"market_up": {"periods": len(up), "mean_ic": _r(float(up.mean())) if len(up) else None},
            "market_down": {"periods": len(dn), "mean_ic": _r(float(dn.mean())) if len(dn) else None},
            "definition": "Sign of the universe-average 20-session return at the rebalance date."}


def _parity(prog, p: pd.DataFrame, ent: str, spec: Spec) -> dict:
    """Recompute features on data truncated at a mid-sample date; earlier values must not change."""
    dates = np.sort(p["date"].unique())
    if len(dates) < 50:
        return {"checked": False}
    cut = dates[len(dates) // 2]
    full = prog.run(p, entity=ent)
    part = prog.run(p.loc[p["date"] <= cut], entity=ent)
    a = full.loc[full["date"] <= cut].set_index(["date", ent])[spec.score].sort_index()
    b = part.set_index(["date", ent])[spec.score].sort_index()
    same = bool(np.allclose(a.to_numpy(), b.reindex(a.index).to_numpy(), equal_nan=True))
    return {"checked": True, "cut": str(pd.Timestamp(cut).date()), "identical": same}


def _skeptics(spec, summ, perm_p, base, incr, years, regime, dsr, parity, prov, rt_cost) -> list[Finding]:
    F: list[Finding] = []
    # Leakage Detector
    F.append(Finding("Leakage Detector", "pass" if parity.get("identical", True) else "fail",
                     "Features computed on truncated history match the full-history values (no future data reaches the score)." if parity.get("identical", True)
                     else "Score values changed when future rows were removed: the feature uses information from after the decision date.",
                     parity, critical=True))
    # Data Quality Investigator
    warns = prov.get("warnings", [])
    survivorship = any("survivorship" in w.lower() for w in warns)
    if survivorship:
        text = ("The universe is a list of today's index members, so every stock in it is known to have survived and grown into the index. "
                "Any score that favours small, illiquid or beaten-down names benefits from that hindsight. Rerun on the point-in-time exchange panel before trusting this result.")
    elif warns:
        text = "Dataset caveats apply: " + " ".join(warns)
    else:
        text = "Exchange bhavcopy panel with corporate-action adjustment; no dataset caveats raised."
    F.append(Finding("Data Quality Investigator", "fail" if survivorship else ("warn" if warns else "pass"), text,
                     {"source": prov.get("source"), "mean_names": summ.get("mean_names"), "warnings": warns}, critical=survivorship))
    # Statistical Skeptic
    ci = summ.get("ic_ci95") or [None, None]
    ok = perm_p < 0.05 and (summ.get("ic_hac_t") or 0) > 2 and ci[0] is not None and ci[0] > 0
    F.append(Finding("Statistical Skeptic", "pass" if ok else "fail",
                     "Mean IC is distinguishable from zero (permutation p < 0.05, HAC t > 2, bootstrap CI above 0)." if ok
                     else "Mean IC is not reliably different from zero: the pattern is consistent with noise.",
                     {"mean_ic": summ.get("mean_ic"), "permutation_p": _r(perm_p), "hac_t": summ.get("ic_hac_t"), "ci95": ci}, critical=True))
    # Baseline Challenger
    ici = incr.get("ci95") or [None, None]
    beats = ici[0] is not None and ici[0] > 0
    best = max(base.items(), key=lambda kv: kv[1]["mean_ic"])
    F.append(Finding("Baseline Challenger", "pass" if beats else "fail",
                     "The score keeps predictive power after removing momentum, short-term reversal and low-volatility." if beats
                     else f"Once simple baselines are accounted for, little is left; the strongest baseline here is {best[0]} (mean IC {best[1]['mean_ic']}).",
                     {"incremental": incr, "best_baseline": best[0]}, critical=True))
    # Multiple-testing auditor
    dsr_ok = not math.isnan(dsr) and dsr > 0.95
    F.append(Finding("Multiple-Testing Auditor", "pass" if dsr_ok else ("warn" if spec.trials_so_far <= 1 else "fail"),
                     f"After {spec.trials_so_far} trial(s), the deflated Sharpe ratio is {_r(dsr)}" + (" (above 0.95)." if dsr_ok else "; the more ideas tried, the higher the bar."),
                     {"dsr": _r(dsr), "trials": spec.trials_so_far}, critical=spec.trials_so_far > 1))
    # Regime Robustness Investigator
    yrs = list(years.values)
    share = float(np.mean([y > 0 for y in yrs])) if yrs else 0.0
    up, dn = regime["market_up"]["mean_ic"], regime["market_down"]["mean_ic"]
    robust = share >= 0.6 and (up or 0) > 0 and (dn or 0) > 0
    F.append(Finding("Regime Robustness Investigator", "pass" if robust else "warn",
                     f"IC was positive in {share:.0%} of calendar years; up-market IC {up}, down-market IC {dn}.",
                     {"years_positive_share": round(share, 2)}))
    # Cost and Execution Auditor
    net = summ.get("top_excess_net_per_period") or 0
    gross = summ.get("top_excess_gross_per_period") or 0
    be = gross / summ["avg_turnover"] if summ.get("avg_turnover") else None
    F.append(Finding("Cost and Execution Auditor", "pass" if net > 0 else "fail",
                     f"Top-quantile excess return is {gross:.3%} gross and {net:.3%} net per {spec.horizon}-session period at {summ.get('avg_turnover')} turnover; break-even round-trip cost {be:.3%}." if be is not None
                     else "Turnover could not be measured.",
                     {"round_trip_cost": round(rt_cost, 5), "break_even_round_trip": _r(be)}, critical=True))
    return F


def _verdict(findings: list[Finding]) -> dict:
    crit_fail = [f.agent for f in findings if f.critical and f.status == "fail"]
    stat_fail = any(f.agent == "Statistical Skeptic" and f.status == "fail" for f in findings)
    if not crit_fail:
        label, text = "supported", "The relationship survived every critical check in the research window. It is still a historical finding, not a forecast; the untouched holdout is the next test."
    elif stat_fail:
        label, text = "not_supported", "No reliable evidence: the measured relationship is consistent with chance."
    else:
        label, text = "fragile", "There is a measurable pattern, but it fails: " + ", ".join(crit_fail) + "."
    return {"label": label, "text": text, "failed_checks": crit_fail}


def _r(x, nd: int = 4):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def _ci(d: dict) -> list:
    return [_r(d.get("lo")), _r(d.get("hi"))]


def compare(specs: list[Spec], panel: pd.DataFrame, provenance: dict | None = None) -> dict:
    """Run several candidate hypotheses on the same window and correct for having tried them all.

    Reports each candidate, Holm-adjusted permutation p-values, Romano-Wolf adjusted p-values on
    net top-quantile excess returns, and the probability of backtest overfitting (CSCV) of
    picking the in-sample best. Rejects the "winner" if it does not survive the corrections.
    """
    if not 2 <= len(specs) <= 12:
        raise ValueError("compare between 2 and 12 candidates")
    names = [s.score for s in specs]
    if len(set(names)) != len(names):
        raise ValueError("candidate scores must have distinct names")
    reports = [run_experiment(s, panel, provenance) for s in specs]
    bad = [r for r in reports if r["status"] != "ok"]
    if bad:
        return {"status": "invalid", "reports": reports}
    frames = [pd.Series({x["date"]: x["top_net"] for x in r["series"]}, name=n) for r, n in zip(reports, names)]
    m = pd.concat(frames, axis=1, join="inner").dropna()
    perm = np.array([r.get("permutation_p") if r.get("permutation_p") is not None else 1.0 for r in reports])
    holm_p, _ = ls.holm(perm)
    rw = ls.romano_wolf_stepdown(m.to_numpy(), seed=specs[0].seed) if len(m) >= 10 else np.full(len(names), np.nan)
    blocks = min(16, (len(m) // 4) * 2)
    pbo = rm.pbo_cscv(m.to_numpy(), s=blocks) if blocks >= 4 else math.nan
    best = int(np.argmax(m.mean().to_numpy())) if len(m) else 0
    survives = reports[best]["verdict"]["label"] == "supported" and holm_p[best] < 0.05 and (np.isnan(rw[best]) or rw[best] < 0.05)
    rows = [{"name": n, "verdict": r["verdict"]["label"], "mean_ic": r["result"].get("mean_ic"),
             "net_per_period": r["result"].get("top_excess_net_per_period"), "permutation_p": r.get("permutation_p"),
             "holm_p": _r(holm_p[i]), "romano_wolf_p": _r(rw[i])} for i, (n, r) in enumerate(zip(names, reports))]
    return {
        "status": "ok", "periods": len(m), "candidates": rows, "pbo": _r(pbo),
        "in_sample_best": names[best], "best_survives_corrections": bool(survives),
        "text": _compare_text(names[best], reports[best], holm_p[best], rw[best], survives, pbo),
        "reports": reports,
    }


def _compare_text(name: str, rep: dict, holm_p: float, rw_p: float, survives: bool, pbo: float) -> str:
    if survives:
        why = " and survives the corrections for having tried several candidates."
    else:
        reasons = []
        if rep["verdict"]["label"] != "supported":
            reasons.append(f"its own checks failed ({', '.join(rep['verdict']['failed_checks'])})")
        if holm_p >= 0.05:
            reasons.append(f"Holm-adjusted p = {holm_p:.3f}")
        if not np.isnan(rw_p) and rw_p >= 0.05:
            reasons.append(f"Romano-Wolf p = {rw_p:.3f}")
        why = " but is not supported: " + "; ".join(reasons) + "."
    tail = f" Probability of backtest overfitting across the candidates: {pbo:.0%}." if not math.isnan(pbo) else ""
    return f"{name} looked best in-sample{why}{tail}"
