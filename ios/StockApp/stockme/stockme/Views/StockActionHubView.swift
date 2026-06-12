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
    case cached      // show the stored report, no network
    case regenerate  // fresh standard analysis
    case deepScan    // fresh analysis with PKScreener + FinBERT
    case extremeScan // DeepSeek reasoning, 4 graph bundles, 10-min deep report
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
                            if let cached = cachedReport {
                                actionCard(
                                    symbol: "doc.text.magnifyingglass",
                                    title: "View Cached Report",
                                    subtitle: "Last analysed \(cached.analysisDate)",
                                    tint: Theme.goldPrimary
                                ) {
                                    path.append(AnalysisDest(ticker: dest.ticker, mode: .cached))
                                }
                            }

                            actionCard(
                                symbol: "sparkles",
                                title: "Regenerate",
                                subtitle: "Fresh standard analysis",
                                tint: Theme.bullGreen
                            ) {
                                path.append(AnalysisDest(ticker: dest.ticker, mode: .regenerate))
                            }

                            actionCard(
                                symbol: "scope",
                                title: "Deep Scan",
                                subtitle: deepScanForbidden
                                    ? "Unavailable for indices"
                                    : "PKScreener + FinBERT, slower & deeper",
                                tint: Theme.goldPrimary,
                                disabled: deepScanForbidden
                            ) {
                                path.append(AnalysisDest(ticker: dest.ticker, mode: .deepScan))
                            }

                            actionCard(
                                symbol: "flame.fill",
                                title: "Extreme Analysis",
                                subtitle: deepScanForbidden
                                    ? "Unavailable for indices"
                                    : "DeepSeek V4 Pro · 3-round debate · 1000+ word thesis",
                                tint: Theme.bearRed,
                                disabled: deepScanForbidden
                            ) {
                                path.append(AnalysisDest(ticker: dest.ticker, mode: .extremeScan))
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
