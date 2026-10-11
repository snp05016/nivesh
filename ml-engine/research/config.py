"""Frozen, pre-registered constants for the research engine (spec 5.1).

Every procedure constant lives here and ``config_sha256()`` hashes all of them
(paths excluded) into every manifest and trial row. Changing any value after
out-of-sample results have been seen is a new trial or a new procedure version,
so treat this module as read-only at runtime: never mutate these objects.

Conventions: rates are fractions (0.001 = 0.1%), money is INR, windows are
counted in trading sessions unless the key says otherwise.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

# ── Identity ────────────────────────────────────────────────────────────────
PROCEDURE_ID = "rg-lgbm-v1"
FEATURE_VERSION = "fv1"
COST_MODEL_VERSION = "nse_delivery_2026_v1"
UNIVERSE_ID = "NSE_LIQ200"
BENCHMARK_ID = "NIFTY50_PR"
HORIZONS = (21, 63)
EMBARGO = 21  # sessions, after the h-session purge (D7)
LOCKBOX_SPENT = True  # rg-lgbm-v1: design agents saw the lockbox data (5.1, D13)

# ── Dates (5.2). OOS rows must also satisfy the lockbox boundary in 5.3:
# idx(label_end) <= idx(lockbox_start) - EMBARGO.
DATES: dict[str, dict[str, Any]] = {
    "prod": {
        "data_start": date(2008, 1, 1),
        "train_start": date(2010, 1, 1),
        "initial_train_end": date(2014, 12, 31),  # expanding window
        "oos_start": date(2015, 1, 1),
        "oos_end": date(2024, 6, 30),
        "oos_refits": 38,  # quarterly
        "prob_metrics_start": date(2017, 1, 1),
        "lockbox_start": date(2024, 7, 1),
        "lockbox_end": date(2026, 6, 30),
    },
    "dev": {  # code paths only (local CSV)
        "data_start": date(2018, 1, 1),
        "train_start": date(2019, 1, 1),
        "initial_train_end": date(2020, 12, 31),
        "oos_start": date(2021, 1, 1),
        "oos_end": date(2024, 6, 30),
        "oos_refits": 14,  # quarterly
        "prob_metrics_start": date(2023, 1, 1),
        "lockbox_start": date(2024, 7, 1),
        "lockbox_end": date(2026, 3, 20),
    },
}

# ── Universe NSE_LIQ200 (3.6, D1). No eligibility clause on suspect days.
UNIVERSE: dict[str, Any] = {
    "size": 200,
    "buffer_rank": 240,  # existing members ranked <= 240 are kept (in rank order, up to size)
    "series": "EQ",
    "rank_window_sessions": 126,  # median turnover_inr
    "min_history_sessions": 252,  # since the entity first appeared
    "median_close_window_sessions": 21,
    "min_median_close_inr": 20.0,
    "traded_window_sessions": 126,
    "min_traded_share": 0.95,  # volume > 0 on at least this share of the window
}

# ── Market data (3.4, 3.5, 2.2, 2.6)
LINKING: dict[str, Any] = {"lookback_sessions": 5}
GAP_FILL: dict[str, Any] = {"max_calendar_days": 15}
QUALITY: dict[str, Any] = {
    "event_threshold": 0.005,  # |f - 1| above this records an event; the factor is always applied
    "jump_threshold": 0.25,  # abs(adjusted daily return) candidate for a bad tick
    "reversal_share": 0.8,  # log move reversing by >= 80% ...
    "reversal_window_sessions": 3,  # ... within this many sessions, with no event -> suspect
    "second_source_tolerance": 0.02,  # yfinance raw close differs by more -> suspect
    "split_match_tolerance": 0.02,  # 1/f vs a yfinance split ratio
    "dividend_match_tolerance": 0.002,  # |(1 - f) - D/close_p|
    "drop_limit": 0.02,  # a step dropping more of the expected rows fails the run (ML-06)
    "min_bhavcopy_eq_rows": 1500,
    "crosscheck_share": 0.05,  # monthly yfinance cross-check sample
    "crosscheck_tolerance": 0.01,
}

# ── Features and labels (4.1, 4.2)
FEATURE_RULES: dict[str, Any] = {
    "min_window_coverage": 0.8,  # else the feature is NaN (never zero-filled)
    "max_row_nan_share": 0.3,  # training drops rows with more NaN features
}
LABELS: dict[str, Any] = {"stale_exit_sessions": 5}

# ── Historical return ranges (4.5, D11). Descriptive only, never a forecast.
RANGES: dict[str, Any] = {
    "window_sessions": 756,
    "min_sessions": 252,
    "low_quantile": 0.1,
    "high_quantile": 0.9,
}

# ── Model rg-lgbm-v1 (4.3)
LGBM_PARAMS: dict[str, Any] = {
    "objective": "regression",  # L2 on rank_h
    "metric": "l2",
    "num_leaves": 15,
    "max_depth": 4,
    "learning_rate": 0.03,
    "min_data_in_leaf": 500,
    "feature_fraction": 0.7,
    "bagging_fraction": 0.7,
    "bagging_freq": 1,
    "lambda_l2": 10.0,
    "max_bin": 63,
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 3,
    "verbose": -1,
}
LGBM_SEEDS = (11, 23, 37, 51, 73)  # seed k trains on sessions with session_index % 5 == k
LGBM_MAX_ROUNDS = 1500
LGBM_PATIENCE = 100  # early stopping on inner-validation L2, then refit at the best iteration
INNER_VAL_SESSIONS = 252
RIDGE_ALPHAS = (1.0, 10.0, 100.0)  # baseline B8, chosen on inner validation
FAST: dict[str, Any] = {"seeds": 1, "max_rounds": 50, "last_folds": 2}  # dev only, TRIALS_DEV
NULL_CALIBRATION: dict[str, Any] = {"seeds": 1, "max_rounds": 300, "max_weak": 2, "max_validated": 0}
MIN_DSR_TRIALS = 7

# ── Probability calibration (4.4)
CALIBRATION: dict[str, Any] = {"n_bins": 5, "lookback_months": 36, "min_months": 24}

# ── Metrics (5.4). HAC LRV: Hansen-Hodrick uniform kernel, lags 1..h-1;
# Bartlett at L = 4h when the HH estimate is <= 0.
METRICS: dict[str, Any] = {"min_names_per_date": 40, "ece_bins": 5, "cscv_blocks": 16}
HAC: dict[str, Any] = {
    "kernel": "hansen_hodrick",
    "max_lag_offset": -1,  # max lag = h - 1
    "fallback_kernel": "bartlett",
    "fallback_lag_multiple": 4,  # L = 4h
}
BOOTSTRAP: dict[str, Any] = {
    "reps": 2000,
    "seed": 20261010,
    "daily_block_multiple": 2,  # block = 2h for daily series
    "monthly_block": 3,
}

# ── Gates (5.6). No gate R and no class-share clause. Comparisons: ">=" for
# min_*, "<=" for max_*, ">" for *_gt.
GATES: dict[str, dict[str, Any]] = {
    "G0": {  # data; required at both levels
        "universe_quality": "pit",
        "max_drop_share": 0.02,
        "identical_fold_hashes": True,
        "manifest_verifies": True,
    },
    "G1": {"validated": {"min_t_star": 3.0}, "weak": {"min_t_star": 2.0}},
    "G2": {  # paired HAC t vs the best of B3-B8; weak only needs a point estimate >= 0
        "validated": {"min_paired_t": 2.0},
        "weak": {"min_delta_ic": 0.0},
    },
    "G3": {
        "validated": {"min_positive_period_share": 0.7, "every_vol_tercile_ic_gt": 0.0},
        "weak": {"min_positive_period_share": 0.6},
    },
    "G4": {  # net mean monthly active return at 1x slippage
        "validated": {"net_active_gt": 0.0, "min_dsr": 0.95, "beats_b4": True},
        "weak": {"net_active_gt": 0.0},
    },
    "G5": {"validated": {"max_pbo": 0.20}, "weak": {"max_pbo": 0.50}},
    "G6": {  # lockbox, one shot (spent)
        "validated": {"min_hac_t": 1.65, "net_active_gt": 0.0},
        "weak": {"mean_ic_gt": 0.0},
    },
    "P": {  # probability display; required for a cohort only
        "bss_ci_low_gt": 0.0,
        "min_auc_ci_low_every_year": 0.52,
        "max_lockbox_ece": 0.03,
        "min_lockbox_n_eff": 2000,
    },
}

# ── Costs nse_delivery_2026_v1 (5.5). Rates per side on |delta w|.
COSTS: dict[str, Any] = {
    "stt_rate": 0.001,
    "stamp_duty_buy_rate": 0.00015,
    "exchange_rate": 0.0000297,
    "sebi_rate": 0.000001,
    "gst_rate": 0.18,  # on exchange + SEBI charges
    "dp_charge_inr_per_sell": 15.93,
    "ticket_inr": 50000.0,
    # One-way slippage by 63-day median ADV in INR crore: first row whose
    # threshold the ADV exceeds; the last row (0) catches everything else.
    "slippage_bp_by_adv_cr": ((500.0, 4.0), (100.0, 8.0), (20.0, 18.0), (0.0, 40.0)),
    "slippage_multipliers": (1.0, 2.0),
    "top_fraction": 0.2,  # equal-weight top quintile
    "buffer_exit_pctl": 0.6,  # robustness variant only
    "h63_tranches": 3,
}

# ── Risk (4.6)
RISK: dict[str, Any] = {
    "ewma_lambda": 0.94,
    "annualisation_days": 252,
    "vol_windows": (63, 252),
    "var_levels": (0.95, 0.99),
    "var_methods": ("historical_500d", "fhs_ewma"),
    "hist_window_days": 500,
    "backtest_window_days": 250,
    "var99_max_exceptions": 4,
    "kupiec_p_min": 0.05,
    "christoffersen_p_min": 0.05,
    "beta_window_days": 252,
    "beta_min_pairs": 200,
    "blume_weights": (0.67, 0.33),
    "drawdown_years": (1, 3, 5),
    "ulcer_years": 1,
    "drawdown_series_weeks": 156,
    "drawdown_series_max_points": 160,
}

# ── Fundamentals, display only (4.7)
FUNDAMENTALS: dict[str, Any] = {
    "cache_ttl_days": 7,
    "max_refreshes_per_night": 60,
    "stale_after_months": 15,
    "min_sector_peers": 5,
}

# ── Outcomes and live metrics (8.4, 8.5, D13, D28). Only A1 changes status.
OUTCOMES: dict[str, Any] = {"entry_price_tolerance": 0.0001, "scorer_version": "os-2"}
LIVE: dict[str, Any] = {
    "a1": {"window_months": 12, "consecutive_month_ends": 6, "ic_below": 0.0},
    "g7": {"min_independent_periods": 12, "min_hac_t": 1.65, "min_ic_ratio_vs_oos": 0.5},
    "calibrator_drift": {"consecutive_months": 3, "min_rows_per_bucket_month": 100},
    "psi_warning": 0.25,
    "ece_min_n_eff": 500,
}

# ── Paths (excluded from config_sha256)
_ML_ENGINE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("RESEARCH_DATA_DIR") or _ML_ENGINE_DIR / "data" / "research")
LOCAL_CSV = Path(os.environ.get("RESEARCH_LOCAL_CSV") or _ML_ENGINE_DIR / "nifty50_data.csv")

_PATH_CONSTANTS = frozenset({"DATA_DIR", "LOCAL_CSV"})


def _constants() -> dict[str, Any]:
    """Every public UPPER_CASE constant of this module except the paths."""
    return {
        name: value
        for name, value in globals().items()
        if name.isupper() and not name.startswith("_") and name not in _PATH_CONSTANTS
    }


def _json_default(obj: Any) -> Any:
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"unhashable config value of type {type(obj).__name__}")


def config_sha256() -> str:
    """sha256 of the canonical JSON of all constants (sorted keys, paths excluded)."""
    canonical = json.dumps(
        _constants(), sort_keys=True, separators=(",", ":"), default=_json_default
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
