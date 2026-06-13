import SwiftUI

// MARK: - Navigation destinations

/// Pushed when a stock card is tapped. Renders the in-screen action hub
/// (replaces the old confirmationDialog).
struct StockActionHubDest: Hashable {
    let ticker: String
    var companyName: String? = nil
    var exchange: String = "NSE"
}

/// How the AI report should launch when pushed from the hub. When set on
/// AnalysisScreen it bypasses the legacy "Cached Report Found" alert.
enum AnalysisLaunchMode: Hashable {
    case cached      // show the most recent cached report (priority: extreme > deep > standard)
    case standard    // fresh standard analysis (V4 Flash, 1 round)
    case deepScan    // fresh analysis with PKScreener + FinBERT
    case extremeScan // DeepSeek V4 Pro, 3-round debate, long-form thesis
    case regenerate  // re-run same type as cached report
}

/// Pushed from the hub to open the AI report in a specific mode.
struct AnalysisDest: Hashable {
    let ticker: String
    let mode: AnalysisLaunchMode
}

// MARK: - Stock Action Hub

/// Full-screen, in-screen chooser shown after tapping a stock. Offers the
/// stock profile and the three AI analysis modes as banknote cards — no dialogs.
struct StockActionHubView: View {
    let dest: StockActionHubDest
    @Binding var path: NavigationPath

    @EnvironmentObject var reportManager: LocalReportManager

    private static let deepScanDisabledTickers: Set<String> = [
        "NIFTY", "SENSEX", "BANKNIFTY", "NIFTYBANK", "INDIAVIX",
    ]

    private var cachedReport: StockAnalysis? {
        reportManager.getReport(for: dest.ticker)
    }

    private var cachedStaleness: (label: String, age: String, tier: String)? {
        guard let cached = cachedReport else { return nil }
        let tier = cached.analysisTier ?? "standard"
        let fmt = DateFormatter()
        fmt.dateFormat = "dd-MMM-yyyy"
        let date = fmt.date(from: cached.analysisDate) ?? Date()
        let hours = Date().timeIntervalSince(date) / 3600
        let label = hours < 6 ? "Fresh" : hours < 48 ? "Aging" : "Stale"
        let ageStr: String
        if hours < 1 { ageStr = "\(Int(hours * 60))m ago" }
        else if hours < 24 { ageStr = "\(Int(hours))h ago" }
        else { ageStr = "\(Int(hours / 24))d ago" }
        return (label, ageStr, tier)
    }

    private var deepScanForbidden: Bool {
        Self.deepScanDisabledTickers.contains(dest.ticker.uppercased())
    }

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .twoHundred)
            BanknoteWatermark(text: dest.ticker.uppercased(), size: 90, opacity: 0.018, alignment: .center)

            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.sectionGap) {
                    header

                    section(title: "STOCK PROFILE") {
                        actionCard(
                            symbol: "chart.xyaxis.line",
                            title: "View Stock Info & Charts",
                            subtitle: "Quote, fundamentals, history & immersive chart",
                            tint: Theme.inkSecondary
                        ) {
                            path.append(StockProfileDest(ticker: dest.ticker, exchange: dest.exchange))
                        }
                    }

                    GuillocheDivider()
                        .padding(.horizontal, Theme.screenPadding)

                    section(title: "AI ANALYSIS") {
                        VStack(spacing: Theme.Spacing.card) {
                            // View Cached — shows highest priority cached report
                            if let cached = cachedReport, let stale = cachedStaleness {
                                let tierLabel = stale.tier == "extreme" ? "EXTREME" : stale.tier == "deep" ? "DEEP" : "STANDARD"
                                let tierColor: Color = stale.tier == "extreme" ? Theme.bearRed : stale.tier == "deep" ? Theme.goldPrimary : Theme.bullGreen

                                actionCard(
                                    symbol: "doc.text.magnifyingglass",
                                    title: "View Cached Report",
                                    subtitle: "\(tierLabel) · \(stale.age) · \(stale.label)",
                                    tint: tierColor
                                ) {
                                    path.append(AnalysisDest(ticker: dest.ticker, mode: .cached))
                                }
                            }

                            // Standard analysis
                            actionCard(
                                symbol: "sparkles",
                                title: "Standard Analysis",
                                subtitle: "DeepSeek V4 Flash · 1-round debate · fastest",
                                tint: Theme.bullGreen
                            ) {
                                path.append(AnalysisDest(ticker: dest.ticker, mode: .standard))
                            }

                            // Deep Scan
                            actionCard(
                                symbol: "scope",
                                title: "Deep Scan",
                                subtitle: deepScanForbidden
                                    ? "Unavailable for indices"
                                    : "PKScreener + FinBERT · deeper fundamentals",
                                tint: Theme.goldPrimary,
                                disabled: deepScanForbidden
                            ) {
                                path.append(AnalysisDest(ticker: dest.ticker, mode: .deepScan))
                            }

                            // Extreme Analysis
                            actionCard(
                                symbol: "flame.fill",
                                title: "Extreme Analysis",
                                subtitle: deepScanForbidden
                                    ? "Unavailable for indices"
                                    : "DeepSeek V4 Pro · 3-round debate · long-form thesis",
                                tint: Theme.bearRed,
                                disabled: deepScanForbidden
                            ) {
                                path.append(AnalysisDest(ticker: dest.ticker, mode: .extremeScan))
                            }

                            // Regenerate (same type as cached)
                            if cachedReport != nil {
                                let cachedTier = cachedReport?.analysisTier ?? "standard"
                                actionCard(
                                    symbol: "arrow.triangle.2.circlepath",
                                    title: "Regenerate",
                                    subtitle: "Re-run as \(cachedTier.uppercased()) with fresh data",
                                    tint: Theme.inkSecondary
                                ) {
                                    path.append(AnalysisDest(ticker: dest.ticker, mode: .regenerate))
                                }
                            }
                        }
                    }

                    Spacer(minLength: 80)
                }
                .padding(.top, Theme.Spacing.large)
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
    }

    // MARK: - Header

    private var header: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            Text(dest.ticker.uppercased())
                .font(Theme.serialNumberFont(size: 28, relativeTo: .largeTitle))
                .foregroundStyle(Theme.inkPrimary)
            if let name = dest.companyName, !name.isEmpty {
                Text(name)
                    .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .subheadline))
                    .foregroundStyle(Theme.inkSecondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, Theme.screenPadding)
    }

    // MARK: - Section wrapper

    @ViewBuilder
    private func section<Content: View>(title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            SectionHeaderView(title: title)
            content()
                .padding(.horizontal, Theme.screenPadding)
        }
    }

    // MARK: - Action card

    private func actionCard(
        symbol: String,
        title: String,
        subtitle: String,
        tint: Color,
        disabled: Bool = false,
        action: @escaping () -> Void
    ) -> some View {
        Button {
            HapticManager.selection()
            action()
        } label: {
            HStack(spacing: Theme.Spacing.card) {
                Image(systemName: symbol)
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(tint)
                    .frame(width: 32, height: 32)

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(title)
                        .font(Theme.engravedSerif(size: 16, weight: .semibold, relativeTo: .headline))
                        .foregroundStyle(Theme.inkPrimary)
                    Text(subtitle)
                        .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                        .multilineTextAlignment(.leading)
                }

                Spacer(minLength: Theme.Spacing.medium)

                Image(systemName: "chevron.right")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(Theme.inkTertiary)
            }
            .padding(Theme.Spacing.card)
            .frame(maxWidth: .infinity, alignment: .leading)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .disabled(disabled)
        .opacity(disabled ? 0.4 : 1.0)
    }
}
