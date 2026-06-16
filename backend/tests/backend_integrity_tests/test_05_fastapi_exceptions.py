"""
test_05_fastapi_exceptions.py
==============================
Tests FastAPI-specific exception handling:
- ValidationError (Pydantic v2)
- RequestValidationError (FastAPI input validation)
- HTTPException (custom error codes)
- 422 Unprocessable Entity behavior
- 401 / 403 / 404 / 500 handlers
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test_secret")

import unittest.mock as mock
for _m in ["tradingagents", "tradingagents.graph", "tradingagents.graph.trading_graph",
           "tradingagents.default_config", "tradingagents.agents",
           "tradingagents.agents.utils", "tradingagents.agents.utils.agent_states",
           "langchain_anthropic", "langchain_core", "langchain_core.messages",
           "langchain_core.prompts", "langchain_core.tools", "langgraph", "langgraph.graph",
           "apscheduler", "apscheduler.schedulers", "apscheduler.schedulers.asyncio",
           "anthropic", "openai", "prompts", "yfinance", "openpyxl", "openpyxl.styles",
           "services.options_scraper", "services.nse_data_provider",
           "services.disk_cache", "services.piotroski"]:
    if _m not in sys.modules:
        sys.modules[_m] = mock.MagicMock()
sys.modules["prompts"].INDIAN_MARKET_SYSTEM_PROMPT = "mock"
sys.modules["prompts"].NEWS_ANALYST_PERSONA = "mock"
sys.modules["prompts"].EXTREME_ADDENDUM = "\nmock"

from _base import TestRunner

# Pydantic imports
from pydantic import BaseModel, ValidationError, field_validator
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from fastapi import FastAPI
from pydantic import Field


def run():
    runner = TestRunner("05_fastapi_exceptions")

    # ---- Pydantic ValidationError
    class TickerRequest(BaseModel):
        ticker: str = Field(..., min_length=1, max_length=20)
        shares: float = Field(..., gt=0)
        buy_price: float = Field(..., gt=0)

    # Valid
    try:
        t = TickerRequest(ticker="RELIANCE", shares=10, buy_price=2500.0)
        runner.ok("pydantic_valid_model", f"Valid model created: {t.ticker}")
    except ValidationError as e:
        runner.fail("pydantic_valid_model", f"Valid model raised ValidationError: {e}")

    # Invalid: empty ticker
    try:
        TickerRequest(ticker="", shares=10, buy_price=2500.0)
        runner.fail("pydantic_empty_ticker", "Empty ticker was accepted by ValidationError")
    except ValidationError as e:
        errors = e.errors()
        runner.ok("pydantic_empty_ticker", f"Empty ticker ValidationError: {errors[0]['type']}")

    # Invalid: negative shares
    try:
        TickerRequest(ticker="RELIANCE", shares=-5, buy_price=2500.0)
        runner.fail("pydantic_negative_shares", "Negative shares accepted by Pydantic")
    except ValidationError as e:
        runner.ok("pydantic_negative_shares", f"Negative shares ValidationError: {e.errors()[0]['type']}")

    # Invalid: zero buy_price
    try:
        TickerRequest(ticker="RELIANCE", shares=10, buy_price=0)
        runner.fail("pydantic_zero_buy_price", "Zero buy_price accepted by Pydantic")
    except ValidationError as e:
        runner.ok("pydantic_zero_buy_price", f"Zero buy_price ValidationError: {e.errors()[0]['type']}")

    # ---- HTTPException
    try:
        raise HTTPException(status_code=404, detail="Ticker not found")
    except HTTPException as e:
        runner.ok("http_exception_404", f"HTTPException raised and caught: status={e.status_code} detail={e.detail}")

    try:
        raise HTTPException(status_code=401, detail="Not authenticated")
    except HTTPException as e:
        runner.ok("http_exception_401", f"HTTPException 401: {e.detail}")

    try:
        raise HTTPException(status_code=403, detail="Forbidden")
    except HTTPException as e:
        runner.ok("http_exception_403", f"HTTPException 403: {e.detail}")

    try:
        raise HTTPException(status_code=500, detail="Internal server error")
    except HTTPException as e:
        runner.ok("http_exception_500", f"HTTPException 500: {e.detail}")

    # ---- HTTPException with custom headers
    try:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except HTTPException as e:
        if e.headers and "WWW-Authenticate" in e.headers:
            runner.ok("http_exception_custom_headers", f"HTTPException custom headers work: {e.headers}")
        else:
            runner.fail("http_exception_custom_headers", f"HTTPException headers not set: {e.headers}")

    # ---- FastAPI app exception handling (end-to-end)
    app = FastAPI()

    class CreatePortfolioRequest(BaseModel):
        ticker: str = Field(..., min_length=1)
        shares: float = Field(..., gt=0)
        buy_price: float = Field(..., gt=0)

    @app.post("/portfolio/test")
    def create_portfolio(req: CreatePortfolioRequest):
        return {"ticker": req.ticker, "shares": req.shares}

    @app.get("/trigger/http-exception")
    def trigger_http():
        raise HTTPException(status_code=404, detail="Not found test")

    @app.get("/trigger/internal-error")
    def trigger_internal():
        raise RuntimeError("Simulated internal error")

    client = TestClient(app, raise_server_exceptions=False)

    # 422 on invalid input
    resp = client.post("/portfolio/test", json={"ticker": "", "shares": -1, "buy_price": 0})
    if resp.status_code == 422:
        runner.ok("fastapi_422_validation", "FastAPI returns 422 for invalid Pydantic input")
        body = resp.json()
        if "detail" in body:
            runner.ok("fastapi_422_detail", f"422 response includes detail: {str(body['detail'])[:100]}")
    else:
        runner.fail("fastapi_422_validation", f"Expected 422, got {resp.status_code}: {resp.text[:200]}")

    # 404 from HTTPException
    resp2 = client.get("/trigger/http-exception")
    if resp2.status_code == 404:
        runner.ok("fastapi_http_exception_404", "HTTPException 404 propagated correctly to client")
    else:
        runner.fail("fastapi_http_exception_404", f"Expected 404, got {resp2.status_code}")

    # 500 from RuntimeError
    resp3 = client.get("/trigger/internal-error")
    if resp3.status_code == 500:
        runner.ok("fastapi_500_internal_error", "RuntimeError correctly results in 500 response")
    else:
        runner.fail("fastapi_500_internal_error", f"Expected 500, got {resp3.status_code}: {resp3.text[:100]}")

    # 404 on non-existent route
    resp4 = client.get("/this/route/does/not/exist")
    if resp4.status_code == 404:
        runner.ok("fastapi_404_not_found", "Non-existent route returns 404")
    else:
        runner.fail("fastapi_404_not_found", f"Expected 404, got {resp4.status_code}")

    # ---- ValidationError: class is importable and catchable
    if issubclass(ValidationError, Exception):
        runner.ok("pydantic_ValidationError_importable", "pydantic.ValidationError is an Exception subclass")
    if issubclass(HTTPException, Exception):
        runner.ok("fastapi_HTTPException_importable", "fastapi.HTTPException is an Exception subclass")
    if issubclass(RequestValidationError, Exception):
        runner.ok("fastapi_RequestValidationError_importable", "RequestValidationError is an Exception subclass")

    passed, failed = runner.summarize()
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    runner.write_log(log_dir / "backend_integrity_latest.txt")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
