import SwiftUI

struct YouTubeCardView: View {
    let video: YouTubeVideoItem
    var onTickerTap: ((String) -> Void)? = nil

    private let goldAccent = Color(red: 0.78, green: 0.64, blue: 0.25)
    private let dimText    = Color.primary.opacity(0.45)

    var body: some View {
        Button(action: {
            if let url = URL(string: video.videoUrl) {
                UIApplication.shared.open(url)
            }
        }) {
            HStack(alignment: .top, spacing: 12) {
                // Thumbnail
                ZStack(alignment: .bottomTrailing) {
                    if let thumbUrl = video.thumbnailUrl, let url = URL(string: thumbUrl) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(width: 110, height: 70)
                                    .clipped()
                                    .cornerRadius(8)
                            default:
                                Rectangle()
                                    .fill(Color.primary.opacity(0.08))
                                    .frame(width: 110, height: 70)
                                    .cornerRadius(8)
                            }
                        }
                    } else {
                        Rectangle()
                            .fill(Color.primary.opacity(0.08))
                            .frame(width: 110, height: 70)
                            .cornerRadius(8)
                    }

                    // Play button overlay
                    Image(systemName: "play.circle.fill")
                        .font(.system(size: 22, weight: .regular))
                        .foregroundStyle(.white, Color.black.opacity(0.55))
                        .padding(4)

                    // Duration badge
                    if video.durationSeconds > 0 {
                        Text(video.formattedDuration)
                            .font(.system(size: 9, weight: .semibold, design: .monospaced))
                            .foregroundColor(.white)
                            .padding(.horizontal, 4)
                            .padding(.vertical, 2)
                            .background(Color.black.opacity(0.70))
                            .cornerRadius(3)
                            .padding(4)
                    }
                }

                // Metadata
                VStack(alignment: .leading, spacing: 5) {
                    // Channel name
                    Text(video.channelName.uppercased())
                        .font(.system(size: 9, weight: .bold, design: .monospaced))
                        .tracking(1.2)
                        .foregroundColor(goldAccent)

                    // Title
                    Text(video.title)
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundColor(.primary.opacity(0.88))
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                        .lineSpacing(2)

                    Spacer(minLength: 0)

                    // Footer: views + tickers
                    HStack(spacing: 6) {
                        Image(systemName: "eye")
                            .font(.system(size: 9))
                            .foregroundColor(dimText)
                        Text(video.formattedViewCount)
                            .font(.system(size: 10, weight: .medium, design: .monospaced))
                            .foregroundColor(dimText)

                        // Ticker chips (tappable)
                        ForEach(video.tickersMentioned.prefix(2), id: \.self) { ticker in
                            Button(action: { onTickerTap?(ticker) }) {
                                Text(ticker)
                                    .font(.system(size: 9, weight: .semibold, design: .monospaced))
                                    .foregroundColor(.primary.opacity(0.65))
                                    .padding(.horizontal, 5)
                                    .padding(.vertical, 2)
                                    .background(Color.primary.opacity(0.07))
                                    .cornerRadius(3)
                            }
                            .buttonStyle(EKPressStyle())
                        }
                    }
                }

                Spacer(minLength: 0)
            }
            .padding(12)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(.ultraThinMaterial)
                    .overlay(PaperTexture().opacity(0.45))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.primary.opacity(0.07), lineWidth: 0.5)
            )
            .cornerRadius(12)
        }
        .buttonStyle(EKPressStyle())
    }
}

// MARK: - Compact Card for Horizontal Scrolling (3 rows × 5 columns)

struct YouTubeCompactCard: View {
    let video: YouTubeVideoItem
    var onTickerTap: ((String) -> Void)? = nil

    private let goldAccent = Color(red: 0.78, green: 0.64, blue: 0.25)

    var body: some View {
        Button(action: {
            if let url = URL(string: video.videoUrl) {
                UIApplication.shared.open(url)
            }
        }) {
            VStack(alignment: .leading, spacing: 6) {
                // Thumbnail
                ZStack(alignment: .bottomTrailing) {
                    if let thumbUrl = video.thumbnailUrl, let url = URL(string: thumbUrl) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(width: 155, height: 87)
                                    .clipped()
                                    .cornerRadius(6)
                            default:
                                Rectangle()
                                    .fill(Color.primary.opacity(0.08))
                                    .frame(width: 155, height: 87)
                                    .cornerRadius(6)
                            }
                        }
                    } else {
                        Rectangle()
                            .fill(Color.primary.opacity(0.08))
                            .frame(width: 155, height: 87)
                            .cornerRadius(6)
                    }

                    // Play button
                    Image(systemName: "play.circle.fill")
                        .font(.system(size: 18, weight: .regular))
                        .foregroundStyle(.white, Color.black.opacity(0.55))
                        .padding(3)

                    // Duration badge
                    if video.durationSeconds > 0 {
                        Text(video.formattedDuration)
                            .font(.system(size: 8, weight: .semibold, design: .monospaced))
                            .foregroundColor(.white)
                            .padding(.horizontal, 3)
                            .padding(.vertical, 1.5)
                            .background(Color.black.opacity(0.70))
                            .cornerRadius(2)
                            .padding(3)
                    }
                }

                // Channel
                Text(video.channelName.uppercased())
                    .font(.system(size: 8, weight: .bold, design: .monospaced))
                    .tracking(0.8)
                    .foregroundColor(goldAccent)
                    .lineLimit(1)

                // Title
                Text(video.title)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(.primary.opacity(0.88))
                    .lineLimit(2)
                    .lineSpacing(1)

                // Views
                HStack(spacing: 3) {
                    Image(systemName: "eye")
                        .font(.system(size: 8))
                        .foregroundColor(Color.primary.opacity(0.35))
                    Text(video.formattedViewCount)
                        .font(.system(size: 9, weight: .medium, design: .monospaced))
                        .foregroundColor(Color.primary.opacity(0.35))
                }

                // Ticker chips
                if !video.tickersMentioned.isEmpty {
                    HStack(spacing: 3) {
                        ForEach(video.tickersMentioned.prefix(2), id: \.self) { ticker in
                            Button(action: { onTickerTap?(ticker) }) {
                                Text(ticker)
                                    .font(.system(size: 8, weight: .semibold, design: .monospaced))
                                    .foregroundColor(.primary.opacity(0.65))
                                    .padding(.horizontal, 4)
                                    .padding(.vertical, 1.5)
                                    .background(Color.primary.opacity(0.07))
                                    .cornerRadius(2)
                            }
                            .buttonStyle(EKPressStyle())
                        }
                    }
                }
            }
            .frame(width: 155, alignment: .leading)
            .padding(8)
            .background(
                RoundedRectangle(cornerRadius: 10)
                    .fill(.ultraThinMaterial)
                    .overlay(PaperTexture().opacity(0.45))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(Color.primary.opacity(0.07), lineWidth: 0.5)
            )
            .cornerRadius(10)
        }
        .buttonStyle(EKPressStyle())
    }
}
