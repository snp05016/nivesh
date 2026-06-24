# Critical Gaps in Nivesh Infrastructure

## 1. Disconnected Feedback Loop
The platform stores every prediction, Brier score, and outcome. However, these outcomes **do not** influence the model dynamically. `confidence_fusion.py` uses hardcoded weights instead of trailing historical accuracy to weight the pillars. 

## 2. LLM Over-Reliance
The LLM is assigned 45% of the total confidence score, while the calibrated ML model is capped at 25%. This prevents the quantitative edge from succeeding, as the LLM's inherently uncalibrated text-based probabilities override statistical reality.

## 3. Data Temporal Leakage
There is no automated enforcement in `dataset_builder.py` guaranteeing that features generated for Day `T` *only* have access to data available at `T`'s market close. Without strict database-level Point-In-Time (PiT) safety, the models risk look-ahead bias.

## 4. Manual Training Operations
The platform lacks an MLOps orchestrator (e.g., Celery Beat or Airflow). Walk-forward training and model promotion are manual processes rather than automated nightly/weekly cron jobs.
