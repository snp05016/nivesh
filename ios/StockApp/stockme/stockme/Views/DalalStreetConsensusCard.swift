import SwiftUI
import Combine

// MARK: - View State

enum ConsensusViewState {
    case loading
    case loaded(AdvisoryConsensusResponse)
    case empty
    case error

    var isLoading: Bool {
        if case .loading = self { return true }
        return false
    }
}

// MARK: - ViewModel

@MainActor
class AdvisoryConsensusViewModel: ObservableObject {
    @Published var state: ConsensusViewState = .loading
    @AppStorage("consensusLastFetchDate") private var lastFetchTimestamp: Double = 0

    func fetch(userId: Int) {
        // 30-minute cache: if last fetch was < 30 min ago and not in initial loading, skip
        let now = Date().timeIntervalSince1970
        if (now - lastFetchTimestamp) < 1800 && !state.isLoading { return }

        Task {
            do {
                let response = try await NetworkManager.shared.fetchAdvisoryConsensus(userId: userId)
                if response.trendingTickers.isEmpty && response.sectorSignals.isEmpty {
                    state = .empty
                } else {
                    state = .loaded(response)
                }
                lastFetchTimestamp = now
            } catch {
                // On first load: show empty. On subsequent: keep existing state silently.
                if state.isLoading { state = .empty }
            }
        }
    }
}

// MARK: - Colors

private let bullishColor = Theme.bullGreen
private let bearishColor = Theme.bearRed
private let neutralColor = Theme.holdAmber

// MARK: - Indian Number Formatter

private func formatIndianViews(_ count: Int) -> String {
    if count >= 10_000_000 { return String(format: "%.1fCr", Double(count) / 10_000_000) }
    if count >= 100_000 { return String(format: "%.1fL", Double(count) / 100_000) }
    if count >= 1_000 { return String(format: "%.1fK", Double(count) / 1_000) }
    return "\(count)"
}

// MARK: - Stance Color

private func stanceColor(for stance: String) -> Color {
    let upper = stance.uppercased()
    if upper.contains("BULL") { return bullishColor }
    if upper.contains("BEAR") { return bearishColor }
    return neutralColor
}

// MARK: - Main Card

struct DalalStreetConsensusCard: View {
    @ObservedObject var viewModel: AdvisoryConsensusViewModel
    let onTickerTap: (String) -> Void

    var body: some View {
        switch viewModel.state {
        case .loading:
            loadingView
        case .loaded(let response):
            loadedView(response: response)
        case .empty:
            emptyView
        case .error:
            EmptyView()
        }
    }

    // MARK: - Loading

    private var loadingView: some View {
        HStack {
            Spacer()
            ProgressView()
                .progressViewStyle(CircularProgressViewStyle(tint: Theme.inkSecondary))
            Spacer()
        }
        .padding(.vertical, Theme.Spacing.xLarge)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }

    // MARK: - Empty

    private var emptyView: some View {
        AdvisoryConsensusEmptyCard()
            .padding(.horizontal, Theme.screenPadding)
    }

    // MARK: - Loaded

    private func loadedView(response: AdvisoryConsensusResponse) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header row
            HStack(alignment: .top, spacing: 0) {
                SecurityThread()

                VStack(alignment: .leading, spacing: 2) {
                    Text("DALAL STREET ADVISORY CONSENSUS")
                        .font(Theme.officialStampFont(size: 10))
                        .tracking(0.8)
                        .foregroundStyle(Theme.inkPrimary)
                    Text("दलाल स्ट्रीट सलाह")
                        .font(Theme.hindiFont(size: 8))
                        .foregroundStyle(Theme.inkSecondary)
                }
                .padding(.leading, 10)

                Spacer()

                Text("7D")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1)
                    .foregroundStyle(Theme.securityGold)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Theme.securityGold.opacity(0.10))
                    .overlay(
                        RoundedRectangle(cornerRadius: 3)
                            .stroke(Theme.securityGold.opacity(0.35), lineWidth: 0.5)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 3))
            }
            .padding(.top, 14)
            .padding(.trailing, 16)

            GuillocheDivider()
                .padding(.horizontal, 4)

            // Sector heat section
            if !response.sectorSignals.isEmpty {
                Text("SECTOR HEAT")
                    .font(Theme.officialStampFont(size: 8))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)
                    .padding(.horizontal, Theme.Spacing.card)
                    .padding(.bottom, 6)

                VStack(spacing: 8) {
                    ForEach(Array(response.sectorSignals.prefix(3))) { signal in
                        SectorSignalRow(signal: signal)
                    }
                }
                .padding(.horizontal, Theme.Spacing.card)
                .padding(.bottom, 12)

                GuillocheDivider()
                    .padding(.horizontal, 4)
            }

            // Most discussed section
            if !response.trendingTickers.isEmpty {
                Text("MOST DISCUSSED")
                    .font(Theme.officialStampFont(size: 8))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)
                    .padding(.horizontal, Theme.Spacing.card)
                    .padding(.bottom, 6)

                VStack(spacing: 0) {
                    ForEach(Array(response.trendingTickers.prefix(3))) { ticker in
                        TrendingTickerRow(ticker: ticker, onTap: {
                            HapticManager.selection()
                            onTickerTap(ticker.ticker)
                        })
                    }
                }
                .padding(.bottom, Theme.Spacing.medium)
            }
        }
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - Sector Signal Row

private struct SectorSignalRow: View {
    let signal: SectorSignal

    private var total: Int { signal.bullishCount + signal.bearishCount + signal.neutralCount }
    private var bullFraction: CGFloat {
        total > 0 ? CGFloat(signal.bullishCount) / CGFloat(total) : 0
    }

    var body: some View {
        HStack(spacing: 8) {
            // Dominant stance dot
            Circle()
                .fill(dotColor)
                .frame(width: 6, height: 6)

            // Theme name
            Text(stripEmoji(signal.theme).uppercased())
                .font(Theme.officialStampFont(size: 9))
                .tracking(0.5)
                .foregroundStyle(Theme.inkPrimary)
                .lineLimit(1)
                .frame(minWidth: 80, alignment: .leading)

            // Progress bar
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 2)
                    .fill(bearishColor.opacity(0.18))
                RoundedRectangle(cornerRadius: 2)
                    .fill(bullishColor.opacity(0.75))
                    .frame(width: UIScreen.main.bounds.width * 0.25 * bullFraction)
            }
            .frame(height: 5)

            // Count label
            Text("\(signal.bullishCount) BULL / \(signal.bearishCount) BEAR")
                .font(Theme.serialNumberFont(size: 8))
                .foregroundStyle(Theme.inkSecondary)
                .lineLimit(1)
                .frame(minWidth: 80, alignment: .trailing)
        }
        .frame(height: 18)
    }

    private var dotColor: Color {
        if signal.bullishCount > signal.bearishCount { return bullishColor }
        if signal.bearishCount > signal.bullishCount { return bearishColor }
        return neutralColor
    }
}

// MARK: - Trending Ticker Row

private struct TrendingTickerRow: View {
    let ticker: TrendingTicker
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 10) {
                // Ticker label
                Text(stripEmoji(ticker.ticker))
                    .font(Theme.serialNumberFont(size: 12))
                    .foregroundStyle(Theme.inkPrimary)
                    .frame(minWidth: 50, alignment: .leading)

                // Stance dot
                Circle()
                    .fill(stanceColor(for: ticker.dominantStance))
                    .frame(width: 6, height: 6)

                // Mention count
                Text("\(ticker.mentionCount) mentions")
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(1)

                Spacer()

                // Views in Indian format
                HStack(spacing: 3) {
                    Image(systemName: "eye.fill")
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundStyle(Theme.inkTertiary)
                    Text(formatIndianViews(ticker.totalViewCount))
                        .font(Theme.serialNumberFont(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
            .padding(.horizontal, Theme.Spacing.card)
            .padding(.vertical, Theme.Spacing.standard)
        }
        .buttonStyle(EKPressStyle())
        .overlay(
            Rectangle()
                .fill(Theme.borderFine)
                .frame(height: 0.5),
            alignment: .bottom
        )
    }
}
