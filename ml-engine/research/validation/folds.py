"""Walk-forward folds with purge, embargo and the lockbox boundary (spec 5.3, D7, ML-25).

Everything is session-index arithmetic on the panel calendar ``sessions``
(sorted unique session dates). A row at session index ``i`` has its label
ending at ``i + h``. idx(date) is the index of the first session on or after
that date.

- Outer purge: a training row needs ``i + h + embargo < idx(test_start)``.
- Lockbox boundary: an OOS test row needs ``i + h <= idx(lockbox_start) - embargo``.
- Inner validation: the last ``INNER_VAL_SESSIONS`` allowed training sessions;
  inner-training rows keep the same gap before the inner-validation start.
- ``Fold.hash`` is the sha256 of the index arrays, so the model and every
  baseline can prove they ran on identical folds (gate G0).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, cast

import numpy as np
import numpy.typing as npt
import pandas as pd

from .. import config

IntArray = npt.NDArray[np.int64]


@dataclass(frozen=True, eq=False)
class Fold:
    """One refit: integer session indices into the calendar the fold was built from."""

    k: int  # 0.. for OOS quarters, -1 for the lockbox
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_idx: IntArray
    inner_train_idx: IntArray
    inner_val_idx: IntArray
    test_idx: IntArray
    hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hash", fold_hash(self))


def fold_hash(fold: Fold) -> str:
    """sha256 over the four index arrays (each length-prefixed, little-endian int64)."""
    digest = hashlib.sha256()
    for arr in (fold.train_idx, fold.inner_train_idx, fold.inner_val_idx, fold.test_idx):
        a = np.ascontiguousarray(arr, dtype="<i8")
        digest.update(len(a).to_bytes(8, "little"))
        digest.update(a.tobytes())
    return digest.hexdigest()


def _calendar(sessions: Sequence[Any] | pd.DatetimeIndex) -> pd.DatetimeIndex:
    cal = pd.DatetimeIndex(sessions)
    if not cal.is_monotonic_increasing or not cal.is_unique:
        raise ValueError("sessions must be sorted and unique")
    return cal


def _idx(cal: pd.DatetimeIndex, d: Any, side: Literal["left", "right"] = "left") -> int:
    """Index of the first session on or after ``d`` (len(cal) when none); ``side="right"`` skips ``d``."""
    return int(cal.searchsorted(pd.DatetimeIndex([d]), side=side)[0])


def _inner_split(train_idx: IntArray, h: int, embargo: int) -> tuple[IntArray, IntArray]:
    """Inner validation = last INNER_VAL_SESSIONS training sessions, gapped like the outer split."""
    n_val = config.INNER_VAL_SESSIONS
    if len(train_idx) <= n_val:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    val = train_idx[-n_val:]
    inner_train = train_idx[train_idx + h + embargo < val[0]]
    return inner_train, val


def _arange(lo: int, hi_inclusive: int) -> IntArray:
    return np.arange(lo, max(lo, hi_inclusive + 1), dtype=np.int64)


def make_walkforward_folds(
    sessions: Sequence[Any] | pd.DatetimeIndex,
    dates_cfg: Mapping[str, Any],
    h: int,
    embargo: int = config.EMBARGO,
) -> list[Fold]:
    """Quarterly expanding-window OOS folds from ``oos_start`` to ``oos_end`` (spec 5.2, 5.3).

    ``dates_cfg`` is one entry of ``config.DATES``. Quarters whose test rows are
    all removed by the lockbox boundary (or by missing labels) are skipped, so at
    63d the last quarters before the lockbox produce no fold.
    """
    cal = _calendar(sessions)
    n = len(cal)
    train_lo = _idx(cal, dates_cfg["train_start"])
    lockbox_idx = _idx(cal, dates_cfg["lockbox_start"])
    last_test = min(lockbox_idx - embargo - h, n - 1 - h)  # label end inside the data and the boundary
    oos_end = pd.Timestamp(dates_cfg["oos_end"])
    quarter_starts = pd.date_range(pd.Timestamp(dates_cfg["oos_start"]), oos_end, freq="QS-JAN")

    folds: list[Fold] = []
    for q_start in quarter_starts:
        q_end = min(q_start + pd.offsets.QuarterEnd(0), oos_end)
        ts = _idx(cal, q_start)
        te = _idx(cal, q_end, "right") - 1  # last session on or before q_end
        test_idx = _arange(ts, min(te, last_test))
        if len(test_idx) == 0:
            continue
        train_idx = _arange(train_lo, ts - h - embargo - 1)  # i + h + embargo < ts
        inner_train, inner_val = _inner_split(train_idx, h, embargo)
        folds.append(
            Fold(
                k=len(folds),
                test_start=cast(pd.Timestamp, cal[int(test_idx[0])]),
                test_end=cast(pd.Timestamp, cal[int(test_idx[-1])]),
                train_idx=train_idx,
                inner_train_idx=inner_train,
                inner_val_idx=inner_val,
                test_idx=test_idx,
            )
        )
    return folds


def make_lockbox_fold(
    sessions: Sequence[Any] | pd.DatetimeIndex,
    dates_cfg: Mapping[str, Any],
    h: int,
    embargo: int = config.EMBARGO,
) -> Fold | None:
    """The one-shot lockbox fold: rows from ``lockbox_start`` whose labels end within the data.

    Training uses every row with ``i + h + embargo < idx(lockbox_start)``. Opening
    it is gated by ``train.py`` (``--open-lockbox``), not here. Returns None when
    no lockbox row has a complete label yet.
    """
    cal = _calendar(sessions)
    n = len(cal)
    ls = _idx(cal, dates_cfg["lockbox_start"])
    le = _idx(cal, dates_cfg["lockbox_end"], "right") - 1
    test_idx = _arange(ls, min(le, n - 1 - h))
    if len(test_idx) == 0:
        return None
    train_idx = _arange(_idx(cal, dates_cfg["train_start"]), ls - h - embargo - 1)
    inner_train, inner_val = _inner_split(train_idx, h, embargo)
    return Fold(
        k=-1,
        test_start=cast(pd.Timestamp, cal[int(test_idx[0])]),
        test_end=cast(pd.Timestamp, cal[int(test_idx[-1])]),
        train_idx=train_idx,
        inner_train_idx=inner_train,
        inner_val_idx=inner_val,
        test_idx=test_idx,
    )


def cscv_blocks(n_rows: int, s: int = config.METRICS["cscv_blocks"]) -> list[IntArray]:
    """Split ``n_rows`` time-ordered rows (e.g. months) into ``s`` contiguous blocks (CSCV)."""
    if n_rows < s:
        raise ValueError(f"CSCV needs at least {s} rows, got {n_rows}")
    return [np.asarray(b, dtype=np.int64) for b in np.array_split(np.arange(n_rows), s)]
