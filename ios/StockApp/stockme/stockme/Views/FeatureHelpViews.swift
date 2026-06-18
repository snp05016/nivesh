import SwiftUI

// MARK: - Reusable Help Button

struct HelpTypedButton: View {
    @Binding var showHelp: Bool
    
    var body: some View {
        Button { HapticManager.selection(); showHelp = true }
        label: {
            Image(systemName: "questionmark.circle")
                .font(Theme.engravedSerif(size: 18, weight: .medium))
                .foregroundColor(Theme.securityGold)
        }
        .buttonStyle(EKPressStyle())
    }
}

// MARK: - Inline Help Button (for screens without NavigationStack)
struct HelpInlineButton: View {
    @Binding var showHelp: Bool
    
    var body: some View {
        HStack {
            Spacer()
            Button { HapticManager.selection(); showHelp = true }
            label: {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "questionmark.circle")
                        .font(Theme.engravedSerif(size: 14, weight: .medium))
                    Text("HOW IT WORKS")
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .tracking(1.0)
                }
                .foregroundColor(Theme.securityGold)
                .padding(.horizontal, Theme.Spacing.standard)
                .padding(.vertical, Theme.Spacing.tight)
                .background(Theme.securityGold.opacity(0.08))
                .clipShape(Capsule())
                .overlay(Capsule().stroke(Theme.securityGold.opacity(0.3), lineWidth: 0.5))
            }
            .buttonStyle(EKPressStyle())
        }
    }
}

// MARK: - Generic Help Card Component

struct HelpSection: Identifiable {
    let id = UUID()
    let icon: String
    let title: String
    let detail: String
}

struct GenericHelpSheet: View {
    @Environment(\.dismiss) var dismiss
    let title: String
    let subtitle: String
    let sections: [HelpSection]
    
    var body: some View {
        NavigationStack {
            ZStack {
                DenominationBackground(denomination: .twoHundred)
                ScrollView {
                    VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                            Text("HOW TO READ")
                                .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                                .tracking(1.5)
                                .foregroundColor(Theme.inkTertiary)
                                .padding(.horizontal, Theme.screenPadding)
                            Text(subtitle)
                                .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                                .foregroundColor(Theme.inkPrimary)
                                .lineSpacing(4)
                                .padding(.horizontal, Theme.screenPadding)
                        }
                        
                        ForEach(Array(sections.enumerated()), id: \.offset) { idx, sec in
                            HStack(alignment: .top, spacing: Theme.Spacing.card) {
                                ZStack {
                                    RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                                        .fill(Theme.securityGold.opacity(0.08))
                                        .frame(width: 40, height: 40)
                                    Text("\(idx + 1)")
                                        .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                                        .foregroundColor(Theme.securityGold)
                                }
                                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                                    HStack(spacing: Theme.Spacing.small) {
                                        Image(systemName: sec.icon)
                                            .font(Theme.engravedSerif(size: 14, weight: .medium))
                                            .foregroundColor(Theme.securityGold)
                                        Text(sec.title)
                                            .font(Theme.engravedSerif(size: 15, weight: .semibold, relativeTo: .headline))
                                            .foregroundColor(Theme.inkPrimary)
                                    }
                                    Text(sec.detail)
                                        .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .caption))
                                        .foregroundColor(Theme.inkSecondary)
                                        .lineSpacing(4)
                                        .fixedSize(horizontal: false, vertical: true)
                                }
                                Spacer()
                            }
                            .padding(Theme.Spacing.card)
                            .banknoteCard()
                            .padding(.horizontal, Theme.screenPadding)
                        }
                    }
                    .padding(.top, Theme.Spacing.large)
                    Spacer(minLength: 80)
                }
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") { HapticManager.selection(); dismiss() }
                        .font(Theme.officialStampFont(size: 12, relativeTo: .body))
                        .foregroundColor(Theme.securityGold)
                }
            }
        }
    }
}

// MARK: - Toolbar Help Button Modifier

struct HelpToolbarButton: ViewModifier {
    @Binding var showHelp: Bool
    
    func body(content: Content) -> some View {
        content
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button { HapticManager.selection(); showHelp = true }
                    label: {
                        Image(systemName: "questionmark.circle")
                            .font(Theme.engravedSerif(size: 18, weight: .medium))
                            .foregroundColor(Theme.securityGold)
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
    }
}

// MARK: - Feature-Specific Help Content

enum FeatureHelp {
    static let correlation = (
        title: "Correlation Matrix Guide",
        subtitle: "A correlation matrix measures how your holdings move together. Lower correlation = better diversification.",
        sections: [
            HelpSection(icon: "squareshape.split.2x2", title: "Reading the Heatmap",
                detail: "Each cell shows the correlation between two stocks from -1 to 1. A +1 score means they move identically in the market — which is bad for diversification. A 0 score means there is no relationship in their price movements. A -1 score means they move in exact opposite directions — providing an ideal hedge."),
            HelpSection(icon: "shield.checkered", title: "Diversification Score",
                detail: "Your portfolio receives a computed score from 0–100 based on the average correlation. A score above 70 is excellent, meaning your holdings are well distributed across uncorrelated sectors. A score below 40 signals dangerous concentration, leaving you vulnerable to sector-wide macroeconomic shocks."),
            HelpSection(icon: "chart.pie.fill", title: "Sector Concentration",
                detail: "Calculates the percentage weight of your portfolio invested in each sector. To prevent catastrophic drawdowns, no single sector should ideally exceed 40% of your total holding. The tool identifies over-exposure and recommends defensive sectors like FMCG or Healthcare to balance risk."),
            HelpSection(icon: "lightbulb.fill", title: "Smart Suggestions",
                detail: "Nivesh runs a hypothetical optimization algorithm in the background to suggest which sectors would most effectively lower your portfolio's overall correlation matrix. It predicts the exact numerical improvement in your Diversification Score if you allocate capital to the suggested sectors."),
            HelpSection(icon: "clock.arrow.circlepath", title: "How It's Calculated",
                detail: "The backend pulls 6 months of daily historical price data for all your active holdings plus the Nifty 50 benchmark. It computes the daily logarithmic returns, then runs a Pearson correlation coefficient matrix using numpy. Sector data is dynamically fetched from the yfinance company info endpoint."),
        ]
    )
    
    static let stressTest = (
        title: "Stress Test Guide",
        subtitle: "Simulates how your portfolio would perform under extreme economic scenarios — recession, inflation, interest rate shocks, and more.",
        sections: [
            HelpSection(icon: "function", title: "How It Works",
                detail: "The Stress Test Engine uses a Tier 2.5 hybrid architecture combining BlackRock-style predictive stress testing with econometric techniques:\n\n• Beta Estimation: Exponentially Weighted Moving Average (EWMA) OLS betas with Vasicek Bayesian Shrinkage to stabilize small-cap estimates\n• Shock Propagation: Conditional expectation propagation using covariance matrices (MSCI/BlackRock methodology)\n• Liquidity Penalty: Almgren-Chriss Square-Root Law of Market Impact with 60% volume suppression during crises\n• Concentration Risk: Herfindahl-Hirschman Index (HHI) and Marginal Risk Contribution (Euler's theorem) using crisis covariance\n• 6 Risk Scores: Risk, Stress, Macro Fragility, Liquidity, Concentration, Tail Risk\n• 14 Pre-built scenarios and custom macro shock capability"),
            HelpSection(icon: "bolt.trianglebadge.exclamationmark", title: "Tornado Chart",
                detail: "Visualizes the expected drawdown or gain via horizontal bars for each modeled scenario. Green bars represent a net positive impact (your portfolio gains value), while red bars represent a net negative impact (your portfolio loses value). The length indicates the absolute magnitude of the shock."),
            HelpSection(icon: "chart.bar.fill", title: "Reading Bar Values",
                detail: "Impact percentages reflect the expected drawdown. For instance, a bar showing -12% means a specific macroeconomic shock is statistically projected to erase 12% of your portfolio's value. The equivalent fiat value in INR (₹) is dynamically calculated against your current holding value."),
            HelpSection(icon: "list.bullet.rectangle.portrait", title: "14 Macro Scenarios",
                detail: "The engine runs deterministic simulations covering: Nifty Crash, Oil Shock, Rate Hikes, FII Exodus, Global Recession, Policy Shock, Currency Crash, and Custom macro shock parameters. Each model applies historical beta, sector sensitivity, and liquidity penalty parameters to your specific stocks."),
            HelpSection(icon: "arrow.up.and.down.text.horizontal", title: "Holding-Level Detail",
                detail: "By tapping a specific scenario, you can drill down into a micro-view that reveals how EACH individual stock in your portfolio contributes to the shock. This enables precision hedging by identifying exactly which holding is dragging your portfolio down under specific conditions."),
        ]
    )
    
    static let nlScreener = (
        title: "NL Screener Guide",
        subtitle: "Search for stocks using plain English — no need to remember complex screener filters or checkbox combinations.",
        sections: [
            HelpSection(icon: "text.magnifyingglass", title: "Natural Language Processing",
                detail: "Type your query naturally in plain English. The AI parses your intent into precise database filters. E.g., \"Show me midcap pharma companies with low debt and high growth\" or \"Large cap banks with promoter holding above 50%\". It understands complex financial jargon and translates it to SQL-like queries."),
            HelpSection(icon: "slider.horizontal.3", title: "Parameter Extraction",
                detail: "The NLP engine extracts exact numerical thresholds and sector mappings from your text: market cap ranges (e.g., 'midcap' -> 5000-20000 Cr), PE limits, debt-to-equity ceilings, promoter holding minimums, and ROE/ROCE thresholds. You can inspect the exact extracted filters directly in the UI."),
            HelpSection(icon: "list.number", title: "Relevance Scoring",
                detail: "Each result is assigned a computed match score (0–100) based on how strictly it satisfies your multi-variate constraints. Hard constraints (e.g., 'PE under 20') filter stocks out, while soft constraints (e.g., 'good dividend yield') rank them higher. Results are sorted by relevance."),
            HelpSection(icon: "clock.arrow.circlepath", title: "Instant Caching",
                detail: "To optimize response times and save LLM credits, screener queries are intelligently cached on the backend for 1 hour. If you submit a semantically identical query, the backend returns the cached payload instantly. Fresh, complex queries bypass the cache and hit the LangGraph pipeline, taking 5–15 seconds."),
        ]
    )
    
    static let anomalies = (
        title: "Market Anomalies Guide",
        subtitle: "A real-time surveillance system that scans the market for unusual activity — volume spikes, price breakouts, and order book irregularities.",
        sections: [
            HelpSection(icon: "exclamationmark.triangle.fill", title: "Anomaly Types",
                detail: "Monitors critical deviations: Volume Spikes (trading volume exceeding 3× the 20-day average), Price Breakouts (closing beyond 2 standard deviations on Bollinger Bands), Order Book irregularities (unusual bid-ask spreads or depth imbalances), and Gap Up/Downs (opening price deviating >3% from prior close)."),
            HelpSection(icon: "chart.line.flaktrends.xyaxis", title: "Severity Levels",
                detail: "Anomalies are bucketed: HIGH signals a statistically rare, >3 sigma event requiring immediate attention. MEDIUM signals unusual but explainable variance. LOW represents mild deviation from moving averages. You can filter by severity to separate noise from actionable alpha."),
            HelpSection(icon: "clock.arrow.2.circlepath", title: "Auto-Scanning & Cron",
                detail: "The backend anomaly scanner runs as an asynchronous cron job every hour, continuously tracking the top NSE stocks to flag statistical irregularities in real-time. When you open the view, you are served pre-computed findings immediately without triggering heavy real-time scans."),
            HelpSection(icon: "arrowshape.turn.up.right.fill", title: "Action Steps",
                detail: "Institutional volume spikes often precede major news or earnings beats. Bollinger breakouts indicate potential trend reversals. These technical flags should be strictly corroborated with the AI Analyst Committee's fundamental reporting before executing trades. Anomalies provide alerts, not guarantees."),
        ]
    )
    
    static let sectorRotation = (
        title: "Sector Rotation Guide",
        subtitle: "Tracks institutional money flow across NSE sectors. Spot which sectors are heating up and which are cooling down before the crowd.",
        sections: [
            HelpSection(icon: "arrow.triangle.2.circlepath", title: "The 4 Quadrants",
                detail: "Sectors are classified dynamically into 4 states: Leaders (high returns + positive momentum, buying accelerates), Improving (low returns but momentum turning positive, indicating early entry), Fading (high returns but declining momentum, indicating profit booking), and Laggards (low returns + negative momentum, avoid)."),
            HelpSection(icon: "chart.line.uptrend.xyaxis", title: "Reading Momentum",
                detail: "The Momentum Score represents the first derivative (rate of change) of sector returns. A +5 score shows explosive upward acceleration, while -3 indicates deceleration. The true signal lies in quadrant transitions—a sector shifting from 'Improving' to 'Leaders' is a classic bullish indicator."),
            HelpSection(icon: "building.2.fill", title: "Institutional Confluence",
                detail: "Evaluates the combined net flow of Foreign Institutional Investors (FII) and Domestic Institutional Investors (DII). A high institutional conviction score (>70) means both FIIs and DIIs are aggressively deploying capital into the sector, providing a massive liquidity tailwind."),
            HelpSection(icon: "calendar", title: "Time Horizon Filtering",
                detail: "Allows toggling between 1M, 3M, 6M, and 1Y lookback windows. Shorter timeframes expose recent momentum rotation, while the 1-year view filters out noise to reveal macro structural trends. Traders use 3M for tactical swings, while investors use 1Y for strategic core allocations."),
        ]
    )
}

// MARK: - View Modifier Extension

extension View {
    func withHelpButton(showHelp: Binding<Bool>) -> some View {
        self.modifier(HelpToolbarButton(showHelp: showHelp))
    }
    
    func helpSheet(isPresented: Binding<Bool>, title: String, subtitle: String, sections: [HelpSection]) -> some View {
        self.sheet(isPresented: isPresented) {
            GenericHelpSheet(title: title, subtitle: subtitle, sections: sections)
        }
    }
}
