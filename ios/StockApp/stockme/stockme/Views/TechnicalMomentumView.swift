import SwiftUI
import Charts

// MARK: - Technical Momentum View (Section 9)

struct TechnicalMomentumView: View {
    @State private var selectedSubTab: Int = 0      // 9.2 nav sub-bar
    @State private var selectedMomentum: String = "Bullish"  // 9.3 radio group
    @State private var dashboard: MarketDashboardResponse? = nil
    @State private var isLoading = false
    @State private var topMovers: TopMoversResponse? = nil
    @State private var isLoadingMovers = false
    @State private var dashboardError: String? = nil
    @State private var moversError: String? = nil

    let subTabs = ["Technical Trends", "Sectors", "Top Gainers", "Top Losers", "Active by Value", "Active by Volume"]
    let momentumFilters = ["Bullish", "Turning Bullish", "Bearish", "Turning Bearish"]

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()
            VStack(spacing: Theme.Spacing.none) {
                pageHeader
                // 9.2 Horizontal Analytics Sub-Bar
                subTabBar
                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                subTabContent
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .task { await loadDashboard() }
        .task { await loadTopMovers() }
    }

    // MARK: Header

    private var pageHeader: some View {
        HStack {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                Text("तकनीकी गति")
                    .font(Theme.hindiFont(size: 11))
                    .foregroundStyle(Theme.inkSecondary)
                Text("TECHNICAL MOMENTUM")
                    .font(Theme.engravedSerif(size: 24, weight: .bold))
                    .foregroundStyle(Theme.inkPrimary)
                Text("Algorithmic Indicator Engine")
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
            }
            Spacer()
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.top, Theme.Spacing.standard)
        .padding(.bottom, Theme.Spacing.medium)
        .background(Theme.canvasDeep)
    }

    // MARK: 9.2 Horizontal Analytics Sub-Bar

    private var subTabBar: some View {
        ScrollView(.horizontal) {
            HStack(spacing: Theme.Spacing.none) {
                ForEach(Array(subTabs.enumerated()), id: \.offset) { idx, tab in
                    Button(action: { HapticManager.selection(); selectedSubTab = idx }) {
                        Text(tab)
                            .font(Theme.officialStampFont(size: 11))
                            .fontWeight(selectedSubTab == idx ? .bold : .regular)
                            .foregroundStyle(selectedSubTab == idx ? Theme.securityGold : Theme.inkTertiary)
                            .padding(.horizontal, Theme.Spacing.standard)
                            .padding(.vertical, Theme.Spacing.medium)
                            .background(selectedSubTab == idx ? Theme.securityGold.opacity(0.08) : Color.clear)
                    }
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
        .scrollIndicators(.hidden)
        .background(Theme.canvasDeep)
    }

    // MARK: Sub-tab content

    @ViewBuilder
    private var subTabContent: some View {
        switch selectedSubTab {
        case 0: technicalTrendsTab
        case 1: sectorsTab
        case 2: topGainersTab
        case 3: topLosersTab
        case 4: activeByValueTab
        case 5: activeByVolumeTab
        default: comingSoonTab(subTabs[selectedSubTab])
        }
    }

    // MARK: 9.3 / 9.4 / 9.5 Technical Trends Tab

    private var technicalTrendsTab: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                // 9.3 Radio Button Momentum Filters
                momentumFilterRow

                if isLoading {
                    ForEach(0..<5, id: \.self) { _ in momentumCardPlaceholder }
                } else {
                    let tickers = momentumTickers(for: selectedMomentum)
                    if tickers.isEmpty {
                        Text(dashboardError ?? "No \(selectedMomentum.lowercased()) signals detected.")
                            .font(Theme.officialStampFont(size: 12))
                            .foregroundStyle(Theme.inkTertiary)
                            .padding(Theme.Spacing.xLarge)
                            .frame(maxWidth: .infinity)
                    } else {
                        ForEach(tickers) { ticker in
                            MomentumIndicatorCard(ticker: ticker, momentum: selectedMomentum)
                        }
                    }
                }
            }
            .padding(Theme.screenPadding)
        }
        .background(Theme.canvas)
    }

    // 9.3 Radio Button Selection Controls
    private var momentumFilterRow: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("MOMENTUM FILTER")
                .font(Theme.officialStampFont(size: 10))
                .tracking(1.5)
                .foregroundStyle(Theme.inkSecondary)

            HStack(spacing: Theme.Spacing.medium) {
                ForEach(momentumFilters, id: \.self) { filter in
                    Button(action: { HapticManager.selection(); selectedMomentum = filter }) {
                        HStack(spacing: Theme.Spacing.tight) {
                            // Radio circle
                            ZStack {
                                Circle()
                                    .stroke(momentumColor(filter).opacity(0.5), lineWidth: 1.5)
                                    .frame(width: Theme.Spacing.standard, height: Theme.Spacing.standard)
                                if selectedMomentum == filter {
                                    Circle()
                                        .fill(momentumColor(filter))
                                        .frame(width: 7, height: 7)
                                }
                            }
                            Text(filter)
                                .font(Theme.officialStampFont(size: 10))
                                .fontWeight(selectedMomentum == filter ? .bold : .regular)
                                .foregroundStyle(selectedMomentum == filter ? momentumColor(filter) : Theme.inkTertiary)
                        }
                        .padding(.horizontal, Theme.Spacing.medium)
                        .padding(.vertical, Theme.Spacing.tight)
                        .background(selectedMomentum == filter ? momentumColor(filter).opacity(0.08) : Color.clear)
                        .cornerRadius(Theme.CornerRadius.tight)
                        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(
                            selectedMomentum == filter ? momentumColor(filter).opacity(0.3) : Theme.borderSage,
                            lineWidth: 0.5))
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func momentumColor(_ filter: String) -> Color {
        switch filter {
        case "Bullish": return Theme.bullGreen
        case "Turning Bullish": return Theme.bullGreen.opacity(0.7)
        case "Bearish": return Theme.bearRed
        default: return Theme.bearRed.opacity(0.7)
        }
    }

    private func momentumTickers(for filter: String) -> [MomentumTicker] {
        switch filter {
        case "Bullish", "Turning Bullish":
            return dashboard?.momentum?.bullish ?? []
        case "Bearish", "Turning Bearish":
            return dashboard?.momentum?.bearish ?? []
        default:
            return []
        }
    }

    // MARK: Sectors Tab

    private var sectorsTab: some View {
        ScrollView {
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.medium) {
                if let pulse = dashboard?.pulse {
                    // Fallback: show advance/decline breadth block
                    let total = pulse.advances + pulse.declines
                    let advPct = total > 0 ? Double(pulse.advances) / Double(total) : 0.5
                    SectorHeatBlock(name: "Advances", pct: advPct * 100, isPositive: true)
                    SectorHeatBlock(name: "Declines", pct: Double(pulse.declines) / Double(total) * 100, isPositive: false)
                } else {
                    ForEach(0..<6, id: \.self) { _ in sectorPlaceholder }
                }
            }
            .padding(Theme.Spacing.card)
        }
        .background(Theme.canvas)
    }

    // MARK: Top Gainers Tab (tab 2)

    private var topGainersTab: some View {
        topMoversListTab(title: "TOP GAINERS", items: topMovers?.gainers, isLoading: isLoadingMovers, positive: true)
    }

    // MARK: Top Losers Tab (tab 3)

    private var topLosersTab: some View {
        topMoversListTab(title: "TOP LOSERS", items: topMovers?.losers, isLoading: isLoadingMovers, positive: false)
    }

    // MARK: Active by Value Tab (tab 4)

    private var activeByValueTab: some View {
        topMoversListTab(title: "ACTIVE BY VALUE", items: topMovers?.activeByValue, isLoading: isLoadingMovers, valueMode: true)
    }

    // MARK: Active by Volume Tab (tab 5)

    private var activeByVolumeTab: some View {
        topMoversListTab(title: "ACTIVE BY VOLUME", items: topMovers?.activeByVolume, isLoading: isLoadingMovers, volumeMode: true)
    }

    private func topMoversListTab(
        title: String,
        items: [TopMover]?,
        isLoading: Bool,
        positive: Bool = true,
        valueMode: Bool = false,
        volumeMode: Bool = false
    ) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                Text(title)
                    .font(Theme.officialStampFont(size: 10))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkSecondary)
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, Theme.Spacing.card)

                if isLoading {
                    ForEach(0..<8, id: \.self) { _ in
                        moverRowPlaceholder
                            .padding(.horizontal, Theme.screenPadding)
                    }
                } else if let list = items, !list.isEmpty {
                    ForEach(Array(list.enumerated()), id: \.element.id) { rank, mover in
                        TopMoverRow(
                            rank: rank + 1,
                            mover: mover,
                            valueMode: valueMode,
                            volumeMode: volumeMode
                        )
                        .padding(.horizontal, Theme.screenPadding)
                    }
                } else {
                    Text(moversError ?? "No data available.")
                        .font(Theme.officialStampFont(size: 12))
                        .foregroundStyle(Theme.inkTertiary)
                        .padding(Theme.Spacing.xLarge)
                        .frame(maxWidth: .infinity)
                }
            }
            .padding(.bottom, Theme.Spacing.xLarge)
        }
        .background(Theme.canvas)
    }

    private var moverRowPlaceholder: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return HStack(spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.07, height: 12)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: UIScreen.main.bounds.width * 0.22, height: 14)
            Spacer()
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.20, height: 12)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.14, height: 12)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }

    // MARK: Data load — top movers

    private func loadTopMovers() async {
        guard topMovers == nil else { return }
        isLoadingMovers = true
        moversError = nil
        do {
            topMovers = try await NetworkManager.shared.fetchTopMovers()
        } catch {
            moversError = error.localizedDescription
        }
        isLoadingMovers = false
    }

    private var comingSoonTab: some View { EmptyView() }
    private func comingSoonTab(_ label: String) -> some View {
        VStack {
            Spacer()
            Text(label)
                .font(Theme.officialStampFont(size: 14))
                .foregroundStyle(Theme.inkTertiary)
            Spacer()
        }
    }

    // MARK: Placeholders

    private var momentumCardPlaceholder: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return HStack(spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: UIScreen.main.bounds.width * 0.2, height: 14)
            Spacer()
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.17, height: 12)
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small).fill(Theme.inkTertiary.opacity(0.10)).frame(width: colW * 0.11, height: 12)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }

    private var sectorPlaceholder: some View {
        RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
            .fill(Theme.inkTertiary.opacity(0.08))
            .frame(height: UIScreen.main.bounds.width * 0.5)
            .shimmerPlaceholder(isLoading: true)
    }

    // MARK: Data Load

    private func loadDashboard() async {
        isLoading = true
        dashboardError = nil
        do {
            dashboard = try await NetworkManager.shared.fetchDashboardPulse()
        } catch {
            dashboardError = error.localizedDescription
        }
        isLoading = false
    }
}

// MARK: - 9.4 Momentum Indicator Card

struct MomentumIndicatorCard: View {
    let ticker: MomentumTicker
    let momentum: String
    @State private var showAnalysis = false

    private var momentumLabel: String {
        switch momentum {
        case "Bullish": return "Very Bullish"
        case "Turning Bullish": return "Turning Bullish"
        case "Bearish": return "Very Bearish"
        default: return "Turning Bearish"
        }
    }

    private var signalColor: Color {
        momentum.contains("Bullish") ? Theme.bullGreen : Theme.bearRed
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                HStack(spacing: Theme.Spacing.medium) {
                    Text(ticker.ticker)
                        .font(Theme.serialNumberFont(size: 14))
                        .foregroundStyle(Theme.inkPrimary)
                    // 9.4 Momentum classification badge
                    Text(momentumLabel.uppercased())
                        .font(Theme.serialNumberFont(size: 8))
                        .tracking(1)
                        .foregroundStyle(signalColor)
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .background(signalColor.opacity(0.10))
                        .cornerRadius(Theme.CornerRadius.small)
                }
                // 9.4 Core execution data
                HStack(spacing: Theme.Spacing.standard) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("LTP").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                        Text(IndianFormatter.price(ticker.lastPrice))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 12))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("MA20").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                        Text(IndianFormatter.price(ticker.ma20))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 11))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("SINCE").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                        Text(ticker.trendDate)
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }
            }

            Spacer()

            // 9.4 / 9.5 Sparkline mini-chart
            if !ticker.sparkline.isEmpty {
                SparklineView(values: ticker.sparkline, color: signalColor)
                    .frame(width: UIScreen.main.bounds.width * 0.16, height: UIScreen.main.bounds.width * 0.10)
            }

            // 9.6 View in Chart button — navigates to AnalysisScreen for this ticker
            Button(action: {
                HapticManager.selection()
                showAnalysis = true
            }) {
                VStack(spacing: Theme.Spacing.xSmall) {
                    Image(systemName: "chart.xyaxis.line")
                        .font(Theme.officialStampFont(size: 13))
                        .foregroundStyle(Theme.securityGold)
                    Text("Chart")
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundStyle(Theme.securityGold.opacity(0.7))
                }
            }
            .buttonStyle(EKPressStyle())
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
        .sheet(isPresented: $showAnalysis) {
            NavigationStack {
                AnalysisScreen(ticker: ticker.ticker)
            }
        }
    }
}

// MARK: - Sector Heat Block (for 9.2 Sectors tab)

struct SectorHeatBlock: View {
    let name: String
    let pct: Double
    let isPositive: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text(name)
                .font(Theme.officialStampFont(size: 11))
                .foregroundStyle(Theme.inkPrimary)
            Text(String(format: "%.1f%%", pct))
                .font(Theme.serialNumberFont(size: 18))
                .foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(isPositive ? Theme.bullGreen.opacity(0.06) : Theme.bearRed.opacity(0.06))
        .cornerRadius(Theme.CornerRadius.medium)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(isPositive ? Theme.bullGreen.opacity(0.2) : Theme.bearRed.opacity(0.2), lineWidth: 0.5)
        )
    }
}

// MARK: - Top Mover Row (Section 9 — Gainers/Losers/Active tabs)

struct TopMoverRow: View {
    let rank: Int
    let mover: TopMover
    var valueMode: Bool = false
    var volumeMode: Bool = false

    @State private var showAnalysis = false

    private var isPositive: Bool { mover.changePct >= 0 }
    private var changeColor: Color { isPositive ? Theme.bullGreen : Theme.bearRed }

    var body: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        HStack(spacing: Theme.Spacing.standard) {
            // Rank badge
            Text("#\(rank)")
                .font(Theme.serialNumberFont(size: 11))
                .foregroundStyle(Theme.inkTertiary)
                .frame(width: colW * 0.08, alignment: .trailing)

            // Ticker + submetric
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(mover.ticker)
                    .font(Theme.serialNumberFont(size: 14))
                    .foregroundStyle(Theme.inkPrimary)
                if volumeMode {
                    Text("\(IndianFormatter.count(Double(mover.volume))) shares")
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                } else if valueMode {
                    Text(IndianFormatter.priceCompact(mover.value))
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }

            Spacer()

            // Price + change
            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text(IndianFormatter.price(mover.price))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundStyle(Theme.inkPrimary)
                HStack(spacing: Theme.Spacing.xSmall) {
                    Text(IndianFormatter.percent(mover.changePct))
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                        .font(Theme.serialNumberFont(size: 11))
                        .foregroundStyle(changeColor)
                    Text(IndianFormatter.delta(mover.changeAbs))
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundStyle(changeColor.opacity(0.7))
                }
            }

            // Chart shortcut
            Button(action: {
                HapticManager.selection()
                showAnalysis = true
            }) {
                Image(systemName: "chart.xyaxis.line")
                    .font(Theme.officialStampFont(size: 13))
                    .foregroundStyle(Theme.securityGold.opacity(0.7))
            }
            .buttonStyle(EKPressStyle())
            .accessibilityLabel("Open chart for \(mover.ticker)")
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
        .sheet(isPresented: $showAnalysis) {
            NavigationStack {
                AnalysisScreen(ticker: mover.ticker)
            }
        }
    }
}

// MARK: - Preview

#Preview("Technical Momentum") {
    TechnicalMomentumView()
}
