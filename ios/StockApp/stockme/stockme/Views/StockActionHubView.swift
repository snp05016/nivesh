import SwiftUI

// MARK: - Navigation destinations

/// Pushed when a stock card is tapped. Renders the in-screen action hub
/// (replaces the old confirmationDialog).
struct StockActionHubDest: Hashable {
    let ticker: String
    var companyName: String? = nil
    var exchange: String = "NSE"
}

/// How the AI report should launch when pushed from the hub.
enum AnalysisLaunchMode: Hashable {
    case standard
    case deepScan
    case extremeScan
    case cached
    case regenerate
}

/// Pushed from the hub to open the AI report.
struct AnalysisDest: Hashable {
    let ticker: String
    let mode: AnalysisLaunchMode
}

// MARK: - Stock Action Hub

struct StockActionHubView: View {
    let dest: StockActionHubDest
    @Binding var path: NavigationPath
    @Environment(\.dismiss) private var dismiss

    @EnvironmentObject var reportManager: LocalReportManager
    @AppStorage("nivesh_autoRunOnTap") private var autoRunOnTap = false
    @AppStorage("nivesh_defaultScanType") private var defaultScanType = "ask"

    @State private var showHowItWorks = false
    @State private var showCacheAlert = false
    @State private var pendingMode: AnalysisLaunchMode = .standard
    @State private var didAutoRun = false

    private static let deepScanDisabledTickers: Set<String> = [
        "NIFTY", "SENSEX", "BANKNIFTY", "NIFTYBANK", "INDIAVIX",
    ]

    private var cachedReport: StockAnalysis? {
        reportManager.getReport(for: dest.ticker)
    }

    private var cachedScanType: String {
        cachedReport?.cachedScanType ?? cachedReport?.analysisTier ?? "standard"
    }

    private var deepScanForbidden: Bool {
        Self.deepScanDisabledTickers.contains(dest.ticker.uppercased())
    }

    /// Returns a human-readable staleness string for the cached report, or nil if no cache
    private func stalenessSuffix(for cached: StockAnalysis) -> String {
        guard let hours = cached.stalenessHours else { return "" }
        let label = cached.stalenessLabel ?? "Fresh"
        let age: String
        if hours < 1 { age = "\(Int(hours * 60))m ago" }
        else if hours < 24 { age = "\(Int(hours))h ago" }
        else { age = "\(Int(hours / 24))d ago" }
        return "\(label) · \(age)"
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

                    VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                        HStack {
                            SectionHeaderView(title: "AI ANALYSIS")
                            Spacer()
                            Button { HapticManager.selection(); 
    HapticManager.selection()
                                HapticManager.selection()
                                showHowItWorks = true
                            } label: {
                                Image(systemName: "info.circle")
                                    .font(.title3)
                                    .foregroundStyle(Theme.securityGold)
                            }
                            .buttonStyle(EKPressStyle())
                        }

                        VStack(spacing: Theme.Spacing.card) {
                            // Standard analysis
                            actionCard(
                                symbol: "sparkles",
                                title: "Standard Analysis",
                                subtitle: standardSubtitle,
                                tint: Theme.bullGreen
                            ) {
                                tapAnalysis(mode: .standard)
                            }

                            // Deep Scan
                            actionCard(
                                symbol: "scope",
                                title: "Deep Scan",
                                subtitle: deepScanForbidden
                                    ? "Unavailable for indices"
                                    : deepSubtitle,
                                tint: Theme.goldPrimary,
                                disabled: deepScanForbidden
                            ) {
                                tapAnalysis(mode: .deepScan)
                            }

                            // Extreme Analysis
                            actionCard(
                                symbol: "flame.fill",
                                title: "Extreme Analysis",
                                subtitle: deepScanForbidden
                                    ? "Unavailable for indices"
                                    : extremeSubtitle,
                                tint: Theme.bearRed,
                                disabled: deepScanForbidden
                            ) {
                                tapAnalysis(mode: .extremeScan)
                            }
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)

                    Spacer(minLength: 80)
                }
                .padding(.top, Theme.Spacing.large)
            }
        }
        .sheet(isPresented: $showHowItWorks) {
            NavigationStack { AIHowItWorksView() }
        }
        .banknoteDialog(
            "Cached Report Found",
            isPresented: $showCacheAlert,
            message: "A \(pendingModeLabel) analysis already exists. View the cached report or generate a fresh one?",
            buttons: [
                .init("View Cached Report") {
                    path.append(AnalysisDest(ticker: dest.ticker, mode: .cached))
                },
                .init("Regenerate", role: .destructive) {
                    path.append(AnalysisDest(ticker: dest.ticker, mode: pendingMode))
                },
                .cancel()
            ]
        )
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .banknoteBackButton { HapticManager.selection();  dismiss() }
        .onAppear {
            guard autoRunOnTap, !didAutoRun else { return }
            didAutoRun = true
            let mode: AnalysisLaunchMode = {
                switch defaultScanType {
                case "deep": return .deepScan
                case "extreme": return .extremeScan
                default: return .standard
                }
            }()
            tapAnalysis(mode: mode)
        }
    }

    // MARK: - Cache-check logic

    private func tapAnalysis(mode: AnalysisLaunchMode) {
        let cacheType = scanTypeFor(mode)
        if cachedReport != nil && cachedScanType == cacheType {
            pendingMode = mode
            showCacheAlert = true
        } else {
            path.append(AnalysisDest(ticker: dest.ticker, mode: mode))
        }
    }

    private func scanTypeFor(_ mode: AnalysisLaunchMode) -> String {
        switch mode {
        case .standard: return "standard"
        case .deepScan: return "deep"
        case .extremeScan: return "extreme"
        case .cached, .regenerate: return "standard"
        }
    }

    private var pendingModeLabel: String {
        switch pendingMode {
        case .standard: return "Standard"
        case .deepScan: return "Deep"
        case .extremeScan: return "Extreme"
        case .cached, .regenerate: return "Standard"
        }
    }

    // MARK: - Subtitles with cache info

    private var standardSubtitle: String {
        if let cached = cachedReport, cachedScanType == "standard", let suffix = cachedStalenessQuick(cached) {
            return "DeepSeek V4 Flash · 1-round debate · fastest\nCached: \(suffix)"
        }
        return "DeepSeek V4 Flash · 1-round debate · fastest"
    }

    private var deepSubtitle: String {
        if let cached = cachedReport, cachedScanType == "deep", let suffix = cachedStalenessQuick(cached) {
            return "PKScreener + FinBERT · deeper fundamentals\nCached: \(suffix)"
        }
        return "PKScreener + FinBERT · deeper fundamentals"
    }

    private var extremeSubtitle: String {
        if let cached = cachedReport, cachedScanType == "extreme", let suffix = cachedStalenessQuick(cached) {
            return "DeepSeek V4 Pro · 3-round debate · long-form thesis\nCached: \(suffix)"
        }
        return "DeepSeek V4 Pro · 3-round debate · long-form thesis"
    }

    private func cachedStalenessQuick(_ cached: StockAnalysis) -> String? {
        guard let hours = cached.stalenessHours else { return nil }
        let label = cached.stalenessLabel ?? "Fresh"
        if hours < 1 { return "\(label) · \(Int(hours * 60))m ago" }
        else if hours < 24 { return "\(label) · \(Int(hours))h ago" }
        else { return "\(label) · \(Int(hours / 24))d ago" }
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
        Button { HapticManager.selection(); 
    HapticManager.selection()
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
