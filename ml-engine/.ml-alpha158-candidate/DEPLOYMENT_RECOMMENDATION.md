# Deployment Recommendation
- Promotion gate: **FAILED** (corrected by hand, audit item ML-05)

The earlier "Passed Guardrails: True" came from thresholds that no skill-free
model can fail: hit rate > 0.53 (always-bullish scores 0.5882) and an in-sample
Brier < 0.2529 (a constant 0.5 forecast scores 0.25). The gate in
`training/promotion_gate.py` replaces them.

| Validation year (fold) | Brier | Base-rate Brier p(1-p) | ROC AUC | best_iteration |
|---|---|---|---|---|
| 1 | 0.2499 | 0.2493 | 0.5388 | 19 |
| 2 | 0.2342 | 0.2263 | 0.5131 | 1 |
| 3 | 0.2487 | 0.2476 | 0.5086 | 1 |
| 4 | 0.2438 | 0.2442 | 0.5290 | 22 |

### Reasons for Rejection
- no out-of-fold predictions: the artifact `lightgbm_alpha158_candidate_v1_20260624` has no `oof_predictions.csv`, so the gate fails closed.
- Brier skill vs the base rate is <= 0 in folds 1-3: the model is no better than predicting the training up-share.
- AUC 0.509-0.539 point estimates; none is credibly above 0.52 once a confidence interval is applied.
- Early stopping chose 1 tree in two folds and recall is about 1.0: the model predicts "up" almost everywhere.
