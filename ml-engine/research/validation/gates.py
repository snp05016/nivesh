"""Gates G0-G6 and P, and the artefact evidence tier (spec 5.6; ML-05, D2, D9).

``summary`` is the ``validation.json`` dict (5.8) plus two additive blocks the
gates need and the report shows:

- ``data_checks {drop_share, fold_hashes_identical, manifest_verifies}`` (G0);
- ``rank_ic.positive_period_share``: share of OOS refit periods with mean IC > 0 (G3);
- ``probability.bss_ci95_lockbox`` (P).

Portfolio ``*_monthly_pct`` values are mean monthly **active** returns in percent
(net of costs unless named gross). t* = min(rank_ic.hac_t, rank_ic.nonoverlap_t_median).

Every gate is a list of criteria; a criterion with a missing or non-finite value
fails (fail closed). G7 (live) is applied by the backend, never here; there is no
gate R and no class-share clause.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .. import config

_GATE_IDS = ("G1", "G2", "G3", "G4", "G5", "G6")


def _get(summary: Mapping[str, Any], path: str) -> Any:
    node: Any = summary
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return float(v)


def _ci_low(v: Any) -> float | None:
    return _num(v[0]) if isinstance(v, (list, tuple)) and len(v) == 2 else None


def _row(gid: str, level: str, metric: str, value: Any, op: str, threshold: Any) -> dict[str, Any]:
    if op == "==":
        passed = value is not None and value == threshold
    else:
        v, t = _num(value), _num(threshold)
        passed = v is not None and t is not None and {
            ">=": v >= t, "<=": v <= t, ">": v > t,
        }[op]
    if isinstance(value, float) and not math.isfinite(value):
        value = None
    return {"id": gid, "level": level, "metric": metric, "passed": bool(passed),
            "value": value, "op": op, "threshold": threshold}


def _min_or_none(values: list[float | None]) -> float | None:
    """min of the values, or None when empty or any value is missing (fail closed)."""
    present = [v for v in values if v is not None]
    return min(present) if present and len(present) == len(values) else None


def _criteria(summary: Mapping[str, Any], universe_quality: str, cfg: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    c0 = cfg["G0"]
    rows += [
        _row("G0", "required", "universe_quality", universe_quality, "==", c0["universe_quality"]),
        _row("G0", "required", "drop_share", _get(summary, "data_checks.drop_share"), "<=", c0["max_drop_share"]),
        _row("G0", "required", "fold_hashes_identical", _get(summary, "data_checks.fold_hashes_identical"),
             "==", c0["identical_fold_hashes"]),
        _row("G0", "required", "manifest_verifies", _get(summary, "data_checks.manifest_verifies"),
             "==", c0["manifest_verifies"]),
    ]

    hac, med = _num(_get(summary, "rank_ic.hac_t")), _num(_get(summary, "rank_ic.nonoverlap_t_median"))
    t_star = min(hac, med) if hac is not None and med is not None else None
    paired_t = _get(summary, "vs_best_baseline.t")
    delta_ic = _get(summary, "vs_best_baseline.delta_ic")
    share = _get(summary, "rank_ic.positive_period_share")
    terciles = _get(summary, "slices.vol_tercile")
    tercile_min = (
        _min_or_none([_num(v.get("mean_ic")) if isinstance(v, Mapping) else None for v in terciles.values()])
        if isinstance(terciles, Mapping) and terciles else None
    )
    net = _get(summary, "portfolio.net_monthly_pct")
    b4 = _get(summary, "portfolio.b4_net_monthly_pct")
    for level in ("validated", "weak"):
        c = {gid: cfg[gid][level] for gid in _GATE_IDS}
        rows.append(_row("G1", level, "t_star", t_star, ">=", c["G1"]["min_t_star"]))
        if level == "validated":
            rows.append(_row("G2", level, "paired_t", paired_t, ">=", c["G2"]["min_paired_t"]))
        else:
            rows.append(_row("G2", level, "delta_ic", delta_ic, ">=", c["G2"]["min_delta_ic"]))
        rows.append(_row("G3", level, "positive_period_share", share, ">=", c["G3"]["min_positive_period_share"]))
        if "every_vol_tercile_ic_gt" in c["G3"]:
            rows.append(_row("G3", level, "min_vol_tercile_ic", tercile_min, ">", c["G3"]["every_vol_tercile_ic_gt"]))
        rows.append(_row("G4", level, "net_monthly_pct", net, ">", c["G4"]["net_active_gt"]))
        if "min_dsr" in c["G4"]:
            rows.append(_row("G4", level, "dsr", _get(summary, "portfolio.dsr"), ">=", c["G4"]["min_dsr"]))
        if c["G4"].get("beats_b4"):
            rows.append(_row("G4", level, "net_monthly_pct_vs_b4", net, ">", b4))
        rows.append(_row("G5", level, "pbo", _get(summary, "overfitting.pbo"), "<=", c["G5"]["max_pbo"]))
        if level == "validated":
            rows.append(_row("G6", level, "lockbox_hac_t", _get(summary, "lockbox.hac_t"), ">=", c["G6"]["min_hac_t"]))
            rows.append(_row("G6", level, "lockbox_net_monthly_pct", _get(summary, "lockbox.net_monthly_pct"),
                             ">", c["G6"]["net_active_gt"]))
        else:
            rows.append(_row("G6", level, "lockbox_rank_ic_mean", _get(summary, "lockbox.rank_ic_mean"),
                             ">", c["G6"]["mean_ic_gt"]))

    cp = cfg["P"]
    auc_years = _get(summary, "probability.auc_by_year")
    auc_low = (
        _min_or_none([_ci_low(v.get("ci95")) if isinstance(v, Mapping) else None for v in auc_years.values()])
        if isinstance(auc_years, Mapping) and auc_years else None
    )
    rows += [
        _row("P", "probability", "bss_ci95_low", _ci_low(_get(summary, "probability.bss_ci95")), ">", cp["bss_ci_low_gt"]),
        _row("P", "probability", "bss_ci95_lockbox_low", _ci_low(_get(summary, "probability.bss_ci95_lockbox")),
             ">", cp["bss_ci_low_gt"]),
        _row("P", "probability", "min_auc_ci95_low_by_year", auc_low, ">=", cp["min_auc_ci_low_every_year"]),
        _row("P", "probability", "ece_lockbox", _get(summary, "probability.ece_lockbox"), "<=", cp["max_lockbox_ece"]),
        _row("P", "probability", "n_eff_lockbox", _get(summary, "probability.n_eff_lockbox"), ">=", cp["min_lockbox_n_eff"]),
    ]
    return rows


def evaluate_gates(
    summary: Mapping[str, Any],
    *,
    universe_quality: str,
    horizon: int,
    cfg: Mapping[str, Any] = config.GATES,
) -> dict[str, Any]:
    """``{horizon, gates, tier, reason_codes, probability_display_passed}`` (5.6, 5.8).

    - ``validated_edge`` = G0 and G1..G6 at the validated level.
    - ``weak_evidence`` = not validated, and G0 and G1..G6 at the weak level.
    - Otherwise ``no_reliable_edge``; a non-PIT universe always lands here (D2).
    Reason codes: ``survivorship_biased_universe`` and ``gate_failed:Gx`` for each
    gate that failed at the level the tier fell short of.
    ``probability_display_passed`` needs gate P and a ``validated_edge`` tier (D9).
    """
    rows = _criteria(summary, universe_quality, cfg)

    def ok(gid: str, level: str) -> bool:
        return all(r["passed"] for r in rows if r["id"] == gid and r["level"] == level)

    g0 = ok("G0", "required")
    validated = g0 and all(ok(gid, "validated") for gid in _GATE_IDS)
    weak = g0 and all(ok(gid, "weak") for gid in _GATE_IDS)
    tier = "validated_edge" if validated else "weak_evidence" if weak else "no_reliable_edge"

    reasons: list[str] = []
    if universe_quality != "pit":
        reasons.append("survivorship_biased_universe")
    g0_other = [r for r in rows if r["id"] == "G0" and r["metric"] != "universe_quality" and not r["passed"]]
    if g0_other:
        reasons.append("gate_failed:G0")
    if tier != "validated_edge":
        level = "validated" if tier == "weak_evidence" else "weak"
        reasons += [f"gate_failed:{gid}" for gid in _GATE_IDS if not ok(gid, level)]

    return {
        "horizon": horizon,
        "gates": rows,
        "tier": tier,
        "reason_codes": reasons,
        "probability_display_passed": tier == "validated_edge" and ok("P", "probability"),
    }
