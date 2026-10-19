import SwiftUI
import Combine

/// Entry point for a stock's report from every screen and the `nivesh://analyze/{SYMBOL}`
/// deep link. It renders the Research Engine's `ResearchReportView`: opening it starts no
/// job (IOSUI-09) and saves nothing to History. Only an explicit "cached" launch opens a
/// report saved on this device by the previous engine, in the old (archived) view.
struct AnalysisScreen: View {
    let ticker: String
    var forceCached: Bool = false
    /// `.cached` (from StockActionHubView) opens the archived saved report, if any.
    var launchMode: AnalysisLaunchMode? = nil
    var userNote: String? = nil
    var purchaseDateStr: String? = nil
    var portfolioHolding: PortfolioHolding? = nil

    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var reportManager: LocalReportManager
    @StateObject private var viewModel = AnalysisViewModel()
    @AppStorage("nivesh_defaultChartRange") private var defaultChartRange: String = "1M"
    // Extreme result: 0 = AI report, 1 = full stock profile (embedded verbatim).
    @State private var extremeViewMode = 0

    @Environment(\.scenePhase) private var scenePhase
    @State private var livePrice: Double? = nil
    @State private var pricePollingTask: Task<Void, Never>? = nil
    @State private var pricePollPausedInBackground = false
    @State private var previousAnalysis: StockAnalysis? = nil

    // Immersive hero chart (1y price history, fetched once on appear)
    @State private var heroPrices: [Double] = []
    @State private var heroDates: [Date] = []
    @State private var heroLoading = false
    @State private var heroPeriod = ""

    // Retained copy of analysis to prevent EXC_BAD_ACCESS from view model dealloc
    @State private var retainedAnalysis: StockAnalysis? = nil

    private var opensArchivedReport: Bool { forceCached || launchMode == .cached }

    var body: some View {
            ZStack {
                Theme.canvas.ignoresSafeArea()

                if let analysis = retainedAnalysis {
                    renderFullAnalysis(analysis)
                } else {
                    ResearchReportView(symbol: ticker)
                }
            }
            // App-owned back button that also restores the edge-swipe pop gesture.
            .banknoteBackButton { dismiss() }
            .toolbar {
            ToolbarItem(placement: .principal) {
                Text(retainedAnalysis == nil ? "Stock report" : ticker)
                    .font(.headline.weight(.bold))
                    .foregroundStyle(Theme.inkPrimary)
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                HStack(spacing: Theme.Spacing.medium) {
                    NavigationLink(value: StockProfileDest(ticker: ticker, exchange: portfolioHolding?.stock.exchange ?? "NSE")) {
                        Image(systemName: "doc.text.magnifyingglass")
                            .foregroundStyle(Theme.securityGold)
                    }
                    .buttonStyle(EKPressStyle())
                    .accessibilityLabel("Stock profile")
                    // Archived view only: price + ChangeBadge inline on the right
                    if retainedAnalysis != nil, let info = viewModel.quickInfo {
                        Text(IndianFormatter.price(livePrice ?? info.price))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkPrimary)
                        if let pct = info.changePercent {
                            ChangeBadge(value: pct)
                        }
                    }
                    if retainedAnalysis != nil {
                        Button {
                            HapticManager.selection()
                            shareAsImage()
                        } label: {
                            Image(systemName: "square.and.arrow.up")
                                .foregroundStyle(Theme.inkPrimary)
                        }
                        .accessibilityLabel("Share as Image")
                    }
                }
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .onAppear {
            guard viewModel.analysis == nil, opensArchivedReport,
                  let saved = reportManager.getReport(for: ticker) else { return }
            previousAnalysis = saved
            viewModel.analysis = saved
            if heroPeriod.isEmpty {
                heroPeriod = ["1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y"][defaultChartRange] ?? "1y"
            }
            viewModel.loadQuickInfo(ticker: ticker)
            startPricePolling()
            fetchHeroHistory(period: heroPeriod)
        }
        // No price polling while the app is in the background (PERF-22).
        .onChange(of: scenePhase) { _, phase in
            if phase == .background, pricePollingTask != nil {
                pricePollingTask?.cancel(); pricePollingTask = nil
                pricePollPausedInBackground = true
            } else if phase == .active, pricePollPausedInBackground {
                pricePollPausedInBackground = false
                startPricePolling()
            }
        }
        .onReceive(viewModel.$analysis) { newValue in
            retainedAnalysis = newValue
        }
        .onDisappear {
            pricePollingTask?.cancel()
            pricePollingTask = nil
        }
    }

    // MARK: - Immersive hero chart

    private func fetchHeroHistory(period: String = "1y") {
        heroLoading = true
        Task {
            let hist = await NetworkManager.shared.fetchStockHistory(ticker: ticker, exchange: "NSE", period: period)
            await MainActor.run {
                if let hist = hist, !hist.prices.isEmpty {
                    heroPrices = hist.prices.map(\.close)
                    heroDates = hist.prices.map(\.parsedDate)
                }
                heroLoading = false
            }
        }
    }

    // MARK: - Live price polling

    private func startPricePolling() {
        pricePollingTask?.cancel()
        let exchange = "NSE"
        pricePollingTask = Task {
            while !Task.isCancelled {
                // The server caches quick-info for 15 min, so a 30 s poll mostly re-downloaded
                // identical data (PERF-22).
                try? await Task.sleep(nanoseconds: 300_000_000_000) // 5 min
                guard !Task.isCancelled else { return }
                if let info = await NetworkManager.shared.quickInfo(ticker: ticker, exchange: exchange) {
                    livePrice = info.price
                }
            }
        }
    }

    // MARK: - Share as Image

    private func shareAsImage() {
        guard let analysis = viewModel.analysis else { return }

        let viewToRender = ZStack {
            Theme.canvas.ignoresSafeArea()
            DenominationBackground(denomination: .hundred)
            BanknoteWatermark(text: "CONFIDENTIAL", size: 100, opacity: 0.018, alignment: .center)

            VStack(spacing: Theme.Spacing.sectionGap) {
                AnalysisCoreSections(analysis: analysis, previousAnalysis: previousAnalysis, ticker: ticker, livePrice: livePrice, viewModel: viewModel)
                if analysis.analysisTier == "extreme" {
                    AnalysisExtremeSections(analysis: analysis, previousAnalysis: previousAnalysis, viewModel: viewModel)
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, Theme.Spacing.standard)
            .padding(.bottom, Theme.Spacing.large)
        }
        .frame(width: UIScreen.main.bounds.width)

        let renderer = ImageRenderer(content: viewToRender)
        renderer.scale = UIScreen.main.scale

        if let uiImage = renderer.uiImage {
            let avc = UIActivityViewController(activityItems: [uiImage], applicationActivities: nil)
            if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
               let rootVC = windowScene.windows.first(where: { $0.isKeyWindow })?.rootViewController {
                avc.popoverPresentationController?.sourceView = rootVC.view
                avc.popoverPresentationController?.sourceRect = CGRect(x: UIScreen.main.bounds.midX, y: UIScreen.main.bounds.midY, width: 0, height: 0)
                rootVC.present(avc, animated: true)
            }
        }
    }

    // MARK: - Archived report

    private func renderFullAnalysis(_ analysis: StockAnalysis) -> some View {
        AnalysisFullView(
            analysis: analysis,
            previousAnalysis: previousAnalysis,
            ticker: ticker,
            livePrice: livePrice,
            viewModel: viewModel,
            extremeViewMode: $extremeViewMode,
            heroPrices: heroPrices,
            heroDates: heroDates,
            heroLoading: heroLoading,
            heroPeriod: $heroPeriod,
            onPeriodChange: { period in fetchHeroHistory(period: period) }
        )
    }
}

// MARK: - Analysis Metric Cell (Screen C 3-col grid)

struct AnalysisMetricCell: View {
    let label: String
    let term: String
    let value: String

    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 8)).tracking(1.2)
                .foregroundStyle(Theme.inkTertiary)
                .explainableTerm(term)
            Text(value)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .footnote).weight(.bold))
                .foregroundStyle(Theme.inkPrimary)
                .lineLimit(1).minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.small)
        .banknoteCard()
    }
}

// MARK: - News Item Card

struct NewsItemCard: View {
    let item: NewsItem
    let onTap: () -> Void

    var body: some View {
        Button {
            HapticManager.impact(.light)
            onTap()
        } label: {
            HStack(spacing: Theme.Spacing.card) {
                if let urlStr = item.imageUrl, let url = URL(string: urlStr) {
                    AsyncImage(url: url) { image in
                        image.resizable().aspectRatio(contentMode: .fill)
                    } placeholder: {
                        Rectangle().fill(Theme.inkSecondary.opacity(0.1))
                    }
                    .frame(width: UIScreen.main.bounds.width * 0.20, height: UIScreen.main.bounds.width * 0.20)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                    Text(item.title)
                        .font(Theme.engravedSerif(size: 15, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                        .lineLimit(3)
                        .multilineTextAlignment(.leading)

                    HStack {
                        Text(item.publisher.uppercased())
                            .font(Theme.officialStampFont(size: 8))
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.caption2)
                    }
                    .foregroundStyle(Theme.inkSecondary)
                }
            }
            .padding(Theme.Spacing.standard)
            .banknoteCard()
        }
        .buttonStyle(.plain)
    }
}

// MARK: - News Section (extracted per AGENTS.md §6.6 — owns single hoisted cover)

struct NewsSectionView: View {
    let news: [NewsItem]
    @State private var selectedNews: NewsItem?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            GuillocheDivider()
            HStack {
                Text("RECENT NEWS")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkSecondary)
                Spacer()
                Text("\(news.count) articles")
                    .font(Theme.microLabel(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
            }
            ForEach(news.prefix(5)) { item in
                NewsItemCard(item: item) { selectedNews = item }
            }
        }
        .fullScreenCover(item: $selectedNews) { item in
            NewsReaderView(item: item)
        }
    }
}

// MARK: - News Reader View

struct NewsReaderView: View {
    let item: NewsItem
    @Environment(\.dismiss) var dismiss

    var body: some View {
            NavigationStack {
                ScrollView {
                    VStack(alignment: .leading, spacing: Theme.Spacing.screen) {
                        // Hero Image (proportional height — no GeometryReader per AGENTS.md §2.5/§6.6)
                        if let urlStr = item.imageUrl, let url = URL(string: urlStr) {
                            AsyncImage(url: url) { image in
                                image.resizable().aspectRatio(contentMode: .fill)
                            } placeholder: {
                                Rectangle().fill(Theme.inkSecondary.opacity(0.1))
                            }
                            .frame(height: UIScreen.main.bounds.height * 0.28)
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
                            .padding(.horizontal, Theme.screenPadding)
                        }

                    VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                        Text(item.title)
                            .font(Theme.engravedSerif(size: 24, weight: .bold))
                            .foregroundStyle(Theme.inkPrimary)
                            .lineSpacing(4)

                        HStack {
                            Text(item.publisher.uppercased())
                                .font(Theme.officialStampFont(size: 10))
                                .foregroundStyle(Theme.securityGold)
                            
                            if let time = item.publishTime {
                                Text("•")
                                Text(Date(timeIntervalSince1970: TimeInterval(time)), style: .date)
                            }
                        }
                        .font(Theme.serialNumberFont(size: 11))
                        .foregroundStyle(Theme.inkTertiary)

                        GuillocheDivider()

                        if let summary = item.summary, !summary.isEmpty {
                            Text(summary)
                                .font(Theme.engravedSerif(size: 17, weight: .medium, relativeTo: .headline))
                                .foregroundStyle(Theme.inkSecondary)
                                .lineSpacing(8)
                        } else {
                            Text("Summary not available. Please read the full story for more details.")
                                .italic()
                                .font(Theme.serialNumberFont(size: 14))
                                .foregroundStyle(Theme.inkTertiary)
                        }

                        Group {
                            if let url = SafeURL.web(item.link) {
                                Link(destination: url) {
                                    HStack {
                                        Text("READ FULL STORY ON \(item.publisher.uppercased())")
                                        Image(systemName: "arrow.up.right")
                                    }
                                    .font(Theme.officialStampFont(size: 11))
                                    .foregroundStyle(Theme.canvas)
                                    .padding(.vertical, Theme.Spacing.standard)
                                    .frame(maxWidth: .infinity)
                                    .background(Theme.inkPrimary)
                                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                                }
                            } else {
                                HStack {
                                    Text("READ FULL STORY ON \(item.publisher.uppercased())")
                                    Image(systemName: "link.badge.plus")
                                }
                                .font(Theme.officialStampFont(size: 11))
                                .foregroundStyle(Theme.canvas.opacity(0.5))
                                .padding(.vertical, Theme.Spacing.standard)
                                .frame(maxWidth: .infinity)
                                .background(Theme.inkPrimary.opacity(0.5))
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                            }
                        }
                        .padding(.top, Theme.Spacing.screen)
                    }
                    .padding(.horizontal, Theme.screenPadding)

                    Spacer(minLength: 40)
                }
            }
            .background(Theme.canvasDeep)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button { HapticManager.selection();  dismiss() } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(Theme.inkTertiary)
                            .font(Theme.engravedSerif(size: 24))
                    }
                    .accessibilityLabel("Close")
                }
            }
        }
    }
}

// MARK: - Diagnostic Error Helpers

struct TraceRow: View {
    let label: String
    let value: String

    var body: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return HStack(alignment: .top, spacing: Theme.Spacing.medium) {
            Text(label)
                .font(Theme.serialNumberFont(size: 10))
                .foregroundStyle(Theme.inkTertiary)
                .frame(width: colW * 0.25, alignment: .leading)
            Text(value)
                .font(Theme.serialNumberFont(size: 10))
                .foregroundStyle(Theme.inkSecondary)
                .lineSpacing(3)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct CollapsibleSection<Content: View>: View {
    let header: String
    @ViewBuilder let content: () -> Content
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Button(action: {
                HapticManager.selection()
                withAnimation(.easeInOut(duration: 0.2)) { expanded.toggle() }
            }) {
                HStack(spacing: Theme.Spacing.tight) {
                    Image(systemName: expanded ? "chevron.down" : "chevron.right")
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(Theme.securityGold)
                    Text(header)
                        .font(Theme.serialNumberFont(size: 10))
                        .foregroundStyle(Theme.inkSecondary)
                    Spacer()
                }
            }
            .buttonStyle(.plain)

            if expanded {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    content()
                }
                .padding(.leading, Theme.Spacing.card)
                .padding(.vertical, Theme.Spacing.medium)
                .background(Theme.canvasDeep.opacity(0.5))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
            }
        }
    }
}
// Item 14: MagnificationGesture added in StockCharts.swift
