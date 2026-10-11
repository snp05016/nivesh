"""Validation protocol for the research engine (spec 5.3-5.8).

- ``folds``: walk-forward folds with purge, embargo, lockbox boundary and fold hashes.
- ``metrics``: RankIC, HAC t, bootstrap CIs, probability metrics, DSR and PBO.
- ``costs``: the ``nse_delivery_2026_v1`` cost model and the daily-path portfolio test.
- ``gates``: gates G0-G6 and P, and the artefact evidence tier.
- ``report``: ``validation.json`` to admin markdown (no verdict prose).

All session arithmetic is on integer session indices of the panel calendar.
"""
