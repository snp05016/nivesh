# Market Data & News Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix missing index/sector data using yfinance fallbacks and implement a premium, high-fidelity news reader in iOS.

**Architecture:** 
- Backend: Update `main.py` with history-based fallbacks for indices/sectors and enriched news fields.
- iOS: Extend `NewsItem` model and implement a `fullScreenCover` reader view with image support.

**Tech Stack:** Python 3.12+, FastAPI, yfinance, SwiftUI, Combine.

---

## File Map

| File | Responsibility |
|------|----------------|
| `/Users/saumya/Desktop/stocks/main.py` | API endpoints (harden indices/sectors, enrich news). |
| `StockApp/stockme/stockme/Models.swift` | Data models (add summary and image_url to NewsItem). |
| `StockApp/stockme/stockme/Views/AnalysisScreen.swift` | UI (NewsItemCard, NewsReaderView). |

---

## Task 1: Backend Hardening for Market Indices

**Files:**
- Modify: `/Users/saumya/Desktop/stocks/main.py`

- [ ] **Step 1: Update `_get_indices_data` with history fallback**

Replace the existing `_get_indices_data` function in `main.py`:

```python
def _get_indices_data() -> dict:
    """Fetch and cache market indices data. Used by both /market-indices and /morning-summary."""
    now = time.time()
    if _indices_cache["data"] is not None and (now - _indices_cache["ts"]) < _INDICES_CACHE_TTL:
        return _indices_cache["data"]

    result = []
    import time
    import random
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
            
            change_abs = round(current - prev_close, 4) if prev_close else 0.0
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
        "fetched_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _indices_cache["data"] = payload
    _indices_cache["ts"] = now
    return payload
```

- [ ] **Step 2: Verify endpoint via curl**

Run: `curl -s http://localhost:8000/market-indices | jq .`
Expected: JSON with "indices" array containing Nifty 50, Sensex, etc.

- [ ] **Step 3: Commit**

```bash
git add /Users/saumya/Desktop/stocks/main.py
git commit -m "fix: harden market-indices fetching with history fallback"
```

---

## Task 2: Backend Hardening for Sector Pulse

**Files:**
- Modify: `/Users/saumya/Desktop/stocks/main.py`

- [ ] **Step 1: Update `sector_performance_endpoint` with history fallback**

Replace the existing `sector_performance_endpoint` function in `main.py`:

```python
@app.get("/sector-performance")
def sector_performance_endpoint():
    global _sector_cache
    now = time.time()
    if _sector_cache["data"] and now - _sector_cache["ts"] < 600:
        return _sector_cache["data"]

    sectors = []
    import time
    import random
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
        "fetched_at": datetime.utcnow().isoformat(),
    }
    _sector_cache = {"data": result, "ts": now}
    return result
```

- [ ] **Step 2: Verify endpoint via curl**

Run: `curl -s http://localhost:8000/sector-performance | jq .`
Expected: JSON with "sectors" array.

- [ ] **Step 3: Commit**

```bash
git add /Users/saumya/Desktop/stocks/main.py
git commit -m "fix: harden sector-performance fetching with history fallback"
```

---

## Task 3: Backend Enriched News Fields

**Files:**
- Modify: `/Users/saumya/Desktop/stocks/main.py`

- [ ] **Step 1: Update `quick_info_endpoint` news extraction**

Locate the `raw_news` processing loop in `quick_info_endpoint` (around line 880) and update it to include `summary` and `image_url`:

```python
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
```

- [ ] **Step 2: Verify enriched news via curl**

Run: `curl -s "http://localhost:8000/quick-info?ticker=RELIANCE&exchange=NSE" | jq '.recent_news[0]'`
Expected: JSON object containing "summary" and "image_url".

- [ ] **Step 3: Commit**

```bash
git add /Users/saumya/Desktop/stocks/main.py
git commit -m "feat: enrich news items with summary and image_url"
```

---

## Task 4: iOS Model Extension

**Files:**
- Modify: `StockApp/stockme/stockme/Models.swift`

- [ ] **Step 1: Update `NewsItem` struct**

Add the new fields and `CodingKeys` to `NewsItem`:

```swift
struct NewsItem: Codable, Identifiable {
    var id: String { link }
    let title: String
    let publisher: String
    let link: String
    let publishTime: Int?
    let summary: String?
    let imageUrl: String?

    enum CodingKeys: String, CodingKey {
        case title, publisher, link, summary
        case publishTime = "publish_time"
        case imageUrl = "image_url"
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add StockApp/stockme/stockme/Models.swift
git commit -m "feat: update NewsItem model with summary and imageUrl"
```

---

## Task 5: iOS High-Fidelity News Reader UI

**Files:**
- Modify: `StockApp/stockme/stockme/Views/AnalysisScreen.swift`

- [ ] **Step 1: Implement `NewsReaderView`**

Add this view at the end of `AnalysisScreen.swift` or in a new file (prefer end of file for now as per current project style):

```swift
struct NewsReaderView: View {
    let item: NewsItem
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Hero Image
                    if let urlStr = item.imageUrl, let url = URL(string: urlStr) {
                        AsyncImage(url: url) { image in
                            image.resizable().aspectRatio(contentMode: .fill)
                        } placeholder: {
                            Rectangle().fill(Theme.inkSecondary.opacity(0.1))
                        }
                        .frame(height: 240)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                        .padding(.horizontal, Theme.screenPadding)
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        Text(item.title)
                            .font(Theme.engravedSerif(size: 24, weight: .bold))
                            .foregroundColor(Theme.inkPrimary)
                            .lineSpacing(4)

                        HStack {
                            Text(item.publisher.uppercased())
                                .font(Theme.officialStampFont(size: 10))
                                .foregroundColor(Theme.securityGold)
                            
                            if let time = item.publishTime {
                                Text("•")
                                Text(Date(timeIntervalSince1970: TimeInterval(time)), style: .date)
                            }
                        }
                        .font(Theme.serialNumberFont(size: 11))
                        .foregroundColor(Theme.inkTertiary)

                        Divider().background(Theme.guilloche)

                        if let summary = item.summary, !summary.isEmpty {
                            Text(summary)
                                .font(.system(size: 17, weight: .medium, design: .serif))
                                .foregroundColor(Theme.inkSecondary)
                                .lineSpacing(8)
                        } else {
                            Text("Summary not available. Please read the full story for more details.")
                                .italic()
                                .font(Theme.serialNumberFont(size: 14))
                                .foregroundColor(Theme.inkTertiary)
                        }

                        Link(destination: URL(string: item.link)!) {
                            HStack {
                                Text("READ FULL STORY ON \(item.publisher.uppercased())")
                                Image(systemName: "arrow.up.right")
                            }
                            .font(Theme.officialStampFont(size: 11))
                            .foregroundColor(.white)
                            .padding(.vertical, 14)
                            .frame(maxWidth: .infinity)
                            .background(Theme.inkPrimary)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                        .padding(.top, 20)
                    }
                    .padding(.horizontal, Theme.screenPadding)

                    Spacer(minLength: 40)
                }
            }
            .background(Theme.canvasDeep)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button { dismiss() } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(Theme.inkTertiary)
                            .font(.system(size: 24))
                    }
                }
            }
        }
    }
}
```

- [ ] **Step 2: Update `NewsItemCard` to support image and navigation**

Replace `NewsItemCard` in `AnalysisScreen.swift`:

```swift
private struct NewsItemCard: View {
    let item: NewsItem
    @State private var showingReader = false

    var body: some View {
        Button {
            HapticManager.impact(.light)
            showingReader = true
        } label: {
            HStack(spacing: 16) {
                if let urlStr = item.imageUrl, let url = URL(string: urlStr) {
                    AsyncImage(url: url) { image in
                        image.resizable().aspectRatio(contentMode: .fill)
                    } placeholder: {
                        Rectangle().fill(Theme.inkSecondary.opacity(0.1))
                    }
                    .frame(width: 80, height: 80)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }

                VStack(alignment: .leading, spacing: 6) {
                    Text(item.title)
                        .font(Theme.engravedSerif(size: 15, weight: .bold))
                        .foregroundColor(Theme.inkPrimary)
                        .lineLimit(3)
                        .multilineTextAlignment(.leading)
                    
                    HStack {
                        Text(item.publisher.uppercased())
                            .font(Theme.officialStampFont(size: 8))
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.system(size: 10))
                    }
                    .foregroundColor(Theme.inkSecondary)
                }
            }
            .padding(12)
            .banknoteCard()
        }
        .buttonStyle(.plain)
        .fullScreenCover(isPresented: $showingReader) {
            NewsReaderView(item: item)
        }
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add StockApp/stockme/stockme/Views/AnalysisScreen.swift
git commit -m "feat: implement NewsReaderView and update NewsItemCard with image support"
```

---

## Task 6: Final Verification

- [ ] **Step 1: Run Backend**

```bash
cd /Users/saumya/Desktop/stocks
.venv/bin/python3 main.py
```

- [ ] **Step 2: Verify Endpoints (Indices, Sectors, News)**

Test Indices: `curl -s http://localhost:8000/market-indices | jq .`
Test Sectors: `curl -s http://localhost:8000/sector-performance | jq .`
Test News: `curl -s "http://localhost:8000/quick-info?ticker=SBIN&exchange=NSE" | jq .recent_news[0]`

- [ ] **Step 3: Check iOS compilation (Dry Run)**

Since I cannot run Xcode, I will verify the `AnalysisScreen.swift` and `Models.swift` syntax and ensuring all used `Theme` and `IndianFormatter` calls match existing project patterns.

- [ ] **Step 4: Commit and Finish**

```bash
git status
git commit -m "docs: completion of market data hardening and news reader features"
```
