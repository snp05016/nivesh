import pytest
import sys
import os
import pandas as pd
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from training.train_alpha158 import _get_feature_columns
from training.model_registry import evaluate_deployment_guardrails, list_model_versions

def test_alpha158_features_limit():
    # Construct a dummy dataframe with alpha158 features + extra features + sector
    from config import ALPHA158_FEATURES
    
    cols = ALPHA158_FEATURES + ["momentum_120d", "volatility_60d", "sector_Energy", "rsi_14"]
    df = pd.DataFrame(columns=cols)
    
    feat_cols = _get_feature_columns(df)
    
    # Assert exactly the 158 features are returned, no extras, no sectors
    assert len(feat_cols) == 158
    assert "momentum_120d" not in feat_cols
    assert "sector_Energy" not in feat_cols
    assert "rsi_14" not in feat_cols

def test_guardrails_missing_files(tmp_path, monkeypatch):
    import training.model_registry as mr
    monkeypatch.setattr(mr, "REGISTRY_DIR", tmp_path)
    
    # Test rejection if files missing
    (tmp_path / "candidate" / "v1").mkdir(parents=True)
    res = mr.evaluate_deployment_guardrails("v1", status="candidate")
    assert not res["passed"]
    assert "Missing validation_metrics.json or calibration_report.json" in res["reasons_for_rejection"]

def test_guardrails_thresholds(tmp_path, monkeypatch):
    import json
    import training.model_registry as mr
    monkeypatch.setattr(mr, "REGISTRY_DIR", tmp_path)
    
    dir_path = tmp_path / "candidate" / "v2"
    dir_path.mkdir(parents=True)
    
    # Case 1: Pass
    with open(dir_path / "validation_metrics.json", "w") as f:
        json.dump([{"hit_rate": 0.54}], f)
    with open(dir_path / "calibration_report.json", "w") as f:
        json.dump({"brier_score": 0.2500}, f)
        
    res = mr.evaluate_deployment_guardrails("v2", status="candidate")
    assert res["passed"]
    
    # Case 2: Fail Brier
    with open(dir_path / "calibration_report.json", "w") as f:
        json.dump({"brier_score": 0.2600}, f)
        
    res = mr.evaluate_deployment_guardrails("v2", status="candidate")
    assert not res["passed"]
    assert any("Brier score" in r for r in res["reasons_for_rejection"])
    
    # Case 3: Fail Hit Rate
    with open(dir_path / "validation_metrics.json", "w") as f:
        json.dump([{"hit_rate": 0.52}], f)
    with open(dir_path / "calibration_report.json", "w") as f:
        json.dump({"brier_score": 0.2500}, f)
        
    res = mr.evaluate_deployment_guardrails("v2", status="candidate")
    assert not res["passed"]
    assert any("Hit rate" in r for r in res["reasons_for_rejection"])
