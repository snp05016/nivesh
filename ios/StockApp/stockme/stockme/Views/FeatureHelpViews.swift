import SwiftUI

// MARK: - Reusable Help Button

struct HelpTypedButton: View {
    @Binding var showHelp: Bool
    
    var body: some View {
        Button { HapticManager.selection(); showHelp = true }
        label: {
            Image(systemName: "questionmark.circle")
                .font(.system(size: 18, weight: .medium))
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
                        .font(.system(size: 14, weight: .medium))
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
                                            .font(.system(size: 14, weight: .medium))
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
                            .font(.system(size: 18, weight: .medium))
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
                detail: "Each cell shows the correlation between two stocks from -1 to 1. +1 means they move identically — bad for diversification. 0 means no relationship. -1 means they move in opposite directions — ideal for hedging."),
            HelpSection(icon: "shield.checkered", title: "Diversification Score",
                detail: "Scored 0–100. A score above 70 is excellent — your holdings are spread across different sectors and have low correlation. Below 40 signals your portfolio is concentrated and vulnerable to sector-wide shocks."),
            HelpSection(icon: "chart.pie.fill", title: "Sector Concentration",
                detail: "Shows what percentage of your portfolio is in each sector. If any single sector exceeds 40%, your portfolio is over-concentrated. Adding stocks from healthcare, FMCG, or IT can improve your score."),
            HelpSection(icon: "lightbulb.fill", title: "Smart Suggestions",
                detail: "Nivesh suggests which sectors to add to improve your diversification. Each suggestion includes the expected improvement in your diversification score if you add a stock from that sector."),
            HelpSection(icon: "clock.arrow.circlepath", title: "How It's Calculated",
                detail: "Uses 6 months of daily price data for all your holdings plus Nifty 50. Computes daily returns, then runs numpy's corrcoef to calculate pairwise correlations. Sectors are fetched from yfinance company info."),
        ]
    )
    
    static let stressTest = (
        title: "Stress Test Guide",
        subtitle: "Simulates how your portfolio would perform under extreme economic scenarios — recession, inflation, interest rate shocks, and more.",
        sections: [
            HelpSection(icon: "bolt.trianglebadge.exclamationmark", title: "Tornado Chart",
                detail: "Each horizontal bar shows the impact of one scenario on your portfolio. Green bars = positive impact (your portfolio gains), red bars = negative (your portfolio loses). The longer the bar, the bigger the impact."),
            HelpSection(icon: "chart.bar.fill", title: "Reading Bar Values",
                detail: "Impact percentages show the expected change in your portfolio value. A bar showing -12% means the scenario would drop your portfolio by 12%. The amount in rupees (₹) is also shown for clarity."),
            HelpSection(icon: "list.bullet.rectangle.portrait", title: "8 Scenarios",
                detail: "Tests cover: Recession, Inflation Spike, Crude Oil Shock, Interest Rate Hike (RBI), Currency Crash (INR), Global Market Selloff, Domestic Political Crisis, and COVID-style Black Swan. Each is modeled with historical data from similar events."),
            HelpSection(icon: "arrow.up.and.down.text.horizontal", title: "Holding-Level Detail",
                detail: "Tap any scenario bar to see how EACH of your holdings performs individually. This helps identify which stocks are most vulnerable to specific shocks — useful for hedging decisions."),
        ]
    )
    
    static let nlScreener = (
        title: "NL Screener Guide",
        subtitle: "Search for stocks using plain English — no need to remember complex screener filters or checkbox combinations.",
        sections: [
            HelpSection(icon: "text.magnifyingglass", title: "How to Query",
                detail: "Type naturally: \"Show me midcap pharma companies with low debt and high growth\", \"Large cap banks with promoter holding above 50%\", or \"IT stocks with PE under 20 and good dividend yield\". The AI parses your intent into precise filters."),
            HelpSection(icon: "slider.horizontal.3", title: "Parsed Filters",
                detail: "The AI extracts key parameters from your query: sector, market cap range, PE limits, debt-to-equity ceiling, promoter holding minimum, ROE/ROCE thresholds, and more. You can see exactly what filters were extracted."),
            HelpSection(icon: "list.number", title: "Match Scoring",
                detail: "Each result gets a match score (0–100). Higher scores mean the stock fits your criteria more closely. Results are sorted from best match to weakest, so the most relevant stocks appear first."),
            HelpSection(icon: "clock.arrow.circlepath", title: "Cached Results",
                detail: "Results are cached for 1 hour. If you run the same query within an hour, you get instant results without waiting for the AI to re-analyze. Fresh queries hit the AI pipeline and take 5–15 seconds."),
        ]
    )
    
    static let anomalies = (
        title: "Market Anomalies Guide",
        subtitle: "A real-time surveillance system that scans the market for unusual activity — volume spikes, price breakouts, and order book irregularities.",
        sections: [
            HelpSection(icon: "exclamationmark.triangle.fill", title: "Anomaly Types",
                detail: "Volume Spike: Trading volume 3× above 20-day average. Price Breakout: Close beyond 2 Bollinger Bands. Order Book: Unusual bid-ask spreads or depth imbalances. Gap Up/Down: Opening price gap exceeding 3% from previous close."),
            HelpSection(icon: "chart.line.flaktrends.xyaxis", title: "Severity Levels",
                detail: "HIGH: Requires immediate attention — statistically rare event. MEDIUM: Unusual but may have explanations. LOW: Mild deviation from normal ranges. Filter by severity to focus on the most actionable signals."),
            HelpSection(icon: "clock.arrow.2.circlepath", title: "Auto-Scanning",
                detail: "The anomaly scanner runs automatically every hour on the server. It monitors the top 20 NSE stocks and flags any irregularities. You see results immediately when opening the screen — no need to trigger a scan manually."),
            HelpSection(icon: "arrowshape.turn.up.right.fill", title: "Action Steps",
                detail: "Volume spikes may signal insider activity or pending news. Price breakouts can indicate trend changes. Use these signals with other analysis (fundamentals, sentiment) before making trading decisions. Anomalies are alerts, not recommendations."),
        ]
    )
    
    static let sectorRotation = (
        title: "Sector Rotation Guide",
        subtitle: "Tracks institutional money flow across NSE sectors. Spot which sectors are heating up and which are cooling down before the crowd.",
        sections: [
            HelpSection(icon: "arrow.triangle.2.circlepath", title: "The 4 Quadrants",
                detail: "Leaders: High return + positive momentum (buying continues). Improving: Low return but momentum turning positive (early entry opportunity). Fading: High return but momentum declining (consider taking profits). Laggards: Low return + negative momentum (avoid or wait)."),
            HelpSection(icon: "chart.line.uptrend.xyaxis", title: "Reading Momentum",
                detail: "Momentum score shows the rate of change in sector returns. A score of +5 means strong upward acceleration. -3 means deceleration. Watch for quadrant transitions — when a sector moves from Improving to Leaders, that's a bullish signal."),
            HelpSection(icon: "building.2.fill", title: "FII & DII Flows",
                detail: "Foreign Institutional Investor (FII) and Domestic Institutional Investor (DII) flows show where the big money is going. High institutional conviction (70+) means both FIIs and DIIs are buying the sector — a powerful endorsement."),
            HelpSection(icon: "calendar", title: "Time Periods",
                detail: "Toggle between 1 month, 3 months, 6 months, and 1 year views. Shorter periods show recent momentum shifts. Longer periods filter out noise and reveal structural trends. Use 3-month for tactical allocation, 1-year for strategic decisions."),
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
