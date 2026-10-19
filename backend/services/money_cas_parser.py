"""CAS PDF -> normalized fund balances, parsed in a killable child process (spec 3.5).

casparser runs in a ``spawn`` child with an address-space cap and a wall-clock limit, so a
hostile or huge PDF cannot take the API process down. The child returns only the PII-stripped
dict from ``money_cas_mapping.normalize``. At most two parses run at once. The PDF, its password
and any exception text are never logged; only exception class names are.
"""
from __future__ import annotations

import importlib
import io
import logging
import multiprocessing
import os
import threading
from typing import Any

from services import money_cas_mapping

logger = logging.getLogger(__name__)

PARSE_TIMEOUT_SECONDS = 30.0
MAX_CONCURRENT = 2
DEFAULT_TARGET = "services.money_cas_parser:_read_and_normalize"
CODES = ("WRONG_PASSWORD", "UNSUPPORTED_STATEMENT", "DEMAT_CAS_NOT_SUPPORTED", "PARSE_TIMEOUT", "PARSE_BUSY")

_SEM = threading.BoundedSemaphore(MAX_CONCURRENT)


class CASParseError(Exception):
    """``code`` is one of CODES; the message is the code, never statement text."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _read_and_normalize(data: bytes, password: str) -> dict:
    """Runs inside the child. Raises CASParseError; returns the normalized statement only."""
    import casparser
    from casparser.exceptions import IncorrectPasswordError

    try:
        cas = casparser.read_cas_pdf(io.BytesIO(data), password, output="dict")
    except IncorrectPasswordError:
        raise CASParseError("WRONG_PASSWORD") from None
    except Exception as exc:
        logger.warning("casparser failed: %s", type(exc).__name__)
        raise CASParseError("UNSUPPORTED_STATEMENT") from None
    source = str(getattr(cas, "file_type", None) or (cas.get("file_type") if isinstance(cas, dict) else ""))
    if source in ("NSDL", "CDSL"):
        raise CASParseError("DEMAT_CAS_NOT_SUPPORTED")
    return money_cas_mapping.normalize(cas)


def _child(conn: Any, target: str, data: bytes, password: str) -> None:
    try:
        try:
            import resource

            mb = int(os.environ.get("MONEY_CAS_PARSE_MEM_MB", "512"))
            limit = mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        except (ImportError, ValueError, OSError):
            pass
        module_name, _, func_name = target.partition(":")
        func = getattr(importlib.import_module(module_name), func_name)
        conn.send(("ok", func(data, password)))
    except CASParseError as exc:
        conn.send(("err", exc.code))
    except BaseException as exc:  # includes MemoryError; never send text
        logger.warning("cas child failed: %s", type(exc).__name__)
        try:
            conn.send(("err", "UNSUPPORTED_STATEMENT"))
        except Exception:
            pass
    finally:
        conn.close()


def parse_cas_pdf(data: bytes, password: str, *, target: str = DEFAULT_TARGET, timeout: float = PARSE_TIMEOUT_SECONDS) -> dict:
    """Parse in a child process; raises CASParseError(code)."""
    if not _SEM.acquire(blocking=False):
        raise CASParseError("PARSE_BUSY")
    proc = None
    try:
        ctx = multiprocessing.get_context("spawn")
        recv, send = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=_child, args=(send, target, data, password), daemon=True)
        proc.start()
        send.close()
        try:
            if not recv.poll(timeout):
                raise CASParseError("PARSE_TIMEOUT")
            kind, payload = recv.recv()
        except (EOFError, OSError):
            raise CASParseError("UNSUPPORTED_STATEMENT") from None
        finally:
            recv.close()
        if kind == "ok":
            return payload
        raise CASParseError(payload if payload in CODES else "UNSUPPORTED_STATEMENT")
    finally:
        try:
            if proc is not None and proc.pid is not None:
                if proc.is_alive():
                    proc.terminate()
                    proc.join(5)
                    if proc.is_alive():
                        proc.kill()
                        proc.join(5)
                else:
                    proc.join(5)
        finally:
            _SEM.release()
