import SwiftUI

// MARK: - YouTube AI Summary Sheet

struct YouTubeSummarySheet: View {
    let video: YouTubeVideoItem
    var onTickerTap: ((String) -> Void)? = nil

    @EnvironmentObject var networkManager: NetworkManager
    @State private var state: LoadState = .idle
    @Environment(\.dismiss) private var dismiss

    private enum LoadState {
        case idle, loading, loaded(YouTubeVideoSummaryResponse), failed(String)
    }

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                    sheetHeader
                    switch state {
                    case .idle, .loading:
                        loadingView
                    case .loaded(let summary):
                        summaryBody(summary)
                    case .failed(let msg):
                        errorView(msg)
                    }
                }
                .padding(.bottom, Theme.Spacing.xLarge)
            }
        }
        .task { await load() }
    }

    // MARK: Header

    private var sheetHeader: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(video.channelName.uppercased())
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .tracking(1.5)
                        .foregroundStyle(Theme.securityGold)
                    Text(video.title)
                        .font(Theme.engravedSerif(size: 17, weight: .semibold, relativeTo: .headline))
                        .foregroundStyle(Theme.inkPrimary)
                        .lineLimit(3)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: Theme.Spacing.medium)
                Button(action: { HapticManager.light(); dismiss() }) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title3)
                        .foregroundStyle(Theme.inkTertiary)
                }
                .buttonStyle(EKPressStyle())
            }
            GuillocheDivider()
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.top, Theme.Spacing.large)
    }

    // MARK: Loading

    private var loadingView: some View {
        VStack(spacing: Theme.Spacing.large) {
            ProgressView()
                .tint(Theme.securityGold)
                .scaleEffect(1.3)
            Text("Generating AI summary...")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.2)
                .foregroundStyle(Theme.inkSecondary)
            Text("Extracting transcript, analysing with DeepSeek")
                .font(.caption2)
                .foregroundStyle(Theme.inkTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, Theme.Spacing.xLarge)
        .padding(.horizontal, Theme.screenPadding)
    }

    // MARK: Error

    private func errorView(_ message: String) -> some View {
        VStack(spacing: Theme.Spacing.medium) {
            Image(systemName: "exclamationmark.triangle")
                .font(.largeTitle)
                .foregroundStyle(Theme.holdAmber)
            Text("Summary unavailable")
                .font(Theme.engravedSerif(size: 15, weight: .semibold, relativeTo: .subheadline))
                .foregroundStyle(Theme.inkPrimary)
            Text(message)
                .font(.caption)
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
            Button("Open on YouTube") {
                HapticManager.selection()
                if let url = URL(string: video.videoUrl) { UIApplication.shared.open(url) }
            }
            .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
            .foregroundStyle(Theme.securityGold)
            .buttonStyle(EKPressStyle())
        }
        .frame(maxWidth: .infinity)
        .padding(.top, Theme.Spacing.xLarge)
        .padding(.horizontal, Theme.screenPadding)
    }

    // MARK: Summary Body

    private func summaryBody(_ resp: YouTubeVideoSummaryResponse) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.large) {
            sentimentBadge(resp.summary.sentiment, provider: resp.source.summaryProvider)
            tldrCard(resp.summary.tldr)
            if !resp.summary.tickersMentioned.isEmpty {
                tickerRow(resp.summary.tickersMentioned)
            }
            if !resp.summary.keyPoints.isEmpty {
                bulletSection(title: "KEY POINTS", icon: "list.bullet", items: resp.summary.keyPoints, color: Theme.securityGold)
            }
            if !resp.summary.financeInsights.isEmpty {
                bulletSection(title: "FINANCE INSIGHTS", icon: "chart.line.uptrend.xyaxis", items: resp.summary.financeInsights, color: Theme.bullGreen)
            }
            if !resp.summary.risksOrRedFlags.isEmpty {
                bulletSection(title: "RISKS & RED FLAGS", icon: "exclamationmark.triangle", items: resp.summary.risksOrRedFlags, color: Theme.bearRed)
            }
            if !resp.summary.actionItems.isEmpty {
                bulletSection(title: "ACTION ITEMS", icon: "checkmark.circle", items: resp.summary.actionItems, color: Theme.holdAmber)
            }
            if !resp.timestamps.isEmpty {
                timestampSection(resp.timestamps)
            }
            watchButton
        }
        .padding(.horizontal, Theme.screenPadding)
    }

    // MARK: Sentiment Badge

    private func sentimentBadge(_ sentiment: String, provider: String) -> some View {
        HStack(spacing: Theme.Spacing.medium) {
            let (label, color) = sentimentStyle(sentiment)
            HStack(spacing: Theme.Spacing.small) {
                Circle().fill(color).frame(width: 8, height: 8)
                Text(label)
                    .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                    .tracking(1.2)
                    .foregroundStyle(color)
            }
            .padding(.horizontal, Theme.Spacing.card)
            .padding(.vertical, Theme.Spacing.small)
            .background(color.opacity(0.12))
            .clipShape(Capsule())

            Spacer()

            Text("via \(provider.uppercased())")
                .font(.caption2.monospaced())
                .foregroundStyle(Theme.inkTertiary)
        }
    }

    private func sentimentStyle(_ s: String) -> (String, Color) {
        switch s.lowercased() {
        case "bullish":  return ("BULLISH", Theme.bullGreen)
        case "bearish":  return ("BEARISH", Theme.bearRed)
        case "mixed":    return ("MIXED", Theme.holdAmber)
        default:         return ("NEUTRAL", Theme.inkSecondary)
        }
    }

    // MARK: TLDR Card

    private func tldrCard(_ text: String) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Label("TLDR", systemImage: "text.quote")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.5)
                .foregroundStyle(Theme.securityGold)
            Text(text.isEmpty ? "No summary available." : text)
                .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .subheadline))
                .foregroundStyle(Theme.inkPrimary)
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
    }

    // MARK: Ticker Row

    private func tickerRow(_ tickers: [String]) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text("MENTIONED")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: Theme.Spacing.small) {
                    ForEach(tickers, id: \.self) { ticker in
                        Button(action: { HapticManager.selection(); onTickerTap?(ticker); dismiss() }) {
                            Text(ticker)
                                .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                                .foregroundStyle(Theme.securityGold)
                                .padding(.horizontal, Theme.Spacing.card)
                                .padding(.vertical, Theme.Spacing.small)
                                .background(Theme.securityGold.opacity(0.10))
                                .overlay(
                                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                        .stroke(Theme.securityGold.opacity(0.30), lineWidth: 0.5)
                                )
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
                        }
                        .buttonStyle(EKPressStyle())
                    }
                }
            }
        }
    }

    // MARK: Bullet Section

    private func bulletSection(title: String, icon: String, items: [String], color: Color) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Label(title, systemImage: icon)
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.5)
                .foregroundStyle(color)
            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                ForEach(items, id: \.self) { item in
                    HStack(alignment: .top, spacing: Theme.Spacing.small) {
                        Circle()
                            .fill(color)
                            .frame(width: 4, height: 4)
                            .padding(.top, 6)
                        Text(item)
                            .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkSecondary)
                            .lineSpacing(2)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            .padding(Theme.Spacing.card)
            .frame(maxWidth: .infinity, alignment: .leading)
            .banknoteCard()
        }
    }

    // MARK: Timestamp Section

    private func timestampSection(_ stamps: [YouTubeSummaryTimestamp]) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text("CHAPTERS")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
            VStack(spacing: 0) {
                ForEach(stamps) { stamp in
                    HStack(alignment: .top, spacing: Theme.Spacing.card) {
                        Text(formatSeconds(stamp.startSeconds))
                            .font(Theme.serialNumberFont(size: 11, relativeTo: .caption2))
                            .foregroundStyle(Theme.securityGold)
                            .frame(width: 40, alignment: .trailing)
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            Text(stamp.label)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(Theme.inkPrimary)
                            if !stamp.summary.isEmpty {
                                Text(stamp.summary)
                                    .font(.caption2)
                                    .foregroundStyle(Theme.inkSecondary)
                                    .lineLimit(2)
                            }
                        }
                        Spacer(minLength: 0)
                    }
                    .padding(.vertical, Theme.Spacing.small)
                    if stamp.id != stamps.last?.id {
                        Divider().padding(.leading, 52)
                    }
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }

    private func formatSeconds(_ s: Int) -> String {
        let m = s / 60; let sec = s % 60
        return String(format: "%d:%02d", m, sec)
    }

    // MARK: Watch Button

    private var watchButton: some View {
        Button(action: {
            HapticManager.selection()
            if let url = URL(string: video.videoUrl) { UIApplication.shared.open(url) }
        }) {
            HStack(spacing: Theme.Spacing.small) {
                Image(systemName: "play.fill")
                Text("WATCH ON YOUTUBE")
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.2)
            }
            .foregroundStyle(Theme.inkPrimary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, Theme.Spacing.card)
            .background(Theme.securityGold.opacity(0.15))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                    .stroke(Theme.securityGold.opacity(0.40), lineWidth: 0.5)
            )
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
        }
        .buttonStyle(EKPressStyle())
        .padding(.top, Theme.Spacing.small)
    }

    // MARK: Load

    private func load() async {
        state = .loading
        do {
            let resp = try await networkManager.fetchYouTubeSummary(videoId: video.videoId)
            state = .loaded(resp)
        } catch {
            state = .failed(error.localizedDescription)
        }
    }
}
