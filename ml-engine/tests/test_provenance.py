"""ML-19: training provenance helpers."""

import pandas as pd

from training.provenance import dataframe_sha256, file_sha256, git_sha, library_versions


def _ohlcv() -> pd.DataFrame:
    return pd.DataFrame({
        "symbol": ["INFY", "INFY", "TCS", "TCS"],
        "date": pd.to_datetime(["2026-10-08", "2026-10-09", "2026-10-08", "2026-10-09"]),
        "close": [1500.0, 1510.5, 4100.0, 4095.25],
        "volume": [1_000_000, 1_200_000, 800_000, 750_000],
    })


def test_dataframe_sha256_ignores_row_order():
    df = _ohlcv()
    shuffled = df.sample(frac=1.0, random_state=7).reset_index(drop=True)
    assert dataframe_sha256(shuffled) == dataframe_sha256(df)


def test_dataframe_sha256_changes_with_one_close():
    df = _ohlcv()
    changed = df.copy()
    changed.loc[2, "close"] = 4100.01
    assert dataframe_sha256(changed) != dataframe_sha256(df)


def test_file_sha256(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"abc")
    assert file_sha256(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_library_versions_and_git_sha():
    versions = library_versions()
    assert versions["lightgbm"]
    assert "python" in versions
    sha = git_sha()
    assert sha is None or (isinstance(sha, str) and len(sha) == 40)
