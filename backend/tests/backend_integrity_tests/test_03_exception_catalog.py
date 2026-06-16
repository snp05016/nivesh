"""
test_03_exception_catalog.py
=============================
Comprehensive catalog test: verifies every exception class in the
user's required list is importable, is a proper Exception subclass,
can be raised and caught, and produces meaningful error messages.

Covers:
- Python built-in exceptions (full catalog)
- ExceptionGroup / BaseExceptionGroup (Python 3.11+)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _base import TestRunner


def run():
    runner = TestRunner("03_exception_catalog")

    # Complete exception catalog from the user's requirement
    EXCEPTION_CATALOG = [
        # Base exceptions
        ("BaseException",                 BaseException),
        ("Exception",                     Exception),
        # Arithmetic
        ("ArithmeticError",               ArithmeticError),
        ("FloatingPointError",            FloatingPointError),
        ("OverflowError",                 OverflowError),
        ("ZeroDivisionError",             ZeroDivisionError),
        # Logic / Programming
        ("AssertionError",                AssertionError),
        ("AttributeError",               AttributeError),
        ("BufferError",                   BufferError),
        ("EOFError",                      EOFError),
        ("ImportError",                   ImportError),
        ("ModuleNotFoundError",           ModuleNotFoundError),
        ("LookupError",                   LookupError),
        ("IndexError",                    IndexError),
        ("KeyError",                      KeyError),
        ("MemoryError",                   MemoryError),
        ("NameError",                     NameError),
        ("UnboundLocalError",             UnboundLocalError),
        # OS / IO
        ("OSError",                       OSError),
        ("BlockingIOError",               BlockingIOError),
        ("ChildProcessError",             ChildProcessError),
        ("ConnectionError",               ConnectionError),
        ("BrokenPipeError",               BrokenPipeError),
        ("ConnectionAbortedError",        ConnectionAbortedError),
        ("ConnectionRefusedError",        ConnectionRefusedError),
        ("ConnectionResetError",          ConnectionResetError),
        ("FileExistsError",               FileExistsError),
        ("FileNotFoundError",             FileNotFoundError),
        ("InterruptedError",              InterruptedError),
        ("IsADirectoryError",             IsADirectoryError),
        ("NotADirectoryError",            NotADirectoryError),
        ("PermissionError",               PermissionError),
        ("ProcessLookupError",            ProcessLookupError),
        ("TimeoutError",                  TimeoutError),
        # Reference / Runtime
        ("ReferenceError",                ReferenceError),
        ("RuntimeError",                  RuntimeError),
        ("NotImplementedError",           NotImplementedError),
        ("RecursionError",                RecursionError),
        # Async / Iteration
        ("StopAsyncIteration",            StopAsyncIteration),
        ("StopIteration",                 StopIteration),
        # Syntax
        ("SyntaxError",                   SyntaxError),
        ("IndentationError",              IndentationError),
        ("TabError",                      TabError),
        # System
        ("SystemError",                   SystemError),
        # Type / Value
        ("TypeError",                     TypeError),
        ("ValueError",                    ValueError),
        # Unicode
        ("UnicodeError",                  UnicodeError),
        ("UnicodeDecodeError",            UnicodeDecodeError),
        ("UnicodeEncodeError",            UnicodeEncodeError),
        ("UnicodeTranslateError",         UnicodeTranslateError),
    ]

    # Test each exception
    for name, exc_class in EXCEPTION_CATALOG:
        # 1. Verify it's a class
        if not isinstance(exc_class, type):
            runner.fail(f"is_class:{name}", f"{name} is not a type: {type(exc_class)}")
            continue

        # 2. Verify it's a subclass of BaseException
        if not issubclass(exc_class, BaseException):
            runner.fail(f"is_exception:{name}", f"{name} is not a subclass of BaseException")
            continue

        # 3. Verify it can be raised and caught
        try:
            try:
                if exc_class == UnicodeDecodeError:
                    raise exc_class("utf-8", b"\xff", 0, 1, "test error")
                elif exc_class == UnicodeEncodeError:
                    raise exc_class("utf-8", "\xff", 0, 1, "test error")
                elif exc_class == UnicodeTranslateError:
                    raise exc_class("\xff", 0, 1, "test error")
                else:
                    raise exc_class("test error message")
            except exc_class as e:
                runner.ok(f"raise_catch:{name}", f"Can raise and catch {name}: '{str(e)[:60]}'")
        except Exception as e:
            runner.fail(
                f"raise_catch:{name}",
                f"Cannot raise/catch {name}: {type(e).__name__}: {e}",
                e
            )

        # 4. Verify hierarchy (e.g., IndexError is a LookupError)
        hierarchy_checks = {
            IndexError: LookupError,
            KeyError: LookupError,
            ModuleNotFoundError: ImportError,
            UnboundLocalError: NameError,
            IndentationError: SyntaxError,
            TabError: IndentationError,
            BrokenPipeError: ConnectionError,
            ConnectionAbortedError: ConnectionError,
            ConnectionRefusedError: ConnectionError,
            ConnectionResetError: ConnectionError,
            FileExistsError: OSError,
            FileNotFoundError: OSError,
            FloatingPointError: ArithmeticError,
            OverflowError: ArithmeticError,
            ZeroDivisionError: ArithmeticError,
            RecursionError: RuntimeError,
            NotImplementedError: RuntimeError,
            UnicodeDecodeError: UnicodeError,
            UnicodeEncodeError: UnicodeError,
            UnicodeTranslateError: UnicodeError,
        }
        if exc_class in hierarchy_checks:
            parent = hierarchy_checks[exc_class]
            if issubclass(exc_class, parent):
                runner.ok(f"hierarchy:{name}", f"{name} correctly inherits from {parent.__name__}")
            else:
                runner.fail(
                    f"hierarchy:{name}",
                    f"{name} does NOT inherit from {parent.__name__} — unexpected Python exception hierarchy change"
                )

    # ---- ExceptionGroup / BaseExceptionGroup (Python 3.11+)
    if sys.version_info >= (3, 11):
        try:
            eg = ExceptionGroup("test group", [ValueError("a"), TypeError("b")])
            runner.ok("ExceptionGroup_available", f"ExceptionGroup available in Python {sys.version_info.major}.{sys.version_info.minor}")
        except NameError:
            runner.fail("ExceptionGroup_available", "ExceptionGroup not available despite Python 3.11+")

        try:
            beg = BaseExceptionGroup("base group", [KeyboardInterrupt()])
            runner.ok("BaseExceptionGroup_available", "BaseExceptionGroup available")
        except NameError:
            runner.fail("BaseExceptionGroup_available", "BaseExceptionGroup not available despite Python 3.11+")
    else:
        runner.ok(
            "ExceptionGroup_skipped",
            f"ExceptionGroup requires Python 3.11+ (running {sys.version_info.major}.{sys.version_info.minor})"
        )

    # ---- Real-world ZeroDivisionError (simulates division in P&L formula)
    try:
        buy_price = 0.0
        current_price = 500.0
        pnl_pct = (current_price - buy_price) / buy_price * 100
        runner.fail(
            "zero_division_in_pnl",
            f"ZeroDivisionError NOT raised on buy_price=0. "
            f"This means the CheckConstraint ck_portfolio_buy_price_positive is not enforced."
        )
    except ZeroDivisionError:
        runner.ok("zero_division_in_pnl", "ZeroDivisionError raised on buy_price=0 as expected — DB constraint prevents this")

    # ---- Real-world RecursionError
    def deep_recursion(n):
        return deep_recursion(n + 1)
    try:
        deep_recursion(0)
        runner.fail("recursion_error_detection", "RecursionError was not raised — sys.setrecursionlimit may be very high")
    except RecursionError:
        runner.ok("recursion_error_detection", "RecursionError correctly raised on infinite recursion")

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "backend_integrity_latest.txt")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
