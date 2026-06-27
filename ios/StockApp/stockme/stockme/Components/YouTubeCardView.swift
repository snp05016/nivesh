import SwiftUI

struct YouTubeCardView: View {
    let video: YouTubeVideoItem
    var onTickerTap: ((String) -> Void)? = nil

    @State private var showSummary = false
    private var goldAccent: Color { Theme.securityGold }
    private let dimText    = Theme.inkSecondary

    var body: some View {
        Button(action: { HapticManager.selection()
            if let url = URL(string: video.videoUrl) {
                UIApplication.shared.open(url)
            }
        }) {
            let thumbW = UIScreen.main.bounds.width * 0.38
            let thumbH = thumbW * 9.0 / 16.0
            HStack(alignment: .top, spacing: Theme.Spacing.standard) {
                // Thumbnail
                ZStack(alignment: .bottomTrailing) {
                    if let thumbUrl = video.thumbnailUrl, let url = URL(string: thumbUrl) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(width: thumbW, height: thumbH)
                                    .clipped()
                            default:
                                Rectangle()
                                    .fill(Color.primary.opacity(0.08))
                                    .frame(width: thumbW, height: thumbH)
                            }
                        }
                    } else {
                        Rectangle()
                            .fill(Color.primary.opacity(0.08))
                            .frame(width: thumbW, height: thumbH)
                    }

                    // Play button overlay
                    Image(systemName: "play.circle.fill")
                        .font(.title2.weight(.regular))
                        .foregroundStyle(.white, Theme.inkPrimary.opacity(0.55))
                        .padding(Theme.Spacing.small)

                    // Duration badge
                    if (video.durationSeconds ?? 0) > 0 {
                        Text(video.formattedDuration)
                            .font(.caption2.weight(.semibold).monospaced())
                            .foregroundStyle(.white)
                            .padding(.horizontal, Theme.Spacing.small)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.inkPrimary.opacity(0.70))
                            .cornerRadius(Theme.CornerRadius.small)
                            .padding(Theme.Spacing.small)
                    }
                }
                .frame(width: thumbW, height: thumbH)
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))

                // Metadata
                VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                    // Channel name
                    Text(video.channelName.uppercased())
                        .font(.caption2.weight(.bold).monospaced())
                        .tracking(1.2)
                        .foregroundStyle(goldAccent)

                    // Title
                    Text(video.title)
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(.primary.opacity(0.88))
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                        .lineSpacing(2)

                    // Description snippet
                    if let desc = video.description, !desc.isEmpty {
                        Text(desc)
                            .font(Theme.engravedSerif(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkSecondary)
                            .lineLimit(2)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    Spacer(minLength: 0)

                    // Footer: views + tickers + summary
                    HStack(spacing: Theme.Spacing.tight) {
                        Image(systemName: "eye")
                            .font(.caption2)
                            .foregroundStyle(dimText)
                        Text(video.formattedViewCount)
                            .font(.caption2.weight(.medium).monospaced())
                            .foregroundStyle(dimText)

                        // Ticker chips (tappable)
                        ForEach(video.tickersMentioned.prefix(2), id: \.self) { ticker in
                            Button(action: { HapticManager.selection(); onTickerTap?(ticker) }) {
                                Text(ticker)
                                    .font(.caption2.weight(.semibold).monospaced())
                                    .foregroundStyle(.primary.opacity(0.65))
                                    .padding(.horizontal, Theme.Spacing.tight)
                                    .padding(.vertical, Theme.Spacing.xSmall)
                                    .background(Color.primary.opacity(0.07))
                                    .cornerRadius(Theme.CornerRadius.small)
                            }
                            .buttonStyle(EKPressStyle())
                        }

                        Spacer(minLength: 0)

                        // AI Summary button
                        Button(action: { HapticManager.selection(); showSummary = true }) {
                            HStack(spacing: Theme.Spacing.xSmall) {
                                Image(systemName: "text.magnifyingglass")
                                    .font(.caption2)
                                Text("Summary")
                                    .font(.caption2.weight(.semibold))
                            }
                            .foregroundStyle(Theme.securityGold)
                            .padding(.horizontal, Theme.Spacing.small)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.securityGold.opacity(0.12))
                            .clipShape(Capsule())
                        }
                        .buttonStyle(EKPressStyle())
                    }
                }

                Spacer(minLength: 0)
            }
            .padding(Theme.Spacing.standard)
            .background(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .fill(.ultraThinMaterial)
                    .overlay(PaperTexture().opacity(0.45))
            )
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .stroke(Color.primary.opacity(0.07), lineWidth: 0.5)
            )
            .cornerRadius(Theme.CornerRadius.large)
        }
        .buttonStyle(EKPressStyle())
        .sheet(isPresented: $showSummary) {
            YouTubeSummarySheet(video: video, onTickerTap: onTickerTap)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
    }
}

// MARK: - Compact Card for Horizontal Scrolling (3 rows × 5 columns)

struct YouTubeCompactCard: View {
    let video: YouTubeVideoItem
    var onTickerTap: ((String) -> Void)? = nil

    @State private var showSummary = false

    var body: some View {
        Button(action: { HapticManager.selection()
            if let url = URL(string: video.videoUrl) {
                UIApplication.shared.open(url)
            }
        }) {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                // Thumbnail
                ZStack(alignment: .bottomTrailing) {
                    if let thumbUrl = video.thumbnailUrl, let url = URL(string: thumbUrl) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(16/9, contentMode: .fill)
                                    .frame(maxWidth: .infinity)
                                    .clipped()
                                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                            default:
                                thumbnailPlaceholder
                            }
                        }
                    } else {
                        thumbnailPlaceholder
                    }

                    // Play button
                    Image(systemName: "play.circle.fill")
                        .font(.title3.weight(.regular))
                        .foregroundStyle(.white, Theme.inkPrimary.opacity(0.55))
                        .padding(Theme.Spacing.small)

                    // Duration badge
                    if (video.durationSeconds ?? 0) > 0 {
                        Text(video.formattedDuration)
                            .font(.caption2.weight(.semibold).monospaced())
                            .foregroundStyle(.white)
                            .padding(.horizontal, Theme.Spacing.small)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.inkPrimary.opacity(0.70))
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
                            .padding(Theme.Spacing.small)
                    }
                }

                // Channel
                Text(video.channelName.uppercased())
                    .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                    .tracking(0.8)
                    .foregroundStyle(Theme.securityGold)
                    .lineLimit(1)

                // Title (fallback for empty)
                Text(video.title.isEmpty ? video.channelName : video.title)
                    .font(Theme.engravedSerif(size: 11, weight: .semibold, relativeTo: .caption))
                    .foregroundStyle(Theme.inkPrimary)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)

                // Description snippet
                if let desc = video.description, !desc.isEmpty {
                    Text(desc)
                        .font(Theme.engravedSerif(size: 9, weight: .regular, relativeTo: .caption2))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineLimit(2)
                }

                // Views + Ticker chips + Summary
                HStack(spacing: Theme.Spacing.xSmall) {
                    Image(systemName: "eye")
                        .font(.caption2)
                        .foregroundStyle(Theme.inkTertiary)
                    Text(video.formattedViewCount)
                        .font(.caption2.weight(.medium).monospaced())
                        .foregroundStyle(Theme.inkTertiary)

                    ForEach(video.tickersMentioned.prefix(2), id: \.self) { ticker in
                        Button(action: { HapticManager.selection(); onTickerTap?(ticker) }) {
                            Text(ticker)
                                .font(.caption2.weight(.semibold).monospaced())
                                .foregroundStyle(Theme.inkPrimary.opacity(0.65))
                                .padding(.horizontal, Theme.Spacing.small)
                                .padding(.vertical, Theme.Spacing.xSmall)
                                .background(Theme.inkPrimary.opacity(0.07))
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
                        }
                        .buttonStyle(EKPressStyle())
                    }
                    Spacer(minLength: 0)
                    Button(action: { HapticManager.selection(); showSummary = true }) {
                        Image(systemName: "text.magnifyingglass")
                            .font(.caption2.weight(.semibold))
                            .foregroundStyle(Theme.securityGold)
                            .padding(Theme.Spacing.small)
                            .background(Theme.securityGold.opacity(0.12))
                            .clipShape(Circle())
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
            .padding(Theme.Spacing.standard)
            .background(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .fill(Theme.canvasDeep)
            )
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .sheet(isPresented: $showSummary) {
            YouTubeSummarySheet(video: video, onTickerTap: onTickerTap)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
    }

    private var thumbnailPlaceholder: some View {
        Rectangle()
            .fill(Theme.canvasShadow)
            .aspectRatio(16/9, contentMode: .fill)
            .frame(maxWidth: .infinity)
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
    }
}
