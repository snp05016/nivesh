import SwiftUI

// MARK: - Compact Card for Horizontal Scrolling (3 rows × 5 columns)

struct YouTubeCompactCard: View {
    let video: YouTubeVideoItem
    var onTickerTap: ((String) -> Void)? = nil

    @State private var showSummary = false

    var body: some View {
        Button(action: { HapticManager.selection()
            SafeURL.open(video.videoUrl)
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
                    .accessibilityLabel("Show video summary")
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
