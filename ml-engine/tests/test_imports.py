"""Every serving and training module imports cleanly (ML-17 / TEST-18).

Catches deleted or renamed modules (the training.feature_builder class of
breakage) and undefined names evaluated at import time.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent

MODULES = ["config", "main"] + sorted(
    f"{p.parent.name}.{p.stem}"
    for pkg in ("pipeline", "models", "training")
    for p in (_ROOT / pkg).glob("*.py")
    if p.stem != "__init__"
)


def test_module_list_is_not_empty():
    assert {"training.validation", "training.feature_pipeline", "models.lgb_model"} <= set(MODULES)


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name: str):
    importlib.import_module(name)
