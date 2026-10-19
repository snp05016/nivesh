"""Alias of core.feature_flags, the one flag registry (no logic here).

core/version_gate.py (trust cluster) imports `from config import feature_flags`
for ios_min_build(). Replacing this module in sys.modules makes both paths the
same object, so a monkeypatch on either reaches the gate and app-config alike.
"""
import sys

from core import feature_flags as _registry
from core.feature_flags import *  # noqa: F401,F403  (names for static checkers only)

sys.modules[__name__] = _registry
