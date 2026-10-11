"""ARCH-21 regression: helpers.py stays a re-export hub, and the rate-limit patch point is real.

Tests used to patch main._check_rate_limit, a name nothing read; the middleware now
resolves core.rate_limiter._check_rate_limit at call time, so that is the one patch point.
"""
import ast
from pathlib import Path

from fastapi import HTTPException

import core.rate_limiter as rate_limiter

HELPERS = Path(__file__).resolve().parent.parent / "helpers.py"

# Canonical homes that remain in helpers.py by design; anything new belongs in core/ or services/.
ALLOWED_FUNCTIONS = {"upsert_device_token", "format_indian_currency", "_ban_western_scale"}
ALLOWED_CLASSES = {"DataHarvestingError"}


def test_helpers_has_no_new_definitions():
    tree = ast.parse(HELPERS.read_text(encoding="utf-8"))
    funcs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    assert funcs <= ALLOWED_FUNCTIONS, funcs - ALLOWED_FUNCTIONS
    assert classes <= ALLOWED_CLASSES, classes - ALLOWED_CLASSES


def test_middleware_honours_core_rate_limiter_patch(client, monkeypatch):
    def _deny(*_args, **_kwargs):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    monkeypatch.setattr(rate_limiter, "_check_rate_limit", _deny)
    assert client.get("/ping").status_code == 429

    monkeypatch.setattr(rate_limiter, "_check_rate_limit", lambda *_a, **_k: True)
    assert all(client.get("/ping").status_code == 200 for _ in range(130))
