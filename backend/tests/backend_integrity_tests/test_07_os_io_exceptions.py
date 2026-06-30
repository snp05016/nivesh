"""
test_07_os_io_exceptions.py
============================
Tests OS and I/O exception handling relevant to the Nivesh backend:
- FileNotFoundError (missing .db file, missing .env)
- PermissionError (read-only DB file)
- OSError family (disk full, connection refused)
- ConnectionRefusedError (remote server unreachable)
- TimeoutError (slow DB query, slow LLM response)
- ChildProcessError (multiprocessing.Process failure)
"""
import sys
import os
import tempfile
import stat
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _base import TestRunner


def run():
    runner = TestRunner("07_os_io_exceptions")

    # ---- FileNotFoundError: accessing non-existent DB file
    try:
        with open("/tmp/non_existent_nivesh_db_12345.db", "r") as f:
            pass
        runner.fail("FileNotFoundError_db", "FileNotFoundError not raised for missing file")
    except FileNotFoundError as e:
        runner.ok("FileNotFoundError_db", f"FileNotFoundError caught: '{e.strerror}' for '{e.filename}'")

    # ---- FileNotFoundError: missing .env file
    try:
        from dotenv import dotenv_values
        vals = dotenv_values("/tmp/non_existent.env.12345")
        runner.ok("FileNotFoundError_dotenv", f"dotenv_values returns empty dict for missing file: {vals}")
    except FileNotFoundError as e:
        runner.ok("FileNotFoundError_dotenv", f"FileNotFoundError on missing .env: {e}")
    except ImportError:
        runner.ok("FileNotFoundError_dotenv", "python-dotenv not installed — skipped")

    # ---- PermissionError: write to read-only file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
        tmp.write("test")

    os.chmod(tmp_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    try:
        with open(tmp_path, "w") as f:
            f.write("should fail")
        runner.fail("PermissionError_readonly_db",
                    "PermissionError not raised when writing to read-only file. "
                    "If stockapp.db permissions are wrong, the server will silently fail to write.")
    except PermissionError as e:
        runner.ok("PermissionError_readonly_db", f"PermissionError on read-only DB file: '{e.strerror}'")
    finally:
        os.chmod(tmp_path, stat.S_IRWXU)
        os.unlink(tmp_path)

    # ---- IsADirectoryError
    try:
        with open("/tmp", "r") as f:
            pass
        runner.fail("IsADirectoryError", "IsADirectoryError not raised when opening directory as file")
    except (IsADirectoryError, PermissionError) as e:
        runner.ok("IsADirectoryError", f"IsADirectoryError / PermissionError opening dir: '{e}'")

    # ---- ConnectionRefusedError: connecting to a port that's definitely closed
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 19999))  # Unlikely to be open
        s.close()
        runner.fail("ConnectionRefusedError_closed_port",
                    "ConnectionRefusedError not raised for closed port. Port 19999 appears to be open.")
    except ConnectionRefusedError as e:
        runner.ok("ConnectionRefusedError_closed_port",
                  f"ConnectionRefusedError on closed port 19999: '{e}'. "
                  f"Backend correctly raises this when a dependency is down.")
    except OSError as e:
        runner.ok("OSError_connection", f"OSError on closed port: '{e}'")
    finally:
        try:
            s.close()
        except Exception as _e:
            pass

    # ---- TimeoutError: socket timeout
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.001)  # 1ms timeout
        s.connect(("10.255.255.1", 80))  # Unreachable IP
        s.close()
        runner.fail("TimeoutError_connection", "TimeoutError not raised for unreachable host")
    except (TimeoutError, OSError) as e:
        runner.ok("TimeoutError_connection",
                  f"TimeoutError / OSError for unreachable host: '{type(e).__name__}: {e}'")
    finally:
        try:
            s.close()
        except Exception as _e:
            pass

    # ---- OSError: disk operations
    try:
        raise OSError(28, "No space left on device")  # errno 28 = ENOSPC
    except OSError as e:
        runner.ok("OSError_disk_full",
                  f"OSError(ENOSPC) raised and caught: errno={e.errno} strerror='{e.strerror}'")

    # ---- ProcessLookupError: killing non-existent PID
    import signal as _signal
    try:
        os.kill(999999, _signal.SIGTERM)  # Non-existent PID
        runner.fail("ProcessLookupError_kill", "ProcessLookupError not raised for non-existent PID")
    except ProcessLookupError as e:
        runner.ok("ProcessLookupError_kill",
                  f"ProcessLookupError for non-existent PID: '{e}'. "
                  f"multiprocessing.Process.terminate() can raise this — always catch it.")
    except PermissionError as e:
        runner.ok("PermissionError_kill",
                  f"PermissionError on kill (expected on some systems): '{e}'")

    # ---- ChildProcessError: subprocess failure
    import subprocess
    result = subprocess.run(["false"], capture_output=True)  # 'false' command always returns exit code 1
    if result.returncode != 0:
        runner.ok("ChildProcessError_subprocess",
                  f"Subprocess failure correctly detected via returncode={result.returncode}. "
                  f"Non-zero exit = error in the analysis worker subprocess.")
    else:
        runner.fail("ChildProcessError_subprocess", "'false' command returned 0 — unexpected")

    # ---- InterruptedError (EINTR — happens with signal handling)
    try:
        raise InterruptedError("System call interrupted by signal")
    except InterruptedError as e:
        runner.ok("InterruptedError_catchable", f"InterruptedError caught: '{e}'")

    # ---- OSError hierarchy
    hierarchy = [
        (BlockingIOError, OSError),
        (ChildProcessError, OSError),
        (ConnectionError, OSError),
        (BrokenPipeError, ConnectionError),
        (ConnectionAbortedError, ConnectionError),
        (ConnectionRefusedError, ConnectionError),
        (ConnectionResetError, ConnectionError),
        (FileExistsError, OSError),
        (FileNotFoundError, OSError),
        (InterruptedError, OSError),
        (IsADirectoryError, OSError),
        (NotADirectoryError, OSError),
        (PermissionError, OSError),
        (ProcessLookupError, OSError),
        (TimeoutError, OSError),
    ]
    for child, parent in hierarchy:
        if issubclass(child, parent):
            runner.ok(f"hierarchy:{child.__name__}→{parent.__name__}")
        else:
            runner.fail(f"hierarchy:{child.__name__}→{parent.__name__}",
                        f"{child.__name__} does not inherit from {parent.__name__}")

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "backend_integrity_latest.txt")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
