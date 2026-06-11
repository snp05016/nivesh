import SwiftUI

struct YouTubeCardView: View {
    let video: YouTubeVideoItem
    var onTickerTap: ((String) -> Void)? = nil

    private let goldAccent = Theme.securityGold
    private let dimText    = Color.secondary

    var body: some View {
        Button(action: {
            if let url = URL(string: video.videoUrl) {
                UIApplication.shared.open(url)
            }
        }) {
            HStack(alignment: .top, spacing: Theme.Spacing.standard) {
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
                                    .cornerRadius(Theme.CornerRadius.medium)
                            default:
                                Rectangle()
                                    .fill(Color.primary.opacity(0.08))
                                    .aspectRatio(16/9, contentMode: .fill)
                                    .frame(maxWidth: .infinity)
                                    .cornerRadius(Theme.CornerRadius.medium)
                            }
                        }
                    } else {
                        Rectangle()
                            .fill(Color.primary.opacity(0.08))
                            .aspectRatio(16/9, contentMode: .fill)
                            .frame(maxWidth: .infinity)
                            .cornerRadius(Theme.CornerRadius.medium)
                    }

                    // Play button overlay
                    Image(systemName: "play.circle.fill")
                        .font(.title2.weight(.regular))
                        .foregroundStyle(.white, Color.black.opacity(0.55))
                        .padding(Theme.Spacing.small)

                    // Duration badge
                    if (video.durationSeconds ?? 0) > 0 {
                        Text(video.formattedDuration)
                            .font(.caption2.weight(.semibold).monospaced())
                            .foregroundStyle(.white)
                            .padding(.horizontal, Theme.Spacing.small)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(Color.black.opacity(0.70))
                            .cornerRadius(Theme.CornerRadius.small)
                            .padding(Theme.Spacing.small)
                    }
                }

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

                    Spacer(minLength: 0)

                    // Footer: views + tickers
                    HStack(spacing: Theme.Spacing.tight) {
                        Image(systemName: "eye")
                            .font(.caption2)
                            .foregroundStyle(dimText)
                        Text(video.formattedViewCount)
                            .font(.caption2.weight(.medium).monospaced())
                            .foregroundStyle(dimText)

                        // Ticker chips (tappable)
                        ForEach(video.tickersMentioned.prefix(2), id: \.self) { ticker in
                            Button(action: { onTickerTap?(ticker) }) {
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
    }
}

// MARK: - Compact Card for Horizontal Scrolling (3 rows × 5 columns)

struct YouTubeCompactCard: View {
    let video: YouTubeVideoItem
    var onTickerTap: ((String) -> Void)? = nil

    private let goldAccent = Theme.securityGold

    var body: some View {
        Button(action: {
            if let url = URL(string: video.videoUrl) {
                UIApplication.shared.open(url)
            }
        }) {
            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
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
                                    .cornerRadius(Theme.CornerRadius.tight)
                            default:
                                Rectangle()
                                    .fill(Color.primary.opacity(0.08))
                                    .aspectRatio(16/9, contentMode: .fill)
                                    .frame(maxWidth: .infinity)
                                    .cornerRadius(Theme.CornerRadius.tight)
                            }
                        }
                    } else {
                        Rectangle()
                            .fill(Color.primary.opacity(0.08))
                            .aspectRatio(16/9, contentMode: .fill)
                            .frame(maxWidth: .infinity)
                            .cornerRadius(Theme.CornerRadius.tight)
                    }

                    // Play button
                    Image(systemName: "play.circle.fill")
                        .font(.title3.weight(.regular))
                        .foregroundStyle(.white, Color.black.opacity(0.55))
                        .padding(Theme.Spacing.small)

                    // Duration badge
                    if (video.durationSeconds ?? 0) > 0 {
                        Text(video.formattedDuration)
                            .font(.caption2.weight(.semibold).monospaced())
                            .foregroundStyle(.white)
                            .padding(.horizontal, Theme.Spacing.small)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(Color.black.opacity(0.70))
                            .cornerRadius(Theme.CornerRadius.small)
                            .padding(Theme.Spacing.small)
                    }
                }

                // Channel
                Text(video.channelName.uppercased())
                    .font(.caption2.weight(.bold).monospaced())
                    .tracking(0.8)
                    .foregroundStyle(goldAccent)
                    .lineLimit(1)

                // Title
                Text(video.title)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.primary.opacity(0.88))
                    .lineLimit(2)
                    .lineSpacing(1)

                // Views
                HStack(spacing: Theme.Spacing.xSmall) {
                    Image(systemName: "eye")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text(video.formattedViewCount)
                        .font(.caption2.weight(.medium).monospaced())
                        .foregroundStyle(.secondary)
                }

                // Ticker chips
                if !video.tickersMentioned.isEmpty {
                    HStack(spacing: Theme.Spacing.xSmall) {
                        ForEach(video.tickersMentioned.prefix(2), id: \.self) { ticker in
                            Button(action: { onTickerTap?(ticker) }) {
                                Text(ticker)
                                    .font(.caption2.weight(.semibold).monospaced())
                                    .foregroundStyle(.primary.opacity(0.65))
                                    .padding(.horizontal, Theme.Spacing.small)
                                    .padding(.vertical, Theme.Spacing.xSmall)
                                    .background(Color.primary.opacity(0.07))
                                    .cornerRadius(Theme.CornerRadius.small)
                            }
                            .buttonStyle(EKPressStyle())
                        }
                    }
                }
            }
            .padding(Theme.Spacing.medium)
            .background(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .fill(.ultraThinMaterial)
                    .overlay(PaperTexture().opacity(0.45))
            )
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .stroke(Color.primary.opacity(0.07), lineWidth: 0.5)
            )
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
        }
        .buttonStyle(EKPressStyle())
    }
}
