# Model Registry Entry
```json
{
  "target": "direction_20d",
  "folds": [
    "2021:2022",
    "2022:2023",
    "2023:2024",
    "2024:2025"
  ],
  "n_folds_completed": 4,
  "n_features": 158,
  "n_total_samples": 95685,
  "final_num_boost_round": 10,
  "lightgbm_params": {
    "objective": "binary",
    "metric": "binary_logloss",
    "num_leaves": 32,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "lambda_l1": 0.001,
    "lambda_l2": 0.001,
    "verbose": -1,
    "num_boost_round": 2000,
    "early_stopping_rounds": 100
  },
  "data_date_range": {
    "min": "2018-06-26",
    "max": "2026-05-26"
  },
  "n_symbols": 49,
  "model_version": "lightgbm_alpha158_candidate_v1_20260624",
  "saved_at": "2026-06-24T17:17:53.308189+00:00",
  "num_features": 158,
  "num_trees": 10
}
```
