import SwiftUI
import Combine

@MainActor
class AnalysisViewModel: ObservableObject {
    @Published var analysis: StockAnalysis? = nil
    @Published var quickInfo: QuickInfo? = nil
    @Published var isLoading = false
    @Published var errorInfo: AnalysisErrorInfo? = nil
    @Published var quarterlyFinancials: [QuarterlyFinancial] = []
    @Published var promoterHistory: [PromoterHistoryPoint] = []
    @Published var niftyPrices: [NiftyPricePoint] = []
    @Published var macroStrip: MacroStrip? = nil
    @Published var earningsEvents: [EarningsEvent] = []
    @Published var analystRatings: AnalystRatingsResponse? = nil
    @Published var macroImpacts: [MacroImpactItem] = []

    private var analysisTask: Task<Void, Never>?

    func fetchAnalysis(ticker: String, userId: Int?, useMock: Bool, reportManager: LocalReportManager, deepScan: Bool = false, scanType: String = "standard") {
        analysisTask?.cancel()

        analysisTask = Task {
            isLoading = true
            errorInfo = nil

            let parallelStart = Date()
            async let qi = NetworkManager.shared.quickInfo(ticker: ticker)
            async let qfr = NetworkManager.shared.getQuarterlyFinancialsResponse(ticker: ticker)
            async let nifty = NetworkManager.shared.getNiftyHistory(days: 365)
            async let macro = NetworkManager.shared.getMacroStrip()
            async let earnings = NetworkManager.shared.getEarningsCalendar()
            async let ratings = NetworkManager.shared.getAnalystRatings(ticker: ticker)

            quickInfo = await qi
            let qfResult = await qfr
            quarterlyFinancials = qfResult?.quarters ?? []
            promoterHistory = qfResult?.promoterHistory ?? []
            niftyPrices = await nifty
            macroStrip = await macro
            earningsEvents = await earnings
            self.analystRatings = await ratings

            if let uid = userId {
                self.macroImpacts = (try? await NetworkManager.shared.fetchMacroImpact(userId: uid))?.impacts ?? []
            }

            let quickInfoElapsed = Date().timeIntervalSince(parallelStart)

            if Task.isCancelled { return }

            do {
                let result = try await NetworkManager.shared.analyze(ticker: ticker, userId: userId, useMock: useMock, deepScan: deepScan, scanType: scanType)
                if !Task.isCancelled {
                    self.analysis = result
                    reportManager.saveReport(result)
                }
            } catch is CancellationError {
            } catch {
                if !Task.isCancelled {
                    if let networkError = error as? NetworkError,
                       let diag = networkError.diagnosticInfo {
                        var info = diag
                        info = AnalysisErrorInfo(
                            diagnostic: info.diagnostic,
                            rawError: info.rawError,
                            httpStatusCode: info.httpStatusCode,
                            responseBody: info.responseBody,
                            responseHeaders: info.responseHeaders,
                            requestUrl: info.requestUrl,
                            elapsedSeconds: info.elapsedSeconds,
                            quickInfoElapsed: quickInfoElapsed,
                            isRetryable: info.isRetryable,
                            isMockMode: info.isMockMode,
                            isDeepScan: info.isDeepScan
                        )
                        self.errorInfo = info
                    } else {
                        self.errorInfo = AnalysisErrorInfo(
                            diagnostic: nil,
                            rawError: error.localizedDescription,
                            httpStatusCode: 0,
                            responseBody: "",
                            responseHeaders: "",
                            requestUrl: NetworkManager.shared.baseURL + "/analyze",
                            elapsedSeconds: 0,
                            quickInfoElapsed: quickInfoElapsed,
                            isRetryable: true,
                            isMockMode: useMock,
                            isDeepScan: deepScan
                        )
                    }
                }
            }

            if !Task.isCancelled { isLoading = false }
        }
    }

    func cancelAnalysis() {
        analysisTask?.cancel()
        isLoading = false
    }
}

struct AnalysisScreen: View {
    let ticker: String
    var forceCached: Bool = false
    /// When set (from StockActionHubView), bypasses the legacy "Cached Report
    /// Found" alert and launches the report directly in the chosen mode.
    var launchMode: AnalysisLaunchMode? = nil
    var userNote: String? = nil
    var purchaseDateStr: String? = nil
    var portfolioHolding: PortfolioHolding? = nil

    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var authManager: AuthManager
    @EnvironmentObject var reportManager: LocalReportManager
    @StateObject private var viewModel = AnalysisViewModel()
    @State private var showingRegenerateAlert = false
    @State private var showSetAlertSheet = false
    @State private var activeTab = 0
    @AppStorage("useMockAI") private var useMockAI = false
    @AppStorage("defaultDeepScan") private var defaultDeepScan: Bool = false
    @AppStorage("analysisLastTab") private var savedLastTab: Int = 0
    @State private var deepScanEnabled: Bool = false
    @State private var isAnalyzing = false

    @State private var livePrice: Double? = nil
    @State private var pricePollingTask: Task<Void, Never>? = nil
    @State private var previousAnalysis: StockAnalysis? = nil

    // Immersive hero chart (1y price history, fetched once on appear)
    @State private var heroPrices: [Double] = []
    @State private var heroDates: [Date] = []
    @State private var heroLoading = false
    @State private var heroPeriod = "1y"

    private static let deepScanDisabledTickers: Set<String> = [
        "NIFTY", "SENSEX", "BANKNIFTY", "NIFTYBANK", "INDIAVIX",
    ]

    private let tabs = ["OVERVIEW", "ANALYSIS", "CHARTS", "FUNDAMENTS", "NEWS"]

    private var parsedPurchaseDate: Date? {
        guard let s = purchaseDateStr else { return nil }
        let fmt = DateFormatter()
        for f in ["dd-MMM-yyyy", "yyyy-MM-dd", "MM/dd/yyyy"] {
            fmt.dateFormat = f
            if let d = fmt.date(from: s) { return d }
        }
        return nil
    }

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .hundred)
            BanknoteWatermark(text: "CONFIDENTIAL", size: 100, opacity: 0.018, alignment: .center)

            if let analysis = viewModel.analysis {
                renderFullAnalysis(analysis)
            } else if viewModel.isLoading || showingRegenerateAlert {
                renderLoadingState()
            } else if let errorInfo = viewModel.errorInfo {
                renderErrorState(errorInfo)
            }
        }
        .navigationBarBackButtonHidden(true)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button {
                    viewModel.cancelAnalysis()
                    dismiss()
                } label: {
                    Image(systemName: "chevron.left")
                        .foregroundStyle(Theme.inkPrimary)
                        .padding(Theme.Spacing.medium)
                        .background(Theme.canvasDeep)
                        .clipShape(Circle())
                }
                .accessibilityLabel("Back")
            }
            ToolbarItem(placement: .principal) {
                // Screen C — inline ticker title
                Text(ticker)
                    .font(.headline.weight(.bold))
                    .foregroundStyle(Theme.inkPrimary)
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                HStack(spacing: Theme.Spacing.medium) {
                    // Screen C — price + ChangeBadge inline on the right
                    if let info = viewModel.quickInfo {
                        Text(IndianFormatter.price(livePrice ?? info.price ?? 0))
                            .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkPrimary)
                        ChangeBadge(value: info.changePercent ?? 0)
                    }
                    Button {
                        shareAsImage()
                    } label: {
                        Image(systemName: "square.and.arrow.up")
                            .foregroundStyle(viewModel.analysis != nil ? Theme.inkPrimary : Theme.inkSecondary.opacity(0.3))
                    }
                    .disabled(viewModel.analysis == nil)
                    .accessibilityLabel("Share as Image")
                }
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .onAppear {
            activeTab = savedLastTab
            deepScanEnabled = defaultDeepScan
            if viewModel.analysis == nil && !viewModel.isLoading {
                if let cached = reportManager.getReport(for: ticker) {
                    previousAnalysis = cached
                }

                if let mode = launchMode {
                    // Hub-driven launch: act directly, no alert.
                    switch mode {
                    case .cached:
                        if let cached = previousAnalysis { viewModel.analysis = cached }
                        else { viewModel.fetchAnalysis(ticker: ticker, userId: authManager.currentUser?.userId, useMock: useMockAI, reportManager: reportManager, deepScan: false) }
                    case .regenerate:
                        viewModel.fetchAnalysis(ticker: ticker, userId: authManager.currentUser?.userId, useMock: useMockAI, reportManager: reportManager, deepScan: false)
                    case .deepScan:
                        let forbidden = Self.deepScanDisabledTickers.contains(ticker.uppercased())
                        viewModel.fetchAnalysis(ticker: ticker, userId: authManager.currentUser?.userId, useMock: useMockAI, reportManager: reportManager, deepScan: !forbidden)
                    case .extremeScan:
                        let forbidden = Self.deepScanDisabledTickers.contains(ticker.uppercased())
                        viewModel.fetchAnalysis(ticker: ticker, userId: authManager.currentUser?.userId, useMock: useMockAI, reportManager: reportManager, deepScan: !forbidden, scanType: "extreme")
                    }
                } else if forceCached, let cached = previousAnalysis {
                    viewModel.analysis = cached
                } else if previousAnalysis != nil {
                    showingRegenerateAlert = true
                } else {
                    viewModel.fetchAnalysis(ticker: ticker, userId: authManager.currentUser?.userId, useMock: useMockAI, reportManager: reportManager, deepScan: deepScanEnabled)
                }
            }
            startPricePolling()
            fetchHeroHistory(period: heroPeriod)
        }
        .onChange(of: activeTab) { _, val in savedLastTab = val }
        .onDisappear {
            viewModel.cancelAnalysis()
            pricePollingTask?.cancel()
            pricePollingTask = nil
            // Fix 3.10: Cancel active URLSession tasks when navigating back
            URLSession.shared.getAllTasks { tasks in
                tasks.forEach { $0.cancel() }
            }
        }
        .alert("Cached Report Found", isPresented: $showingRegenerateAlert) {
            // Fix 3.16: Disable Deep Scan for indices and newly listed tickers
            let deepScanForbidden = Self.deepScanDisabledTickers.contains(ticker.uppercased())
            Toggle("Deep Scan (PKScreener + FinBERT)", isOn: $deepScanEnabled)
                .tint(Theme.securityGold)
                .disabled(deepScanForbidden)
                .opacity(deepScanForbidden ? 0.4 : 1.0)
            Button("View Cached") {
                if let cached = reportManager.getReport(for: ticker) {
                    viewModel.analysis = cached
                }
            }
            Button("Regenerate") {
                viewModel.fetchAnalysis(ticker: ticker, userId: authManager.currentUser?.userId, useMock: useMockAI, reportManager: reportManager, deepScan: deepScanEnabled)
            }
        } message: {
            Text("A report for \(ticker) was recently generated. Generating a new one takes time and credits. Do you want to view the existing report or generate a new one?")
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

    @ViewBuilder
    private func heroChartSection(_ analysis: StockAnalysis) -> some View {
        if !heroPrices.isEmpty {
            let price = livePrice ?? viewModel.quickInfo?.price ?? heroPrices.last ?? 0
            let changePct = viewModel.quickInfo?.changePercent ?? 0
            ImmersiveStockHeroChart(
                prices: heroPrices,
                changePercent: changePct,
                currentPrice: price,
                dates: heroDates
            )
            HStack(spacing: Theme.Spacing.tight) {
                ForEach(Array(zip(["1mo","3mo","6mo","1y","2y","5y","max"], ["1M","3M","6M","1Y","2Y","5Y","ALL"])), id: \.0) { period, label in
                    Button {
                        HapticManager.selection()
                        heroPeriod = period
                        fetchHeroHistory(period: period)
                    } label: {
                        Text(label)
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(0.8)
                            .foregroundStyle(heroPeriod == period ? Theme.securityGold : Theme.inkTertiary)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(heroPeriod == period ? Theme.securityGold.opacity(0.12) : Theme.canvasDeep)
                            .clipShape(Capsule())
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
            .padding(.top, Theme.Spacing.standard)
        } else if heroLoading {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                .fill(Theme.inkTertiary.opacity(0.08))
                .frame(height: UIScreen.main.bounds.height * 0.26)
                .shimmerPlaceholder(isLoading: true)
        }
    }

    // MARK: - Live price polling

    private func startPricePolling() {
        pricePollingTask?.cancel()
        let exchange = "NSE"
        pricePollingTask = Task {
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 30_000_000_000) // 30s
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
                stockHeaderSection(analysis)
                aiVerdictCard(analysis)
                dialecticDebateSection(analysis)
                timeHorizonSection(analysis)
                riskFactorsSection(analysis)
                fundamentalsSection(analysis)
                whatToWatchSection(analysis)
                disclaimerSection(analysis)
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

    // MARK: - Loading State (Redesigned)

    @ViewBuilder
    private func renderLoadingState() -> some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.sectionGap) {
                if let info = viewModel.quickInfo {
                    stockHeaderCard(info: info)
                }
                VStack(spacing: Theme.Spacing.screen) {
                    if deepScanEnabled {
                        HStack(spacing: Theme.Spacing.tight) {
                            Image(systemName: "waveform.badge.magnifyingglass")
                                .font(Theme.microLabel())
                            Text("DEEP SCAN ACTIVE")
                                .font(Theme.sectionCapsLabel(size: 8))
                                .tracking(1.5)
                        }
                        .foregroundStyle(Theme.goldPrimary)
                        .padding(.horizontal, Theme.Spacing.standard)
                        .padding(.vertical, Theme.Spacing.tight)
                        .background(Theme.goldMuted.opacity(0.5))
                        .clipShape(Capsule())
                        .overlay(Capsule().stroke(Theme.goldMuted, lineWidth: 0.5))
                    }
                    DialecticProgressView(
                        userId: authManager.currentUser?.userId,
                        ticker: ticker
                    )
                    Button(action: {
                        HapticManager.impact(.rigid)
                        viewModel.cancelAnalysis()
                        dismiss()
                    }) {
                        Text("ABORT PROCESS")
                            .font(Theme.sectionCapsLabel(size: 9))
                            .foregroundStyle(Theme.dataNegative)
                            .padding(.vertical, Theme.Spacing.medium)
                            .padding(.horizontal, Theme.Spacing.screen)
                            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.dataNegative.opacity(0.3), lineWidth: 1))
                    }
                }
                .padding(.top, Theme.Spacing.screen)
                if let info = viewModel.quickInfo {
                    VStack(alignment: .leading, spacing: Theme.Spacing.screen) {
                        SectionHeaderView(title: "COMPANY PROFILE")
                        if let desc = info.description {
                            Text(desc)
                                .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                                .foregroundStyle(Theme.inkSecondary)
                                .lineSpacing(6)
                        }
                        SectionDivider()
                        if let officers = info.officers, !officers.isEmpty {
                            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                                Text("KEY EXECUTIVES")
                                    .font(Theme.sectionCapsLabel(size: 8))
                                    .foregroundStyle(Theme.inkSecondary)
                                ForEach(officers, id: \.self) { officer in
                                    Text("• \(officer.uppercased())")
                                        .font(Theme.monoTabular(size: 13))
                                        .foregroundStyle(Theme.inkPrimary)
                                }
                            }
                        }
                    }
                    .padding(Theme.Spacing.card)
                    .background(Theme.surfaceElevated)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderSubtle, lineWidth: 0.5))
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.bottom, 100)
        }
    }

    // MARK: - Full Analysis (Redesigned)

    @ViewBuilder
    private func renderFullAnalysis(_ analysis: StockAnalysis) -> some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.none) {
                // Immersive hero chart for this specific stock — full-bleed, very top.
                heroChartSection(analysis)
                    .padding(.bottom, Theme.Spacing.standard)

                VStack(spacing: Theme.Spacing.sectionGap) {
                    stockHeaderSection(analysis)
                    aiVerdictCard(analysis)
                if let prev = previousAnalysis, prev.analysisDate != analysis.analysisDate {
                    whatChangedSection(analysis, previous: prev)
                }
                signalTimelineSection(analysis)
                dialecticDebateSection(analysis)
                timeHorizonSection(analysis)
                riskFactorsSection(analysis)
                fundamentalsSection(analysis)
                newsSection(analysis)
                whatToWatchSection(analysis)
                disclaimerSection(analysis)
                Spacer(minLength: 100)
                }
                .padding(.horizontal, Theme.screenPadding)
                .padding(.top, Theme.Spacing.standard)
            }
        }
    }

    // MARK: -- Signal Timeline Section
    @ViewBuilder
    private func signalTimelineSection(_ analysis: StockAnalysis) -> some View {
        if let prices = viewModel.quickInfo?.priceHistory90d, !prices.isEmpty {
            VStack(spacing: Theme.Spacing.standard) {
                SectionHeaderView(title: "SIGNAL ACCURACY TIMELINE")
                AnalysisHistoryTimelineView(ticker: ticker, priceHistory: prices)
            }
        }
    }

    // MARK: -- Stock Header

    private func stockHeaderSection(_ analysis: StockAnalysis) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(analysis.companyName)
                        .font(Theme.engravedSerif(size: 22, weight: .bold, relativeTo: .title2))
                        .foregroundStyle(Theme.inkPrimary).lineLimit(2)
                    HStack(spacing: Theme.Spacing.tight) {
                        Text(analysis.exchange ?? "NSE")
                            .font(Theme.monoTabular(size: 9, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkSecondary)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.surfaceElevated).clipShape(Capsule())
                            .overlay(Capsule().stroke(Theme.goldMuted, lineWidth: 0.5))
                        Text(analysis.ticker)
                            .font(Theme.monoTabular(size: 9, relativeTo: .caption2))
                            .foregroundStyle(Theme.goldPrimary)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.goldMuted).clipShape(Capsule())
                    }
                }
                Spacer()
            }
            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.medium) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.small) {
                        Text("₹")
                            .font(Theme.dataXL(size: 28, relativeTo: .title))
                            .foregroundStyle(Theme.goldPrimary)
                        Text((livePrice ?? analysis.currentPriceInr).inrFormatted.replacingOccurrences(of: "₹", with: ""))
                            .font(Theme.dataXL(size: 38, relativeTo: .largeTitle))
                            .foregroundStyle(Theme.inkPrimary)
                            .contentTransition(.numericText())
                    }
                    if let info = viewModel.quickInfo {
                        HStack(spacing: Theme.Spacing.tight) {
                            Image(systemName: (info.change ?? 0.0) >= 0 ? "arrowtriangle.up.fill" : "arrowtriangle.down.fill")
                                .font(.caption2)
                            Text("\((info.change ?? 0.0) >= 0 ? "+" : "")\((info.change ?? 0.0).inrFormatted)")
                            Text("(\((info.changePercent ?? 0.0).percentFormatted))")
                        }
                        .font(Theme.monoTabular(size: 14, relativeTo: .footnote))
                        .foregroundStyle((info.change ?? 0.0) >= 0 ? Theme.dataPositive : Theme.dataNegative)
                    }
                    if livePrice != nil {
                        HStack(spacing: Theme.Spacing.small) {
                            Circle().fill(Theme.dataPositive).frame(width: 6, height: 6)
                            Text("LIVE").font(Theme.microLabel(size: 9)).foregroundStyle(Theme.dataPositive)
                        }
                    }
                }
                Spacer()
                BanknoteSignalBadge(signal: analysis.signal, rotation: -3).stampAppear()
            }
            if let perf = analysis.pricePerformance {
                HStack(spacing: Theme.Spacing.medium) {
                    pricePerformanceChip(label: "3M", pct: perf.change3mPct)
                    pricePerformanceChip(label: "6M", pct: perf.change6mPct)
                    pricePerformanceChip(label: "1Y", pct: perf.change12mPct)
                    Spacer()
                }
            }
            SectionDivider()
            if let prices = viewModel.quickInfo?.priceHistory90d, !prices.isEmpty {
                PriceHistoryChart(
                    prices: prices,
                    ticker: ticker,
                    week52High: viewModel.quickInfo?.week52High,
                    week52Low: viewModel.quickInfo?.week52Low
                )
                .padding(.horizontal, -Theme.screenPadding)
                .immersiveChartTint(isPositive: (viewModel.quickInfo?.changePercent ?? 0) >= 0)
            }
        }
    }

    private func stockHeaderCard(info: QuickInfo) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            HStack(spacing: Theme.Spacing.card) {
                StockIcon(ticker: info.ticker, signal: info.signal)
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(info.ticker).font(Theme.serialNumberFont(size: 24)).foregroundStyle(Theme.inkPrimary)
                    Text(info.sector ?? info.industry ?? "").font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary)
                }
                Spacer()
            }
            SectionDivider()
            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.small) {
                Text("₹").font(Theme.engravedSerif(size: 24, weight: .bold)).foregroundStyle(Theme.goldPrimary)
                Text((info.price ?? 0.0).inrFormatted.replacingOccurrences(of: "₹", with: ""))
                    .font(Theme.dataLarge()).foregroundStyle(Theme.inkPrimary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            HStack(spacing: Theme.Spacing.medium) {
                Text("\((info.change ?? 0.0) >= 0 ? "+" : "")\((info.change ?? 0.0).inrFormatted)")
                Text("(\((info.changePercent ?? 0.0).percentFormatted))")
            }
            .font(Theme.monoTabular(size: 16))
            .foregroundStyle((info.change ?? 0.0) >= 0 ? Theme.dataPositive : Theme.dataNegative)
        }
        .padding(Theme.Spacing.card)
        .background(Theme.surfaceElevated)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
        .padding(.top, Theme.Spacing.screen)
    }

    // MARK: -- AI Verdict Card (Hero)

    private func aiVerdictCard(_ analysis: StockAnalysis) -> some View {
        VStack(spacing: Theme.Spacing.none) {
            SectionDivider()
            VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                HStack {
                    Text("AI VERDICT").font(Theme.sectionCapsLabel()).tracking(1.5).foregroundStyle(Theme.inkPrimary)
                    Spacer()
                    Text(analysis.analysisDate).font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
                }
                HStack(spacing: Theme.Spacing.standard) {
                    Text(analysis.signal.rawValue)
                        .font(Theme.engravedSerif(size: 18, weight: .bold))
                        .foregroundStyle(signalBadgeTextColor(analysis.signal))
                        .padding(.horizontal, Theme.Spacing.card).padding(.vertical, Theme.Spacing.medium)
                        .background(signalBadgeBgColor(analysis.signal))
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.pill))
                    Spacer()
                    ConfidenceArcView(score: analysis.confidencePercent, size: 64)
                }
                VStack(spacing: Theme.Spacing.small) {
                    Text("CONFIDENCE").font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
                        .financeTerm("Confidence Score")
                    HStack(spacing: Theme.Spacing.xSmall) {
                        ForEach(0..<5, id: \.self) { i in
                            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                .fill(i < confidenceSegments(analysis.confidencePercent) ? Theme.goldPrimary : Theme.inkTertiary.opacity(0.15))
                                .frame(height: 6)
                        }
                    }
                }
                Text(analysis.keyFactors.fundamentalsSummary)
                    .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                    .foregroundStyle(Theme.inkSecondary).lineSpacing(6).lineLimit(4)
                VStack(spacing: Theme.Spacing.medium) {
                    horizonRow(label: "3 MONTHS", target: analysis.targetPrices.shortTerm3m, upside: analysis.upsideDownsidePct.shortTerm)
                    horizonRow(label: "12 MONTHS", target: analysis.targetPrices.mediumTerm12m, upside: analysis.upsideDownsidePct.mediumTerm, featured: true)
                    horizonRow(label: "3 YEARS", target: analysis.targetPrices.longTerm36m, upside: analysis.upsideDownsidePct.longTerm)
                }
                Text("Analysis by Nivesh AI · Dalal Street weighted")
                    .font(Theme.microLabel(size: 9)).foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, alignment: .center)
            }
            .padding(Theme.Spacing.cardInset)
            .background(Theme.surfaceElevated)
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderStrong, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
            SectionDivider()
        }
    }

    private func horizonRow(label: String, target: Double, upside: Double, featured: Bool = false) -> some View {
        HStack(spacing: Theme.Spacing.standard) {
            Text(label)
                .font(featured ? Theme.monoTabular(size: 13).weight(.bold) : Theme.monoTabular(size: 12))
                .foregroundStyle(featured ? Theme.goldPrimary : Theme.inkSecondary)
                .frame(width: 80, alignment: .leading)
            Image(systemName: upside >= 0 ? "arrowtriangle.up.fill" : "arrowtriangle.down.fill")
                .font(.caption2)
                .foregroundStyle(upside >= 0 ? Theme.dataPositive : Theme.dataNegative)
            Text(IndianFormatter.priceCompact(target))
                .font(Theme.monoTabular(size: 14)).foregroundStyle(Theme.inkPrimary)
            Spacer()
            PnlBadge(value: upside, showPercentage: true)
        }
        .padding(.horizontal, Theme.Spacing.medium).padding(.vertical, Theme.Spacing.small)
        .background(featured ? Theme.goldMuted.opacity(0.5) : Color.clear)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
    }

    private func signalBadgeTextColor(_ signal: Signal) -> Color {
        switch signal {
        case .bullish, .cautiously_bullish: return .white
        case .bearish, .cautiously_bearish: return .white
        case .hold, .neutral: return Theme.goldPrimary
        }
    }

    private func signalBadgeBgColor(_ signal: Signal) -> Color {
        switch signal {
        case .bullish, .cautiously_bullish: return Theme.dataPositive
        case .bearish, .cautiously_bearish: return Theme.dataNegative
        case .hold, .neutral: return Theme.goldMuted
        }
    }

    private func confidenceSegments(_ pct: Int) -> Int {
        if pct >= 80 { return 5 }
        if pct >= 60 { return 4 }
        if pct >= 40 { return 3 }
        if pct >= 20 { return 2 }
        return 1
    }

    // MARK: -- Dialectic Debate

    private func dialecticDebateSection(_ analysis: StockAnalysis) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "DIALECTICAL ANALYSIS")
            HStack(alignment: .top, spacing: Theme.Spacing.tight) {
                VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "arrowtriangle.up.fill").font(.caption).foregroundStyle(Theme.dataPositive)
                        Text("BULL CASE").font(Theme.sectionCapsLabel()).foregroundStyle(Theme.dataPositive)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    ForEach(Array(analysis.bullCase.prefix(3).enumerated()), id: \.offset) { idx, point in
                        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                            Text("\(idx + 1)")
                                .font(Theme.officialStampFont(size: 10)).tracking(1.2)
                                .foregroundStyle(Theme.securityGold)
                                .frame(width: 20, height: 20)
                                .background(Theme.securityGold.opacity(0.15))
                                .clipShape(Circle())
                            Text(stripEmoji(point))
                                .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .caption))
                                .foregroundStyle(Theme.inkSecondary).lineSpacing(3)
                        }
                    }
                }
                .padding(Theme.Spacing.card).frame(maxWidth: .infinity)
                .background(Theme.dataPositiveMuted.opacity(0.3))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "arrowtriangle.down.fill").font(.caption).foregroundStyle(Theme.dataNegative)
                        Text("BEAR CASE").font(Theme.sectionCapsLabel(size: 12)).foregroundStyle(Theme.dataNegative)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    ForEach(Array(analysis.bearCase.prefix(3).enumerated()), id: \.offset) { idx, point in
                        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                            Text("\(idx + 1)")
                                .font(Theme.officialStampFont(size: 10)).tracking(1.2)
                                .foregroundStyle(Theme.bearRed)
                                .frame(width: 20, height: 20)
                                .background(Theme.bearRed.opacity(0.15))
                                .clipShape(Circle())
                            Text(stripEmoji(point))
                                .font(Theme.engravedSerif(size: 13, weight: .medium, relativeTo: .caption))
                                .foregroundStyle(Theme.inkPrimary).lineSpacing(3)
                        }
                    }
                }
                .padding(Theme.Spacing.card).frame(maxWidth: .infinity)
                .background(Theme.dataNegativeMuted.opacity(0.3))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
            }
        }
    }

    // MARK: -- Time Horizon

    private func timeHorizonSection(_ analysis: StockAnalysis) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "PRICE PROJECTIONS")
            HStack(spacing: Theme.Spacing.card) {
                horizonCard(label: "3M", target: analysis.targetPrices.shortTerm3m, upside: analysis.upsideDownsidePct.shortTerm)
                horizonCard(label: "12M", target: analysis.targetPrices.mediumTerm12m, upside: analysis.upsideDownsidePct.mediumTerm, featured: true)
                horizonCard(label: "3Y", target: analysis.targetPrices.longTerm36m, upside: analysis.upsideDownsidePct.longTerm)
            }
        }
    }

    private func horizonCard(label: String, target: Double, upside: Double, featured: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text(label)
                .font(Theme.sectionCapsLabel(size: 9))
                .foregroundStyle(featured ? Theme.goldPrimary : Theme.inkSecondary)
                .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                .background(featured ? Theme.goldMuted : Theme.inkTertiary.opacity(0.1))
                .clipShape(Capsule())
            Text(IndianFormatter.priceCompact(target))
                .font(Theme.dataLarge(size: featured ? 24 : 20, relativeTo: featured ? .title : .title2))
                .foregroundStyle(Theme.inkPrimary)
            PnlBadge(value: upside, showPercentage: true)
        }
        .padding(Theme.Spacing.card).frame(maxWidth: .infinity)
        .background(featured ? Theme.surfaceFloat : Theme.surfaceElevated)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
            .stroke(featured ? Theme.borderStrong : Theme.borderSubtle, lineWidth: featured ? 1 : 0.5))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
    }

    // MARK: -- Risk Factors

    private func riskFactorsSection(_ analysis: StockAnalysis) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "RISK FACTORS")
            VStack(spacing: Theme.Spacing.tight) {
                ForEach(Array(analysis.keyRisks.enumerated()), id: \.offset) { idx, risk in
                    let severity: SeverityDot.Severity = idx == 0 ? .high : (idx == 1 ? .medium : .low)
                    HStack(spacing: Theme.Spacing.medium) {
                        SeverityDot(severity: severity)
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            Text(severity.label).font(Theme.microLabel(size: 9)).foregroundStyle(severity.color)
                            Text(stripEmoji(risk))
                                .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                                .foregroundStyle(Theme.inkPrimary).lineSpacing(3)
                        }
                        Spacer()
                    }
                    .padding(Theme.Spacing.card)
                    .background(Theme.surfaceElevated)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderSubtle, lineWidth: 0.5))
                }
            }
        }
    }

    // MARK: -- Fundamentals

    private func fundamentalsSection(_ analysis: StockAnalysis) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "FUNDAMENTALS")

            // Screen C — 3-column numeric metric grid with long-press term tooltips
            if let info = viewModel.quickInfo {
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())],
                          spacing: Theme.Spacing.standard) {
                    AnalysisMetricCell(label: "P/E", term: "P/E Ratio",
                                       value: info.peRatio.map { String(format: "%.1f", $0) } ?? "—")
                    AnalysisMetricCell(label: "DEBT/EQ", term: "Debt/Equity",
                                       value: info.debtToEquity.map { String(format: "%.2f", $0) } ?? "—")
                    AnalysisMetricCell(label: "PROMOTER", term: "Promoter Pledging",
                                       value: info.promoterHoldingPct.map { String(format: "%.1f%%", $0) } ?? "—")
                    AnalysisMetricCell(label: "52W HIGH", term: "52W High",
                                       value: info.week52High.map { IndianFormatter.price($0) } ?? "—")
                    AnalysisMetricCell(label: "52W LOW", term: "52W Low",
                                       value: info.week52Low.map { IndianFormatter.price($0) } ?? "—")
                    AnalysisMetricCell(label: "VOLUME", term: "Bulk Deal",
                                       value: info.volume.map { "\($0)" } ?? "—")
                }
            }

            let factors: [(String, String)] = [
                ("MANAGEMENT QUALITY", analysis.keyFactors.managementQuality),
                ("GEOPOLITICAL CONTEXT", analysis.keyFactors.geopoliticalContext),
                ("PROMOTER / FII / DII", analysis.keyFactors.promoterFiiDiiActivity),
                ("TURNAROUND STORY", analysis.keyFactors.turnaroundStory),
                ("GLOBAL MACRO IMPACT", analysis.keyFactors.globalMacroImpact),
                ("NEWS SENTIMENT", analysis.keyFactors.newsSentiment),
            ]
            VStack(spacing: Theme.Spacing.tight) {
                ForEach(factors, id: \.0) { label, text in
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text(label).font(Theme.microLabel(size: 9)).foregroundStyle(Theme.inkTertiary)
                        Text(stripEmoji(text))
                            .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkPrimary).lineSpacing(3)
                    }
                    .padding(Theme.Spacing.card).frame(maxWidth: .infinity, alignment: .leading)
                    .background(Theme.surfaceElevated)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderSubtle, lineWidth: 0.5))
                }
            }
        }
    }

    // MARK: -- What to Watch + Disclaimer

    private func whatToWatchSection(_ analysis: StockAnalysis) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "WHAT TO WATCH")
            VStack(spacing: Theme.Spacing.tight) {
                ForEach(analysis.whatToWatch, id: \.self) { item in
                    HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                        Circle().fill(Theme.goldPrimary).frame(width: 6, height: 6).padding(.top, Theme.Spacing.tight)
                        Text(stripEmoji(item))
                            .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkPrimary).lineSpacing(3)
                        Spacer()
                    }
                    .padding(Theme.Spacing.standard)
                    .background(Theme.surfaceElevated)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                }
            }
        }
    }

    // MARK: -- Price Performance Chip

    @ViewBuilder
    private func pricePerformanceChip(label: String, pct: Double?) -> some View {
        if let pct = pct {
            let isPositive = pct >= 0
            HStack(spacing: Theme.Spacing.xSmall) {
                Image(systemName: isPositive ? "arrowtriangle.up.fill" : "arrowtriangle.down.fill")
                    .font(Theme.officialStampFont(size: 7))
                Text("\(label)  \(isPositive ? "+" : "")\(String(format: "%.1f", pct))%")
                    .font(Theme.serialNumberFont(size: 11))
            }
            .foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.xSmall)
            .background((isPositive ? Theme.bullGreen : Theme.bearRed).opacity(0.10))
            .clipShape(Capsule())
        }
    }

    // MARK: -- News Section

    @ViewBuilder
    private func newsSection(_ analysis: StockAnalysis) -> some View {
        if let news = analysis.recentNews, !news.isEmpty {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                SectionDivider()
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
                    NewsItemCard(item: item)
                }
            }
        }
    }

    private func disclaimerSection(_ analysis: StockAnalysis) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionDivider()
            Text(stripEmoji(analysis.disclaimer))
                .font(Theme.microLabel(size: 9)).foregroundStyle(Theme.inkTertiary)
                .lineSpacing(4).frame(maxWidth: .infinity, alignment: .leading)
                .padding(Theme.Spacing.card)
                .background(Theme.surfaceElevated.opacity(0.5))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        }
    }
    // MARK: -- What Changed (Diff View)
    @ViewBuilder
    private func whatChangedSection(_ analysis: StockAnalysis, previous: StockAnalysis) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "WHAT CHANGED SINCE LAST ANALYSIS")
            
            VStack(spacing: Theme.Spacing.medium) {
                // Signal change
                if analysis.signal != previous.signal {
                    diffRow(label: "AI SIGNAL", oldVal: previous.signal.rawValue, newVal: analysis.signal.rawValue, isPositive: analysis.signal == .bullish)
                }
                
                // Price change
                if analysis.currentPriceInr != previous.currentPriceInr {
                    let pctChange = ((analysis.currentPriceInr - previous.currentPriceInr) / previous.currentPriceInr) * 100
                    diffRow(label: "PRICE", oldVal: IndianFormatter.priceCompact(previous.currentPriceInr), newVal: IndianFormatter.priceCompact(analysis.currentPriceInr), isPositive: pctChange > 0)
                }
                
                // Confidence change
                if analysis.confidencePercent != previous.confidencePercent {
                    let diff = analysis.confidencePercent - previous.confidencePercent
                    diffRow(label: "CONFIDENCE", oldVal: "\(previous.confidencePercent)%", newVal: "\(analysis.confidencePercent)%", isPositive: diff > 0)
                }
                
                // 12M Target change
                if analysis.targetPrices.mediumTerm12m != previous.targetPrices.mediumTerm12m {
                    let diff = analysis.targetPrices.mediumTerm12m - previous.targetPrices.mediumTerm12m
                    diffRow(label: "12M TARGET", oldVal: IndianFormatter.priceCompact(previous.targetPrices.mediumTerm12m), newVal: IndianFormatter.priceCompact(analysis.targetPrices.mediumTerm12m), isPositive: diff > 0)
                }
            }
            .padding(Theme.Spacing.card)
            .background(Theme.surfaceElevated)
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderSubtle, lineWidth: 0.5))
        }
    }
    
    private func diffRow(label: String, oldVal: String, newVal: String, isPositive: Bool) -> some View {
        HStack(spacing: Theme.Spacing.medium) {
            Text(label).font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary).frame(width: 80, alignment: .leading)
            Text(oldVal).font(Theme.monoTabular(size: 13)).foregroundStyle(Theme.inkTertiary).strikethrough()
            Image(systemName: "arrow.right").font(.caption2).foregroundStyle(Theme.inkTertiary)
            Text(newVal).font(Theme.monoTabular(size: 13).weight(.bold)).foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
            Spacer()
        }
    }

    private func renderErrorState(_ info: AnalysisErrorInfo) -> some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.screen) {
                // ── Stock Header Card ──────────────────────────────────
                if let qi = viewModel.quickInfo {
                    VStack(spacing: Theme.Spacing.card) {
                        HStack(spacing: Theme.Spacing.card) {
                            StockIcon(ticker: qi.ticker, signal: qi.signal)
                            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                                Text(qi.ticker)
                                    .font(Theme.serialNumberFont(size: 24))
                                    .foregroundStyle(Theme.inkPrimary)
                                Text("OFFICIAL QUOTATION")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                            }
                            Spacer()
                        }
                        SectionDivider()
                        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.small) {
                                Text("₹")
                                    .font(Theme.engravedSerif(size: 24, weight: .bold))
                                    .foregroundStyle(Theme.securityGold)
                                Text((qi.price ?? 0.0).inrFormatted.replacingOccurrences(of: "₹", with: ""))
                                    .font(Theme.serialNumberFont(size: 44))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                            HStack(spacing: Theme.Spacing.medium) {
                                Text("\((qi.change ?? 0.0) >= 0 ? "+" : "")\((qi.change ?? 0.0).inrFormatted)")
                                Text("(\((qi.changePercent ?? 0.0).percentFormatted))")
                            }
                            .font(Theme.serialNumberFont(size: 16))
                            .foregroundStyle((qi.change ?? 0.0) >= 0 ? Theme.bullGreen : Theme.bearRed)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(Theme.Spacing.large)
                        .banknoteCard()
                    }
                    .padding(.top, 20)
                }

                // ── Error Summary Card ─────────────────────────────────
                VStack(spacing: Theme.Spacing.card) {
                    HStack(spacing: Theme.Spacing.standard) {
                        Image(systemName: info.iconName)
                            .font(.title)
                            .foregroundStyle(info.isRateLimit ? Theme.holdAmber : Theme.bearRed)
                        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                            Text(info.displayTitle)
                                .font(Theme.engravedSerif(size: 16, weight: .bold))
                                .foregroundStyle(Theme.inkPrimary)
                            BanknoteSignalBadge(text: info.badgeText, color: info.isRateLimit ? Theme.holdAmber : Theme.bearRed, rotation: -3)
                        }
                        Spacer()
                        if let code = info.diagnostic?.errorCode {
                            Text(code)
                                .font(Theme.officialStampFont(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                                .padding(.horizontal, 8).padding(.vertical, 4)
                                .background(Theme.inkTertiary.opacity(0.1))
                                .clipShape(Capsule())
                        }
                    }

                    SectionDivider()

                    Text(info.suggestedActionText)
                        .font(.footnote.weight(.medium))
                        .foregroundStyle(info.isRateLimit ? Theme.holdAmber : Theme.securityGold)
                        .lineSpacing(4)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(Theme.Spacing.screen)
                .banknoteCard()

                // ── What Went Wrong ────────────────────────────────────
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    Label {
                        Text("WHAT WENT WRONG")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                    } icon: {
                        Image(systemName: "magnifyingglass")
                            .foregroundStyle(Theme.bearRed)
                            .font(.footnote)
                    }

                    Text(info.displayDetail)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineSpacing(5)

                    if let phase = info.diagnostic?.phaseFailed {
                        HStack(spacing: Theme.Spacing.tight) {
                            Text("FAILED PHASE:")
                                .font(Theme.officialStampFont(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                            Text(phase.replacingOccurrences(of: "_", with: " ").uppercased())
                                .font(Theme.serialNumberFont(size: 10))
                                .foregroundStyle(Theme.bearRed)
                        }
                    }
                }
                .padding(Theme.Spacing.screen)
                .banknoteCard()

                // ── Performance Trace ──────────────────────────────────
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    Label {
                        Text("PERFORMANCE TRACE")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                    } icon: {
                        Image(systemName: "stopwatch")
                            .foregroundStyle(Theme.securityGold)
                            .font(.footnote)
                    }

                    VStack(spacing: Theme.Spacing.medium) {
                        HStack {
                            Text("Total elapsed:")
                                .font(Theme.serialNumberFont(size: 11))
                                .foregroundStyle(Theme.inkTertiary)
                            Spacer()
                            Text(String(format: "%.1fs", info.elapsedSeconds))
                                .font(Theme.serialNumberFont(size: 11))
                                .foregroundStyle(info.elapsedSeconds > 30 ? Theme.bearRed : Theme.inkPrimary)
                        }
                        if let qiElapsed = info.quickInfoElapsed {
                            HStack {
                                Text("Parallel data fetch:")
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundStyle(Theme.inkTertiary)
                                Spacer()
                                Text(String(format: "%.1fs", qiElapsed))
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundStyle(Theme.bullGreen)
                            }
                            let analyzeElapsed = info.elapsedSeconds - qiElapsed
                            if analyzeElapsed > 0 {
                                HStack {
                                    Text("Analyze API call:")
                                        .font(Theme.serialNumberFont(size: 11))
                                        .foregroundStyle(Theme.inkTertiary)
                                    Spacer()
                                    Text(String(format: "%.1fs", analyzeElapsed))
                                        .font(Theme.serialNumberFont(size: 11))
                                        .foregroundStyle(Theme.bearRed)
                                }
                            }
                        }
                        if let ts = info.diagnostic?.timestamp {
                            HStack {
                                Text("Failed at:")
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundStyle(Theme.inkTertiary)
                                Spacer()
                                Text(ts)
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundStyle(Theme.inkSecondary)
                            }
                        }
                    }
                }
                .padding(Theme.Spacing.screen)
                .banknoteCard()

                // ── Network Trace ──────────────────────────────────────
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    Label {
                        Text("NETWORK TRACE")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                    } icon: {
                        Image(systemName: "network")
                            .foregroundStyle(Theme.inkSecondary)
                            .font(.footnote)
                    }

                    VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                        TraceRow(label: "URL", value: info.requestUrl)
                        TraceRow(label: "Method", value: "POST")
                        TraceRow(label: "HTTP Status", value: "\(info.httpStatusCode)")
                        if !info.responseHeaders.isEmpty {
                            CollapsibleSection(header: "RESPONSE HEADERS") {
                                Text(info.responseHeaders)
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundStyle(Theme.inkTertiary)
                                    .lineSpacing(3)
                            }
                        }
                        if !info.responseBody.isEmpty {
                            CollapsibleSection(header: "RAW RESPONSE BODY") {
                                Text(info.responseBody)
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundStyle(Theme.inkTertiary)
                                    .lineSpacing(3)
                            }
                        }
                    }
                }
                .padding(Theme.Spacing.screen)
                .banknoteCard()

                // ── Backend Diagnostic ─────────────────────────────────
                if let diagInfo = info.diagnostic?.diagnosticInfo, !diagInfo.isEmpty {
                    VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                        Label {
                            Text("BACKEND DIAGNOSTIC")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkPrimary)
                        } icon: {
                            Image(systemName: "gearshape.2")
                                .foregroundStyle(Theme.holdAmber)
                                .font(.footnote)
                        }

                        CollapsibleSection(header: "SERVER TRACE (tap to expand)") {
                            Text(diagInfo)
                                .font(Theme.serialNumberFont(size: 10))
                                .foregroundStyle(Theme.inkTertiary)
                                .lineSpacing(4)
                        }
                    }
                    .padding(Theme.Spacing.screen)
                    .banknoteCard()
                }

                // ── Client Context ─────────────────────────────────────
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    Label {
                        Text("CLIENT CONTEXT")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                    } icon: {
                        Image(systemName: "iphone")
                            .foregroundStyle(Theme.inkSecondary)
                            .font(.footnote)
                    }

                    VStack(spacing: Theme.Spacing.tight) {
                        TraceRow(label: "App", value: "StockMe v\(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?.?.?")")
                        TraceRow(label: "Mock Mode", value: info.isMockMode ? "ON" : "OFF")
                        TraceRow(label: "Deep Scan", value: info.isDeepScan ? "ON" : "OFF")
                        TraceRow(label: "Base URL", value: info.requestUrl)
                    }
                }
                .padding(Theme.Spacing.screen)
                .banknoteCard()

                // ── Action Buttons ─────────────────────────────────────
                VStack(spacing: Theme.Spacing.standard) {
                    Button(action: {
                        HapticManager.impact(.medium)
                        viewModel.fetchAnalysis(ticker: ticker, userId: authManager.currentUser?.userId, useMock: useMockAI, reportManager: reportManager, deepScan: deepScanEnabled)
                    }) {
                        HStack(spacing: Theme.Spacing.medium) {
                            Image(systemName: "arrow.clockwise")
                            Text("RETRY ANALYSIS")
                        }
                        .font(Theme.officialStampFont(size: 10))
                        .foregroundStyle(Theme.inkPrimary)
                        .padding(.vertical, 14)
                        .frame(maxWidth: .infinity)
                        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.inkPrimary, lineWidth: 1))
                    }
                }
                .padding(.top, 8)

                Spacer(minLength: 80)
            }
            .padding(.horizontal, Theme.screenPadding)
        }
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
        .padding(.vertical, 10)
    }
}

// MARK: - Analysis Metric Cell (Screen C 3-col grid)

private struct AnalysisMetricCell: View {
    let label: String
    let term: String
    let value: String

    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 8)).tracking(1.2)
                .foregroundStyle(Theme.inkTertiary)
                .financeTerm(term)
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
            SectionDivider()
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

private struct NewsItemCard: View {
    let item: NewsItem
    @State private var showingReader = false

    var body: some View {
        Button {
            HapticManager.impact(.light)
            showingReader = true
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
        .fullScreenCover(isPresented: $showingReader) {
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
                            .padding(.top, 4)
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
                        .financeTerm("Confidence Score")
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
                    SectionDivider()
                    Text(glossaryDefinitions[term] ?? "No definition available for this term.")
                        .font(.body.weight(.medium))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineSpacing(6)
                    Spacer()
                }
                .padding(28)
            }
            .navigationTitle("शब्दावली / Glossary")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }.foregroundStyle(Theme.securityGold)
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
        GeometryReader { geo in
            NavigationStack {
                ScrollView {
                    VStack(alignment: .leading, spacing: Theme.Spacing.screen) {
                        // Hero Image
                        if let urlStr = item.imageUrl, let url = URL(string: urlStr) {
                            AsyncImage(url: url) { image in
                                image.resizable().aspectRatio(contentMode: .fill)
                            } placeholder: {
                                Rectangle().fill(Theme.inkSecondary.opacity(0.1))
                            }
                            .frame(height: geo.size.height * 0.28)
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

                        SectionDivider()

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
                            if let url = URL(string: item.link) {
                                Link(destination: url) {
                                    HStack {
                                        Text("READ FULL STORY ON \(item.publisher.uppercased())")
                                        Image(systemName: "arrow.up.right")
                                    }
                                    .font(Theme.officialStampFont(size: 11))
                                    .foregroundStyle(.white)
                                    .padding(.vertical, 14)
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
                                .foregroundStyle(.white.opacity(0.5))
                                .padding(.vertical, 14)
                                .frame(maxWidth: .infinity)
                                .background(Theme.inkPrimary.opacity(0.5))
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                            }
                        }
                        .padding(.top, 20)
                    }
                    .padding(.horizontal, Theme.screenPadding)

                    Spacer(minLength: 40)
                }
            }
            .background(Theme.canvasDeep)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button { dismiss() } label: {
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
}

// MARK: - Diagnostic Error Helpers

private struct TraceRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
            Text(label)
                .font(Theme.serialNumberFont(size: 10))
                .foregroundStyle(Theme.inkTertiary)
                .frame(width: 90, alignment: .leading)
            Text(value)
                .font(Theme.serialNumberFont(size: 10))
                .foregroundStyle(Theme.inkSecondary)
                .lineSpacing(3)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct CollapsibleSection<Content: View>: View {
    let header: String
    @ViewBuilder let content: () -> Content
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Button(action: {
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
                .padding(.leading, 16)
                .padding(.vertical, 8)
                .background(Theme.canvasDeep.opacity(0.5))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
            }
        }
    }
}
// Item 14: MagnificationGesture added in StockCharts.swift
