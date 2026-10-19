import SwiftUI
import Combine

/// One analysis run as the user asked for it, kept so Retry replays the same tier and settings.
struct AnalysisRequest: Equatable {
    let ticker: String
    let deepScan: Bool
    let scanType: String
    let language: String?
    let debateRounds: Int?

    /// Maps the Settings picker values to the request fields: English is the server default (nil).
    static func from(ticker: String, scanType: String, deepScan: Bool, languageSetting: String, roundsSetting: String) -> AnalysisRequest {
        AnalysisRequest(ticker: ticker, deepScan: deepScan, scanType: scanType,
                        language: languageSetting == "English" ? nil : languageSetting,
                        debateRounds: Int(roundsSetting))
    }
}

/// State for an archived report from the previous engine. New reports come from the
/// Research Engine (`ResearchReportView`); this model no longer starts or polls jobs.
/// The static policies below are still used by `AnalysisEngineManager`'s watcher.
@MainActor
class AnalysisViewModel: ObservableObject {
    @Published var analysis: StockAnalysis? = nil
    @Published var quickInfo: QuickInfo? = nil

    /// What AnalysisScreen does on appear when it was NOT launched from the
    /// action hub (holding rows, Home, Search, Earnings push it directly).
    enum AutoStart: Equatable { case idle, showCached, promptCached, fetch }

    /// Never starts a paid job just because the screen appeared: without a
    /// saved report the screen goes idle and waits for an explicit "Run analysis".
    static func autoStart(forceCached: Bool, hasCached: Bool, autoRegenerateStale: Bool, cachedIsStale: Bool) -> AutoStart {
        guard hasCached else { return .idle }
        if forceCached { return .showCached }
        if autoRegenerateStale && cachedIsStale { return .fetch }  // explicit opt-in setting
        return .promptCached
    }

    /// How to treat the POST /analyze response.
    enum StartOutcome: Equatable { case cached, attach(String), conflict(String), unexpected }

    static func classify(_ start: StartJobResponse, ticker: String) -> StartOutcome {
        if start.analysis != nil { return .cached }
        if let jid = start.jobId, start.status == "QUEUED" || start.status == "RUNNING" { return .attach(jid) }
        if start.errorCode == "ALREADY_RUNNING" {
            // The 409 is keyed on user + scan type, not ticker: only attach to a
            // job for this same ticker, never show another stock's result here.
            if let jid = start.jobId, start.ticker?.uppercased() == ticker.uppercased() { return .attach(jid) }
            return .conflict(start.ticker ?? "another stock")
        }
        return .unexpected
    }

    // MARK: - Job polling policy (AnalysisEngineManager)

    /// What a failed job poll means for the loop.
    enum PollOutcome: Equatable { case retry, terminal(String) }

    static let jobLostMessage = "This analysis is no longer available. Start a new one."
    static let maxPollFailures = 8
    static let maxPollDuration: TimeInterval = 30 * 60

    /// 401/403/404/422 mean the job is gone or not this user's: polling again cannot succeed.
    /// Network errors and 5xx are transient and retried with backoff.
    static func pollOutcome(for error: Error) -> PollOutcome {
        switch error as? NetworkError {
        case .serverError(let code, _)? where [401, 403, 404, 422].contains(code):
            return .terminal(jobLostMessage)
        case .unauthorized?:
            return .terminal(jobLostMessage)
        default:
            return .retry
        }
    }

    /// Delay before the next poll: 2 s, doubling per consecutive failure, capped at 15 s.
    static func pollDelay(consecutiveFailures: Int) -> UInt64 {
        let seconds: UInt64 = consecutiveFailures >= 3 ? 15 : 2 << UInt64(max(consecutiveFailures, 0))
        return seconds * 1_000_000_000
    }

    /// Price/header data for the archived view only; no analysis job.
    func loadQuickInfo(ticker: String) {
        Task { quickInfo = await NetworkManager.shared.quickInfo(ticker: ticker) }
    }
}

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

// MARK: - Macro Impact Banner

private struct MacroImpactBanner: View {
    let impacts: [MacroImpactItem]

    var body: some View {
        ScrollView(.horizontal) {
            HStack(spacing: Theme.Spacing.medium) {
                ForEach(impacts) { item in
                    MacroImpactChip(item: item)
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
        .scrollIndicators(.hidden)
    }
}

private struct MacroImpactChip: View {
    let item: MacroImpactItem

    var chipColor: Color {
        switch item.direction ?? "neutral" {
        case "positive": return Theme.signalEmerald
        case "negative": return Theme.signalRuby
        default: return Theme.canvasDeep
        }
    }

    var directionArrow: String {
        switch item.direction ?? "neutral" {
        case "positive": return "↑"
        case "negative": return "↓"
        default: return "→"
        }
    }

    var shortImpact: String {
        let words = (item.impactStatement ?? "").split(separator: " ")
        return words.prefix(6).joined(separator: " ")
    }

    var textColor: Color {
        switch item.direction ?? "neutral" {
        case "positive", "negative": return .white
        default: return .primary
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            HStack(spacing: Theme.Spacing.xSmall) {
                Text(item.ticker)
                    .font(Theme.monoTabular(size: 11, relativeTo: .caption2).weight(.bold))
                Text(directionArrow)
                    .font(.caption2)
            }
            .foregroundStyle(textColor)
            Text(shortImpact)
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                .foregroundStyle(textColor.opacity(0.85))
                .lineLimit(1)
        }
        .padding(.horizontal, Theme.Spacing.medium)
        .padding(.vertical, Theme.Spacing.tight)
        .background(chipColor.opacity(0.8))
        .cornerRadius(Theme.CornerRadius.tight)
    }
}

// MARK: - Macro Chip

private struct MacroChip: View {
    let label: String
    let value: String
    let color: Color
    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 7))
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 11))
                .foregroundStyle(color)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Spacing.medium)
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

// MARK: - Key Factor Card

private struct KeyFactorCard: View {
    let icon: String
    let title: String
    let hindiTitle: String
    let text: String
    let color: Color
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack(spacing: Theme.Spacing.medium) {
                Image(systemName: icon)
                    .font(.subheadline)
                    .foregroundStyle(color)
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(hindiTitle)
                        .font(Theme.hindiFont(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                    Text(title)
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundStyle(Theme.inkPrimary)
                }
            }
            GuillocheDivider()
            Text(text)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(Theme.inkSecondary)
                .lineSpacing(4)
        }
        .padding(Theme.Spacing.card)
        .background(color.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(color.opacity(0.2), lineWidth: 0.8))
    }
}

// MARK: - Perforation Bar (dotted confidence indicator)

private struct PerforationBar: View {
    let percent: Int

    var body: some View {
        HStack(spacing: Theme.Spacing.xSmall) {
            ForEach(0..<20, id: \.self) { i in
                let threshold = Double(i + 1) / 20.0 * 100.0
                Circle()
                    .fill(Double(percent) >= threshold ? Theme.securityGold : Theme.inkSecondary.opacity(0.15))
                    .frame(width: 6, height: 6)
            }
        }
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

// MARK: - Horizon Note Card

private struct HorizonNoteCard: View {
    let label: String
    let target: Double
    let upside: Double
    var isFeatured: Bool = false

    var body: some View {
        GeometryReader { geo in
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text(label.uppercased())
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(Theme.inkSecondary)

                Text(target.inrFormatted)
                    .font(Theme.serialNumberFont(size: 18))
                    .foregroundStyle(Theme.inkPrimary)

                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: upside >= 0 ? "arrow.up.right" : "arrow.down.right")
                    Text("\(upside.percentFormatted)")
                }
                .font(Theme.serialNumberFont(size: 11))
                .foregroundStyle(upside >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
            .padding(Theme.Spacing.card)
            .frame(width: geo.size.width * 0.33)
            .banknoteCard()
        }
        .overlay(
            VStack {
                if isFeatured {
                    Rectangle().fill(Theme.securityGold).frame(height: 2)
                    Spacer()
                }
            }
        )
    }
}

// MARK: - Analysis Note Section (bull/bear/risk)

private struct AnalysisNoteSection: View {
    let title: String
    let items: [String]
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(Theme.inkPrimary)

            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                ForEach(items, id: \.self) { item in
                    HStack(alignment: .top, spacing: Theme.Spacing.standard) {
                        Rectangle()
                            .fill(color.opacity(0.5))
                            .frame(width: 2, height: 14)
                            .padding(.top, Theme.Spacing.small)
                        Text(item)
                            .font(.subheadline.weight(.medium))
                            .foregroundStyle(Theme.inkSecondary)
                            .lineSpacing(4)
                    }
                }
            }
        }
        .padding(Theme.Spacing.large)
        .banknoteCard()
        .overlay(
            HStack(spacing: Theme.Spacing.none) {
                Rectangle()
                    .fill(color.opacity(0.25))
                    .frame(width: 2)
                Spacer()
            }
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        )
    }
}

// MARK: - Stat Note Cell

private struct StatNoteCell: View {
    let label: String
    let value: String
    @State private var showGlossary = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            HStack(spacing: Theme.Spacing.small) {
                Text(label)
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(Theme.inkSecondary)
                Image(systemName: "questionmark.circle")
                    .font(.caption2)
                    .foregroundStyle(Theme.inkTertiary.opacity(0.6))
            }
            Text(value)
                .font(Theme.serialNumberFont(size: 16))
                .foregroundStyle(Theme.inkPrimary)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
        .onLongPressGesture(minimumDuration: 0.4) {
            HapticManager.impact(.medium)
            showGlossary = true
        }
        .sheet(isPresented: $showGlossary) {
            GlossarySheet(term: label)
        }
    }
}

// MARK: - Confidence Card

private struct ConfidenceCard: View {
    let percent: Int

    private var label: String {
        switch percent {
        case 80...100: return "High Confidence"
        case 60..<80:  return "Moderate Confidence"
        case 40..<60:  return "Uncertain"
        default:       return "Low Confidence"
        }
    }
    private var color: Color {
        switch percent {
        case 70...100: return Theme.bullGreen
        case 50..<70:  return Theme.holdAmber
        default:       return Theme.bearRed
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("CONFIDENCE SCORE")
                        .font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkSecondary)
                        .explainableTerm("Confidence Score")
                    Text(label)
                        .font(Theme.engravedSerif(size: 15, weight: .bold)).foregroundStyle(color)
                }
                Spacer()
                Text("\(percent)%")
                    .font(Theme.serialNumberFont(size: 22)).foregroundStyle(color)
            }
            PerforationBar(percent: percent)
            if percent < 50 {
                HStack(spacing: Theme.Spacing.tight) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.caption2).foregroundStyle(Theme.holdAmber)
                    Text("Uncertainty is high. Cross-check before acting.")
                        .font(.caption.weight(.medium)).foregroundStyle(Theme.holdAmber)
                }
            }
        }
        .padding(Theme.Spacing.screen).banknoteCard()
    }
}

// MARK: - Trend Bar (for promoter history)

private struct TrendBar: View {
    let label: String
    let value: Double
    let color: Color
    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(String(format: "%.1f%%", value))
                .font(.caption2.weight(.medium)).foregroundStyle(color)
            GeometryReader { geo in
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(color.opacity(0.25))
                    .frame(width: geo.size.width)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(color)
                    .frame(width: geo.size.width * min(value / 80.0, 1.0))
            }
            .frame(height: 6)
            Text(label).font(.caption2).foregroundStyle(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Valuation Badge

private struct ValuationBadge: View {
    let peVsAvg: PeVsAvg

    private var isAbove: Bool { peVsAvg.pctVsAvg > 0 }
    private var absPct: Double { abs(peVsAvg.pctVsAvg) }
    private var badgeColor: Color { isAbove ? Theme.bearRed : Theme.bullGreen }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: isAbove ? "arrow.up.circle.fill" : "arrow.down.circle.fill")
                .foregroundStyle(badgeColor)
                .font(.body)
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("VALUATION VS HISTORY")
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(Theme.inkSecondary)
                Text("Trading \(String(format: "%.0f", absPct))% \(isAbove ? "above" : "below") 3Y avg valuation")
                    .font(Theme.serialNumberFont(size: 12))
                    .foregroundStyle(badgeColor)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text("NOW").font(Theme.officialStampFont(size: 7)).foregroundStyle(Theme.inkTertiary)
                Text(String(format: "%.1f", peVsAvg.currentPe)).font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkPrimary)
                Text("AVG").font(Theme.officialStampFont(size: 7)).foregroundStyle(Theme.inkTertiary)
                Text(String(format: "%.1f", peVsAvg.avgPe3y)).font(Theme.serialNumberFont(size: 11)).foregroundStyle(Theme.inkSecondary)
            }
        }
        .padding(Theme.Spacing.standard)
        .background(badgeColor.opacity(0.07))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(badgeColor.opacity(0.35), lineWidth: 1))
    }
}

// MARK: - Glossary Sheet

private let glossaryDefinitions: [String: String] = [
    "P/E RATIO": "Price-to-Earnings. How much you pay for ₹1 of company profit. P/E of 20 means you pay ₹20 for every ₹1 earned. Lower can mean cheaper; very high can mean overpriced.",
    "D/E RATIO": "Debt-to-Equity. How much the company borrowed vs what it owns. A D/E of 1 means equal debt and equity. High D/E (above 2) means heavy borrowing — risky if profits fall.",
    "PROMOTER": "The founders or controlling family who own a stake in the company. High promoter holding (above 50%) means they believe in the business. Falling promoter holding is a warning sign.",
    "INSTITUTION": "Foreign Institutional Investors (FIIs) — large global funds. When FIIs increase holding, they're betting the company will grow. Their exits can cause short-term price drops.",
    "DII": "Domestic Institutional Investors — Indian mutual funds and insurance companies. DII buying usually means Indian experts see long-term value.",
    "RSI": "Relative Strength Index (0–100). Above 70: stock is overbought (may pull back). Below 30: oversold (may bounce). Between 30–70: normal range.",
    "CONFIDENCE SCORE": "How certain the AI analysis system is about its signal. Above 70 is reliable. Below 50 means the data is mixed and you should be more cautious.",
    "52W HIGH": "The highest price this stock traded at in the last 52 weeks. Being near the 52W high means the stock is doing well, but there is less room to run before it becomes expensive.",
    "52W LOW": "The lowest price in the last 52 weeks. Being near the 52W low can be a buying opportunity if the business is still strong — but also a sign of trouble if fundamentals weakened.",
    "UPSIDE": "How much the price could go up to reach the target. 30% upside means the AI expects the stock to rise 30% from today's price over the stated time period.",
]

private struct GlossarySheet: View {
    let term: String
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvasDeep.ignoresSafeArea()
                VStack(alignment: .leading, spacing: Theme.Spacing.screen) {
                    Text(term)
                        .font(Theme.engravedSerif(size: 22, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                    GuillocheDivider()
                    Text(glossaryDefinitions[term] ?? "No definition available for this term.")
                        .font(.body.weight(.medium))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineSpacing(6)
                    Spacer()
                }
                .padding(Theme.Spacing.sectionGap)
            }
            .navigationTitle("शब्दावली / Glossary")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }.foregroundStyle(Theme.securityGold).buttonStyle(EKPressStyle())
                }
            }
        }
    }
}

struct AnalysisLimitationsCard: View {
    let disclaimer: String
    @State private var expanded = false
    @AppStorage("analysisLimitationsShownBefore") private var shownBefore = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Button(action: {
                HapticManager.selection()
                withAnimation(.easeInOut(duration: 0.25)) { expanded.toggle() }
            }) {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(Theme.securityGold)
                    Text("HOW TO READ THIS ANALYSIS")
                        .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                    Spacer()
                    Image(systemName: expanded ? "chevron.up" : "chevron.down")
                        .font(.caption2).foregroundStyle(Theme.inkTertiary)
                }
            }
            .buttonStyle(.plain)

            if expanded || !shownBefore {
                VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                    Text("⚠️ AI cannot predict black swan events. Geopolitical shocks — wars, sanctions, pandemics — are outside this model's scope. These have caused real losses for investors in the past.")
                        .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.bearRed.opacity(0.9))

                    Text("This analysis weights Indian market factors: promoter behaviour, FII/DII flows, retail sentiment, and news momentum. It is not a substitute for your own judgment.")
                        .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkSecondary)

                    Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)

                    Text(disclaimer)
                        .font(Theme.serialNumberFont(size: 9)).foregroundStyle(Theme.inkTertiary)
                }
                .onAppear { shownBefore = true }
            }
        }
        .padding(Theme.Spacing.card).banknoteCard()
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
