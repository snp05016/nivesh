import os
import json
import hashlib
import time
import time as _time
import io
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import multiprocessing
import asyncio
from fastapi import Request
from fastapi import FastAPI, HTTPException
from collections import deque
import uuid
from fastapi.responses import StreamingResponse, HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
import anthropic
import yfinance as yf

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, START, END

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font as XLFont, Alignment
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

import importlib.util as _importlib_util
FPDF2_AVAILABLE = _importlib_util.find_spec("fpdf2") is not None
if FPDF2_AVAILABLE:
    try:
        from fpdf import FPDF
    except Exception:
        FPDF2_AVAILABLE = False

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from prompts import INDIAN_MARKET_SYSTEM_PROMPT, NEWS_ANALYST_PERSONA
from database import init_db, get_session, save_analysis, get_recent_analyses, get_user_by_credentials, Portfolio, User, AnalysisHistory, SignalEvent, get_analysis_for_date, get_all_ticker_history, PriceTarget, TradeJournal, DeviceToken

# Import specific agent factories and states from core
from tradingagents.agents import create_bull_researcher, create_bear_researcher, create_research_manager, create_trader, create_aggressive_debator, create_neutral_debator, create_conservative_debator, create_portfolio_manager, create_msg_delete
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.graph.analyst_execution import build_analyst_execution_plan
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.setup import GraphSetup
from tradingagents.agents.utils.agent_utils import get_instrument_context_from_state

load_dotenv()

# Model Identifiers
HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Constants: Prompt Caching Blocks
# ---------------------------------------------------------------------------

BASE_INSTITUTIONAL_INSTRUCTION = """You are a helpful AI assistant, collaborating with other assistants. Use the provided tools to progress towards answering the question. If you are unable to fully answer, that's OK; another assistant with different tools will help where you left off. Execute what you can to make progress. If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable, prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."""

MARKET_ANALYST_PERSONA = """You are a trading assistant tasked with analyzing financial markets. Your role is to select the **most relevant indicators** for a given market condition or trading strategy from the following list. The goal is to choose up to **8 indicators** that provide complementary insights without redundancy.

Indicators:
- close_50_sma, close_200_sma, close_10_ema (Moving Averages)
- macd, macds, macdh (Momentum)
- rsi (Momentum)
- boll, boll_ub, boll_lb (Volatility)
- atr (Volatility)
- vwma (Volume)

Tool Definitions:
- get_stock_data(symbol, start_date, end_date): Retrieve OHLCV price data.
- get_indicators(symbol, indicator, curr_date, look_back_days): Get specific technical indicators.
- get_verified_market_snapshot(symbol, date): Source of truth for exact price/indicator values.

Write a very detailed and nuanced report. Append a Markdown table for key points."""



FUNDAMENTALS_ANALYST_PERSONA = """You are a researcher tasked with analyzing fundamental information. Write a comprehensive report on the company's financials (balance sheet, cash flow, income statement) and profile to gain a full view for traders.

Tool Definitions:
- get_fundamentals(ticker, curr_date): Comprehensive fundamental summary.
- get_balance_sheet(ticker, freq, curr_date): Balance sheet details.
- get_cashflow(ticker, freq, curr_date): Cash flow details.
- get_income_statement(ticker, freq, curr_date): Income statement details.

Provide specific, actionable insights. Append a Markdown table for key points."""

import threading
_token_log_lock = threading.Lock()
TOKEN_LOG_PATH = Path(__file__).parent / "token_log.jsonl"

# ---------------------------------------------------------------------------
# Dashboard state (in-memory, main process only)
# ---------------------------------------------------------------------------
_server_start = datetime.now()
_dash_lock = threading.Lock()
_active_analyses: dict = {}          # job_id -> info dict
_completed_analyses: deque = deque(maxlen=50)
_request_log: deque = deque(maxlen=200)
_token_stats: dict = {
    "total_input": 0,
    "total_output": 0,
    "total_cache_read": 0,
    "total_cache_write": 0,
    "total_calls": 0,
    "recent": deque(maxlen=20),
}

def _dash_start_job(job_id: str, ticker: str, exchange: str, user_id, mock: bool) -> None:
    with _dash_lock:
        _active_analyses[job_id] = {
            "job_id": job_id,
            "ticker": ticker.upper(),
            "exchange": exchange,
            "user_id": user_id,
            "mock": mock,
            "start_ts": datetime.now().isoformat(),
            "stage": "MOCK mode" if mock else "AI agents initializing...",
        }

def _dash_end_job(job_id: str, result: dict | None = None, error: str | None = None, killed: bool = False) -> None:
    with _dash_lock:
        job = _active_analyses.pop(job_id, None)
        if not job:
            return
        duration = (datetime.now() - datetime.fromisoformat(job["start_ts"])).total_seconds()
        entry = {**job, "end_ts": datetime.now().isoformat(), "duration_s": round(duration, 1)}
        if result:
            entry["signal"] = result.get("signal")
            entry["confidence"] = result.get("confidence_pct")
            entry["company_name"] = result.get("company_name", "")
            entry["cache_type"] = result.get("_cache_type", "FULL AI")
            entry["status"] = "completed"
        elif killed:
            entry["status"] = "disconnected"
            entry["cache_type"] = "—"
        else:
            entry["status"] = "error"
            entry["error"] = error or "unknown"
            entry["cache_type"] = "—"
        _completed_analyses.appendleft(entry)

def _dash_log_request(method: str, path: str, params: dict, status: int, duration_ms: float) -> None:
    with _dash_lock:
        _request_log.appendleft({
            "id": str(uuid.uuid4())[:8],
            "ts": datetime.now().isoformat(),
            "method": method,
            "path": path,
            "params": params,
            "status": status,
            "duration_ms": round(duration_ms),
        })


def _log_token_usage(endpoint: str, usage) -> None:
    inp  = getattr(usage, "input_tokens", 0)
    out  = getattr(usage, "output_tokens", 0)
    cr   = getattr(usage, "cache_read_input_tokens", 0)
    cw   = getattr(usage, "cache_creation_input_tokens", 0)
    try:
        entry = {
            "ts": datetime.now().isoformat(),
            "endpoint": endpoint,
            "input_tokens": inp,
            "output_tokens": out,
            "cache_creation_input_tokens": cw,
            "cache_read_input_tokens": cr,
        }
        with _token_log_lock:
            with open(TOKEN_LOG_PATH, "a") as f:
                f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    with _dash_lock:
        _token_stats["total_input"]      += inp
        _token_stats["total_output"]     += out
        _token_stats["total_cache_read"] += cr
        _token_stats["total_cache_write"]+= cw
        _token_stats["total_calls"]      += 1
        _token_stats["recent"].appendleft({
            "ts": datetime.now().isoformat(),
            "endpoint": endpoint,
            "input": inp, "output": out, "cache_read": cr, "cache_write": cw,
        })

app = FastAPI(title="Indian Stock Market Analysis API")

# ---------------------------------------------------------------------------
# CORS — env-configurable for production
# ---------------------------------------------------------------------------
from fastapi.middleware.cors import CORSMiddleware

_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _ALLOWED_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins if _origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class _RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        dur_ms = (time.time() - start) * 1000
        if request.url.path not in ("/", "/dashboard-data", "/ping"):
            _dash_log_request(
                method=request.method,
                path=request.url.path,
                params=dict(request.query_params),
                status=response.status_code,
                duration_ms=dur_ms,
            )
        return response

app.add_middleware(_RequestLogMiddleware)


@app.get("/ping")
def ping():
    """Zero-dependency liveness probe — no DB, no yfinance."""
    return {"pong": True}

_running_analyses: set[int] = set()  # user_ids with analysis currently in-flight

# Init DB and seed on startup
init_db()



EXCHANGE_SUFFIX = {"NSE": ".NS", "BSE": ".BO"}

_quick_info_cache: dict[str, tuple[float, dict]] = {}  # key -> (expiry_timestamp, data)
_QUICK_INFO_TTL = 300  # 5 minutes

# ---------------------------------------------------------------------------
# NSE Stock Directory — in-memory, searched in <1ms, no yfinance call
# ---------------------------------------------------------------------------

_NSE_DIRECTORY = [
    # Nifty 50 / Large Cap
    {"ticker": "RELIANCE",    "company_name": "Reliance Industries Ltd",        "sector": "Oil & Gas"},
    {"ticker": "TCS",         "company_name": "Tata Consultancy Services",       "sector": "IT"},
    {"ticker": "HDFCBANK",    "company_name": "HDFC Bank Ltd",                   "sector": "Banking"},
    {"ticker": "INFY",        "company_name": "Infosys Ltd",                     "sector": "IT"},
    {"ticker": "ICICIBANK",   "company_name": "ICICI Bank Ltd",                  "sector": "Banking"},
    {"ticker": "SBIN",        "company_name": "State Bank of India",             "sector": "Banking"},
    {"ticker": "BHARTIARTL",  "company_name": "Bharti Airtel Ltd",               "sector": "Telecom"},
    {"ticker": "KOTAKBANK",   "company_name": "Kotak Mahindra Bank",             "sector": "Banking"},
    {"ticker": "AXISBANK",    "company_name": "Axis Bank Ltd",                   "sector": "Banking"},
    {"ticker": "LT",          "company_name": "Larsen & Toubro Ltd",             "sector": "Engineering"},
    {"ticker": "HCLTECH",     "company_name": "HCL Technologies Ltd",            "sector": "IT"},
    {"ticker": "WIPRO",       "company_name": "Wipro Ltd",                       "sector": "IT"},
    {"ticker": "NTPC",        "company_name": "NTPC Ltd",                        "sector": "Power"},
    {"ticker": "POWERGRID",   "company_name": "Power Grid Corporation",          "sector": "Power"},
    {"ticker": "MARUTI",      "company_name": "Maruti Suzuki India Ltd",         "sector": "Auto"},
    {"ticker": "SUNPHARMA",   "company_name": "Sun Pharmaceutical Industries",   "sector": "Pharma"},
    {"ticker": "ONGC",        "company_name": "Oil & Natural Gas Corporation",   "sector": "Oil & Gas"},
    {"ticker": "ITC",         "company_name": "ITC Ltd",                         "sector": "FMCG"},
    {"ticker": "TITAN",       "company_name": "Titan Company Ltd",               "sector": "Consumer"},
    {"ticker": "BAJFINANCE",  "company_name": "Bajaj Finance Ltd",               "sector": "Finance"},
    {"ticker": "ASIANPAINT",  "company_name": "Asian Paints Ltd",                "sector": "Paints"},
    {"ticker": "NESTLEIND",   "company_name": "Nestle India Ltd",                "sector": "FMCG"},
    {"ticker": "HINDUNILVR",  "company_name": "Hindustan Unilever Ltd",          "sector": "FMCG"},
    {"ticker": "ULTRACEMCO",  "company_name": "UltraTech Cement Ltd",            "sector": "Cement"},
    {"ticker": "TATAMOTORS",  "company_name": "Tata Motors Ltd",                 "sector": "Auto"},
    {"ticker": "TATASTEEL",   "company_name": "Tata Steel Ltd",                  "sector": "Steel"},
    {"ticker": "M&M",         "company_name": "Mahindra & Mahindra",             "sector": "Auto"},
    {"ticker": "DRREDDY",     "company_name": "Dr Reddy's Laboratories",         "sector": "Pharma"},
    {"ticker": "CIPLA",       "company_name": "Cipla Ltd",                       "sector": "Pharma"},
    {"ticker": "BAJAJ-AUTO",  "company_name": "Bajaj Auto Ltd",                  "sector": "Auto"},
    {"ticker": "EICHERMOT",   "company_name": "Eicher Motors Ltd",               "sector": "Auto"},
    {"ticker": "INDUSINDBK",  "company_name": "IndusInd Bank Ltd",               "sector": "Banking"},
    {"ticker": "HINDALCO",    "company_name": "Hindalco Industries Ltd",         "sector": "Metals"},
    {"ticker": "JSWSTEEL",    "company_name": "JSW Steel Ltd",                   "sector": "Steel"},
    {"ticker": "BPCL",        "company_name": "Bharat Petroleum",                "sector": "Oil & Gas"},
    {"ticker": "TATACONSUM",  "company_name": "Tata Consumer Products",          "sector": "FMCG"},
    {"ticker": "HEROMOTOCO",  "company_name": "Hero MotoCorp Ltd",               "sector": "Auto"},
    {"ticker": "ADANIENT",    "company_name": "Adani Enterprises Ltd",           "sector": "Diversified"},
    {"ticker": "ADANIPOWER",  "company_name": "Adani Power Ltd",                 "sector": "Power"},
    {"ticker": "GRASIM",      "company_name": "Grasim Industries Ltd",           "sector": "Diversified"},
    {"ticker": "COALINDIA",   "company_name": "Coal India Ltd",                  "sector": "Mining"},
    {"ticker": "VEDL",        "company_name": "Vedanta Ltd",                     "sector": "Mining"},
    # Midcap / Portfolio holdings
    {"ticker": "SUZLON",      "company_name": "Suzlon Energy Ltd",               "sector": "Renewable Energy"},
    {"ticker": "HAL",         "company_name": "Hindustan Aeronautics Ltd",       "sector": "Defence"},
    {"ticker": "BEL",         "company_name": "Bharat Electronics Ltd",          "sector": "Defence"},
    {"ticker": "BHEL",        "company_name": "Bharat Heavy Electricals Ltd",    "sector": "Engineering"},
    {"ticker": "IRFC",        "company_name": "Indian Railway Finance Corp",     "sector": "Finance"},
    {"ticker": "CDSL",        "company_name": "Central Depository Services",     "sector": "Finance"},
    {"ticker": "BSE",         "company_name": "BSE Ltd",                         "sector": "Finance"},
    {"ticker": "POLYCAB",     "company_name": "Polycab India Ltd",               "sector": "Electricals"},
    {"ticker": "TATAELXSI",   "company_name": "Tata Elxsi Ltd",                  "sector": "IT"},
    {"ticker": "ZOMATO",      "company_name": "Zomato Ltd",                      "sector": "Consumer Tech"},
    {"ticker": "IRCTC",       "company_name": "Indian Railway Catering & Tourism","sector": "Travel"},
    {"ticker": "DMART",       "company_name": "Avenue Supermarts",               "sector": "Retail"},
    {"ticker": "IDEA",        "company_name": "Vodafone Idea Ltd",               "sector": "Telecom"},
    {"ticker": "ABBOTINDIA",  "company_name": "Abbott India Ltd",                "sector": "Pharma"},
    {"ticker": "AVANTEL",     "company_name": "Avantel Ltd",                     "sector": "Defence"},
    {"ticker": "APOLLO",      "company_name": "Apollo Microsystems Ltd",         "sector": "Defence"},
    {"ticker": "BGRENERGY",   "company_name": "BGR Energy Systems Ltd",          "sector": "Engineering"},
    {"ticker": "MCLEODRUSS",  "company_name": "McLeod Russel India Ltd",         "sector": "Tea"},
    {"ticker": "JITFINFRA",   "company_name": "JITF Infralogistics Ltd",         "sector": "Logistics"},
    {"ticker": "GAUDIUMIVF",  "company_name": "Gaudium IVF and Women Health",    "sector": "Healthcare"},
    {"ticker": "OMPOWER",     "company_name": "OM Power Trans Ltd",              "sector": "Power"},
    # Finance & Markets
    {"ticker": "RECLTD",      "company_name": "REC Ltd",                         "sector": "Finance"},
    {"ticker": "PFC",         "company_name": "Power Finance Corporation",       "sector": "Finance"},
    {"ticker": "LICI",        "company_name": "Life Insurance Corporation",      "sector": "Finance"},
    {"ticker": "JIOFIN",      "company_name": "Jio Financial Services",          "sector": "Finance"},
    {"ticker": "SBICARD",     "company_name": "SBI Cards and Payment Services",  "sector": "Finance"},
    {"ticker": "CHOLAFIN",    "company_name": "Cholamandalam Investment",        "sector": "Finance"},
    {"ticker": "MUTHOOTFIN",  "company_name": "Muthoot Finance Ltd",             "sector": "Finance"},
    {"ticker": "MANAPPURAM",  "company_name": "Manappuram Finance",              "sector": "Finance"},
    {"ticker": "CAMS",        "company_name": "Computer Age Management Services","sector": "Finance"},
    {"ticker": "MCX",         "company_name": "Multi Commodity Exchange",        "sector": "Finance"},
    {"ticker": "IEX",         "company_name": "Indian Energy Exchange",          "sector": "Finance"},
    {"ticker": "ANGELONE",    "company_name": "Angel One Ltd",                   "sector": "Finance"},
    {"ticker": "MOTILALOFS",  "company_name": "Motilal Oswal Financial",         "sector": "Finance"},
    {"ticker": "360ONE",      "company_name": "360 ONE WAM",                     "sector": "Finance"},
    {"ticker": "KFINTECH",    "company_name": "KFin Technologies",               "sector": "Finance"},
    {"ticker": "ABCAPITAL",   "company_name": "Aditya Birla Capital",            "sector": "Finance"},
    {"ticker": "L&TFH",       "company_name": "L&T Finance Holdings",            "sector": "Finance"},
    {"ticker": "EDELWEISS",   "company_name": "Edelweiss Financial",             "sector": "Finance"},
    {"ticker": "PNBHOUSING",  "company_name": "PNB Housing Finance",             "sector": "Finance"},
    {"ticker": "LICHSGFIN",   "company_name": "LIC Housing Finance",             "sector": "Finance"},
    {"ticker": "AAVAS",       "company_name": "Aavas Financiers",                "sector": "Finance"},
    {"ticker": "SUNDARMFIN",  "company_name": "Sundaram Finance",                "sector": "Finance"},
    {"ticker": "CANFINHOME",  "company_name": "Can Fin Homes",                   "sector": "Finance"},
    {"ticker": "CREDITACC",   "company_name": "CreditAccess Grameen",            "sector": "Finance"},
    {"ticker": "FUSION",      "company_name": "Fusion Micro Finance",            "sector": "Finance"},
    {"ticker": "HUDCO",       "company_name": "HUDCO",                           "sector": "Finance"},
    {"ticker": "IREDA",       "company_name": "IREDA Ltd",                       "sector": "Finance"},
    # IT
    {"ticker": "LTIM",        "company_name": "LTIMindtree",                     "sector": "IT"},
    {"ticker": "LTTS",        "company_name": "L&T Technology Services",         "sector": "IT"},
    {"ticker": "MPHASIS",     "company_name": "Mphasis Ltd",                     "sector": "IT"},
    {"ticker": "PERSISTENT",  "company_name": "Persistent Systems",              "sector": "IT"},
    {"ticker": "COFORGE",     "company_name": "Coforge Ltd",                     "sector": "IT"},
    {"ticker": "TECHM",       "company_name": "Tech Mahindra Ltd",               "sector": "IT"},
    {"ticker": "AFFLE",       "company_name": "Affle India",                     "sector": "Consumer Tech"},
    {"ticker": "INDIAMART",   "company_name": "IndiaMART InterMESH",             "sector": "IT"},
    {"ticker": "CEINFO",      "company_name": "CE Info Systems (MapMyIndia)",    "sector": "IT"},
    {"ticker": "NAZARA",      "company_name": "Nazara Technologies",             "sector": "Consumer Tech"},
    {"ticker": "TEJASNET",    "company_name": "Tejas Networks",                  "sector": "Telecom"},
    # Banking (PSU & Private)
    {"ticker": "PNB",         "company_name": "Punjab National Bank",            "sector": "Banking"},
    {"ticker": "CANBK",       "company_name": "Canara Bank",                     "sector": "Banking"},
    {"ticker": "BANKBARODA",  "company_name": "Bank of Baroda",                  "sector": "Banking"},
    {"ticker": "UNIONBANK",   "company_name": "Union Bank of India",             "sector": "Banking"},
    {"ticker": "BANKINDIA",   "company_name": "Bank of India",                   "sector": "Banking"},
    {"ticker": "INDIANB",     "company_name": "Indian Bank",                     "sector": "Banking"},
    {"ticker": "IDFCFIRSTB",  "company_name": "IDFC First Bank",                 "sector": "Banking"},
    {"ticker": "YESBANK",     "company_name": "Yes Bank Ltd",                    "sector": "Banking"},
    {"ticker": "FEDERALBNK",  "company_name": "Federal Bank Ltd",                "sector": "Banking"},
    {"ticker": "AUBANK",      "company_name": "AU Small Finance Bank",           "sector": "Banking"},
    {"ticker": "BANDHANBNK",  "company_name": "Bandhan Bank Ltd",                "sector": "Banking"},
    {"ticker": "EQUITASBNK",  "company_name": "Equitas Small Finance Bank",      "sector": "Banking"},
    {"ticker": "UJJIVANSFB",  "company_name": "Ujjivan Small Finance Bank",      "sector": "Banking"},
    {"ticker": "IDBI",        "company_name": "IDBI Bank Ltd",                   "sector": "Banking"},
    {"ticker": "RBLBANK",     "company_name": "RBL Bank Ltd",                    "sector": "Banking"},
    {"ticker": "KARURVYSYA",  "company_name": "Karur Vysya Bank",                "sector": "Banking"},
    {"ticker": "CUB",         "company_name": "City Union Bank",                 "sector": "Banking"},
    # Pharma
    {"ticker": "LUPIN",       "company_name": "Lupin Ltd",                       "sector": "Pharma"},
    {"ticker": "BIOCON",      "company_name": "Biocon Ltd",                      "sector": "Pharma"},
    {"ticker": "AUROPHARMA",  "company_name": "Aurobindo Pharma",                "sector": "Pharma"},
    {"ticker": "DIVISLAB",    "company_name": "Divis Laboratories",              "sector": "Pharma"},
    {"ticker": "TORNTPHARM",  "company_name": "Torrent Pharma",                  "sector": "Pharma"},
    {"ticker": "ZYDUSLIFE",   "company_name": "Zydus Lifesciences",              "sector": "Pharma"},
    {"ticker": "ALKEM",       "company_name": "Alkem Laboratories",              "sector": "Pharma"},
    {"ticker": "LAURUSLABS",  "company_name": "Laurus Labs Ltd",                 "sector": "Pharma"},
    {"ticker": "SYNGENE",     "company_name": "Syngene International",           "sector": "Pharma"},
    {"ticker": "GLENMARK",    "company_name": "Glenmark Pharma",                 "sector": "Pharma"},
    {"ticker": "APLLTD",      "company_name": "Alembic Pharma",                  "sector": "Pharma"},
    {"ticker": "NATCOPHARM",  "company_name": "Natco Pharma",                    "sector": "Pharma"},
    {"ticker": "PFIZER",      "company_name": "Pfizer Ltd",                      "sector": "Pharma"},
    {"ticker": "GLAXO",       "company_name": "GlaxoSmithKline Pharma",          "sector": "Pharma"},
    {"ticker": "GRANULES",    "company_name": "Granules India",                  "sector": "Pharma"},
    # Healthcare
    {"ticker": "APOLLOHOSP",  "company_name": "Apollo Hospitals",                "sector": "Healthcare"},
    {"ticker": "MAXHEALTH",   "company_name": "Max Healthcare",                  "sector": "Healthcare"},
    {"ticker": "FORTIS",      "company_name": "Fortis Healthcare",               "sector": "Healthcare"},
    {"ticker": "KIMS",        "company_name": "Krishna Institute of Medical Sciences","sector": "Healthcare"},
    {"ticker": "RAINBOW",     "company_name": "Rainbow Childrens Medicare",      "sector": "Healthcare"},
    {"ticker": "MEDANTA",     "company_name": "Global Health (Medanta)",         "sector": "Healthcare"},
    {"ticker": "POLYMED",     "company_name": "Poly Medicure Ltd",               "sector": "Healthcare"},
    # Power & Energy
    {"ticker": "NHPC",        "company_name": "NHPC Ltd",                        "sector": "Power"},
    {"ticker": "JSWENERGY",   "company_name": "JSW Energy Ltd",                  "sector": "Power"},
    {"ticker": "TATAPOWER",   "company_name": "Tata Power Company",              "sector": "Power"},
    {"ticker": "TORNTPOWER",  "company_name": "Torrent Power Ltd",               "sector": "Power"},
    {"ticker": "CESC",        "company_name": "CESC Ltd",                        "sector": "Power"},
    {"ticker": "ADANIGREEN",  "company_name": "Adani Green Energy",              "sector": "Renewable Energy"},
    {"ticker": "BORORENEW",   "company_name": "Borosil Renewables",              "sector": "Renewable Energy"},
    {"ticker": "KPIGREEN",    "company_name": "KPI Green Energy",                "sector": "Renewable Energy"},
    {"ticker": "SWSOLAR",     "company_name": "Sterling & Wilson",               "sector": "Renewable Energy"},
    # Oil & Gas
    {"ticker": "HPCL",        "company_name": "Hindustan Petroleum",             "sector": "Oil & Gas"},
    {"ticker": "IOC",         "company_name": "Indian Oil Corp",                 "sector": "Oil & Gas"},
    {"ticker": "OIL",         "company_name": "Oil India Ltd",                   "sector": "Oil & Gas"},
    {"ticker": "GAIL",        "company_name": "GAIL (India) Ltd",                "sector": "Gas"},
    {"ticker": "PETRONET",    "company_name": "Petronet LNG Ltd",                "sector": "Gas"},
    {"ticker": "IGL",         "company_name": "Indraprastha Gas Ltd",            "sector": "Gas"},
    {"ticker": "MGL",         "company_name": "Mahanagar Gas Ltd",               "sector": "Gas"},
    {"ticker": "GUJGASLTD",   "company_name": "Gujarat Gas Ltd",                 "sector": "Gas"},
    # Defence
    {"ticker": "BEML",        "company_name": "BEML Limited",                    "sector": "Defence"},
    {"ticker": "BDL",         "company_name": "Bharat Dynamics Ltd",             "sector": "Defence"},
    {"ticker": "MAZDOCK",     "company_name": "Mazagon Dock Shipbuilders",       "sector": "Defence"},
    {"ticker": "GRSE",        "company_name": "Garden Reach Shipbuilders",       "sector": "Defence"},
    {"ticker": "COCHINSHIP",  "company_name": "Cochin Shipyard Ltd",             "sector": "Defence"},
    {"ticker": "DATAPATTNS",  "company_name": "Data Patterns",                   "sector": "Defence"},
    {"ticker": "MTARTECH",    "company_name": "MTAR Technologies",               "sector": "Defence"},
    {"ticker": "PARAS",       "company_name": "Paras Defence",                   "sector": "Defence"},
    {"ticker": "ZENTEC",      "company_name": "Zen Technologies",                "sector": "Defence"},
    # Infrastructure
    {"ticker": "RVNL",        "company_name": "Rail Vikas Nigam Ltd",            "sector": "Infrastructure"},
    {"ticker": "IRCON",       "company_name": "Ircon International",             "sector": "Infrastructure"},
    {"ticker": "NBCC",        "company_name": "NBCC (India) Ltd",                "sector": "Infrastructure"},
    {"ticker": "GRINFRA",     "company_name": "G R Infraprojects",               "sector": "Infrastructure"},
    {"ticker": "ASHOKA",      "company_name": "Ashoka Buildcon",                 "sector": "Infrastructure"},
    {"ticker": "KNRCON",      "company_name": "KNR Constructions",               "sector": "Infrastructure"},
    {"ticker": "PNCINFRA",    "company_name": "PNC Infratech Ltd",               "sector": "Infrastructure"},
    # Chemicals
    {"ticker": "PIDILITIND",  "company_name": "Pidilite Industries",             "sector": "Chemicals"},
    {"ticker": "SRF",         "company_name": "SRF Ltd",                         "sector": "Chemicals"},
    {"ticker": "UPL",         "company_name": "UPL Ltd",                         "sector": "Chemicals"},
    {"ticker": "AARTIIND",    "company_name": "Aarti Industries Ltd",            "sector": "Chemicals"},
    {"ticker": "DEEPAKNTR",   "company_name": "Deepak Nitrite Ltd",              "sector": "Chemicals"},
    {"ticker": "TATACHEM",    "company_name": "Tata Chemicals Ltd",              "sector": "Chemicals"},
    {"ticker": "VINATIORGA",  "company_name": "Vinati Organics",                 "sector": "Chemicals"},
    {"ticker": "FINEORG",     "company_name": "Fine Organic Industries",         "sector": "Chemicals"},
    {"ticker": "GALAXYSURF",  "company_name": "Galaxy Surfactants",              "sector": "Chemicals"},
    {"ticker": "CLEAN",       "company_name": "Clean Science & Tech",            "sector": "Chemicals"},
    {"ticker": "ROSSARI",     "company_name": "Rossari Biotech",                 "sector": "Chemicals"},
    {"ticker": "AETHER",      "company_name": "Aether Industries",               "sector": "Chemicals"},
    # Consumer / FMCG / Retail
    {"ticker": "VBL",         "company_name": "Varun Beverages Ltd",             "sector": "FMCG"},
    {"ticker": "BRITANNIA",   "company_name": "Britannia Industries",            "sector": "FMCG"},
    {"ticker": "DABUR",       "company_name": "Dabur India Ltd",                 "sector": "FMCG"},
    {"ticker": "MARICO",      "company_name": "Marico Ltd",                      "sector": "FMCG"},
    {"ticker": "COLPAL",      "company_name": "Colgate-Palmolive India",         "sector": "FMCG"},
    {"ticker": "GODREJCP",    "company_name": "Godrej Consumer Products",        "sector": "FMCG"},
    {"ticker": "AWL",         "company_name": "Adani Wilmar",                    "sector": "FMCG"},
    {"ticker": "PATANJALI",   "company_name": "Patanjali Foods",                 "sector": "FMCG"},
    {"ticker": "BIKAJI",      "company_name": "Bikaji Foods",                    "sector": "FMCG"},
    {"ticker": "TRENT",       "company_name": "Trent Ltd",                       "sector": "Retail"},
    {"ticker": "KALYANKJIL",  "company_name": "Kalyan Jewellers",                "sector": "Consumer"},
    {"ticker": "TITAN",       "company_name": "Titan Company Ltd",               "sector": "Consumer"},
    {"ticker": "MANYAVAR",    "company_name": "Vedant Fashions",                 "sector": "Retail"},
    {"ticker": "METROBRAND",  "company_name": "Metro Brands",                    "sector": "Retail"},
    # Auto
    {"ticker": "ESCORTS",     "company_name": "Escorts Kubota Ltd",              "sector": "Auto"},
    {"ticker": "ASHOKLEY",    "company_name": "Ashok Leyland Ltd",               "sector": "Auto"},
    {"ticker": "TVSMOTOR",    "company_name": "TVS Motor Company",               "sector": "Auto"},
    {"ticker": "MRF",         "company_name": "MRF Ltd",                         "sector": "Tyres"},
    {"ticker": "APOLLOTYRE",  "company_name": "Apollo Tyres Ltd",                "sector": "Tyres"},
    {"ticker": "BALKRISIND",  "company_name": "Balkrishna Industries",           "sector": "Tyres"},
    {"ticker": "CEATLTD",     "company_name": "CEAT Ltd",                        "sector": "Tyres"},
    {"ticker": "BHARATFORG",  "company_name": "Bharat Forge Ltd",                "sector": "Auto Ancillary"},
    {"ticker": "BOSCHLTD",    "company_name": "Bosch Ltd",                       "sector": "Auto Ancillary"},
    {"ticker": "MOTHERSON",   "company_name": "Samvardhana Motherson",           "sector": "Auto Ancillary"},
    {"ticker": "SONACOMS",    "company_name": "Sona BLW Precision",              "sector": "Auto Ancillary"},
    {"ticker": "UNOMINDA",    "company_name": "Uno Minda Ltd",                   "sector": "Auto Ancillary"},
    # Real Estate
    {"ticker": "DLF",         "company_name": "DLF Ltd",                         "sector": "Real Estate"},
    {"ticker": "GODREJPROP",  "company_name": "Godrej Properties",               "sector": "Real Estate"},
    {"ticker": "OBEROIRLTY",  "company_name": "Oberoi Realty Ltd",               "sector": "Real Estate"},
    {"ticker": "LODHA",       "company_name": "Macrotech Developers",            "sector": "Real Estate"},
    {"ticker": "PRESTIGE",    "company_name": "Prestige Estate",                 "sector": "Real Estate"},
    {"ticker": "PHOENIXLTD",  "company_name": "Phoenix Mills Ltd",               "sector": "Real Estate"},
    {"ticker": "BRIGADE",     "company_name": "Brigade Enterprises",             "sector": "Real Estate"},
    # Consumer Tech / Startups
    {"ticker": "NYKAA",       "company_name": "FSN E-Commerce (Nykaa)",          "sector": "Consumer Tech"},
    {"ticker": "PAYTM",       "company_name": "One 97 Communications",           "sector": "Consumer Tech"},
    {"ticker": "POLICYBZR",   "company_name": "PB Fintech (PolicyBazaar)",       "sector": "Consumer Tech"},
    {"ticker": "DELHIVERY",   "company_name": "Delhivery Ltd",                   "sector": "Logistics"},
    {"ticker": "ZEEL",        "company_name": "Zee Entertainment",               "sector": "Media"},
    {"ticker": "SUNTV",       "company_name": "Sun TV Network Ltd",              "sector": "Media"},
    # Cement
    {"ticker": "SHREECEM",    "company_name": "Shree Cement Ltd",                "sector": "Cement"},
    {"ticker": "ACC",         "company_name": "ACC Ltd",                         "sector": "Cement"},
    {"ticker": "AMBUJACEM",   "company_name": "Ambuja Cements Ltd",              "sector": "Cement"},
    {"ticker": "DALBHARAT",   "company_name": "Dalmia Bharat Ltd",               "sector": "Cement"},
    {"ticker": "JKCEMENT",    "company_name": "JK Cement Ltd",                   "sector": "Cement"},
    {"ticker": "RAMCOCEM",    "company_name": "Ramco Cements",                   "sector": "Cement"},
    # Steel / Metals / Mining
    {"ticker": "SAIL",        "company_name": "Steel Authority of India",        "sector": "Steel"},
    {"ticker": "HINDZINC",    "company_name": "Hindustan Zinc Ltd",              "sector": "Metals"},
    {"ticker": "NMDC",        "company_name": "NMDC Ltd",                        "sector": "Mining"},
    # Consumer Durables
    {"ticker": "HAVELLS",     "company_name": "Havells India Ltd",               "sector": "Consumer Durables"},
    {"ticker": "VOLTAS",      "company_name": "Voltas Ltd",                      "sector": "Consumer Durables"},
    {"ticker": "DIXON",       "company_name": "Dixon Technologies",              "sector": "Consumer Durables"},
    {"ticker": "BLUESTARCO",  "company_name": "Blue Star Ltd",                   "sector": "Consumer Durables"},
    {"ticker": "WHIRLPOOL",   "company_name": "Whirlpool of India",              "sector": "Consumer Durables"},
    # Hotels
    {"ticker": "INDHOTEL",    "company_name": "Indian Hotels Co Ltd",            "sector": "Hotels"},
    {"ticker": "EIHOTEL",     "company_name": "EIH Ltd (Oberoi Hotels)",         "sector": "Hotels"},
    {"ticker": "LEMONTREE",   "company_name": "Lemon Tree Hotels",               "sector": "Hotels"},
    # Fertilizers
    {"ticker": "COROMANDEL",  "company_name": "Coromandel International",        "sector": "Fertilizers"},
    {"ticker": "CHAMBLFERT",  "company_name": "Chambal Fertilizers",             "sector": "Fertilizers"},
    {"ticker": "DEEPAKFERT",  "company_name": "Deepak Fertilisers",              "sector": "Fertilizers"},
    # Additional prominent names
    {"ticker": "NAUKRI",      "company_name": "Info Edge (Naukri)",              "sector": "IT"},
    {"ticker": "ZOMATO",      "company_name": "Zomato Ltd",                      "sector": "Consumer Tech"},
    {"ticker": "SWIGGY",      "company_name": "Bundl Technologies (Swiggy)",     "sector": "Consumer Tech"},
    {"ticker": "IXIGO",       "company_name": "Le Travenues Technology (ixigo)", "sector": "Consumer Tech"},
    {"ticker": "KAYNES",      "company_name": "Kaynes Technology",               "sector": "Engineering"},
    {"ticker": "SYRMA",       "company_name": "Syrma SGS Technology",            "sector": "Engineering"},
    {"ticker": "AVALON",      "company_name": "Avalon Technologies",             "sector": "Engineering"},
    {"ticker": "DOMS",        "company_name": "DOMS Industries",                 "sector": "Consumer"},
    {"ticker": "VARUN",       "company_name": "Varun Beverages Ltd",             "sector": "FMCG"},
    {"ticker": "PVRINOX",     "company_name": "PVR INOX Ltd",                    "sector": "Media"},
    {"ticker": "INOXWIND",    "company_name": "Inox Wind Ltd",                   "sector": "Renewable Energy"},
    {"ticker": "WAAREEENER",  "company_name": "Waaree Energies",                 "sector": "Renewable Energy"},
    {"ticker": "PREMIERENE",  "company_name": "Premier Energies",                "sector": "Renewable Energy"},
]

# Pre-process for fast search: lowercase index
_NSE_DIR_INDEX = [
    {
        "ticker": e["ticker"],
        "company_name": e["company_name"],
        "sector": e["sector"],
        "exchange": "NSE",
        "_t": e["ticker"].lower(),
        "_n": e["company_name"].lower(),
        "_s": e["sector"].lower(),
    }
    for e in _NSE_DIRECTORY
]

NSE_TICKERS = {t: f"{t}.NS" for t in [
    "BGRENERGY", "MCLEODRUSS", "CDSL", "GAUDIUMIVF",
    "SBIN", "TATAELXSI", "OMPOWER", "AVANTEL", "ABBOTINDIA",
    "SUZLON", "POLYCAB", "HAL", "IDEA", "APOLLO", "BSE",
]}
# Special cases where NSE ticker differs from yfinance symbol
NSE_TICKER_OVERRIDES = {
    "JITFINFRA": "JITFINFRA.NS",
    "GAUDIUMIVF": "GAUDIUMIVF.NS",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_ticker(ticker: str, exchange: str) -> str:
    suffix = EXCHANGE_SUFFIX[exchange]
    t = ticker.upper()
    if t.endswith(".NS") or t.endswith(".BO"):
        return t
    # Handle common abbreviations or missing suffixes
    if t == "BGR": t = "BGRENERGY"
    if t == "MCLEOD": t = "MCLEODRUSS"
    if t == "SUZLON": return "SUZLON.NS"
    if t == "IDEA": return "IDEA.NS"
    if t == "GIFT" or t == "JITFINFRA": return "JITFINFRA.NS"
    if t == "GAUDIUM" or t == "GAUDIUMIVF": return "GAUDIUMIVF.NS"
    if t in NSE_TICKER_OVERRIDES: return NSE_TICKER_OVERRIDES[t]
    return NSE_TICKERS.get(t, f"{t}{suffix}")





def _yf_fetch_info(sym: str) -> dict:
    """Fetch yfinance info with 3 attempts and exponential backoff."""
    import time
    import random
    for attempt in range(3):
        try:
            info = yf.Ticker(sym).info
            if info and (info.get("currentPrice") or info.get("regularMarketPrice")):
                # Check for pledging info (attempt)
                if not any("pledge" in k.lower() for k in info.keys()):
                    print(f"[WARN] No promoter pledging data found in .info for {sym}")
                return info
        except Exception as e:
            print(f"[YF] Attempt {attempt+1} failed for {sym}: {e}")
            if attempt < 2:
                # Exponential backoff: 1.5s, 3s, etc. + jitter
                sleep_time = (1.5 * (2 ** attempt)) + (random.random() * 0.5)
                time.sleep(sleep_time)
    return {}


def _yf_price(ticker_sym: str) -> tuple[float | None, float | None]:
    """Return (current_price, prev_close) with retry and BSE->NSE fallback."""
    def _fetch(sym: str):
        info = _yf_fetch_info(sym)
        current = info.get("currentPrice") or info.get("regularMarketPrice")
        prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
        return current, prev

    current, prev = _fetch(ticker_sym)
    if current is None and ticker_sym.upper().endswith(".BO"):
        ns_sym = ticker_sym[:-3] + ".NS"
        print(f"[BSE FALLBACK] No data for {ticker_sym}, trying {ns_sym}")
        current, prev = _fetch(ns_sym)
    return current, prev


def _to_ns(ticker: str) -> str:
    """Convert bare ticker to .NS suffix for yfinance."""
    t = ticker.upper()
    if "." in t:
        return t
    return NSE_TICKERS.get(t, f"{t}.NS")


def _extract_json_from_text(text: str) -> str:
    """Extract JSON from markdown code blocks or return raw text."""
    if "```json" in text:
        return text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        return text.split("```")[1].strip()
    return text.strip()


# ---------------------------------------------------------------------------
# Optimized Analyst Node Factory
# ---------------------------------------------------------------------------

def create_optimized_analyst_node(llm, persona: str, report_key: str, tools: list):
    def analyst_node(state):
        instrument_context = get_instrument_context_from_state(state)
        current_date = state["trade_date"]
        
        # Dual-Breakpoint Cache Strategy for Analyst Node
        # 1. Static Institutional Instruction (Shared across all nodes)
        # 2. Specific Persona & Tools (Stable for this analyst type)
        # 3. Volatile Context (Ticker, Date - in HumanMessage)
        
        system_blocks = [
            {
                "type": "text", 
                "text": BASE_INSTITUTIONAL_INSTRUCTION,
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": f"{persona}\n\nYou have access to the following tools: {', '.join([t.name for t in tools])}.",
                "cache_control": {"type": "ephemeral"}
            }
        ]
        
        volatile_context = f"The current trading date is {current_date}. {instrument_context}"
        
        messages = [
            SystemMessage(content=system_blocks),
            MessagesPlaceholder(variable_name="messages"),
            HumanMessage(content=volatile_context)
        ]
        
        prompt = ChatPromptTemplate.from_messages(messages)
        chain = prompt | llm.bind_tools(tools)
        
        result = chain.invoke(state["messages"])
        report = result.content if not result.tool_calls else ""
        
        return {
            "messages": [result],
            f"{report_key}_report": report,
        }
    return analyst_node

# ---------------------------------------------------------------------------
# Optimized Graph Setup
# ---------------------------------------------------------------------------

class OptimizedGraphSetup(GraphSetup):
    def setup_graph(self, selected_analysts=["market", "news", "fundamentals"]):
        from tradingagents.agents.utils.agent_utils import (
            get_stock_data, get_indicators, get_news, get_global_news, 
            get_insider_transactions, get_fundamentals, get_balance_sheet, 
            get_cashflow, get_income_statement
        )
        
        plan = build_analyst_execution_plan(selected_analysts, concurrency_limit=self.analyst_concurrency_limit)
        
        analyst_factories = {
            "market": lambda: create_optimized_analyst_node(
                self.quick_thinking_llm, MARKET_ANALYST_PERSONA, "market",
                [get_stock_data, get_indicators]
            ),
            "news": lambda: create_optimized_analyst_node(
                self.quick_thinking_llm, NEWS_ANALYST_PERSONA, "news",
                [get_news, get_global_news, get_insider_transactions]
            ),
            "fundamentals": lambda: create_optimized_analyst_node(
                self.quick_thinking_llm, FUNDAMENTALS_ANALYST_PERSONA, "fundamentals",
                [get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement]
            ),
            "social": lambda: create_optimized_analyst_node(
                self.quick_thinking_llm, "You are a sentiment analyst.", "sentiment", [get_news]
            )
        }

        bull_researcher_node = create_bull_researcher(self.quick_thinking_llm)
        bear_researcher_node = create_bear_researcher(self.quick_thinking_llm)
        research_manager_node = create_research_manager(self.deep_thinking_llm)
        trader_node = create_trader(self.quick_thinking_llm)
        aggressive_analyst = create_aggressive_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        conservative_analyst = create_conservative_debator(self.quick_thinking_llm)
        portfolio_manager_node = create_portfolio_manager(self.deep_thinking_llm)

        workflow = StateGraph(AgentState)
        for spec in plan.specs:
            workflow.add_node(spec.agent_node, analyst_factories[spec.key]())
            workflow.add_node(spec.clear_node, create_msg_delete())
            workflow.add_node(spec.tool_node, self.tool_nodes[spec.key])

        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Aggressive Analyst", aggressive_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Conservative Analyst", conservative_analyst)
        workflow.add_node("Portfolio Manager", portfolio_manager_node)

        workflow.add_edge(START, plan.specs[0].agent_node)
        for i, spec in enumerate(plan.specs):
            workflow.add_conditional_edges(spec.agent_node, getattr(self.conditional_logic, f"should_continue_{spec.key}"), [spec.tool_node, spec.clear_node])
            workflow.add_edge(spec.tool_node, spec.agent_node)
            if i < len(plan.specs) - 1:
                workflow.add_edge(spec.clear_node, plan.specs[i+1].agent_node)
            else:
                workflow.add_edge(spec.clear_node, "Bull Researcher")

        workflow.add_conditional_edges("Bull Researcher", self.conditional_logic.should_continue_debate, {"Bear Researcher": "Bear Researcher", "Research Manager": "Research Manager"})
        workflow.add_conditional_edges("Bear Researcher", self.conditional_logic.should_continue_debate, {"Bull Researcher": "Bull Researcher", "Research Manager": "Research Manager"})
        workflow.add_edge("Research Manager", "Trader")
        workflow.add_edge("Trader", "Aggressive Analyst")
        workflow.add_conditional_edges("Aggressive Analyst", self.conditional_logic.should_continue_risk_analysis, {"Conservative Analyst": "Conservative Analyst", "Portfolio Manager": "Portfolio Manager"})
        workflow.add_conditional_edges("Conservative Analyst", self.conditional_logic.should_continue_risk_analysis, {"Neutral Analyst": "Neutral Analyst", "Portfolio Manager": "Portfolio Manager"})
        workflow.add_conditional_edges("Neutral Analyst", self.conditional_logic.should_continue_risk_analysis, {"Aggressive Analyst": "Aggressive Analyst", "Portfolio Manager": "Portfolio Manager"})
        workflow.add_edge("Portfolio Manager", END)

        return workflow

class OptimizedTradingAgentsGraph(TradingAgentsGraph):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.graph_setup = OptimizedGraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.conditional_logic,
            analyst_concurrency_limit=self.config.get("analyst_concurrency_limit", 1),
        )
        self.workflow = self.graph_setup.setup_graph(kwargs.get("selected_analysts", ["market", "news", "fundamentals"]))
        self.graph = self.workflow.compile()

# ---------------------------------------------------------------------------
# TradingAgents
# ---------------------------------------------------------------------------

def build_ta_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "anthropic"
    config["deep_think_llm"] = HAIKU_MODEL
    config["quick_think_llm"] = HAIKU_MODEL
    config["max_debate_rounds"] = 1
    config["max_risk_discuss_rounds"] = 1
    config["max_tokens"] = 2000
    return config


def run_trading_agents(full_ticker: str, analysis_date: str) -> str:
    print(f"\n[AI] Initializing Analysis for {full_ticker}...")
    print(f"[AI] Thinking: Gathering market data and fundamental ratios...")
    config = build_ta_config()
    ta = OptimizedTradingAgentsGraph(
        selected_analysts=["market", "news", "fundamentals"],
        debug=True, # Enable debug for terminal logs
        config=config,
    )
    print(f"[AI] Thinking: Running Agent Graph propagation...")
    _, decision = ta.propagate(full_ticker, analysis_date)
    print(f"[AI] Thinking: Analysis complete. Formatting output...")
    return str(decision)


def reformat_with_claude(
    raw_output: str,
    full_ticker: str,
    exchange: str,
    prior_analyses: list[dict] | None = None,
) -> dict:
    import json
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    # Deterministic serialization for breakpoint 2
    serialized_history = ""
    if prior_analyses:
        # Take last 15, sort keys for stable cache hash
        history_points = []
        for p in prior_analyses[-15:]:
            history_points.append({
                "date": p.get('analysis_date'),
                "signal": p.get('signal'),
                "conf": p.get('confidence_pct'),
                "target_3m": p.get('target_prices', {}).get('short_term_3m')
            })
        serialized_history = json.dumps(history_points, sort_keys=True)

    # EXECUTION PHASE 2: Dual-Breakpoint Cache Strategy
    system_array = [
        {
            "type": "text",
            "text": INDIAN_MARKET_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"} # Breakpoint 1: Static Blueprint
        }
    ]
    
    if serialized_history:
        system_array.append({
            "type": "text",
            "text": f"PREVIOUS HISTORICAL ANALYSES (CONTEXT):\n{serialized_history}",
            "cache_control": {"type": "ephemeral"} # Breakpoint 2: Ticker-specific Archives
        })

    user_message = (
        f"Below is the raw trading analysis for {full_ticker} ({exchange}).\n\n"
        f"<raw_analysis>\n{raw_output}\n</raw_analysis>\n\n"
        f"Today's date: {date.today().strftime('%d-%b-%Y')}"
    )

    import time
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=SONNET_MODEL,
                max_tokens=2000,
                system=system_array,
                messages=[{"role": "user", "content": user_message}],
                temperature=0 # Strict deterministic output
            )
            break
        except Exception as e:
            print(f"[Anthropic] Reformat attempt {attempt+1} failed: {e}")
            if attempt == 2: raise
            time.sleep(1.0 * (2 ** attempt))
    
    # Log token usage
    _log_token_usage("reformat", response.usage)

    raw_json = _extract_json_from_text(response.content[0].text)
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to parse reformatted JSON: {e}")
        # Return a minimal valid structure if parsing fails
        return {
            "signal": "HOLD",
            "confidence_pct": 0,
            "target_prices": {},
            "key_factors": {"indian_market_sentiment": "Parse error occurred."}
        }

    # Validate indian_market_sentiment is populated
    kf = parsed.get("key_factors", {})
    if not kf.get("indian_market_sentiment", "").strip():
        print("[WARN] indian_market_sentiment empty in reformatted output — filling placeholder")
        kf["indian_market_sentiment"] = "Sentiment data not available for this stock."
        parsed["key_factors"] = kf

    return parsed


# ---------------------------------------------------------------------------
# Signal normalization
# ---------------------------------------------------------------------------

_SIGNAL_MAP = {
    "BUY": "BULLISH",
    "STRONG BUY": "BULLISH",
    "STRONG_BUY": "BULLISH",
    "SELL": "BEARISH",
    "STRONG SELL": "BEARISH",
    "STRONG_SELL": "BEARISH",
    "AVOID": "BEARISH",
    "CAUTIOUS": "CAUTIOUSLY BEARISH",
}


def _normalize_signal(result: dict) -> dict:
    """Normalize legacy signal values to iOS-compatible enum strings."""
    if "signal" in result:
        normalized = result["signal"].strip().upper()
        result["signal"] = _SIGNAL_MAP.get(normalized, normalized)
    return result


def analyze(ticker: str, exchange: str, user_id: int | None = None, use_mock: bool = False) -> dict:
    exchange = exchange.upper()
    if exchange not in EXCHANGE_SUFFIX:
        raise ValueError(f"Unsupported exchange: {exchange}. Use NSE or BSE.")
    full_ticker = _resolve_ticker(ticker, exchange)
    analysis_date = date.today().strftime("%Y-%m-%d")

    if use_mock:
        print(f"\n[MOCK MODE] Returning mock AI data for {full_ticker} to save credits.")
        import time
        time.sleep(2) # Simulate slight delay for UI testing
        ns_ticker = _to_ns(ticker)
        curr_p, _ = _yf_price(ns_ticker)
        
        # Fetch REAL news to inject into MOCK report
        real_news = []
        try:
            t = yf.Ticker(ns_ticker)
            if t.news:
                for n in t.news[:5]:
                    real_news.append({
                        "title": n.get("title", ""),
                        "publisher": n.get("publisher", ""),
                        "link": n.get("link", ""),
                        "publish_time": n.get("providerPublishTime", 0)
                    })
        except Exception as e:
            print(f"Mock news fetch failed: {e}")

        return {
            "ticker": ticker.upper(),
            "company_name": full_ticker,
            "exchange": exchange,
            "analysis_date": analysis_date,
            "signal": "HOLD",
            "confidence_pct": 50,
            "current_price_inr": curr_p or 0.0,
            "target_prices": {"short_term_3m": 0, "medium_term_12m": 0, "long_term_36m": 0},
            "upside_downside_pct": {"short_term": 0.0, "medium_term": 0.0, "long_term": 0.0},
            "bull_case": ["[MOCK] Strong domestic demand expected to support volumes.", "[MOCK] Margin expansion possible if raw material costs stabilize."],
            "bear_case": ["[MOCK] High valuation multiples leave little room for error.", "[MOCK] Increased competition may pressure market share."],
            "key_risks": ["[MOCK] Regulatory changes could impact operations.", "[MOCK] Macroeconomic slowdown affecting consumer spending."],
            "key_factors": {
                "management_quality": "[MOCK] Management has a solid track record of execution.",
                "geopolitical_context": "[MOCK] Domestic focus insulates somewhat from global shocks.",
                "promoter_fii_dii_activity": "[MOCK] Institutional holding remains stable.",
                "turnaround_story": "[MOCK] Core business is steady, not a turnaround play.",
                "fundamentals_summary": "[MOCK] Revenue growth is moderating but cash flows are robust.",
                "global_macro_impact": "[MOCK] Sensitive to interest rate cycles.",
                "news_sentiment": "[MOCK] Recent news is mostly neutral."
            },
            "fundamentals_snapshot": {
                "pe_ratio": 20.5, "debt_to_equity": 0.5,
                "promoter_holding_pct": 50.0, "fii_holding_pct": 20.0, "dii_holding_pct": 15.0
            },
            "what_to_watch": ["[MOCK] Watch upcoming quarterly earnings for margin trends.", "[MOCK] Monitor market share data releases."],
            "disclaimer": "[MOCK DATA] This is a mock report generated in Development Mode to save API credits. The live prices and news below are real, but this analysis text is a placeholder.",
            "recent_news": real_news,
            "_cache_type": "MOCK",
        }

    with get_session() as session:
        # 1. Query Cache: Check global history for today
        cached_today = get_analysis_for_date(session, ticker, analysis_date)
        if cached_today:
            print(f"[CACHE HIT] Returning existing analysis for {full_ticker} on {analysis_date}")
            cached_today = _normalize_signal(cached_today)
            cached_today["_cache_type"] = "CACHE HIT"
            if user_id:
                user_has_it = session.query(AnalysisHistory).filter_by(user_id=user_id, ticker=ticker.upper(), analysis_date=analysis_date).first()
                if not user_has_it:
                    cached_today = save_analysis(session, user_id, ticker.upper(), cached_today, raw_output=cached_today.get("raw_output"))
            return cached_today

        # 2. Fetch deep history for AI context
        prior = get_all_ticker_history(session, ticker, user_id)

    # 3. Smart Cache: Check if news warrants a new expensive analysis
    if prior:
        last_analysis = prior[-1]
        last_date_str = last_analysis.get("analysis_date")
        if last_date_str != analysis_date:
            try:
                ns_ticker = _to_ns(ticker)
                t = yf.Ticker(ns_ticker)
                recent_news = t.news[:5] if t.news else []
                if recent_news:
                    print(f"[AI] Thinking: Fast-checking recent news to see if full analysis is needed...")
                    news_text = "\n".join([f"- {n.get('title', '')}" for n in recent_news])
                    
                    api_key = os.getenv("ANTHROPIC_API_KEY")
                    if api_key:
                        client = anthropic.Anthropic(api_key=api_key)
                        prompt = f"Stock: {full_ticker}\nLast analysis date: {last_date_str}\nRecent News Headlines:\n{news_text}\n\nBased ONLY on these headlines, has there been a major fundamental shift, severe shock, or significant trend-changing event for this company since {last_date_str}? Answer strictly with a single word: 'YES' or 'NO'."
                        
                        import time
                        for attempt in range(3):
                            try:
                                resp = client.messages.create(
                                    model=HAIKU_MODEL,
                                    max_tokens=10,
                                    messages=[{"role": "user", "content": prompt}]
                                )
                                break
                            except Exception as e:
                                print(f"[Anthropic] Smart cache attempt {attempt+1} failed: {e}")
                                if attempt == 2: raise
                                time.sleep(1.0 * (2 ** attempt))
                        _log_token_usage("smart_cache", resp.usage)
                        answer = resp.content[0].text.strip().upper()
                        
                        if "NO" in answer:
                            print(f"[SMART CACHE] No major news changes for {full_ticker} since {last_date_str}. Reusing previous report to save credits.")
                            import copy
                            new_analysis = copy.deepcopy(last_analysis)
                            new_analysis["analysis_date"] = analysis_date
                            curr_p, _ = _yf_price(ns_ticker)
                            if curr_p:
                                new_analysis["current_price_inr"] = curr_p

                            new_analysis = _normalize_signal(new_analysis)
                            new_analysis["_cache_type"] = "SMART CACHE"
                            with get_session() as session:
                                new_analysis = save_analysis(session, user_id, ticker.upper(), new_analysis, raw_output=new_analysis.get("raw_output"))
                            return new_analysis
                        else:
                            print(f"[AI] Thinking: News indicates possible changes ({answer}). Proceeding with full deep analysis.")
            except Exception as e:
                print(f"[AI] Smart cache news check failed: {e}. Defaulting to full analysis.")

    print(f"[CACHE MISS] Generating new deep analysis for {full_ticker}...")

    # Fetch pledging info for AI context
    pledging_data = "Unavailable"
    try:
        ns_ticker = _to_ns(ticker)
        inf = _yf_fetch_info(ns_ticker)
        # Search for any key that might be pledging
        p_keys = [k for k in inf.keys() if "pledge" in k.lower()]
        if p_keys:
            pledging_data = f"{inf[p_keys[0]]}%"
        else:
            # Try to get from major_holders if available
            try:
                mh = yf.Ticker(ns_ticker).major_holders
                if "pledged" in str(mh).lower():
                    pledging_data = str(mh)
            except: pass
    except: pass

    raw_output = run_trading_agents(full_ticker, analysis_date)
    raw_output += f"\n\nADDITIONAL DATA (MANDATORY TO INCLUDE IN fundamentals_snapshot):\nPromoter Pledging: {pledging_data}\n"

    result = reformat_with_claude(raw_output, full_ticker, exchange, prior_analyses=prior)
    result = _normalize_signal(result)
    result["_cache_type"] = "FULL AI"

    with get_session() as session:
        result = save_analysis(session, user_id, ticker.upper(), result, raw_output=raw_output)

    return result


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class AnalyzeRequest(BaseModel):
    ticker: str
    exchange: str = "NSE"
    user_id: Optional[int] = None
    use_mock: bool = False


class WatchlistAddRequest(BaseModel):
    user_id: int
    ticker: str
    exchange: str = "NSE"
    company_name: str


class WatchlistRemoveRequest(BaseModel):
    user_id: int
    ticker: str


class PortfolioAddRequest(BaseModel):
    user_id: int
    ticker: str
    exchange: str = "NSE"
    company_name: str
    shares: float
    buy_price: float
    group_name: str = "holdings"


class PortfolioRemoveRequest(BaseModel):
    user_id: int
    ticker: str


class PortfolioUpdateRequest(BaseModel):
    user_id: int
    ticker: str
    shares: float
    buy_price: float


class PortfolioNoteRequest(BaseModel):
    user_id: int
    ticker: str
    note: str


class AlertAddRequest(BaseModel):
    user_id: int
    ticker: str
    target_price: float
    direction: str  # "above" or "below"
    company_name: str = ""


class AlertRemoveRequest(BaseModel):
    user_id: int
    alert_id: int


class BatchAnalyzeRequest(BaseModel):
    tickers: list[str]
    exchange: str = "NSE"
    user_id: int | None = None


class TradeJournalAddRequest(BaseModel):
    user_id: int
    ticker: str
    action: str  # BUY / SELL / HOLD / WATCH
    price_at_time: float
    reason_text: str
    outcome_text: Optional[str] = None
    company_name: Optional[str] = None
    mood: Optional[str] = None


class TradeJournalUpdateRequest(BaseModel):
    outcome_text: str
    mood: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/login")
def login_endpoint(req: LoginRequest):
    with get_session() as session:
        user = get_user_by_credentials(session, req.username, req.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        return {
            "user_id": user.id,
            "username": user.username,
            "display_name": user.display_name,
        }


@app.get("/quick-info")
def quick_info_endpoint(ticker: str, exchange: str = "NSE"):
    try:
        exchange = exchange.upper()
        if exchange not in EXCHANGE_SUFFIX:
            raise HTTPException(status_code=400, detail=f"Unsupported exchange: {exchange}")

        cache_key = f"{ticker.upper()}_{exchange.upper()}"
        _now = _time.time()
        if cache_key in _quick_info_cache:
            expiry, cached_data = _quick_info_cache[cache_key]
            if _now < expiry:
                print(f"[QUICK-INFO CACHE HIT] {cache_key}")
                return cached_data

        full_ticker = _resolve_ticker(ticker, exchange)
        
        import time
        import random
        info = {}
        t = None
        for attempt in range(3):
            try:
                t = yf.Ticker(full_ticker)
                info = t.info
                if info and (info.get("currentPrice") or info.get("regularMarketPrice")):
                    break
            except Exception as e:
                print(f"[YF] Quick info attempt {attempt+1} failed for {full_ticker}: {e}")
                if attempt < 2:
                    time.sleep((1.5 * (2 ** attempt)) + (random.random() * 0.5))
        
        if not info:
            # Fallback if info is empty but ticker might still work for history
            t = yf.Ticker(full_ticker)
            info = t.info or {}

        import math
        # Fetch 1 year so 200-DMA has enough data points (~250 trading days)
        hist = t.history(period="1y")
        sparkline = [round(float(p), 2) for p in hist["Close"].tolist()[-30:] if not math.isnan(float(p))] if not hist.empty else []

        price_history_90d = []  # field name kept for API compat; now contains up to 1Y of data
        if not hist.empty:
            for date, row in hist.iterrows():
                close_val = float(row["Close"])
                if math.isnan(close_val):
                    continue
                price_history_90d.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "close": round(close_val, 2),
                    "volume": int(row["Volume"]) if not math.isnan(float(row["Volume"])) else 0,
                })

        raw_news = t.news if hasattr(t, "news") and t.news else []
        recent_news = []
        for item in raw_news[:8]: # Increase to 8 items
            content = item.get("content", {})
            pub = content.get("pubDate") or item.get("providerPublishTime", 0)
            if isinstance(pub, str):
                try:
                    from datetime import datetime, timezone
                    pub = int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp())
                except Exception:
                    pub = 0
            
            # Extract image URL from thumbnail resolutions
            image_url = None
            thumbnail = content.get("thumbnail", {})
            if thumbnail:
                image_url = thumbnail.get("originalUrl")
                if not image_url and thumbnail.get("resolutions"):
                    # Pick largest resolution
                    res = sorted(thumbnail["resolutions"], key=lambda x: x.get("width", 0), reverse=True)
                    if res:
                        image_url = res[0].get("url")

            recent_news.append({
                "title": content.get("title") or item.get("title", ""),
                "publisher": content.get("provider", {}).get("displayName") or item.get("publisher", ""),
                "link": content.get("canonicalUrl", {}).get("url") or item.get("link", ""),
                "publish_time": int(pub) if pub else 0,
                "summary": content.get("summary") or "",
                "image_url": image_url
            })

        current = info.get("currentPrice") or info.get("regularMarketPrice") or (sparkline[-1] if sparkline else None)
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        day_change_abs = round(current - prev_close, 2) if current and prev_close else None
        day_change_pct = round((day_change_abs / prev_close) * 100, 2) if day_change_abs and prev_close else None
        market_cap = info.get("marketCap")

        # Historical PE average (approximate using 3Y price/earnings data)
        pe_current = info.get("trailingPE") or info.get("forwardPE")
        pe_vs_avg = None
        try:
            hist_3y = t.history(period="3y")  # we already have 90d, fetch 3y for PE
            # yfinance doesn't give historical PE directly — use earnings_history
            earnings = t.earnings_history
            if earnings is not None and not earnings.empty and pe_current:
                # Estimate: average of trailing 12 EPS values vs current PE
                # Approximate: if we have multiple PE data points
                pe_history = t.info.get("fiveYearAvgDividendYield")  # proxy not ideal
                # Better: use historical price / EPS
                fin = t.quarterly_financials
                if fin is not None and not fin.empty and "Basic EPS" in fin.index:
                    eps_ttm = fin.loc["Basic EPS"].dropna().head(4).sum()
                    if eps_ttm and eps_ttm > 0 and pe_current:
                        hist_prices = t.history(period="3y")["Close"].dropna()
                        if not hist_prices.empty:
                            avg_price_3y = float(hist_prices.mean())
                            avg_pe_3y = round(avg_price_3y / float(eps_ttm), 1)
                            pct_diff = round((pe_current - avg_pe_3y) / avg_pe_3y * 100, 1)
                            pe_vs_avg = {"current_pe": round(pe_current, 1), "avg_pe_3y": avg_pe_3y, "pct_vs_avg": pct_diff}
        except Exception:
            pass

        dividends = []
        try:
            div = t.dividends
            if div is not None and not div.empty:
                # Annual dividend aggregation
                div_df = div.resample("Y").sum()
                for dt, amt in div_df.tail(5).items():
                    if not math.isnan(float(amt)) and float(amt) > 0:
                        dividends.append({"year": dt.year, "amount": round(float(amt), 2)})
        except Exception:
            pass

        corporate_actions = []
        try:
            actions = t.actions
            if actions is not None and not actions.empty:
                for dt, row in actions.tail(10).iterrows():
                    splits = float(row.get("Stock Splits", 0))
                    divs = float(row.get("Dividends", 0))
                    if splits > 0:
                        corporate_actions.append({"date": dt.strftime("%d-%b-%Y"), "type": "split", "detail": f"Stock split {splits}:1"})
                    if divs > 0:
                        corporate_actions.append({"date": dt.strftime("%d-%b-%Y"), "type": "dividend", "detail": f"Dividend ₹{round(divs,2)}"})
        except Exception:
            pass


        # ASM/GSM Check
        asm_gsm_status = "CLEAN"
        try:
            lists = _get_asm_gsm_lists()
            t_base = ticker.upper().split(".")[0]
            if t_base in lists.get("GSM", set()): asm_gsm_status = "GSM"
            elif t_base in lists.get("ASM", set()): asm_gsm_status = "ASM"
            elif not lists.get("ASM") and not lists.get("GSM"): asm_gsm_status = "UNKNOWN"
        except:
            asm_gsm_status = "UNKNOWN"

        result = {
            "ticker": ticker.upper().split(".")[0],
            "asm_gsm_status": asm_gsm_status,
            "company_name": info.get("longName") or info.get("shortName") or ticker.upper(),
            "exchange": exchange,
            "current_price": current,
            "day_change_abs": day_change_abs,
            "day_change_pct": day_change_pct,
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
            "market_cap_crores": round(market_cap / 1e7, 0) if market_cap else None,
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "debt_to_equity": round(info.get("debtToEquity") / 100, 2) if info.get("debtToEquity") else None,
            "promoter_holding_pct": round(info.get("heldPercentInsiders", 0) * 100, 1) or None,
            "volume": info.get("volume") or info.get("regularMarketVolume"),
            "avg_volume": info.get("averageVolume"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "description": info.get("longBusinessSummary") or "Company profile not available.",
            "officers": [officer.get("name") for officer in info.get("companyOfficers", [])[:3]] if info.get("companyOfficers") else [],
            "website": info.get("website"),
            "sparkline_30d": sparkline,
            "price_history_90d": price_history_90d,
            "recent_news": recent_news,
            "pe_vs_avg": pe_vs_avg,
            "dividends": dividends,
            "corporate_actions": corporate_actions,
        }
        _quick_info_cache[cache_key] = (_time.time() + _QUICK_INFO_TTL, result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/nifty-history")
def nifty_history_endpoint(days: int = 365):
    try:
        import time
        import random
        hist = None
        for attempt in range(3):
            try:
                t = yf.Ticker("^NSEI")
                hist = t.history(period=f"{days}d")
                if not hist.empty:
                    break
            except Exception as e:
                print(f"[YF] Nifty history attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    time.sleep((1.5 * (2 ** attempt)) + (random.random() * 0.5))
        
        if hist is None or hist.empty:
            return {"prices": []}
            
        result = []
        for date, row in hist.iterrows():
            result.append({
                "date": date.strftime("%Y-%m-%d"),
                "close": round(float(row["Close"]), 2)
            })
        return {"prices": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_quarterly_fin(full_ticker: str):
    """Fetch quarterly financials with retry, falling back to .BO if .NS returns empty."""
    import time
    import random
    
    def _fetch(sym: str):
        _t = None
        _fin = None
        for attempt in range(3):
            try:
                _t = yf.Ticker(sym)
                _fin = _t.quarterly_financials
                if _fin is not None and not _fin.empty:
                    return _t, _fin
            except Exception as e:
                print(f"[YF] Quarterly fin attempt {attempt+1} failed for {sym}: {e}")
                if attempt < 2:
                    time.sleep((1.5 * (2 ** attempt)) + (random.random() * 0.5))
        return _t, _fin

    t, fin = _fetch(full_ticker)
    if (fin is None or fin.empty) and full_ticker.endswith(".NS"):
        alt = full_ticker[:-3] + ".BO"
        print(f"[QF FALLBACK] No data for {full_ticker}, trying {alt}")
        t, fin = _fetch(alt)
    return t, fin


@app.get("/quarterly-financials")
def quarterly_financials_endpoint(ticker: str, exchange: str = "NSE"):
    try:
        exchange = exchange.upper()
        full_ticker = _resolve_ticker(ticker, exchange)
        t, fin = _get_quarterly_fin(full_ticker)
        result = []
        if fin is not None and not fin.empty:
            rev_row = fin.loc["Total Revenue"] if "Total Revenue" in fin.index else None
            profit_row = fin.loc["Net Income"] if "Net Income" in fin.index else None
            for col in list(fin.columns)[:8]:  # last 8 quarters
                label = col.strftime("Q%q %Y") if hasattr(col, 'strftime') else str(col)[:7]
                rev = float(rev_row[col]) / 1e7 if rev_row is not None and col in rev_row.index else 0  # in crores
                profit = float(profit_row[col]) / 1e7 if profit_row is not None and col in profit_row.index else 0
                result.append({"label": label, "revenue": round(rev, 1), "net_profit": round(profit, 1)})
        # Fetch promoter holding history from quarterly balance sheet / info
        promoter_history = []
        try:
            # yfinance doesn't expose quarterly promoter holdings directly
            # Use the last 4 entries from analysis_history in our DB if available
            from database import get_session, AnalysisHistory
            with get_session() as session:
                rows = session.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker.upper()
                ).order_by(AnalysisHistory.created_at.desc()).limit(8).all()
                seen = {}
                for row in rows:
                    if row.full_json:
                        try:
                            data = json.loads(row.full_json)
                            fs = data.get("fundamentals_snapshot", {})
                            promoter = fs.get("promoter_holding_pct")
                            fii = fs.get("fii_holding_pct")
                            dii = fs.get("dii_holding_pct")
                            date_key = row.analysis_date[:7] if row.analysis_date else "?"
                            if date_key not in seen and promoter is not None:
                                seen[date_key] = True
                                promoter_history.append({
                                    "period": row.analysis_date,
                                    "promoter": promoter,
                                    "fii": fii or 0,
                                    "dii": dii or 0,
                                })
                        except Exception:
                            pass
            promoter_history = list(reversed(promoter_history[:4]))
        except Exception:
            pass

        return {"quarters": result, "promoter_history": promoter_history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _run_analysis_worker(queue, ticker, exchange, user_id, use_mock):
    try:
        result = analyze(ticker, exchange, user_id, use_mock)
        queue.put({"status": "ok", "result": result})
    except Exception as e:
        queue.put({"status": "error", "error": str(e)})

@app.post("/analyze")
async def analyze_endpoint(req: AnalyzeRequest, request: Request):
    user_id = req.user_id
    if user_id and user_id in _running_analyses:
        raise HTTPException(status_code=429, detail="Analysis already running for this user. Please wait.")
    if user_id:
        _running_analyses.add(user_id)
    try:
        job_id = str(uuid.uuid4())[:12]
        _dash_start_job(job_id, req.ticker, req.exchange, req.user_id, req.use_mock)

        queue = multiprocessing.Queue()
        p = multiprocessing.Process(
            target=_run_analysis_worker,
            args=(queue, req.ticker, req.exchange, req.user_id, req.use_mock)
        )
        p.start()

        try:
            while p.is_alive():
                if await request.is_disconnected():
                    print(f"\n[AI] 🚨 Client disconnected! FORCE KILLING AI query for {req.ticker} to save credits! 🚨")
                    p.terminate()
                    p.join()
                    _dash_end_job(job_id, killed=True)
                    return {}

                if not queue.empty():
                    res = queue.get()
                    if res["status"] == "ok":
                        _dash_end_job(job_id, result=res["result"])
                        return res["result"]
                    else:
                        _dash_end_job(job_id, error=res["error"])
                        raise HTTPException(status_code=500, detail=res["error"])

                await asyncio.sleep(0.5)

            if not queue.empty():
                res = queue.get()
                if res["status"] == "ok":
                    _dash_end_job(job_id, result=res["result"])
                    return res["result"]
                else:
                    _dash_end_job(job_id, error=res["error"])
                    raise HTTPException(status_code=500, detail=res["error"])

            _dash_end_job(job_id, error="Process unexpectedly exited")
            raise HTTPException(status_code=500, detail="Process unexpectedly exited.")
        finally:
            if p.is_alive():
                p.terminate()
                p.join()
    finally:
        if user_id:
            _running_analyses.discard(user_id)


@app.get("/portfolio/{user_id}")
def portfolio_endpoint(user_id: int):
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")

            holdings = session.query(Portfolio).filter_by(user_id=user_id).all()
            if not holdings:
                return {"user": user.display_name, "holdings": [], "total_invested": 0, "total_current": 0, "total_pnl": 0}

        rows = []
        total_invested = 0.0
        total_current = 0.0

        for h in holdings:
            ns = _to_ns(h.ticker)
            current_price, prev_close = _yf_price(ns)

            invested = h.shares * h.buy_price
            current_value = h.shares * current_price if current_price else 0.0
            pnl = current_value - invested if current_value > 0 else 0.0
            pnl_pct = (pnl / invested * 100) if invested > 0 and current_value > 0 else 0.0
            day_change_pct = 0.0
            if current_price and prev_close and prev_close > 0:
                day_change_pct = round((current_price - prev_close) / prev_close * 100, 2)

            total_invested += invested
            total_current += current_value

            rows.append({
                "ticker": h.ticker,
                "company_name": h.company_name,
                "group": h.group_name,
                "shares": h.shares,
                "buy_price": h.buy_price,
                "purchase_date": getattr(h, "purchase_date", "N/A"),
                "notes": getattr(h, "notes", ""),
                "target_price": getattr(h, "target_price", 0.0),
                "current_price": current_price or 0.0,
                "day_change_pct": day_change_pct,
                "invested_inr": round(invested, 2),
                "current_value_inr": round(current_value, 2),
                "pnl_inr": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
                "notes": h.notes or "",
            })

        total_pnl = total_current - total_invested

        return {
            "user": user.display_name,
            "user_id": user_id,
            "as_of": datetime.now(timezone.utc).strftime("%d-%b-%Y %H:%M UTC"),
            "total_invested_inr": round(total_invested, 2),
            "total_current_inr": round(total_current, 2),
            "total_pnl_inr": round(total_pnl, 2),
            "total_pnl_pct": round((total_pnl / total_invested * 100), 2) if total_invested > 0 else 0,
            "holdings": sorted(rows, key=lambda x: (x["pnl_pct"] or 0), reverse=True),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


_morning_cache: dict = {}  # {user_id: {"data": {...}, "ts": float}}
_MORNING_CACHE_TTL = 7200  # 2 hours

_macro_impact_cache: dict[int, tuple[float, dict]] = {}  # {user_id: (expiry_ts, data)}
_MACRO_IMPACT_TTL = 7200  # 2 hours

def _nse_session():
    """Bootstrap a session with NSE cookies."""
    import requests
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nseindia.com/",
    })
    try:
        s.get("https://www.nseindia.com", timeout=8)
    except: pass
    return s

_asm_gsm_cache = {"data": {}, "ts": 0}
_ASM_GSM_CACHE_TTL = 21600  # 6 hours

def _get_asm_gsm_lists():
    """Fetch and cache ASM/GSM lists from NSE."""
    global _asm_gsm_cache
    now = time.time()
    if _asm_gsm_cache["ts"] > 0 and (now - _asm_gsm_cache["ts"]) < _ASM_GSM_CACHE_TTL:
        return _asm_gsm_cache["data"]

    print("[NSE] Refreshing ASM/GSM lists...")
    data = {"ASM": set(), "GSM": set()}
    try:
        session = _nse_session()
        # ASM Long Term
        resp = session.get("https://www.nseindia.com/api/surveillance-asm-list?index=longTerm", timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym: data["ASM"].add(sym.upper())
        
        # ASM Short Term
        resp = session.get("https://www.nseindia.com/api/surveillance-asm-list?index=shortTerm", timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym: data["ASM"].add(sym.upper())

        # GSM
        resp = session.get("https://www.nseindia.com/api/surveillance-gsm-list", timeout=10)
        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                sym = item.get("symbol")
                if sym: data["GSM"].add(sym.upper())

        _asm_gsm_cache = {"data": data, "ts": now}
        return data
    except Exception as e:
        print(f"[NSE] ASM/GSM fetch failed: {e}")
        return data

@app.get("/morning-summary/{user_id}")
def morning_summary_endpoint(user_id: int):
    import time
    now = time.time()

    # Check cache
    cached = _morning_cache.get(user_id)
    if cached and (now - cached["ts"]) < _MORNING_CACHE_TTL:
        return cached["data"]

    generated_at = datetime.now(timezone.utc).strftime("%H:%M")

    fallback = {
        "summary": "• Market data loaded. AI brief unavailable at this time.",
        "movers": [],
        "mood": "cautious",
        "generated_at": generated_at,
    }

    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()

            # Get last known signal for each ticker from analysis_history
            last_signals: dict[str, str] = {}
            for h in holdings:
                row = (
                    session.query(AnalysisHistory)
                    .filter(AnalysisHistory.user_id == user_id, AnalysisHistory.ticker == h.ticker)
                    .order_by(AnalysisHistory.created_at.desc())
                    .first()
                )
                if row:
                    last_signals[h.ticker] = row.signal

        # Fetch prices and compute movers
        holding_lines = []
        mover_tickers = []
        significant_movers_lines = []

        for h in holdings:
            ns = _to_ns(h.ticker)
            try:
                current_price, prev_close = _yf_price(ns)
            except Exception:
                current_price, prev_close = None, None

            day_pct = None
            if current_price and prev_close and prev_close > 0:
                day_pct = round((current_price - prev_close) / prev_close * 100, 2)

            invested = h.shares * h.buy_price
            current_value = h.shares * current_price if current_price else None
            pnl_inr = (current_value - invested) if current_value else None
            pnl_pct = ((current_value - invested) / invested * 100) if current_value and invested > 0 else None

            price_str = f"₹{current_price:.2f}" if current_price else "N/A"
            day_str = (f"+{day_pct:.1f}%" if day_pct and day_pct >= 0 else f"{day_pct:.1f}%") if day_pct is not None else "N/A"
            pnl_str = ""
            if pnl_inr is not None and pnl_pct is not None:
                pnl_sign = "+" if pnl_inr >= 0 else ""
                pnl_str = f", overall P&L: {pnl_sign}₹{pnl_inr:.0f} ({pnl_sign}{pnl_pct:.1f}%)"

            company = h.company_name or h.ticker
            holding_lines.append(f"{h.ticker} ({company}): {price_str}, day change: {day_str}{pnl_str}")

            if day_pct is not None and abs(day_pct) >= 2.0:
                mover_tickers.append(h.ticker)
                direction = "UP" if day_pct > 0 else "DOWN"
                significant_movers_lines.append(f"{h.ticker}: {day_str} ({direction})")

        # Get signals text
        signal_lines = []
        for h in holdings:
            sig = last_signals.get(h.ticker, "No analysis yet")
            signal_lines.append(f"{h.ticker}: {sig}")

        # Get market indices
        indices_lines = []
        try:
            indices_data = _get_indices_data()
            for idx in indices_data.get("indices", []):
                if idx["name"] in ("Nifty 50", "Sensex"):
                    chg = idx["change_pct"]
                    chg_str = (f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%")
                    indices_lines.append(f"{idx['name']}: {idx['value']:.2f} ({chg_str})")
        except Exception:
            pass

        portfolio_text = "\n".join(holding_lines) if holding_lines else "No holdings found."
        movers_text = "\n".join(significant_movers_lines) if significant_movers_lines else "None today"
        signals_text = "\n".join(signal_lines) if signal_lines else "No analysis available."
        indices_text = "\n".join(indices_lines) if indices_lines else "Data unavailable."

        prompt = f"""You are a friendly Indian stock market advisor. Write a short morning brief (4-6 bullet points) for an investor based on their portfolio data. Write in simple English. Be specific about which stocks to watch and why. Mention any big movers. Flag anything concerning. End with one sentence on overall market mood. Use Indian number format (lakhs/crores). Be warm and helpful.

Portfolio holdings today:
{portfolio_text}

Significant movers (±2%+):
{movers_text}

Last AI signals:
{signals_text}

Market indices:
{indices_text}

Return ONLY a JSON object (no markdown):
{{"summary": "• Point 1\\n• Point 2\\n• Point 3\\n• Point 4", "movers": ["TICKER1", "TICKER2"], "mood": "positive"}}

mood must be exactly: "positive", "cautious", or "negative"
"""

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key or api_key == "placeholder":
            _morning_cache[user_id] = {"data": fallback, "ts": now}
            return fallback

        client = anthropic.Anthropic(api_key=api_key)
        for attempt in range(3):
            try:
                response = client.messages.create(
                    model=HAIKU_MODEL,
                    max_tokens=400,
                    messages=[{"role": "user", "content": prompt}],
                )
                break
            except Exception as e:
                print(f"[Anthropic] Morning summary attempt {attempt+1} failed: {e}")
                if attempt == 2: raise
                time.sleep(1.0 * (2 ** attempt))
        _log_token_usage("morning_summary", response.usage)

        raw = _extract_json_from_text(response.content[0].text)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse morning summary JSON: {e}")
            parsed = fallback

        result = {
            "summary": parsed.get("summary", fallback["summary"]),
            "movers": parsed.get("movers", mover_tickers),
            "mood": parsed.get("mood", "cautious"),
            "generated_at": generated_at,
        }

        # Validate mood value
        if result["mood"] not in ("positive", "cautious", "negative"):
            result["mood"] = "cautious"

        # Build prioritised action list for today
        priority_items = []

        # Priority 1: Triggered alerts
        try:
            with get_session() as session:
                triggered = session.query(PriceTarget).filter(
                    PriceTarget.user_id == user_id,
                    PriceTarget.triggered == True
                ).all()
                for a in triggered:
                    priority_items.append({
                        "priority": 1,
                        "type": "alert_triggered",
                        "ticker": a.ticker,
                        "message": f"Price alert triggered: {a.ticker} {a.direction} ₹{a.target_price:.0f}",
                    })
        except Exception as e:
            print(f"[MORNING] Alert priority check failed: {e}")

        # Priority 2: Signal changes in last 24h for held stocks
        try:
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            with get_session() as session:
                held_tickers = {h.ticker for h in session.query(Portfolio).filter(
                    Portfolio.user_id == user_id,
                    Portfolio.group_name == "holdings"
                ).all()}
                flips = session.query(SignalEvent).filter(
                    SignalEvent.created_at >= cutoff,
                    SignalEvent.ticker.in_(held_tickers)
                ).all()
                for f in flips:
                    priority_items.append({
                        "priority": 2,
                        "type": "signal_change",
                        "ticker": f.ticker,
                        "message": f"{f.ticker}: signal changed {f.from_signal} → {f.to_signal}",
                    })
        except Exception as e:
            print(f"[MORNING] Signal change priority check failed: {e}")

        priority_items.sort(key=lambda x: x["priority"])
        result["priority_items"] = priority_items

        _morning_cache[user_id] = {"data": result, "ts": now}
        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"[morning-summary] Error: {e}")
        _morning_cache[user_id] = {"data": fallback, "ts": now}
        return fallback


@app.get("/users")
def list_users():
    with get_session() as session:
        users = session.query(User).all()
        return [{"id": u.id, "name": u.name} for u in users]


# ---------------------------------------------------------------------------
# Market Indices
# ---------------------------------------------------------------------------

_INDICES_TICKERS = [
    ("^NSEI",      "Nifty 50"),
    ("^BSESN",     "Sensex"),
    ("^NSEBANK",   "Nifty Bank"),
    ("^CNXIT",     "Nifty IT"),
    ("^CNXMIDCAP", "Nifty Midcap 100"),
    ("USDINR=X",   "USD/INR"),
]

_indices_cache: dict = {"data": None, "ts": 0}

_INDICES_CACHE_TTL = 300  # 5 minutes


def _get_indices_data() -> dict:
    """Fetch and cache market indices data. Used by both /market-indices and /morning-summary."""
    now = time.time()
    if _indices_cache["data"] is not None and (now - _indices_cache["ts"]) < _INDICES_CACHE_TTL:
        return _indices_cache["data"]

    result = []
    import math
    for ticker, name in _INDICES_TICKERS:
        try:
            current = None
            prev_close = None
            for attempt in range(3):
                try:
                    t = yf.Ticker(ticker)
                    info = t.fast_info
                    current = getattr(info, "last_price", None)
                    prev_close = getattr(info, "previous_close", None)
                    
                    if current is None or prev_close is None or math.isnan(current):
                        # Fallback 1: Standard info
                        full_info = t.info
                        current = full_info.get("currentPrice") or full_info.get("regularMarketPrice")
                        prev_close = full_info.get("previousClose") or full_info.get("regularMarketPreviousClose")
                    
                    if current is None or math.isnan(current):
                        # Fallback 2: History (Reliable for indices)
                        hist = t.history(period="5d")
                        if not hist.empty and len(hist) >= 2:
                            current = float(hist["Close"].iloc[-1])
                            prev_close = float(hist["Close"].iloc[-2])
                    
                    if current is not None and not math.isnan(current):
                        break
                except Exception as e:
                    print(f"[YF] Indices attempt {attempt+1} failed for {ticker}: {e}")
                    if attempt < 2:
                        time.sleep((1.0 * (2 ** attempt)) + (random.random() * 0.2))
            
            if current is None or math.isnan(current):
                continue
            
            change_abs = round(current - (prev_close or 0), 4)
            change_pct = round((change_abs / prev_close) * 100, 4) if prev_close else 0.0
            result.append({
                "name": name,
                "ticker": ticker,
                "value": round(float(current), 4),
                "change_pct": change_pct,
                "change_abs": change_abs,
            })
        except Exception as e:
            print(f"[indices] Skipping {ticker}: {e}")
            continue

    payload = {
        "indices": result,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _indices_cache["data"] = payload
    _indices_cache["ts"] = now
    return payload


@app.get("/market-indices")
def market_indices_endpoint():
    return _get_indices_data()


# ---------------------------------------------------------------------------
# Watchlist endpoints
# ---------------------------------------------------------------------------

_watchlist_price_cache: dict = {}  # {user_id: {"data": [...], "ts": float}}
_WATCHLIST_CACHE_TTL = 120  # 2 minutes


@app.post("/watchlist/add")
def watchlist_add_endpoint(req: WatchlistAddRequest):
    try:
        ticker = req.ticker.upper()
        with get_session() as session:
            existing = session.query(Portfolio).filter_by(
                user_id=req.user_id, ticker=ticker, group_name="watchlist"
            ).first()
            if existing:
                return {"already_exists": True, "message": "Already in watchlist"}
            new_item = Portfolio(
                user_id=req.user_id,
                ticker=ticker,
                company_name=req.company_name,
                shares=0,
                buy_price=0,
                group_name="watchlist",
            )
            session.add(new_item)
            session.commit()
        # Invalidate cache for this user
        _watchlist_price_cache.pop(req.user_id, None)
        return {"success": True, "ticker": ticker}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/watchlist/remove")
def watchlist_remove_endpoint(req: WatchlistRemoveRequest):
    try:
        ticker = req.ticker.upper()
        with get_session() as session:
            item = session.query(Portfolio).filter_by(
                user_id=req.user_id, ticker=ticker, group_name="watchlist"
            ).first()
            if not item:
                return {"success": False, "message": "Not in watchlist"}
            session.delete(item)
            session.commit()
        # Invalidate cache for this user
        _watchlist_price_cache.pop(req.user_id, None)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/portfolio/add")
def portfolio_add_endpoint(req: PortfolioAddRequest):
    if not req.ticker or not req.ticker.strip():
        raise HTTPException(status_code=400, detail="Ticker cannot be empty.")
    if req.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be greater than 0.")
    if req.buy_price <= 0:
        raise HTTPException(status_code=400, detail="Buy price must be greater than 0.")

    ticker = req.ticker.upper().strip()
    try:
        with get_session() as session:
            existing = session.query(Portfolio).filter_by(
                user_id=req.user_id, ticker=ticker, group_name="holdings"
            ).first()
            if existing:
                raise HTTPException(status_code=409, detail="Holding already exists. Use /portfolio/update to modify.")

            new_holding = Portfolio(
                user_id=req.user_id,
                ticker=ticker,
                company_name=req.company_name,
                shares=req.shares,
                buy_price=req.buy_price,
                group_name="holdings",
            )
            session.add(new_holding)
            session.commit()

        ns = _to_ns(ticker)
        current_price, prev_close = _yf_price(ns)
        invested = req.shares * req.buy_price
        current_value = req.shares * current_price if current_price else 0.0
        pnl = current_value - invested if current_value > 0 else 0.0
        pnl_pct = (pnl / invested * 100) if invested > 0 and current_value > 0 else 0.0
        day_change_pct = 0.0
        if current_price and prev_close and prev_close > 0:
            day_change_pct = round((current_price - prev_close) / prev_close * 100, 2)

        return {
            "success": True,
            "ticker": ticker,
            "company_name": req.company_name,
            "group": "holdings",
            "shares": req.shares,
            "buy_price": req.buy_price,
            "current_price": current_price or 0.0,
            "day_change_pct": day_change_pct,
            "invested_inr": round(invested, 2),
            "current_value_inr": round(current_value, 2),
            "pnl_inr": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/portfolio/remove")
def portfolio_remove_endpoint(req: PortfolioRemoveRequest):
    ticker = req.ticker.upper().strip()
    try:
        with get_session() as session:
            holding = session.query(Portfolio).filter_by(
                user_id=req.user_id, ticker=ticker, group_name="holdings"
            ).first()
            if not holding:
                raise HTTPException(status_code=404, detail="Holding not found.")
            session.delete(holding)
            session.commit()
        return {"success": True, "ticker": ticker}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/portfolio/update")
def portfolio_update_endpoint(req: PortfolioUpdateRequest):
    if req.shares <= 0:
        raise HTTPException(status_code=400, detail="Shares must be greater than 0.")
    if req.buy_price <= 0:
        raise HTTPException(status_code=400, detail="Buy price must be greater than 0.")

    ticker = req.ticker.upper().strip()
    try:
        with get_session() as session:
            holding = session.query(Portfolio).filter_by(
                user_id=req.user_id, ticker=ticker, group_name="holdings"
            ).first()
            if not holding:
                raise HTTPException(status_code=404, detail="Holding not found.")
            holding.shares = req.shares
            holding.buy_price = req.buy_price
            session.commit()
            company_name = holding.company_name

        ns = _to_ns(ticker)
        current_price, prev_close = _yf_price(ns)
        invested = req.shares * req.buy_price
        current_value = req.shares * current_price if current_price else 0.0
        pnl = current_value - invested if current_value > 0 else 0.0
        pnl_pct = (pnl / invested * 100) if invested > 0 and current_value > 0 else 0.0
        day_change_pct = 0.0
        if current_price and prev_close and prev_close > 0:
            day_change_pct = round((current_price - prev_close) / prev_close * 100, 2)

        return {
            "success": True,
            "ticker": ticker,
            "company_name": company_name,
            "group": "holdings",
            "shares": req.shares,
            "buy_price": req.buy_price,
            "current_price": current_price or 0.0,
            "day_change_pct": day_change_pct,
            "invested_inr": round(invested, 2),
            "current_value_inr": round(current_value, 2),
            "pnl_inr": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/portfolio/signal-warnings")
def portfolio_signal_warnings(user_id: int):
    """Return tickers where signal flipped or is BEARISH/CAUTIOUSLY BEARISH for held stocks."""
    warnings = []
    with get_session() as session:
        holdings = session.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.group_name == "holdings"
        ).all()

        for h in holdings:
            rows = (
                session.query(AnalysisHistory)
                .filter(AnalysisHistory.ticker == h.ticker)
                .order_by(AnalysisHistory.created_at.desc())
                .limit(2)
                .all()
            )

            if not rows:
                continue

            latest = rows[0]
            prev = rows[1] if len(rows) > 1 else None

            signal_flipped = prev is not None and prev.signal != latest.signal
            confidence_dropped = (
                prev is not None
                and latest.confidence_pct is not None
                and prev.confidence_pct is not None
                and (prev.confidence_pct - latest.confidence_pct) > 20
            )
            is_bearish = latest.signal in ("BEARISH", "CAUTIOUSLY BEARISH")

            if signal_flipped or confidence_dropped or is_bearish:
                warnings.append({
                    "ticker": h.ticker,
                    "current_signal": latest.signal,
                    "previous_signal": prev.signal if prev else None,
                    "signal_flipped": signal_flipped,
                    "confidence_dropped": confidence_dropped,
                    "is_bearish": is_bearish,
                    "analysis_date": latest.analysis_date,
                })

    return {"warnings": warnings}


@app.put("/portfolio/note")
def portfolio_note_endpoint(req: PortfolioNoteRequest):
    ticker = req.ticker.upper().strip()
    try:
        with get_session() as session:
            holding = session.query(Portfolio).filter_by(
                user_id=req.user_id, ticker=ticker
            ).first()
            if not holding:
                raise HTTPException(status_code=404, detail="Stock not found in portfolio or watchlist")
            holding.notes = req.note.strip()
            session.commit()
        return {"success": True, "ticker": ticker, "note": req.note.strip()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/watchlist/{user_id}")
def watchlist_get_endpoint(user_id: int):
    try:
        now = time.time()
        cached = _watchlist_price_cache.get(user_id)
        if cached and (now - cached["ts"]) < _WATCHLIST_CACHE_TTL:
            return {"watchlist": cached["data"]}

        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            items = session.query(Portfolio).filter_by(
                user_id=user_id, group_name="watchlist"
            ).all()
            # Snapshot the data we need before session closes
            items_data = [(h.ticker, h.company_name) for h in items]

        # Build ASM/GSM lookup once for all tickers
        try:
            asm_gsm_data = _get_asm_gsm_lists()
        except Exception:
            asm_gsm_data = {"ASM": set(), "GSM": set()}

        result = []
        for ticker, company_name in items_data:
            ns = _to_ns(ticker)
            current_price, prev_close = _yf_price(ns)
            day_change_pct = 0.0
            if current_price and prev_close and prev_close > 0:
                day_change_pct = round((current_price - prev_close) / prev_close * 100, 2)

            # Task F: enrich with last_signal, last_signal_date, asm_gsm_status
            last_signal = None
            last_signal_date = None
            try:
                with get_session() as _sess:
                    sig_row = _sess.query(AnalysisHistory).filter(
                        AnalysisHistory.ticker == ticker
                    ).order_by(AnalysisHistory.created_at.desc()).first()
                    if sig_row:
                        last_signal = sig_row.signal
                        last_signal_date = sig_row.analysis_date
            except Exception:
                pass

            asm_gsm_status = "UNKNOWN"
            try:
                t_base = ticker.upper().split(".")[0]
                if t_base in asm_gsm_data.get("GSM", set()):
                    asm_gsm_status = "GSM"
                elif t_base in asm_gsm_data.get("ASM", set()):
                    asm_gsm_status = "ASM"
                elif asm_gsm_data.get("ASM") or asm_gsm_data.get("GSM"):
                    asm_gsm_status = "CLEAN"
            except Exception:
                asm_gsm_status = "UNKNOWN"

            result.append({
                "ticker": ticker,
                "company_name": company_name,
                "exchange": "NSE",
                "current_price": current_price or 0.0,
                "day_change_pct": day_change_pct,
                "last_signal": last_signal,
                "last_signal_date": last_signal_date,
                "asm_gsm_status": asm_gsm_status,
            })

        _watchlist_price_cache[user_id] = {"data": result, "ts": now}
        return {"watchlist": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Price Alerts endpoints
# ---------------------------------------------------------------------------

@app.post("/alerts/add")
def alerts_add_endpoint(req: AlertAddRequest):
    if req.direction not in ("above", "below"):
        raise HTTPException(status_code=400, detail="direction must be 'above' or 'below'")
    if req.target_price <= 0:
        raise HTTPException(status_code=400, detail="target_price must be greater than 0")
    ticker = req.ticker.upper()
    try:
        with get_session() as session:
            new_alert = PriceTarget(
                user_id=req.user_id,
                ticker=ticker,
                target_price=req.target_price,
                direction=req.direction,
                triggered=False,
            )
            session.add(new_alert)
            session.commit()
            session.refresh(new_alert)
            alert_id = new_alert.id
        return {
            "success": True,
            "alert_id": alert_id,
            "ticker": ticker,
            "target_price": req.target_price,
            "direction": req.direction,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/alerts/remove")
def alerts_remove_endpoint(req: AlertRemoveRequest):
    try:
        with get_session() as session:
            alert = session.query(PriceTarget).filter_by(
                id=req.alert_id, user_id=req.user_id
            ).first()
            if not alert:
                raise HTTPException(status_code=404, detail="Alert not found")
            session.delete(alert)
            session.commit()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# NOTE: /alerts/check/{user_id} MUST be defined before /alerts/{user_id}
# to avoid FastAPI routing /alerts/check/1 into the {user_id} route first.
@app.get("/alerts/check/{user_id}")
def alerts_check_endpoint(user_id: int):
    try:
        with get_session() as session:
            pending = (
                session.query(PriceTarget)
                .filter_by(user_id=user_id, triggered=False)
                .all()
            )
            pending_data = [
                {
                    "id": a.id,
                    "ticker": a.ticker,
                    "target_price": a.target_price,
                    "direction": a.direction,
                }
                for a in pending
            ]

        newly_triggered = []
        for row in pending_data:
            ns_ticker = _to_ns(row["ticker"])
            current_price, _ = _yf_price(ns_ticker)
            if current_price is None:
                continue
            triggered = False
            if row["direction"] == "above" and current_price >= row["target_price"]:
                triggered = True
            elif row["direction"] == "below" and current_price <= row["target_price"]:
                triggered = True

            if triggered:
                with get_session() as session:
                    alert = session.query(PriceTarget).filter_by(id=row["id"]).first()
                    if alert:
                        alert.triggered = True
                        session.commit()
                newly_triggered.append({
                    "id": row["id"],
                    "ticker": row["ticker"],
                    "target_price": row["target_price"],
                    "direction": row["direction"],
                    "current_price": current_price,
                })

        return {"newly_triggered": newly_triggered}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alerts/{user_id}")
def alerts_get_endpoint(user_id: int):
    try:
        with get_session() as session:
            alerts = (
                session.query(PriceTarget)
                .filter_by(user_id=user_id)
                .order_by(PriceTarget.created_at.desc())
                .all()
            )
            alerts_data = [
                {
                    "id": a.id,
                    "ticker": a.ticker,
                    "target_price": a.target_price,
                    "direction": a.direction,
                    "triggered": a.triggered,
                    "created_at": a.created_at.strftime("%Y-%m-%d") if a.created_at else "",
                }
                for a in alerts
            ]

        result = []
        for row in alerts_data:
            ns_ticker = _to_ns(row["ticker"])
            current_price, _ = _yf_price(ns_ticker)
            distance_pct = None
            if current_price and row["target_price"]:
                distance_pct = round(abs(current_price - row["target_price"]) / row["target_price"] * 100, 2)
            result.append({
                "id": row["id"],
                "ticker": row["ticker"],
                "company_name": row["ticker"],  # PriceTarget has no company_name column; fallback to ticker
                "target_price": row["target_price"],
                "direction": row["direction"],
                "current_price": current_price,
                "distance_pct": distance_pct,
                "triggered": row["triggered"],
                "created_at": row["created_at"],
            })

        return {"alerts": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Excel Export
# ---------------------------------------------------------------------------

@app.get("/portfolio/export/excel/{user_id}")
def export_portfolio_excel(user_id: int):
    if not OPENPYXL_AVAILABLE:
        raise HTTPException(status_code=501, detail="openpyxl not installed on server")
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()

            last_signals: dict[str, str] = {}
            last_confidence: dict[str, float | None] = {}
            for h in holdings:
                row = session.query(AnalysisHistory)\
                    .filter(AnalysisHistory.ticker == h.ticker)\
                    .order_by(AnalysisHistory.created_at.desc()).first()
                if row:
                    last_signals[h.ticker] = row.signal
                    last_confidence[h.ticker] = row.confidence_pct

            history_rows = session.query(AnalysisHistory)\
                .order_by(AnalysisHistory.created_at.desc()).limit(100).all()
            # Detach data before session closes
            history_data = [(r.analysis_date, r.ticker, r.signal, r.confidence_pct,
                             r.target_short, r.target_medium, r.target_long) for r in history_rows]
            holdings_data = [(h.ticker, h.company_name, h.shares, h.buy_price,
                              h.notes or "") for h in holdings]

        wb = openpyxl.Workbook()

        # ── Sheet 1: Portfolio ──────────────────────────────────────
        ws1 = wb.active
        ws1.title = "Portfolio"

        headers = ["Ticker", "Company", "Shares", "Buy Price (Rs)", "Current Price (Rs)",
                   "Current Value (Rs)", "Invested (Rs)", "P&L (Rs)", "P&L %",
                   "Signal", "Confidence %", "Notes"]

        header_fill = PatternFill(start_color="2C2C2C", end_color="2C2C2C", fill_type="solid")
        header_font = XLFont(color="F5F0E8", bold=True, size=11)

        for col, header in enumerate(headers, 1):
            cell = ws1.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws1.row_dimensions[1].height = 22

        col_widths = [12, 32, 10, 18, 20, 20, 18, 16, 10, 20, 14, 40]
        for i, w in enumerate(col_widths, 1):
            ws1.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

        green_fill = PatternFill(start_color="D6F5E3", end_color="D6F5E3", fill_type="solid")
        red_fill   = PatternFill(start_color="FADBD8", end_color="FADBD8", fill_type="solid")

        for row_num, (ticker, company, shares, buy_price, notes) in enumerate(holdings_data, 2):
            ns = _to_ns(ticker)
            current_price, _ = _yf_price(ns)
            if not current_price:
                current_price = 0.0
            invested       = round(shares * buy_price, 2)
            current_value  = round(shares * current_price, 2)
            pnl            = round(current_value - invested, 2)
            pnl_pct        = round((pnl / invested * 100) if invested > 0 else 0, 2)
            signal         = last_signals.get(ticker, "—")
            confidence     = last_confidence.get(ticker, "—")

            row_data = [ticker, company, shares, buy_price, current_price,
                        current_value, invested, pnl, pnl_pct, signal, confidence, notes]
            for col, value in enumerate(row_data, 1):
                cell = ws1.cell(row=row_num, column=col, value=value)
                cell.alignment = Alignment(
                    horizontal="center" if col in (1, 3, 10, 11) else "right"
                )
                if col in (8, 9):
                    cell.fill = green_fill if pnl >= 0 else red_fill

        # ── Sheet 2: Analysis History ───────────────────────────────
        ws2 = wb.create_sheet("Analysis History")
        hist_headers = ["Date", "Ticker", "Signal", "Confidence %",
                        "Target 3M (Rs)", "Target 12M (Rs)", "Target 3Y (Rs)"]
        for col, h in enumerate(hist_headers, 1):
            cell = ws2.cell(row=1, column=col, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
        for w, col in zip([14, 14, 22, 14, 18, 18, 18], range(1, 8)):
            ws2.column_dimensions[openpyxl.utils.get_column_letter(col)].width = w

        for idx, (adate, aticker, signal, conf, t3m, t12m, t36m) in enumerate(history_data, 2):
            ws2.cell(row=idx, column=1, value=adate)
            ws2.cell(row=idx, column=2, value=aticker)
            ws2.cell(row=idx, column=3, value=signal)
            ws2.cell(row=idx, column=4, value=conf)
            ws2.cell(row=idx, column=5, value=t3m)
            ws2.cell(row=idx, column=6, value=t12m)
            ws2.cell(row=idx, column=7, value=t36m)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        today = date.today().strftime("%Y%m%d")
        filename = f"nivesh_portfolio_{today}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/macro-strip")
def macro_strip_endpoint():
    """Returns USD/INR rate, crude oil price, and RBI repo rate for context strip."""
    try:
        import math
        result = {}

        # USD/INR
        try:
            t = yf.Ticker("USDINR=X")
            info = t.info
            usd_inr = info.get("regularMarketPrice") or info.get("currentPrice")
            if usd_inr and not math.isnan(float(usd_inr)):
                result["usd_inr"] = round(float(usd_inr), 2)
            else:
                result["usd_inr"] = None
        except Exception:
            result["usd_inr"] = None

        # Crude oil (WTI)
        try:
            t = yf.Ticker("CL=F")
            info = t.info
            crude = info.get("regularMarketPrice") or info.get("currentPrice")
            if crude and not math.isnan(float(crude)):
                result["crude_oil_usd"] = round(float(crude), 2)
            else:
                result["crude_oil_usd"] = None
        except Exception:
            result["crude_oil_usd"] = None

        # Brent crude (India imports Brent-priced oil, more relevant than WTI)
        try:
            t = yf.Ticker("BZ=F")
            info = t.info
            brent = info.get("regularMarketPrice") or info.get("currentPrice")
            if brent and not math.isnan(float(brent)):
                result["brent_oil_usd"] = round(float(brent), 2)
            else:
                result["brent_oil_usd"] = None
        except Exception:
            result["brent_oil_usd"] = None

        # India VIX — fear gauge for Indian retail markets
        try:
            t = yf.Ticker("^INDIAVIX")
            info = t.info
            vix = info.get("regularMarketPrice") or info.get("currentPrice")
            if vix and not math.isnan(float(vix)):
                result["india_vix"] = round(float(vix), 2)
            else:
                result["india_vix"] = None
        except Exception:
            result["india_vix"] = None

        # RBI repo rate — hardcoded (changes rarely, update manually)
        result["rbi_repo_rate_pct"] = 6.50
        result["rbi_stance"] = "Neutral"

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/earnings-calendar")
def earnings_calendar_endpoint():
    """Returns upcoming earnings dates for NSE portfolio stocks."""
    try:
        from database import get_session, Portfolio
        with get_session() as session:
            tickers = session.query(Portfolio.ticker).filter(
                Portfolio.group_name == "holdings"
            ).distinct().all()
            tickers = [t[0] for t in tickers]

        results = []
        today = datetime.now().date()

        for ticker_raw in tickers:
            try:
                full_ticker = _resolve_ticker(ticker_raw, "NSE")
                t = yf.Ticker(full_ticker)
                cal = t.calendar
                
                earnings_dates = []
                if isinstance(cal, dict) and 'Earnings Date' in cal:
                    dates_val = cal['Earnings Date']
                    if isinstance(dates_val, list):
                        earnings_dates = dates_val
                elif hasattr(cal, 'empty') and not cal.empty and 'Earnings Date' in cal.columns:
                    # fallback for older yfinance versions that return DataFrame
                    earnings_dates = cal['Earnings Date'].dropna().tolist()

                for d in earnings_dates:
                    try:
                        ed = d.date() if hasattr(d, 'date') else d
                        days_away = (ed - today).days
                        if -7 <= days_away <= 45:
                            results.append({
                                "ticker": ticker_raw.upper(),
                                "earnings_date": ed.strftime("%d-%b-%Y"),
                                "days_away": days_away,
                            })
                    except Exception:
                        pass
            except Exception:
                pass

        results.sort(key=lambda x: x["days_away"])
        return {"events": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/batch")
async def batch_analyze_endpoint(req: BatchAnalyzeRequest):
    """Submit multiple tickers as an Anthropic Message Batches job (nightly use only)."""
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

        exchange = req.exchange.upper()
        analysis_date = date.today().strftime("%Y-%m-%d")
        requests_list = []

        for ticker in req.tickers:
            full_ticker = _resolve_ticker(ticker, exchange)
            # Run agents synchronously for each ticker to get raw output
            # For batch we just create the Anthropic requests
            user_message = f"Analyze {full_ticker} on {exchange} for {analysis_date}. Return analysis JSON per system prompt."
            requests_list.append({
                "custom_id": ticker.upper(),
                "params": {
                    "model": SONNET_MODEL,
                    "max_tokens": 2000,
                    "system": [{"type": "text", "text": INDIAN_MARKET_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                    "messages": [{"role": "user", "content": user_message}],
                }
            })

        client = anthropic.Anthropic(api_key=api_key)
        
        import time
        for attempt in range(3):
            try:
                batch = client.messages.batches.create(requests=requests_list)
                break
            except Exception as e:
                print(f"[Anthropic] Batch create attempt {attempt+1} failed: {e}")
                if attempt == 2: raise
                time.sleep(1.0 * (2 ** attempt))

        return {
            "batch_id": batch.id,
            "status": batch.processing_status,
            "request_counts": batch.request_counts.model_dump() if hasattr(batch.request_counts, 'model_dump') else {},
            "tickers": req.tickers,
            "note": "Poll GET /analyze/batch/{batch_id} for results"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analyze/batch/{batch_id}")
async def batch_analyze_status(batch_id: str):
    """Poll batch job status and store results when complete."""
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key)
        
        import time
        for attempt in range(3):
            try:
                batch = client.messages.batches.retrieve(batch_id)
                break
            except Exception as e:
                print(f"[Anthropic] Batch retrieve attempt {attempt+1} failed: {e}")
                if attempt == 2: raise
                time.sleep(1.0 * (2 ** attempt))

        if batch.processing_status == "ended":
            results = []
            for result in client.messages.batches.results(batch_id):
                if result.result.type == "succeeded":
                    try:
                        raw_json = result.result.message.content[0].text.strip()
                        analysis = json.loads(raw_json)
                        analysis = _normalize_signal(analysis)
                        with get_session() as session:
                            save_analysis(session, None, result.custom_id, analysis)
                        results.append({"ticker": result.custom_id, "status": "saved"})
                    except Exception as e:
                        results.append({"ticker": result.custom_id, "status": "error", "detail": str(e)})
            return {"status": "complete", "results": results}

        return {"status": batch.processing_status, "batch_id": batch_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analyst-ratings")
def analyst_ratings_endpoint(ticker: str, exchange: str = "NSE"):
    try:
        full_ticker = _resolve_ticker(ticker, exchange)
        
        import time
        import random
        recs = None
        for attempt in range(3):
            try:
                t = yf.Ticker(full_ticker)
                recs = t.recommendations
                if recs is not None and not recs.empty:
                    break
            except Exception as e:
                print(f"[YF] Ratings attempt {attempt+1} failed for {full_ticker}: {e}")
                if attempt < 2:
                    time.sleep((1.5 * (2 ** attempt)) + (random.random() * 0.5))

        if recs is None or recs.empty:
            return {"ratings": [], "consensus": None}

        import math
        recent = recs.tail(10)
        ratings = []
        for _, row in recent.iterrows():
            firm = row.get("Firm", row.get("firm", "Unknown"))
            grade = row.get("To Grade", row.get("toGrade", row.get("Action", "")))
            period = row.name.strftime("%b %Y") if hasattr(row.name, 'strftime') else str(row.name)[:7]
            if firm and grade:
                ratings.append({"firm": str(firm), "grade": str(grade), "period": period})

        # Consensus
        buys = sum(1 for r in ratings if any(w in r["grade"].upper() for w in ["BUY", "OUTPERFORM", "OVERWEIGHT", "ACCUMULATE"]))
        sells = sum(1 for r in ratings if any(w in r["grade"].upper() for w in ["SELL", "UNDERPERFORM", "UNDERWEIGHT", "REDUCE"]))
        holds = len(ratings) - buys - sells
        if buys > sells and buys > holds: consensus = "BUY"
        elif sells > buys and sells > holds: consensus = "SELL"
        elif len(ratings) > 0: consensus = "HOLD"
        else: consensus = None

        return {"ratings": ratings[-6:], "consensus": consensus, "buy": buys, "hold": holds, "sell": sells}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ipo-calendar")
def ipo_calendar_endpoint():
    """Returns upcoming IPO data (best-effort from public sources)."""
    return {
        "ipos": UPCOMING_IPOS,
        "note": "IPO data from manual tracking.",
        "source": "Manual Tracking"
    }


@app.get("/sector-weekly")
def sector_weekly_endpoint():
    """Returns sector performance with 1-week and 1-day change."""
    SECTOR_ETFS = {
        "Nifty Bank": "^NSEBANK",
        "Nifty IT": "^CNXIT",
        "Nifty Pharma": "^CNXPHARMA",
        "Nifty Auto": "^CNXAUTO",
        "Nifty FMCG": "^CNXFMCG",
        "Nifty Metal": "^CNXMETAL",
        "Nifty Energy": "^CNXENERGY",
        "Nifty Realty": "^CNXREALTY",
        "Nifty Infra": "^CNXINFRA",
        "Nifty Media": "^CNXMEDIA",
        "Nifty PSU Bank": "^CNXPSUBANK",
        "Nifty MidCap": "^NSEMDCP50",
    }
    import math
    import time
    import random
    results = []
    for name, sym in SECTOR_ETFS.items():
        try:
            hist = None
            for attempt in range(3):
                try:
                    t = yf.Ticker(sym)
                    hist = t.history(period="8d")
                    if not hist.empty and len(hist) >= 2:
                        break
                except Exception as e:
                    print(f"[YF] Sector attempt {attempt+1} failed for {sym}: {e}")
                    if attempt < 2:
                        time.sleep((1.0 * (2 ** attempt)) + (random.random() * 0.2))

            if hist is None or hist.empty or len(hist) < 2:
                continue
            closes = hist["Close"].dropna()
            if len(closes) < 2:
                continue
            current = float(closes.iloc[-1])
            prev_day = float(closes.iloc[-2])
            week_ago = float(closes.iloc[0]) if len(closes) >= 5 else prev_day
            if math.isnan(current) or math.isnan(prev_day):
                continue
            day_chg = round((current - prev_day) / prev_day * 100, 2)
            week_chg = round((current - week_ago) / week_ago * 100, 2)
            results.append({"name": name, "ticker": sym, "value": round(current, 2), "change_pct": day_chg, "change_abs": round(current - prev_day, 2), "week_change_pct": week_chg})
        except Exception:
            continue
    return {"sectors": results}


# ---------------------------------------------------------------------------
# Stock Directory Search
# ---------------------------------------------------------------------------

@app.get("/search")
def search_endpoint(q: str = "", limit: int = 20):
    """Fast in-memory NSE stock search. No yfinance, no DB. Returns in <5ms."""
    q = q.strip()
    if not q:
        return []
    ql = q.lower()
    prefix: list[dict] = []
    contains: list[dict] = []
    for e in _NSE_DIR_INDEX:
        if e["_t"].startswith(ql) or e["_n"].startswith(ql):
            prefix.append(e)
        elif ql in e["_t"] or ql in e["_n"] or ql in e["_s"]:
            contains.append(e)
    results = prefix + contains
    return [
        {"ticker": r["ticker"], "company_name": r["company_name"],
         "sector": r["sector"], "exchange": r["exchange"]}
        for r in results[:limit]
    ]


# ---------------------------------------------------------------------------
# Portfolio Risk Analysis
# ---------------------------------------------------------------------------

def _risk_label(score: int | None) -> str:
    if score is None: return "Unknown"
    if score <= 3: return "Low"
    if score <= 6: return "Moderate"
    if score <= 8: return "High"
    return "Very High"


@app.get("/portfolio/risk-analysis/{user_id}")
def portfolio_risk_analysis_endpoint(user_id: int):
    try:
        import math
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()
            holdings_data = [(h.ticker, h.company_name, h.shares, h.buy_price) for h in holdings]

        if not holdings_data:
            return {"user_id": user_id, "holdings_count": 0, "total_portfolio_value": 0,
                    "sector_concentration": [], "portfolio_beta": None, "risk_score": None,
                    "risk_score_label": "Unknown", "concentration_risks": [], "stock_details": []}

        stock_details = []
        total_value = 0.0
        # For correlation: keep (ticker, list_of_daily_returns) indexed by date
        _return_series: dict[str, dict] = {}  # ticker -> {date_str: return_float}

        for ticker, company_name, shares, buy_price in holdings_data:
            ns = _to_ns(ticker)
            info = _yf_fetch_info(ns)
            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or buy_price
            beta = info.get("beta")
            sector = info.get("sector") or "Unknown"
            current_value = shares * current_price
            total_value += current_value

            hist_volatility = None
            try:
                t = yf.Ticker(ns)
                hist = t.history(period="90d")
                if not hist.empty and len(hist) > 1:
                    returns = hist["Close"].pct_change().dropna()
                    v = float(returns.std() * (252 ** 0.5) * 100)
                    hist_volatility = round(v, 2) if not math.isnan(v) else None
                    # Store daily returns for correlation
                    daily = {}
                    for idx, val in returns.items():
                        try:
                            dstr = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                            if not math.isnan(float(val)):
                                daily[dstr] = float(val)
                        except Exception:
                            pass
                    if daily:
                        _return_series[ticker] = daily
            except Exception:
                pass

            stock_details.append({
                "ticker": ticker,
                "company_name": company_name,
                "shares": shares,
                "current_price": current_price,
                "current_value": round(current_value, 2),
                "beta": round(beta, 3) if beta is not None and not math.isnan(beta) else None,
                "sector": sector,
                "hist_volatility_annualized_pct": hist_volatility,
            })

        # Sector concentration
        sector_map: dict[str, float] = {}
        for s in stock_details:
            sector_map[s["sector"]] = sector_map.get(s["sector"], 0) + s["current_value"]
        sector_concentration = sorted([
            {"sector": sec, "value": round(val, 2),
             "pct": round(val / total_value * 100, 1) if total_value > 0 else 0}
            for sec, val in sector_map.items()
        ], key=lambda x: x["pct"], reverse=True)

        # Beta-weighted portfolio beta
        stocks_with_beta = [s for s in stock_details if s["beta"] is not None]
        portfolio_beta = None
        if stocks_with_beta and total_value > 0:
            covered_value = sum(s["current_value"] for s in stocks_with_beta)
            portfolio_beta = round(
                sum(s["current_value"] / covered_value * s["beta"] for s in stocks_with_beta), 3
            )

        risk_score = min(10, max(1, round(portfolio_beta * 5))) if portfolio_beta is not None else None

        # Concentration risks: stocks > 20% of portfolio
        concentration_risks = sorted([
            {"ticker": s["ticker"], "company_name": s["company_name"],
             "pct_of_portfolio": round(s["current_value"] / total_value * 100, 1),
             "current_value": s["current_value"]}
            for s in stock_details
            if total_value > 0 and (s["current_value"] / total_value) > 0.20
        ], key=lambda x: x["pct_of_portfolio"], reverse=True)[:3]

        for s in stock_details:
            s["portfolio_weight_pct"] = round(s["current_value"] / total_value * 100, 1) if total_value > 0 else 0

        # ------------------------------------------------------------------
        # Pearson correlation: find highest correlated pair (manual, no sklearn)
        # ------------------------------------------------------------------
        highest_corr_pair = None
        try:
            ticker_list = list(_return_series.keys())
            if len(ticker_list) >= 2:
                max_corr = -999.0
                best_pair = None
                for i in range(len(ticker_list)):
                    for j in range(i + 1, len(ticker_list)):
                        ta = ticker_list[i]
                        tb = ticker_list[j]
                        ra_map = _return_series[ta]
                        rb_map = _return_series[tb]
                        # Align by common dates
                        common = [d for d in ra_map if d in rb_map]
                        n = len(common)
                        if n < 10:
                            continue
                        ra = [ra_map[d] for d in common]
                        rb = [rb_map[d] for d in common]
                        mean_a = sum(ra) / n
                        mean_b = sum(rb) / n
                        cov = sum((ra[k] - mean_a) * (rb[k] - mean_b) for k in range(n))
                        var_a = sum((ra[k] - mean_a) ** 2 for k in range(n))
                        var_b = sum((rb[k] - mean_b) ** 2 for k in range(n))
                        denom = (var_a * var_b) ** 0.5
                        if denom == 0:
                            continue
                        corr = cov / denom
                        if not math.isnan(corr) and corr > max_corr:
                            max_corr = corr
                            best_pair = (ta, tb)
                if best_pair:
                    highest_corr_pair = {
                        "ticker_a": best_pair[0],
                        "ticker_b": best_pair[1],
                        "correlation": round(max_corr, 4),
                    }
        except Exception as _corr_err:
            print(f"[RISK] Correlation calc failed: {_corr_err}")

        return {
            "user_id": user_id,
            "total_portfolio_value": round(total_value, 2),
            "holdings_count": len(stock_details),
            "portfolio_beta": portfolio_beta,
            "risk_score": risk_score,
            "risk_score_label": _risk_label(risk_score),
            "sector_concentration": sector_concentration,
            "concentration_risks": concentration_risks,
            "highest_correlation_pair": highest_corr_pair,
            "stock_details": sorted(stock_details, key=lambda x: x["current_value"], reverse=True),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Portfolio Red Flags
# ---------------------------------------------------------------------------

@app.get("/portfolio/red-flags/{user_id}")
def portfolio_red_flags_endpoint(user_id: int):
    try:
        from datetime import timedelta
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()
            held_tickers = [h.ticker for h in holdings]

            if not held_tickers:
                return {"user_id": user_id, "total_flags": 0, "critical": 0,
                        "warnings": 0, "watches": 0, "flags": [],
                        "summary": "No holdings found."}

            latest_analyses: dict[str, dict] = {}
            for ticker in held_tickers:
                row = session.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker
                ).order_by(AnalysisHistory.created_at.desc()).first()
                if row and row.full_json:
                    try:
                        data = json.loads(row.full_json)
                        data["_pledged_pct_db"] = row.promoter_pledged_pct
                        latest_analyses[ticker] = data
                    except Exception:
                        pass

            # FII trend: last 4 analyses per ticker (most recent first)
            fii_histories: dict[str, list[float]] = {}
            for ticker in held_tickers:
                rows = session.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker
                ).order_by(AnalysisHistory.created_at.desc()).limit(4).all()
                fiis = []
                for r in rows:
                    try:
                        d = json.loads(r.full_json)
                        fii = d.get("fundamentals_snapshot", {}).get("fii_holding_pct")
                        if fii is not None:
                            fiis.append(float(fii))
                    except Exception:
                        pass
                fii_histories[ticker] = fiis

            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            bearish_flips = session.query(SignalEvent).filter(
                SignalEvent.created_at >= cutoff,
                SignalEvent.ticker.in_(held_tickers),
                SignalEvent.to_signal.in_(["BEARISH", "CAUTIOUSLY BEARISH"])
            ).all()
            bearish_flip_map = {f.ticker: (f.from_signal, f.to_signal) for f in bearish_flips}

        try:
            asm_gsm = _get_asm_gsm_lists()
        except Exception:
            asm_gsm = {"ASM": set(), "GSM": set()}

        flags = []
        for ticker in held_tickers:
            analysis = latest_analyses.get(ticker, {})
            fs = analysis.get("fundamentals_snapshot", {})

            pledged = fs.get("promoter_pledged_pct") or analysis.get("_pledged_pct_db")
            if pledged is not None and pledged > 30:
                flags.append({
                    "ticker": ticker,
                    "severity": "CRITICAL",
                    "flag_type": "HIGH_PROMOTER_PLEDGING",
                    "detail": f"Promoter pledging at {pledged:.1f}% (threshold: 30%)",
                })

            t_base = ticker.upper().split(".")[0]
            if t_base in asm_gsm.get("GSM", set()):
                flags.append({
                    "ticker": ticker, "severity": "CRITICAL",
                    "flag_type": "GSM_LISTED",
                    "detail": "Stock on NSE Graded Surveillance Measure (GSM) list",
                })
            elif t_base in asm_gsm.get("ASM", set()):
                flags.append({
                    "ticker": ticker, "severity": "WARNING",
                    "flag_type": "ASM_LISTED",
                    "detail": "Stock on NSE Additional Surveillance Measure (ASM) list",
                })

            if ticker in bearish_flip_map:
                from_sig, to_sig = bearish_flip_map[ticker]
                flags.append({
                    "ticker": ticker, "severity": "WARNING",
                    "flag_type": "BEARISH_SIGNAL_FLIP",
                    "detail": f"Signal flipped {from_sig} → {to_sig} in last 30 days",
                })

            fiis = fii_histories.get(ticker, [])
            if len(fiis) >= 3:
                consecutive_declines = 0
                for i in range(len(fiis) - 1):
                    if fiis[i] < fiis[i + 1]:
                        consecutive_declines += 1
                    else:
                        break
                if consecutive_declines >= 2:
                    fii_str = " → ".join(f"{v:.1f}%" for v in reversed(fiis[:consecutive_declines + 1]))
                    flags.append({
                        "ticker": ticker, "severity": "WATCH",
                        "flag_type": "FII_DECLINING",
                        "detail": f"FII holding declining: {fii_str}",
                    })

        severity_order = {"CRITICAL": 0, "WARNING": 1, "WATCH": 2}
        flags.sort(key=lambda x: severity_order.get(x["severity"], 3))

        summary = "No significant red flags detected across the portfolio."
        if flags:
            try:
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if api_key and api_key != "placeholder":
                    client = anthropic.Anthropic(api_key=api_key)
                    flags_text = "\n".join(
                        f"- [{f['severity']}] {f['ticker']}: {f['detail']}" for f in flags
                    )
                    prompt = (
                        f"Portfolio red flags:\n{flags_text}\n\n"
                        "Write exactly 3 sentences summarizing the biggest risks. "
                        "Be specific about tickers and risk types. Plain English."
                    )
                    import time as _tt
                    for attempt in range(3):
                        try:
                            resp = client.messages.create(
                                model=HAIKU_MODEL, max_tokens=200,
                                messages=[{"role": "user", "content": prompt}]
                            )
                            break
                        except Exception as e:
                            print(f"[RED-FLAGS] Haiku attempt {attempt+1} failed: {e}")
                            if attempt == 2: raise
                            _tt.sleep(1.0 * (2 ** attempt))
                    _log_token_usage("red_flags_summary", resp.usage)
                    summary = resp.content[0].text.strip()
            except Exception as e:
                print(f"[RED-FLAGS] Summary call failed: {e}")

        return {
            "user_id": user_id,
            "total_flags": len(flags),
            "critical": sum(1 for f in flags if f["severity"] == "CRITICAL"),
            "warnings": sum(1 for f in flags if f["severity"] == "WARNING"),
            "watches": sum(1 for f in flags if f["severity"] == "WATCH"),
            "flags": flags,
            "summary": summary,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Macro Impact
# ---------------------------------------------------------------------------

@app.get("/macro-impact/{user_id}")
def macro_impact_endpoint(user_id: int):
    try:
        import math
        now = _time.time()
        cached = _macro_impact_cache.get(user_id)
        if cached and now < cached[0]:
            return cached[1]

        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()
            holdings_data = [(h.ticker, h.company_name) for h in holdings]

        if not holdings_data:
            return {"user_id": user_id, "macro_readings": {}, "impacts": [], "generated_at": datetime.now(timezone.utc).isoformat()}

        macro: dict = {}
        for sym, key in [("BZ=F", "brent_oil_usd"), ("^INDIAVIX", "india_vix"), ("USDINR=X", "usd_inr")]:
            try:
                info = yf.Ticker(sym).info
                val = info.get("regularMarketPrice") or info.get("currentPrice")
                macro[key] = round(float(val), 2) if val and not math.isnan(float(val)) else None
            except Exception:
                macro[key] = None
        macro["rbi_repo_rate_pct"] = 6.50

        holdings_list = "\n".join(f"- {t}: {c}" for t, c in holdings_data)
        macro_str = (
            f"Brent crude: ${macro.get('brent_oil_usd', 'N/A')}/bbl, "
            f"India VIX: {macro.get('india_vix', 'N/A')}, "
            f"USD/INR: {macro.get('usd_inr', 'N/A')}, "
            f"RBI repo rate: {macro.get('rbi_repo_rate_pct')}%"
        )
        prompt = (
            f"Current Indian macro environment: {macro_str}\n\n"
            f"Holdings:\n{holdings_list}\n\n"
            "For each ticker write one sentence on macro impact and classify direction. "
            "Return ONLY valid JSON array, no markdown:\n"
            '[{"ticker": "TICKER", "impact_statement": "...", "direction": "positive|negative|neutral"}]'
        )

        impacts = []
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key and api_key != "placeholder":
            try:
                client = anthropic.Anthropic(api_key=api_key)
                import time as _tt
                for attempt in range(3):
                    try:
                        resp = client.messages.create(
                            model=HAIKU_MODEL, max_tokens=1500,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0,
                        )
                        break
                    except Exception as e:
                        print(f"[MACRO-IMPACT] Attempt {attempt+1} failed: {e}")
                        if attempt == 2: raise
                        _tt.sleep(1.0 * (2 ** attempt))
                _log_token_usage("macro_impact", resp.usage)
                raw = _extract_json_from_text(resp.content[0].text)
                parsed = json.loads(raw)
                for item in parsed:
                    if item.get("direction") not in ("positive", "negative", "neutral"):
                        item["direction"] = "neutral"
                impacts = parsed
            except Exception as e:
                print(f"[MACRO-IMPACT] AI call failed: {e}")
                impacts = [{"ticker": t, "impact_statement": "Macro assessment unavailable.", "direction": "neutral"} for t, _ in holdings_data]
        else:
            impacts = [{"ticker": t, "impact_statement": "API key not configured.", "direction": "neutral"} for t, _ in holdings_data]

        result = {
            "user_id": user_id,
            "macro_readings": macro,
            "impacts": impacts,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _macro_impact_cache[user_id] = (now + _MACRO_IMPACT_TTL, result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Portfolio Timeframe Conflicts
# ---------------------------------------------------------------------------

@app.get("/portfolio/timeframe-conflicts/{user_id}")
def portfolio_timeframe_conflicts_endpoint(user_id: int):
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()
            held_tickers = [h.ticker for h in holdings]

            conflicts = []
            for ticker in held_tickers:
                row = session.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker
                ).order_by(AnalysisHistory.created_at.desc()).first()
                if not row or not row.full_json:
                    continue
                try:
                    data = json.loads(row.full_json)
                except Exception:
                    continue

                current_price = data.get("current_price_inr")
                tp = data.get("target_prices") or {}
                short_target = tp.get("short_term_3m")
                long_target = tp.get("long_term_36m")

                if not all([current_price, short_target, long_target]) or current_price <= 0:
                    continue

                short_dir = "up" if short_target > current_price else "down"
                long_dir = "up" if long_target > current_price else "down"

                if short_dir == long_dir:
                    continue

                short_upside = round((short_target - current_price) / current_price * 100, 1)
                long_upside = round((long_target - current_price) / current_price * 100, 1)

                if short_dir == "down" and long_dir == "up":
                    explanation = (
                        f"{ticker} shows near-term caution ({short_upside:+.1f}% to ₹{short_target:.0f} in 3M) "
                        f"but long-term recovery expected ({long_upside:+.1f}% to ₹{long_target:.0f} in 3Y). "
                        "Consider holding through short-term weakness if long-term thesis is intact."
                    )
                else:
                    explanation = (
                        f"{ticker} has near-term upside ({short_upside:+.1f}% to ₹{short_target:.0f} in 3M) "
                        f"but faces long-term headwinds ({long_upside:+.1f}% to ₹{long_target:.0f} in 3Y). "
                        "Consider taking near-term gains; long-term outlook is uncertain."
                    )

                conflicts.append({
                    "ticker": ticker,
                    "company_name": data.get("company_name", ticker),
                    "current_price": current_price,
                    "short_term_target": short_target,
                    "long_term_target": long_target,
                    "short_term_direction": short_dir,
                    "long_term_direction": long_dir,
                    "short_upside_pct": short_upside,
                    "long_upside_pct": long_upside,
                    "explanation": explanation,
                    "analysis_date": row.analysis_date,
                    "signal": data.get("signal"),
                })

        return {"user_id": user_id, "conflict_count": len(conflicts), "conflicts": conflicts}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Trade Journal
# ---------------------------------------------------------------------------

@app.post("/trade-journal")
def trade_journal_add_endpoint(req: TradeJournalAddRequest):
    action = req.action.upper()
    if action not in ("BUY", "SELL", "HOLD", "WATCH"):
        raise HTTPException(status_code=400, detail="action must be BUY, SELL, HOLD, or WATCH")
    if req.price_at_time <= 0:
        raise HTTPException(status_code=400, detail="price_at_time must be > 0")
    ticker = req.ticker.upper().strip()
    try:
        with get_session() as session:
            entry = TradeJournal(
                user_id=req.user_id,
                ticker=ticker,
                action=action,
                price_at_time=req.price_at_time,
                reason_text=req.reason_text.strip(),
                outcome_text=req.outcome_text.strip() if req.outcome_text else None,
            )
            # Set optional new columns gracefully (only if col exists in DB after migration)
            try:
                entry.company_name = req.company_name
            except Exception:
                pass
            try:
                entry.mood = req.mood
            except Exception:
                pass
            session.add(entry)
            session.commit()
            session.refresh(entry)
            entry_id = entry.id
        return {"success": True, "entry_id": entry_id, "ticker": ticker, "action": action}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trade-journal/{user_id}")
def trade_journal_get_endpoint(user_id: int):
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            entries = session.query(TradeJournal).filter_by(
                user_id=user_id
            ).order_by(TradeJournal.created_at.desc()).all()
            result = []
            for e in entries:
                row = {
                    "id": e.id,
                    "ticker": e.ticker,
                    "action": e.action,
                    "price_at_time": e.price_at_time,
                    "reason_text": e.reason_text,
                    "outcome_text": e.outcome_text,
                    "created_at": e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "",
                }
                # Gracefully include new columns if they exist post-migration
                try:
                    row["company_name"] = getattr(e, "company_name", None)
                except Exception:
                    row["company_name"] = None
                try:
                    row["mood"] = getattr(e, "mood", None)
                except Exception:
                    row["mood"] = None
                try:
                    upd = getattr(e, "updated_at", None)
                    row["updated_at"] = upd.strftime("%Y-%m-%d %H:%M") if upd else None
                except Exception:
                    row["updated_at"] = None
                result.append(row)
        return {"user_id": user_id, "entries": result, "total": len(result)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Task B: Trade Journal — PUT, DELETE, stats
# ---------------------------------------------------------------------------

@app.put("/trade-journal/{entry_id}")
def trade_journal_update_endpoint(entry_id: int, req: TradeJournalUpdateRequest, user_id: int):
    """Update outcome_text and mood on a trade journal entry. user_id passed as query param."""
    try:
        with get_session() as session:
            entry = session.query(TradeJournal).filter_by(id=entry_id).first()
            if not entry:
                raise HTTPException(status_code=404, detail="Entry not found")
            if entry.user_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to edit this entry")
            entry.outcome_text = req.outcome_text.strip()
            try:
                entry.mood = req.mood
            except Exception:
                pass
            try:
                entry.updated_at = datetime.now(timezone.utc)
            except Exception:
                pass
            session.commit()
            session.refresh(entry)
            result = {
                "id": entry.id,
                "ticker": entry.ticker,
                "action": entry.action,
                "price_at_time": entry.price_at_time,
                "reason_text": entry.reason_text,
                "outcome_text": entry.outcome_text,
                "created_at": entry.created_at.strftime("%Y-%m-%d %H:%M") if entry.created_at else "",
            }
            try:
                result["company_name"] = getattr(entry, "company_name", None)
                result["mood"] = getattr(entry, "mood", None)
                upd = getattr(entry, "updated_at", None)
                result["updated_at"] = upd.strftime("%Y-%m-%d %H:%M") if upd else None
            except Exception:
                pass
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/trade-journal/{entry_id}")
def trade_journal_delete_endpoint(entry_id: int, user_id: int):
    """Delete a trade journal entry. user_id passed as query param."""
    try:
        with get_session() as session:
            entry = session.query(TradeJournal).filter_by(id=entry_id).first()
            if not entry:
                raise HTTPException(status_code=404, detail="Entry not found")
            if entry.user_id != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to delete this entry")
            session.delete(entry)
            session.commit()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trade-journal/{user_id}/stats")
def trade_journal_stats_endpoint(user_id: int):
    """Compute analytics over all journal entries for a user."""
    try:
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            entries = session.query(TradeJournal).filter_by(user_id=user_id).all()
            entries_data = []
            for e in entries:
                entries_data.append({
                    "ticker": e.ticker,
                    "action": e.action,
                    "reason_text": e.reason_text or "",
                    "outcome_text": (e.outcome_text or "").lower(),
                })

        total_entries = len(entries_data)

        # most_journalled_ticker
        ticker_counts: dict[str, int] = {}
        for e in entries_data:
            ticker_counts[e["ticker"]] = ticker_counts.get(e["ticker"], 0) + 1
        most_journalled_ticker = max(ticker_counts, key=lambda k: ticker_counts[k]) if ticker_counts else None

        # win_loss_ratio
        wins = sum(1 for e in entries_data if "profit" in e["outcome_text"])
        losses = sum(1 for e in entries_data if "loss" in e["outcome_text"])
        ratio = round(wins / losses, 2) if losses > 0 else None
        win_loss_ratio = {"wins": wins, "losses": losses, "ratio": ratio}

        # top_keywords from reason_text
        STOPWORDS = {"the", "a", "an", "is", "in", "of", "and", "to", "i", "my", "this", "for", "it", "at"}
        word_freq: dict[str, int] = {}
        for e in entries_data:
            for w in e["reason_text"].lower().split():
                cleaned = "".join(c for c in w if c.isalpha())
                if cleaned and cleaned not in STOPWORDS and len(cleaned) > 2:
                    word_freq[cleaned] = word_freq.get(cleaned, 0) + 1
        top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        top_keywords = [{"word": w, "count": c} for w, c in top_keywords]

        # action_breakdown
        action_breakdown = {"BUY": 0, "SELL": 0, "HOLD": 0, "WATCH": 0}
        for e in entries_data:
            act = e["action"].upper()
            if act in action_breakdown:
                action_breakdown[act] += 1

        # AI pattern detection — one Haiku call
        patterns = []
        try:
            all_reasons = " | ".join(e["reason_text"] for e in entries_data if e["reason_text"])
            if all_reasons:
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if api_key and api_key != "placeholder":
                    client = anthropic.Anthropic(api_key=api_key)
                    prompt = (
                        f'Find 2 patterns in these trade journal reasons: {all_reasons[:2000]}. '
                        'Return JSON: [{"pattern": str}]'
                    )
                    import time as _tt
                    for attempt in range(3):
                        try:
                            resp = client.messages.create(
                                model=HAIKU_MODEL, max_tokens=150,
                                messages=[{"role": "user", "content": prompt}],
                            )
                            break
                        except Exception as _pe:
                            if attempt == 2:
                                raise
                            _tt.sleep(1.0 * (2 ** attempt))
                    _log_token_usage("trade_journal_stats", resp.usage)
                    raw = _extract_json_from_text(resp.content[0].text)
                    patterns = json.loads(raw)
                    if not isinstance(patterns, list):
                        patterns = []
        except Exception as _pe:
            print(f"[TJ-STATS] Pattern AI call failed: {_pe}")
            patterns = []

        return {
            "user_id": user_id,
            "total_entries": total_entries,
            "most_journalled_ticker": most_journalled_ticker,
            "win_loss_ratio": win_loss_ratio,
            "top_keywords": top_keywords,
            "action_breakdown": action_breakdown,
            "patterns": patterns,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Task C: Screener endpoint
# ---------------------------------------------------------------------------

SECTOR_PE_MAP = {
    "Technology": 35, "Financial Services": 18, "Energy": 12,
    "Healthcare": 28, "Consumer Cyclical": 25, "Industrials": 22,
    "Basic Materials": 15, "Consumer Defensive": 30, "Utilities": 20,
    "Real Estate": 20, "Communication Services": 22,
}

_BULLISH_SIGNALS = {"BULLISH", "CAUTIOUSLY BULLISH"}
_BEARISH_SIGNALS = {"BEARISH", "CAUTIOUSLY BEARISH"}


@app.get("/screener")
def screener_endpoint(preset: str):
    """
    Preset-based screener using analysis_history + yfinance.
    presets: quality_value | promoter_conviction | fii_accumulation | turnaround | 52w_low_bullish
    """
    try:
        results = []

        if preset == "quality_value":
            try:
                from datetime import timedelta
                cutoff_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
                with get_session() as session:
                    rows = session.query(AnalysisHistory).filter(
                        AnalysisHistory.analysis_date >= cutoff_date,
                        AnalysisHistory.signal.in_(["BULLISH", "CAUTIOUSLY BULLISH"]),
                        AnalysisHistory.confidence_pct > 65,
                    ).order_by(AnalysisHistory.confidence_pct.desc()).all()
                    # Deduplicate by ticker — keep highest confidence
                    seen: dict[str, tuple] = {}
                    for r in rows:
                        if r.ticker not in seen:
                            seen[r.ticker] = (r.signal, r.confidence_pct, r.full_json)
                candidates = list(seen.items())

                for ticker, (signal, conf, fj) in candidates:
                    try:
                        ns = _to_ns(ticker)
                        info = _yf_fetch_info(ns)
                        pe = info.get("trailingPE") or info.get("forwardPE")
                        sector = info.get("sector") or "Unknown"
                        sector_pe = SECTOR_PE_MAP.get(sector, 25)
                        if pe is None or pe <= 0 or pe >= sector_pe:
                            continue
                        company = info.get("longName") or info.get("shortName") or ticker
                        results.append({
                            "ticker": ticker,
                            "company_name": company,
                            "signal": signal,
                            "confidence_pct": conf,
                            "reason": f"Signal: {signal}, Confidence: {conf}%, PE below sector avg",
                        })
                    except Exception:
                        continue
                results = results[:12]
            except Exception as _se:
                print(f"[SCREENER quality_value] {_se}")

        elif preset == "promoter_conviction":
            try:
                from datetime import timedelta
                cutoff_60 = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
                with get_session() as session:
                    # Get latest analysis per ticker
                    from sqlalchemy import func
                    latest_ids = session.query(
                        func.max(AnalysisHistory.id)
                    ).group_by(AnalysisHistory.ticker).all()
                    latest_ids = [row[0] for row in latest_ids]
                    rows = session.query(AnalysisHistory).filter(
                        AnalysisHistory.id.in_(latest_ids),
                        AnalysisHistory.signal.notin_(["BEARISH", "CAUTIOUSLY BEARISH"]),
                    ).all()

                    # Bearish flips in last 60 days
                    bearish_flipped = set(
                        r.ticker for r in session.query(SignalEvent).filter(
                            SignalEvent.event_date >= cutoff_60,
                            SignalEvent.to_signal.in_(["BEARISH", "CAUTIOUSLY BEARISH"]),
                        ).all()
                    )

                    for r in rows:
                        if r.ticker in bearish_flipped:
                            continue
                        try:
                            data = json.loads(r.full_json)
                            fs = data.get("fundamentals_snapshot", {})
                            pledged = fs.get("promoter_pledged_pct")
                            if pledged is None:
                                pledged = r.promoter_pledged_pct
                            if pledged is None or pledged >= 10:
                                continue
                            company = data.get("company_name") or r.ticker
                            results.append({
                                "ticker": r.ticker,
                                "company_name": company,
                                "signal": r.signal,
                                "confidence_pct": r.confidence_pct or 0,
                                "reason": f"Low pledging ({pledged:.1f}%), signal: {r.signal}",
                            })
                        except Exception:
                            continue
                results = results[:12]
            except Exception as _se:
                print(f"[SCREENER promoter_conviction] {_se}")

        elif preset == "fii_accumulation":
            try:
                with get_session() as session:
                    from sqlalchemy import func
                    # Get all tickers with >= 2 analysis entries
                    tickers_with_multi = session.query(AnalysisHistory.ticker).group_by(
                        AnalysisHistory.ticker
                    ).having(func.count(AnalysisHistory.id) >= 2).all()
                    tickers_with_multi = [t[0] for t in tickers_with_multi]

                    for ticker in tickers_with_multi:
                        rows = session.query(AnalysisHistory).filter(
                            AnalysisHistory.ticker == ticker
                        ).order_by(AnalysisHistory.created_at.desc()).limit(2).all()
                        if len(rows) < 2:
                            continue
                        try:
                            d0 = json.loads(rows[0].full_json)
                            d1 = json.loads(rows[1].full_json)
                            fii0 = d0.get("fundamentals_snapshot", {}).get("fii_holding_pct")
                            fii1 = d1.get("fundamentals_snapshot", {}).get("fii_holding_pct")
                            if fii0 is None or fii1 is None:
                                continue
                            if fii0 <= fii1:
                                continue
                            company = d0.get("company_name") or ticker
                            results.append({
                                "ticker": ticker,
                                "company_name": company,
                                "signal": rows[0].signal,
                                "confidence_pct": rows[0].confidence_pct or 0,
                                "reason": f"FII increased: {fii1:.1f}% → {fii0:.1f}%",
                            })
                        except Exception:
                            continue
                results = results[:12]
            except Exception as _se:
                print(f"[SCREENER fii_accumulation] {_se}")

        elif preset == "turnaround":
            try:
                with get_session() as session:
                    from sqlalchemy import func
                    latest_ids = session.query(
                        func.max(AnalysisHistory.id)
                    ).group_by(AnalysisHistory.ticker).all()
                    latest_ids = [row[0] for row in latest_ids]
                    rows = session.query(AnalysisHistory).filter(
                        AnalysisHistory.id.in_(latest_ids),
                        AnalysisHistory.signal.in_(["BULLISH", "CAUTIOUSLY BULLISH"]),
                    ).all()

                    for r in rows:
                        try:
                            data = json.loads(r.full_json)
                            ts_story = (data.get("key_factors") or {}).get("turnaround_story") or ""
                            if len(ts_story.strip()) <= 20:
                                continue
                            company = data.get("company_name") or r.ticker
                            results.append({
                                "ticker": r.ticker,
                                "company_name": company,
                                "signal": r.signal,
                                "confidence_pct": r.confidence_pct or 0,
                                "reason": ts_story.strip()[:60],
                            })
                        except Exception:
                            continue
                results = results[:12]
            except Exception as _se:
                print(f"[SCREENER turnaround] {_se}")

        elif preset == "52w_low_bullish":
            try:
                with get_session() as session:
                    from sqlalchemy import func
                    latest_ids = session.query(
                        func.max(AnalysisHistory.id)
                    ).group_by(AnalysisHistory.ticker).all()
                    latest_ids = [row[0] for row in latest_ids]
                    rows = session.query(AnalysisHistory).filter(
                        AnalysisHistory.id.in_(latest_ids),
                        AnalysisHistory.signal.in_(["BULLISH", "CAUTIOUSLY BULLISH"]),
                    ).all()
                    rows_data = [(r.ticker, r.signal, r.confidence_pct, r.full_json) for r in rows]

                for ticker, signal, conf, fj in rows_data:
                    try:
                        ns = _to_ns(ticker)
                        info = _yf_fetch_info(ns)
                        current = info.get("currentPrice") or info.get("regularMarketPrice")
                        low52 = info.get("fiftyTwoWeekLow")
                        if not current or not low52 or low52 <= 0:
                            continue
                        if current > low52 * 1.15:
                            continue
                        company = info.get("longName") or info.get("shortName") or ticker
                        try:
                            fj_data = json.loads(fj)
                            company = fj_data.get("company_name") or company
                        except Exception:
                            pass
                        results.append({
                            "ticker": ticker,
                            "company_name": company,
                            "signal": signal,
                            "confidence_pct": conf or 0,
                            "reason": "Price near 52W low, signal bullish",
                        })
                    except Exception:
                        continue
                results = results[:12]
            except Exception as _se:
                print(f"[SCREENER 52w_low_bullish] {_se}")

        else:
            return []

        return results
    except Exception as _top_err:
        print(f"[SCREENER] Top-level error: {_top_err}")
        return []


# ---------------------------------------------------------------------------
# Task D: PDF Export endpoint
# ---------------------------------------------------------------------------

@app.get("/portfolio/export/pdf/{user_id}")
def export_portfolio_pdf(user_id: int):
    """Generate a one-page portfolio review PDF (or plain text if fpdf2 not installed)."""
    try:
        import math

        # Step 1: Fetch holdings with P&L (same logic as /portfolio/{user_id})
        with get_session() as session:
            user = session.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            holdings = session.query(Portfolio).filter_by(user_id=user_id, group_name="holdings").all()
            holdings_snap = [(h.ticker, h.company_name, h.shares, h.buy_price) for h in holdings]

            # Step 2: Get latest signal per ticker
            ticker_signals: dict[str, dict] = {}
            for ticker, _, _, _ in holdings_snap:
                row = session.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker
                ).order_by(AnalysisHistory.created_at.desc()).first()
                if row:
                    ticker_signals[ticker] = {"signal": row.signal, "conf": row.confidence_pct}

            # Step 3: Red flags (inline — no HTTP call)
            red_flag_list = []
            from datetime import timedelta
            cutoff30 = datetime.now(timezone.utc) - timedelta(days=30)
            bearish_flips_pdf = session.query(SignalEvent).filter(
                SignalEvent.created_at >= cutoff30,
                SignalEvent.ticker.in_([t for t, _, _, _ in holdings_snap]),
                SignalEvent.to_signal.in_(["BEARISH", "CAUTIOUSLY BEARISH"]),
            ).all()
            bf_map = {f.ticker for f in bearish_flips_pdf}
            for ticker, _, _, _ in holdings_snap:
                row = session.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker
                ).order_by(AnalysisHistory.created_at.desc()).first()
                if row and row.full_json:
                    try:
                        d = json.loads(row.full_json)
                        pledged = (d.get("fundamentals_snapshot") or {}).get("promoter_pledged_pct") or row.promoter_pledged_pct
                        if pledged and pledged > 30:
                            red_flag_list.append(f"{ticker}: High pledging {pledged:.1f}%")
                    except Exception:
                        pass
                if ticker in bf_map:
                    red_flag_list.append(f"{ticker}: Bearish signal flip in last 30 days")

        # Build P&L summary
        holdings_summary = []
        for ticker, company, shares, buy_price in holdings_snap:
            ns = _to_ns(ticker)
            current_price, _ = _yf_price(ns)
            invested = shares * buy_price
            current_val = shares * current_price if current_price else 0.0
            pnl_pct = round((current_val - invested) / invested * 100, 1) if invested > 0 and current_val > 0 else 0.0
            sig_info = ticker_signals.get(ticker, {})
            holdings_summary.append({
                "ticker": ticker,
                "company": company,
                "signal": sig_info.get("signal", "N/A"),
                "pnl_pct": pnl_pct,
                "current_price": round(current_price, 2) if current_price else 0.0,
            })

        holdings_json = json.dumps(holdings_summary, indent=2)
        flags_text = "\n".join(red_flag_list) if red_flag_list else "None detected"

        # Step 4: One Sonnet call for review markdown
        markdown_text = "# Portfolio Review\n\nUnable to generate AI review.\n"
        try:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key and api_key != "placeholder":
                client = anthropic.Anthropic(api_key=api_key)
                import time as _tt
                for attempt in range(3):
                    try:
                        resp = client.messages.create(
                            model=SONNET_MODEL,
                            max_tokens=1200,
                            system="You are a private wealth advisor. Write a one-page portfolio review for a long-term Indian equity investor. Use bullet points. Format as clean markdown.",
                            messages=[{
                                "role": "user",
                                "content": (
                                    f"Holdings: {holdings_json}\n"
                                    f"Red flags: {flags_text}\n\n"
                                    "Write: Executive Summary (3 bullets), Holdings Review (one line per stock with signal and P&L%), Risk Watch, Overall Recommendation."
                                )
                            }],
                        )
                        break
                    except Exception as _pe:
                        if attempt == 2:
                            raise
                        _tt.sleep(1.0 * (2 ** attempt))
                _log_token_usage("pdf_export", resp.usage)
                markdown_text = resp.content[0].text.strip()
        except Exception as _ae:
            print(f"[PDF-EXPORT] AI call failed: {_ae}")

        # Step 5/6: Return PDF or plain text
        if FPDF2_AVAILABLE:
            try:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)

                for line in markdown_text.split("\n"):
                    if line.startswith("# "):
                        pdf.set_font("Arial", style="B", size=16)
                        pdf.cell(0, 10, line[2:], ln=True)
                    elif line.startswith("## "):
                        pdf.set_font("Arial", style="B", size=13)
                        pdf.cell(0, 8, line[3:], ln=True)
                    elif line.startswith("### "):
                        pdf.set_font("Arial", style="B", size=11)
                        pdf.cell(0, 7, line[4:], ln=True)
                    else:
                        # Strip bold markers
                        clean = line.replace("**", "").replace("__", "")
                        pdf.set_font("Arial", size=10)
                        pdf.multi_cell(0, 6, clean)

                pdf_bytes = pdf.output(dest="S")
                if isinstance(pdf_bytes, str):
                    pdf_bytes = pdf_bytes.encode("latin-1")

                today_str = date.today().strftime("%Y%m%d")
                return StreamingResponse(
                    io.BytesIO(pdf_bytes),
                    media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=portfolio_review_{user_id}_{today_str}.pdf"},
                )
            except Exception as _pdfe:
                print(f"[PDF-EXPORT] fpdf2 render failed: {_pdfe}")
                # Fall through to plain text

        # Plain text fallback
        today_str = date.today().strftime("%Y%m%d")
        return StreamingResponse(
            io.BytesIO(markdown_text.encode("utf-8")),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=portfolio_review_{user_id}_{today_str}.txt"},
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[PDF-EXPORT] Top-level error: {e}")
        fallback_text = f"Portfolio review unavailable. Error: {str(e)}"
        return StreamingResponse(
            io.BytesIO(fallback_text.encode("utf-8")),
            media_type="text/plain",
        )


# ---------------------------------------------------------------------------
# Task E: Token stats endpoint (reads token_log.jsonl)
# ---------------------------------------------------------------------------

@app.get("/token-stats")
def token_stats_endpoint():
    """Read token_log.jsonl and return aggregated usage + cost stats."""
    try:
        HAIKU_INPUT_RATE  = 0.001 / 1_000_000   # $ per token
        HAIKU_OUTPUT_RATE = 0.005 / 1_000_000
        SONNET_INPUT_RATE  = 0.003 / 1_000_000
        SONNET_OUTPUT_RATE = 0.015 / 1_000_000

        if not TOKEN_LOG_PATH.exists():
            return {
                "total_cost_usd": 0.0,
                "total_calls": 0,
                "cost_by_endpoint": {},
                "cache_hit_rate_pct": 0.0,
                "most_expensive_endpoint": None,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cache_read_tokens": 0,
            }

        total_cost = 0.0
        total_calls = 0
        cost_by_ep: dict[str, float] = {}
        total_input = 0
        total_output = 0
        total_cache_read = 0

        with open(TOKEN_LOG_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                inp = entry.get("input_tokens", 0) or 0
                out = entry.get("output_tokens", 0) or 0
                cr  = entry.get("cache_read_input_tokens", 0) or 0
                model = (entry.get("model") or "").lower()
                endpoint = entry.get("endpoint") or "unknown"

                if "haiku" in model:
                    cost = inp * HAIKU_INPUT_RATE + out * HAIKU_OUTPUT_RATE
                else:
                    cost = inp * SONNET_INPUT_RATE + out * SONNET_OUTPUT_RATE

                total_cost += cost
                total_calls += 1
                total_input += inp
                total_output += out
                total_cache_read += cr
                cost_by_ep[endpoint] = cost_by_ep.get(endpoint, 0.0) + cost

        cache_hit_rate = round(total_cache_read / total_input * 100, 2) if total_input > 0 else 0.0
        most_expensive = max(cost_by_ep, key=lambda k: cost_by_ep[k]) if cost_by_ep else None

        return {
            "total_cost_usd": round(total_cost, 6),
            "total_calls": total_calls,
            "cost_by_endpoint": {k: round(v, 6) for k, v in cost_by_ep.items()},
            "cache_hit_rate_pct": cache_hit_rate,
            "most_expensive_endpoint": most_expensive,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cache_read_tokens": total_cache_read,
        }
    except Exception as e:
        print(f"[TOKEN-STATS] Error: {e}")
        return {
            "total_cost_usd": 0.0,
            "total_calls": 0,
            "cost_by_endpoint": {},
            "cache_hit_rate_pct": 0.0,
            "most_expensive_endpoint": None,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cache_read_tokens": 0,
        }


# ---------------------------------------------------------------------------
# Daily Action Card
# ---------------------------------------------------------------------------

@app.get("/daily-action/{user_id}")
def daily_action_endpoint(user_id: int):
    """One-sentence daily action derived from signal warnings, timeframe conflicts, alerts.
    Returns {action: str, urgency: 'high'|'medium'|'low'}."""
    try:
        from datetime import timedelta

        # Collect signal warnings
        warnings = []
        try:
            w = portfolio_signal_warnings(user_id)
            warnings = w.get("warnings", [])
        except Exception:
            pass

        # Collect timeframe conflicts from DB directly (no HTTP)
        conflicts = []
        try:
            with get_session() as session:
                holdings = session.query(Portfolio).filter_by(
                    user_id=user_id, group_name="holdings"
                ).all()
                held_tickers = [h.ticker for h in holdings]
                for ticker in held_tickers:
                    row = session.query(AnalysisHistory).filter(
                        AnalysisHistory.ticker == ticker
                    ).order_by(AnalysisHistory.created_at.desc()).first()
                    if not row or not row.full_json:
                        continue
                    try:
                        data = json.loads(row.full_json)
                        cp = data.get("current_price_inr")
                        tp = data.get("target_prices") or {}
                        st = tp.get("short_term_3m")
                        lt = tp.get("long_term_36m")
                        if cp and st and lt and cp > 0:
                            if (st > cp) != (lt > cp):
                                conflicts.append({
                                    "ticker": ticker,
                                    "short": round((st - cp) / cp * 100, 1),
                                    "long": round((lt - cp) / cp * 100, 1),
                                })
                    except Exception:
                        pass
        except Exception:
            pass

        # Collect triggered alerts
        triggered = []
        try:
            with get_session() as session:
                alerts = session.query(PriceTarget).filter_by(
                    user_id=user_id, triggered=True
                ).all()
                triggered = [{"ticker": a.ticker, "direction": a.direction, "price": a.target_price} for a in alerts]
        except Exception:
            pass

        # Build urgency
        urgency = "low"
        if triggered or any(w.get("is_bearish") for w in warnings):
            urgency = "high"
        elif warnings or conflicts:
            urgency = "medium"

        # Haiku call
        action = "Review your portfolio — no urgent signals detected today."
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key and api_key != "placeholder":
            try:
                context_parts = []
                if triggered:
                    context_parts.append(f"Triggered alerts: {', '.join(t['ticker'] for t in triggered)}")
                if warnings:
                    bearish = [w['ticker'] for w in warnings if w.get('is_bearish')]
                    flipped = [w['ticker'] for w in warnings if w.get('signal_flipped')]
                    if bearish: context_parts.append(f"Bearish signals: {', '.join(bearish)}")
                    if flipped: context_parts.append(f"Signal flips: {', '.join(flipped)}")
                if conflicts:
                    context_parts.append(f"Timeframe conflicts: {', '.join(c['ticker'] for c in conflicts)}")

                prompt = (
                    f"Portfolio data:\n{chr(10).join(context_parts) if context_parts else 'No urgent signals.'}\n\n"
                    "In exactly one sentence of max 20 words, what is the single most important "
                    "thing this investor should do today? Be specific — name the ticker."
                )
                client = anthropic.Anthropic(api_key=api_key)
                import time as _tt
                for attempt in range(3):
                    try:
                        resp = client.messages.create(
                            model=HAIKU_MODEL, max_tokens=60, temperature=0,
                            messages=[{"role": "user", "content": prompt}]
                        )
                        break
                    except Exception as e:
                        if attempt == 2: raise
                        _tt.sleep(1.0 * (2 ** attempt))
                _log_token_usage("daily_action", resp.usage)
                action = resp.content[0].text.strip().rstrip(".")
            except Exception as e:
                print(f"[DAILY-ACTION] Haiku failed: {e}")

        return {"action": action, "urgency": urgency}

    except Exception as e:
        return {"action": "Check your portfolio for any recent signal changes.", "urgency": "low"}


# ---------------------------------------------------------------------------
# Push Notifications
# ---------------------------------------------------------------------------

class DeviceTokenRegisterRequest(BaseModel):
    user_id: int
    device_token: str
    platform: str = "ios"


class TestNotificationRequest(BaseModel):
    user_id: int
    ticker: str
    exchange: str = "NSE"


class MorningSummaryPushRequest(BaseModel):
    user_id: int


@app.post("/notifications/register-device")
def notifications_register_device(req: DeviceTokenRegisterRequest):
    try:
        with get_session() as session:
            existing = session.query(DeviceToken).filter_by(device_token=req.device_token).first()
            if existing:
                existing.updated_at = datetime.now(timezone.utc)
                existing.user_id = req.user_id
            else:
                session.add(DeviceToken(
                    user_id=req.user_id,
                    device_token=req.device_token,
                    platform=req.platform,
                ))
            session.commit()
        return {"success": True, "message": "Device token registered"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/notifications/test")
def notifications_test(req: TestNotificationRequest):
    try:
        # Fetch quick info
        ns_ticker = _to_ns(req.ticker)
        info = _yf_fetch_info(ns_ticker)
        price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0

        # Get latest signal
        signal_str = "UNKNOWN"
        confidence = None
        with get_session() as session:
            row = session.query(AnalysisHistory).filter(
                AnalysisHistory.ticker == req.ticker.upper()
            ).order_by(AnalysisHistory.created_at.desc()).first()
            if row:
                signal_str = row.signal
                confidence = row.confidence_pct

        conf_str = f" | Confidence: {int(confidence)}%" if confidence else ""
        price_str = f"₹{price:,.2f}" if price else "Price unavailable"

        return {
            "title": f"{req.ticker.upper()} — {signal_str}",
            "body": f"{price_str}{conf_str}",
            "data": {"ticker": req.ticker.upper(), "exchange": req.exchange},
        }
    except Exception as e:
        return {
            "title": f"{req.ticker.upper()} — Analysis",
            "body": "Tap to view latest analysis",
            "data": {"ticker": req.ticker.upper(), "exchange": req.exchange},
        }


@app.post("/notifications/morning-summary-push")
def notifications_morning_summary_push(req: MorningSummaryPushRequest):
    try:
        with get_session() as session:
            user = session.get(User, req.user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            display_name = user.display_name

        # Call morning summary logic inline
        try:
            summary_data = morning_summary_endpoint(req.user_id)
        except Exception:
            summary_data = {"summary": "Check your portfolio today.", "mood": "cautious", "priority_items": []}

        mood = summary_data.get("mood", "cautious")
        mood_emoji = "📈" if mood == "positive" else "📉" if mood == "negative" else "📊"

        priority_items = summary_data.get("priority_items", []) or []
        first_action = ""
        if priority_items:
            first_action = priority_items[0].get("message", "")

        summary = summary_data.get("summary", "")
        first_bullet = ""
        for line in summary.split("\n"):
            line = line.strip()
            if line.startswith("•"):
                first_bullet = line.lstrip("• ").strip()
                break

        body_parts = []
        if first_action: body_parts.append(first_action)
        elif first_bullet: body_parts.append(first_bullet)
        body_parts.append(f"{mood.capitalize()} market today.")

        return {
            "title": f"Good morning, {display_name} {mood_emoji}",
            "body": " ".join(body_parts[:2]),
            "data": {"screen": "home"},
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "title": "Good morning",
            "body": "Your daily portfolio summary is ready.",
            "data": {"screen": "home"},
        }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health_endpoint():
    import os
    result = {"status": "ok", "version": "1.0", "timestamp": datetime.now(timezone.utc).isoformat()}

    # Check yfinance
    try:
        info = yf.Ticker("SBIN.NS").info
        result["yfinance"] = bool(info and (info.get("currentPrice") or info.get("regularMarketPrice")))
    except Exception:
        result["yfinance"] = False

    # Check DB
    try:
        with get_session() as session:
            from sqlalchemy import text
            session.execute(text("SELECT 1"))
        result["db"] = True
    except Exception:
        result["db"] = False

    # Check Anthropic key
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    result["anthropic_key_set"] = bool(api_key and api_key != "placeholder")

    result["status"] = "ok" if all([result.get("yfinance"), result.get("db"), result.get("anthropic_key_set")]) else "degraded"
    return result


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nivesh Backend Dashboard</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#0d1117;color:#c9d1d9;font-family:'SF Mono','Cascadia Code',monospace;font-size:13px}
    header{background:#161b22;border-bottom:1px solid #30363d;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}
    header h1{font-size:18px;color:#f0f6fc;font-weight:600;letter-spacing:.5px}
    .status{display:flex;align-items:center;gap:12px;color:#8b949e;font-size:12px}
    .dot{width:8px;height:8px;border-radius:50%;background:#3fb950;animation:pulse 2s infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
    main{padding:20px 24px;display:grid;gap:20px}
    .row2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
    .card{background:#161b22;border:1px solid #30363d;border-radius:8px;overflow:hidden}
    .card-header{padding:10px 16px;border-bottom:1px solid #30363d;display:flex;justify-content:space-between;align-items:center}
    .card-title{font-size:11px;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:1px}
    .card-body{padding:16px}
    .empty{color:#484f58;font-style:italic;text-align:center;padding:24px}
    .analysis-item{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px;margin-bottom:10px}
    .analysis-item:last-child{margin-bottom:0}
    .a-ticker{font-size:16px;font-weight:700;color:#f0f6fc}
    .a-meta{color:#8b949e;font-size:11px;margin-top:4px}
    .a-stage{margin-top:8px;color:#58a6ff;font-size:12px}
    .s-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#58a6ff;margin-right:6px;animation:pulse 1s infinite}
    .tok-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
    .tok-stat{background:#0d1117;border-radius:6px;padding:12px;text-align:center}
    .tok-stat .val{font-size:20px;font-weight:700;color:#f0f6fc}
    .tok-stat .lbl{font-size:10px;color:#8b949e;margin-top:4px;text-transform:uppercase;letter-spacing:.5px}
    .tok-stat.r .val{color:#f85149}
    .tok-stat.g .val{color:#3fb950}
    .tok-stat.b .val{color:#58a6ff}
    .tok-stat.y .val{color:#d29922}
    table{width:100%;border-collapse:collapse}
    th{text-align:left;padding:8px 12px;font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid #30363d;font-weight:600}
    td{padding:7px 12px;border-bottom:1px solid #21262d;font-size:12px;vertical-align:middle}
    tr:last-child td{border-bottom:none}
    tr:hover td{background:#1c2128}
    .badge{display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600}
    .bull{background:rgba(63,185,80,.15);color:#3fb950}
    .bear{background:rgba(248,81,73,.15);color:#f85149}
    .hold{background:rgba(210,153,34,.15);color:#d29922}
    .cache{background:rgba(88,166,255,.15);color:#58a6ff}
    .smart{background:rgba(188,140,255,.15);color:#bc8cff}
    .full{background:rgba(63,185,80,.12);color:#3fb950}
    .mock{background:rgba(139,148,158,.15);color:#8b949e}
    .err{background:rgba(248,81,73,.15);color:#f85149}
    .ok{background:rgba(63,185,80,.1);color:#3fb950}
    .mGET{background:rgba(88,166,255,.1);color:#58a6ff}
    .mPOST{background:rgba(63,185,80,.1);color:#3fb950}
    .mDELETE{background:rgba(248,81,73,.1);color:#f85149}
    .mPUT{background:rgba(210,153,34,.1);color:#d29922}
    .ts{color:#6e7681;font-size:11px}
    .path{max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    #lu{color:#484f58;font-size:11px}
    .uptime{font-size:11px;color:#8b949e;margin-top:4px}
    .archive-details{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px;margin-top:10px;display:none}
    .json-box{background:#161b22;padding:10px;border-radius:4px;overflow:auto;max-height:300px;font-size:11px;color:#8b949e;border:1px solid #21262d;white-space:pre-wrap;margin-top:8px}
    .btn-view{background:#238636;color:#fff;border:none;padding:2px 8px;border-radius:4px;cursor:pointer;font-size:10px}
    .btn-view:hover{background:#2ea043}
    .tab-btn{background:#21262d;color:#8b949e;border:1px solid #30363d;padding:4px 10px;border-radius:4px 4px 0 0;cursor:pointer;font-size:10px;margin-right:2px}
    .tab-btn.active{background:#30363d;color:#f0f6fc;border-bottom:none}
  </style>
</head>
<body>
<header>
  <div>
    <h1>&#x20B9; Nivesh Backend Dashboard</h1>
    <div class="uptime" id="uptime"></div>
  </div>
  <div class="status">
    <div class="dot"></div>
    <span>Live &bull; 1s refresh</span>
    <span id="lu"></span>
  </div>
</header>
<main>
  <div class="row2">
    <div class="card">
      <div class="card-header">
        <span class="card-title">&#x1F4BE; System & Cache Metrics</span>
      </div>
      <div class="card-body">
        <div class="tok-grid">
          <div class="tok-stat r"><div class="val" id="db_u">-</div><div class="lbl">Users</div></div>
          <div class="tok-stat g"><div class="val" id="db_h">-</div><div class="lbl">Holdings</div></div>
          <div class="tok-stat b"><div class="val" id="db_a">-</div><div class="lbl">Analyses</div></div>
          <div class="tok-stat y"><div class="val" id="db_s">-</div><div class="lbl">Signals</div></div>
          <div class="tok-stat r"><div class="val" id="c_q">-</div><div class="lbl">Quick Info Caches</div></div>
          <div class="tok-stat g"><div class="val" id="c_m">-</div><div class="lbl">Morning Caches</div></div>
          <div class="tok-stat b"><div class="val" id="c_sec">-</div><div class="lbl">Sector Cache</div></div>
          <div class="tok-stat y"><div class="val" id="c_asm">-</div><div class="lbl">ASM/GSM Cache</div></div>
        </div>
      </div>
    </div>
    
    <div class="card">
      <div class="card-header">
        <span class="card-title">&#x1F6E0; Scraper Engine Status</span>
      </div>
      <div class="card-body">
        <div class="tok-grid" id="scraper_status_grid">
          <div class="empty">Loading...</div>
        </div>
      </div>
    </div>
  </div>

  <div class="row2">
    <div class="card">
      <div class="card-header">
        <span class="card-title">&#x26A1; Active Analyses</span>
        <span class="ts" id="ac"></span>
      </div>
      <div class="card-body" id="ab"><div class="empty">No active analyses</div></div>
    </div>
    <div class="card">
      <div class="card-header">
        <span class="card-title">&#x1F522; Session Token Usage</span>
        <span class="ts" id="tc"></span>
      </div>
      <div class="card-body">
        <div class="tok-grid">
          <div class="tok-stat r"><div class="val" id="ti">-</div><div class="lbl">Input</div></div>
          <div class="tok-stat g"><div class="val" id="to">-</div><div class="lbl">Output</div></div>
          <div class="tok-stat b"><div class="val" id="tr">-</div><div class="lbl">Cache Read</div></div>
          <div class="tok-stat y"><div class="val" id="tw">-</div><div class="lbl">Cache Write</div></div>
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <span class="card-title">&#x1F4CA; Recent Session Activity</span>
      <span class="ts" id="anc"></span>
    </div>
    <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Time</th><th>Ticker</th><th>Exchange</th><th>User</th>
          <th>Type</th><th>Signal</th><th>Conf</th><th>Duration</th><th>Status</th>
        </tr></thead>
        <tbody id="at"><tr><td colspan="9" class="empty">No analyses yet</td></tr></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <span class="card-title">&#x1F5D3; Historical Analysis Archive (Database)</span>
      <span class="ts" id="hnc"></span>
    </div>
    <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Created At</th><th>Ticker</th><th>Date</th><th>Signal</th><th>Conf</th><th>User</th><th>Details</th>
        </tr></thead>
        <tbody id="ht"><tr><td colspan="7" class="empty">No historical data</td></tr></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <span class="card-title">&#x1F4BB; Recent Claude Calls</span>
      <span class="ts" id="clc"></span>
    </div>
    <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Time</th><th>Endpoint</th><th>Input</th><th>Output</th><th>Cache Read</th><th>Cache Write</th>
        </tr></thead>
        <tbody id="ct"><tr><td colspan="6" class="empty">No Claude calls yet</td></tr></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <span class="card-title">&#x1F310; API Request Log</span>
      <span class="ts" id="rc"></span>
    </div>
    <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Time</th><th>Method</th><th>Path</th><th>Params</th><th>Status</th><th>Duration</th>
        </tr></thead>
        <tbody id="rt"><tr><td colspan="6" class="empty">No requests yet</td></tr></tbody>
      </table>
    </div>
  </div>
</main>

<script>
let historicalData = [];

function fmt(n){if(n==null)return'-';if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'K';return''+n}
function ts(iso){if(!iso)return'-';return new Date(iso).toLocaleTimeString('en-IN',{hour12:false})}
function dts(iso){if(!iso)return'-';const d=new Date(iso);return d.toLocaleDateString('en-IN')+' '+d.toLocaleTimeString('en-IN',{hour12:false})}
function ela(iso){if(!iso)return'';const s=Math.floor((Date.now()-new Date(iso))/1000);if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m '+s%60+'s';return Math.floor(s/3600)+'h'}
function sig(s){if(!s)return'-';const u=s.toUpperCase();if(u.includes('BULL'))return`<span class="badge bull">${s}</span>`;if(u.includes('BEAR'))return`<span class="badge bear">${s}</span>`;return`<span class="badge hold">${s}</span>`}
function ctype(t){if(!t)return'-';const u=(t||'').toUpperCase();if(u==='CACHE HIT')return`<span class="badge cache">CACHE HIT</span>`;if(u==='SMART CACHE')return`<span class="badge smart">SMART CACHE</span>`;if(u==='FULL AI')return`<span class="badge full">FULL AI</span>`;if(u==='MOCK')return`<span class="badge mock">MOCK</span>`;return`<span class="badge cache">${t}</span>`}
function stbadge(s){if(!s)return'-';const l=s.toLowerCase();if(l==='completed')return`<span class="badge ok">&#x2713; done</span>`;if(l==='error')return`<span class="badge err">&#x2717; error</span>`;if(l==='disconnected')return`<span class="badge err">&#x2717; killed</span>`;return`<span class="badge hold">${s}</span>`}
function mbadge(m){return`<span class="badge m${m}">${m}</span>`}
function hbadge(c){if(!c)return'-';const cls=c<300?'ok':c<400?'cache':'err';return`<span class="badge ${cls}">${c}</span>`}
function fmtParams(p){if(!p)return'';const s=JSON.stringify(p).replace(/[{}"]/g,'');return s.length>45?s.slice(0,45)+'...':s}

function toggleDetails(id){
  const el = document.getElementById('details-'+id);
  el.style.display = el.style.display === 'block' ? 'none' : 'block';
}

function showTab(id, tab){
  const raw = document.getElementById('raw-'+id);
  const full = document.getElementById('full-'+id);
  const bRaw = document.getElementById('bt-raw-'+id);
  const bFull = document.getElementById('bt-full-'+id);
  if(tab==='raw'){
    raw.style.display='block'; full.style.display='none';
    bRaw.classList.add('active'); bFull.classList.remove('active');
  }else{
    raw.style.display='none'; full.style.display='block';
    bRaw.classList.remove('active'); bFull.classList.add('active');
  }
}

async function refresh(){
  try{
    const r=await fetch('/dashboard-data');
    const d=await r.json();

    document.getElementById('lu').textContent='updated '+new Date().toLocaleTimeString('en-IN',{hour12:false});
    if(d.uptime_s!=null){const h=Math.floor(d.uptime_s/3600),m=Math.floor((d.uptime_s%3600)/60),s=Math.floor(d.uptime_s%60);document.getElementById('uptime').textContent=`Server up ${h}h ${m}m ${s}s`;}

    if(d.db_stats) {
      document.getElementById('db_u').textContent = d.db_stats.users || 0;
      document.getElementById('db_h').textContent = d.db_stats.holdings || 0;
      document.getElementById('db_a').textContent = d.db_stats.analyses || 0;
      document.getElementById('db_s').textContent = d.db_stats.signal_events || 0;
    }
    if(d.cache_stats) {
      document.getElementById('c_q').textContent = d.cache_stats.quick_info || 0;
      document.getElementById('c_m').textContent = d.cache_stats.morning_brief || 0;
      document.getElementById('c_sec').textContent = d.cache_stats.sector_performance ? 'OK' : 'Empty';
      document.getElementById('c_asm').textContent = d.cache_stats.asm_gsm ? 'OK' : 'Empty';
      
      const sg = document.getElementById('scraper_status_grid');
      const sdata = d.cache_stats.scraper || {};
      const skeys = Object.keys(sdata);
      if(skeys.length === 0) {
        sg.innerHTML = '<div class="empty">No Scraper Cache</div>';
      } else {
        const colors = ['r', 'g', 'b', 'y'];
        sg.innerHTML = skeys.map((k, i) => `
          <div class="tok-stat ${colors[i % colors.length]}">
            <div class="val">${sdata[k].age_s}s ago</div>
            <div class="lbl">${k}</div>
          </div>
        `).join('');
      }
    }

    const active=d.active_analyses||[];
    document.getElementById('ac').textContent=active.length+' running';
    const ab=document.getElementById('ab');
    ab.innerHTML=active.length===0?'<div class="empty">No active analyses</div>':active.map(a=>`
      <div class="analysis-item">
        <div style="display:flex;justify-content:space-between">
          <span class="a-ticker">${a.ticker}</span><span class="ts">${ts(a.start_ts)}</span>
        </div>
        <div class="a-meta">${a.exchange||'NSE'} &bull; User ${a.user_id||'N/A'} &bull; ${a.mock?'<span class="badge mock">MOCK</span>':'<span class="badge full">LIVE AI</span>'} &bull; running ${ela(a.start_ts)}</div>
        <div class="a-stage"><span class="s-dot"></span>${a.stage||'Processing...'}</div>
      </div>`).join('');

    const tok=d.token_stats||{};
    document.getElementById('ti').textContent=fmt(tok.total_input||0);
    document.getElementById('to').textContent=fmt(tok.total_output||0);
    document.getElementById('tr').textContent=fmt(tok.total_cache_read||0);
    document.getElementById('tw').textContent=fmt(tok.total_cache_write||0);
    document.getElementById('tc').textContent=(tok.total_calls||0)+' Claude calls';

    const an=d.recent_analyses||[];
    document.getElementById('anc').textContent=an.length+' shown';
    const at=document.getElementById('at');
    at.innerHTML=an.length===0?'<tr><td colspan="9" class="empty">No activity yet</td></tr>':an.map(a=>`<tr>
      <td class="ts">${ts(a.start_ts||a.ts)}</td>
      <td style="font-weight:700;color:#f0f6fc">${a.ticker}</td>
      <td>${a.exchange||'NSE'}</td>
      <td class="ts">${a.user_id||'-'}</td>
      <td>${ctype(a.cache_type)}</td>
      <td>${sig(a.signal)}</td>
      <td style="color:#d29922">${a.confidence!=null?a.confidence+'%':'-'}</td>
      <td class="ts">${a.duration_s!=null?a.duration_s+'s':'-'}</td>
      <td>${stbadge(a.status)}</td>
    </tr>`).join('');

    // Historical Archive
    const hist = d.historical_analyses || [];
    document.getElementById('hnc').textContent = hist.length + ' records';
    const ht = document.getElementById('ht');
    ht.innerHTML = hist.length === 0 ? '<tr><td colspan="7" class="empty">No historical data</td></tr>' : hist.map(h => {
      const isExpanded = expandedIds.has(h.id);
      const activeTab = activeTabs[h.id] || "raw";
      return `
      <tr>
        <td class="ts">${dts(h.ts)}</td>
        <td style="font-weight:700;color:#f0f6fc">${h.ticker}</td>
        <td class="ts">${h.analysis_date}</td>
        <td>${sig(h.signal)}</td>
        <td style="color:#d29922">${h.confidence != null ? h.confidence + '%' : '-'}</td>
        <td class="ts">${h.user_id || '-'}</td>
        <td><button class="btn-view" onclick="toggleDetails(${h.id})">View Analysis</button></td>
      </tr>
      <tr id="details-${h.id}" style="display:${isExpanded ? 'table-row' : 'none'}">
        <td colspan="7">
          <div class="archive-details" style="display:block">
            <div style="display:flex;margin-bottom:8px">
              <button class="tab-btn ${activeTab==='raw'?'active':''}" id="bt-raw-${h.id}" onclick="showTab(${h.id}, 'raw')">AI Raw Output</button>
              <button class="tab-btn ${activeTab==='full'?'active':''}" id="bt-full-${h.id}" onclick="showTab(${h.id}, 'full')">API Formatted JSON</button>
            </div>
            <div id="raw-${h.id}" class="json-box" style="display:${activeTab==='raw'?'block':'none'}">${h.raw_output || 'No raw output stored for this record.'}</div>
            <div id="full-${h.id}" class="json-box" style="display:${activeTab==='full'?'block':'none'}">${JSON.stringify(JSON.parse(h.full_json), null, 2)}</div>
          </div>
        </td>
      </tr>`;
    }).join('');

    const cl=(tok.recent||[]);
    document.getElementById('clc').textContent=cl.length+' recent';
    const ct=document.getElementById('ct');
    ct.innerHTML=cl.length===0?'<tr><td colspan="6" class="empty">No Claude calls yet</td></tr>':cl.map(c=>`<tr>
      <td class="ts">${ts(c.ts)}</td>
      <td style="color:#bc8cff">${c.endpoint||'-'}</td>
      <td style="color:#f85149">${fmt(c.input)}</td>
      <td style="color:#3fb950">${fmt(c.output)}</td>
      <td style="color:#58a6ff">${fmt(c.cache_read)}</td>
      <td style="color:#d29922">${fmt(c.cache_write)}</td>
    </tr>`).join('');

    const reqs=d.request_log||[];
    document.getElementById('rc').textContent=reqs.length+' requests';
    const rt=document.getElementById('rt');
    rt.innerHTML=reqs.length===0?'<tr><td colspan="6" class="empty">No requests yet</td></tr>':reqs.map(r=>`<tr>
      <td class="ts">${ts(r.ts)}</td>
      <td>${mbadge(r.method)}</td>
      <td class="path" title="${r.path}">${r.path}</td>
      <td class="ts">${fmtParams(r.params)}</td>
      <td>${hbadge(r.status)}</td>
      <td class="ts">${r.duration_ms!=null?r.duration_ms+'ms':'-'}</td>
    </tr>`).join('');
  }catch(e){console.error('Dashboard error:',e)}
}
refresh();
setInterval(refresh,1000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard_html():
    return HTMLResponse(content=_DASHBOARD_HTML)


@app.get("/dashboard-data")
def dashboard_data():
    uptime = (datetime.now() - _server_start).total_seconds()
    
    # Fetch historical analyses and stats from DB
    history = []
    db_stats = {}
    try:
        with get_session() as session:
            rows = session.query(AnalysisHistory).order_by(AnalysisHistory.created_at.desc()).all()
            for r in rows:
                history.append({
                    "id": r.id,
                    "ts": r.created_at.isoformat(),
                    "ticker": r.ticker,
                    "analysis_date": r.analysis_date,
                    "signal": r.signal,
                    "confidence": r.confidence_pct,
                    "raw_output": r.raw_output,
                    "full_json": r.full_json,
                    "user_id": r.user_id,
                })
            db_stats = {
                "users": session.query(User).count(),
                "holdings": session.query(Portfolio).count(),
                "analyses": session.query(AnalysisHistory).count(),
                "signal_events": session.query(SignalEvent).count() if 'SignalEvent' in globals() else 0,
                "trade_journals": session.query(TradeJournal).count() if 'TradeJournal' in globals() else 0,
            }
    except Exception as e:
        print(f"Error fetching history for dashboard: {e}")

    try:
        import services.scraper as scr
        scraper_cache = {k: {"age_s": round(time.time() - v["ts"])} for k, v in scr._CACHE.items()}
    except Exception:
        scraper_cache = {}

    cache_stats = {
        "quick_info": len(_quick_info_cache),
        "morning_brief": len(_morning_cache),
        "sector_performance": 1 if _sector_cache.get("data") else 0,
        "asm_gsm": 1 if _asm_gsm_cache.get("data") else 0,
        "scraper": scraper_cache
    }

    with _dash_lock:
        active = list(_active_analyses.values())
        completed = list(_completed_analyses)
        reqs = list(_request_log)
        tok = {
            "total_input":       _token_stats["total_input"],
            "total_output":      _token_stats["total_output"],
            "total_cache_read":  _token_stats["total_cache_read"],
            "total_cache_write": _token_stats["total_cache_write"],
            "total_calls":       _token_stats["total_calls"],
            "recent":            list(_token_stats["recent"]),
        }
    return {
        "server_start":    _server_start.isoformat(),
        "uptime_s":        round(uptime),
        "active_analyses": active,
        "recent_analyses": completed,
        "historical_analyses": history,
        "request_log":     reqs,
        "token_stats":     tok,
        "db_stats":        db_stats,
        "cache_stats":     cache_stats,
    }


# ---------------------------------------------------------------------------
# Sector Performance
# ---------------------------------------------------------------------------

_sector_cache: dict = {"data": None, "ts": 0.0}

# Upcoming IPOs (manually tracked)
UPCOMING_IPOS = [
    {"company": "Swiggy Ltd", "open_date": "TBD 2026", "price_band": "₹371-390"},
    {"company": "Bajaj Housing Finance", "open_date": "TBD 2026", "price_band": "₹66-70"},
    {"company": "Hyundai India", "open_date": "TBD 2026", "price_band": "₹1865-1960"},
]

SECTOR_TICKERS = [
    ("^CNXPSUBANK",  "PSU Bank"),
    ("^CNXFMCG",     "FMCG"),
    ("^CNXIT",       "IT"),
    ("^CNXPHARMA",   "Pharma"),
    ("^CNXAUTO",     "Auto"),
    ("^CNXREALTY",   "Realty"),
    ("^CNXENERGY",   "Energy"),
    ("^CNXMETAL",    "Metal"),
]


@app.get("/sector-performance")
def sector_performance_endpoint():
    global _sector_cache
    now = time.time()
    if _sector_cache["data"] and now - _sector_cache["ts"] < 600:
        return _sector_cache["data"]

    sectors = []
    import math
    for ticker, name in SECTOR_TICKERS:
        try:
            current = None
            prev = None
            for attempt in range(3):
                try:
                    t = yf.Ticker(ticker)
                    info = t.fast_info if hasattr(t, "fast_info") else {}
                    current = getattr(info, "last_price", None) or (t.info or {}).get("regularMarketPrice")
                    prev    = getattr(info, "previous_close", None) or (t.info or {}).get("previousClose")
                    
                    if current is None or math.isnan(current):
                        # Fallback: History
                        hist = t.history(period="5d")
                        if not hist.empty and len(hist) >= 2:
                            current = float(hist["Close"].iloc[-1])
                            prev = float(hist["Close"].iloc[-2])
                            
                    if current is not None and not math.isnan(current):
                        break
                except Exception as e:
                    print(f"[YF] Sector perf attempt {attempt+1} failed for {ticker}: {e}")
                    if attempt < 2:
                        time.sleep((1.0 * (2 ** attempt)) + (random.random() * 0.2))
            
            if not current or math.isnan(current) or not prev:
                continue
            change_abs = round(current - prev, 2)
            change_pct = round((change_abs / prev) * 100, 2)
            sectors.append({
                "name": name,
                "ticker": ticker,
                "value": round(current, 2),
                "change_abs": change_abs,
                "change_pct": change_pct,
            })
        except Exception:
            continue

    result = {
        "sectors": sorted(sectors, key=lambda x: abs(x["change_pct"]), reverse=True),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    _sector_cache = {"data": result, "ts": now}
    return result

class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str

@app.post("/register")
def register_endpoint(req: RegisterRequest):
    with get_session() as session:
        existing = session.query(User).filter_by(username=req.username.lower()).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        from database import create_user
        user = create_user(session, req.username, req.password, req.display_name)
        if not user:
            raise HTTPException(status_code=500, detail="Failed to create user")
        
        return {"user_id": user.id, "username": user.username, "display_name": user.display_name}

# ---------------------------------------------------------------------------
# v1 Market Intelligence Routes (Firecrawl + fallback scraping, 15-min cache)
# ---------------------------------------------------------------------------

from services.scraper import (
    fetch_market_pulse,
    fetch_momentum,
    fetch_macro_alternatives,
    fetch_institutional_flow,
)

@app.get("/api/v1/market/pulse")
def market_pulse_endpoint():
    """Market indices + advance/decline breadth ratio."""
    try:
        return fetch_market_pulse()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market pulse unavailable: {e}")

@app.get("/api/v1/market/momentum")
def market_momentum_endpoint():
    """Bullish/bearish MA crossover lists with sparkline coordinate arrays."""
    try:
        return fetch_momentum()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Momentum data unavailable: {e}")

@app.get("/api/v1/market/macro-alternatives")
def market_macro_alternatives_endpoint():
    """Brent, Gold, USD/INR, US 10Y, India VIX, ETFs."""
    try:
        return fetch_macro_alternatives()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Macro data unavailable: {e}")

@app.get("/api/v1/market/institutional-flow")
def market_institutional_flow_endpoint():
    """Top 10 mutual funds by 1-year return (leaderboard)."""
    try:
        return fetch_institutional_flow()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Institutional flow unavailable: {e}")

# ---------------------------------------------------------------------------
# Unified dashboard endpoint — returns all 4 market intelligence feeds in one
# call. Fetchers are cached (15-min TTL) so this is fast after first load.
# ---------------------------------------------------------------------------

from datetime import datetime as _dt
import concurrent.futures as _cf

@app.get("/api/v1/market/dashboard")
def market_dashboard_endpoint():
    """All four market intelligence feeds in a single round-trip."""
    try:
        with _cf.ThreadPoolExecutor(max_workers=4) as ex:
            fp = ex.submit(fetch_market_pulse)
            fm = ex.submit(fetch_momentum)
            fa = ex.submit(fetch_macro_alternatives)
            fi = ex.submit(fetch_institutional_flow)
            return {
                "pulse":         fp.result(timeout=25),
                "momentum":      fm.result(timeout=25),
                "macro":         fa.result(timeout=25),
                "institutional": fi.result(timeout=25),
                "fetched_at":    _dt.utcnow().isoformat(),
            }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Dashboard fetch failed: {e}")
