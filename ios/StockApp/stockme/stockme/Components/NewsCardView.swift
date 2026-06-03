import SwiftUI

struct NewsCardView: View {
    let article: NewsArticleItem
    var onTickerTap: ((String) -> Void)? = nil

    private let goldAccent = Color(red: 0.78, green: 0.64, blue: 0.25)
    private let bearRed    = Color(red: 0.72, green: 0.09, blue: 0.09)
    private let bullGreen  = Color(red: 0.10, green: 0.53, blue: 0.24)
    private let dimText    = Color.primary.opacity(0.45)

    var sentimentColor: Color {
        switch article.sentiment {
        case "POSITIVE": return bullGreen
        case "NEGATIVE": return bearRed
        default:         return dimText
        }
    }

    var sourceLabel: String {
        switch article.source {
        case "moneycontrol": return "Moneycontrol"
        case "economic_times": return "Economic Times"
        case "nse": return "NSE"
        default: return article.source.capitalized
        }
    }

    var body: some View {
        Button(action: {
            if let url = URL(string: article.articleUrl) {
                UIApplication.shared.open(url)
            }
        }) {
            VStack(alignment: .leading, spacing: 0) {
                // Hero image (if available)
                if let imageUrl = article.imageUrl, let url = URL(string: imageUrl) {
                    AsyncImage(url: url) { phase in
                        switch phase {
                        case .success(let image):
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                                .frame(maxWidth: .infinity)
                                .frame(height: 160)
                                .clipped()
                        case .failure(_):
                            EmptyView()
                        case .empty:
                            Rectangle()
                                .fill(Color.primary.opacity(0.04))
                                .frame(height: 100)
                        @unknown default:
                            EmptyView()
                        }
                    }
                }

                VStack(alignment: .leading, spacing: 8) {
                    // Header row
                    HStack(spacing: 8) {
                        // Source pill
                        Text(sourceLabel.uppercased())
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                            .tracking(1.2)
                            .foregroundColor(goldAccent)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 3)
                            .background(goldAccent.opacity(0.10))
                            .cornerRadius(4)
                            .overlay(
                                RoundedRectangle(cornerRadius: 4)
                                    .stroke(goldAccent.opacity(0.25), lineWidth: 0.5)
                            )

                        // Red flag indicator
                        if article.isRedFlag {
                            HStack(spacing: 3) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .font(.system(size: 9, weight: .bold))
                                Text("RED FLAG")
                                    .font(.system(size: 9, weight: .bold, design: .monospaced))
                                    .tracking(1.0)
                            }
                            .foregroundColor(bearRed)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 3)
                            .background(bearRed.opacity(0.10))
                            .cornerRadius(4)
                        }

                        Spacer()

                        // Ticker chip (tappable)
                        if let ticker = article.ticker {
                            Button(action: { onTickerTap?(ticker) }) {
                                Text(ticker)
                                    .font(.system(size: 10, weight: .semibold, design: .monospaced))
                                    .foregroundColor(.primary.opacity(0.75))
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 3)
                                    .background(Color.primary.opacity(0.07))
                                    .cornerRadius(4)
                            }
                            .buttonStyle(EKPressStyle())
                        }
                    }

                    // Headline
                    Text(article.headline)
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(.primary.opacity(0.90))
                        .lineLimit(3)
                        .fixedSize(horizontal: false, vertical: true)
                        .lineSpacing(2)

                    // Summary
                    if let summary = article.summary, !summary.isEmpty {
                        Text(summary)
                            .font(.system(size: 12, weight: .regular))
                            .foregroundColor(.primary.opacity(0.55))
                            .lineLimit(2)
                            .lineSpacing(2)
                    }

                    // Footer
                    HStack {
                        Text(relativeTime(article.publishedAt))
                            .font(.system(size: 11))
                            .foregroundColor(dimText)

                        Spacer()

                        // Sentiment dot
                        if let sentiment = article.sentiment, sentiment != "NEUTRAL" {
                            Circle()
                                .fill(sentimentColor)
                                .frame(width: 5, height: 5)
                            Text(sentiment.capitalized)
                                .font(.system(size: 10, weight: .medium))
                                .foregroundColor(sentimentColor)
                        }
                    }
                }
                .padding(12)
            }
            .background(
                RoundedRectangle(cornerRadius: 14)
                    .fill(.ultraThinMaterial)
                    .overlay(PaperTexture().opacity(0.5))
                    .overlay(
                        // Left red stripe for red flag articles
                        article.isRedFlag
                            ? HStack {
                                Rectangle()
                                    .fill(bearRed)
                                    .frame(width: 3)
                                    .cornerRadius(14)
                                Spacer()
                              }
                            : nil
                    )
            )
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(
                        article.isRedFlag ? bearRed.opacity(0.3) : Color.primary.opacity(0.07),
                        lineWidth: article.isRedFlag ? 1.0 : 0.5
                    )
            )
            .cornerRadius(14)
        }
        .buttonStyle(EKPressStyle())
    }

    func relativeTime(_ isoString: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let date = formatter.date(from: isoString) else { return "" }
        let interval = Date().timeIntervalSince(date)
        if interval < 3600 { return "\(Int(interval/60))m ago" }
        if interval < 86400 { return "\(Int(interval/3600))h ago" }
        return "\(Int(interval/86400))d ago"
    }
}
