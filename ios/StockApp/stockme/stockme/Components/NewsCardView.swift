import SwiftUI

struct NewsCardView: View {
    let article: NewsArticleItem
    var onTickerTap: ((String) -> Void)? = nil

    private var goldAccent: Color { Theme.securityGold }
    private let bearRed    = Theme.bearRed
    private let bullGreen  = Theme.bullGreen
    private let dimText    = Theme.inkSecondary

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
        Button(action: { HapticManager.selection();  HapticManager.selection()
            if let url = URL(string: article.articleUrl) {
                UIApplication.shared.open(url)
            }
        }) {
            VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                    // Hero image (if available)
                    if let imageUrl = article.imageUrl, let url = URL(string: imageUrl) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(maxWidth: .infinity)
                                    .frame(height: UIScreen.main.bounds.width * 0.43)
                                    .clipped()
                            case .failure(_):
                                EmptyView()
                            case .empty:
                                Rectangle()
                                    .fill(Color.primary.opacity(0.04))
                                    .frame(height: UIScreen.main.bounds.width * 0.26)
                            @unknown default:
                                EmptyView()
                            }
                        }
                    }

                VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                    // Header row
                    HStack(spacing: Theme.Spacing.medium) {
                        // Source pill
                        Text(sourceLabel.uppercased())
                            .font(.caption2.weight(.bold).monospaced())
                            .tracking(1.2)
                            .foregroundStyle(goldAccent)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, Theme.Spacing.small)
                            .background(goldAccent.opacity(0.10))
                            .cornerRadius(Theme.CornerRadius.small)
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                    .stroke(goldAccent.opacity(0.25), lineWidth: 0.5)
                            )

                        // Red flag indicator
                        if article.isRedFlag {
                            HStack(spacing: Theme.Spacing.xSmall) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .font(.caption2.weight(.bold))
                                Text("RED FLAG")
                                    .font(.caption2.weight(.bold).monospaced())
                                    .tracking(1.0)
                            }
                            .foregroundStyle(bearRed)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, Theme.Spacing.small)
                            .background(bearRed.opacity(0.10))
                            .cornerRadius(Theme.CornerRadius.small)
                        }

                        Spacer()

                        // Ticker chip (tappable)
                        if let ticker = article.ticker {
                            Button(action: { HapticManager.selection(); onTickerTap?(ticker) }) {
                                Text(ticker)
                                    .font(.caption2.weight(.semibold).monospaced())
                                    .foregroundStyle(.primary.opacity(0.75))
                                    .padding(.horizontal, Theme.Spacing.tight)
                                    .padding(.vertical, Theme.Spacing.small)
                                    .background(Color.primary.opacity(0.07))
                                    .cornerRadius(Theme.CornerRadius.small)
                            }
                            .buttonStyle(EKPressStyle())
                        }
                    }

                    // Headline
                    Text(article.headline)
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(.primary)
                        .lineLimit(3)
                        .fixedSize(horizontal: false, vertical: true)
                        .lineSpacing(2)

                    // Summary
                    if let summary = article.summary, !summary.isEmpty {
                        Text(summary)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(2)
                            .lineSpacing(2)
                    }

                    // Footer
                    HStack {
                        Text(relativeTime(article.publishedAt))
                            .font(.caption)
                            .foregroundStyle(dimText)

                        Spacer()

                        // Sentiment dot
                        if let sentiment = article.sentiment, sentiment != "NEUTRAL" {
                            Circle()
                                .fill(sentimentColor)
                                .frame(width: 5, height: 5)
                            Text(sentiment.capitalized)
                                .font(.caption2.weight(.medium))
                                .foregroundStyle(sentimentColor)
                        }
                    }
                }
                .padding(Theme.Spacing.standard)
            }
            .background(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .fill(.ultraThinMaterial)
                    .overlay(PaperTexture().opacity(0.5))
                    .overlay(
                        // Left red stripe for red flag articles
                        article.isRedFlag
                            ? HStack {
                                Rectangle()
                                    .fill(bearRed)
                                    .frame(width: 3)
                                    .cornerRadius(Theme.CornerRadius.large)
                                Spacer()
                              }
                            : nil
                    )
            )
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .stroke(
                        article.isRedFlag ? bearRed.opacity(0.3) : Color.primary.opacity(0.07),
                        lineWidth: article.isRedFlag ? 1.0 : 0.5
                    )
            )
            .cornerRadius(Theme.CornerRadius.large)
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
