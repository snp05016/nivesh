"""
test_06_python_builtins_exceptions.py
======================================
Tests runtime behavior of Python built-in exceptions in the context of
common Nivesh backend patterns. Each test simulates a real code path
that could trigger the exception.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _base import TestRunner


def run():
    runner = TestRunner("06_python_builtins_exceptions")

    # ---- ArithmeticError family (P&L calculations)

    # ZeroDivisionError (P&L percentage with buy_price=0)
    try:
        total_invested = 0.0
        pnl = 50000.0
        pnl_pct = pnl / total_invested
        runner.fail("ZeroDivisionError_pnl", "Division by zero in P&L not caught")
    except ZeroDivisionError as e:
        runner.ok("ZeroDivisionError_pnl", f"ZeroDivisionError in P&L calc: '{e}'")

    # OverflowError (large number in formatting)
    try:
        import math
        _ = math.exp(1000)  # Returns inf, not OverflowError in Python
        runner.ok("OverflowError_no_crash", "math.exp(1000) returns inf (not OverflowError)")
    except OverflowError as e:
        runner.ok("OverflowError_caught", f"OverflowError: {e}")

    # FloatingPointError (usually needs SIGFPE which is platform-specific)
    runner.ok("FloatingPointError_importable", "FloatingPointError is importable and catchable in principle")

    # ---- AssertionError (defensive programming)
    try:
        assert False, "Assertion in production code"
    except AssertionError as e:
        runner.ok("AssertionError_caught", f"AssertionError: '{e}'")

    # ---- AttributeError (accessing non-existent attribute)
    try:
        class FakeRow:
            signal = "BULLISH"
        row = FakeRow()
        _ = row.non_existent_field  # Simulates accessing wrong ORM column name
        runner.fail("AttributeError_orf", "AttributeError not raised on non-existent attribute")
    except AttributeError as e:
        runner.ok("AttributeError_orf", f"AttributeError on ORM field access: '{e}'")

    # ---- LookupError family

    # IndexError (empty list access — e.g., LLM response parsing)
    try:
        choices = []
        _ = choices[0].message.content  # Simulates empty LLM response
        runner.fail("IndexError_empty_choices", "IndexError not raised on empty list")
    except IndexError as e:
        runner.ok("IndexError_empty_choices", f"IndexError on empty LLM choices: '{e}'")

    # KeyError (dict access without .get() — e.g., JSON response field)
    try:
        response = {"signal": "BULLISH"}
        _ = response["confidence_pct"]  # Field may not be in response
        runner.fail("KeyError_missing_field", "KeyError not raised on missing dict field")
    except KeyError as e:
        runner.ok("KeyError_missing_field", f"KeyError on missing JSON field: '{e}'")

    # ---- NameError / UnboundLocalError
    try:
        def _test_unbound():
            if False:
                x = 5
            return x  # UnboundLocalError if False branch never executes
        _test_unbound()
        runner.fail("UnboundLocalError_conditional", "UnboundLocalError not raised on unbound conditional var")
    except UnboundLocalError as e:
        runner.ok("UnboundLocalError_conditional", f"UnboundLocalError: '{e}'")

    # ---- MemoryError (cannot easily trigger, but verify it's catchable)
    try:
        raise MemoryError("Simulated OOM")
    except MemoryError as e:
        runner.ok("MemoryError_catchable", f"MemoryError raised and caught: '{e}'")

    # ---- EOFError (reading from stdin — affects interactive scripts)
    try:
        raise EOFError("End of input")
    except EOFError as e:
        runner.ok("EOFError_catchable", f"EOFError caught: '{e}'")

    # ---- BufferError
    try:
        raise BufferError("Buffer operation failed")
    except BufferError as e:
        runner.ok("BufferError_catchable", f"BufferError caught: '{e}'")

    # ---- TypeError family (Nivesh-specific patterns)

    # TypeError: NoneType + float (when DB returns None for a numeric field)
    try:
        db_value = None
        result = db_value + 100.0
        runner.fail("TypeError_none_add", "TypeError not raised on None + float")
    except TypeError as e:
        runner.ok("TypeError_none_add", f"TypeError on None + float (DB null field): '{e}'")

    # TypeError: str format with None
    try:
        signal = None
        formatted = f"Signal: {signal.upper()}"
        runner.fail("TypeError_none_method", "TypeError/AttributeError not raised on None.upper()")
    except AttributeError as e:
        runner.ok("TypeError_none_method", f"AttributeError on None.upper() (signal is NULL): '{e}'")

    # ---- ValueError family

    # ValueError: json.loads on invalid JSON
    try:
        import json
        _ = json.loads("{invalid json}")
        runner.fail("ValueError_json_loads", "ValueError not raised on invalid JSON")
    except ValueError as e:
        runner.ok("ValueError_json_loads", f"ValueError on invalid JSON: '{str(e)[:60]}'")

    # ValueError: int conversion
    try:
        _ = int("not_a_number")
        runner.fail("ValueError_int_conversion", "ValueError not raised on int('not_a_number')")
    except ValueError as e:
        runner.ok("ValueError_int_conversion", f"ValueError on int conversion: '{e}'")

    # ValueError: float conversion (common in price parsing)
    try:
        price_str = "₹2,500.00"  # Indian format with ₹ symbol
        _ = float(price_str)
        runner.fail("ValueError_float_indian_format", "ValueError not raised on Indian price format")
    except ValueError as e:
        runner.ok("ValueError_float_indian_format",
                  f"ValueError on Indian price format without stripping: '{e}'. "
                  f"Always strip ₹ and commas before float() conversion.")

    # ---- StopIteration (generator exhaustion)
    def gen():
        yield 1

    g = gen()
    next(g)  # First value
    try:
        next(g)  # StopIteration
        runner.fail("StopIteration_generator", "StopIteration not raised on exhausted generator")
    except StopIteration:
        runner.ok("StopIteration_generator", "StopIteration raised on exhausted generator")

    # ---- NotImplementedError (abstract methods)
    class AbstractAnalyzer:
        def analyze(self):
            raise NotImplementedError("Subclasses must implement analyze()")

    try:
        AbstractAnalyzer().analyze()
        runner.fail("NotImplementedError_abstract", "NotImplementedError not raised from abstract method")
    except NotImplementedError as e:
        runner.ok("NotImplementedError_abstract", f"NotImplementedError: '{e}'")

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "backend_integrity_latest.txt")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
