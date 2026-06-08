import SwiftUI

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

    // Discover / Screener
    @State private var activePreset: String? = nil
    @State private var screenerResults: [ScreenerResult] = []
    @State private var screenerLoading = false

    // Fallback trending if no movers data available
    private let fallbackTrending = [
        Stock(ticker: "RELIANCE", companyName: "Reliance Industries", exchange: "NSE", currentPrice: 0, changePercent: 0, signal: nil),
        Stock(ticker: "TCS", companyName: "Tata Consultancy", exchange: "NSE", currentPrice: 0, changePercent: 0, signal: nil),
        Stock(ticker: "HDFCBANK", companyName: "HDFC Bank", exchange: "NSE", currentPrice: 0, changePercent: 0, signal: nil),
        Stock(ticker: "INFY", companyName: "Infosys Ltd", exchange: "NSE", currentPrice: 0, changePercent: 0, signal: nil),
        Stock(ticker: "ICICIBANK", companyName: "ICICI Bank Ltd", exchange: "NSE", currentPrice: 0, changePercent: 0, signal: nil),
    ]

    var body: some View {
        NavigationStack {
            ZStack {
                DenominationBackground(denomination: .twoHundred)

                VStack(spacing: 0) {
                    // Bilingual header
                    VStack(alignment: .leading, spacing: 4) {
                        Text("खोजें")
                            .font(Theme.hindiFont(size: 11))
                            .foregroundStyle(Theme.inkSecondary)
                        Text("SEARCH DIRECTORY")
                            .font(Theme.engravedSerif(size: 28, weight: .bold))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, 12)
                    .padding(.bottom, 16)

                    // Search field
                    VStack(alignment: .leading, spacing: 8) {
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
                                        Button(action: { hideKeyboard() }) {
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
                                Button(action: {
                                    searchText = ""
                                    hideKeyboard()
                                }) {
                                    Image(systemName: "xmark.circle.fill")
                                        .foregroundStyle(Theme.inkSecondary)
                                }
                                .accessibilityLabel("Clear search")
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
                    .padding(.bottom, 12)

                    // Discover screener pills — glass capsule strip
                    if searchText.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("DISCOVER / खोजें")
                                .font(Theme.officialStampFont(size: 8))
                                .foregroundStyle(Theme.inkSecondary)
                                .padding(.horizontal, Theme.screenPadding)

                            ScrollView(.horizontal) {
                                HStack(spacing: Theme.Spacing.medium) {
                                    ForEach(screenerPresets, id: \.preset) { item in
                                        Button {
                                            HapticManager.light()
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
                                }
                                .padding(.horizontal, Theme.screenPadding)
                            }
                            .scrollIndicators(.hidden)
                        }
                        .padding(.bottom, 4)
                    }

                    // Results section
                    VStack(alignment: .leading, spacing: 12) {
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
                            LazyVStack(spacing: 12) {
                                if !searchText.isEmpty {
                                    // search mode handled below
                                } else if screenerLoading {
                                    HStack {
                                        Spacer()
                                        ProgressView().tint(Theme.securityGold)
                                        Spacer()
                                    }
                                    .padding(.top, 40)
                                } else if activePreset != nil && screenerResults.isEmpty {
                                    VStack(spacing: 12) {
                                        BanknoteSignalBadge(text: "NO RESULTS", color: Theme.inkSecondary, rotation: -3)
                                        Text("No stocks matched this screen")
                                            .font(.subheadline)
                                            .foregroundStyle(Theme.inkSecondary)
                                    }
                                    .padding(.top, 40)
                                } else if activePreset != nil {
                                    ForEach(Array(screenerResults.enumerated()), id: \.element.id) { index, result in
                                        NavigationLink(value: result.ticker) {
                                            ScreenerResultRow(result: result)
                                        }
                                        .staggerAppear(delay: Double(index) * 0.06)
                                    }
                                } else if searchText.isEmpty {
                                    ForEach(trendingStocks) { stock in
                                        NavigationLink(value: stock.ticker) {
                                            StockRow(stock: stock)
                                        }
                                        .ekPressHaptic()
                                    }
                                }

                                if !searchText.isEmpty {
                                    if searchResults.isEmpty && !isSearching {
                                        VStack(spacing: 16) {
                                            BanknoteSignalBadge(text: "NOT FOUND", color: Theme.bearRed, rotation: -4)
                                            Text("No entries matching '\(searchText)'")
                                                .font(.subheadline)
                                                .foregroundStyle(Theme.inkSecondary)
                                            // Still allow direct navigation — user may know the exact ticker
                                            let ticker = searchText.uppercased().trimmingCharacters(in: .whitespaces)
                                            NavigationLink(value: ticker) {
                                                Text("Analyse \(ticker) anyway →")
                                                    .font(.caption)
                                                    .foregroundStyle(Theme.securityGold)
                                            }
                                            .ekPressHaptic()
                                        }
                                        .padding(.top, 60)
                                    } else {
                                        ForEach(searchResults) { entry in
                                            NavigationLink(value: entry.ticker) {
                                                StockEntryRow(entry: entry)
                                            }
                                            .ekPressHaptic()
                                        }
                                        if isSearching {
                                            VStack(spacing: 12) {
                                                ForEach(0..<3, id: \.self) { _ in
                                                    SearchSkeletonRow()
                                                }
                                            }
                                        }
                                        if searchResultsTotalCount > 20 {
                                            Text("Showing top 20 results. Type more to narrow down.")
                                                .font(Theme.serialNumberFont(size: 10))
                                                .foregroundStyle(Theme.inkTertiary)
                                                .padding(.top, 4)
                                        }
                                    }
                                }
                            }
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.bottom, 100)
                        }
                        .simultaneousGesture(
                            DragGesture().onChanged { _ in hideKeyboard() }
                        )
                    }
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
        }
    }

    // MARK: - Screener

    private func runScreener(preset: String) async {
        screenerLoading = true
        screenerResults = []
        screenerResults = (try? await NetworkManager.shared.fetchScreener(preset: preset)) ?? []
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
                    currentPrice: info.price,
                    changePercent: info.changePercent,
                    signal: info.signal
                )
            }
        }
    }
}

private struct ScreenerResultRow: View {
    let result: ScreenerResult

    var body: some View {
        HStack(spacing: 0) {
            Rectangle()
                .fill(Theme.securityGold.opacity(0.4))
                .frame(width: 1)
                .padding(.vertical, Theme.Spacing.standard)

            HStack(spacing: Theme.Spacing.card) {
                StockIcon(ticker: result.ticker, signal: nil)

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    // TICKER — engraved serif for premium feel
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
                // Metrics column — serialNumberFont for all numbers
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
                    if let pcr = result.pcr {
                        Text("PCR:\(String(format: "%.1f", pcr))")
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.holdAmber)
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

private struct StockEntryRow: View {
    let entry: StockEntry

    var body: some View {
        HStack(spacing: 0) {
            Rectangle()
                .fill(Theme.inkSecondary.opacity(0.3))
                .frame(width: 1)
                .padding(.vertical, Theme.Spacing.standard)

            HStack(spacing: 16) {
                StockIcon(ticker: entry.ticker, signal: nil)

                VStack(alignment: .leading, spacing: 4) {
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
            .padding(.leading, 12)
            .padding(.trailing, 16)
        }
        .banknoteCard()
    }
}

private struct SearchSkeletonRow: View {
    var body: some View {
        HStack(spacing: 0) {
            Rectangle()
                .fill(Theme.inkSecondary.opacity(0.15))
                .frame(width: 1)
                .padding(.vertical, Theme.Spacing.standard)

            HStack(spacing: 16) {
                Circle()
                    .fill(Theme.inkTertiary.opacity(0.15))
                    .frame(width: 40, height: 40)
                VStack(alignment: .leading, spacing: 6) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Theme.inkTertiary.opacity(0.15))
                        .frame(width: UIScreen.main.bounds.width * 0.35, height: 12)
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Theme.inkTertiary.opacity(0.1))
                        .frame(width: UIScreen.main.bounds.width * 0.20, height: 9)
                }
                Spacer()
            }
            .padding(.vertical, Theme.Spacing.standard)
            .padding(.leading, 12)
            .padding(.trailing, 16)
        }
        .banknoteCard()
        .shimmerPlaceholder(isLoading: true)
    }
}
