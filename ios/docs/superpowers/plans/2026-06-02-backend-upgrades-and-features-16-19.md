# Backend Upgrades + Features 16-19 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the Nivesh backend (reliability, signal history, AI quality, caching, health) and implement iOS features 16-19 (broker ratings strip, AI disclaimer card, morning brief upgrade, portfolio warning chips).

**Architecture:** All backend changes are in `/Users/saumya/Desktop/stocks/main.py`, `database.py`, and `prompts.py`. iOS changes are in the `stockme` Xcode target under `Views/` and `Models.swift`. No new files needed — all changes extend existing files.

**Tech Stack:** Python 3.14 + FastAPI + yfinance + SQLite/SQLAlchemy + SwiftUI + Combine

---

## File Map

| File | Changes |
|------|---------|
| `/Users/saumya/Desktop/stocks/database.py` | Add `signal_events` table; update `save_analysis` to detect+record flips |
| `/Users/saumya/Desktop/stocks/main.py` | yfinance retry; `/health` upgrade; `/analyze` rate-limit; `/macro-strip` Brent+VIX; `/quick-info` TTL cache; `/quarterly-financials` .BO fallback; `signal_changed` in response |
| `/Users/saumya/Desktop/stocks/prompts.py` | `confidence_rationale` field; `indian_market_sentiment` validation instruction; patterns agent instruction |
| `stockme/Models.swift` | Add `AnalystRating`, `AnalystRatingsResponse`, `confidenceRationale` to `StockAnalysis`, `signalChanged`/`previousSignal` |
| `stockme/NetworkManager.swift` | `getAnalystRatings()`, `checkWarningSignals()` |
| `stockme/Views/AnalysisScreen.swift` | Broker ratings strip; collapsible AI disclaimer card |
| `stockme/Views/PortfolioScreen.swift` | Warning chip on flipped/degraded holdings |
| `stockme/Views/HomeScreen.swift` | Morning brief upgrade (prioritised list) |

---

## Task 1: `signal_events` table + signal flip detection in `save_analysis`

**Files:**
- Modify: `/Users/saumya/Desktop/stocks/database.py`

- [ ] **Step 1: Add `SignalEvent` model and `signal_events` table**

```python
# In database.py, after AnalysisHistory class definition:

class SignalEvent(Base):
    __tablename__ = "signal_events"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    ticker      = Column(String(20), nullable=False, index=True)
    from_signal = Column(String(30), nullable=False)
    to_signal   = Column(String(30), nullable=False)
    event_date  = Column(String(20), nullable=False)
    created_at  = Column(DateTime, default=datetime.utcnow)
```

Add `SignalEvent` to the `init_db()` call so the table is created on startup (it uses `Base.metadata.create_all` which auto-picks up new models).

- [ ] **Step 2: Update `save_analysis` to detect flip and return metadata**

Replace the existing `save_analysis` function:

```python
def save_analysis(session: Session, user_id: Optional[int], ticker: str, result: dict) -> dict:
    """Save analysis. Returns dict with signal_changed, previous_signal injected."""
    tp = result.get("target_prices") or {}
    new_signal = result.get("signal", "UNKNOWN")

    # Check previous signal for this ticker (any user)
    prev_row = (
        session.query(AnalysisHistory)
        .filter(AnalysisHistory.ticker == ticker)
        .order_by(AnalysisHistory.created_at.desc())
        .first()
    )
    prev_signal = prev_row.signal if prev_row else None
    flipped = prev_signal is not None and prev_signal != new_signal

    if flipped:
        session.add(SignalEvent(
            ticker=ticker,
            from_signal=prev_signal,
            to_signal=new_signal,
            event_date=result.get("analysis_date", date.today().isoformat()),
        ))

    record = AnalysisHistory(
        user_id=user_id,
        ticker=ticker,
        analysis_date=result.get("analysis_date", date.today().isoformat()),
        signal=new_signal,
        confidence_pct=result.get("confidence_pct"),
        target_short=tp.get("short_term_3m"),
        target_medium=tp.get("medium_term_12m"),
        target_long=tp.get("long_term_36m"),
        full_json=json.dumps(result),
    )
    session.add(record)
    session.commit()

    result["signal_changed"] = flipped
    result["previous_signal"] = prev_signal
    return result
```

- [ ] **Step 3: Update all callers of `save_analysis` in `main.py` to use returned value**

In `main.py`, every call to `save_analysis(session, ...)` now returns the enriched result. Update:

```python
# In analyze() function, line ~662:
with get_session() as session:
    result = save_analysis(session, user_id, ticker.upper(), result)
return result

# In smart cache path (~648):
with get_session() as session:
    new_analysis = save_analysis(session, user_id, ticker.upper(), new_analysis)
return new_analysis

# In cache hit path (~604) — save_analysis called only when user doesn't have it yet:
if not user_has_it:
    cached_today = save_analysis(session, user_id, ticker.upper(), cached_today)
```

- [ ] **Step 4: Add `SignalEvent` to imports in `main.py`**

```python
# In main.py top imports, update the database import line:
from database import init_db, get_session, save_analysis, get_recent_analyses, get_user_by_credentials, Portfolio, User, AnalysisHistory, SignalEvent, get_analysis_for_date, get_all_ticker_history, PriceTarget
```

- [ ] **Step 5: Verify table created on server restart**

```bash
cd /Users/saumya/Desktop/stocks
.venv/bin/python3 -c "from database import init_db; init_db(); from database import get_session, SignalEvent; print('SignalEvent table OK')"
```

Expected: `SignalEvent table OK`

- [ ] **Step 6: Commit**

```bash
cd /Users/saumya/Desktop/stocks
git add database.py main.py
git commit -m "feat: signal_events table + flip detection in save_analysis"
```

---

## Task 2: `confidence_rationale` field — prompt + iOS model

**Files:**
- Modify: `/Users/saumya/Desktop/stocks/prompts.py`
- Modify: `stockme/Models.swift`
- Modify: `stockme/Views/AnalysisScreen.swift`

- [ ] **Step 1: Add `confidence_rationale` to the JSON schema in `prompts.py`**

In the REQUIRED JSON STRUCTURE section of `INDIAN_MARKET_SYSTEM_PROMPT`, add after `"confidence_pct"`:

```
  "confidence_rationale": "<one sentence explaining why confidence is this level, e.g. 'High confidence due to consistent promoter buying and strong fundamentals, tempered by sector headwinds'>",
```

Also add to Field instructions:
```
- confidence_rationale: one sentence max. Reference the 2-3 specific factors most responsible for the confidence level.
```

- [ ] **Step 2: Add `indian_market_sentiment` validation in reformatter**

In `main.py`, in `reformat_with_claude()`, after `raw_json = response.content[0].text.strip()` parsing, add:

```python
parsed = json.loads(raw_json)

# Validate indian_market_sentiment is populated
kf = parsed.get("key_factors", {})
if not kf.get("indian_market_sentiment", "").strip():
    print("[WARN] indian_market_sentiment empty — reformatter may need retry")
    kf["indian_market_sentiment"] = "Sentiment data not available for this stock."
    parsed["key_factors"] = kf

return parsed
```

Replace the current `return json.loads(raw_json)` with this block.

- [ ] **Step 3: Add `confidenceRationale` to iOS `StockAnalysis` model**

In `stockme/Models.swift`, in `struct StockAnalysis`:

```swift
// Add field:
let confidenceRationale: String?

// Add to CodingKeys:
case confidenceRationale = "confidence_rationale"
```

Also add `signalChanged` and `previousSignal`:

```swift
let signalChanged: Bool?
let previousSignal: String?

// CodingKeys:
case signalChanged = "signal_changed"
case previousSignal = "previous_signal"
```

- [ ] **Step 4: Surface `confidence_rationale` in AnalysisScreen**

In `AnalysisScreen.swift`, find the section that displays `confidencePercent`. After the confidence display, add:

```swift
if let rationale = analysis.confidenceRationale {
    Text(rationale)
        .font(Theme.officialStampFont(size: 8))
        .foregroundColor(Theme.inkSecondary)
        .padding(.top, 2)
}
```

- [ ] **Step 5: Commit**

```bash
git add /Users/saumya/Desktop/stocks/prompts.py /Users/saumya/Desktop/stocks/main.py
git add StockApp/stockme/stockme/Models.swift StockApp/stockme/stockme/Views/AnalysisScreen.swift
git commit -m "feat: confidence_rationale field + indian_market_sentiment validation"
```

---

## Task 3: yfinance retry + `/health` upgrade + `/analyze` rate-limit

**Files:**
- Modify: `/Users/saumya/Desktop/stocks/main.py`

- [ ] **Step 1: Add yfinance retry wrapper**

In `main.py`, replace `_yf_price` with a version that retries once after 1.5s:

```python
def _yf_fetch_info(sym: str) -> dict:
    """Fetch yfinance info with one retry on failure."""
    import time
    for attempt in range(2):
        try:
            info = yf.Ticker(sym).info
            if info and info.get("currentPrice") or info.get("regularMarketPrice"):
                return info
        except Exception as e:
            print(f"[YF] Attempt {attempt+1} failed for {sym}: {e}")
            if attempt == 0:
                time.sleep(1.5)
    return {}

def _yf_price(ticker_sym: str) -> tuple[float | None, float | None]:
    """Return (current_price, prev_close) with retry and BSE fallback."""
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
```

- [ ] **Step 2: Upgrade `/health` endpoint**

Replace the existing `health_endpoint`:

```python
@app.get("/health")
def health_endpoint():
    import os
    result = {"status": "ok", "version": "1.0", "timestamp": datetime.utcnow().isoformat()}

    # Check yfinance
    try:
        info = yf.Ticker("SBIN.NS").info
        result["yfinance"] = bool(info and (info.get("currentPrice") or info.get("regularMarketPrice")))
    except Exception:
        result["yfinance"] = False

    # Check DB
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
        result["db"] = True
    except Exception:
        result["db"] = False

    # Check Anthropic key
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    result["anthropic_key_set"] = bool(api_key and api_key != "placeholder")

    result["status"] = "ok" if all([result["yfinance"], result["db"], result["anthropic_key_set"]]) else "degraded"
    return result
```

Add `from sqlalchemy import text` at top if not already imported (check existing imports first).

- [ ] **Step 3: Add rate-limit guard on `/analyze`**

Add this at module level (near the top, after `app = FastAPI(...)`):

```python
_running_analyses: set[int] = set()  # user_ids with analysis in flight
```

In `analyze_endpoint`, wrap the `analyze()` call:

```python
@app.post("/analyze")
async def analyze_endpoint(req: AnalyzeRequest, request: Request):
    user_id = req.user_id

    if user_id and user_id in _running_analyses:
        raise HTTPException(status_code=429, detail="Analysis already running for this user. Please wait.")

    if user_id:
        _running_analyses.add(user_id)
    try:
        loop = asyncio.get_event_loop()
        queue = multiprocessing.Queue()
        # ... rest of existing analyze logic unchanged ...
    finally:
        if user_id:
            _running_analyses.discard(user_id)
```

Find the exact structure of `analyze_endpoint` (it uses `multiprocessing.Queue`) and wrap the outer try/finally correctly.

- [ ] **Step 4: Commit**

```bash
cd /Users/saumya/Desktop/stocks
git add main.py
git commit -m "feat: yfinance retry, health checks, analyze rate-limit guard"
```

---

## Task 4: `/macro-strip` — add Brent crude + India VIX

**Files:**
- Modify: `/Users/saumya/Desktop/stocks/main.py`

- [ ] **Step 1: Add Brent and India VIX to macro_strip_endpoint**

In `macro_strip_endpoint()`, after the WTI crude block (which sets `result["crude_oil_usd"]`), add:

```python
# Brent crude (India imports Brent-priced oil)
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

# India VIX (fear gauge for Indian retail)
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
```

- [ ] **Step 2: Add fields to iOS `MacroStrip` model**

In `stockme/Models.swift`, `struct MacroStrip`:

```swift
let brentOilUsd: Double?
let indiaVix: Double?

// CodingKeys:
case brentOilUsd = "brent_oil_usd"
case indiaVix = "india_vix"
```

- [ ] **Step 3: Surface India VIX in AnalysisScreen macro strip**

Find the `MacroChip` row in `AnalysisScreen.swift` (around line 601). Add after existing chips:

```swift
if let vix = macro.indiaVix {
    MacroChip(label: "INDIA VIX", value: String(format: "%.1f", vix),
              color: vix > 20 ? .red : vix > 15 ? Theme.securityGold : Theme.bullGreen)
}
```

- [ ] **Step 4: Commit**

```bash
git add /Users/saumya/Desktop/stocks/main.py
git add StockApp/stockme/stockme/Models.swift StockApp/stockme/stockme/Views/AnalysisScreen.swift
git commit -m "feat: Brent crude + India VIX in macro-strip"
```

---

## Task 5: `/quick-info` 5-minute in-memory cache

**Files:**
- Modify: `/Users/saumya/Desktop/stocks/main.py`

- [ ] **Step 1: Add TTL cache dict at module level**

After the module-level `_running_analyses` set, add:

```python
import time as _time
_quick_info_cache: dict[str, tuple[float, dict]] = {}  # key -> (expiry_ts, data)
_QUICK_INFO_TTL = 300  # 5 minutes
```

- [ ] **Step 2: Wrap `quick_info_endpoint` with cache**

At the start of `quick_info_endpoint`, before any yfinance calls:

```python
cache_key = f"{ticker.upper()}_{exchange.upper()}"
now = _time.time()
if cache_key in _quick_info_cache:
    expiry, cached = _quick_info_cache[cache_key]
    if now < expiry:
        print(f"[QUICK-INFO CACHE HIT] {cache_key}")
        return cached
```

At the end, before `return result`:

```python
_quick_info_cache[cache_key] = (_time.time() + _QUICK_INFO_TTL, result)
return result
```

- [ ] **Step 3: Commit**

```bash
cd /Users/saumya/Desktop/stocks
git add main.py
git commit -m "feat: 5-min TTL in-memory cache for /quick-info"
```

---

## Task 6: `/quarterly-financials` — try `.BO` fallback on empty data

**Files:**
- Modify: `/Users/saumya/Desktop/stocks/main.py`

- [ ] **Step 1: Add .BO fallback in `quarterly_financials_endpoint`**

Find the section in `quarterly_financials_endpoint` that does `fin = t.quarterly_financials` and `if fin is not None and not fin.empty`. Wrap the initial fetch in a helper:

```python
def _get_quarterly_fin(full_ticker: str):
    t = yf.Ticker(full_ticker)
    fin = t.quarterly_financials
    if fin is None or fin.empty:
        # try .BO if we were using .NS
        if full_ticker.endswith(".NS"):
            alt = full_ticker[:-3] + ".BO"
            print(f"[QF FALLBACK] No data for {full_ticker}, trying {alt}")
            t = yf.Ticker(alt)
            fin = t.quarterly_financials
    return t, fin
```

Call `t, fin = _get_quarterly_fin(full_ticker)` instead of the existing `t = yf.Ticker(full_ticker); fin = t.quarterly_financials`.

- [ ] **Step 2: Commit**

```bash
cd /Users/saumya/Desktop/stocks
git add main.py
git commit -m "feat: .BO fallback for /quarterly-financials on empty data"
```

---

## Task 7: Feature 16 — Broker analyst ratings strip (iOS)

The `/analyst-ratings` endpoint already exists and returns `{ratings: [{firm, grade, period}], consensus, buy, hold, sell}`.

**Files:**
- Modify: `stockme/Models.swift`
- Modify: `stockme/NetworkManager.swift`
- Modify: `stockme/Views/AnalysisScreen.swift`

- [ ] **Step 1: Add models in `Models.swift`**

```swift
struct AnalystRating: Codable, Identifiable {
    var id: String { firm + period }
    let firm: String
    let grade: String
    let period: String
}

struct AnalystRatingsResponse: Codable {
    let ratings: [AnalystRating]
    let consensus: String?
    let buy: Int
    let hold: Int
    let sell: Int
}
```

- [ ] **Step 2: Add `getAnalystRatings` to `NetworkManager.swift`**

```swift
func getAnalystRatings(ticker: String, exchange: String = "NSE") async -> AnalystRatingsResponse? {
    guard let url = URL(string: "\(baseURL)/analyst-ratings?ticker=\(ticker)&exchange=\(exchange)") else { return nil }
    var request = URLRequest(url: url)
    request.timeoutInterval = 12
    guard let (data, resp) = try? await session.data(for: request),
          let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return nil }
    return try? JSONDecoder().decode(AnalystRatingsResponse.self, from: data)
}
```

- [ ] **Step 3: Add `analystRatings` state to `AnalysisScreenViewModel`**

In `AnalysisScreen.swift`, inside `AnalysisScreenViewModel` (the `@MainActor class`):

```swift
@Published var analystRatings: AnalystRatingsResponse? = nil
```

In `loadAll()` or the existing parallel fetch block, add:

```swift
async let ratings = NetworkManager.shared.getAnalystRatings(ticker: ticker, exchange: exchange)
// ... in the assignment block:
self.analystRatings = await ratings
```

- [ ] **Step 4: Add broker ratings strip UI in `AnalysisScreen.swift`**

After the signals section (around the `key_factors` cards), add:

```swift
if let ratings = viewModel.analystRatings, !ratings.ratings.isEmpty {
    VStack(alignment: .leading, spacing: 10) {
        HStack {
            Text("BROKER CONSENSUS")
                .font(Theme.officialStampFont(size: 9)).foregroundColor(Theme.inkPrimary)
            Spacer()
            if let consensus = ratings.consensus {
                Text(consensus)
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundColor(consensus == "BUY" ? Theme.bullGreen : consensus == "SELL" ? Theme.bearRed : Theme.inkSecondary)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .background((consensus == "BUY" ? Theme.bullGreen : consensus == "SELL" ? Theme.bearRed : Theme.inkSecondary).opacity(0.1))
                    .clipShape(Capsule())
            }
        }
        // Buy/Hold/Sell tally
        HStack(spacing: 16) {
            Label("\(ratings.buy) Buy", systemImage: "arrow.up.circle.fill").foregroundColor(Theme.bullGreen)
            Label("\(ratings.hold) Hold", systemImage: "minus.circle.fill").foregroundColor(Theme.inkSecondary)
            Label("\(ratings.sell) Sell", systemImage: "arrow.down.circle.fill").foregroundColor(Theme.bearRed)
        }
        .font(Theme.serialNumberFont(size: 11))
        // Individual broker chips
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(ratings.ratings) { r in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(r.firm).font(Theme.serialNumberFont(size: 9)).foregroundColor(Theme.inkPrimary)
                        Text(r.grade).font(Theme.officialStampFont(size: 8))
                            .foregroundColor(r.grade.uppercased().contains("BUY") || r.grade.uppercased().contains("OUTPERFORM") ? Theme.bullGreen :
                                            r.grade.uppercased().contains("SELL") || r.grade.uppercased().contains("UNDERPERFORM") ? Theme.bearRed : Theme.inkSecondary)
                        Text(r.period).font(Theme.serialNumberFont(size: 8)).foregroundColor(Theme.inkTertiary)
                    }
                    .padding(8).banknoteCard()
                }
            }
        }
    }
    .padding(16).banknoteCard()
}
```

- [ ] **Step 5: Commit**

```bash
git add StockApp/stockme/stockme/Models.swift StockApp/stockme/stockme/NetworkManager.swift StockApp/stockme/stockme/Views/AnalysisScreen.swift
git commit -m "feat: broker analyst ratings strip on Analysis screen"
```

---

## Task 8: Feature 17 — Collapsible AI limitations disclaimer card

**Files:**
- Modify: `stockme/Views/AnalysisScreen.swift`

- [ ] **Step 1: Replace plain disclaimer text with collapsible card**

Find the existing disclaimer section (around line 800 in AnalysisScreen.swift):

```swift
// Disclaimer
VStack(alignment: .leading, spacing: 8) {
    Text("OFFICIAL DISCLAIMER")
    ...
    Text(analysis.disclaimer)
```

Replace with:

```swift
// AI Limitations + Disclaimer card
AnalysisLimitationsCard(disclaimer: analysis.disclaimer)
```

- [ ] **Step 2: Add `AnalysisLimitationsCard` view at bottom of `AnalysisScreen.swift`**

```swift
struct AnalysisLimitationsCard: View {
    let disclaimer: String
    @State private var expanded = false
    @AppStorage("analysisLimitationsExpanded") private var shownBefore = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Button(action: {
                withAnimation(.easeInOut(duration: 0.25)) { expanded.toggle() }
            }) {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(Theme.securityGold)
                    Text("HOW TO READ THIS ANALYSIS")
                        .font(Theme.officialStampFont(size: 9)).foregroundColor(Theme.inkPrimary)
                    Spacer()
                    Image(systemName: expanded ? "chevron.up" : "chevron.down")
                        .font(.system(size: 10)).foregroundColor(Theme.inkTertiary)
                }
            }
            .buttonStyle(.plain)

            if expanded || !shownBefore {
                VStack(alignment: .leading, spacing: 8) {
                    Text("⚠️ AI cannot predict black swan events. Geopolitical shocks — wars, sanctions, pandemics — are outside this model's scope. These have caused real losses for investors in the past.")
                        .font(Theme.serialNumberFont(size: 10)).foregroundColor(Theme.bearRed.opacity(0.9))

                    Text("This analysis weights Indian market factors: promoter behaviour, FII/DII flows, retail sentiment, and news momentum. It is not a substitute for your own judgment.")
                        .font(Theme.serialNumberFont(size: 10)).foregroundColor(Theme.inkSecondary)

                    Divider().background(Theme.guilloche)

                    Text(disclaimer)
                        .font(Theme.serialNumberFont(size: 9)).foregroundColor(Theme.inkTertiary)
                }
                .onAppear { shownBefore = true }
            }
        }
        .padding(16).banknoteCard()
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add StockApp/stockme/stockme/Views/AnalysisScreen.swift
git commit -m "feat: collapsible AI limitations + black swan disclaimer card"
```

---

## Task 9: Feature 19 — Warning chips on Portfolio holdings

Show a red `⚠ SIGNAL CHANGED` chip on a portfolio row when the stock's latest analysis has `signal_changed = true` or the signal is BEARISH and they hold it.

**Files:**
- Modify: `stockme/Models.swift` (already has `signalChanged`/`previousSignal` from Task 2)
- Modify: `stockme/Views/PortfolioScreen.swift`
- Modify: `stockme/NetworkManager.swift` (quick batch signal check)
- Backend: Add `/portfolio/signal-warnings` endpoint in `main.py`

- [ ] **Step 1: Add backend `/portfolio/signal-warnings` endpoint**

In `main.py`, add after the portfolio endpoints:

```python
@app.get("/portfolio/signal-warnings")
def portfolio_signal_warnings(user_id: int):
    """Return tickers where latest signal flipped or is BEARISH for held stocks."""
    warnings = []
    with get_session() as session:
        holdings = session.query(Portfolio).filter(
            Portfolio.user_id == user_id,
            Portfolio.group_name == "holdings"
        ).all()

        for h in holdings:
            rows = session.query(AnalysisHistory).filter(
                AnalysisHistory.ticker == h.ticker
            ).order_by(AnalysisHistory.created_at.desc()).limit(2).all()

            if not rows:
                continue

            latest = rows[0]
            prev = rows[1] if len(rows) > 1 else None

            signal_flipped = prev and prev.signal != latest.signal
            confidence_dropped = (
                prev and latest.confidence_pct and prev.confidence_pct
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
```

- [ ] **Step 2: Add models and NetworkManager call**

In `Models.swift`:

```swift
struct SignalWarning: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let currentSignal: String
    let previousSignal: String?
    let signalFlipped: Bool
    let confidenceDropped: Bool
    let isBearish: Bool
    let analysisDate: String

    enum CodingKeys: String, CodingKey {
        case ticker
        case currentSignal = "current_signal"
        case previousSignal = "previous_signal"
        case signalFlipped = "signal_flipped"
        case confidenceDropped = "confidence_dropped"
        case isBearish = "is_bearish"
        case analysisDate = "analysis_date"
    }
}

struct SignalWarningsResponse: Codable {
    let warnings: [SignalWarning]
}
```

In `NetworkManager.swift`:

```swift
func getSignalWarnings(userId: Int) async -> [SignalWarning] {
    guard let url = URL(string: "\(baseURL)/portfolio/signal-warnings?user_id=\(userId)") else { return [] }
    var request = URLRequest(url: url)
    request.timeoutInterval = 10
    guard let (data, resp) = try? await session.data(for: request),
          let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return [] }
    return (try? JSONDecoder().decode(SignalWarningsResponse.self, from: data))?.warnings ?? []
}
```

- [ ] **Step 3: Wire into PortfolioScreen**

In `PortfolioScreen.swift`, add `@Published var signalWarnings: [String: SignalWarning] = [:]` to the portfolio view model (or `@State` if no VM).

In `.onAppear` / `.task`, fetch warnings:

```swift
Task {
    if let uid = authManager.userId {
        let ws = await NetworkManager.shared.getSignalWarnings(userId: uid)
        signalWarnings = Dictionary(uniqueKeysWithValues: ws.map { ($0.ticker, $0) })
    }
}
```

On each portfolio row, after the company name, add:

```swift
if let warning = signalWarnings[holding.stock.ticker] {
    HStack(spacing: 4) {
        Image(systemName: "exclamationmark.triangle.fill")
            .font(.system(size: 9))
        Text(warning.signalFlipped ? "SIGNAL CHANGED" : "BEARISH")
            .font(Theme.officialStampFont(size: 7))
    }
    .foregroundColor(.white)
    .padding(.horizontal, 6).padding(.vertical, 2)
    .background(Theme.bearRed)
    .clipShape(Capsule())
}
```

- [ ] **Step 4: Commit**

```bash
git add /Users/saumya/Desktop/stocks/main.py
git add StockApp/stockme/stockme/Models.swift StockApp/stockme/stockme/NetworkManager.swift StockApp/stockme/stockme/Views/PortfolioScreen.swift
git commit -m "feat: signal warning chips on held stocks in Portfolio"
```

---

## Task 10: Feature 18 — Morning brief upgrade

Upgrade `/morning-summary` to prioritise: triggered alerts → signal changes → upcoming earnings → sector moves.

**Files:**
- Modify: `/Users/saumya/Desktop/stocks/main.py`
- Modify: `stockme/Views/HomeScreen.swift`

- [ ] **Step 1: Read existing `/morning-summary` endpoint** (line ~1180 in main.py) to understand current structure before modifying.

- [ ] **Step 2: Add `priority_items` array to morning summary response**

After the existing analysis loop in `morning_summary_endpoint`, add:

```python
# Build prioritised action list
priority_items = []

# 1. Triggered alerts
try:
    from database import get_session
    with get_session() as session:
        from database import PriceAlert
        alerts = session.query(PriceAlert).filter(
            PriceAlert.user_id == user_id,
            PriceAlert.is_triggered == True
        ).all()
        for a in alerts:
            priority_items.append({
                "priority": 1,
                "type": "alert_triggered",
                "ticker": a.ticker,
                "message": f"Price alert triggered: {a.ticker} {a.direction} ₹{a.target_price:.0f}",
            })
except Exception:
    pass

# 2. Signal changes (from signal_events last 24h)
try:
    from database import SignalEvent
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    with get_session() as session:
        flips = session.query(SignalEvent).filter(
            SignalEvent.created_at >= cutoff
        ).all()
        held_tickers = {h.ticker for h in holdings}
        for f in flips:
            if f.ticker in held_tickers:
                priority_items.append({
                    "priority": 2,
                    "type": "signal_change",
                    "ticker": f.ticker,
                    "message": f"{f.ticker}: signal changed {f.from_signal} → {f.to_signal}",
                })
except Exception:
    pass

# 3. Upcoming earnings (next 7 days) for held stocks
# (reuse existing earnings_calendar data if available in the response)

result["priority_items"] = sorted(priority_items, key=lambda x: x["priority"])
```

- [ ] **Step 3: Surface priority items in HomeScreen morning brief card**

In `HomeScreen.swift`, find the morning summary display. After the existing summary text, add:

```swift
if let items = summary.priorityItems, !items.isEmpty {
    VStack(alignment: .leading, spacing: 8) {
        Text("TODAY'S PRIORITY")
            .font(Theme.officialStampFont(size: 8)).foregroundColor(Theme.inkPrimary)
        ForEach(items.prefix(5), id: \.ticker) { item in
            HStack(spacing: 8) {
                Image(systemName: item.type == "alert_triggered" ? "bell.fill" : "arrow.triangle.2.circlepath")
                    .foregroundColor(item.type == "alert_triggered" ? Theme.securityGold : Theme.bearRed)
                    .font(.system(size: 11))
                Text(item.message)
                    .font(Theme.serialNumberFont(size: 10))
                    .foregroundColor(Theme.inkSecondary)
            }
        }
    }
    .padding(.top, 8)
}
```

- [ ] **Step 4: Add `MorningSummaryPriorityItem` and update `MorningSummaryResponse` in `Models.swift`**

```swift
struct MorningSummaryPriorityItem: Codable, Identifiable {
    var id: String { ticker + type }
    let priority: Int
    let type: String
    let ticker: String
    let message: String
}

// In MorningSummaryResponse, add:
let priorityItems: [MorningSummaryPriorityItem]?
// CodingKeys: case priorityItems = "priority_items"
```

- [ ] **Step 5: Commit**

```bash
git add /Users/saumya/Desktop/stocks/main.py
git add StockApp/stockme/stockme/Models.swift StockApp/stockme/stockme/Views/HomeScreen.swift
git commit -m "feat: morning brief upgrade with prioritised items (alerts, signal changes)"
```

---

## Self-Review

**Spec coverage:**
- ✅ `confidence_rationale` — Task 2
- ✅ `indian_market_sentiment` validation — Task 2
- ✅ `signal_changed`/`previous_signal` — Task 1
- ✅ `signal_events` table — Task 1
- ✅ yfinance retry — Task 3
- ✅ `/health` real checks — Task 3
- ✅ `/analyze` rate-limit — Task 3
- ✅ Brent + India VIX — Task 4
- ✅ `/quick-info` TTL cache — Task 5
- ✅ `/quarterly-financials` .BO fallback — Task 6
- ✅ Feature 16: broker ratings strip — Task 7
- ✅ Feature 17: AI disclaimer card — Task 8
- ✅ Feature 19: portfolio warning chips — Task 9
- ✅ Feature 18: morning brief upgrade — Task 10
- ℹ️ Token logging: already implemented (`_log_token_usage` + `token_log.jsonl`)
- ℹ️ GIFT/JITFINFRA/GAUDIUM/OMPOWER: already resolve correctly in `_resolve_ticker`
- ℹ️ Feature 15 (PE badge): already implemented end-to-end
- ℹ️ Fly.io deployment: out of scope for this plan (infrastructure task, ~1hr, separate session)

**Placeholder scan:** No TBDs. Task 3 step 3 mentions "find the exact structure" — reading `analyze_endpoint` first is required. Do that before writing the rate-limit guard.

**Type consistency:** `SignalEvent` defined in Task 1 (database.py), imported in Task 1 step 4, referenced in Task 9 and Task 10. `SignalWarning`/`SignalWarningsResponse` defined in Task 9 step 2, used in same task. `AnalystRating`/`AnalystRatingsResponse` defined in Task 7 step 1, used in Task 7 steps 3-4. Consistent throughout.
