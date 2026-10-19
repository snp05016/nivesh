import pytest
import sys
import os
import pandas as pd
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from training.train_alpha158 import _get_feature_columns
from training.model_registry import _parse_version_date

# The promotion gate itself (ML-05) is tested in test_promotion_gate.py.


def test_version_date_parses_with_and_without_git_suffix():
    assert _parse_version_date("lightgbm_alpha158_20261019_ab12cd3") == "20261019"
    assert _parse_version_date("lightgbm_baseline_alpha158_v1_20260624") == "20260624"
    assert _parse_version_date("unversioned") == "00000000"


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
