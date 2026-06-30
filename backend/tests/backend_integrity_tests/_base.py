from __future__ import annotations
import logging
"""
backend_integrity_tests/_base.py
================================
Shared test harness for backend integrity tests.
Provides structured logging with file:line details for LLM debugging.
"""

import sys
import os
import traceback
import datetime
import inspect
from pathlib import Path


class TestRunner:
    """Lightweight test runner producing structured logs with full context."""

    def __init__(self, name: str):
        self.name = name
        self.results: list[dict] = []

    def ok(self, test_name: str, detail: str = ""):
        self.results.append({"status": "PASS", "test": test_name, "detail": detail})
        logging.info(f"  [PASS] {test_name}" + (f" — {detail}" if detail else ""))

    def fail(self, test_name: str, detail: str, exc: Exception | None = None):
        frame = inspect.stack()[1]
        loc = f"{frame.filename}:{frame.lineno}"
        tb = ""
        if exc is not None:
            tb = traceback.format_exc()
        self.results.append({
            "status": "FAIL",
            "test": test_name,
            "detail": detail,
            "location": loc,
            "traceback": tb,
        })
        logging.info(f"  [FAIL] {test_name} at {loc}")
        logging.info(f"         {detail}")
        if tb:
            for line in tb.splitlines():
                logging.info(f"           {line}")

    def summarize(self) -> tuple[int, int]:
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        logging.info(f"\n{'='*60}")
        logging.info(f"  {self.name}")
        logging.info(f"  PASSED: {passed}  FAILED: {failed}")
        logging.info(f"{'='*60}")
        return passed, failed

    def write_log(self, log_path: Path):
        ts = datetime.datetime.now().isoformat()
        with open(log_path, "a") as fh:
            fh.write(f"\n{'='*70}\n")
            fh.write(f"MODULE : {self.name}\n")
            fh.write(f"TIME   : {ts}\n")
            fh.write(f"{'='*70}\n")
            for r in self.results:
                status = r["status"]
                fh.write(f"\n  [{status}] {r['test']}\n")
                if r.get("detail"):
                    fh.write(f"         Detail   : {r['detail']}\n")
                if r.get("location"):
                    fh.write(f"         Location : {r['location']}\n")
                if r.get("traceback"):
                    fh.write("         Traceback:\n")
                    for line in r["traceback"].splitlines():
                        fh.write(f"           {line}\n")
            passed = sum(1 for r in self.results if r["status"] == "PASS")
            failed = sum(1 for r in self.results if r["status"] == "FAIL")
            fh.write(f"\n  Summary: {passed} PASSED / {failed} FAILED\n")
