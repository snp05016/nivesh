"""Portfolio, trading, and analysis Pydantic request schemas."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator

_ALLOWED_TX_TYPES = {"BUY", "SELL", "SPLIT", "BONUS", "DIVIDEND"}


class AnalyzeRequest(BaseModel):
    ticker: str
    exchange: str = "NSE"
    user_id: Optional[int] = None
    deep_scan: bool = False
    scan_type: str = "standard"   # "standard" | "extreme"
    language: Optional[str] = None
    debate_rounds: Optional[int] = None
    risk_tolerance: Optional[str] = None

    @field_validator("ticker")
    def validate_ticker(cls, v):
        import re
        v = v.strip().upper()
        # Hyphen allowed: NSE symbols such as BAJAJ-AUTO
        if not re.match(r'^[A-Za-z0-9&\-\.]{1,20}$', v):
            raise ValueError("Ticker contains invalid characters")
        return v

    @field_validator("exchange")
    def validate_exchange(cls, v):
        if v not in ("NSE", "BSE"):
            raise ValueError("Exchange must be NSE or BSE")
        return v


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
    shares: float = Field(gt=0, description="Number of shares (must be > 0)")
    buy_price: float = Field(gt=0, description="Price per share (must be > 0)")
    group_name: str = "holdings"
    target_price: Optional[float] = None
    purchase_date: Optional[str] = None
    notes: Optional[str] = None
    transaction_type: str = "BUY"
    is_virtual: bool = False  # paper trade

    @field_validator("transaction_type")
    @classmethod
    def validate_transaction_type(cls, v: str) -> str:
        upper = v.upper()
        if upper not in _ALLOWED_TX_TYPES:
            raise ValueError(f"transaction_type must be one of {sorted(_ALLOWED_TX_TYPES)}")
        return upper


class PortfolioRemoveRequest(BaseModel):
    user_id: int
    ticker: str


class PortfolioUpdateRequest(BaseModel):
    user_id: int
    ticker: str
    shares: float
    buy_price: float
    target_price: Optional[float] = None
    purchase_date: Optional[str] = None


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
    tickers: list[str] = Field(min_length=1, max_length=20)
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
