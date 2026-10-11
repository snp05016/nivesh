"""Five-bucket cohort calibrator behind ``p_top_half`` (spec 4.4, D9, ML-12).

For a test quarter starting at ``test_start`` the calibrator is fitted on
out-of-sample predictions from the prior 36 months whose ``label_end`` precedes
``test_start``; with fewer than 24 distinct months of such rows p is unavailable.

- f_b = mean(top) of the rows in bucket b; p = f_bucket.
- CIs: circular block bootstrap over dates (block 2h, 2000 reps, seed 20261010).
- n_b = rows in the bucket; neutral = the CI covers 0.5 (or the bucket is empty).

JSON (production ``calibrator.json``)::

    {"buckets": [{"bucket", "frequency", "ci_low", "ci_high", "n", "neutral"}], "period", "base_rate"}

An unavailable calibrator serialises as ``{"buckets": [], "period": null, "base_rate": null}``.
The cohort block it feeds is reserved (no v1 UI) and is emitted only for a
``validated_edge`` artefact that passed gate P.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np
import pandas as pd

from .. import config
from ..validation.metrics import block_bootstrap_indices, daily_block

N_BINS: int = config.CALIBRATION["n_bins"]


def _day(v: Any) -> str:
    return cast(pd.Timestamp, pd.Timestamp(v)).date().isoformat()


def fit_rows(preds: pd.DataFrame, test_start: Any) -> pd.DataFrame:
    """Rows a calibrator for ``test_start`` may use: as-of within the prior 36 months, label ended before.

    ``preds`` is indexed with the as-of date on level 0 and has ``bucket``,
    ``top`` and ``label_end`` columns. Rows with a missing bucket or outcome are dropped.
    """
    ts = cast(pd.Timestamp, pd.Timestamp(test_start))
    lo = ts - pd.DateOffset(months=config.CALIBRATION["lookback_months"])
    dates = pd.DatetimeIndex(preds.index.get_level_values(0))
    label_end = pd.DatetimeIndex(preds["label_end"])
    keep = (dates >= lo) & (dates < ts) & (label_end < ts)
    out = preds.loc[np.asarray(keep), ["bucket", "top", "label_end"]]
    return out.loc[out["bucket"].notna() & out["top"].notna()]


@dataclass(frozen=True)
class CohortCalibrator:
    buckets: list[dict[str, Any]] = field(default_factory=list)
    period: str | None = None
    base_rate: float | None = None

    @property
    def available(self) -> bool:
        return bool(self.buckets)

    @classmethod
    def fit(cls, preds: pd.DataFrame, test_start: Any, h: int) -> CohortCalibrator:
        """Fit for the quarter starting ``test_start``; unavailable (no buckets) below 24 months."""
        rows = fit_rows(preds, test_start)
        dates = pd.DatetimeIndex(rows.index.get_level_values(0))
        n_months = len(pd.unique(dates.to_period("M"))) if len(rows) else 0
        if n_months < config.CALIBRATION["min_months"]:
            return cls()
        b = rows["bucket"].to_numpy(dtype=float).astype(int)
        top = rows["top"].to_numpy(dtype=float)
        codes, uniq = pd.factorize(dates, sort=True)
        n_dates = len(uniq)
        # per (date, bucket) sums and counts; the bootstrap resamples whole dates
        sums = np.zeros((n_dates, N_BINS))
        counts = np.zeros((n_dates, N_BINS))
        np.add.at(sums, (codes, b - 1), top)
        np.add.at(counts, (codes, b - 1), 1.0)
        idx = block_bootstrap_indices(n_dates, daily_block(h))
        boot_s = sums[idx].sum(axis=1)  # (reps, N_BINS)
        boot_c = counts[idx].sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            boot_f = boot_s / boot_c
        out: list[dict[str, Any]] = []
        for k in range(N_BINS):
            n = int(counts[:, k].sum())
            if n == 0:
                out.append({"bucket": k + 1, "frequency": None, "ci_low": None, "ci_high": None,
                            "n": 0, "neutral": True})
                continue
            freq = float(sums[:, k].sum() / n)
            col = boot_f[:, k]
            col = col[np.isfinite(col)]
            lo, hi = (float(v) for v in np.quantile(col, [0.025, 0.975]))
            out.append({"bucket": k + 1, "frequency": freq, "ci_low": lo, "ci_high": hi,
                        "n": n, "neutral": bool(lo <= 0.5 <= hi)})
        period = f"{_day(uniq[0])} to {_day(uniq[-1])}"
        return cls(buckets=out, period=period, base_rate=float(top.mean()))

    def _entry(self, bucket: Any) -> dict[str, Any] | None:
        try:
            b = int(bucket)
        except (TypeError, ValueError):
            return None
        return self.buckets[b - 1] if 1 <= b <= len(self.buckets) else None

    def p(self, bucket: Any) -> float | None:
        """p = f_bucket, or None when unavailable."""
        e = self._entry(bucket)
        return None if e is None or e["frequency"] is None else float(e["frequency"])

    def p_array(self, buckets: Any) -> np.ndarray:
        """Vectorised ``p``: NaN where the bucket is missing or the calibrator unavailable."""
        freq = np.array([np.nan if e["frequency"] is None else e["frequency"] for e in self.buckets]
                        or [np.nan] * N_BINS, dtype=float)
        b = np.asarray(buckets, dtype=float)
        ok = np.isfinite(b)
        out = np.full(b.shape, np.nan)
        out[ok] = freq[b[ok].astype(int) - 1]
        return out

    def neutral_array(self, buckets: Any) -> np.ndarray:
        """True where the row's bucket is neutral (or unknown)."""
        flags = np.array([e["neutral"] for e in self.buckets] or [True] * N_BINS, dtype=bool)
        b = np.asarray(buckets, dtype=float)
        ok = np.isfinite(b)
        out = np.ones(b.shape, dtype=bool)
        out[ok] = flags[b[ok].astype(int) - 1]
        return out

    def cohort_for(self, bucket: Any) -> dict[str, Any] | None:
        """Raw values for the reserved Cohort block (contract 6.2); None when unavailable."""
        e = self._entry(bucket)
        if e is None or e["frequency"] is None or self.period is None:
            return None
        return {"bucket": e["bucket"], "frequency": e["frequency"], "ci_low": e["ci_low"],
                "ci_high": e["ci_high"], "cases": e["n"], "period": self.period, "neutral": e["neutral"]}

    def to_json(self) -> dict[str, Any]:
        return {"buckets": [dict(e) for e in self.buckets], "period": self.period, "base_rate": self.base_rate}

    @classmethod
    def from_json(cls, data: Mapping[str, Any] | None) -> CohortCalibrator:
        if not data:
            return cls()
        buckets = [dict(e) for e in data.get("buckets") or []]
        if buckets and [e.get("bucket") for e in buckets] != list(range(1, N_BINS + 1)):
            raise ValueError("calibrator buckets must be 1..5 in order")
        base = data.get("base_rate")
        return cls(
            buckets=buckets,
            period=data.get("period"),
            base_rate=None if base is None or not math.isfinite(float(base)) else float(base),
        )
