# ML Production Integration

This document outlines how the trained LightGBM baseline alpha model is integrated into the Nivesh production pipeline.

## 1. System Architecture

The Nivesh system utilizes a multi-process architecture to decouple heavy Machine Learning inference and feature computation from the main FastAPI orchestrator.

1.  **FastAPI Backend (Port 8000)**
    *   Coordinates the overall analysis flow.
    *   Fetches stock data and signals.
    *   Makes a non-blocking synchronous POST request (fire-and-forget fallback) to the ML engine.
    *   Performs deterministic Confidence Fusion.

2.  **ML Engine Microservice (Port 8001)**
    *   Runs in a dedicated Docker container based on `python:3.10-slim`.
    *   Loads the trained LightGBM alpha model (e.g., `lightgbm_baseline_alpha158_v1_20260624`).
    *   Computes Alpha158 features internally.
    *   Returns raw inference and metadata, setting the `ml_engine_mode` to `trained_lightgbm_baseline`.

## 2. Confidence Fusion

Once the ML Engine responds, the FastAPI backend fuses the confidence scores.
The `ml_engine_mode` acts as a dynamic switch:

*   **`fallback_technical_heuristic`**: (Used if ML engine is unreachable) ML weight = `0.05`.
*   **`trained_lightgbm_baseline`**: ML weight = `0.15`.
*   **`calibrated_ensemble`**: ML weight = `0.25` (Future).

```python
final_conf = (
    0.45 * llm_conf +
    0.25 * quant_conf +
    0.15 * venn_abers_conf +
    0.10 * signal_agreement +
    ML_WEIGHT * ml_conf
)
```

## 3. Graceful Degradation (Fallback Safety)

The `ml_client.py` implements a robust fallback mechanism:
1.  **Timeouts**: Short 5-second connection timeout, 15-second read timeout.
2.  **Exception Handling**: All exceptions (`httpx.RequestError`, `httpx.HTTPStatusError`) are swallowed.
3.  **Fallback**: The client returns `None`. The orchestrator seamlessly falls back to the `fallback_technical_heuristic` mode, ensuring the user always receives an analysis report even if the ML pipeline crashes.

## 4. Prediction Logging and Model Tracking

Every single prediction is tracked in the `analysis_predictions` table.
Crucially, the following metadata is attached to each prediction row:
*   `ml_engine_mode`: Indicates exactly how the ML score was derived.
*   `model_version`: The specific artifact string (e.g., `lightgbm_baseline_alpha158_v1_20260624`).
*   `scan_type`: Indicates manual vs automated scans.
*   `ml_confidence`: Isolated ML pillar score.

This closed-loop system allows the future outcome tracker to calculate separate Brier scores for the ML pillar vs the overall fused score, measuring the value-add of the ML models directly.

## 5. Deployment and Operations

**Artifact Location:**
`/Users/saumya/Desktop/nivesh/ml-engine/models/lgb_model.txt`

**Status Endpoint:**
`GET http://localhost:8001/model/status`
Returns:
```json
{
  "lightgbm_loaded": true,
  "ml_engine_mode": "trained_lightgbm_baseline",
  "model_version": "lightgbm_baseline_alpha158_v1_20260624",
  "supported_horizons": [20],
  "feature_count": 158
}
```

**Testing:**
*   `backend/tests/test_fallback_safety.py`: Tests graceful failures.
*   `backend/tests/test_ml_client_integration.py`: Tests valid payload mapping.
*   `ml-engine/tests/test_trained_model_loading.py`: Tests container and model load health.
