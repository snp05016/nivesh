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

    func fetchAnalysis(ticker: String, userId: Int?, useMock: Bool, reportManager: LocalReportManager, deepScan: Bool = false) {
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
                let result = try await NetworkManager.shared.analyze(ticker: ticker, userId: userId, useMock: useMock, deepScan: deepScan)
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

    // Live price polling
    @State private var livePrice: Double? = nil
    @State private var pricePollingTask: Task<Void, Never>? = nil

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
                        .foregroundColor(Theme.inkPrimary)
                        .padding(8)
                        .background(Theme.canvasDeep)
                        .clipShape(Circle())
                }
            }
            ToolbarItem(placement: .principal) {
                VStack(spacing: 0) {
                    Text("विश्लेषण रिपोर्ट")
                        .font(Theme.hindiFont(size: 9))
                        .foregroundColor(Theme.inkSecondary)
                    Text("ANALYSIS REPORT")
                        .font(Theme.engravedSerif(size: 14, weight: .bold))
                        .foregroundColor(Theme.inkPrimary)
                }
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                ShareLink(
                    item: PDFGenerator.generatePDFURL(for: viewModel.analysis),
                    preview: SharePreview("\(ticker) Analysis", image: Image(systemName: "doc.text"))
                ) {
                    Image(systemName: "square.and.arrow.up")
                        .foregroundColor(viewModel.analysis != nil ? Theme.inkPrimary : Theme.inkSecondary.opacity(0.3))
                }
                .disabled(viewModel.analysis == nil)
            }
        }
        .onAppear {
            activeTab = savedLastTab
            deepScanEnabled = defaultDeepScan
            if viewModel.analysis == nil && !viewModel.isLoading {
                if forceCached, let cached = reportManager.getReport(for: ticker) {
                    viewModel.analysis = cached
                } else if let cached = reportManager.getReport(for: ticker) {
                    _ = cached
                    showingRegenerateAlert = true
                } else {
                    viewModel.fetchAnalysis(ticker: ticker, userId: authManager.currentUser?.userId, useMock: useMockAI, reportManager: reportManager, deepScan: deepScanEnabled)
                }
            }
            startPricePolling()
        }
        .onChange(of: activeTab) { _, val in savedLastTab = val }
        .onDisappear {
            viewModel.cancelAnalysis()
            pricePollingTask?.cancel()
            pricePollingTask = nil
        }
        .alert("Cached Report Found", isPresented: $showingRegenerateAlert) {
            Toggle("Deep Scan (PKScreener + FinBERT)", isOn: $deepScanEnabled)
                .tint(Theme.securityGold)
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

    @ViewBuilder
    private func renderLoadingState() -> some View {
        ScrollView {
            VStack(spacing: 32) {
                if let info = viewModel.quickInfo {
                    VStack(spacing: 24) {
                        HStack(spacing: 16) {
                            StockIcon(ticker: info.ticker, signal: info.signal)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(info.ticker)
                                    .font(Theme.serialNumberFont(size: 24))
                                    .foregroundColor(Theme.inkPrimary)
                                Text("OFFICIAL QUOTATION")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundColor(Theme.inkSecondary)
                            }
                            Spacer()
                        }

                        GuillocheDivider()

                        VStack(alignment: .leading, spacing: 8) {
                            HStack(alignment: .firstTextBaseline, spacing: 4) {
                                Text("₹")
                                    .font(Theme.engravedSerif(size: 24, weight: .bold))
                                    .foregroundColor(Theme.securityGold)
                                Text(info.price.inrFormatted.replacingOccurrences(of: "₹", with: ""))
                                    .font(Theme.serialNumberFont(size: 44))
                                    .foregroundColor(Theme.inkPrimary)
                            }

                            HStack(spacing: 8) {
                                Text(info.change >= 0 ? "+" : "") + Text(info.change.inrFormatted)
                                Text("(\(info.changePercent.percentFormatted))")
                            }
                            .font(Theme.serialNumberFont(size: 16))
                            .foregroundColor(info.change >= 0 ? Theme.bullGreen : Theme.bearRed)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(24)
                        .banknoteCard()
                    }
                    .padding(.top, 20)
                }

                // Personal note card (loading state)
                if let note = userNote, !note.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("आपका नोट / YOUR NOTE")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkSecondary)
                        Text(note)
                            .font(Theme.hindiFont(size: 14))
                            .foregroundColor(Theme.inkPrimary)
                            .lineSpacing(4)
                    }
                    .padding(20)
                    .background(Theme.holdAmber.opacity(0.06))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.securityGold.opacity(0.4), lineWidth: 1))
                }

                VStack(spacing: 20) {
                    if deepScanEnabled {
                        HStack(spacing: 6) {
                            Image(systemName: "waveform.badge.magnifyingglass")
                                .font(.system(size: 11, weight: .medium))
                            Text("DEEP SCAN ACTIVE")
                                .font(Theme.officialStampFont(size: 8))
                                .tracking(1.5)
                        }
                        .foregroundColor(Theme.securityGold)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Theme.securityGold.opacity(0.08))
                        .clipShape(Capsule())
                        .overlay(Capsule().stroke(Theme.securityGold.opacity(0.25), lineWidth: 0.5))
                    }

                    ZStack {
                        Circle()
                            .stroke(Theme.securityGold.opacity(0.3), lineWidth: 1)
                            .frame(width: 80, height: 80)
                        ProgressView()
                            .tint(Theme.securityGold)
                            .scaleEffect(1.2)
                    }

                    VStack(spacing: 8) {
                        Text(useMockAI ? "सत्यापन मोड / MOCK MODE ACTIVE" : "विश्लेषण प्रक्रिया / GENERATING INSIGHTS")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkPrimary)

                        Text(useMockAI ? "Bypassing heavy compute to preserve tender." : "Securing fundamental, news, and technical data threads...")
                            .font(.system(size: 13, weight: .medium))
                            .foregroundColor(Theme.inkSecondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 40)
                    }

                    Button(action: {
                        HapticManager.impact(.rigid)
                        viewModel.cancelAnalysis()
                        dismiss()
                    }) {
                        Text("ABORT PROCESS")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.bearRed)
                            .padding(.vertical, 10)
                            .padding(.horizontal, 20)
                            .overlay(RoundedRectangle(cornerRadius: 2).stroke(Theme.bearRed.opacity(0.3), lineWidth: 1))
                    }
                }
                .padding(.top, 20)

                if let info = viewModel.quickInfo {
                    VStack(alignment: .leading, spacing: 20) {
                        Text("संस्था का विवरण / COMPANY PROFILE")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkPrimary)

                        if let desc = info.description {
                            Text(desc)
                                .font(.system(size: 14, weight: .medium))
                                .foregroundColor(Theme.inkSecondary)
                                .lineSpacing(6)
                        }

                        GuillocheDivider()

                        if let officers = info.officers, !officers.isEmpty {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("KEY EXECUTIVES")
                                    .font(Theme.officialStampFont(size: 8))
                                    .foregroundColor(Theme.inkSecondary)

                                ForEach(officers, id: \.self) { officer in
                                    Text("• \(officer.uppercased())")
                                        .font(Theme.serialNumberFont(size: 13))
                                        .foregroundColor(Theme.inkPrimary)
                                }
                            }
                        }
                    }
                    .padding(24)
                    .banknoteCard()

                    if let news = info.recentNews, !news.isEmpty {
                        VStack(alignment: .leading, spacing: 16) {
                            Text("ताज़ा समाचार / LATEST BULLETINS")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundColor(Theme.inkPrimary)
                                .padding(.horizontal, 4)

                            VStack(spacing: 12) {
                                ForEach(news) { item in
                                    NewsItemCard(item: item)
                                }
                            }
                        }
                        .padding(.top, 16)
                    }
                }

                Spacer(minLength: 100)
            }
            .padding(.horizontal, Theme.screenPadding)
        }
    }

    @ViewBuilder
    private func renderFullAnalysis(_ analysis: StockAnalysis) -> some View {
        VStack(spacing: 0) {
            // ── Sticky header ──────────────────────────────────────────
            VStack(spacing: 0) {
                HStack(alignment: .top, spacing: 12) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(analysis.companyName.uppercased())
                            .font(Theme.engravedSerif(size: 17, weight: .bold))
                            .foregroundColor(Theme.inkPrimary)
                            .lineLimit(1)
                        Text("\(analysis.ticker) • \(analysis.exchange ?? "NSE")")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundColor(Theme.inkSecondary)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 3) {
                        HStack(alignment: .firstTextBaseline, spacing: 4) {
                            Text("₹")
                                .font(Theme.engravedSerif(size: 14, weight: .bold))
                                .foregroundColor(Theme.securityGold)
                            Text((livePrice ?? analysis.currentPriceInr).inrFormatted.replacingOccurrences(of: "₹", with: ""))
                                .font(Theme.serialNumberFont(size: 22))
                                .foregroundColor(Theme.inkPrimary)
                                .contentTransition(.numericText())
                                .animation(.easeInOut(duration: 0.3), value: livePrice)
                            if livePrice != nil {
                                Text("LIVE")
                                    .font(.system(size: 8, weight: .bold))
                                    .foregroundColor(.white)
                                    .padding(.horizontal, 4)
                                    .padding(.vertical, 2)
                                    .background(Theme.bullGreen)
                                    .cornerRadius(3)
                            }
                        }
                        BanknoteSignalBadge(signal: analysis.signal, rotation: -3)
                            .stampAppear()
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
                .padding(.top, 12)
                .padding(.bottom, 10)

                GuillocheDivider()
                    .padding(.horizontal, Theme.screenPadding)

                // Tab bar
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 0) {
                        ForEach(tabs.indices, id: \.self) { i in
                            Button {
                                HapticManager.selection()
                                withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                                    activeTab = i
                                }
                            } label: {
                                VStack(spacing: 6) {
                                    Text(tabs[i])
                                        .font(Theme.officialStampFont(size: 9))
                                        .foregroundColor(activeTab == i ? Theme.inkPrimary : Theme.inkTertiary)
                                        .padding(.horizontal, 16)
                                        .padding(.top, 10)

                                    Rectangle()
                                        .fill(activeTab == i ? Theme.securityGold : Color.clear)
                                        .frame(height: 2)
                                }
                            }
                        }
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            }
            .background(Theme.canvasDeep.opacity(0.95))

            // ── Tab pages ──────────────────────────────────────────────
            TabView(selection: $activeTab) {
                tabOverview(analysis).tag(0)
                tabAnalysis(analysis).tag(1)
                tabCharts(analysis).tag(2)
                tabFundamentals(analysis).tag(3)
                tabNews(analysis).tag(4)
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            .animation(.spring(response: 0.35, dampingFraction: 0.85), value: activeTab)
        }
    }

    // MARK: - Tab 0: Overview

    @ViewBuilder
    private func tabOverview(_ analysis: StockAnalysis) -> some View {
        ScrollView {
            VStack(spacing: 20) {

                // ── Earnings banner ────────────────────────────────────
                if let event = viewModel.earningsEvents.first(where: { $0.ticker.uppercased() == ticker.uppercased() }) {
                    HStack(spacing: 10) {
                        Image(systemName: "calendar.badge.exclamationmark")
                            .foregroundColor(Theme.holdAmber).font(.system(size: 16))
                        VStack(alignment: .leading, spacing: 2) {
                            Text("EARNINGS DUE")
                                .font(Theme.officialStampFont(size: 8))
                                .foregroundColor(Theme.inkSecondary)
                            Text(event.daysAway == 0 ? "Results today" :
                                 event.daysAway < 0 ? "Results \(-event.daysAway) days ago" :
                                 "Results in \(event.daysAway) days — \(event.earningsDate)")
                                .font(Theme.serialNumberFont(size: 12))
                                .foregroundColor(Theme.inkPrimary)
                        }
                        Spacer()
                    }
                    .padding(14)
                    .background(Theme.holdAmber.opacity(0.07))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.holdAmber.opacity(0.4), lineWidth: 1))
                }

                // ── "Should I be worried?" card (held stocks only) ─────
                if let holding = portfolioHolding {
                    let worryLevel: (label: String, color: Color, icon: String) = {
                        switch analysis.signal {
                        case .bullish:            return ("Low", Theme.bullGreen, "checkmark.shield.fill")
                        case .cautiously_bullish: return ("Low", Theme.bullGreen, "checkmark.shield")
                        case .neutral, .hold:     return ("Medium", Theme.holdAmber, "exclamationmark.triangle")
                        case .cautiously_bearish: return ("Medium-High", Theme.bearRed.opacity(0.8), "exclamationmark.triangle.fill")
                        case .bearish:            return ("High", Theme.bearRed, "xmark.shield.fill")
                        }
                    }()
                    VStack(alignment: .leading, spacing: 14) {
                        HStack(spacing: 10) {
                            Image(systemName: worryLevel.icon)
                                .font(.system(size: 22))
                                .foregroundColor(worryLevel.color)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("SHOULD I BE WORRIED?")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundColor(Theme.inkPrimary)
                                Text("Worry level: \(worryLevel.label)")
                                    .font(Theme.serialNumberFont(size: 13))
                                    .foregroundColor(worryLevel.color)
                            }
                            Spacer()
                            BanknoteSignalBadge(signal: analysis.signal, rotation: -4).stampAppear()
                        }
                        GuillocheDivider()
                        HStack(spacing: 0) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text("YOU HOLD").font(Theme.officialStampFont(size: 8)).foregroundColor(Theme.inkSecondary)
                                Text("\(Int(holding.shares)) shares @ \(holding.buyPrice.inrFormatted)").font(Theme.serialNumberFont(size: 12)).foregroundColor(Theme.inkPrimary)
                            }
                            Spacer()
                            VStack(alignment: .trailing, spacing: 3) {
                                Text("UNREALISED P&L").font(Theme.officialStampFont(size: 8)).foregroundColor(Theme.inkSecondary)
                                Text(holding.pnl.inrFormatted)
                                    .font(Theme.serialNumberFont(size: 12))
                                    .foregroundColor(holding.pnl >= 0 ? Theme.bullGreen : Theme.bearRed)
                                Text("(\(String(format: "%.1f%%", holding.pnlPercent)))")
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundColor(holding.pnl >= 0 ? Theme.bullGreen : Theme.bearRed)
                            }
                        }
                        if let target = holding.targetPrice, target > 0 {
                            let upside = (target - holding.stock.currentPrice) / holding.stock.currentPrice * 100
                            HStack {
                                Text("YOUR TARGET").font(Theme.officialStampFont(size: 8)).foregroundColor(Theme.inkSecondary)
                                Spacer()
                                Text("\(target.inrFormatted)  (\(upside >= 0 ? "+" : "")\(String(format: "%.1f%%", upside)) to go)")
                                    .font(Theme.serialNumberFont(size: 12))
                                    .foregroundColor(upside >= 0 ? Theme.bullGreen : Theme.bearRed)
                            }
                        }
                    }
                    .padding(18)
                    .background(worryLevel.color.opacity(0.04))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(worryLevel.color.opacity(0.3), lineWidth: 1))
                }

                // ── Signal change diff card ─────────────────────────────
                // Prefer API-provided signal change data; fall back to local history comparison.
                let apiSignalChanged = analysis.signalChanged == true
                let apiPreviousSignal = analysis.previousSignal
                let previousReports = reportManager.savedReports.filter { $0.ticker == analysis.ticker }
                let prevReport = previousReports.first(where: { $0.analysisDate != analysis.analysisDate })
                let localSignalChanged = prevReport != nil && prevReport!.signal != analysis.signal
                let showDiffCard = apiSignalChanged || localSignalChanged
                if showDiffCard {
                    let fromSignalText: String = apiPreviousSignal ?? prevReport?.signal.rawValue ?? ""
                    let sinceText: String = prevReport?.analysisDate ?? ""
                    VStack(alignment: .leading, spacing: 10) {
                        HStack(spacing: 10) {
                            Image(systemName: "arrow.triangle.2.circlepath")
                                .foregroundColor(Theme.securityGold).font(.system(size: 14))
                            VStack(alignment: .leading, spacing: 2) {
                                Text("SIGNAL CHANGED — WHY?")
                                    .font(Theme.officialStampFont(size: 8))
                                    .foregroundColor(Theme.inkSecondary)
                                Text("\(fromSignalText)  →  \(analysis.signal.rawValue)")
                                    .font(Theme.serialNumberFont(size: 12))
                                    .foregroundColor(Theme.inkPrimary)
                                if !sinceText.isEmpty {
                                    Text("Since \(sinceText)")
                                        .font(Theme.serialNumberFont(size: 10))
                                        .foregroundColor(Theme.inkTertiary)
                                }
                            }
                            Spacer()
                        }
                        GuillocheDivider()
                        let factors: [(String, String)] = [
                            ("News/Sentiment", analysis.keyFactors.newsSentiment),
                            ("Geopolitical", analysis.keyFactors.geopoliticalContext),
                            ("Promoter/FII", analysis.keyFactors.promoterFiiDiiActivity),
                        ]
                        ForEach(factors, id: \.0) { label, text in
                            VStack(alignment: .leading, spacing: 3) {
                                Text(label.uppercased()).font(Theme.officialStampFont(size: 7)).foregroundColor(Theme.inkTertiary)
                                Text(text).font(.system(size: 13, weight: .medium)).foregroundColor(Theme.inkSecondary).lineSpacing(3)
                            }
                        }
                    }
                    .padding(16)
                    .background(Theme.securityGold.opacity(0.04))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.securityGold.opacity(0.3), lineWidth: 1))
                }

                // Confidence
                ConfidenceCard(percent: analysis.confidencePercent)
                if let rationale = analysis.confidenceRationale {
                    Text(rationale)
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundColor(Theme.inkSecondary)
                        .padding(.top, 2)
                }

                // Price projections
                VStack(alignment: .leading, spacing: 12) {
                    Text("मूल्य अनुमान / PRICE PROJECTIONS")
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundColor(Theme.inkPrimary)
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 16) {
                            HorizonNoteCard(label: "3 Months", target: analysis.targetPrices.shortTerm3m, upside: analysis.upsideDownsidePct.shortTerm)
                            HorizonNoteCard(label: "12 Months", target: analysis.targetPrices.mediumTerm12m, upside: analysis.upsideDownsidePct.mediumTerm, isFeatured: true)
                            HorizonNoteCard(label: "3 Years", target: analysis.targetPrices.longTerm36m, upside: analysis.upsideDownsidePct.longTerm)
                        }
                    }
                }

                // Alert row
                Button { showSetAlertSheet = true } label: {
                    HStack(spacing: 12) {
                        Image(systemName: "bell.badge").font(.system(size: 18)).foregroundColor(Theme.securityGold)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("SET PRICE ALERT")
                                .font(Theme.officialStampFont(size: 9)).foregroundColor(Theme.inkPrimary)
                            Text("Alert me when \(ticker) reaches a target price")
                                .font(Theme.serialNumberFont(size: 11)).foregroundColor(Theme.inkSecondary)
                        }
                        Spacer()
                        Image(systemName: "chevron.right").foregroundColor(Theme.inkTertiary)
                    }
                    .padding(16).banknoteCard()
                }
                .ekPressHaptic()
                .sheet(isPresented: $showSetAlertSheet) {
                    AddAlertSheet(authManager: authManager, onAdded: { }, prefilledTicker: ticker, prefilledCompany: analysis.companyName)
                }

                // Personal note
                if let note = userNote, !note.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("आपका नोट / YOUR NOTE")
                            .font(Theme.officialStampFont(size: 9)).foregroundColor(Theme.inkSecondary)
                        Text(note)
                            .font(Theme.hindiFont(size: 14)).foregroundColor(Theme.inkPrimary).lineSpacing(4)
                    }
                    .padding(20)
                    .background(Theme.holdAmber.opacity(0.06))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.securityGold.opacity(0.4), lineWidth: 1))
                }

                Spacer(minLength: 80)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, 16)
        }
    }

    // MARK: - Tab 1: Analysis

    @ViewBuilder
    private func tabAnalysis(_ analysis: StockAnalysis) -> some View {
        ScrollView {
            VStack(spacing: 20) {

                // ── Macro data strip (USD/INR · Crude · RBI · VIX) ──────────
                if let macro = viewModel.macroStrip {
                    HStack(spacing: 0) {
                        MacroChip(label: "USD/INR", value: macro.usdInr.map { String(format: "₹%.2f", $0) } ?? "—", color: Theme.inkSecondary)
                        Divider().frame(height: 28).background(Theme.borderFine)
                        MacroChip(label: "CRUDE WTI", value: macro.crudeOilUsd.map { "$\(String(format: "%.1f", $0))" } ?? "—", color: macro.crudeOilUsd ?? 0 > 85 ? Theme.bearRed : Theme.inkSecondary)
                        Divider().frame(height: 28).background(Theme.borderFine)
                        MacroChip(label: "RBI RATE", value: "\(String(format: "%.2f", macro.rbiRepoRatePct))%  \(macro.rbiStance)", color: Theme.holdAmber)
                        if let vix = macro.indiaVix {
                            Divider().frame(height: 28).background(Theme.borderFine)
                            MacroChip(
                                label: "INDIA VIX",
                                value: String(format: "%.1f", vix),
                                color: vix > 20 ? .red : vix > 15 ? Theme.securityGold : Theme.bullGreen
                            )
                        }
                    }
                    .banknoteCard()
                }

                // ── Macro impact per holding ──────────────────────────
                if !viewModel.macroImpacts.isEmpty {
                    MacroImpactBanner(impacts: viewModel.macroImpacts)
                }

                // ── Geopolitical context ───────────────────────────────
                KeyFactorCard(
                    icon: "globe.asia.australia.fill",
                    title: "GEOPOLITICAL / POLICY",
                    hindiTitle: "भू-राजनीति",
                    text: analysis.keyFactors.geopoliticalContext,
                    color: Theme.holdAmber
                )

                // ── Global macro impact ────────────────────────────────
                KeyFactorCard(
                    icon: "chart.line.uptrend.xyaxis",
                    title: "GLOBAL MACRO IMPACT",
                    hindiTitle: "वैश्विक प्रभाव",
                    text: analysis.keyFactors.globalMacroImpact,
                    color: Theme.inkSecondary
                )

                // ── Indian market sentiment ────────────────────────────
                if let sentiment = analysis.keyFactors.indianMarketSentiment {
                    KeyFactorCard(
                        icon: "person.3.fill",
                        title: "INDIAN MARKET SENTIMENT",
                        hindiTitle: "बाज़ार की भावना",
                        text: sentiment,
                        color: Theme.securityGold
                    )
                }

                // ── Pattern cards ──────────────────────────────────────
                if let patterns = analysis.patterns, !patterns.isEmpty {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack(spacing: 8) {
                            Image(systemName: "waveform.path.ecg").foregroundColor(Theme.securityGold).font(.system(size: 14))
                            VStack(alignment: .leading, spacing: 1) {
                                Text("ऐतिहासिक पैटर्न").font(Theme.hindiFont(size: 9)).foregroundColor(Theme.inkTertiary)
                                Text("PATTERNS DETECTED").font(Theme.officialStampFont(size: 9)).foregroundColor(Theme.inkPrimary)
                            }
                        }
                        GuillocheDivider()
                        ForEach(patterns, id: \.self) { pattern in
                            HStack(alignment: .top, spacing: 8) {
                                Image(systemName: "sparkle").foregroundColor(Theme.securityGold).font(.system(size: 10)).padding(.top, 3)
                                Text(pattern).font(.system(size: 14, weight: .medium)).foregroundColor(Theme.inkSecondary).lineSpacing(3)
                            }
                        }
                    }
                    .padding(16).banknoteCard()
                }

                AnalysisNoteSection(title: "The Bull Case", items: analysis.bullCase, color: Theme.bullGreen)
                AnalysisNoteSection(title: "The Bear Case", items: analysis.bearCase, color: Theme.bearRed)
                AnalysisNoteSection(title: "Operational Risks", items: analysis.keyRisks, color: Theme.securityGold)

                if !analysis.whatToWatch.isEmpty {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("नज़र रखें / WHAT TO WATCH")
                            .font(Theme.officialStampFont(size: 9)).foregroundColor(Theme.inkPrimary)
                        ForEach(analysis.whatToWatch, id: \.self) { point in
                            let isCorp = point.lowercased().contains("split") || point.lowercased().contains("bonus") || point.lowercased().contains("rights") || point.lowercased().contains("dividend")
                            HStack(alignment: .top, spacing: 10) {
                                Rectangle().fill(Theme.securityGold.opacity(0.4)).frame(width: 2, height: 14).padding(.top, 3)
                                Text(point).font(.system(size: 14, weight: .medium)).foregroundColor(Theme.inkSecondary).lineSpacing(3)
                                Spacer()
                                if isCorp { BanknoteSignalBadge(text: "CORP ACTION", color: Theme.securityGold, rotation: -2) }
                            }
                        }
                    }
                    .padding(20).banknoteCard()
                }

                if let ratings = viewModel.analystRatings, !ratings.ratings.isEmpty {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Text("BROKER CONSENSUS")
                                .font(Theme.officialStampFont(size: 9)).foregroundColor(Theme.inkPrimary)
                            Spacer()
                            if let consensus = ratings.consensus {
                                Text(consensus)
                                    .font(Theme.officialStampFont(size: 8))
                                    .foregroundColor(consensus == "BUY" ? Theme.bullGreen : consensus == "SELL" ? Theme.bearRed : Theme.inkSecondary)
                                    .padding(.horizontal, 8).padding(.vertical, 3)
                                    .background((consensus == "BUY" ? Theme.bullGreen : consensus == "SELL" ? Theme.bearRed : Theme.inkSecondary).opacity(0.1))
                                    .clipShape(Capsule())
                            }
                        }
                        HStack(spacing: 16) {
                            Label("\(ratings.buy) Buy", systemImage: "arrow.up.circle.fill").foregroundColor(Theme.bullGreen)
                            Label("\(ratings.hold) Hold", systemImage: "minus.circle.fill").foregroundColor(Theme.inkSecondary)
                            Label("\(ratings.sell) Sell", systemImage: "arrow.down.circle.fill").foregroundColor(Theme.bearRed)
                        }
                        .font(Theme.serialNumberFont(size: 11))
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(ratings.ratings) { r in
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(r.firm).font(Theme.serialNumberFont(size: 9)).foregroundColor(Theme.inkPrimary)
                                        Text(r.grade).font(Theme.officialStampFont(size: 8))
                                            .foregroundColor(brokerGradeColor(r.grade))
                                        Text(r.period).font(Theme.serialNumberFont(size: 8)).foregroundColor(Theme.inkTertiary)
                                    }
                                    .padding(8).banknoteCard()
                                }
                            }
                        }
                    }
                    .padding(16).banknoteCard()
                }

                // ── Street Intelligence — Advisor Matrix ──────────────
                AdvisoryMatrixCard(
                    insights: analysis.advisorMatrix,
                    ticker: analysis.ticker
                )

                Spacer(minLength: 80)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, 16)
        }
    }

    // MARK: - Tab 2: Charts

    @ViewBuilder
    private func tabCharts(_ analysis: StockAnalysis) -> some View {
        ScrollView {
            VStack(spacing: 16) {
                if let qi = viewModel.quickInfo, let low = qi.week52Low, let high = qi.week52High {
                    PriceRangeGauge(low52w: low, high52w: high, current: qi.price, target12m: analysis.targetPrices.mediumTerm12m)
                        .padding(20).banknoteCard()
                }

                if let history = viewModel.quickInfo?.priceHistory90d, !history.isEmpty {
                    PriceHistoryChart(prices: history, ticker: ticker, week52High: viewModel.quickInfo?.week52High, week52Low: viewModel.quickInfo?.week52Low)
                        .padding(20).banknoteCard()
                    RSIChart(prices: history)
                        .padding(20).banknoteCard()
                    VolumeChart(prices: history)
                        .padding(20).banknoteCard()
                } else {
                    VStack(spacing: 12) {
                        Image(systemName: "chart.xyaxis.line")
                            .font(.system(size: 32)).foregroundColor(Theme.inkTertiary)
                        Text("Charts load after quick-info fetch completes")
                            .font(Theme.serialNumberFont(size: 13)).foregroundColor(Theme.inkTertiary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(40)
                }

                // ── Stock vs Nifty (only for held stocks with purchase date)
                if let pd = parsedPurchaseDate, !viewModel.niftyPrices.isEmpty,
                   let history = viewModel.quickInfo?.priceHistory90d, !history.isEmpty {
                    StockVsNiftyChart(
                        stockPrices: history,
                        niftyPrices: viewModel.niftyPrices,
                        purchaseDate: pd,
                        ticker: ticker
                    )
                    .padding(20).banknoteCard()
                }

                Spacer(minLength: 80)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, 16)
        }
    }

    // MARK: - Tab 3: Fundamentals

    @ViewBuilder
    private func tabFundamentals(_ analysis: StockAnalysis) -> some View {
        ScrollView {
            VStack(spacing: 16) {
                // Key numbers grid
                VStack(alignment: .leading, spacing: 12) {
                    Text("मुख्य आंकड़े / KEY NUMBERS")
                        .font(Theme.officialStampFont(size: 9)).foregroundColor(Theme.inkPrimary)
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
                        StatNoteCell(label: "P/E RATIO", value: analysis.fundamentalsSnapshot.peRatio.map { String(format: "%.1f", $0) } ?? "N/A")
                        StatNoteCell(label: "D/E RATIO", value: (analysis.fundamentalsSnapshot.debtToEquity ?? viewModel.quickInfo?.debtToEquity).map { String(format: "%.2f", $0) } ?? "N/A")
                        StatNoteCell(label: "PROMOTER", value: (analysis.fundamentalsSnapshot.promoterHoldingPct ?? viewModel.quickInfo?.promoterHoldingPct ?? viewModel.promoterHistory.last?.promoter).map { String(format: "%.1f%%", $0) } ?? "N/A")
                        StatNoteCell(label: "INSTITUTION", value: analysis.fundamentalsSnapshot.fiiHoldingPct.map { String(format: "%.1f%%", $0) } ?? "N/A")
                        StatNoteCell(label: "DII", value: analysis.fundamentalsSnapshot.diiHoldingPct.map { String(format: "%.1f%%", $0) } ?? "N/A")
                    }

                    if let pva = viewModel.quickInfo?.peVsAvg {
                        ValuationBadge(peVsAvg: pva)
                    }
                }

                // Promoter/FII/DII trend (if history available)
                if !viewModel.promoterHistory.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("INSIDER TREND")
                            .font(Theme.officialStampFont(size: 9)).foregroundColor(Theme.inkPrimary)
                        ForEach(viewModel.promoterHistory) { point in
                            HStack(spacing: 0) {
                                Text(point.period)
                                    .font(Theme.serialNumberFont(size: 10)).foregroundColor(Theme.inkTertiary)
                                    .frame(width: 90, alignment: .leading)
                                TrendBar(label: "PRO", value: point.promoter, color: Color(hex: "4A5A8A"))
                                TrendBar(label: "FII", value: point.fii, color: Theme.bullGreen)
                                TrendBar(label: "DII", value: point.dii, color: Theme.securityGold)
                            }
                        }
                    }
                    .padding(16).banknoteCard()
                }

                // Shareholding chart
                let fs = analysis.fundamentalsSnapshot
                let promoterVal = fs.promoterHoldingPct ?? 0
                let fiiVal = fs.fiiHoldingPct ?? 0
                let diiVal = fs.diiHoldingPct ?? 0
                let holdingTotal = promoterVal + fiiVal + diiVal
                if holdingTotal > 1 {
                    ShareholdingChart(
                        promoterPct: promoterVal,
                        fiiPct: fiiVal,
                        diiPct: diiVal,
                        publicPct: max(0, 100 - holdingTotal)
                    )
                    .padding(20).banknoteCard()
                }

                // Financials chart
                if !viewModel.quarterlyFinancials.isEmpty {
                    FinancialsChart(quarters: viewModel.quarterlyFinancials)
                        .padding(20).banknoteCard()
                }

                // Disclaimer
                AnalysisLimitationsCard(disclaimer: analysis.disclaimer)

                Spacer(minLength: 80)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, 16)
        }
    }

    // MARK: - Tab 4: News

    @ViewBuilder
    private func tabNews(_ analysis: StockAnalysis) -> some View {
        ScrollView {
            VStack(spacing: 12) {
                let news = analysis.recentNews ?? viewModel.quickInfo?.recentNews ?? []
                if news.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "newspaper")
                            .font(.system(size: 32)).foregroundColor(Theme.inkTertiary)
                        Text("No recent news available")
                            .font(Theme.serialNumberFont(size: 13)).foregroundColor(Theme.inkTertiary)
                    }
                    .padding(60)
                } else {
                    ForEach(news) { item in
                        NewsItemCard(item: item)
                    }
                }
                Spacer(minLength: 80)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, 16)
        }
    }

    private func brokerGradeColor(_ grade: String) -> Color {
        let g = grade.uppercased()
        if g.contains("BUY") || g.contains("OUTPERFORM") || g.contains("OVERWEIGHT") || g.contains("ACCUMULATE") || g.contains("ADD") {
            return Theme.bullGreen
        }
        if g.contains("SELL") || g.contains("UNDERPERFORM") || g.contains("UNDERWEIGHT") || g.contains("REDUCE") || g.contains("AVOID") {
            return Theme.bearRed
        }
        return Theme.inkSecondary
    }

    @ViewBuilder
    private func renderErrorState(_ info: AnalysisErrorInfo) -> some View {
        ScrollView {
            VStack(spacing: 20) {
                // ── Stock Header Card ──────────────────────────────────
                if let qi = viewModel.quickInfo {
                    VStack(spacing: 16) {
                        HStack(spacing: 16) {
                            StockIcon(ticker: qi.ticker, signal: qi.signal)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(qi.ticker)
                                    .font(Theme.serialNumberFont(size: 24))
                                    .foregroundColor(Theme.inkPrimary)
                                Text("OFFICIAL QUOTATION")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundColor(Theme.inkSecondary)
                            }
                            Spacer()
                        }
                        GuillocheDivider()
                        VStack(alignment: .leading, spacing: 8) {
                            HStack(alignment: .firstTextBaseline, spacing: 4) {
                                Text("₹")
                                    .font(Theme.engravedSerif(size: 24, weight: .bold))
                                    .foregroundColor(Theme.securityGold)
                                Text(qi.price.inrFormatted.replacingOccurrences(of: "₹", with: ""))
                                    .font(Theme.serialNumberFont(size: 44))
                                    .foregroundColor(Theme.inkPrimary)
                            }
                            HStack(spacing: 8) {
                                Text(qi.change >= 0 ? "+" : "") + Text(qi.change.inrFormatted)
                                Text("(\(qi.changePercent.percentFormatted))")
                            }
                            .font(Theme.serialNumberFont(size: 16))
                            .foregroundColor(qi.change >= 0 ? Theme.bullGreen : Theme.bearRed)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(24)
                        .banknoteCard()
                    }
                    .padding(.top, 20)
                }

                // ── Error Summary Card ─────────────────────────────────
                VStack(spacing: 16) {
                    HStack(spacing: 12) {
                        Image(systemName: info.iconName)
                            .font(.system(size: 28))
                            .foregroundColor(info.isRateLimit ? Theme.holdAmber : Theme.bearRed)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(info.displayTitle)
                                .font(Theme.engravedSerif(size: 16, weight: .bold))
                                .foregroundColor(Theme.inkPrimary)
                            BanknoteSignalBadge(text: info.badgeText, color: info.isRateLimit ? Theme.holdAmber : Theme.bearRed, rotation: -3)
                        }
                        Spacer()
                        if let code = info.diagnostic?.errorCode {
                            Text(code)
                                .font(Theme.officialStampFont(size: 8))
                                .foregroundColor(Theme.inkTertiary)
                                .padding(.horizontal, 8).padding(.vertical, 4)
                                .background(Theme.inkTertiary.opacity(0.1))
                                .clipShape(Capsule())
                        }
                    }

                    GuillocheDivider()

                    Text(info.suggestedActionText)
                        .font(.system(size: 13, weight: .medium))
                        .foregroundColor(info.isRateLimit ? Theme.holdAmber : Theme.securityGold)
                        .lineSpacing(4)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(20)
                .banknoteCard()

                // ── What Went Wrong ────────────────────────────────────
                VStack(alignment: .leading, spacing: 12) {
                    Label {
                        Text("WHAT WENT WRONG")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkPrimary)
                    } icon: {
                        Image(systemName: "magnifyingglass")
                            .foregroundColor(Theme.bearRed)
                            .font(.system(size: 12))
                    }

                    Text(info.displayDetail)
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(Theme.inkSecondary)
                        .lineSpacing(5)

                    if let phase = info.diagnostic?.phaseFailed {
                        HStack(spacing: 6) {
                            Text("FAILED PHASE:")
                                .font(Theme.officialStampFont(size: 8))
                                .foregroundColor(Theme.inkTertiary)
                            Text(phase.replacingOccurrences(of: "_", with: " ").uppercased())
                                .font(Theme.serialNumberFont(size: 10))
                                .foregroundColor(Theme.bearRed)
                        }
                    }
                }
                .padding(20)
                .banknoteCard()

                // ── Performance Trace ──────────────────────────────────
                VStack(alignment: .leading, spacing: 12) {
                    Label {
                        Text("PERFORMANCE TRACE")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkPrimary)
                    } icon: {
                        Image(systemName: "stopwatch")
                            .foregroundColor(Theme.securityGold)
                            .font(.system(size: 12))
                    }

                    VStack(spacing: 8) {
                        HStack {
                            Text("Total elapsed:")
                                .font(Theme.serialNumberFont(size: 11))
                                .foregroundColor(Theme.inkTertiary)
                            Spacer()
                            Text(String(format: "%.1fs", info.elapsedSeconds))
                                .font(Theme.serialNumberFont(size: 11))
                                .foregroundColor(info.elapsedSeconds > 30 ? Theme.bearRed : Theme.inkPrimary)
                        }
                        if let qiElapsed = info.quickInfoElapsed {
                            HStack {
                                Text("Parallel data fetch:")
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundColor(Theme.inkTertiary)
                                Spacer()
                                Text(String(format: "%.1fs", qiElapsed))
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundColor(Theme.bullGreen)
                            }
                            let analyzeElapsed = info.elapsedSeconds - qiElapsed
                            if analyzeElapsed > 0 {
                                HStack {
                                    Text("Analyze API call:")
                                        .font(Theme.serialNumberFont(size: 11))
                                        .foregroundColor(Theme.inkTertiary)
                                    Spacer()
                                    Text(String(format: "%.1fs", analyzeElapsed))
                                        .font(Theme.serialNumberFont(size: 11))
                                        .foregroundColor(Theme.bearRed)
                                }
                            }
                        }
                        if let ts = info.diagnostic?.timestamp {
                            HStack {
                                Text("Failed at:")
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundColor(Theme.inkTertiary)
                                Spacer()
                                Text(ts)
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundColor(Theme.inkSecondary)
                            }
                        }
                    }
                }
                .padding(20)
                .banknoteCard()

                // ── Network Trace ──────────────────────────────────────
                VStack(alignment: .leading, spacing: 12) {
                    Label {
                        Text("NETWORK TRACE")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkPrimary)
                    } icon: {
                        Image(systemName: "network")
                            .foregroundColor(Theme.inkSecondary)
                            .font(.system(size: 12))
                    }

                    VStack(alignment: .leading, spacing: 6) {
                        TraceRow(label: "URL", value: info.requestUrl)
                        TraceRow(label: "Method", value: "POST")
                        TraceRow(label: "HTTP Status", value: "\(info.httpStatusCode)")
                        if !info.responseHeaders.isEmpty {
                            CollapsibleSection(header: "RESPONSE HEADERS") {
                                Text(info.responseHeaders)
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundColor(Theme.inkTertiary)
                                    .lineSpacing(3)
                            }
                        }
                        if !info.responseBody.isEmpty {
                            CollapsibleSection(header: "RAW RESPONSE BODY") {
                                Text(info.responseBody)
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundColor(Theme.inkTertiary)
                                    .lineSpacing(3)
                            }
                        }
                    }
                }
                .padding(20)
                .banknoteCard()

                // ── Backend Diagnostic ─────────────────────────────────
                if let diagInfo = info.diagnostic?.diagnosticInfo, !diagInfo.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Label {
                            Text("BACKEND DIAGNOSTIC")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundColor(Theme.inkPrimary)
                        } icon: {
                            Image(systemName: "gearshape.2")
                                .foregroundColor(Theme.holdAmber)
                                .font(.system(size: 12))
                        }

                        CollapsibleSection(header: "SERVER TRACE (tap to expand)") {
                            Text(diagInfo)
                                .font(Theme.serialNumberFont(size: 10))
                                .foregroundColor(Theme.inkTertiary)
                                .lineSpacing(4)
                        }
                    }
                    .padding(20)
                    .banknoteCard()
                }

                // ── Client Context ─────────────────────────────────────
                VStack(alignment: .leading, spacing: 12) {
                    Label {
                        Text("CLIENT CONTEXT")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundColor(Theme.inkPrimary)
                    } icon: {
                        Image(systemName: "iphone")
                            .foregroundColor(Theme.inkSecondary)
                            .font(.system(size: 12))
                    }

                    VStack(spacing: 6) {
                        TraceRow(label: "App", value: "StockMe v\(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?.?.?")")
                        TraceRow(label: "Mock Mode", value: info.isMockMode ? "ON" : "OFF")
                        TraceRow(label: "Deep Scan", value: info.isDeepScan ? "ON" : "OFF")
                        TraceRow(label: "Base URL", value: info.requestUrl)
                    }
                }
                .padding(20)
                .banknoteCard()

                // ── Action Buttons ─────────────────────────────────────
                VStack(spacing: 12) {
                    Button(action: {
                        HapticManager.impact(.medium)
                        viewModel.fetchAnalysis(ticker: ticker, userId: authManager.currentUser?.userId, useMock: useMockAI, reportManager: reportManager, deepScan: deepScanEnabled)
                    }) {
                        HStack(spacing: 8) {
                            Image(systemName: "arrow.clockwise")
                            Text("RETRY ANALYSIS")
                        }
                        .font(Theme.officialStampFont(size: 10))
                        .foregroundColor(Theme.inkPrimary)
                        .padding(.vertical, 14)
                        .frame(maxWidth: .infinity)
                        .overlay(RoundedRectangle(cornerRadius: 2).stroke(Theme.inkPrimary, lineWidth: 1))
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
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(impacts) { item in
                    MacroImpactChip(item: item)
                }
            }
            .padding(.horizontal)
        }
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

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 3) {
                Text(item.ticker)
                    .font(.system(.caption2, design: .monospaced).weight(.bold))
                Text(directionArrow)
                    .font(.caption2)
            }
            .foregroundColor(.white)
            Text(shortImpact)
                .font(.system(size: 10, design: .serif))
                .foregroundColor(.white.opacity(0.85))
                .lineLimit(1)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
        .background(chipColor.opacity(0.8))
        .cornerRadius(6)
    }
}

// MARK: - Macro Chip

private struct MacroChip: View {
    let label: String
    let value: String
    let color: Color
    var body: some View {
        VStack(spacing: 3) {
            Text(label)
                .font(Theme.officialStampFont(size: 7))
                .foregroundColor(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 11))
                .foregroundColor(color)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
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
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.system(size: 14))
                    .foregroundColor(color)
                VStack(alignment: .leading, spacing: 1) {
                    Text(hindiTitle)
                        .font(Theme.hindiFont(size: 9))
                        .foregroundColor(Theme.inkTertiary)
                    Text(title)
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundColor(Theme.inkPrimary)
                }
            }
            GuillocheDivider()
            Text(text)
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(Theme.inkSecondary)
                .lineSpacing(4)
        }
        .padding(16)
        .background(color.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(color.opacity(0.2), lineWidth: 0.8))
    }
}

// MARK: - Perforation Bar (dotted confidence indicator)

private struct PerforationBar: View {
    let percent: Int

    var body: some View {
        HStack(spacing: 3) {
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
            HStack(spacing: 16) {
                if let urlStr = item.imageUrl, let url = URL(string: urlStr) {
                    AsyncImage(url: url) { image in
                        image.resizable().aspectRatio(contentMode: .fill)
                    } placeholder: {
                        Rectangle().fill(Theme.inkSecondary.opacity(0.1))
                    }
                    .frame(width: 80, height: 80)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                }

                VStack(alignment: .leading, spacing: 6) {
                    Text(item.title)
                        .font(Theme.engravedSerif(size: 15, weight: .bold))
                        .foregroundColor(Theme.inkPrimary)
                        .lineLimit(3)
                        .multilineTextAlignment(.leading)
                    
                    HStack {
                        Text(item.publisher.uppercased())
                            .font(Theme.officialStampFont(size: 8))
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.system(size: 10))
                    }
                    .foregroundColor(Theme.inkSecondary)
                }
            }
            .padding(12)
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
        VStack(alignment: .leading, spacing: 12) {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 8))
                .foregroundColor(Theme.inkSecondary)

            Text(target.inrFormatted)
                .font(Theme.serialNumberFont(size: 18))
                .foregroundColor(Theme.inkPrimary)

            HStack(spacing: 4) {
                Image(systemName: upside >= 0 ? "arrow.up.right" : "arrow.down.right")
                Text("\(upside.percentFormatted)")
            }
            .font(Theme.serialNumberFont(size: 11))
            .foregroundColor(upside >= 0 ? Theme.bullGreen : Theme.bearRed)
        }
        .padding(16)
        .frame(width: 130)
        .banknoteCard()
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
        VStack(alignment: .leading, spacing: 16) {
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .foregroundColor(Theme.inkPrimary)

            VStack(alignment: .leading, spacing: 14) {
                ForEach(items, id: \.self) { item in
                    HStack(alignment: .top, spacing: 12) {
                        Rectangle()
                            .fill(color.opacity(0.5))
                            .frame(width: 2, height: 14)
                            .padding(.top, 4)
                        Text(item)
                            .font(.system(size: 14, weight: .medium))
                            .foregroundColor(Theme.inkSecondary)
                            .lineSpacing(4)
                    }
                }
            }
        }
        .padding(24)
        .banknoteCard()
        .overlay(
            HStack(spacing: 0) {
                Rectangle()
                    .fill(color.opacity(0.25))
                    .frame(width: 2)
                Spacer()
            }
            .clipShape(RoundedRectangle(cornerRadius: 8))
        )
    }
}

// MARK: - Stat Note Cell

private struct StatNoteCell: View {
    let label: String
    let value: String
    @State private var showGlossary = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 4) {
                Text(label)
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundColor(Theme.inkSecondary)
                Image(systemName: "questionmark.circle")
                    .font(.system(size: 8))
                    .foregroundColor(Theme.inkTertiary.opacity(0.6))
            }
            Text(value)
                .font(Theme.serialNumberFont(size: 16))
                .foregroundColor(Theme.inkPrimary)
        }
        .padding(16)
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
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("CONFIDENCE SCORE")
                        .font(Theme.officialStampFont(size: 8)).foregroundColor(Theme.inkSecondary)
                    Text(label)
                        .font(Theme.engravedSerif(size: 15, weight: .bold)).foregroundColor(color)
                }
                Spacer()
                Text("\(percent)%")
                    .font(Theme.serialNumberFont(size: 22)).foregroundColor(color)
            }
            PerforationBar(percent: percent)
            if percent < 50 {
                HStack(spacing: 6) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 10)).foregroundColor(Theme.holdAmber)
                    Text("Uncertainty is high. Cross-check before acting.")
                        .font(.system(size: 11, weight: .medium)).foregroundColor(Theme.holdAmber)
                }
            }
        }
        .padding(20).banknoteCard()
    }
}

// MARK: - Trend Bar (for promoter history)

private struct TrendBar: View {
    let label: String
    let value: Double
    let color: Color
    var body: some View {
        VStack(spacing: 2) {
            Text(String(format: "%.1f%%", value))
                .font(.system(size: 9, weight: .medium)).foregroundColor(color)
            GeometryReader { geo in
                RoundedRectangle(cornerRadius: 2)
                    .fill(color.opacity(0.25))
                    .frame(width: geo.size.width)
                RoundedRectangle(cornerRadius: 2)
                    .fill(color)
                    .frame(width: geo.size.width * min(value / 80.0, 1.0))
            }
            .frame(height: 6)
            Text(label).font(.system(size: 7)).foregroundColor(Theme.inkTertiary)
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
        HStack(spacing: 10) {
            Image(systemName: isAbove ? "arrow.up.circle.fill" : "arrow.down.circle.fill")
                .foregroundColor(badgeColor)
                .font(.system(size: 16))
            VStack(alignment: .leading, spacing: 2) {
                Text("VALUATION VS HISTORY")
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundColor(Theme.inkSecondary)
                Text("Trading \(String(format: "%.0f", absPct))% \(isAbove ? "above" : "below") 3Y avg valuation")
                    .font(Theme.serialNumberFont(size: 12))
                    .foregroundColor(badgeColor)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text("NOW").font(Theme.officialStampFont(size: 7)).foregroundColor(Theme.inkTertiary)
                Text(String(format: "%.1f", peVsAvg.currentPe)).font(Theme.serialNumberFont(size: 13)).foregroundColor(Theme.inkPrimary)
                Text("AVG").font(Theme.officialStampFont(size: 7)).foregroundColor(Theme.inkTertiary)
                Text(String(format: "%.1f", peVsAvg.avgPe3y)).font(Theme.serialNumberFont(size: 11)).foregroundColor(Theme.inkSecondary)
            }
        }
        .padding(12)
        .background(badgeColor.opacity(0.07))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(badgeColor.opacity(0.35), lineWidth: 1))
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
                VStack(alignment: .leading, spacing: 20) {
                    Text(term)
                        .font(Theme.engravedSerif(size: 22, weight: .bold))
                        .foregroundColor(Theme.inkPrimary)
                    GuillocheDivider()
                    Text(glossaryDefinitions[term] ?? "No definition available for this term.")
                        .font(.system(size: 16, weight: .medium))
                        .foregroundColor(Theme.inkSecondary)
                        .lineSpacing(6)
                    Spacer()
                }
                .padding(28)
            }
            .navigationTitle("शब्दावली / Glossary")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }.foregroundColor(Theme.securityGold)
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
        VStack(alignment: .leading, spacing: 10) {
            Button(action: {
                withAnimation(.easeInOut(duration: 0.25)) { expanded.toggle() }
            }) {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(Theme.securityGold)
                    Text("HOW TO READ THIS ANALYSIS")
                        .font(Theme.officialStampFont(size: 9)).foregroundColor(Theme.inkPrimary)
                    Spacer()
                    Image(systemName: expanded ? "chevron.up" : "chevron.down")
                        .font(.system(size: 10)).foregroundColor(Theme.inkTertiary)
                }
            }
            .buttonStyle(.plain)

            if expanded || !shownBefore {
                VStack(alignment: .leading, spacing: 8) {
                    Text("⚠️ AI cannot predict black swan events. Geopolitical shocks — wars, sanctions, pandemics — are outside this model's scope. These have caused real losses for investors in the past.")
                        .font(Theme.serialNumberFont(size: 10)).foregroundColor(Theme.bearRed.opacity(0.9))

                    Text("This analysis weights Indian market factors: promoter behaviour, FII/DII flows, retail sentiment, and news momentum. It is not a substitute for your own judgment.")
                        .font(Theme.serialNumberFont(size: 10)).foregroundColor(Theme.inkSecondary)

                    Divider().background(Theme.inkTertiary.opacity(0.3))

                    Text(disclaimer)
                        .font(Theme.serialNumberFont(size: 9)).foregroundColor(Theme.inkTertiary)
                }
                .onAppear { shownBefore = true }
            }
        }
        .padding(16).banknoteCard()
    }
}

// MARK: - News Reader View

struct NewsReaderView: View {
    let item: NewsItem
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Hero Image
                    if let urlStr = item.imageUrl, let url = URL(string: urlStr) {
                        AsyncImage(url: url) { image in
                            image.resizable().aspectRatio(contentMode: .fill)
                        } placeholder: {
                            Rectangle().fill(Theme.inkSecondary.opacity(0.1))
                        }
                        .frame(height: 240)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                        .padding(.horizontal, Theme.screenPadding)
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        Text(item.title)
                            .font(Theme.engravedSerif(size: 24, weight: .bold))
                            .foregroundColor(Theme.inkPrimary)
                            .lineSpacing(4)

                        HStack {
                            Text(item.publisher.uppercased())
                                .font(Theme.officialStampFont(size: 10))
                                .foregroundColor(Theme.securityGold)
                            
                            if let time = item.publishTime {
                                Text("•")
                                Text(Date(timeIntervalSince1970: TimeInterval(time)), style: .date)
                            }
                        }
                        .font(Theme.serialNumberFont(size: 11))
                        .foregroundColor(Theme.inkTertiary)

                        GuillocheDivider()

                        if let summary = item.summary, !summary.isEmpty {
                            Text(summary)
                                .font(.system(size: 17, weight: .medium, design: .serif))
                                .foregroundColor(Theme.inkSecondary)
                                .lineSpacing(8)
                        } else {
                            Text("Summary not available. Please read the full story for more details.")
                                .italic()
                                .font(Theme.serialNumberFont(size: 14))
                                .foregroundColor(Theme.inkTertiary)
                        }

                        Link(destination: URL(string: item.link)!) {
                            HStack {
                                Text("READ FULL STORY ON \(item.publisher.uppercased())")
                                Image(systemName: "arrow.up.right")
                            }
                            .font(Theme.officialStampFont(size: 11))
                            .foregroundColor(.white)
                            .padding(.vertical, 14)
                            .frame(maxWidth: .infinity)
                            .background(Theme.inkPrimary)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
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
                            .foregroundColor(Theme.inkTertiary)
                            .font(.system(size: 24))
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
        HStack(alignment: .top, spacing: 8) {
            Text(label)
                .font(Theme.serialNumberFont(size: 10))
                .foregroundColor(Theme.inkTertiary)
                .frame(width: 90, alignment: .leading)
            Text(value)
                .font(Theme.serialNumberFont(size: 10))
                .foregroundColor(Theme.inkSecondary)
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
        VStack(alignment: .leading, spacing: 8) {
            Button(action: {
                withAnimation(.easeInOut(duration: 0.2)) { expanded.toggle() }
            }) {
                HStack(spacing: 6) {
                    Image(systemName: expanded ? "chevron.down" : "chevron.right")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(Theme.securityGold)
                    Text(header)
                        .font(Theme.serialNumberFont(size: 10))
                        .foregroundColor(Theme.inkSecondary)
                    Spacer()
                }
            }
            .buttonStyle(.plain)

            if expanded {
                VStack(alignment: .leading, spacing: 4) {
                    content()
                }
                .padding(.leading, 16)
                .padding(.vertical, 8)
                .background(Theme.canvasDeep.opacity(0.5))
                .clipShape(RoundedRectangle(cornerRadius: 6))
            }
        }
    }
}
