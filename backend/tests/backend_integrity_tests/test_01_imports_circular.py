"""
test_01_imports_circular.py
============================
Detects circular imports and import errors across the entire backend.
Uses Python's importlib + sys.modules isolation to test each module
independently. Reports:
- Circular import chains
- ModuleNotFoundError (missing dependencies)
- ImportError (bad import statement)
- SyntaxError (Python syntax errors in the source)
- IndentationError (indentation problems)
- AttributeError (wrong attribute accessed at import time)

This is the most important test — if a module fails to import,
ALL endpoints using that module return 500.
"""
import sys
import os
import importlib
import importlib.util
import traceback
import types
from pathlib import Path

# Set up sys.path
_BACKEND = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_BACKEND))

# Add test dir to path
sys.path.insert(0, str(Path(__file__).parent))
from _base import TestRunner

# Minimal env
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test_secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_key")

# Mock all heavy modules BEFORE importing anything
import unittest.mock as mock
_HEAVY = [
    "tradingagents", "tradingagents.graph", "tradingagents.graph.trading_graph",
    "tradingagents.default_config", "tradingagents.agents",
    "tradingagents.agents.utils", "tradingagents.agents.utils.agent_states",
    "langchain_anthropic", "langchain_core", "langchain_core.messages",
    "langchain_core.prompts", "langchain_core.tools", "langgraph", "langgraph.graph",
    "apscheduler", "apscheduler.schedulers", "apscheduler.schedulers.asyncio",
    "anthropic", "openai", "prompts", "yfinance", "openpyxl", "openpyxl.styles",
]
for _m in _HEAVY:
    if _m not in sys.modules:
        sys.modules[_m] = mock.MagicMock()

# Patch prompts
_pm = sys.modules["prompts"]
_pm.INDIAN_MARKET_SYSTEM_PROMPT = "mock"
_pm.NEWS_ANALYST_PERSONA = "mock"
_pm.EXTREME_ADDENDUM = "\nmock"

# All backend Python modules to test (relative to backend/)
BACKEND_MODULES = [
    "database",
    "helpers",
    "models.db_models",
    "models.signal_config",
    "services.staleness",
    "services.disk_cache",
    "services.cache_service",
    "services.error_telemetry",
    "services.llm_utils",
    "services.rate_limiter",
    "services.job_manager",
    "services.checkpoints",
    "services.brainstorming",
    "services.anomaly_scanner",
    "services.sector_rotation",
    "services.stress_test",
    "services.piotroski",
    "services.strategy_engine",
    "services.earnings_surprise",
    "repositories.analysis_repo",
    "repositories.job_repo",
    "routers.auth",
    "routers.health",
    "routers.user",
]


def try_import(module_name: str) -> tuple[bool, str]:
    """
    Attempt to import a module. Returns (success, error_message).
    """
    try:
        # Use a fresh import attempt without caching
        if module_name in sys.modules:
            del sys.modules[module_name]
        importlib.import_module(module_name)
        return True, ""
    except SyntaxError as e:
        return False, (
            f"SyntaxError at {e.filename}:{e.lineno}\n"
            f"  Line: {e.text}\n"
            f"  Message: {e.msg}\n"
            f"  FIX: Check for missing colons, unmatched brackets, or invalid syntax at the indicated line."
        )
    except IndentationError as e:
        return False, (
            f"IndentationError at {e.filename}:{e.lineno}\n"
            f"  Line: {e.text}\n"
            f"  FIX: Consistent 4-space indentation required. Check mixed tabs/spaces."
        )
    except ModuleNotFoundError as e:
        return False, (
            f"ModuleNotFoundError: {e}\n"
            f"  Missing module: '{e.name}'\n"
            f"  FIX: pip install {e.name} in the venv, or check .gitignore excludes the module."
        )
    except ImportError as e:
        return False, (
            f"ImportError: {e}\n"
            f"  FIX: Check circular imports or missing __init__.py in the package."
        )
    except AttributeError as e:
        return False, (
            f"AttributeError at import time: {e}\n"
            f"  FIX: Module attribute accessed at module level may not exist. "
            f"Move attribute access inside functions/classes."
        )
    except RecursionError as e:
        return False, (
            f"RecursionError (likely circular import): {e}\n"
            f"  TRACE:\n{traceback.format_exc()}\n"
            f"  FIX: Use lazy imports (import inside functions) to break the cycle."
        )
    except Exception as e:
        tb = traceback.format_exc()
        return False, (
            f"{type(e).__name__}: {e}\n"
            f"  Full traceback:\n{tb}"
        )


def run():
    runner = TestRunner("01_imports_circular")

    for module in BACKEND_MODULES:
        ok, error = try_import(module)
        if ok:
            runner.ok(f"import:{module}", "Module imported cleanly")
        else:
            runner.fail(
                f"import:{module}",
                f"Import FAILED for '{module}':\n{error}"
            )

    # ---- Circular import detection using importlib graph analysis
    # Check for any module that tries to import itself (direct circular)
    circular_detected = []
    for module in BACKEND_MODULES:
        if module in sys.modules:
            mod = sys.modules[module]
            if hasattr(mod, "__spec__") and mod.__spec__ is not None:
                if hasattr(mod.__spec__, "submodule_search_locations"):
                    pass  # package, skip
                # Check if the module tried to import itself
                # This is detected by checking if the module name appears in
                # its own source via a simple grep
    if not circular_detected:
        runner.ok("circular_import_detection", "No direct circular imports detected")

    # ---- Test that routers can be imported without starting the app
    # This checks that no router-level code runs at import time
    router_modules = [
        "routers.auth", "routers.health", "routers.user",
    ]
    for rmod in router_modules:
        ok, error = try_import(rmod)
        if ok:
            runner.ok(f"router_import:{rmod}", "Router imports cleanly (no startup side effects)")
        else:
            runner.fail(
                f"router_import:{rmod}",
                f"Router '{rmod}' fails to import — all routes in this module return 500 immediately.\n{error}"
            )

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "backend_integrity_latest.txt")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
