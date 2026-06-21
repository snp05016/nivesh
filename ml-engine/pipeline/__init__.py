"""
ml-engine/pipeline/ — feature engineering and inference pipeline.

Phases:
1. feature_computer.py  — Compute Alpha158 features from raw OHLCV data
2. inference.py          — Run the loaded model on computed features

This mirrors the existing orchestrator.py::analyze() pattern where:
- QuantitativeEngine fetches data and computes math (here: feature computation)
- The LLM pipeline consumes the normalized output (here: model inference)

All pipeline stages produce dict outputs matching the quant_payload contract
so they can be plugged into orchestrator.py:1893 as a drop-in enrichment.
"""

from .feature_computer import FeatureComputer
from .inference import InferenceEngine

__all__ = ["FeatureComputer", "InferenceEngine"]
