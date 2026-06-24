# Next 90 Days: Scale & New Signals

**Objective**: Expand the predictive capability of the models without sacrificing determinism or calibration.

## 1. Cross-Sectional Ranking Models
- Transition the objective function in `train_lightgbm.py` from pointwise binary classification (`binary_logloss`) to listwise ranking (`lambdarank`).
- Train models to rank the entire Nifty 500 cross-section to output relative deciles rather than absolute probabilities, neutralizing broad market regime shifts.

## 2. NLP Feature Extraction
- Build an offline processing pipeline to consume news/earnings call transcripts.
- Convert text to FinBERT embeddings and add them as features (e.g., `nlp_sentiment_3d_rolling`) to the Alpha158 matrix.

## 3. Automated Model Fallback Strategy
- Build a service router that monitors the Brier score of the `stable` LightGBM model. 
- If the model's calibration breaks down, gracefully and automatically revert to the `fallback_technical_heuristic` while alerting the quantitative engineering team.
