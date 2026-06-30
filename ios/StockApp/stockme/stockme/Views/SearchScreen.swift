import SwiftUI
import Combine
import Speech
import AVFoundation

class SpeechRecognizerManager: ObservableObject {
    @Published var isRecording = false
    @Published var transcribedText = ""

    private var speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-IN"))
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let audioEngine = AVAudioEngine()

    func toggleRecording() {
        if isRecording {
            stopRecording()
        } else {
            startRecording()
        }
    }

    private func startRecording() {
        SFSpeechRecognizer.requestAuthorization { authStatus in
            DispatchQueue.main.async {
                if authStatus == .authorized {
                    self.startEngine()
                }
            }
        }
    }

    private func startEngine() {
        if audioEngine.isRunning {
            audioEngine.stop()
            recognitionRequest?.endAudio()
            isRecording = false
            return
        }

        do {
            let audioSession = AVAudioSession.sharedInstance()
            try audioSession.setCategory(.record, mode: .measurement, options: .duckOthers)
            try audioSession.setActive(true, options: .notifyOthersOnDeactivation)
        } catch {
            return
        }

        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let recognitionRequest = recognitionRequest else { return }
        recognitionRequest.shouldReportPartialResults = true

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            self.recognitionRequest?.append(buffer)
        }

        audioEngine.prepare()
        do {
            try audioEngine.start()
            isRecording = true
            transcribedText = ""
        } catch {
            return
        }

        recognitionTask = speechRecognizer?.recognitionTask(with: recognitionRequest) { result, error in
            if let result = result {
                DispatchQueue.main.async {
                    self.transcribedText = result.bestTranscription.formattedString
                }
            }
            if error != nil || result?.isFinal == true {
                self.stopRecording()
            }
        }
    }

    func stopRecording() {
        if audioEngine.isRunning {
            audioEngine.stop()
            audioEngine.inputNode.removeTap(onBus: 0)
        }
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionTask = nil
        recognitionRequest = nil
        isRecording = false
    }
}

// Fix 3.19: Strongly-typed ScreenerPreset — use these typed presets, never raw strings
// ScreenerPreset struct defined in EarningsDashboardView; replicate preset list locally
private let screenerPresets: [(label: String, preset: String)] = [
    ("Quality Value", "quality_value"),
    ("Ghar Ghar Modi", "ghar_ghar_modi"),
    ("Earnings Pioneers", "earnings_pioneers"),
    ("Inst. Capitulation", "institutional_capitulation"),
    ("Promoter Conviction", "promoter_conviction"),
    ("FII Accumulation", "fii_accumulation"),
    ("Turnaround", "turnaround"),
    ("52W Low Bullish", "52w_low_bullish"),
]

struct CustomFilter: Codable, Identifiable, Hashable {
    var id: String { name }
    var name: String
    var sectors: [String]
}

class CustomPresetsManager: ObservableObject {
    @Published var presets: [CustomFilter] = [] {
        didSet {
            if let data = try? JSONEncoder().encode(presets) {
                UserDefaults.standard.set(data, forKey: "customScreenerPresets")
            }
        }
    }
    init() {
        if let data = UserDefaults.standard.data(forKey: "customScreenerPresets"),
           let decoded = try? JSONDecoder().decode([CustomFilter].self, from: data) {
            presets = decoded
        }
    }
}

struct StockProfileDest: Hashable {
    let ticker: String
    let exchange: String
}

struct SearchScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var searchText = ""
    @State private var searchResults: [StockEntry] = []
    @State private var trendingStocks: [Stock] = []
    @State private var trendingLoaded = false
    @State private var isSearching = false
    @State private var searchTask: Task<Void, Never>? = nil
    @State private var searchResultsTotalCount: Int = 0
    @FocusState private var isSearchFocused: Bool
    @StateObject private var speechManager = SpeechRecognizerManager()

    // Discover / Screener
    @State private var activePreset: String? = nil
    @State private var activeCustomPreset: CustomFilter? = nil
    @State private var screenerResults: [ScreenerResult] = []
    @State private var screenerLoading = false
    @State private var showFilterSheet = false
    @StateObject private var customPresetsManager = CustomPresetsManager()

    // Navigation path for programmatic push
    @State private var navPath = NavigationPath()

    // Screener action sheet
    @State private var screenerActionResult: ScreenerResult? = nil
    @State private var showScreenerAction = false

    // Stock tap action sheet (universal)
    @State private var stockTapTicker = ""
    @State private var stockTapCompanyName: String? = nil
    @State private var showStockTapAction = false

    // Fallback trending if no movers data available
    private let fallbackTrending = [
        Stock(ticker: "RELIANCE", companyName: "Reliance Industries", exchange: "NSE", currentPrice: 0, changePercent: 0, signal: nil),
        Stock(ticker: "TCS", companyName: "Tata Consultancy", exchange: "NSE", currentPrice: 0, changePercent: 0, signal: nil),
        Stock(ticker: "HDFCBANK", companyName: "HDFC Bank", exchange: "NSE", currentPrice: 0, changePercent: 0, signal: nil),
        Stock(ticker: "INFY", companyName: "Infosys Ltd", exchange: "NSE", currentPrice: 0, changePercent: 0, signal: nil),
        Stock(ticker: "ICICIBANK", companyName: "ICICI Bank Ltd", exchange: "NSE", currentPrice: 0, changePercent: 0, signal: nil),
    ]

    var body: some View {
        NavigationStack(path: $navPath) {
            ZStack {
                DenominationBackground(denomination: .twoHundred)

                VStack(spacing: Theme.Spacing.none) {
                    // Bilingual header
                    VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                        Text("खोजें")
                            .font(Theme.hindiFont(size: 11))
                            .foregroundStyle(Theme.inkSecondary)
                        Text("SEARCH DIRECTORY")
                            .font(Theme.engravedSerif(size: 28, weight: .bold))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, Theme.Spacing.standard)
                    .padding(.bottom, Theme.Spacing.card)

                    // Search field
                    VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                        Text("खोज / SEARCH DIRECTORY")
                            .font(Theme.officialStampFont(size: 8))
                            .foregroundStyle(Theme.inkSecondary)

                        HStack {
                            Image(systemName: "magnifyingglass")
                                .foregroundStyle(Theme.inkSecondary)
                            TextField("Enter ticker or company name...", text: $searchText)
                                .focused($isSearchFocused)
                                .foregroundStyle(Theme.inkPrimary)
                                .tint(Theme.securityGold)
                                .font(Theme.serialNumberFont(size: 14))
                                .autocapitalization(.allCharacters)
                                .disableAutocorrection(true)
                                .toolbar {
                                    ToolbarItemGroup(placement: .keyboard) {
                                        Spacer()
                                        Button(action: { HapticManager.selection(); hideKeyboard() }) {
                                            Image(systemName: "keyboard.chevron.compact.down")
                                                .foregroundStyle(Theme.securityGold)
                                        }
                                        .accessibilityLabel("Dismiss keyboard")
                                    }
                                }
                            if isSearching {
                                ProgressView()
                                    .scaleEffect(0.7)
                                    .tint(Theme.securityGold)
                            } else if !searchText.isEmpty {
                                Button(action: { HapticManager.selection();  HapticManager.selection()
                                    searchText = ""
                                    hideKeyboard()
                                }) {
                                    Image(systemName: "xmark.circle.fill")
                                        .foregroundStyle(Theme.inkSecondary)
                                }
                                .accessibilityLabel("Clear search")
                            }

                            Button(action: { HapticManager.selection();  HapticManager.selection()
                                speechManager.toggleRecording()
                                HapticManager.selection()
                            }) {
                                Image(systemName: speechManager.isRecording ? "mic.fill" : "mic")
                                    .foregroundStyle(speechManager.isRecording ? Theme.bearRed : Theme.securityGold)
                            }

                            Button(action: { HapticManager.selection();  HapticManager.selection()
                                showFilterSheet = true
                            }) {
                                Image(systemName: "line.3.horizontal.decrease.circle")
                                    .foregroundStyle(Theme.securityGold)
                            }
                        }
                        .padding(Theme.Spacing.card)
                        .background(Theme.canvasDeep)
                        .overlay(
                            Rectangle()
                                .stroke(Theme.inkSecondary.opacity(0.3), lineWidth: 1)
                        )
                    }
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.bottom, Theme.Spacing.standard)

                    // Discover screener pills — glass capsule strip
                    if searchText.isEmpty {
                        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                            Text("DISCOVER / खोजें")
                                .font(Theme.officialStampFont(size: 8))
                                .foregroundStyle(Theme.inkSecondary)
                                .padding(.horizontal, Theme.screenPadding)

                            ScrollView(.horizontal) {
                                HStack(spacing: Theme.Spacing.medium) {
                                    ForEach(screenerPresets, id: \.preset) { item in
                                        Button { HapticManager.selection(); 
    HapticManager.selection()
                                            HapticManager.light()
                                            activeCustomPreset = nil
                                            if activePreset == item.preset {
                                                activePreset = nil
                                                screenerResults = []
                                            } else {
                                                activePreset = item.preset
                                                screenerResults = []
                                                Task { await runScreener(preset: item.preset) }
                                            }
                                        } label: {
                                            Text(item.label)
                                                .font(Theme.officialStampFont(size: 9))
                                                .foregroundStyle(activePreset == item.preset ? Theme.canvasDeep : Theme.inkPrimary)
                                                .padding(.horizontal, Theme.Spacing.standard)
                                                .padding(.vertical, Theme.Spacing.medium)
                                                .background(
                                                    Capsule()
                                                        .fill(activePreset == item.preset ? Theme.securityGold : Theme.canvasShadow.opacity(0.4))
                                                )
                                                .shadow(
                                                    color: activePreset == item.preset ? Theme.securityGold.opacity(0.5) : .clear,
                                                    radius: activePreset == item.preset ? 8 : 0
                                                )
                                        }
                                        .buttonStyle(.plain)
                                    }

                                    ForEach(customPresetsManager.presets) { preset in
                                        Button { HapticManager.selection(); 
    HapticManager.selection()
                                            HapticManager.light()
                                            activePreset = nil
                                            if activeCustomPreset == preset {
                                                activeCustomPreset = nil
                                                screenerResults = []
                                            } else {
                                                activeCustomPreset = preset
                                                applyCustomPreset(preset)
                                            }
                                        } label: {
                                            Text(preset.name)
                                                .font(Theme.officialStampFont(size: 9))
                                                .foregroundStyle(activeCustomPreset == preset ? Theme.canvasDeep : Theme.inkPrimary)
                                                .padding(.horizontal, Theme.Spacing.standard)
                                                .padding(.vertical, Theme.Spacing.medium)
                                                .background(
                                                    Capsule()
                                                        .fill(activeCustomPreset == preset ? Theme.securityGold : Theme.canvasShadow.opacity(0.4))
                                                )
                                                .shadow(
                                                    color: activeCustomPreset == preset ? Theme.securityGold.opacity(0.5) : .clear,
                                                    radius: activeCustomPreset == preset ? 8 : 0
                                                )
                                        }
                                        .buttonStyle(.plain)
                                        .contextMenu {
                                            Button(role: .destructive) { HapticManager.selection(); 
                                                customPresetsManager.presets.removeAll { $0.id == preset.id }
                                                if activeCustomPreset == preset {
                                                    activeCustomPreset = nil
                                                    screenerResults = []
                                                }
                                            } label: {
                                                Label("Delete Preset", systemImage: "trash")
                                            }
                                        }
                                    }
                                }
                                .padding(.horizontal, Theme.screenPadding)
                            }
                            .scrollIndicators(.hidden)
                        }
                        .padding(.bottom, Theme.Spacing.small)
                    }

                    // Results section
                    VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                        SectionHeader(
                            title: {
                                if !searchText.isEmpty { return "Search Results" }
                                if activePreset != nil { return activePreset!.replacingOccurrences(of: "_", with: " ").uppercased() }
                                return "Trending Stocks"
                            }(),
                            hindiTitle: {
                                if !searchText.isEmpty { return "खोज परिणाम" }
                                if activePreset != nil { return "स्क्रीनर" }
                                return "चर्चित शेयर"
                            }()
                        )

                        ScrollView {
                            LazyVStack(spacing: Theme.Spacing.standard) {
                                if !searchText.isEmpty {
                                    // search mode handled below
                                } else if screenerLoading {
                                    HStack {
                                        Spacer()
                                        ProgressView().tint(Theme.securityGold)
                                        Spacer()
                                    }
                                    .padding(.top, Theme.Spacing.xLarge)
                                } else if activePreset != nil && screenerResults.isEmpty {
                                    VStack(spacing: Theme.Spacing.standard) {
                                        BanknoteSignalBadge(text: "NO RESULTS", color: Theme.inkSecondary, rotation: -3)
                                        Text("No stocks matched this screen")
                                            .font(.subheadline)
                                            .foregroundStyle(Theme.inkSecondary)
                                    }
                                    .padding(.top, Theme.Spacing.xLarge)
                                } else if activePreset != nil {
                                    ForEach(Array(screenerResults.enumerated()), id: \.element.id) { index, result in
                                        Button { HapticManager.selection(); 
    HapticManager.selection()
                                            HapticManager.selection()
                                            screenerActionResult = result
                                            showScreenerAction = true
                                        } label: {
                                            ScreenerResultRow(result: result)
                                        }
                                        .buttonStyle(EKPressStyle())
                                        .staggerAppear(delay: Double(index) * 0.06)
                                    }
                                } else if searchText.isEmpty {
                                    ForEach(trendingStocks) { stock in
                                        Button { HapticManager.selection(); 
    HapticManager.selection()
                                            HapticManager.selection()
                                            stockTapTicker = stock.ticker
                                            stockTapCompanyName = stock.companyName
                                            showStockTapAction = true
                                        } label: {
                                            StockRow(stock: stock)
                                        }
                                        .buttonStyle(EKPressStyle())
                                    }
                                }

                                if !searchText.isEmpty {
                                    if searchResults.isEmpty && !isSearching {
                                        VStack(spacing: Theme.Spacing.card) {
                                            BanknoteSignalBadge(text: "NOT FOUND", color: Theme.bearRed, rotation: -4)
                                            Text("No entries matching '\(searchText)'")
                                                .font(.subheadline)
                                                .foregroundStyle(Theme.inkSecondary)
                                            // Still allow direct navigation — user may know the exact ticker
                                            let ticker = searchText.uppercased().trimmingCharacters(in: .whitespaces)
                                            Button { HapticManager.selection(); 
    HapticManager.selection()
                                                HapticManager.selection()
                                                stockTapTicker = ticker
                                                stockTapCompanyName = nil
                                                showStockTapAction = true
                                            } label: {
                                                Text("Analyse \(ticker) anyway →")
                                                    .font(.caption)
                                                    .foregroundStyle(Theme.securityGold)
                                            }
                                            .buttonStyle(EKPressStyle())
                                        }
                                        .padding(.top, Theme.sectionSpacing)
                                    } else {
                                        ForEach(searchResults) { entry in
                                            Button { HapticManager.selection(); 
    HapticManager.selection()
                                                HapticManager.selection()
                                                stockTapTicker = entry.ticker
                                                stockTapCompanyName = entry.companyName
                                                showStockTapAction = true
                                            } label: {
                                                StockEntryRow(entry: entry)
                                            }
                                            .buttonStyle(EKPressStyle())
                                        }
                                        if isSearching {
                                            VStack(spacing: Theme.Spacing.standard) {
                                                ForEach(0..<3, id: \.self) { _ in
                                                    SearchSkeletonRow()
                                                }
                                            }
                                        }
                                        if searchResultsTotalCount > 20 {
                                            Text("Showing top 20 results. Type more to narrow down.")
                                                .font(Theme.serialNumberFont(size: 10))
                                                .foregroundStyle(Theme.inkTertiary)
                                                .padding(.top, Theme.Spacing.small)
                                        }
                                    }
                                }
                            }
                            .padding(.horizontal, Theme.screenPadding)
                        }
                        .simultaneousGesture(
                            DragGesture().onChanged { _ in hideKeyboard() }
                        )
                    }
                    .frame(maxHeight: .infinity)
                }
                .frame(maxHeight: .infinity, alignment: .top)
            }
            .onAppear {
                guard !trendingLoaded else { return }
                trendingLoaded = true
                Task { await loadTrending() }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                    isSearchFocused = true
                }
            }
            .onChange(of: searchText) { _, new in
                // Cancel any in-flight search
                searchTask?.cancel()
                guard !new.isEmpty else {
                    searchResults = []
                    searchResultsTotalCount = 0
                    isSearching = false
                    return
                }
                HapticManager.selection()
                // Local instant preview while waiting for backend
                let localHit = StockDatabase.search(new)
                let cappedLocal = Array(localHit.prefix(20))
                searchResults = cappedLocal
                searchResultsTotalCount = localHit.count

                // Debounce 350ms then hit backend
                searchTask = Task {
                    isSearching = true
                    try? await Task.sleep(nanoseconds: 350_000_000)
                    guard !Task.isCancelled else { return }
                    let backendResults = await NetworkManager.shared.searchStocks(q: new)
                    guard !Task.isCancelled else { return }
                    if backendResults.isEmpty {
                        // Backend unavailable — keep local results
                        isSearching = false
                        return
                    }
                    // Merge: backend is authoritative; add any extra not in backend
                    let backendTickers = Set(backendResults.map { $0.ticker })
                    let localExtra = localHit.filter { !backendTickers.contains($0.ticker) }
                    let merged = backendResults + localExtra
                    let capped = Array(merged.prefix(20))
                    let totalCount = merged.count
                    searchResults = capped
                    searchResultsTotalCount = totalCount
                    isSearching = false
                }
            }
            .navigationDestination(for: String.self) { ticker in
                AnalysisScreen(ticker: ticker)
            }
            .navigationDestination(for: StockProfileDest.self) { dest in
                StockProfileView(ticker: dest.ticker, exchange: dest.exchange)
            }
            .navigationDestination(for: StockActionHubDest.self) { dest in
                StockActionHubView(dest: dest, path: $navPath)
            }
            .navigationDestination(for: AnalysisDest.self) { dest in
                AnalysisScreen(ticker: dest.ticker, launchMode: dest.mode)
            }
            .onChange(of: showScreenerAction) { _, show in
                if show, let result = screenerActionResult {
                    navPath.append(StockActionHubDest(ticker: result.ticker, companyName: result.companyName, exchange: "NSE"))
                    showScreenerAction = false
                }
            }
            .onChange(of: showStockTapAction) { _, show in
                if show {
                    navPath.append(StockActionHubDest(ticker: stockTapTicker, companyName: stockTapCompanyName, exchange: "NSE"))
                    showStockTapAction = false
                }
            }
            .sheet(isPresented: $showFilterSheet) {
                FilterSheet(customPresetsManager: customPresetsManager) { preset in
                    activeCustomPreset = preset
                    activePreset = nil
                    applyCustomPreset(preset)
                }
            }
            .onChange(of: speechManager.transcribedText) { _, newText in
                if !newText.isEmpty {
                    searchText = newText
                }
            }
        }
    }

    // MARK: - Screener

    private func runScreener(preset: String) async {
        screenerLoading = true
        screenerResults = []
        do {
            let results = try await NetworkManager.shared.fetchScreener(preset: preset)
            withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                screenerResults = results
            }
        } catch {
            print("Screener failed: \(error)")
        }
        screenerLoading = false
    }

    private func applyCustomPreset(_ preset: CustomFilter) {
        screenerLoading = true
        let filtered = StockDatabase.all.filter { preset.sectors.isEmpty || preset.sectors.contains($0.sector) }
        let mapped = filtered.map { entry in
            ScreenerResult(
                ticker: entry.ticker,
                companyName: entry.companyName,
                signal: "HOLD",
                confidencePct: nil,
                reason: nil,
                fScore: nil,
                peRatio: nil,
                profitGrowthPct: nil,
                rsi: nil,
                pcr: nil,
                currentPrice: nil,
                changePercent: nil,
                sparkline: nil
            )
        }
        screenerResults = Array(mapped.prefix(20))
        screenerLoading = false
    }

    // MARK: - Trending loader

    private func loadTrending() async {
        var tickers: [String] = []
        if let user = authManager.currentUser,
           let brief = try? await NetworkManager.shared.getMorningSummary(userId: user.userId),
           !brief.movers.isEmpty {
            tickers = Array(brief.movers.prefix(5))
        } else {
            tickers = fallbackTrending.map { $0.ticker }
        }

        // Populate with zero prices while fetching — instant display
        trendingStocks = tickers.map { ticker in
            let entry = StockDatabase.all.first { $0.ticker == ticker }
            return Stock(ticker: ticker, companyName: entry?.companyName ?? ticker,
                         exchange: "NSE", currentPrice: 0, changePercent: 0, signal: nil)
        }

        // Fetch prices in parallel
        await withTaskGroup(of: (Int, QuickInfo?).self) { group in
            for (i, ticker) in tickers.enumerated() {
                group.addTask {
                    let info = await NetworkManager.shared.quickInfo(ticker: ticker)
                    return (i, info)
                }
            }
            for await (i, info) in group {
                guard let info, i < trendingStocks.count else { continue }
                trendingStocks[i] = Stock(
                    ticker: info.ticker,
                    companyName: trendingStocks[i].companyName,
                    exchange: "NSE",
                    currentPrice: info.price ?? 0.0,
                    changePercent: info.changePercent ?? 0.0,
                    signal: info.signal
                )
            }
        }
    }
}

	private struct ScreenerResultRow: View {
	    let result: ScreenerResult

	    private var sparklineColor: Color {
	        guard let vals = result.sparkline, vals.count > 1,
	              let first = vals.first, let last = vals.last else { return Theme.inkTertiary }
	        return last >= first ? Theme.bullGreen : Theme.bearRed
	    }

	    var body: some View {
	        HStack(spacing: Theme.Spacing.standard) {
	            // ── Left: 2-letter ticker tile ──────────────────────
	            Text(String(result.ticker.prefix(2)).uppercased())
	                .font(Theme.serialNumberFont(size: 12))
	                .foregroundStyle(Theme.securityGold)
	                .frame(width: 40, height: 40)
	                .background(Theme.canvasDeep)
	                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))

	            // ── Center-left: ticker + company name ──────────────
	            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
	                Text(result.ticker.uppercased())
	                    .font(Theme.serialNumberFont(size: 13))
	                    .foregroundStyle(Theme.inkPrimary)
	                if let company = result.companyName {
	                    Text(company)
	                        .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
	                        .foregroundStyle(Theme.inkSecondary)
	                        .lineLimit(1)
	                }
	            }

	            Spacer()

	            // ── Center: Sparkline ───────────────────────────────
	            if let sparkVals = result.sparkline, sparkVals.count > 1 {
	                SparklineView(values: sparkVals, color: sparklineColor)
	                    .frame(width: 60, height: 32)
	            }

	            // ── Right: price + % badge ──────────────────────────
	            if let price = result.currentPrice {
	                let change = result.changePercent ?? 0
	                let isUp = change >= 0
	                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
	                    Text(IndianFormatter.price(price))
                     .lineLimit(1)
                     .minimumScaleFactor(0.6)
	                        .font(Theme.serialNumberFont(size: 13))
	                        .foregroundStyle(Theme.inkPrimary)
	                    Text(IndianFormatter.percent(change))
                     .lineLimit(1)
                     .minimumScaleFactor(0.6)
	                        .font(Theme.serialNumberFont(size: 11))
	                        .foregroundStyle(isUp ? Theme.bullGreen : Theme.bearRed)
	                        .padding(.horizontal, Theme.Spacing.small)
	                        .padding(.vertical, Theme.Spacing.xSmall)
	                        .background((isUp ? Theme.bullGreen : Theme.bearRed).opacity(0.15))
	                        .cornerRadius(Theme.CornerRadius.small)
	                }
	            }
	        }
	        .padding(.horizontal, Theme.screenPadding)
	        .padding(.vertical, Theme.Spacing.standard)
	        .banknoteCard()
	    }
	}

private struct StockEntryRow: View {
    let entry: StockEntry

    var body: some View {
        HStack(spacing: Theme.Spacing.none) {
            Rectangle()
                .fill(Theme.inkSecondary.opacity(0.3))
                .frame(width: 1)
                .padding(.vertical, Theme.Spacing.standard)

            HStack(spacing: Theme.Spacing.card) {
                StockIcon(ticker: entry.ticker, signal: nil)

                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(entry.companyName.uppercased())
                        .font(Theme.engravedSerif(size: 16, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                    Text("\(entry.ticker) • \(entry.sector)")
                        .font(Theme.serialNumberFont(size: 10))
                        .foregroundStyle(Theme.inkSecondary)
                }
                Spacer()
                Image(systemName: "arrow.right")
                    .foregroundStyle(Theme.inkSecondary.opacity(0.3))
                    .font(.subheadline.weight(.bold))
            }
            .padding(.vertical, Theme.Spacing.standard)
            .padding(.leading, Theme.Spacing.standard)
            .padding(.trailing, Theme.Spacing.card)
        }
        .banknoteCard()
    }
}

private struct SearchSkeletonRow: View {
    var body: some View {
        HStack(spacing: Theme.Spacing.none) {
            Rectangle()
                .fill(Theme.inkSecondary.opacity(0.15))
                .frame(width: 1)
                .padding(.vertical, Theme.Spacing.standard)

            HStack(spacing: Theme.Spacing.card) {
                Circle()
                    .fill(Theme.inkTertiary.opacity(0.15))
                    .frame(width: 40, height: 40)
                VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(Theme.inkTertiary.opacity(0.15))
                        .frame(width: UIScreen.main.bounds.width * 0.35, height: 12)
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(Theme.inkTertiary.opacity(0.1))
                        .frame(width: UIScreen.main.bounds.width * 0.20, height: 9)
                }
                Spacer()
            }
            .padding(.vertical, Theme.Spacing.standard)
            .padding(.leading, Theme.Spacing.standard)
            .padding(.trailing, Theme.Spacing.card)
        }
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }
}

// MARK: - Filter Sheet

private struct FilterSheet: View {
    @Environment(\.dismiss) var dismiss
    @ObservedObject var customPresetsManager: CustomPresetsManager
    var onSelect: (CustomFilter) -> Void

    @State private var newPresetName = ""
    @State private var selectedSectors: Set<String> = []

    private let allSectors = ["IT", "Banking", "FMCG", "Pharma", "Auto", "Oil & Gas",
                               "Steel", "Power", "Telecom", "Finance", "Cement", "Consumer",
                               "Engineering", "Metals", "Paints", "Renewable Energy"]

    var body: some View {
        NavigationStack {
            List {
                Section("Saved Presets") {
                    if customPresetsManager.presets.isEmpty {
                        Text("No saved presets").foregroundStyle(Theme.inkTertiary)
                            .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                    } else {
                        ForEach(customPresetsManager.presets) { preset in
                            Button { HapticManager.selection(); 
    HapticManager.selection()
                                onSelect(preset)
                                dismiss()
                            } label: {
                                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                    Text(preset.name)
                                        .font(Theme.engravedSerif(size: 14, weight: .semibold, relativeTo: .body))
                                        .foregroundStyle(Theme.inkPrimary)
                                    Text(preset.sectors.isEmpty ? "All sectors" : preset.sectors.joined(separator: ", "))
                                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                                        .foregroundStyle(Theme.inkSecondary)
                                }
                            }
                            .buttonStyle(.plain)
                        }
                        .onDelete { indexSet in
                            customPresetsManager.presets.remove(atOffsets: indexSet)
                        }
                    }
                }

                Section("New Preset") {
                    TextField("Preset name", text: $newPresetName)
                        .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                    ForEach(allSectors, id: \.self) { sector in
                        Button { HapticManager.selection(); 
    HapticManager.selection()
                            if selectedSectors.contains(sector) {
                                selectedSectors.remove(sector)
                            } else {
                                selectedSectors.insert(sector)
                            }
                        } label: {
                            HStack {
                                Text(sector)
                                    .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                                    .foregroundStyle(Theme.inkPrimary)
                                Spacer()
                                if selectedSectors.contains(sector) {
                                    Image(systemName: "checkmark").foregroundStyle(Theme.securityGold)
                                }
                            }
                        }
                        .buttonStyle(.plain)
                    }
                    Button("Save Preset") { HapticManager.selection(); 
                        guard !newPresetName.trimmingCharacters(in: .whitespaces).isEmpty else { return }
                        let preset = CustomFilter(name: newPresetName, sectors: Array(selectedSectors))
                        customPresetsManager.presets.append(preset)
                        onSelect(preset)
                        dismiss()
                    }
                    .disabled(newPresetName.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
            .navigationTitle("Sector Filters")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }.buttonStyle(EKPressStyle())
                }
            }
        }
    }
}
