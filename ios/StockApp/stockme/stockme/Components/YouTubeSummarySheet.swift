import SwiftUI

// MARK: - YouTube AI Summary Sheet

struct YouTubeSummarySheet: View {
    let video: YouTubeVideoItem
    var onTickerTap: ((String) -> Void)? = nil

    @State private var state: LoadState = .idle
    @Environment(\.dismiss) private var dismiss

    private enum LoadState {
        case idle, loading, loaded(YouTubeVideoSummaryResponse), failed(String)
    }

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()

            ScrollView {
                LazyVStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                    YTSSheetHeader(video: video, dismiss: _dismiss)
                    switch state {
                    case .idle, .loading:
                        YTSLoadingView()
                    case .loaded(let summary):
                        YTSSummaryBody(summary: summary, video: video, onTickerTap: onTickerTap, dismiss: _dismiss)
                    case .failed(let msg):
                        YTSErrorView(message: msg, video: video)
                    }
                }
                .padding(.bottom, Theme.Spacing.xLarge)
            }
        }
        .task { await load() }
    }

    private func load() async {
        state = .loading
        do {
            let resp = try await NetworkManager.shared.fetchYouTubeSummary(videoId: video.videoId)
            state = .loaded(resp)
        } catch {
            state = .failed(error.localizedDescription)
        }
    }
}


// MARK: - Sheet Header (extracted per AGENTS.md §6.6)

struct YTSSheetHeader: View {
    let video: YouTubeVideoItem
    @Environment(\.dismiss) var dismiss

    var body: some View {
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
}


// MARK: - Loading View (extracted per AGENTS.md §6.6)

struct YTSLoadingView: View {
    var body: some View {
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
}


// MARK: - Error View (extracted per AGENTS.md §6.6)

struct YTSErrorView: View {
    let message: String
    let video: YouTubeVideoItem

    var body: some View {
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
}


// MARK: - Summary Body (extracted per AGENTS.md §6.6)

struct YTSSummaryBody: View {
    let summary: YouTubeVideoSummaryResponse
    let video: YouTubeVideoItem
    var onTickerTap: ((String) -> Void)? = nil
    @Environment(\.dismiss) var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.large) {
            YTSSentimentBadge(sentiment: summary.summary.sentiment, provider: summary.source.summaryProvider)
            YTSTldrCard(text: summary.summary.tldr)
            if !summary.summary.tickersMentioned.isEmpty {
                YTSTickerRow(tickers: summary.summary.tickersMentioned, onTickerTap: onTickerTap, dismiss: _dismiss)
            }
            if !summary.summary.keyPoints.isEmpty {
                YTSBulletSection(title: "KEY POINTS", icon: "list.bullet", items: summary.summary.keyPoints, color: Theme.securityGold)
            }
            if !summary.summary.financeInsights.isEmpty {
                YTSBulletSection(title: "FINANCE INSIGHTS", icon: "chart.line.uptrend.xyaxis", items: summary.summary.financeInsights, color: Theme.bullGreen)
            }
            if !summary.summary.risksOrRedFlags.isEmpty {
                YTSBulletSection(title: "RISKS & RED FLAGS", icon: "exclamationmark.triangle", items: summary.summary.risksOrRedFlags, color: Theme.bearRed)
            }
            if !summary.summary.actionItems.isEmpty {
                YTSBulletSection(title: "ACTION ITEMS", icon: "checkmark.circle", items: summary.summary.actionItems, color: Theme.holdAmber)
            }
            if !summary.timestamps.isEmpty {
                YTSTimestampSection(stamps: summary.timestamps)
            }
            YTSWatchButton(video: video)
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}


// MARK: - Sentiment Badge (extracted per AGENTS.md §6.6)

struct YTSSentimentBadge: View {
    let sentiment: String
    let provider: String

    var body: some View {
        let (label, color) = YTSSentimentBadge.sentimentStyle(sentiment)
        HStack(spacing: Theme.Spacing.medium) {
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

    static func sentimentStyle(_ s: String) -> (String, Color) {
        switch s.lowercased() {
        case "bullish":  return ("BULLISH", Theme.bullGreen)
        case "bearish":  return ("BEARISH", Theme.bearRed)
        case "mixed":    return ("MIXED", Theme.holdAmber)
        default:         return ("NEUTRAL", Theme.inkSecondary)
        }
    }
}


// MARK: - TLDR Card (extracted per AGENTS.md §6.6)

struct YTSTldrCard: View {
    let text: String

    var body: some View {
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
}


// MARK: - Ticker Row (extracted per AGENTS.md §6.6)

struct YTSTickerRow: View {
    let tickers: [String]
    var onTickerTap: ((String) -> Void)? = nil
    @Environment(\.dismiss) var dismiss

    var body: some View {
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
}


// MARK: - Bullet Section (extracted per AGENTS.md §6.6)

struct YTSBulletSection: View {
    let title: String
    let icon: String
    let items: [String]
    let color: Color

    var body: some View {
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
}


// MARK: - Timestamp Section (extracted per AGENTS.md §6.6)

struct YTSTimestampSection: View {
    let stamps: [YouTubeSummaryTimestamp]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text("CHAPTERS")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
            VStack(spacing: 0) {
                ForEach(stamps) { stamp in
                    HStack(alignment: .top, spacing: Theme.Spacing.card) {
                        Text(YTSTimestampSection.formatSeconds(stamp.startSeconds))
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

    static func formatSeconds(_ s: Int) -> String {
        let m = s / 60; let sec = s % 60
        return String(format: "%d:%02d", m, sec)
    }
}


// MARK: - Watch Button (extracted per AGENTS.md §6.6)

struct YTSWatchButton: View {
    let video: YouTubeVideoItem

    var body: some View {
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
}
