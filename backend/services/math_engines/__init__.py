"""
Math Engines — Deterministic algorithm library for Nivesh stock analysis.

Replaces qualitative AI reasoning with reproducible, testable math.
Tasks 16-30.

Imports are lazy so that missing optional modules don't crash startup.
"""

def _lazy_import(module: str, names: list):
    """Import symbols from a submodule, returning None for each on failure."""
    try:
        import importlib
        mod = importlib.import_module(f".{module}", package=__name__)
        return [getattr(mod, n, None) for n in names]
    except Exception:
        return [None] * len(names)


(compute_piotroski_fscore, compute_beneish_mscore) = _lazy_import(
    "piotroski_beneish", ["compute_piotroski_fscore", "compute_beneish_mscore"]
)
(detect_rsi_divergence, detect_macd_crossover, detect_bollinger_squeeze) = _lazy_import(
    "momentum_divergence", ["detect_rsi_divergence", "detect_macd_crossover", "detect_bollinger_squeeze"]
)
(compute_pcr, compute_gex) = _lazy_import("pcr_gex", ["compute_pcr", "compute_gex"])
(compute_rrg_vectors,) = _lazy_import("relative_rotation_graph", ["compute_rrg_vectors"])
(compute_conformal_bounds,) = _lazy_import("conformal_prediction", ["compute_conformal_bounds"])
(find_historical_analogues,) = _lazy_import("euclidean_analogues", ["find_historical_analogues"])
(compute_dcf_valuation,) = _lazy_import("deterministic_dcf", ["compute_dcf_valuation"])
(detect_volume_anomalies,) = _lazy_import("volume_isolation_forest", ["detect_volume_anomalies"])
(compute_pead_signal,) = _lazy_import("eps_drift_model", ["compute_pead_signal"])
(analyze_news_sentiment,) = _lazy_import("finbert_sentiment", ["analyze_news_sentiment"])
(compute_minsky_risk,) = _lazy_import("minsky_risk", ["compute_minsky_risk"])
(compute_signal_agreement,) = _lazy_import("signal_agreement", ["compute_signal_agreement"])
(dtw_distance, detect_chart_pattern) = _lazy_import(
    "dtw_pattern_matching", ["dtw_distance", "detect_chart_pattern"]
)
(compute_correlation_matrix, optimize_portfolio_weights) = _lazy_import(
    "portfolio_correlation", ["compute_correlation_matrix", "optimize_portfolio_weights"]
)
(compute_auditor_risk_score,) = _lazy_import("auditor_risk", ["compute_auditor_risk_score"])

__all__ = [
    "compute_piotroski_fscore", "compute_beneish_mscore",
    "detect_rsi_divergence", "detect_macd_crossover", "detect_bollinger_squeeze",
    "compute_pcr", "compute_gex",
    "compute_rrg_vectors",
    "compute_conformal_bounds",
    "find_historical_analogues",
    "compute_dcf_valuation",
    "detect_volume_anomalies",
    "compute_pead_signal",
    "analyze_news_sentiment",
    "compute_minsky_risk",
    "compute_signal_agreement",
    "dtw_distance", "detect_chart_pattern",
    "compute_correlation_matrix", "optimize_portfolio_weights",
    "compute_auditor_risk_score",
]
