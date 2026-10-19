from datetime import date

import numpy as np
import pandas as pd

from lab.hypothesis import Spec, run_experiment


def panel(edge: float, n_sym: int = 60, n_days: int = 700, seed: int = 0) -> pd.DataFrame:
    """Synthetic panel. `trades` carries a predictor z_t; returns from t+1 onward load on it with `edge`."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-01-01", periods=n_days)
    z = rng.standard_normal((n_days, n_sym))
    z = pd.DataFrame(z).rolling(10, min_periods=1).mean().to_numpy()  # persistent, so it matters over 5 sessions
    eps = rng.standard_normal((n_days, n_sym)) * 0.015
    r = np.vstack([np.zeros((2, n_sym)), edge * z[:-2] + eps[2:]])  # z at t moves returns from t+2 (after the entry close)
    px = 100 * np.exp(np.cumsum(r, axis=0))
    vol = 1e6 * np.exp(0.3 * rng.standard_normal((n_days, n_sym)))
    rows = []
    for j in range(n_sym):
        for i, d in enumerate(dates):
            c = px[i, j]
            rows.append((d, f"S{j}", f"S{j}", c, c * 1.01, c * 0.99, c, np.nan, vol[i, j] * (1 + j % 7), c * vol[i, j], z[i, j], c))
    cols = ["date", "entity_id", "symbol", "open", "high", "low", "close", "prev_close", "volume", "turnover_inr", "trades", "px_idx"]
    return pd.DataFrame(rows, columns=cols)


def spec(**kw):
    base = dict(question="q", program="s = trades", score="s", start=date(2018, 9, 1), end=date(2020, 9, 30),
                horizon=5, universe_n=60, min_names=30, holdout_months=3, permutations=200)
    base.update(kw)
    return Spec(**base)


def test_planted_edge_is_supported():
    r = run_experiment(spec(), panel(edge=0.004), {"source": "synthetic", "warnings": []})
    assert r["status"] == "ok"
    assert r["result"]["mean_ic"] > 0.05 and r["permutation_p"] < 0.01
    assert r["verdict"]["label"] == "supported", r["verdict"]
    leak = next(f for f in r["skeptics"] if f["agent"] == "Leakage Detector")
    assert leak["status"] == "pass" and leak["evidence"]["identical"]


def test_noise_is_not_supported():
    r = run_experiment(spec(), panel(edge=0.0, seed=3), {"source": "synthetic", "warnings": []})
    assert r["verdict"]["label"] == "not_supported"


def test_direction_flip_turns_edge_negative():
    r = run_experiment(spec(direction=-1), panel(edge=0.004))
    assert r["result"]["mean_ic"] < 0 and r["verdict"]["label"] != "supported"


def test_many_trials_raise_the_bar():
    weak = panel(edge=0.0008, seed=5)
    one = run_experiment(spec(trials_so_far=1), weak)
    many = run_experiment(spec(trials_so_far=200), weak)
    assert many["deflated_sharpe"]["value"] <= one["deflated_sharpe"]["value"]


def test_invalid_programs_are_reported_not_raised():
    p = panel(edge=0.0, n_sym=10, n_days=60)
    assert run_experiment(spec(program="s = delivery_ratio"), p)["status"] == "invalid"
    assert run_experiment(spec(program="s = __import__('os')"), p)["status"] == "invalid"
    assert run_experiment(spec(score="nope"), p)["status"] == "invalid"


def test_holdout_untouched_unless_requested():
    p = panel(edge=0.004)
    assert "holdout" not in run_experiment(spec(), p)
    r = run_experiment(spec(use_holdout=True), p)
    assert r["holdout"]["result"]["periods"] > 0


def test_compare_rejects_noise_winner_and_reports_pbo():
    from lab.hypothesis import compare

    p = panel(edge=0.0, seed=11)
    cands = [spec(program=f"s{i} = mean(volume, {5 + i}) / mean(volume, 60)", score=f"s{i}") for i in range(4)]
    r = compare(cands, p)
    assert r["status"] == "ok" and r["pbo"] is not None
    assert not r["best_survives_corrections"]
    assert all(c["holm_p"] >= c["permutation_p"] for c in r["candidates"])


def test_templates_compile():
    from lab.featurelang import compile_program, panel_schema
    from lab.hypothesis import TEMPLATES

    for t in TEMPLATES:
        prog = compile_program(t["program"], panel_schema())
        assert t["score"] in prog.outputs
