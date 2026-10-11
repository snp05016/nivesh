import os
import sys
import types

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import evaluate_truth


def test_regime_report_from_metrics_and_no_auto_verdicts(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluate_truth, "OUTPUT_DIR", tmp_path)
    results = {
        "LightGBM": {"mean_hit_rate": 0.5, "mean_brier_score": 0.25, "mean_precision": 0.5},
        "Ablation": {},
        "Regime": {
            "Bull": [{"hit_rate": 0.6, "sharpe": 1.2, "year": 2021}],
            "Bear": [],
            "Sideways": [{"hit_rate": 0.5, "sharpe": 0.1, "year": 2019}],
        },
    }
    evaluate_truth.generate_markdown_reports(results, [types.SimpleNamespace()])

    regime = (tmp_path / "REGIME_ANALYSIS.md").read_text()
    assert "| Bull | 2021 | 0.6000 | 1.20 |" in regime
    assert "| Sideways | 2019 | 0.5000 | 0.10 |" in regime
    assert "| Bear | 0 | n/a | n/a |" in regime
    assert "| Bull | 1 | 0.6000 | 1.20 |" in regime
    assert "eval_results.json" not in regime
    for name in ["MODEL_STRENGTHS.md", "MODEL_WEAKNESSES.md", "FINAL_VERDICT.md"]:
        assert not (tmp_path / name).exists()


def test_baseline_report_tolerates_empty_lgb_results(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluate_truth, "OUTPUT_DIR", tmp_path)
    results = {"LightGBM": {"mean_hit_rate": 0.5, "mean_brier_score": 0.25, "mean_precision": 0.5}}
    evaluate_truth.generate_markdown_reports(results, [])
    assert "| **LightGBM** | 0.5 | N/A |" in (tmp_path / "BASELINE_COMPARISON.md").read_text()
