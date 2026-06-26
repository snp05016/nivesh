import logging
"""
database_integrity_tests/_base.py
====================================
Shared test harness for all database integrity tests.
Bootstraps an isolated in-memory SQLite DB from the real ORM models,
provides a rich logging mechanism, and exposes assertion helpers.
"""
from __future__ import annotations

import os
import sys
import traceback
import datetime
import inspect
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path bootstrap: ensure backend/ is on sys.path
# ---------------------------------------------------------------------------
_BACKEND = Path(__file__).parent.parent.parent          # backend/
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Silence heavy optional dependencies that are not needed for DB tests
import unittest.mock as _mock
for _mod in [
    "tradingagents", "tradingagents.graph", "tradingagents.graph.trading_graph",
    "tradingagents.default_config", "tradingagents.agents",
    "tradingagents.agents.utils", "tradingagents.agents.utils.agent_states",
    "langchain_anthropic", "langchain_core", "langchain_core.messages",
    "langchain_core.prompts", "langchain_core.tools", "langgraph", "langgraph.graph",
    "apscheduler", "apscheduler.schedulers", "apscheduler.schedulers.asyncio",
    "anthropic", "openai", "prompts", "yfinance", "openpyxl", "openpyxl.styles",
    "services.options_scraper", "services.nse_data_provider", "services.disk_cache",
    "services.piotroski",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _mock.MagicMock()

# Set minimal env so database.py selects an in-memory SQLite
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "db_integrity_test_secret")

from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.orm import sessionmaker, Session

# Import the real ORM models
from models.db_models import (
    Base, User, Portfolio, AnalysisHistory, SignalEvent, AnalysisJob,
    PriceTarget, TradeJournal, DeviceToken, AdvisorInsight, NewsArticle,
    YouTubeVideo, PortfolioValuationHistory, PKScreenerSignal, MacroEvent,
    NetWorthLedger, MarketErrorLog, EarningsAlert, EarningsErrorLog,
    BlockDeal, FIIDIIFlow, NotificationErrorLog, AdvisorBiography,
    TextAdvisoryInsight, IdeasErrorLog, MarketAnomaly, EarningsSurpriseHistory,
)

# ---------------------------------------------------------------------------
# Engine & Session factory for tests (isolated in-memory DB per module)
# ---------------------------------------------------------------------------

def make_test_engine(echo: bool = False):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=echo,
    )
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def _wal(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    return engine


def make_session(engine) -> Session:
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return factory()


# ---------------------------------------------------------------------------
# All known ORM table models (ordered for easy iteration)
# ---------------------------------------------------------------------------
ALL_MODELS = [
    User, Portfolio, AnalysisHistory, SignalEvent, AnalysisJob,
    PriceTarget, TradeJournal, DeviceToken, AdvisorInsight, NewsArticle,
    YouTubeVideo, PortfolioValuationHistory, PKScreenerSignal, MacroEvent,
    NetWorthLedger, MarketErrorLog, EarningsAlert, EarningsErrorLog,
    BlockDeal, FIIDIIFlow, NotificationErrorLog, AdvisorBiography,
    TextAdvisoryInsight, IdeasErrorLog, MarketAnomaly, EarningsSurpriseHistory,
]

# ---------------------------------------------------------------------------
# Test result logger
# ---------------------------------------------------------------------------

class TestRunner:
    """Lightweight test runner with structured logging."""

    def __init__(self, name: str):
        self.name = name
        self.results: list[dict] = []
        self._engine = None
        self._session = None

    def setup(self):
        self._engine = make_test_engine()
        self._session = make_session(self._engine)

    def teardown(self):
        if self._session:
            self._session.close()
        if self._engine:
            self._engine.dispose()

    @property
    def session(self) -> Session:
        return self._session

    @property
    def engine(self):
        return self._engine

    def ok(self, test_name: str, detail: str = ""):
        self.results.append({"status": "PASS", "test": test_name, "detail": detail})
        logging.info(f"  [PASS] {test_name}" + (f" — {detail}" if detail else ""))

    def fail(self, test_name: str, detail: str, exc: Exception | None = None):
        frame = inspect.stack()[1]
        loc = f"{frame.filename}:{frame.lineno}"
        tb = traceback.format_exc() if exc else ""
        self.results.append({
            "status": "FAIL",
            "test": test_name,
            "detail": detail,
            "location": loc,
            "traceback": tb,
        })
        logging.info(f"  [FAIL] {test_name} — {detail}")
        if tb:
            logging.info(tb)

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
