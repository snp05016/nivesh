"""SILENT-20: model-version detection failures are logged, not swallowed."""
from __future__ import annotations

import logging
from pathlib import Path


import main


def test_unreadable_version_file_logs_warning(tmp_path: Path, caplog) -> None:
    model_dir = tmp_path / "models"
    (model_dir / "VERSION").mkdir(parents=True)  # exists() but read_text() raises
    caplog.set_level(logging.WARNING, logger="ml-engine")

    assert main._detect_model_version(model_dir / "lgb_model.txt") is None
    assert any("version detection failed" in r.getMessage() for r in caplog.records)
