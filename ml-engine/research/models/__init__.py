"""Models for procedure ``rg-lgbm-v1`` (spec 4.3, 4.4).

- ``baselines``: B0-B8, run on the same folds as the model.
- ``lgbm``: the pre-declared LightGBM procedure (date-offset seeds, inner-validation
  early stopping, refit at the best iteration), ``predict``, ``rank_pct``, ``bucket``.
- ``calibration``: the 5-bucket cohort calibrator behind ``p_top_half``.

Scores rank stocks within the universe for research validation only; they are
never shown as a rating, signal or price target.
"""
