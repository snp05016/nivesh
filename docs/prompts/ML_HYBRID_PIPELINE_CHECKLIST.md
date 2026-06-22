# Probabilistic Confidence Estimation Framework - Implementation Checklist

Use this checklist to track your progress while executing the `ML_HYBRID_PIPELINE_PROMPT.md` architectural directive.

## Phase 1: Database & Data Schema Transformations
- [ ] **SQLAlchemy Models Update**
  - [ ] Add `market_regime` (String) to `AnalysisReport`
  - [ ] Add `calibrated_confidence` (Float) to `AnalysisReport`
  - [ ] Add `conformal_target_upper_3m` (Float) to `AnalysisReport`
  - [ ] Add `conformal_target_lower_3m` (Float) to `AnalysisReport`
  - [ ] Add `quantitative_drivers` (JSON) to `AnalysisReport`
  - [ ] Add `tail_risk_flags` (JSON) to `AnalysisReport`
- [ ] **Alembic Migration**
  - [ ] Generate and apply Alembic migration for the new columns
- [ ] **Pydantic Schema Update**
  - [ ] Add new fields to `StockAnalysisResponse` in `backend/schemas.py`
  - [ ] Enforce bounds (`calibrated_confidence` between 0.0 and 1.0)
- [ ] **JSON Normalization Hook**
  - [ ] Modify `_normalize_response()` in `backend/utils.py` to forcefully inject `quant_payload` keys
  - [ ] Ensure LLM-hallucinated values for confidence/targets are explicitly overwritten

## Phase 2: The Quantitative Engine (Backend)
- [ ] **Create `services/quant_engine.py`**
  - [ ] Implement `QuantitativeEngine` class wrapper
  - [ ] Implement `run_full_pipeline()` to orchestrate mathematical steps
- [ ] **Regime Detection Subsystem**
  - [ ] Implement `_detect_market_regime()` using 30-day volatility proxy
  - [ ] Output `Low Volatility`, `Transition`, or `High Volatility / Crisis`
- [ ] **Conformal Prediction Targets**
  - [ ] Implement `_compute_conformal_targets()`
  - [ ] Calculate 3-month volatility boundaries using a 90% confidence Z-score
- [ ] **SHAP Feature Importance & Risks**
  - [ ] Implement `_compute_feature_importance()`
  - [ ] Map fundamental/technical data to relative mathematical SHAP proxies (-1.0 to 1.0)
  - [ ] Define explicit tail risk flags (e.g., high promoter pledging)
- [ ] **Venn-Abers Calibrated Confidence**
  - [ ] Implement `_compute_calibrated_confidence()`
  - [ ] Start with 0.50 base, add SHAP modifiers, apply regime multiplier
  - [ ] Apply direct mathematical deductions for active tail risks
  - [ ] Bound final score between 0.05 and 0.95

## Phase 3: Orchestration & Concurrency Refactoring
- [ ] **Update `services/orchestrator.py`**
  - [ ] Ensure `Smart Cache Gate` runs *before* the quant engine
  - [ ] Instantiate `QuantitativeEngine` and `await run_full_pipeline()`
  - [ ] Inject `quant_payload` into `initial_state["quant_data"]`
  - [ ] Pass the updated state to the LangGraph pipeline
  - [ ] Pass `quant_payload` into `_normalize_response()` at the end
- [ ] **Error Handling**
  - [ ] Catch NSE data fetching exceptions inside `quant_engine.py`
  - [ ] Provide graceful fallback quantitative payload if live data fails

## Phase 4: LangGraph Prompt Engineering
- [ ] **Update `backend/prompts.py`**
  - [ ] Add "QUANTITATIVE SUBORDINATION" rule to `INDIAN_MARKET_SYSTEM_PROMPT`
  - [ ] Explicitly forbid the LLM from inventing target prices or confidence numbers
  - [ ] Instruct the LLM to anchor its Bull/Bear case narrative on the SHAP `quantitative_drivers`
  - [ ] Instruct the LLM to write explicitly cautious risk paragraphs if the regime is "Crisis"

## Phase 5: iOS Frontend UI Engineering
- [ ] **Swift Models Update**
  - [ ] Update `StockAnalysis.swift` to include the new JSON keys (Optional variables)
  - [ ] Create a robust `displayConfidence` fallback variable
- [ ] **Build `RegimeWarningBanner.swift`**
  - [ ] Create independent struct to prevent `chkstk_darwin` crashes
  - [ ] Implement `Theme.holdAmber`/`Theme.bearRed` Banknote styling for crisis states
- [ ] **Build `QuantitativeDriversCard.swift`**
  - [ ] Create independent struct iterating over `quantitativeDrivers`
  - [ ] Implement dynamic horizontal progress bars (green for positive, red for negative SHAP)
  - [ ] Apply `Theme.serialNumberFont` and `Theme.engravedSerif` formatting
- [ ] **Update `AnalysisScreen.swift`**
  - [ ] Rename existing confidence UI to "Mathematically Calibrated Confidence"
  - [ ] Conditionally render `RegimeWarningBanner` below the main hero note
  - [ ] Render `QuantitativeDriversCard` between summary and Bull/Bear cases
  - [ ] Update target price UI to display conformal interval ranges formatted with `IndianFormatter`

## Phase 6: Testing, Validation & Future-Proofing
- [ ] **GitNexus Impact Audit**
  - [ ] Run `gitnexus_impact` on `analyze_ticker` upstream changes
- [ ] **Backend Dry Run**
  - [ ] Create and run `scripts/test_quant_engine.py` to ensure < 1.5s execution time
- [ ] **Swift Compilation Pre-Check**
  - [ ] Verify zero usage of raw `.blue` or `Color(hex:)`
  - [ ] Verify zero usage of `GeometryReader` directly inside main ScrollViews
- [ ] **Drift Monitoring Script**
  - [ ] Create `scripts/monitor_model_drift.py` to verify average historical confidence distributions
