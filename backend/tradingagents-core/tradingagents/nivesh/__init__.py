"""
tradingagents.nivesh — Nivesh AI Intelligence Pipeline Utilities
================================================================
Sub-package implementing Section 13 of the Nivesh TODO:

  13.2  reformatter.py     — Deterministic reformatting layer (Claude Sonnet 4.6,
                             Indian Market Priority Weighting, pristine JSON output)
  13.3  context_cache.py   — Prefix-aligned context stratification (static persona
                             cache + ticker history breakpoints)
  13.4  subprocess_runner.py — Subprocess isolation & per-user concurrency guard
"""

from .reformatter import reformat_with_sonnet
from .context_cache import build_system_array, build_static_persona_block, build_ticker_history_block
from .subprocess_runner import (
    run_analysis_isolated,
    AnalysisAlreadyRunningError,
    is_analysis_running,
    get_running_user_ids,
)

__all__ = [
    # 13.2
    "reformat_with_sonnet",
    # 13.3
    "build_system_array",
    "build_static_persona_block",
    "build_ticker_history_block",
    # 13.4
    "run_analysis_isolated",
    "AnalysisAlreadyRunningError",
    "is_analysis_running",
    "get_running_user_ids",
]
