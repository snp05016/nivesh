# GOVERNANCE TAB — Standalone Implementation Prompt

Copy this entire message into Claude Code and execute.

---

## OBJECTIVE

Add a **Governance tab** to `StockProfileView.swift` that renders corporate governance data — ASM/GSM surveillance status, promoter holding/pledging, FII/DII breakdown, and AI governance score — in a scannable, risk-first dashboard. Add the missing `promoter_pledged_pct` and AI governance fields to the backend `quick-info` endpoint and iOS models.

---

## CONTEXT

The backend `GET /quick-info` endpoint already returns:
- `promoter_holding_pct`, `fii_holding_pct`, `dii_holding_pct`
- `asm_gsm_status` (surveillance list status: "CLEAN", "ASM", "GSM", "UNKNOWN")
- `officers` (first 3 company officers)
- `debt_to_equity`

But the iOS `QuickInfo` Codable model is **missing**:
- `promoter_pledged_pct` (exists in backend `fundamentals_snapshot`, not surfaced in quick-info)
- `governance_score` (new from governance agent — not yet in quick-info)
- `governance_red_flags` (new from governance agent — not yet in quick-info)

The `StockProfileView` has **no Governance tab** — governance data is scattered across Overview (promoter/FII/DII %) and Charts (shareholding breakdown bar chart). Users can't see the full governance picture in one place.

---

## IMPLEMENTATION — 7 FILES

### BACKEND: 1 file

### FILE 1: Add governance fields to quick-info endpoint
**Path:** `backend/routers/analysis.py`
**Action:** In `quick_info_endpoint()` (around line 224), add these fields to the result dict.

**Step 1.1** — Add `promoter_pledged_pct` to the result dict (after the `promoter_holding_pct` line, around line 380):

```python
"promoter_holding_pct": round(info.get("heldPercentInsiders", 0) * 100, 1) or None,
# NEW:
"promoter_pledged_pct": round(info.get("heldPercentInsiders", 0) * 100 * info.get("insiderPercentHeld", 0) * 0.01, 1) if info.get("heldPercentInsiders") and info.get("insiderPercentHeld") else None,
```

**Step 1.2** — After the `pe_vs_avg` block, add a DB query for the most recent AI governance analysis:

```python
        # Fetch latest AI governance analysis for this ticker
        governance_score = None
        governance_red_flags = []
        try:
            from database import AnalysisHistory, get_session as _get_db_session
            import json as _json
            with _get_db_session() as _sess:
                _last = _sess.query(AnalysisHistory).filter(
                    AnalysisHistory.ticker == ticker.upper()
                ).order_by(AnalysisHistory.created_at.desc()).first()
                if _last:
                    try:
                        _fj = _json.loads(_last.full_json) if isinstance(_last.full_json, str) else _last.full_json
                        governance_score = _fj.get("governance_score")
                        governance_red_flags = _fj.get("governance_red_flags") or []
                    except Exception:
                        pass
        except Exception:
            pass
```

**Step 1.3** — Add these to the result dict (before `_dcache_set`):

```python
            "promoter_pledged_pct": promoter_pledged_pct,  # computed above
            "governance_score": governance_score,
            "governance_red_flags": governance_red_flags,
```

---

### iOS: 6 files

### FILE 2: Add governance fields to QuickInfo Codable
**Path:** `ios/StockApp/stockme/stockme/Models.swift`
**Action:** In `struct QuickInfo: Codable` (around line 372), add these properties after `diiHoldingPct`:

```swift
    let promoterPledgedPct: Double?
    let asmGsmStatus: String?
    let governanceScore: Int?
    let governanceRedFlags: [String]?
```

And add corresponding CodingKeys after the existing ones:

```swift
        case promoterPledgedPct = "promoter_pledged_pct"
        case asmGsmStatus = "asm_gsm_status"
        case governanceScore = "governance_score"
        case governanceRedFlags = "governance_red_flags"
```

---

### FILE 3: Add Governance tab to StockProfileView
**Path:** `ios/StockApp/stockme/stockme/Views/StockProfileView.swift`
**Action:** Three changes:

**3.1** — Add "Governance" to the `tabItems` array (around line 435). Insert it as tab index 3 (between Updates and Chart):

```swift
    private var tabItems: [(label: String, icon: String)] {
        [
            ("Overview", "doc.text"),
            ("Holders", "person.3"),
            ("News", "newspaper"),
            ("Updates", "bell"),
            ("Governance", "shield.checkered"),  // NEW
            ("Chart", "chart.xyaxis.line"),
            ("Financials", "tablecells"),
        ]
    }
```

**3.2** — Add the `governanceTab` to the `TabView` (around line 415). Insert `governanceTab.tag(4)` and renumber subsequent tabs:

```swift
                    TabView(selection: $activeTab) {
                        overviewTab.tag(0)
                        holdersTab.tag(1)
                        newsTab.tag(2)
                        updatesTab.tag(3)
                        governanceTab.tag(4)       // NEW — shifted chart=5, financials=6
                        chartTab.tag(5)
                        financialsTab.tag(6)
                    }
```

**3.3** — Add the governance tab view builder. Place it after `updatesTab` and before `chartTab` (around line 720):

```swift
    // MARK: - Tab: Governance

    @ViewBuilder
    private var governanceTab: some View {
        ScrollView {
            VStack(spacing: Theme.sectionSpacing) {
                if vm.overviewLoading {
                    skeletonBlock(rows: 5)
                } else if let info = vm.quickInfo {
                    governanceContent(info: info)
                } else {
                    emptyState(message: "Governance data unavailable")
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await vm.fetchOverview() }
    }

    @ViewBuilder
    private func governanceContent(info: QuickInfo) -> some View {
        // 1. Surveillance Status Banner
        surveillanceBanner(status: info.asmGsmStatus)

        // 2. AI Governance Score (if available)
        if let score = info.governanceScore {
            governanceScoreCard(score: score, redFlags: info.governanceRedFlags ?? [])
        }

        // 3. Promoter Holding + Pledged
        promoterHoldingCard(info: info)

        // 4. FII vs DII Institutional Flow
        institutionalFlowCard(info: info)

        // 5. Key Officers
        if let officers = info.officers, !officers.isEmpty {
            officersCard(officers: officers)
        }

        // 6. Debt Health
        if let dte = info.debtToEquity {
            debtHealthCard(debtToEquity: dte)
        }
    }

    // MARK: -- Surveillance Banner

    @ViewBuilder
    private func surveillanceBanner(status: String?) -> some View {
        let st = (status ?? "UNKNOWN").uppercased()
        let (bgColor, icon, label): (Color, String, String) = {
            switch st {
            case "GSM":  return (Theme.bearRed.opacity(0.12), "exclamationmark.triangle.fill", "GSM SURVEILLANCE — Trading & settlement restrictions active")
            case "ASM":  return (Theme.holdAmber.opacity(0.12), "exclamationmark.shield.fill", "ASM SURVEILLANCE — Additional margins apply")
            case "CLEAN": return (Theme.bullGreen.opacity(0.08), "checkmark.shield.fill", "No active surveillance measures")
            default:     return (Theme.inkTertiary.opacity(0.06), "questionmark.shield", "Surveillance status unavailable")
            }
        }()

        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(st == "GSM" ? Theme.bearRed : st == "ASM" ? Theme.holdAmber : Theme.bullGreen)
            Text(label)
                .font(Theme.officialStampFont(size: 10))
                .tracking(0.8)
                .foregroundStyle(Theme.inkPrimary)
            Spacer()
        }
        .padding(Theme.Spacing.card)
        .background(bgColor)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderFine, lineWidth: 0.5))
        .glossaryTerm("ASM/GSM", definition: "Additional Surveillance Measure (ASM) and Graded Surveillance Measure (GSM) are SEBI-imposed trading restrictions on stocks showing abnormal price/volume action. GSM stocks face trading curbs and T+ settlement. ASM stocks require 100% margin.")
    }

    // MARK: -- AI Governance Score Card

    @ViewBuilder
    private func governanceScoreCard(score: Int, redFlags: [String]) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("AI GOVERNANCE ASSESSMENT")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            HStack(spacing: Theme.Spacing.card) {
                // Score gauge
                ZStack {
                    Circle()
                        .stroke(Theme.inkTertiary.opacity(0.12), lineWidth: 6)
                        .frame(width: 72, height: 72)

                    Circle()
                        .trim(from: 0, to: CGFloat(score) / 100.0)
                        .stroke(
                            score >= 70 ? Theme.bullGreen :
                            score >= 40 ? Theme.holdAmber :
                            Theme.bearRed,
                            style: StrokeStyle(lineWidth: 6, lineCap: .round)
                        )
                        .rotationEffect(.degrees(-90))
                        .frame(width: 72, height: 72)

                    VStack(spacing: Theme.Spacing.xSmall) {
                        Text("\(score)")
                            .font(Theme.serialNumberFont(size: 20, relativeTo: .title3))
                            .foregroundStyle(
                                score >= 70 ? Theme.bullGreen :
                                score >= 40 ? Theme.holdAmber :
                                Theme.bearRed
                            )
                        Text("/100")
                            .font(Theme.microLabel(size: 8))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(score >= 70 ? "PASS" : score >= 40 ? "CAUTION" : "FAIL")
                        .font(Theme.officialStampFont(size: 11))
                        .foregroundStyle(
                            score >= 70 ? Theme.bullGreen :
                            score >= 40 ? Theme.holdAmber :
                            Theme.bearRed
                        )
                    Text("Governance score computed by AI multi-agent analysis of auditor filings, promoter activity, SEBI disclosures, and insider transactions.")
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineSpacing(3)
                        .lineLimit(3)
                }
            }

            if !redFlags.isEmpty {
                GuillocheDivider()

                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text("RED FLAGS DETECTED")
                        .font(Theme.officialStampFont(size: 8))
                        .tracking(1.0)
                        .foregroundStyle(Theme.bearRed)

                    ForEach(Array(redFlags.enumerated()), id: \.offset) { _, flag in
                        HStack(alignment: .top, spacing: Theme.Spacing.small) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.caption2)
                                .foregroundStyle(Theme.bearRed)
                            Text(flag)
                                .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                                .foregroundStyle(Theme.inkPrimary)
                                .lineSpacing(3)
                        }
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    // MARK: -- Promoter Holding Card

    @ViewBuilder
    private func promoterHoldingCard(info: QuickInfo) -> some View {
        let promoter = info.promoterHoldingPct ?? 0
        let pledged = info.promoterPledgedPct ?? 0

        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("PROMOTER HOLDING")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.medium) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(String(format: "%.1f%%", promoter))
                        .font(Theme.serialNumberFont(size: 28, relativeTo: .title))
                        .foregroundStyle(promoter >= 50 ? Theme.bullGreen : promoter >= 25 ? Theme.holdAmber : Theme.bearRed)
                    Text("Promoter Stake")
                        .font(Theme.microLabel(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                    Text(String(format: "%.1f%%", pledged))
                        .font(Theme.serialNumberFont(size: 28, relativeTo: .title))
                        .foregroundStyle(pledged >= 30 ? Theme.bearRed : pledged >= 10 ? Theme.holdAmber : Theme.bullGreen)
                    Text("Pledged")
                        .font(Theme.microLabel(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }

            // Promoter holding health bar
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(Theme.inkTertiary.opacity(0.1))
                        .frame(height: 8)

                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(promoter >= 50 ? Theme.bullGreen : promoter >= 25 ? Theme.holdAmber : Theme.bearRed)
                        .frame(width: geo.size.width * CGFloat(min(promoter / 100.0, 1.0)), height: 8)

                    // Pledged overlay marker
                    if pledged > 0 {
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                            .fill(Theme.bearRed.opacity(0.6))
                            .frame(width: geo.size.width * CGFloat(min(pledged / 100.0, 1.0)), height: 8)
                    }
                }
            }
            .frame(height: 8)

            // Warning text for high pledging
            if pledged >= 30 {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.caption2)
                        .foregroundStyle(Theme.bearRed)
                    Text("Promoter pledging above 30% — margin-call cascade risk. If stock falls 20%, lenders may invoke pledged shares, forcing distressed promoter selling.")
                        .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                        .foregroundStyle(Theme.bearRed)
                        .lineSpacing(3)
                }
            }

            if !vm.promoterHistory.isEmpty {
                SectionDivider()
                Text("HISTORICAL TREND")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.inkTertiary)
                Chart {
                    ForEach(vm.promoterHistory, id: \.period) { pt in
                        LineMark(x: .value("Period", pt.period), y: .value("Holding", pt.promoter))
                            .foregroundStyle(Theme.securityGold)
                        AreaMark(x: .value("Period", pt.period), y: .value("Holding", pt.promoter))
                            .foregroundStyle(Theme.securityGold.opacity(0.06))
                    }
                }
                .chartXAxis { AxisMarks { _ in AxisValueLabel() } }
                .chartYAxis { AxisMarks { _ in AxisValueLabel() } }
                .frame(height: 80)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .glossaryTerm("PROMOTER PLEDGING", definition: "Promoters pledge their shares as collateral for loans. High pledging (>30%) indicates promoter-level financial stress. If the stock price falls, lenders can sell pledged shares, triggering a cascading crash. This is one of the most critical red flags in Indian equity investing.")
    }

    // MARK: -- Institutional Flow Card

    @ViewBuilder
    private func institutionalFlowCard(info: QuickInfo) -> some View {
        let fii = info.fiiHoldingPct ?? 0
        let dii = info.diiHoldingPct ?? 0
        let publicHolding = max(0, 100 - (info.promoterHoldingPct ?? 0) - fii - dii)

        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("INSTITUTIONAL FLOW")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            // FII vs DII tug-of-war visualization
            HStack(spacing: Theme.Spacing.none) {
                // Promoter block
                Rectangle()
                    .fill(Theme.securityGold)
                    .frame(width: max(CGFloat(info.promoterHoldingPct ?? 0) * 2.8, 0), height: 28)
                    .overlay(Text("P \(String(format: "%.0f", info.promoterHoldingPct ?? 0))%")
                        .font(Theme.microLabel(size: 8))
                        .foregroundStyle(.white))

                // FII block
                Rectangle()
                    .fill(Theme.bullGreen)
                    .frame(width: max(CGFloat(fii) * 2.8, 0), height: 28)
                    .overlay(Text("FII \(String(format: "%.0f", fii))%")
                        .font(Theme.microLabel(size: 8))
                        .foregroundStyle(.white))

                // DII block
                Rectangle()
                    .fill(Theme.avatarBlue)
                    .frame(width: max(CGFloat(dii) * 2.8, 0), height: 28)
                    .overlay(Text("DII \(String(format: "%.0f", dii))%")
                        .font(Theme.microLabel(size: 8))
                        .foregroundStyle(.white))

                // Public block
                Rectangle()
                    .fill(Theme.inkTertiary.opacity(0.3))
                    .frame(width: max(CGFloat(publicHolding) * 2.8, 0), height: 28)
                    .overlay(Text("PUB \(String(format: "%.0f", publicHolding))%")
                        .font(Theme.microLabel(size: 8))
                        .foregroundStyle(Theme.inkSecondary))
            }
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.borderFine, lineWidth: 0.5))

            // Legend
            HStack(spacing: Theme.Spacing.standard) {
                legendDot(color: Theme.securityGold, label: "Promoter")
                legendDot(color: Theme.bullGreen, label: "FII")
                legendDot(color: Theme.avatarBlue, label: "DII")
                legendDot(color: Theme.inkTertiary.opacity(0.4), label: "Public")
            }

            // Minskyan tension gauge
            if fii < dii && fii < 5 {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "info.circle.fill")
                        .font(.caption2)
                        .foregroundStyle(Theme.holdAmber)
                    Text("Low FII + high DII = Minskyan fragility risk. DII-driven prices without foreign conviction can unwind sharply if domestic flows reverse.")
                        .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                        .foregroundStyle(Theme.holdAmber)
                        .lineSpacing(3)
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .glossaryTerm("FII vs DII", definition: "Foreign Institutional Investors (FII/FPI) bring global capital and are sentiment-sensitive. Domestic Institutional Investors (DII — mutual funds, LIC, banks) absorb FII selling via SIP inflows. Sustained DII absorption of FII exits without fundamental earnings growth = Minskyan fragility. Prolonged sentiment-driven DII buying suppresses volatility and impairs price discovery.")
    }

    // MARK: -- Officers Card

    @ViewBuilder
    private func officersCard(officers: [String]) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("KEY OFFICERS")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            ForEach(Array(officers.enumerated()), id: \.offset) { idx, name in
                HStack(spacing: Theme.Spacing.medium) {
                    Circle()
                        .fill(Theme.securityGold.opacity(0.2))
                        .frame(width: 28, height: 28)
                        .overlay(
                            Text(String(name.prefix(1)))
                                .font(Theme.officialStampFont(size: 10))
                                .foregroundStyle(Theme.securityGold)
                        )
                    Text(name)
                        .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body))
                        .foregroundStyle(Theme.inkPrimary)
                    Spacer()
                }
                if idx < officers.count - 1 {
                    Rectangle().fill(Theme.borderFine).frame(height: 0.5)
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .glossaryTerm("CORPORATE OFFICERS", definition: "Key management personnel. Sudden departures of the CEO, CFO, or Managing Director are Tier-1 governance red flags in Indian markets and often precede significant stock price declines.")
    }

    // MARK: -- Debt Health Card

    @ViewBuilder
    private func debtHealthCard(debtToEquity: Double) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("DEBT HEALTH")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.medium) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(String(format: "%.2f", debtToEquity))
                        .font(Theme.serialNumberFont(size: 28, relativeTo: .title))
                        .foregroundStyle(debtToEquity > 2 ? Theme.bearRed : debtToEquity > 1 ? Theme.holdAmber : Theme.bullGreen)
                    Text("D/E Ratio")
                        .font(Theme.microLabel(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                    Text(debtToEquity > 2 ? "HIGH RISK" : debtToEquity > 1 ? "MODERATE" : "HEALTHY")
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundStyle(debtToEquity > 2 ? Theme.bearRed : debtToEquity > 1 ? Theme.holdAmber : Theme.bullGreen)
                }
            }

            // D/E gauge bar
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(Theme.inkTertiary.opacity(0.1))
                        .frame(height: 6)

                    // Green zone (0-1)
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(Theme.bullGreen.opacity(0.6))
                        .frame(width: geo.size.width * 0.33, height: 6)

                    // Amber zone (1-2)
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(Theme.holdAmber.opacity(0.4))
                        .frame(width: geo.size.width * 0.33, height: 6)
                        .offset(x: geo.size.width * 0.33)

                    // Red zone (2+)
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(Theme.bearRed.opacity(0.3))
                        .frame(width: geo.size.width * 0.34, height: 6)
                        .offset(x: geo.size.width * 0.66)

                    // Current value marker
                    Circle()
                        .fill(debtToEquity > 2 ? Theme.bearRed : debtToEquity > 1 ? Theme.holdAmber : Theme.bullGreen)
                        .frame(width: 10, height: 10)
                        .offset(x: geo.size.width * CGFloat(min(debtToEquity / 3.0, 1.0)) - 5)
                }
            }
            .frame(height: 10)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .glossaryTerm("DEBT TO EQUITY", definition: "Total debt divided by shareholders' equity. Below 1.0 = low leverage. Above 2.0 = high financial risk — the company is funding growth through debt rather than earnings. In Indian context, capital-intensive sectors (infra, metals) can sustain higher D/E. For other sectors, D/E >1.5 is a governance concern.")
    }

    // MARK: -- Shared helper (reuse from existing chart helpers)

    private func legendDot(color: Color, label: String) -> some View {
        HStack(spacing: Theme.Spacing.small) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(label)
                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                .foregroundStyle(Theme.inkSecondary)
        }
    }
```

**IMPORTANT:** Check if `legendDot` already exists in the file (it was added in the CHARTS_HANDOFF for shareholding breakdown). If it exists, do NOT add a duplicate — the governance tab can reuse the existing one.

---

### FILE 4: No changes needed for StockProfileViewModel
The `vm.fetchOverview()` call already fetches QuickInfo which will now include the new governance fields. No additional fetch needed.

---

### FILE 5: Add NetworkManager quickInfo method — No changes needed
The existing `quickInfo(ticker:exchange:)` method decodes `QuickInfo.self`. Once the Codable model is updated (FILE 2), the new fields auto-decode.

---

### FILE 6: Ensure `promoterHistory` loads for Governance tab
**Path:** `ios/StockApp/stockme/stockme/Views/StockProfileView.swift`
**Action:** In `governanceTab`, add a `.task { await vm.fetchFinancials() }` to ensure promoter history is loaded (it comes from `QuarterlyFinancialsResponse.promoterHistory`):

The `governanceTab` already calls `vm.fetchOverview()`. Add a second task:

```swift
        .task { await vm.fetchOverview() }
        .task { await vm.fetchFinancials() }  // loads promoterHistory for trend chart
```

---

## VERIFICATION

After implementation:

1. **Backend:** `curl "http://localhost:8000/quick-info?ticker=RELIANCE&exchange=NSE"` — verify response includes `promoter_pledged_pct`, `governance_score`, `governance_red_flags`, `asm_gsm_status`

2. **iOS:** Navigate to any stock → scroll to "Governance" tab → verify:
   - Surveillance banner shows (GSM/ASM/CLEAN)
   - AI Governance Score ring renders (or placeholder if no analysis yet)
   - Promoter holding + pledged % with health bar
   - FII/DII flow bar
   - Officers list
   - Debt health gauge

3. **Edge cases:**
   - Stock with no AI analysis → governance score card hidden, rest renders from QuickInfo
   - Stock with CLEAN surveillance → green banner
   - Stock with GSM → red banner with warning
   - Promoter pledged >30% → red warning text appears

---

## CRITICAL "DO NOT" RULES

- Do NOT change `InteractivePriceChartView` or existing chart tab code
- Do NOT change `financialsTab`
- Do NOT remove any existing tabs
- Do NOT use raw colors — only `Theme.*` tokens
- Do NOT use "Million"/"Billion" — only Lakhs/Crores via `IndianFormatter`
- Do NOT add new API endpoints — reuse existing `quick-info`
- Do NOT add a duplicate `legendDot` if it already exists
- All prices: `IndianFormatter.price()` / `.priceCompact()`. ₹ prefix mandatory.

---

## EXPECTED RESULT

The stock profile gains a dedicated Governance tab that:
- Shows ASM/GSM surveillance status as a prominent banner
- Displays AI governance score (0-100 ring gauge) with red flags
- Shows promoter holding + pledged % with visual health bar and historical trend
- Shows FII/DII/Public shareholding as a stacked bar
- Lists key officers (CFO/MD resignations tracked)
- Shows D/E ratio with a 3-zone gauge
- Every metric has a glossary long-press definition
- GSM/ASM stocks get a red warning banner user cannot miss
- All data comes from existing `quick-info` + `quarterly-financials` endpoints
