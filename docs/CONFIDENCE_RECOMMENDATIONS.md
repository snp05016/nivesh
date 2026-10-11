# Confidence Calibration Review & Recommendations

## Current State Analysis
A thorough audit of `backend/services/confidence_fusion.py` reveals the following weight distribution for the final fused confidence score:

| Pillar | Base Weight | Observation |
|--------|-------------|-------------|
| LLM | 45% | Exceptionally high. LLMs are notoriously uncalibrated and tend toward extreme overconfidence (often outputting 80-90% certainty for coin-flip probabilities). |
| Quant | 25% | Reasonable, assuming this relies on robust deterministic logic. |
| Venn-Abers | 15% | **Architectural Flaw:** Venn-Abers is a *calibration wrapper*, not an independent predictive signal. It should not be an additive pillar; it should be applied to the ML/Quant probabilities *before* fusion. |
| Signal Agreement | 10% | Acts as a momentum/consensus check. |
| ML Engine | 0% - 25% | Capped at 25% even under the highest readiness mode (`trained_live_calibrated`). |

## Key Findings

### 1. LLM Over-weighting Risk
By assigning 45% to the LLM, the system is fundamentally an LLM-driven platform rather than an ML-driven quant platform. If the LLM generates a confidence of 95% (as LLMs frequently do) and the ML model outputs 40% (a well-calibrated edge), the LLM will completely override the ML engine. 

### 2. Misapplication of Venn-Abers
Treating Venn-Abers as an additive weight misunderstands the math. Venn-Abers generates a well-calibrated probability interval `[p0, p1]` from an underlying uncalibrated score (like the LightGBM probability). By making it a standalone 15% component, the platform double-counts confidence without actually calibrating the primary ML score.

### 3. ML Under-weighting
The maximum possible weight for a fully trained, live-calibrated LightGBM model is 25%. A machine learning model optimized via walk-forward cross-validation should be the primary anchor of confidence, not a secondary input to the LLM.

## Recommendations for Phase 2 Deployment

### Short-Term Fixes (Immediate)
1. **Reduce LLM Weight**: Cap the LLM confidence weight at 20%. Let the LLM provide the *narrative*, but restrict its influence over the *probability*.
2. **Increase ML Weight**: When `ml_engine_mode == "trained_lightgbm_baseline"`, increase the ML weight to at least 40%.
3. **Dynamic Kelly Scaling**: Rather than fusing linearly, scale the final confidence based on the historical hit rate of the highest-weight component.

### Medium-Term Architectural Refactor (Self-Improving Quant Platform)
1. **Remove Venn-Abers as a Pillar**: Remove `venn_abers_confidence` from the fusion formula.
2. **Apply Venn-Abers as a Wrapper**: Pass the raw `ml_conf` through the Venn-Abers calibrator to get a `calibrated_ml_conf`.
3. **Switch to Log-Odds Fusion**: Instead of linear weighted addition (which fails to handle extreme probabilities correctly), convert probabilities to log-odds, apply learned coefficients (via logistic regression on historical performance), and use the sigmoid function to get the final fused confidence.

*Proposed Formula Structure:*
`Fused Log-Odds = B0 + B1*logit(calibrated_ml) + B2*logit(quant) + B3*logit(llm)`
