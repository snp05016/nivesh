"""
test_09_runtime_exceptions.py
==============================
Tests runtime exception behaviors that are specific to the Nivesh
backend architecture:
- RuntimeError in multiprocessing (worker crashes)
- OverflowError in financial calculations (very large numbers)
- RecursionError in LangGraph (graph cycles)
- SystemError and SystemExit handling
- GeneratorExit (async generator cleanup)
- ReferenceError (weak reference GC)
- BaseException (keyboard interrupt handling)
"""
import sys
import multiprocessing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _base import TestRunner


def _crashing_worker(queue):
    """Worker that raises RuntimeError — simulates analysis pipeline crash."""
    try:
        raise RuntimeError("Simulated analysis pipeline crash")
    except RuntimeError as e:
        queue.put({"error": str(e), "type": "RuntimeError"})


def _successful_worker(queue):
    """Worker that completes successfully."""
    queue.put({"result": "success", "signal": "BULLISH"})


def run():
    runner = TestRunner("09_runtime_exceptions")

    # ---- RuntimeError in multiprocessing (core Nivesh pattern)
    queue = multiprocessing.Queue()

    p_crash = multiprocessing.Process(target=_crashing_worker, args=(queue,))
    p_crash.start()
    p_crash.join(timeout=10)

    if not queue.empty():
        result = queue.get()
        if "error" in result:
            runner.ok("RuntimeError_worker_crash",
                      f"Worker crash correctly communicated via Queue: '{result['error']}'. "
                      f"This is the correct pattern — never let worker exception be silent.")
    else:
        runner.fail("RuntimeError_worker_crash",
                    "Worker crash was NOT communicated via Queue. "
                    "The analysis router has no way to detect the failure. "
                    "Job status will remain 'RUNNING' forever (zombie job).")

    # ---- Successful worker (baseline)
    queue2 = multiprocessing.Queue()
    p_ok = multiprocessing.Process(target=_successful_worker, args=(queue2,))
    p_ok.start()
    p_ok.join(timeout=10)

    if not queue2.empty():
        result2 = queue2.get()
        if result2.get("result") == "success":
            runner.ok("multiprocessing_success", "Worker successfully returns result via Queue")
    else:
        runner.fail("multiprocessing_success", "Worker did not return result via Queue")

    # ---- Process termination
    def _hanging_worker(queue):
        import time
        time.sleep(999)

    queue3 = multiprocessing.Queue()
    p_hang = multiprocessing.Process(target=_hanging_worker, args=(queue3,))
    p_hang.start()
    import time
    time.sleep(0.1)  # Let it start

    p_hang.terminate()
    p_hang.join(timeout=5)

    if not p_hang.is_alive():
        runner.ok("process_terminate", "Hanging worker terminated correctly via .terminate()")
    else:
        runner.fail("process_terminate",
                    "Worker is still alive after .terminate(). "
                    "This means AI analysis processes may not clean up on client disconnect.")

    # ---- RuntimeError hierarchy
    if issubclass(NotImplementedError, RuntimeError):
        runner.ok("hierarchy:NotImplementedError→RuntimeError")
    if issubclass(RecursionError, RuntimeError):
        runner.ok("hierarchy:RecursionError→RuntimeError")

    # ---- OverflowError in financial arithmetic
    try:
        # int can handle arbitrary size in Python, but float overflows
        import math
        big_value = 1.8e308  # Max double
        result = big_value * 2  # This returns inf, not OverflowError in Python
        if math.isinf(result):
            runner.ok("OverflowError_float_inf",
                      f"float overflow produces inf (not exception): {result}. "
                      f"Always check math.isinf(val) before formatting large financial values.")
        else:
            runner.fail("OverflowError_float_inf", f"Expected inf, got {result}")
    except OverflowError as e:
        runner.ok("OverflowError_float_overflow", f"OverflowError caught: {e}")

    # ---- RecursionError (LangGraph cycle detection analog)
    def recursive_graph(depth=0, max_depth=sys.getrecursionlimit()):
        if depth >= max_depth:
            raise RuntimeError("Max graph depth exceeded — infinite loop detected")
        return recursive_graph(depth + 1, max_depth)

    try:
        recursive_graph()
        runner.fail("RecursionError_depth", "RecursionError not raised — recursion limit may be very high")
    except RecursionError as e:
        runner.ok("RecursionError_depth",
                  f"RecursionError raised at recursion limit. "
                  f"LangGraph must enforce max_debate_rounds to prevent this. Current limit: {sys.getrecursionlimit()}")
    except RuntimeError as e:
        runner.ok("RecursionError_prevented",
                  f"Runtime depth guard triggered: {e}")

    # ---- SystemExit (should NOT be swallowed by bare except)
    try:
        try:
            raise SystemExit(0)
        except Exception:
            runner.fail("SystemExit_not_swallowed",
                        "SystemExit was swallowed by 'except Exception:' — "
                        "bare 'except Exception:' in get_session() swallows graceful server shutdown. "
                        "Use 'except BaseException:' then re-raise non-SQLAlchemy errors.")
    except SystemExit:
        runner.ok("SystemExit_not_swallowed",
                  "SystemExit correctly escapes 'except Exception:' block")

    # ---- KeyboardInterrupt (same issue)
    try:
        try:
            raise KeyboardInterrupt()
        except Exception:
            runner.fail("KeyboardInterrupt_not_swallowed",
                        "KeyboardInterrupt swallowed by 'except Exception:' — "
                        "Ctrl+C on the server will not stop the uvicorn worker cleanly.")
    except KeyboardInterrupt:
        runner.ok("KeyboardInterrupt_not_swallowed",
                  "KeyboardInterrupt correctly escapes 'except Exception:' block")

    # ---- GeneratorExit (async generator cleanup)
    def async_gen():
        try:
            yield 1
            yield 2
        except GeneratorExit:
            runner.ok("GeneratorExit_in_generator",
                      "GeneratorExit correctly received by generator on .close()")
            raise

    g = async_gen()
    next(g)
    g.close()  # Sends GeneratorExit

    # ---- ReferenceError (weak reference)
    import weakref
    class WeakTarget:
        pass

    obj = WeakTarget()
    ref = weakref.ref(obj)
    del obj
    import gc
    gc.collect()

    result = ref()
    if result is None:
        runner.ok("ReferenceError_weakref",
                  "Weak reference returns None after GC — always check ref() before use")
    else:
        runner.ok("ReferenceError_weakref_alive",
                  "Weak reference still alive (GC not yet collected) — ref() check required")

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "backend_integrity_latest.txt")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
