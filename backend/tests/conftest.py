import logging
"""
Nivesh FastAPI Test Suite — conftest.py
Handles module-level mocking of heavy AI/trading dependencies before app import.

Run with the project venv:
    cd backend
    .venv/bin/python3 -m pytest tests/test_api.py -v --tb=short

DO NOT run with the system python3 — it lacks bcrypt/sqlalchemy/fastapi.
"""
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# ---------------------------------------------------------------------------
# STEP 1: Patch all heavy / external modules BEFORE importing the app
# ---------------------------------------------------------------------------

_HEAVY_MODS = [
    "tradingagents",
    "tradingagents.graph",
    "tradingagents.graph.trading_graph",
    "tradingagents.default_config",
    "tradingagents.agents",
    "tradingagents.agents.utils",
    "tradingagents.agents.utils.agent_states",
    "tradingagents.agents.utils.agent_utils",
    "tradingagents.graph.analyst_execution",
    "tradingagents.graph.conditional_logic",
    "tradingagents.graph.setup",
    "langchain_anthropic",
    "langchain_core",
    "langchain_core.messages",
    "langchain_core.prompts",
    "langchain_core.tools",
    "langgraph",
    "langgraph.graph",
    "apscheduler",
    "apscheduler.schedulers",
    "apscheduler.schedulers.asyncio",
    "anthropic",
    "openai",
    "prompts",
    "yfinance",
    "openpyxl",
    "openpyxl.styles",
    "services.options_scraper",
    "services.nse_data_provider",
]

# fpdf / fpdf2 need real ModuleSpec objects so that importlib.util.find_spec() returns None
# (not a MagicMock, which causes a ValueError on .__spec__ access).
# We deliberately do NOT add them to sys.modules — that way find_spec("fpdf2") returns None
# and FPDF2_AVAILABLE is set to False, which is the safe test default.

for _mod in _HEAVY_MODS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Patch specific attributes needed by app startup
_ta_mock = sys.modules["tradingagents"]
_ta_mock.graph = MagicMock()
_ta_mock.graph.trading_graph = MagicMock()
_ta_mock.graph.trading_graph.TradingAgentsGraph = MagicMock()
_ta_mock.default_config = MagicMock()
_ta_mock.default_config.DEFAULT_CONFIG = {}

# Patch prompts module with required constants
_prompts_mock = sys.modules["prompts"]
_prompts_mock.INDIAN_MARKET_SYSTEM_PROMPT = "mock_system_prompt"
_prompts_mock.NEWS_ANALYST_PERSONA = "mock_news_persona"
_prompts_mock.EXTREME_ADDENDUM = "\nmock_extreme_addendum"

# Patch langchain/langgraph specifics
_lc_msg = sys.modules["langchain_core.messages"]
_lc_msg.SystemMessage = MagicMock()
_lc_msg.HumanMessage = MagicMock()

_lc_prompt = sys.modules["langchain_core.prompts"]
_lc_prompt.ChatPromptTemplate = MagicMock()
_lc_prompt.MessagesPlaceholder = MagicMock()

_lc_tools = sys.modules["langchain_core.tools"]
_lc_tools.tool = lambda fn=None, **_kwargs: (lambda wrapped: wrapped) if fn is None else fn

_lg = sys.modules["langgraph.graph"]
_lg.StateGraph = MagicMock()
_lg.START = "START"
_lg.END = "END"

# Patch agent states
_agent_states = sys.modules["tradingagents.agents.utils.agent_states"]
_agent_states.AgentState = dict

# Patch yfinance Ticker to return empty/safe data
_yf = sys.modules["yfinance"]
_yf_ticker_mock = MagicMock()
_yf_ticker_mock.history.return_value = MagicMock(empty=True)
_yf_ticker_mock.info = {}
_yf.Ticker.return_value = _yf_ticker_mock
_yf.download.return_value = MagicMock(empty=True)

# Patch openai client
_openai = sys.modules["openai"]
_openai_client = MagicMock()
_openai.OpenAI.return_value = _openai_client
_openai_response = MagicMock()
_openai_response.choices = [MagicMock()]
_openai_response.choices[0].message.content = '{"signal":"BULLISH","confidence_pct":70}'
_openai_response.usage = MagicMock()
_openai_client.chat.completions.create.return_value = _openai_response

# Patch anthropic client
_anthropic = sys.modules["anthropic"]
_anthropic_client = MagicMock()
_anthropic.Anthropic.return_value = _anthropic_client
_anthropic_msg = MagicMock()
_anthropic_msg.content = [MagicMock(text='{"signal":"BULLISH"}')]
_anthropic_msg.usage = MagicMock(input_tokens=100, output_tokens=50)
_anthropic_client.messages.create.return_value = _anthropic_msg

_options = sys.modules["services.options_scraper"]
_options.fetch_option_chain.return_value = {}
_options.compute_derivatives_metrics.return_value = {}

_nse_dp = sys.modules["services.nse_data_provider"]
_nse_dp.get_price_history.return_value = []
_nse_dp.get_fundamentals.return_value = {}

# ---------------------------------------------------------------------------
# STEP 2: Set test environment variables
# ---------------------------------------------------------------------------
_TEST_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stockapp_test.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB_PATH}")
os.environ.setdefault("JWT_SECRET", "test_secret_key_for_pytest_only")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_key")
os.environ.setdefault("ADMIN_TOKEN", "admin")

for _path in (_TEST_DB_PATH, f"{_TEST_DB_PATH}-wal", f"{_TEST_DB_PATH}-shm"):
    try:
        os.remove(_path)
    except FileNotFoundError:
        pass

# ---------------------------------------------------------------------------
# STEP 3: Add backend to sys.path and import the app
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

# Patch services.disk_cache before app import
_disk_cache_mock = MagicMock()
_disk_cache_mock.get.return_value = None
_disk_cache_mock.set.return_value = None
_disk_cache_mock.stats.return_value = {"hits": 0, "misses": 0}
sys.modules["services.disk_cache"] = _disk_cache_mock

_piotroski_mock = MagicMock()
_piotroski_mock.compute_piotroski.return_value = {"score": 5, "interpretation": "Strong"}
sys.modules["services.piotroski"] = _piotroski_mock

from main import app
from database import init_db
init_db()

# Bypass in-memory rate limiter — tests share one IP (127.0.0.1) and would
# exhaust the 30-req/60-s window within a single test class.
import main as _main_module
_main_module._check_rate_limit = lambda _ip: True

# ---------------------------------------------------------------------------
# TEST USER CONSTANTS
# ---------------------------------------------------------------------------
TEST_USERNAME = "test_nivesh_9999"
TEST_PASSWORD = "TestPass!9999"
TEST_DISPLAY  = "Test User 9999"
TEST_USER_ID  = None   # filled by fixture


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def client():
    """Session-scoped TestClient — one client for the entire test run."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
def auth_token(client):
    """
    Register then login as test_nivesh_9999.
    Returns the access_token string.
    """
    # Try to register (may fail if user already exists from a previous run)
    client.post("/register", json={
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "display_name": TEST_DISPLAY,
    })
    # Always login
    resp = client.post("/login", json={
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    # Store the user_id globally so other fixtures can use it
    global TEST_USER_ID
    TEST_USER_ID = data["user_id"]
    return data["access_token"]


@pytest.fixture(scope="session")
def auth_headers(auth_token):
    """Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="session")
def admin_headers():
    """Admin authorization headers."""
    return {"Authorization": "Bearer admin"}


@pytest.fixture(scope="session")
def test_user_id(auth_token):
    """Return the integer user_id for the test user."""
    return TEST_USER_ID


@pytest.fixture(scope="session")
def seeded_portfolio_user_id(client, auth_token, test_user_id):
    """
    Seed the test user's portfolio with a sample holding.
    Returns the user_id (integer).
    """
    uid = test_user_id
    # Add a portfolio entry
    client.post("/portfolio/add", json={
        "user_id": uid,
        "ticker": "RELIANCE",
        "exchange": "NSE",
        "company_name": "Reliance Industries Ltd",
        "shares": 10,
        "buy_price": 2500.0,
        "group_name": "test_holdings",
    }, headers={"Authorization": f"Bearer {auth_token}"})
    return uid


@pytest.fixture(scope="session", autouse=True)
def teardown_test_user(client, request):
    """
    Session-scoped autouse fixture: delete all test user 9999 data after the
    entire test session completes.
    """
    yield
    # Teardown: remove user from DB directly
    try:
        from database import get_session, User, Portfolio, PriceTarget, TradeJournal, DeviceToken
        with get_session() as session:
            user = session.query(User).filter_by(username=TEST_USERNAME.lower()).first()
            if user:
                # Cascade deletes handle related rows if relationships are configured
                session.delete(user)
                session.commit()
    except Exception as e:
        logging.info(f"[Teardown] Warning — could not clean up test user: {e}")


@pytest.fixture(scope="session", autouse=True)
def seed_job_test_users():
    """Create stub users for job/worker tests that reference hard-coded user IDs.
    These IDs are needed to satisfy the FK constraint on analysis_jobs.user_id
    now that PRAGMA foreign_keys=ON is enforced.
    """
    import sqlite3
    from pathlib import Path
    db_path = Path(__file__).parent.parent / "stockapp_test.db"
    conn = sqlite3.connect(str(db_path))
    test_ids = [990001, 990002, 990003, 11_111_111, 11_111_112, 22_222_221]
    for uid in test_ids:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash, display_name) VALUES (?, ?, ?, ?)",
            (uid, f"_test_stub_{uid}", "x", f"Test Stub {uid}")
        )
    conn.commit()
    yield
    for uid in test_ids:
        conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    conn.close()
