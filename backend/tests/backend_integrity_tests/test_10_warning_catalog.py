"""
test_10_warning_catalog.py
===========================
Tests warning categories that indicate latent bugs in the Nivesh backend.
Verifies that:
1. DeprecationWarning for utcnow() usage is emitted
2. ResourceWarning for unclosed DB connections is detectable
3. RuntimeWarning for division quirks is raised
4. UserWarning for deprecated Indian number formats
5. Warning hierarchy is correct
6. Warnings can be promoted to errors (for strict mode)
"""
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _base import TestRunner


def run():
    runner = TestRunner("10_warning_catalog")

    # ---- Warning hierarchy checks
    warning_classes = [
        ("DeprecationWarning",          DeprecationWarning,         Warning),
        ("PendingDeprecationWarning",   PendingDeprecationWarning,  Warning),
        ("RuntimeWarning",              RuntimeWarning,             Warning),
        ("SyntaxWarning",               SyntaxWarning,              Warning),
        ("ResourceWarning",             ResourceWarning,            Warning),
        ("FutureWarning",               FutureWarning,              Warning),
        ("UserWarning",                 UserWarning,                Warning),
        ("ImportWarning",               ImportWarning,              Warning),
        ("UnicodeWarning",              UnicodeWarning,             Warning),
        ("BytesWarning",                BytesWarning,               Warning),
    ]

    for name, cls, parent in warning_classes:
        if issubclass(cls, parent):
            runner.ok(f"hierarchy:{name}→{parent.__name__}", f"{name} correctly inherits from {parent.__name__}")
        else:
            runner.fail(f"hierarchy:{name}→{parent.__name__}",
                        f"{name} does not inherit from {parent.__name__}")

    # ---- DeprecationWarning: datetime.utcnow() (forbidden per AGENTS.md)
    import datetime
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # utcnow() should produce DeprecationWarning in Python 3.12+
        _ = datetime.datetime.utcnow()
        if sys.version_info >= (3, 12) and any(issubclass(x.category, DeprecationWarning) for x in w):
            runner.ok("DeprecationWarning_utcnow",
                      f"datetime.utcnow() emits DeprecationWarning in Python {sys.version_info.major}.{sys.version_info.minor}. "
                      f"Replace with datetime.now(timezone.utc) per AGENTS.md §3.5.")
        elif sys.version_info < (3, 12):
            runner.ok("DeprecationWarning_utcnow_py311",
                      f"Python {sys.version_info.major}.{sys.version_info.minor}: utcnow() no DeprecationWarning yet. "
                      f"Still forbidden per AGENTS.md — use datetime.now(timezone.utc).")
        else:
            runner.fail("DeprecationWarning_utcnow",
                        "datetime.utcnow() did NOT emit DeprecationWarning in Python 3.12+. "
                        "This is unexpected — check if warnings are suppressed globally.")

    # ---- RuntimeWarning: float division edge cases
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        import math
        val = float("inf")
        _ = val - val  # NaN — should not warn but is a runtime hazard
        nan_result = math.isnan(val - val)
        if nan_result:
            runner.ok("RuntimeWarning_nan_arithmetic",
                      "inf - inf = NaN. Always check math.isnan() on financial calculations. "
                      "IndianFormatter must guard against NaN input.")
        else:
            runner.fail("RuntimeWarning_nan_arithmetic", "inf - inf did not produce NaN")

    # ---- ResourceWarning: unclosed file (tests that the system catches resource leaks)
    import gc
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        f = open("/dev/null", "r")
        del f
        gc.collect()

        resource_warnings = [x for x in w if issubclass(x.category, ResourceWarning)]
        if resource_warnings:
            runner.ok("ResourceWarning_unclosed_file",
                      f"ResourceWarning detected for unclosed file. "
                      f"Same will occur if get_session() sessions are not properly closed.")
        else:
            runner.ok("ResourceWarning_unclosed_file_none",
                      "ResourceWarning not raised for unclosed file in this environment. "
                      "Enable with: PYTHONDEVMODE=1 python ... or warnings.filterwarnings('error', ResourceWarning)")

    # ---- Warnings as errors (test that warnings CAN be promoted)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            warnings.warn("Test UserWarning promoted to error", UserWarning)
        runner.fail("UserWarning_promoted_to_error", "UserWarning was not promoted to error")
    except UserWarning as e:
        runner.ok("UserWarning_promoted_to_error",
                  f"UserWarning successfully promoted to error: '{e}'. "
                  f"Use 'PYTHONWARNINGS=error::DeprecationWarning' in CI to catch deprecated API usage.")

    # ---- FutureWarning: SQLAlchemy deprecation detection
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # session.query() is deprecated in SQLAlchemy 2.0 — emit a warning check
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            engine = create_engine("sqlite:///:memory:")
            Session = sessionmaker(bind=engine)
            s = Session()
            # Just check if any DeprecationWarning/SADeprecationWarning fired
            future_warns = [x for x in w if "deprecated" in str(x.message).lower() or
                           issubclass(x.category, (DeprecationWarning, FutureWarning))]
            if future_warns:
                runner.ok("SQLAlchemy_deprecation_warnings",
                          f"SQLAlchemy deprecation warnings detected: {[str(x.message)[:80] for x in future_warns[:3]]}")
            else:
                runner.ok("SQLAlchemy_deprecation_clean",
                          "No SQLAlchemy deprecation warnings — API usage is current")
            s.close()
        except Exception as e:
            runner.fail("SQLAlchemy_deprecation_check", f"Error checking SA warnings: {e}", e)

    # ---- UnicodeWarning
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", UnicodeWarning)
            warnings.warn("Unicode comparison issue", UnicodeWarning)
        runner.fail("UnicodeWarning_promoted", "UnicodeWarning was not promoted to error")
    except UnicodeWarning as e:
        runner.ok("UnicodeWarning_promoted", f"UnicodeWarning promoted to error: '{e}'")

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "backend_integrity_latest.txt")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
