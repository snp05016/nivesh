# NIVESH HARVESTER — Complete Microservice Prompt (v2: Expert-Only)

Paste this entire message into Claude Code. Execute without asking questions.
Follow Andrej Karpathy's guideline: implement end-to-end, handle edge cases, ship a working product.
Use plan-driven execution: read the full plan, understand the architecture, implement sequentially, verify each step.

---

## OBJECTIVE

Build a completely separate web scraping microservice (`nivesh-harvester/`) that:
1. Runs independently from the main Nivesh backend — different port (8001), different DB (harvester.db), different systemd service (nivesh-harvester.service)
2. Scrapes ONLY credentialed expert sources: SEBI filings, CRISIL/ICRA/CARE/India Ratings, CNBC-TV18 expert interviews, Moneycontrol named-author columns, SEBI RIA registry, AMFI mutual fund data, YouTube transcripts
3. Reformats raw text into structured, legible cards using DeepSeek V4 Flash (same model as main backend)
4. Every card gets a CREDIBILITY SCORE (5-10). Below 5 = REJECTED, never stored, never displayed
5. Exposes a clean REST API at port 8001 consumed by the iOS app's "Market Minds" (ExpertNetworkView.swift)
6. Zero overlap with existing backend — if the harvester crashes, Nivesh keeps running

---

## ARCHITECTURE

```
nivesh-harvester/                    ← NEW folder at repo root, peer to backend/
├── main.py                          ← FastAPI app (port 8001, 7 endpoints)
├── requirements.txt                 ← Python deps (NO firecrawl, NO paid APIs)
├── harvester.db                     ← SQLite DB (auto-created on startup)
├── harvesters/
│   ├── __init__.py                  ← exports all harvester functions
│   ├── sebi_filings.py              ← NSE RSS feed → card storage
│   ├── expert_scraper.py            ← CRISIL/ICRA/CARE/India Ratings + CNBC + Moneycontrol + SEBI RIA + AMFI
│   └── youtube_harvester.py         ← YouTube Data API → transcript → card
├── reformatter.py                   ← DeepSeek: raw text → structured JSON card
├── models.py                        ← SQLAlchemy: HarvestedCard + SourceHealth
├── scheduler.py                     ← APScheduler: periodic scrape jobs
└── nivesh-harvester.service         ← systemd unit (separate from nivesh.service)

Existing backend (port 8000)        New harvester (port 8001)
┌──────────────────────┐            ┌───────────────────────────┐
│ main.py               │            │ main.py                    │
│ routers/analysis.py   │    ZERO    │ harvesters/                │
│ services/orchestrator │   OVERLAP  │ reformatter.py (DeepSeek)  │
│ stockapp.db           │            │ harvester.db (SQLite)      │
│ /analyze              │            │ /harvester/feed?ticker=X   │
│ /quick-info           │            │ /harvester/governance/X    │
│ /stock-profile        │            │ /harvester/sources         │
└──────────────────────┘            └───────────────────────────┘
```

---

## CREDIBILITY SCORING SYSTEM

Every scraped item gets a score. Cards below 5 are REJECTED — never stored in DB, never shown to users.

| Score | Source Type | Example | Why Trust It |
|-------|------------|---------|-------------|
| 10 | Regulatory filing | SEBI order, RBI circular, NSE/BSE announcement | Legally binding, government-enforced |
| 10 | Credit rating action | CRISIL downgrade, ICRA upgrade, CARE rating | SEBI-regulated agency, methodology audited |
| 9 | SEBI RIA note | Registered Investment Advisor public commentary | Legally accountable, fiduciary duty |
| 8 | Fund manager interview | Named manager on CNBC-TV18 with title/org | Professional with track record, reputation at stake |
| 7 | Brokerage research | Motilal Oswal, HDFC Securities initiation note | Institutional research, compliance-reviewed |
| 7 | Named expert column | Moneycontrol column by known author with bio | Bylined, accountable, editorial oversight |
| 6 | Financial journalist | ET Prime, Bloomberg Quint by named reporter | Professional journalism standards |
| 5 | Earnings call transcript | Company management's own words | Primary source, but management biased |
| 0 | Anonymous social media | Reddit post, Twitter anon, Telegram forward | REJECTED — zero accountability |

---

## IMPLEMENTATION — BACKEND FILES

### FILE 1: nivesh-harvester/requirements.txt

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
httpx==0.28.1
feedparser==6.0.11
beautifulsoup4==4.12.3
apscheduler==3.11.0
openai>=1.0.0
requests>=2.32.0
google-api-python-client>=2.140.0
youtube-transcript-api>=0.6.2
```

No Firecrawl. No paid scraping APIs. Everything is free HTTP/RSS/JSON.

### FILE 2: nivesh-harvester/models.py

Create two SQLAlchemy tables:

**HarvestedCard:**
- id (PK), external_id (unique hash of URL+content for dedup), source_type (SEBI_FILING/CRISIL_RATING/FUND_MANAGER_INTERVIEW/EXPERT_COLUMN/YOUTUBE/SEBI_RIA_NOTE/AMFI_DATA), source_name, source_url, original_author, published_at, title, raw_text, reformatted_summary, key_takeaways (JSON string list), tickers (JSON string list), sentiment (BULLISH/BEARISH/NEUTRAL), credibility_score (int 5-10), card_type (GOVERNANCE/MACRO/EXPERT/YOUTUBE), expert_credential (string describing why this source is credible), created_at

**SourceHealth:**
- id (PK), source_name (unique), last_success, last_failure, error_message, items_scraped, is_healthy, created_at

Use SQLite at `harvester.db` in the same directory. Include init_db() and get_session() functions.

### FILE 3: nivesh-harvester/reformatter.py

DeepSeek V4 Flash reformatter. Same pattern as backend's llm_utils.py — OpenAI-compatible client at api.deepseek.com.

System prompt must enforce:
- 2-4 sentence summary with exact ₹/%, dates, named parties
- Credibility scoring per the table above
- Below 5 = REJECTED, return None
- Extract tickers, sentiment, key takeaways
- For GOVERNANCE cards: highlight management impact, promoter action, regulatory risk
- For EXPERT cards: name the expert, state credential, summarize their key call and evidence
- Strip all legal boilerplate, emoji, markdown fences
- Return ONLY valid JSON, no text outside

Function: reformat_single(raw_text, source_type, source_name, original_author) → dict or None

Include make_external_id(url, text) for deterministic dedup hashing.

### FILE 4: nivesh-harvester/harvesters/__init__.py

Export: harvest_sebi_filings, harvest_expert_sources, harvest_youtube_transcripts

### FILE 5: nivesh-harvester/harvesters/sebi_filings.py

Scrape NSE corporate announcements RSS feed at `https://www.nseindia.com/corporates/corpInfo/equities/rss/announcementsRss.xml`.

For each entry:
- Extract title, link, summary, published date
- Check for governance keywords: "resignation of statutory auditor", "resignation of auditor", "auditor resignation", "resignation of managing director", "resignation of chief executive", "resignation of chief financial", "pledge", "pledged shares", "invocation of pledge", "sebi order", "sebi action", "insider trading", "sast disclosure", "bulk deal", "block deal", "credit rating downgrade", "forensic audit", "related party transaction"
- If governance keyword found → card_type="GOVERNANCE", credibility_score=10
- Extract tickers using regex: [A-Z]{2,20} (filter common words: THE, AND, FOR, LTD, etc.)
- Dedup by external_id (hash of link+title)
- Store to DB

Function: harvest_sebi_filings(limit=30) → int (number of new cards stored)

### FILE 6: nivesh-harvester/harvesters/expert_scraper.py

THIS IS THE KEY FILE. Five expert sources, all free, no Firecrawl:

**1. Credit Rating Agencies (RSS):**
- CRISIL: `https://www.crisil.com/en/home/newsroom/rss/rating-actions.html`
- ICRA: `https://www.icra.in/RSS/RSSFeeds.aspx?feed=pressreleases`
- CARE: `https://www.careratings.com/rss/press-release`
- India Ratings: `https://www.indiaratings.co.in/rss/pressreleases`
- Parse via feedparser. Each entry → source_type=CRISIL_RATING/ICRA_RATING/CARE_RATING/INDIA_RATINGS, credibility_score=10, card_type=GOVERNANCE, expert_credential="SEBI-Regulated Credit Rating Agency"

**2. CNBC-TV18 Expert Interviews:**
- URLs: `https://www.cnbctv18.com/market/expert-view/`, `/market/stocks/`, `/business/market/`
- Fetch listing page → extract article links → fetch each article → extract text
- Detect expert quotes using regex: "[Name], [Title] at [Organization], said/says/believes/expects/notes..."
- Only keep articles with named expert quotes (skip pure news articles)
- source_type=FUND_MANAGER_INTERVIEW, credibility_score=8, expert_credential extracted from the quote attribution

**3. Moneycontrol Expert Columns:**
- URLs: `https://www.moneycontrol.com/news/business/stocks/`, `/news/opinion/`, `/news/business/markets/`
- Same extraction pattern as CNBC
- CRITICAL FILTER: extract article author. If author is "Moneycontrol", "Reuters", "PTI", "IANS", "BloombergQuint Desk", "FPJ Web Desk", "ET Online" → SKIP (wire service repost, not expert analysis)
- Only keep articles with named, individual authors
- source_type=EXPERT_COLUMN, credibility_score=7

**4. SEBI RIA Registry:**
- URL: `https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId=13`
- For MVP: fetch the page, store as a reference card noting that SEBI RIA registry is available
- credibility_score=9, card_type=GOVERNANCE, expert_credential="SEBI Registered Investment Advisor — legally permitted to provide personalized investment advice"

**5. AMFI Mutual Fund Data:**
- URL: `https://www.amfiindia.com/spages/NAVAll.txt`
- For MVP: fetch, store as reference card about mutual fund flow data availability
- credibility_score=10, card_type=MACRO, expert_credential="AMFI — Association of Mutual Funds in India, regulatory body"

Common entry point: scrape_all_expert_sources() → list[dict] — runs all five, filters out anything with credibility < 5, returns combined results.

Include HTML parsing helpers: _clean_text(), _extract_article_links(), _extract_article_text(), _extract_title(), _extract_article_author(), _extract_expert_quotes()

### FILE 7: nivesh-harvester/harvesters/youtube_harvester.py

Port the existing `backend/services/youtube_harvester.py` pattern. Monitor these channels:
- CNBC-TV18, ET Now, BQ Prime, Zee Business, NDTV Profit, Moneycontrol, FinnovationZ, CA Rachana Ranade, Asset Yogi, Invest Yadnya, SOIC, Value Research

For each video: fetch title, description, channel name, publish date. Use youtube-transcript-api for transcripts. Store as source_type=YOUTUBE, credibility based on channel (CNBC-TV18=8, FinnovationZ=6, etc.), card_type=YOUTUBE.

Function: harvest_youtube_transcripts(limit=20) → int

### FILE 8: nivesh-harvester/scheduler.py

Use APScheduler with BackgroundScheduler. Three jobs:

1. **sebi_harvest** — runs every 15 minutes: harvest_sebi_filings() → for each new card, run reformatter → update reformatted fields in DB
2. **expert_harvest** — runs every 60 minutes: scrape_all_expert_sources() → store raw → reformat each
3. **youtube_harvest** — runs every 120 minutes: harvest_youtube_transcripts() → reformat each

Each job: log start/end with card counts. Update SourceHealth table. Handle exceptions gracefully — one source failing should not block others.

Function: start_scheduler() and stop_scheduler() for lifecycle management.

### FILE 9: nivesh-harvester/main.py

FastAPI app on port 8001. Seven endpoints:

1. `GET /harvester/feed?ticker=RELIANCE&limit=20` — cards for a specific ticker, newest first
2. `GET /harvester/feed?limit=50` — latest cards across all tickers
3. `GET /harvester/governance/{ticker}` — governance-only cards (card_type=GOVERNANCE) for a ticker
4. `GET /harvester/sources` — list of all sources with health status, last run, items scraped
5. `GET /harvester/search?q=auditor+resignation` — full-text search across titles and summaries
6. `POST /harvester/trigger/scrape?source=sebi|expert|youtube&limit=20` — manual trigger
7. `GET /harvester/stats` — total cards, cards per source, cards per card_type, last run times

Lifespan: on startup, init_db() and start_scheduler(). On shutdown, stop_scheduler().

Logging: configure Python logging with timestamps and levels. Log to stdout (systemd captures it).

### FILE 10: nivesh-harvester.service (systemd)

```
[Unit]
Description=Nivesh Harvester Microservice
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/nivesh/nivesh-harvester
ExecStart=/root/nivesh/backend/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10
Environment="DEEPSEEK_API_KEY=your-deepseek-key"
Environment="YOUTUBE_API_KEY=your-youtube-key"
Environment="PYTHONUNBUFFERED=1"
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

No FIRECRAWL_API_KEY needed.

---

## IOS INTEGRATION — EXACT FILES TO CHANGE

### iOS FILE 1: ios/StockApp/stockme/stockme/Models.swift

Add these new model structs at the bottom of the file (before the last closing brace):

```swift
struct HarvestedCard: Codable, Identifiable {
    let id: Int
    let sourceType: String
    let sourceName: String
    let sourceUrl: String
    let originalAuthor: String?
    let publishedAt: String?
    let title: String
    let reformattedSummary: String?
    let keyTakeaways: [String]?
    let tickers: [String]?
    let sentiment: String?
    let credibilityScore: Int
    let cardType: String
    let expertCredential: String?
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case sourceType = "source_type"
        case sourceName = "source_name"
        case sourceUrl = "source_url"
        case originalAuthor = "original_author"
        case publishedAt = "published_at"
        case title
        case reformattedSummary = "reformatted_summary"
        case keyTakeaways = "key_takeaways"
        case tickers
        case sentiment
        case credibilityScore = "credibility_score"
        case cardType = "card_type"
        case expertCredential = "expert_credential"
        case createdAt = "created_at"
    }
}

struct HarvesterFeedResponse: Codable {
    let cards: [HarvestedCard]
    let total: Int
    let sources: [String]
}

struct HarvesterSourceStatus: Codable, Identifiable {
    var id: String { sourceName }
    let sourceName: String
    let lastSuccess: String?
    let lastFailure: String?
    let itemsScraped: Int
    let isHealthy: Bool
    let errorMessage: String?

    enum CodingKeys: String, CodingKey {
        case sourceName = "source_name"
        case lastSuccess = "last_success"
        case lastFailure = "last_failure"
        case itemsScraped = "items_scraped"
        case isHealthy = "is_healthy"
        case errorMessage = "error_message"
    }
}
```

### iOS FILE 2: ios/StockApp/stockme/stockme/NetworkManager.swift

Add a new extension at the bottom of the file:

```swift
// MARK: - Harvester API (port 8001)

extension NetworkManager {
    // Use the same server IP as baseURL but port 8001
    private var harvesterBaseURL: String {
        baseURL.replacingOccurrences(of: ":8000", with: ":8001")
    }

    func fetchHarvesterFeed(ticker: String? = nil, limit: Int = 20) async throws -> HarvesterFeedResponse {
        var urlStr = "\(harvesterBaseURL)/harvester/feed?limit=\(limit)"
        if let t = ticker { urlStr += "&ticker=\(t)" }
        guard let url = URL(string: urlStr) else { throw NetworkError.invalidURL }
        let (data, _) = try await URLSession.shared.data(from: url)
        return try JSONDecoder().decode(HarvesterFeedResponse.self, from: data)
    }

    func fetchGovernanceCards(ticker: String) async throws -> [HarvestedCard] {
        guard let url = URL(string: "\(harvesterBaseURL)/harvester/governance/\(ticker)") else {
            throw NetworkError.invalidURL
        }
        let (data, _) = try await URLSession.shared.data(from: url)
        return try JSONDecoder().decode([HarvestedCard].self, from: data)
    }

    func fetchHarvesterSources() async throws -> [HarvesterSourceStatus] {
        guard let url = URL(string: "\(harvesterBaseURL)/harvester/sources") else {
            throw NetworkError.invalidURL
        }
        let (data, _) = try await URLSession.shared.data(from: url)
        return try JSONDecoder().decode([HarvesterSourceStatus].self, from: data)
    }
}
```

### iOS FILE 3: ios/StockApp/stockme/stockme/Views/ExpertNetworkView.swift

This is the PRIMARY iOS file that displays harvester content. Currently it shows advisor biographies and posts from `/api/v1/ideas/*` endpoints.

**Changes to make (DO NOT REMOVE existing functionality — add alongside it):**

1. Add a new `@State private var harvestedCards: [HarvestedCard] = []` property
2. Add a `.task { await loadHarvestedCards() }` modifier
3. Add a `func loadHarvestedCards()` that calls `NetworkManager.shared.fetchHarvesterFeed(limit: 30)`
4. Add a new section at the TOP of the ScrollView (above existing expert posts) — a "Market Intelligence" section that displays HarvestedCard rows
5. Each card row shows:
   - Credibility badge (small capsule: "CRISIL • Score 10" or "CNBC Expert • Score 8")
   - Source icon (SF Symbol based on source_type)
   - Title (bold, 2 lines max)
   - Reformatted summary (3 lines max)
   - Expert credential (small text below summary)
   - Key takeaways as bullet chips
   - Tickers as small capsules — tapping a ticker navigates to that stock's profile
   - Time ago label
   - Swipe to open source URL in browser
6. Add a "Sources" button in the navigation bar trailing — opens a sheet showing HarvesterSourceStatus list (which sources are healthy, last run times)

**Source icon mapping:**
- SEBI_FILING/EXCHANGE_FILING → "building.columns.fill"
- CRISIL_RATING/ICRA_RATING/CARE_RATING/INDIA_RATINGS → "checkmark.shield.fill"
- FUND_MANAGER_INTERVIEW → "person.fill.checkmark"
- EXPERT_COLUMN → "newspaper.fill"
- SEBI_RIA_NOTE → "person.badge.shield.checkmark.fill"
- AMFI_DATA → "chart.bar.doc.horizontal.fill"
- YOUTUBE → "play.rectangle.fill"

**Credibility score color:**
- 10 → Theme.bullGreen (regulatory/rating action)
- 8-9 → Theme.securityGold (expert/fund manager)
- 6-7 → Theme.inkSecondary (columnist/journalist)
- 5 → Theme.inkTertiary (transcript)

### iOS FILE 4: ios/StockApp/stockme/stockme/Views/StockProfileView.swift

In the existing Governance tab (the one you built earlier), add a section at the bottom:

```swift
// MARK: -- Harvester Governance Cards

@ViewBuilder
private func harvesterGovernanceSection(ticker: String) -> some View {
    // Fetch governance cards from harvester for this ticker
    // Display as a horizontal scrollable row of compact cards
    // Each card: credibility badge + title + 2-line summary
    // Tapping opens source URL
}
```

Add a `@State private var governanceCards: [HarvestedCard] = []` and `.task { governanceCards = (try? await NetworkManager.shared.fetchGovernanceCards(ticker: ticker)) ?? [] }`

---

## DEPLOYMENT

On the server (after all files are created):

```bash
# Create harvester directory
mkdir -p /root/nivesh/nivesh-harvester/harvesters

# Install Python dependencies
/root/nivesh/backend/venv/bin/pip install -r /root/nivesh/nivesh-harvester/requirements.txt

# Copy systemd service
cp /root/nivesh/nivesh-harvester/nivesh-harvester.service /etc/systemd/system/

# Start
systemctl daemon-reload
systemctl enable nivesh-harvester
systemctl start nivesh-harvester

# Verify
curl http://localhost:8001/harvester/sources
curl http://localhost:8001/harvester/feed?limit=5
```

---

## VERIFICATION CHECKLIST

1. `curl http://localhost:8001/harvester/sources` → Returns list of 6+ sources with health status
2. `curl http://localhost:8001/harvester/feed?limit=5` → Returns reformatted cards with credibility scores 5-10
3. `curl http://localhost:8001/harvester/governance/RELIANCE` → Returns governance cards only
4. `curl -X POST http://localhost:8001/harvester/trigger/scrape?source=sebi&limit=5` → Triggers immediate scrape
5. No card has credibility_score < 5
6. No card has source_type REDDIT, TWITTER, or SOCIAL
7. iOS ExpertNetworkView shows "Market Intelligence" section with harvested cards
8. Tapping a ticker on a card navigates to that stock
9. Main Nivesh backend (port 8000) continues working normally — zero impact
10. systemctl status nivesh-harvester shows active/running

---

## CRITICAL "DO NOT" RULES

- Do NOT touch any existing backend file in backend/ — the harvester is completely separate
- Do NOT add Firecrawl or any paid scraping dependency
- Do NOT scrape Reddit, Twitter, Telegram, or any anonymous social media
- Do NOT store cards with credibility_score < 5
- Do NOT change the main Nivesh systemd service
- Do NOT change existing ExpertNetworkView functionality — add NEW sections alongside existing content
- Do NOT use raw colors in iOS — only Theme.* tokens
- Do NOT use "Million"/"Billion" — only Lakhs/Crores via IndianFormatter
- Do NOT create a new Xcode project or Swift package — add files to existing StockApp target
- Do NOT ask the user questions — implement what you think is right

---

## EXPECTED RESULT

A production-ready harvester microservice that:
- Runs on port 8001, separate from the main app
- Scrapes 6+ expert-only sources every 15-120 minutes
- Reformats raw filings/interviews/columns into structured cards with credibility scores
- Displays in the iOS app's Expert Network / Market Minds section
- Shows governance cards in the Stock Profile Governance tab
- Costs $0 in scraping APIs — everything is free HTTP/RSS
- Survives crashes — systemd auto-restarts, one source failing doesn't block others
- Is invisible to users when broken — cards just don't appear, app keeps working
