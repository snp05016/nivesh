"""Run provenance for training artifacts: code version, library versions, data hashes.

Model metadata written with these values can be traced back to the exact code,
libraries and input data that produced it. yfinance auto_adjust history changes
after corporate actions, so a release must archive its raw OHLCV snapshot next
to the ``dataframe_sha256`` recorded here.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import pandas as pd
from pandas.core.util.hashing import hash_pandas_object  # public as pandas.util.hash_pandas_object

_TRACKED_LIBRARIES = ("lightgbm", "numpy", "pandas", "polars", "scikit-learn")


def git_sha() -> str | None:
    """HEAD commit of the checkout containing this file, or None outside git."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True, text=True, timeout=10, check=True,
        )
    except Exception:
        return None
    return out.stdout.strip() or None


def library_versions() -> dict[str, str | None]:
    """Installed versions of the libraries that change model numerics, plus Python."""
    versions: dict[str, str | None] = {"python": sys.version}
    for name in _TRACKED_LIBRARIES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def dataframe_sha256(df: pd.DataFrame) -> str:
    """Order-independent content hash of an OHLCV frame keyed by (symbol, date)."""
    keys = [c for c in ("symbol", "date") if c in df.columns]
    frame = df.sort_values(keys, kind="mergesort") if keys else df
    frame = frame[sorted(frame.columns)]
    row_hashes = hash_pandas_object(frame, index=False).to_numpy()
    return hashlib.sha256(row_hashes.tobytes()).hexdigest()


def file_sha256(path: str | Path) -> str:
    """sha256 of a file's bytes, streamed."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
