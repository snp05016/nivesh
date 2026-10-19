import SwiftUI

// MARK: - 3.1 / 3.2 / 3.3 Screener View

struct ScreenerPreset: Identifiable {
    let id: String
    let title: String
    let icon: String
    let description: String
    /// Filter function: returns matching EarningsResult items (nil = filter not available locally)
    let filter: (([EarningsResult]) -> [EarningsResult])?
    /// Backend preset key for server-side screening (used when filter is nil)
    let backendPreset: String?
}

fileprivate let screenerPresets: [ScreenerPreset] = [
    ScreenerPreset(
        id: "piotroski",
        title: "Piotroski High Score",
        icon: "checklist",
        description: "Stocks with strong fundamentals based on Piotroski F-Score criteria",
        filter: nil,
        backendPreset: "quality_value"
    ),
    ScreenerPreset(
        id: "breakout",
        title: "Breakout Candidates",
        icon: "arrow.up.forward",
        description: "Stocks showing price breakouts above key resistance levels",
        filter: { feed in feed.filter { $0.changePercent > 5.0 } },
        backendPreset: nil
    ),
    ScreenerPreset(
        id: "oversold",
        title: "Oversold (RSI < 30)",
        icon: "arrow.down.heart",
        description: "Stocks in oversold territory with potential for mean reversion",
        filter: nil,
        backendPreset: "institutional_capitulation"
    ),
    ScreenerPreset(
        id: "golden_cross",
        title: "Golden Cross",
        icon: "arrow.triangle.swap",
        description: "50-day MA crossing above 200-day MA — classic bullish signal",
        filter: nil,
        backendPreset: "earnings_pioneers"
    ),
    ScreenerPreset(
        id: "high_momentum",
        title: "High Momentum",
        icon: "speedometer",
        description: "Stocks with strong upward price and earnings momentum",
        filter: { feed in feed.filter { $0.changePercent > 3.0 || $0.netProfitGrowthPct > 25.0 } },
        backendPreset: nil
    ),
    ScreenerPreset(
        id: "value_picks",
        title: "Value Picks (Low PE)",
        icon: "tag",
        description: "Undervalued stocks trading at low price-to-earnings multiples",
        filter: nil,
        backendPreset: "turnaround"
    ),
]

struct ScreenerView: View {
    @ObservedObject var vm: EarningsDashboardViewModel
    @State private var selectedPreset: String? = nil
    @State private var filteredResults: [EarningsResult] = []
    @State private var screenerBackendResults: [ScreenerResult] = []
    @State private var isLoading = false

    var body: some View {
        Group {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    // Header
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("स्क्रीनर सूची")
                            .font(.caption)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("STOCK SCREENERS")
                            .font(.caption.weight(.bold).monospaced())
                            .tracking(2)
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .padding(.horizontal, Theme.Spacing.card)
                    .padding(.top, Theme.Spacing.card)

                    // Info hint
                    if vm.feed.isEmpty && !vm.isLoading {
                        emptyStateMessage
                            .padding(.horizontal, Theme.Spacing.card)
                    }

                    // Screener preset cards — banknote aesthetic grid
                    LazyVGrid(
                        columns: Array(repeating: GridItem(.flexible(), spacing: Theme.Spacing.standard), count: 2),
                        spacing: Theme.Spacing.standard
                    ) {
                        ForEach(screenerPresets) { preset in
                            screenerPresetCard(preset)
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.card)

                    // Filtered results section
                    if let selected = selectedPreset, !filteredResults.isEmpty {
                        screenerResultsSection(presetId: selected)
                            .padding(.horizontal, Theme.Spacing.card)
                    } else if let selected = selectedPreset, !screenerBackendResults.isEmpty {
                        screenerBackendResultsSection(presetId: selected)
                            .padding(.horizontal, Theme.Spacing.card)
                    } else if selectedPreset != nil && filteredResults.isEmpty && screenerBackendResults.isEmpty && !isLoading {
                        noResultsForPreset
                            .padding(.horizontal, Theme.Spacing.card)
                    }
                }
                .padding(.bottom, Theme.screenPadding)
            }
            .background(Theme.canvas)
            .navigationDestination(for: String.self) { ticker in
                AnalysisScreen(ticker: ticker)
            }
        }
    }

    // MARK: - Empty State (no feed data at all)

    private var emptyStateMessage: some View {
        VStack(spacing: Theme.Spacing.card) {
            Spacer().frame(height: 20)
            Image(systemName: "antenna.radiowaves.left.and.right")
                .font(.largeTitle.weight(.light))
                .foregroundStyle(Theme.securityGold.opacity(0.6))

            VStack(spacing: Theme.Spacing.tight) {
                Text("SCREENER FEED STATUS")
                    .font(.caption.weight(.bold).monospaced())
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkPrimary)

                // Feed diagnostics
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    ScreenDiagRow(label: "Feed items", value: "\(vm.feed.count)")
                    ScreenDiagRow(label: "Dashboard error", value: vm.dashboardError ?? "none")
                    ScreenDiagRow(label: "Cap index rows", value: "\(vm.capIndexAggregator.count)")
                    ScreenDiagRow(label: "Backend endpoint", value: "/api/v1/screener?preset=<id>", color: Theme.securityGold)
                }
                .padding(Theme.Spacing.standard)
                .background(Theme.canvasDeep)
                .cornerRadius(Theme.CornerRadius.medium)
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                        .stroke(Theme.borderSage, lineWidth: 0.5)
                )

                Text("No earnings feed data available. Screeners require backend data for Piotroski F-Scores, RSI, Golden Cross signals, and PE ratios. Analyze stocks via the Analysis tab or use Search → Screener for live backend presets.")
                    .font(.caption)
                    .foregroundStyle(Theme.inkTertiary)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, Theme.screenPadding)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Spacing.xLarge)
        .background(Theme.canvasDeep)
        .cornerRadius(Theme.CornerRadius.large)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                .stroke(Theme.borderSage, lineWidth: 0.5)
        )
    }

    // MARK: - No Results for Selected Preset

    private var noResultsForPreset: some View {
        VStack(spacing: Theme.Spacing.standard) {
            GuillocheDivider()
                .padding(.horizontal, Theme.Spacing.card)

            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                HStack(spacing: Theme.Spacing.medium) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.subheadline)
                        .foregroundStyle(Theme.holdAmber)
                    Text("LOCAL FILTER UNAVAILABLE")
                        .font(.caption.weight(.bold).monospaced())
                        .foregroundStyle(Theme.inkPrimary)
                }

                if let presetId = selectedPreset,
                   let preset = screenerPresets.first(where: { $0.id == presetId }) {

                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        ScreenDiagRow(label: "Selected preset", value: preset.title)
                        ScreenDiagRow(label: "Preset ID", value: preset.id)
                        ScreenDiagRow(label: "Has local filter", value: preset.filter != nil ? "YES" : "NO — requires backend")
                        ScreenDiagRow(label: "Missing data",
                            value: missingDataForPreset(preset.id),
                            color: Theme.bearRed)
                        ScreenDiagRow(label: "Backend call",
                            value: "/api/v1/screener?preset=\(preset.id)",
                            color: Theme.securityGold)
                        ScreenDiagRow(label: "Feed available", value: "\(vm.feed.count) items")
                    }
                    .padding(Theme.Spacing.standard)
                    .background(Theme.canvasDeep)
                    .cornerRadius(Theme.CornerRadius.medium)
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                            .stroke(Theme.borderSage, lineWidth: 0.5)
                    )

                    Text("This preset needs server-side computation. Use Search tab → Screener for live backend results, or run analyses on individual stocks to populate local feed data.")
                        .font(.caption)
                        .foregroundStyle(Theme.inkTertiary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(Theme.Spacing.standard)
            .background(Theme.canvasDeep)
            .cornerRadius(Theme.CornerRadius.medium)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(Theme.borderSage, lineWidth: 0.5)
            )
        }
    }

    private func missingDataForPreset(_ id: String) -> String {
        switch id {
        case "piotroski":    return "Piotroski F-Score (needs balance sheet + cash flow + income)"
        case "oversold":     return "RSI-14 calculation (needs 14 days OHLCV history)"
        case "golden_cross": return "50-day + 200-day MA (needs 200 days OHLCV history)"
        case "value_picks":  return "PE ratio + sector average (needs yfinance fundamentals)"
        default:             return "Unknown"
        }
    }

    // MARK: - Diagnostic Row

    private struct ScreenDiagRow: View {
        let label: String
        let value: String
        var color: Color = Theme.inkSecondary

        var body: some View {
            let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
            HStack(alignment: .top, spacing: Theme.Spacing.tight) {
                Text(label)
                    .font(.caption2.weight(.semibold).monospaced())
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(width: colW * 0.28, alignment: .leading)
                Text(value)
                    .font(.caption2.monospaced())
                    .foregroundStyle(color)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    // MARK: - Preset Card

    private func screenerPresetCard(_ preset: ScreenerPreset) -> some View {
        let isSelected = selectedPreset == preset.id
        let isBookmarked = vm.bookmarkedScreeners.contains(preset.id)

        // Compute match count: use local filter if available, else indicate backend
        let matchCount: String = {
            if let filter = preset.filter {
                let matches = filter(vm.feed)
                return "\(matches.count)"
            }
            if preset.backendPreset != nil {
                return "LIVE"
            }
            return "—"
        }()

        return Button(action: {
            HapticManager.selection()
            if isSelected {
                selectedPreset = nil
                filteredResults = []
                screenerBackendResults = []
                return
            }
            selectedPreset = preset.id
            filteredResults = []
            screenerBackendResults = []
            isLoading = true

            if let filter = preset.filter {
                filteredResults = filter(vm.feed)
                isLoading = false
            } else if let backendKey = preset.backendPreset {
                Task {
                    let results = (try? await NetworkManager.shared.fetchScreener(preset: backendKey)) ?? []
                    screenerBackendResults = results
                    isLoading = false
                }
            } else {
                isLoading = false
            }
        }) {
            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                // Icon + Bookmark row
                HStack {
                        ZStack {
                            RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                                .fill(Theme.securityGold.opacity(0.12))
                                .frame(width: Theme.Spacing.xLarge, height: Theme.Spacing.xLarge)
                            Image(systemName: preset.icon)
                                .font(.subheadline.weight(.medium))
                                .foregroundStyle(isSelected ? Theme.securityGold : Theme.inkSecondary)
                        }

                        Spacer()

                        // Bookmark toggle
                        Button(action: {
                            vm.toggleScreenerBookmark(preset.id)
                            HapticManager.impact(.light)
                        }) {
                            Image(systemName: isBookmarked ? "star.fill" : "star")
                                .font(.footnote)
                                .foregroundStyle(isBookmarked ? Theme.securityGold : Theme.inkTertiary.opacity(0.5))
                        }
                        .accessibilityLabel(isBookmarked ? "Remove bookmark" : "Bookmark screener")

                        // Match count badge
                        Text(matchCount)
                            .font(.caption.weight(.bold).monospaced())
                            .foregroundStyle(Theme.securityGold)
                            .padding(.horizontal, Theme.Spacing.medium)
                            .padding(.vertical, Theme.Spacing.small)
                            .background(Theme.securityGold.opacity(0.10))
                            .cornerRadius(Theme.CornerRadius.medium)
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                                    .stroke(Theme.securityGold.opacity(0.2), lineWidth: 0.5)
                            )
                    }

                    // Title
                    Text(preset.title)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(isSelected ? Theme.inkPrimary : Theme.inkPrimary.opacity(0.85))
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)

                    // Description
                    Text(preset.description)
                        .font(.caption2)
                        .foregroundStyle(Theme.inkTertiary)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)

                    Spacer(minLength: 0)
            }
            .padding(Theme.Spacing.standard)
            .frame(minHeight: UIScreen.main.bounds.width * 0.9, alignment: .topLeading)
            .background(isSelected ? Theme.securityGold.opacity(0.06) : Theme.canvasDeep)
            .cornerRadius(Theme.CornerRadius.large)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .stroke(
                        isSelected ? Theme.securityGold.opacity(0.4) : Theme.borderSage,
                        lineWidth: isSelected ? 1.0 : 0.5
                    )
            )
        }
        .buttonStyle(EKPressStyle())
    }

    // MARK: - Results Section

    private func screenerResultsSection(presetId: String) -> some View {
        guard let preset = screenerPresets.first(where: { $0.id == presetId }) else {
            return AnyView(EmptyView())
        }

        return AnyView(
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                GuillocheDivider()

                HStack {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("SCREENER RESULTS")
                            .font(.caption2.weight(.bold).monospaced())
                            .tracking(2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text(preset.title)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    Spacer()
                    Text("\(filteredResults.count) matches")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(Theme.securityGold)
                        .padding(.horizontal, Theme.Spacing.medium)
                        .padding(.vertical, Theme.Spacing.small)
                        .background(Theme.securityGold.opacity(0.10))
                        .cornerRadius(Theme.CornerRadius.tight)
                }

                let colW = UIScreen.main.bounds.width - Theme.Spacing.card * 2
                VStack(spacing: Theme.Spacing.none) {
                        // Table header
                        HStack(spacing: Theme.Spacing.none) {
                            Text("TICKER").tableHeaderStyle().frame(maxWidth: .infinity, alignment: .leading)
                            Text("LTP").tableHeaderStyle().frame(minWidth: colW * 0.18, alignment: .trailing)
                            Text("CHG%").tableHeaderStyle().frame(minWidth: colW * 0.14, alignment: .trailing)
                            Text("PROFIT GR%").tableHeaderStyle().frame(minWidth: colW * 0.18, alignment: .trailing)
                        }
                        .padding(.horizontal, Theme.Spacing.medium)
                        .padding(.vertical, Theme.Spacing.tight)
                        .background(Theme.canvasDeep)
                        .cornerRadius(Theme.CornerRadius.small)

                        ForEach(Array(filteredResults.prefix(15).enumerated()), id: \.offset) { idx, r in
                            HStack(spacing: Theme.Spacing.none) {
                                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                    Text(r.ticker)
                                        .font(.footnote.weight(.bold).monospaced())
                                        .foregroundStyle(Theme.inkPrimary)
                                    Text(r.companyName)
                                        .font(.caption2)
                                        .foregroundStyle(Theme.inkTertiary)
                                        .lineLimit(1)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)

                                Text(IndianFormatter.price(r.ltp))
                                .lineLimit(1)
                                .minimumScaleFactor(0.6)
                                    .font(.caption.monospaced())
                                    .foregroundStyle(Theme.inkPrimary)
                                    .frame(minWidth: colW * 0.18, alignment: .trailing)

                                Text(IndianFormatter.delta(r.changePercent))
                                .lineLimit(1)
                                .minimumScaleFactor(0.6)
                                    .font(.caption.weight(.bold).monospaced())
                                    .foregroundStyle(r.changePercent >= 0 ? Theme.bullGreen : Theme.bearRed)
                                    .frame(minWidth: colW * 0.14, alignment: .trailing)

                                Text(IndianFormatter.delta(r.netProfitGrowthPct))
                                .lineLimit(1)
                                .minimumScaleFactor(0.6)
                                    .font(.caption.weight(.bold).monospaced())
                                    .foregroundStyle(r.netProfitGrowthPct >= 0 ? Theme.bullGreen : Theme.bearRed)
                                    .frame(minWidth: colW * 0.18, alignment: .trailing)
                            }
                            .padding(.horizontal, Theme.Spacing.medium)
                            .padding(.vertical, Theme.Spacing.medium)

                            if idx < min(filteredResults.count, 15) - 1 {
                                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                            }
                        }
            }
            .padding(.vertical, Theme.Spacing.small)
            .background(Theme.canvasDeep)
            .cornerRadius(Theme.CornerRadius.medium)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(Theme.borderSage, lineWidth: 0.5)
            )
        }
    )
    }

    // MARK: - Backend Results Section

    private func screenerBackendResultsSection(presetId: String) -> some View {
        guard let preset = screenerPresets.first(where: { $0.id == presetId }) else {
            return AnyView(EmptyView())
        }
        return AnyView(
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                GuillocheDivider()

                HStack {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("SCREENER RESULTS")
                            .font(.caption2.weight(.bold).monospaced())
                            .tracking(2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text(preset.title)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    Spacer()
                    Text("\(screenerBackendResults.count) matches")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(Theme.securityGold)
                        .padding(.horizontal, Theme.Spacing.medium)
                        .padding(.vertical, Theme.Spacing.small)
                        .background(Theme.securityGold.opacity(0.10))
                        .cornerRadius(Theme.CornerRadius.tight)
                }

                ForEach(Array(screenerBackendResults.enumerated()), id: \.element.id) { idx, result in
                    NavigationLink(value: result.ticker) {
                        screenerBackendResultRow(result: result)
                    }
                    .ekPressHaptic()
                    .staggerAppear(delay: Double(idx) * 0.05)
                }
            }
        )
    }

    private func screenerBackendResultRow(result: ScreenerResult) -> some View {
        HStack(spacing: Theme.Spacing.none) {
            Rectangle()
                .fill(Theme.securityGold.opacity(0.4))
                .frame(width: 1)
                .padding(.vertical, Theme.Spacing.standard)

            HStack(spacing: Theme.Spacing.card) {
                StockIcon(ticker: result.ticker, signal: nil)

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(result.ticker.uppercased())
                        .font(Theme.engravedSerif(size: 14, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                    if let company = result.companyName {
                        Text(company)
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.inkSecondary)
                            .lineLimit(1)
                    }
                    if let reason = result.reason {
                        Text(reason)
                            .font(.caption2)
                            .foregroundStyle(Theme.inkTertiary)
                            .lineLimit(1)
                    }
                }
                Spacer()

                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                    if let conf = result.confidencePct {
                        Text("\(conf)%")
                            .font(Theme.serialNumberFont(size: 11))
                            .contentTransition(.numericText())
                            .foregroundStyle(Theme.securityGold)
                    }
                    if let fs = result.fScore {
                        Text("F:\(fs)/9")
                            .font(Theme.serialNumberFont(size: 10))
                            .contentTransition(.numericText())
                            .foregroundStyle(Theme.bullGreen)
                    }
                    if let pe = result.peRatio {
                        Text("PE:\(String(format: "%.1f", pe))")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    if let pg = result.profitGrowthPct {
                        Text("+\(String(format: "%.0f", pg))%")
                            .font(Theme.serialNumberFont(size: 10))
                            .contentTransition(.numericText())
                            .foregroundStyle(Theme.bullGreen)
                    }
                    if let r = result.rsi {
                        Text("RSI:\(String(format: "%.0f", r))")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.bearRed)
                    }
                }
                Image(systemName: "arrow.right")
                    .foregroundStyle(Theme.inkSecondary.opacity(0.3))
                    .font(.footnote.weight(.bold))
            }
            .padding(.vertical, Theme.Spacing.standard)
            .padding(.leading, Theme.Spacing.standard)
            .padding(.trailing, Theme.Spacing.card)
        }
        .glassCard()
        .banknoteCard()
    }
}
