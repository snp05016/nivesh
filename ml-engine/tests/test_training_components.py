import numpy as np
import pytest

from training.calibration import compute_calibration_report
from training.metrics import aggregate_fold_results
from training.validation import generate_splits, WalkForwardConfig

def test_calibration_report_perfect():
    y_true = np.array([0, 0, 1, 1])
    y_prob = np.array([0.1, 0.2, 0.8, 0.9])
    
    report = compute_calibration_report(y_true, y_prob)
    assert "ece" in report
    assert report["ece"] <= 0.20  # Perfect prediction should have low ECE

def test_calibration_report_overconfident():
    y_true = np.array([0, 0, 0, 0])
    y_prob = np.array([0.9, 0.8, 0.85, 0.95]) # Model is very confident but wrong
    
    report = compute_calibration_report(y_true, y_prob)
    high_bucket = next(b for b in report["buckets"] if b["label"] == "high")
    assert high_bucket["count"] == 4
    assert high_bucket["accuracy"] == 0.0
    assert high_bucket["overconfidence"] > 0.8

def test_aggregate_fold_results():
    folds = [
        {"hit_rate": 0.6, "precision": 0.55, "roc_auc": 0.65},
        {"hit_rate": 0.64, "precision": 0.6, "roc_auc": 0.68}
    ]
    
    agg = aggregate_fold_results(folds)
    assert agg["mean_hit_rate"] == 0.62
    assert agg["mean_precision"] == 0.575
    assert agg["mean_roc_auc"] == 0.665

def test_generate_splits():
    import pandas as pd
    
    # Create dummy dataframe spanning 2021 to 2024
    dates = pd.date_range(start="2021-01-01", end="2024-12-31", freq="D")
    df = pd.DataFrame({
        "date": dates,
        "feature1": np.random.randn(len(dates)),
        "direction_20d": np.random.randint(0, 2, size=len(dates))
    })


    # 1. train: 2021, val: 2022 -> Wait, config is not (train=[2021,2022], val=[2023,2024]). 
    # Ah, generate_splits uses pairs of (train_year, val_year). Let's check logic:
    # Actually, config uses pairs: train_val_pairs=[(2021, 2022), (2022, 2023), (2023, 2024)]
    
    config2 = WalkForwardConfig(
        folds=[(2021, 2022), (2022, 2023)],
        min_train_samples=100
    )
    splits2 = generate_splits(df, config2, feature_cols=["feature1"])
    assert len(splits2) == 2
    assert splits2[0].train_end_year == 2021
    assert splits2[0].val_year == 2022
    assert splits2[0].X_train is not None
