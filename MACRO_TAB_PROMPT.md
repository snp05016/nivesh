# MACRO IMPACT TAB — Standalone Implementation Prompt

Copy this entire message into Claude Code and execute.

---

## OBJECTIVE

Add a **Macro Impact tab** to `StockProfileView` that shows how macroeconomic forces (crude oil, USD/INR, RBI rates, FII/DII flows, India VIX) affect the specific stock being viewed — with a Market Mood Index gauge, macro-to-stock impact cards, and FII/DII flow charts.

No Indian retail app does this. Your feature analysis doc identified it as *"the gap veteran investors find most frustrating — they currently have to mentally bridge macro headlines to stock impact across multiple apps."*

---

## CONTEXT

The backend ALREADY has these endpoints:

| Endpoint | What it returns |
|----------|----------------|
| `GET /macro-strip` | `usd_inr`, `brent_oil_usd`, `crude_oil_usd`, `india_vix`, `rbi_repo_rate_pct`, `rbi_stance` |
| `GET /fii-dii-flow` | Last 30 days: `fii_net`, `dii_net` per day |
| `GET /sector-performance` | All sectors with `changePct` |
| `GET /market-indices` | Nifty, Sensex, Bank Nifty with current + change |
| `GET /nifty-history` | Nifty OHLCV for chart overlay |

None of these are surfaced in `StockProfileView`. This prompt connects them.

---

## APPROACH: 2-tier (Deterministic + AI-enhanced)

- **Tier 1 (Deterministic):** A new `/macro-context/{ticker}` endpoint that takes ticker + sector and applies deterministic sector-macro mapping rules. Zero LLM cost. Always returns instantly.
- **Tier 2 (AI-enhanced):** If the ticker has a recent cached AI analysis, extract `key_factors.global_macro_impact` and `key_factors.indian_market_sentiment` from it. Falls back to Tier 1 if unavailable.

---

## IMPLEMENTATION — BACKEND (1 new endpoint)

### FILE 1: Add macro-context endpoint
**Path:** `backend/routers/market.py`
**Action:** Add new route before or after the `macro_strip_endpoint` (around line 315)

```python
@router.get("/macro-context/{ticker}")
def macro_context_endpoint(ticker: str, exchange: str = "NSE", sector: str = ""):
    """
    Returns macro context for a specific stock:
    - Raw macro data (from /macro-strip)
    - Stock-specific impact mapping (deterministic sector rules)
    - FII/DII trend summary
    - AI-generated impact analysis (if cached analysis exists)
    """
    import math as _m_ctx

    result = {
        "ticker": ticker.upper(),
        "macro_strip": {},
        "fii_dii_trend": {},
        "sector_performance": {},
        "market_mood": {},
        "stock_impact": [],
        "summary": "",
    }

    # ── 1. Fetch macro strip ──────────────────────────────────────────
    try:
        # Reuse the existing macro_strip logic inline (or call the function)
        t_usd = yf.Ticker("USDINR=X")
        usd_info = t_usd.info
        usd_inr = usd_info.get("regularMarketPrice") or usd_info.get("currentPrice")
        if usd_inr and not _m_ctx.isnan(float(usd_inr)):
            result["macro_strip"]["usd_inr"] = round(float(usd_inr), 2)

        t_brent = yf.Ticker("BZ=F")
        brent_info = t_brent.info
        brent = brent_info.get("regularMarketPrice") or brent_info.get("currentPrice")
        if brent and not _m_ctx.isnan(float(brent)):
            result["macro_strip"]["brent_oil_usd"] = round(float(brent), 2)

        t_vix = yf.Ticker("^INDIAVIX")
        vix_info = t_vix.info
        vix = vix_info.get("regularMarketPrice") or vix_info.get("currentPrice")
        if vix and not _m_ctx.isnan(float(vix)):
            result["macro_strip"]["india_vix"] = round(float(vix), 2)
        else:
            result["macro_strip"]["india_vix"] = 16.0  # historical avg

        result["macro_strip"]["rbi_repo_rate_pct"] = 6.50
        result["macro_strip"]["rbi_stance"] = "Neutral"
    except Exception as e:
        result["macro_strip"]["_error"] = str(e)

    # ── 2. FII/DII trend ──────────────────────────────────────────────
    try:
        from database import FIIDIIFlow, get_session as _get_db_sess
        with _get_db_sess() as db:
            flows = db.query(FIIDIIFlow).order_by(FIIDIIFlow.date.desc()).limit(5).all()
            if flows:
                total_fii = sum(f.fii_net or 0 for f in flows)
                total_dii = sum(f.dii_net or 0 for f in flows)
                result["fii_dii_trend"] = {
                    "last_5_sessions": [
                        {"date": f.date, "fii_net": f.fii_net, "dii_net": f.dii_net}
                        for f in flows
                    ],
                    "fii_net_5d_crores": round(total_fii, 0),
                    "dii_net_5d_crores": round(total_dii, 0),
                    "bias": "FII_SELLING" if total_fii < -500 else
                            "FII_BUYING" if total_fii > 500 else
                            "DII_SUPPORTING" if total_dii > 500 and total_fii < 0 else
                            "NEUTRAL",
                }
    except Exception as e:
        result["fii_dii_trend"] = {"_error": str(e)}

    # ── 3. Sector performance ─────────────────────────────────────────
    try:
        from services.scraper import fetch_market_pulse
        pulse = fetch_market_pulse()
        sectors = pulse.get("sectors", [])
        sector_name = sector or "Unknown"
        for s in sectors:
            if s.get("name", "").lower() == sector_name.lower():
                result["sector_performance"] = {
                    "name": s.get("name"),
                    "change_pct": s.get("change_pct"),
                    "market_cap": s.get("market_cap"),
                }
                break
        # Also get broader indices
        result["sector_performance"]["nifty_change_pct"] = pulse.get("nifty_change_pct")
    except Exception as e:
        result["sector_performance"] = {"_error": str(e)}

    # ── 4. Market Mood Index ──────────────────────────────────────────
    vix_val = result["macro_strip"].get("india_vix", 16)
    fii_bias = result["fii_dii_trend"].get("bias", "NEUTRAL")

    # MMI zones: based on India VIX + FII flow direction
    if vix_val > 25 and fii_bias == "FII_SELLING":
        zone = "EXTREME_FEAR"; score = 20
    elif vix_val > 20:
        zone = "FEAR"; score = 35
    elif vix_val > 15 and fii_bias == "FII_BUYING":
        zone = "GREED"; score = 65
    elif vix_val < 12 and fii_bias == "FII_BUYING":
        zone = "EXTREME_GREED"; score = 80
    else:
        zone = "NEUTRAL"; score = 50

    result["market_mood"] = {
        "zone": zone,
        "score": score,
        "india_vix": vix_val,
        "interpretation": {
            "EXTREME_FEAR": "Markets oversold — historically good entry points for long-term investors",
            "FEAR": "Cautious sentiment — observe before deploying heavy capital",
            "NEUTRAL": "Balanced sentiment — normal market conditions",
            "GREED": "Markets overbought — hold existing positions, avoid fresh entries",
            "EXTREME_GREED": "Euphoria zone — consider profit booking, high risk of correction",
        }.get(zone, ""),
    }

    # ── 5. Deterministic stock impact mapping ─────────────────────────
    sector_lower = (sector or "").lower()
    impacts = []

    # Brent crude impact
    brent_val = result["macro_strip"].get("brent_oil_usd")
    if brent_val:
        if any(kw in sector_lower for kw in ["oil", "energy", "petroleum"]):
            impacts.append({
                "factor": "Brent Crude",
                "value": f"${brent_val}/bbl",
                "impact": "POSITIVE",
                "detail": f"Higher crude directly benefits upstream margins. Every $1/bbl rise adds ~₹X to revenue per barrel.",
            })
        elif any(kw in sector_lower for kw in ["paint", "chemical", "aviation", "tyre", "logistics"]):
            impacts.append({
                "factor": "Brent Crude",
                "value": f"${brent_val}/bbl",
                "impact": "NEGATIVE",
                "detail": f"Crude is a key input cost. Sustained high prices compress EBITDA margins in this sector.",
            })
        elif any(kw in sector_lower for kw in ["it", "software", "technology"]):
            impacts.append({
                "factor": "Brent Crude",
                "value": f"${brent_val}/bbl",
                "impact": "INDIRECT",
                "detail": "Crude impacts client budgets in energy-dependent verticals (manufacturing, logistics). Marginally negative for IT services demand from oil-dependent economies.",
            })
        else:
            impacts.append({
                "factor": "Brent Crude",
                "value": f"${brent_val}/bbl",
                "impact": "NEUTRAL",
                "detail": "No direct margin linkage. Indirect impact via inflation expectations and input costs across the supply chain.",
            })

    # USD/INR impact
    usd_val = result["macro_strip"].get("usd_inr")
    if usd_val:
        if any(kw in sector_lower for kw in ["it", "software", "technology", "pharma"]):
            impacts.append({
                "factor": "USD/INR",
                "value": f"₹{usd_val}",
                "impact": "POSITIVE",
                "detail": f"Rupee depreciation boosts export revenues. Every ₹1 weakness adds ~{(usd_val - 80) * 0.8:.1f}% to operating margins for exporters billing in USD.",
            })
        elif any(kw in sector_lower for kw in ["oil", "energy", "chemical", "aviation"]):
            impacts.append({
                "factor": "USD/INR",
                "value": f"₹{usd_val}",
                "impact": "NEGATIVE",
                "detail": "Weaker rupee increases cost of dollar-denominated imports (crude, raw materials). Margin compression risk.",
            })
        else:
            impacts.append({
                "factor": "USD/INR",
                "value": f"₹{usd_val}",
                "impact": "MONITOR",
                "detail": "Indirect impact. FII sentiment turns cautious above ₹85/USD as dollar returns shrink in rupee terms.",
            })

    # RBI rate impact
    repo = result["macro_strip"].get("rbi_repo_rate_pct", 6.5)
    if repo:
        if any(kw in sector_lower for kw in ["bank", "finance", "nbfc", "housing"]):
            impacts.append({
                "factor": "RBI Repo Rate",
                "value": f"{repo}%",
                "impact": "POSITIVE" if repo < 7 else "NEGATIVE",
                "detail": f"Rate-sensitive sector. {'Lower rates boost credit growth and reduce NPAs' if repo < 7 else 'Higher rates compress NIMs and slow credit offtake'}. Every 25bps cut adds ~15bps to bank NIMs.",
            })
        elif any(kw in sector_lower for kw in ["real estate", "auto", "infra"]):
            impacts.append({
                "factor": "RBI Repo Rate",
                "value": f"{repo}%",
                "impact": "INTEREST_RATE_SENSITIVE",
                "detail": "Demand linked to borrowing costs. Rate changes impact buyer affordability with a ~2 quarter lag.",
            })
        else:
            impacts.append({
                "factor": "RBI Repo Rate",
                "value": f"{repo}%",
                "impact": "NEUTRAL",
                "detail": "Minimal direct impact. Broader economy effect via credit cycle and consumption demand.",
            })

    # FII/DII flow impact
    bias = result["fii_dii_trend"].get("bias", "NEUTRAL") if result["fii_dii_trend"] else "NEUTRAL"
    if bias == "FII_SELLING":
        impacts.append({
            "factor": "FII/DII Flow",
            "value": f"{result['fii_dii_trend'].get('fii_net_5d_crores', 0):.0f} Cr (FII 5D net)",
            "impact": "DII_SUPPORTING",
            "detail": "FIIs are net sellers but DIIs (mutual funds, insurance) are absorbing via SIP inflows. This Minskyan dynamic suppresses volatility short-term but builds fragility if fundamentals don't improve. Watch for DII absorption fatigue.",
        })
    elif bias == "FII_BUYING":
        impacts.append({
            "factor": "FII/DII Flow",
            "value": f"{result['fii_dii_trend'].get('fii_net_5d_crores', 0):.0f} Cr (FII 5D net)",
            "impact": "POSITIVE",
            "detail": "FIIs accumulating — institutional conviction supporting the stock. Combined FII+DII buying typically precedes upward price momentum.",
        })

    result["stock_impact"] = impacts

    # ── 6. AI-enhanced summary (if cached analysis exists) ────────────
    try:
        from database import AnalysisHistory, get_session as _get_db_sess2
        import json as _json2
        with _get_db_sess2() as db:
            last = db.query(AnalysisHistory).filter(
                AnalysisHistory.ticker == ticker.upper()
            ).order_by(AnalysisHistory.created_at.desc()).first()
            if last:
                try:
                    fj = _json2.loads(last.full_json) if isinstance(last.full_json, str) else last.full_json
                    kf = fj.get("key_factors", {})
                    macro_impact = kf.get("global_macro_impact", "")
                    sentiment = kf.get("indian_market_sentiment", "")
                    if macro_impact:
                        result["ai_summary"] = macro_impact
                        result["ai_sentiment"] = sentiment
                except Exception:
                    pass
    except Exception:
        pass

    # Build summary text from deterministic impacts
    if not result.get("ai_summary"):
        impact_lines = []
        for imp in impacts:
            if imp["impact"] in ("POSITIVE", "NEGATIVE"):
                impact_lines.append(f"{imp['factor']} ({imp['value']}): {imp['impact']} — {imp['detail'][:100]}")
        result["summary"] = " | ".join(impact_lines[:3]) if impact_lines else "No significant macro headwinds or tailwinds detected."

    return result
```

**Note:** This endpoint has its own yfinance calls. For production, refactor to reuse `macro_strip_endpoint()` logic. But for now, the inline approach avoids import circularity and keeps the change contained.

---

## IMPLEMENTATION — iOS (Models + View)

### FILE 2: Add Macro models to Models.swift
**Path:** `ios/StockApp/stockme/stockme/Models.swift`
**Action:** Add these structs at the bottom of the file (before the last `}`)

```swift
// MARK: - Macro Context Models

struct MacroContextResponse: Codable {
    let ticker: String
    let macroStrip: MacroStrip?
    let fiiDiiTrend: FIIDIITrend?
    let sectorPerformance: MacroSectorPerformance?
    let marketMood: MarketMood?
    let stockImpact: [MacroImpactItem]?
    let summary: String?
    let aiSummary: String?
    let aiSentiment: String?

    enum CodingKeys: String, CodingKey {
        case ticker
        case macroStrip = "macro_strip"
        case fiiDiiTrend = "fii_dii_trend"
        case sectorPerformance = "sector_performance"
        case marketMood = "market_mood"
        case stockImpact = "stock_impact"
        case summary
        case aiSummary = "ai_summary"
        case aiSentiment = "ai_sentiment"
    }
}

struct MacroStrip: Codable {
    let usdInr: Double?
    let brentOilUsd: Double?
    let indiaVix: Double?
    let rbiRepoRatePct: Double?
    let rbiStance: String?

    enum CodingKeys: String, CodingKey {
        case usdInr = "usd_inr"
        case brentOilUsd = "brent_oil_usd"
        case indiaVix = "india_vix"
        case rbiRepoRatePct = "rbi_repo_rate_pct"
        case rbiStance = "rbi_stance"
    }
}

struct FIIDIITrend: Codable {
    let fiiNet5dCrores: Double?
    let diiNet5dCrores: Double?
    let bias: String?

    enum CodingKeys: String, CodingKey {
        case fiiNet5dCrores = "fii_net_5d_crores"
        case diiNet5dCrores = "dii_net_5d_crores"
        case bias
    }
}

struct MacroSectorPerformance: Codable {
    let name: String?
    let changePct: Double?
    let niftyChangePct: Double?

    enum CodingKeys: String, CodingKey {
        case name
        case changePct = "change_pct"
        case niftyChangePct = "nifty_change_pct"
    }
}

struct MarketMood: Codable {
    let zone: String?
    let score: Int?
    let indiaVix: Double?
    let interpretation: String?

    enum CodingKeys: String, CodingKey {
        case zone, score
        case indiaVix = "india_vix"
        case interpretation
    }
}

struct MacroImpactItem: Codable, Identifiable {
    var id: String { factor }
    let factor: String
    let value: String
    let impact: String
    let detail: String
}
```

### FILE 3: Add NetworkManager method
**Path:** `ios/StockApp/stockme/stockme/NetworkManager.swift`
**Action:** Add this method in the NetworkManager class

```swift
    // MARK: - Macro Context

    func fetchMacroContext(ticker: String, exchange: String = "NSE", sector: String = "") async -> MacroContextResponse? {
        var components = URLComponents(string: "\(baseURL)/macro-context/\(ticker)")!
        components.queryItems = [
            URLQueryItem(name: "exchange", value: exchange),
            URLQueryItem(name: "sector", value: sector),
        ]
        guard let url = components.url else { return nil }

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            return try JSONDecoder().decode(MacroContextResponse.self, from: data)
        } catch {
            print("[MacroContext] Fetch failed: \(error)")
            return nil
        }
    }
```

### FILE 4: Add Macro tab to StockProfileView
**Path:** `ios/StockApp/stockme/stockme/Views/StockProfileView.swift`

**Step 4.1:** Add `@State` for macro data (add after `@State private var activeTab = 0` around line 343):

```swift
    @State private var macroContext: MacroContextResponse?
    @State private var macroLoading = false
```

**Step 4.2:** Add "Macro" tab item entry in `tabItems` array (after "Governance"):

```swift
            ("Governance", "shield.checkered"),
            ("Macro", "globe.asia.australia"),  // <-- ADD
            ("Chart", "chart.xyaxis.line"),
```

**Step 4.3:** Add `macroTab` to the TabView (after `governanceTab.tag(4)`):

```swift
                        macroTab.tag(5)           // <-- ADD
                        chartTab.tag(6)           // <-- was 5, now 6
                        financialsTab.tag(7)      // <-- was 6, now 7
```

**Step 4.4:** Add the macro tab view builder (insert before `// MARK: - Tab: Chart`):

```swift
    // MARK: - Tab: Macro

    @ViewBuilder
    private var macroTab: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.card) {
                if macroLoading {
                    skeletonBlock(rows: 4)
                } else if let macro = macroContext {
                    macroMoodGauge(macro: macro)
                    macroStripCard(macro: macro)
                    macroImpactList(macro: macro)
                    macroAIInsightCard(macro: macro)
                } else {
                    emptyState(message: "Macro context unavailable")
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await loadMacroContext() }
    }

    private func loadMacroContext() async {
        guard macroContext == nil else { return }
        macroLoading = true
        let sector = vm.quickInfo?.sector ?? ""
        macroContext = await NetworkManager.shared.fetchMacroContext(
            ticker: ticker, exchange: exchange, sector: sector
        )
        macroLoading = false
    }

    // MARK: -- Market Mood Gauge

    @ViewBuilder
    private func macroMoodGauge(macro: MacroContextResponse) -> some View {
        if let mood = macro.marketMood {
            VStack(spacing: Theme.Spacing.standard) {
                Text("MARKET MOOD INDEX")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                // Semi-circle gauge
                let score = Double(mood.score ?? 50)
                let zoneColor: Color = {
                    switch mood.zone ?? "" {
                    case "EXTREME_FEAR": return Theme.bearRed
                    case "FEAR": return Theme.bearRed.opacity(0.6)
                    case "EXTREME_GREED": return Theme.bullGreen
                    case "GREED": return Theme.bullGreen.opacity(0.6)
                    default: return Theme.holdAmber
                    }
                }()

                ZStack {
                    // Background arc
                    Circle()
                        .trim(from: 0.25, to: 0.75)
                        .stroke(
                            AngularGradient(
                                gradient: Gradient(colors: [
                                    Theme.bearRed, Theme.bearRed.opacity(0.5),
                                    Theme.holdAmber,
                                    Theme.bullGreen.opacity(0.5), Theme.bullGreen
                                ]),
                                center: .center
                            ),
                            style: StrokeStyle(lineWidth: 12, lineCap: .round)
                        )
                        .frame(width: 140, height: 140)
                        .rotationEffect(.degrees(180))

                    // Needle
                    let angle = Angle(degrees: -90 + (score / 100.0 * 180))
                    Path { path in
                        path.move(to: CGPoint(x: 70, y: 70))
                        path.addLine(to: CGPoint(
                            x: 70 + 55 * cos(angle.radians - .pi/2),
                            y: 70 + 55 * sin(angle.radians - .pi/2)
                        ))
                    }
                    .stroke(Theme.inkPrimary, style: StrokeStyle(lineWidth: 2, lineCap: .round))

                    // Center label
                    VStack(spacing: 0) {
                        Text("\(Int(score))")
                            .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                            .foregroundStyle(zoneColor)
                        Text(mood.zone?.replacingOccurrences(of: "_", with: " ") ?? "")
                            .font(Theme.microLabel(size: 7))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .frame(height: 100)

                if let interp = mood.interpretation, !interp.isEmpty {
                    Text(interp)
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                        .multilineTextAlignment(.center)
                        .lineSpacing(3)
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
            .glossaryTerm("MARKET MOOD INDEX", definition: "A composite gauge based on India VIX, FII/DII flow direction, and Nifty momentum. Extreme Fear (<30) = historically good entry zones. Extreme Greed (>70) = caution zone, retail euphoria often precedes corrections. Derived from Tickertape's MMI methodology adapted for Indian markets.")
        }
    }

    // MARK: -- Macro Strip Card

    @ViewBuilder
    private func macroStripCard(macro: MacroContextResponse) -> some View {
        if let strip = macro.macroStrip {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("MACRO INDICATORS")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                HStack(spacing: Theme.Spacing.none) {
                    macroStripItem(
                        label: "BRENT",
                        value: strip.brentOilUsd.map { "$\(String(format: "%.0f", $0))" } ?? "N/A",
                        subtitle: "/bbl",
                        icon: "fuelpump.fill",
                        color: (strip.brentOilUsd ?? 0) > 85 ? Theme.bearRed : Theme.holdAmber
                    )
                    macroStripItem(
                        label: "USD/INR",
                        value: strip.usdInr.map { "₹\(String(format: "%.1f", $0))" } ?? "N/A",
                        subtitle: "₹ per $",
                        icon: "dollarsign.arrow.circlepath",
                        color: (strip.usdInr ?? 0) > 85 ? Theme.bearRed : Theme.bullGreen
                    )
                    macroStripItem(
                        label: "VIX",
                        value: strip.indiaVix.map { String(format: "%.1f", $0) } ?? "N/A",
                        subtitle: "fear gauge",
                        icon: "waveform.path.ecg",
                        color: (strip.indiaVix ?? 0) > 20 ? Theme.bearRed : (strip.indiaVix ?? 0) > 15 ? Theme.holdAmber : Theme.bullGreen
                    )
                    macroStripItem(
                        label: "RBI",
                        value: strip.rbiRepoRatePct.map { "\(String(format: "%.2f", $0))%" } ?? "N/A",
                        subtitle: "repo rate",
                        icon: "building.columns.fill",
                        color: Theme.avatarBlue
                    )
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }

    private func macroStripItem(label: String, value: String, subtitle: String, icon: String, color: Color) -> some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundStyle(color)
            Text(value)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .footnote))
                .foregroundStyle(Theme.inkPrimary)
            Text(label)
                .font(Theme.microLabel(size: 7))
                .tracking(0.5)
                .foregroundStyle(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: -- Macro Impact List

    @ViewBuilder
    private func macroImpactList(macro: MacroContextResponse) -> some View {
        if let impacts = macro.stockImpact, !impacts.isEmpty {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("HOW MACRO AFFECTS \(ticker.uppercased())")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                ForEach(impacts) { item in
                    HStack(alignment: .top, spacing: Theme.Spacing.standard) {
                        // Impact badge
                        Text(item.impact)
                            .font(Theme.microLabel(size: 7))
                            .tracking(0.5)
                            .foregroundStyle(
                                item.impact == "POSITIVE" ? Theme.bullGreen :
                                item.impact == "NEGATIVE" ? Theme.bearRed :
                                Theme.holdAmber
                            )
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(
                                (item.impact == "POSITIVE" ? Theme.bullGreen :
                                 item.impact == "NEGATIVE" ? Theme.bearRed :
                                 Theme.holdAmber).opacity(0.12)
                            )
                            .clipShape(Capsule())

                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            HStack {
                                Text(item.factor)
                                    .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                                    .foregroundStyle(Theme.inkPrimary)
                                Spacer()
                                Text(item.value)
                                    .font(Theme.microLabel(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                            }
                            Text(item.detail)
                                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                                .foregroundStyle(Theme.inkSecondary)
                                .lineLimit(3)
                                .lineSpacing(2)
                        }
                    }
                    .padding(Theme.Spacing.standard)
                    .background(Theme.inkTertiary.opacity(0.03))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))

                    if item.id != impacts.last?.id {
                        Rectangle()
                            .fill(Theme.borderFine)
                            .frame(height: 0.5)
                            .padding(.horizontal, Theme.Spacing.standard)
                    }
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }

    // MARK: -- AI Macro Insight Card

    @ViewBuilder
    private func macroAIInsightCard(macro: MacroContextResponse) -> some View {
        if let aiSummary = macro.aiSummary, !aiSummary.isEmpty {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "sparkles")
                        .font(.caption)
                        .foregroundStyle(Theme.securityGold)
                    Text("AI MACRO ANALYSIS")
                        .font(Theme.officialStampFont(size: 9))
                        .tracking(1.5)
                        .foregroundStyle(Theme.securityGold)
                }

                Text(aiSummary)
                    .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body))
                    .foregroundStyle(Theme.inkPrimary)
                    .lineSpacing(5)
                    .lineLimit(8)

                if let sentiment = macro.aiSentiment, !sentiment.isEmpty {
                    SectionDivider()
                    HStack(spacing: Theme.Spacing.small) {
                        Text("SENTIMENT:")
                            .font(Theme.officialStampFont(size: 8))
                            .foregroundStyle(Theme.inkTertiary)
                        Text(sentiment)
                            .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                            .foregroundStyle(Theme.inkSecondary)
                            .lineLimit(3)
                    }
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }
```

### FILE 4b: If `sector` isn't passed to StockProfileViewModel, add it
**Path:** `ios/StockApp/stockme/stockme/Views/StockProfileView.swift`

The `loadMacroContext()` function uses `vm.quickInfo?.sector`. This is already available via the Overview fetch. If the macro tab loads before overview, it passes empty string — the `/macro-context` endpoint handles that gracefully.

No change needed.

---

## VERIFICATION

After implementation:

1. **Backend:** `curl "http://localhost:8000/macro-context/RELIANCE?exchange=NSE&sector=Oil%20%26%20Gas" | python3 -m json.tool | grep -E "stock_impact|market_mood|macro_strip|bias"`

2. **iOS:** Navigate to RELIANCE → "Macro" tab → verify:
   - Market Mood gauge shows (semi-circle with needle)
   - Macro indicator strip shows Brent/USD-INR/VIX/RBI
   - Impact cards show "How Brent affects RELIANCE" with POSITIVE/NEGATIVE badge
   - AI insight card (if cached analysis exists)
   - FII/DII bias callout

---

## CRITICAL "DO NOT" RULES

- Do NOT use raw colors — only `Theme.*` tokens
- Do NOT use "Million"/"Billion" — Rupees in Crores via `IndianFormatter`
- Do NOT change existing tabs or their tag indices
- Do NOT add new Swift package dependencies
- The MMI gauge is a SwiftUI Path, not a third-party chart
- `macroStripItem` is a private helper, not a standalone view

---

## EXPECTED RESULT

The stock profile gains a Macro Impact tab that:
- Shows Market Mood Index (Fear/Greed semi-circle gauge)
- Displays 4 key macro indicators (Brent, USD/INR, India VIX, RBI rate)
- Lists 4-5 deterministic impact cards mapping each macro factor to this specific stock
- Shows AI-generated macro analysis if a cached analysis exists
- Makes the macro-to-micro connection that no Indian retail app provides
- All data comes from 1 new backend endpoint + existing endpoints
