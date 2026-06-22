# API Contract Fix Report — FIX-A1

**Date:** 2026-06-16  
**Scope:** `backend/schemas/portfolio.py` + `backend/routers/portfolio.py`  
**Severity:** MEDIUM  
**Status:** FIXED ✓

---

## Issue

The `Portfolio` SQLAlchemy model exposes two nullable columns:
- `target_price` (Float, nullable=True)
- `purchase_date` (String, nullable=True)

Neither `PortfolioAddRequest` nor `PortfolioUpdateRequest` included these fields, so clients had no way to set them via the API. The router also did not pass them when constructing or updating `Portfolio` ORM objects.

---

## Schema Changes — `backend/schemas/portfolio.py`

### PortfolioAddRequest

**Before:**
```python
class PortfolioAddRequest(BaseModel):
    user_id: int
    ticker: str
    exchange: str = "NSE"
    company_name: str
    shares: float
    buy_price: float
    group_name: str = "holdings"
```

**After:**
```python
class PortfolioAddRequest(BaseModel):
    user_id: int
    ticker: str
    exchange: str = "NSE"
    company_name: str
    shares: float
    buy_price: float
    group_name: str = "holdings"
    target_price: Optional[float] = None
    purchase_date: Optional[str] = None
```

### PortfolioUpdateRequest

**Before:**
```python
class PortfolioUpdateRequest(BaseModel):
    user_id: int
    ticker: str
    shares: float
    buy_price: float
```

**After:**
```python
class PortfolioUpdateRequest(BaseModel):
    user_id: int
    ticker: str
    shares: float
    buy_price: float
    target_price: Optional[float] = None
    purchase_date: Optional[str] = None
```

---

## Router Changes — `backend/routers/portfolio.py`

### `portfolio_add_endpoint` (POST /portfolio, POST /portfolio/add)

The `Portfolio(...)` constructor call was missing `target_price` and `purchase_date`.

**Before:**
```python
new_holding = Portfolio(
    user_id=req.user_id,
    ticker=ticker,
    company_name=req.company_name,
    shares=req.shares,
    buy_price=req.buy_price,
    group_name="holdings",
)
```

**After:**
```python
new_holding = Portfolio(
    user_id=req.user_id,
    ticker=ticker,
    company_name=req.company_name,
    shares=req.shares,
    buy_price=req.buy_price,
    group_name="holdings",
    target_price=req.target_price,
    purchase_date=req.purchase_date,
)
```

### `portfolio_update_endpoint` (PUT /portfolio/update)

The update block only mutated `shares` and `buy_price`. Added conditional assignment for `target_price` and `purchase_date` (only overwrite if the client sends a non-None value, preserving existing values when the client omits them).

**Before:**
```python
holding.shares = req.shares
holding.buy_price = req.buy_price
session.commit()
```

**After:**
```python
holding.shares = req.shares
holding.buy_price = req.buy_price
if req.target_price is not None:
    holding.target_price = req.target_price
if req.purchase_date is not None:
    holding.purchase_date = req.purchase_date
session.commit()
```

---

## Verification Result

```
ADD target_price: 3500.0 | purchase_date: 2026-01-01
UPDATE target_price: 3600.0 | purchase_date: 2026-02-15
UPDATE without optional fields — target_price: None | purchase_date: None
```

- Schema parses correctly with and without the optional fields.
- Optional fields default to `None` when omitted (backward-compatible).
- No import changes needed (`Optional` was already imported).

---

## Out-of-Scope Observations

1. **`portfolio_add_endpoint` response payload** does not include `target_price` or `purchase_date` in its return dict (lines 951–964). This is a cosmetic gap — the data is stored correctly, but the add response doesn't echo back these fields. A follow-up could add them to the response for consistency with what `GET /portfolio/{user_id}` already returns.

2. **`portfolio_update_endpoint` response payload** similarly omits `target_price` and `purchase_date` from its return dict (lines 1034–1047). Same pattern as above.

3. **No service layer involved** — the portfolio add/update logic lives directly in the router handlers, not in a separate `portfolio_service.py`. This is a minor architectural gap (business logic in a controller, which AGENTS.md §3.1 flags as FORBIDDEN for non-trivial logic), but it is pre-existing and out of scope for this fix.
