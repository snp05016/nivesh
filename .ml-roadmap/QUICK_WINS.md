# Quick Wins (Implementation < 48 Hours)

## 1. Adjust Fusion Weights
Modify `backend/services/confidence_fusion.py` to:
- Reduce LLM baseline weight from 45% to 20%.
- Increase ML baseline weight from 15% to 40% (if `trained_lightgbm_baseline`).
- Apply Venn-Abers calibration *to* the ML probability before fusion, rather than adding it as an independent 15% pillar.

## 2. Deploy Automated Cron Retraining
Create a basic shell script (`retrain.sh`) that triggers `python -m training.train_lightgbm` and loads the new model into `candidate` registry status. Schedule this via standard crontab for every Friday at 18:00 IST.

## 3. Configure Alerts for Brier Score Degradation
Add a lightweight anomaly detector in `outcome_tracker.py` that fires a Slack/Discord webhook if the rolling 7-day Brier Score exceeds 0.25 (indicating severe calibration loss).
