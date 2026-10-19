"""Reproducible run of every hypothesis template, plus the multi-candidate comparison.

    python -m lab.run_templates --source local_csv --out ../docs/platform/experiments/run.json

Records the code revision, dataset provenance and every spec so the run can be repeated.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date

from research.marketdata import store

from .hypothesis import TEMPLATES, Spec, compare, run_experiment
from .loaders import DEV_WARNINGS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["store", "local_csv"], default="store")
    ap.add_argument("--start", default="2019-06-01")
    ap.add_argument("--end", default="2026-06-01")
    ap.add_argument("--universe", type=int, default=49)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    panel = store.load_panel(source=a.source)
    prov = {"source": a.source, "warnings": list(DEV_WARNINGS) if a.source == "local_csv" else [], "rows": len(panel),
            "first": str(panel["date"].min().date()), "last": str(panel["date"].max().date())}
    rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)

    def spec(t: dict, i: int, horizon: int | None = None) -> Spec:
        return Spec(question=t["title"], program=t["program"], score=t["score"], start=start, end=end,
                    horizon=horizon or t["horizon"], universe_n=a.universe, min_names=min(30, a.universe),
                    holdout_months=12, trials_so_far=i, permutations=500)

    out: dict = {"code_revision": rev, "dataset": prov, "runs": []}
    for i, t in enumerate(TEMPLATES, start=1):
        r = run_experiment(spec(t, i), panel, prov)
        out["runs"].append({"template": t["id"], "reference": t["reference"], **r})
        res = r.get("result", {})
        print(f'{t["id"]:20s} h={t["horizon"]:>2} IC={res.get("mean_ic")} CI={res.get("ic_ci95")} p={r.get("permutation_p")} '
              f'net={res.get("top_excess_net_per_period")} DSR={r.get("deflated_sharpe", {}).get("value")} -> {r["verdict"]["label"]}')
    cmp_ = compare([spec(t, 1, horizon=20) for t in TEMPLATES], panel, prov)
    cmp_.pop("reports", None)
    out["compare_h20"] = cmp_
    print(cmp_["text"])
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
