"""
ml-engine configuration — model paths, Alpha158 feature list, model hyperparameters.

All config is centralized here so no magic values leak into pipeline code.
Follows the same pattern as the qlib_engine/ skeleton: constants live in one file,
the microservice references them via import.
"""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent
MODEL_DIR = ROOT_DIR / "models"
DATA_DIR = ROOT_DIR / "data"
CACHE_DIR = ROOT_DIR / "cache"

# Trained model artifacts
LIGHTGBM_MODEL_PATH = MODEL_DIR / "lgb_model.txt"
SCALER_PATH = MODEL_DIR / "feature_scaler.json"

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ── Alpha158 Feature List (referenced from existing qlib_engine research) ──────

# 9 kline-basic factors: candlestick geometry
KLINE_BASIC = [
    "KMID", "KLEN", "KMID2", "KUP", "KUP2",
    "KLOW", "KLOW2", "KSFT", "KSFT2",
]

# 5 windows used across all rolling factors
WINDOWS = [5, 10, 20, 30, 60]

# 4 static price ratios
STATIC_PRICE = ["OPEN0", "HIGH0", "LOW0", "VWAP0"]

# 5 trend sub-groups x 5 windows = 25 factors
TREND_PREFIXES = ["ROC", "MA", "BETA", "RSQR", "RESI"]

# 6 volatility sub-groups x 5 windows = 30 factors
VOLATILITY_PREFIXES = ["STD", "MAX", "MIN", "QTLU", "QTLD", "RSV"]

# 3 extreme-position sub-groups x 5 windows = 15 factors
EXTREME_PREFIXES = ["IMAX", "IMIN", "IMXD"]

# 9 price-volume-statistical sub-groups x 5 windows = 45 factors
PV_STAT_PREFIXES = [
    "CORR", "CORD", "CNTP", "CNTN", "CNTD",
    "SUMP", "SUMN", "SUMD", "RANK",
]

# 2 volume-volatility sub-groups x 5 windows = 10 factors
VOL_VOL_PREFIXES = ["VMA", "VSTD"]

# 4 price-volume-weighted sub-groups x 5 windows = 20 factors
PV_WEIGHT_PREFIXES = ["WVMA", "VSUMP", "VSUMN", "VSUMD"]


def _expand_windowed(prefixes: list[str]) -> list[str]:
    """Expand prefix list into the 5-window factor names."""
    result = []
    for p in prefixes:
        for w in WINDOWS:
            result.append(f"{p}{w}")
    return result


# Complete Alpha158 feature list (158 total)
ALPHA158_FEATURES = (
    KLINE_BASIC
    + STATIC_PRICE
    + _expand_windowed(TREND_PREFIXES)
    + _expand_windowed(VOLATILITY_PREFIXES)
    + _expand_windowed(EXTREME_PREFIXES)
    + _expand_windowed(PV_STAT_PREFIXES)
    + _expand_windowed(VOL_VOL_PREFIXES)
    + _expand_windowed(PV_WEIGHT_PREFIXES)
)

assert len(ALPHA158_FEATURES) == 158, (
    f"Expected 158 Alpha158 features, got {len(ALPHA158_FEATURES)}"
)

# Ordered feature list used by the pipeline
FEATURE_LIST = ALPHA158_FEATURES

# Confidence calibration
CONFIDENCE_CONFIG = {
    "min_confidence": 0.05,
    "max_confidence": 0.95,
    "default_base_probability": 0.50,
    "regime_multipliers": {
        "Bull Market (Momentum)": 1.15,
        "Bull Consolidation": 1.05,
        "Sideways / Range-bound": 1.00,
        "Bear Rally / Correction": 0.90,
        "Bear Breakdown / High Volatility": 0.80,
        "Data Unavailable": 1.00,
    },
}

# ── Model Hyperparameters ──────────────────────────────────────────────────────

# The deployed booster is a binary classifier (lgb_model.txt objective=binary,
# pipeline/inference.py rejects anything else); keep this in step with it.
LIGHTGBM_PARAMS = {
    "objective": "binary",
    "metric": "binary_logloss",
    "num_leaves": 32,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "lambda_l1": 1e-3,
    "lambda_l2": 1e-3,
    "verbose": -1,
    "num_boost_round": 1000,
    "early_stopping_rounds": 50,
}
