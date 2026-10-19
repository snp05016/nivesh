# Final Report
The Alpha158 Candidate (`lightgbm_alpha158_candidate_v1_20260624`) was evaluated.
Guardrail status: **FAILED** (corrected by hand, audit item ML-05; see DEPLOYMENT_RECOMMENDATION.md)

It has no Brier skill over the base rate in 3 of 4 folds, AUC 0.51-0.54,
and no out-of-fold predictions for the promotion gate. Do not deploy it.
