import SafariServices
import SwiftUI

// MARK: - Compact News Cell — rich card with expand-to-detail

struct CompactNewsCell: View {
    let article: NewsArticleItem
    var onTickerTap: ((String) -> Void)? = nil
    @State private var showDetail = false

    private var sourceLabel: String {
        switch article.source {
        case "moneycontrol": return "MC"
        case "economic_times": return "ET"
        case "nse": return "NSE"
        case "business_standard": return "BS"
        case "livemint": return "MINT"
        case "reuters": return "RTR"
        default: return String(article.source.prefix(4)).uppercased()
        }
    }

    private var timeLabel: String {
        if let date = article.parsedDate {
            return IndianFormatter.elapsed(from: date)
        }
        return ""
    }

    private var sentimentColor: Color {
        guard let s = article.sentiment?.lowercased() else { return Theme.holdAmber }
        if s.contains("positive") || s.contains("bullish") { return Theme.bullGreen }
        if s.contains("negative") || s.contains("bearish") { return Theme.bearRed }
        return Theme.holdAmber
    }

    /// Freshness: ≤ 2h = HOT, ≤ 6h = TRENDING, red flag = RED FLAG
    private var signalBadge: (label: String, icon: String, color: Color)? {
        if article.isRedFlag { return ("RED FLAG", "exclamationmark.triangle.fill", Theme.bearRed) }
        if let date = article.parsedDate {
            let age = Date().timeIntervalSince(date)
            if age < 2 * 3600 { return ("HOT", "flame.fill", Theme.holdAmber) }
            if age < 6 * 3600 { return ("TRENDING", "chart.line.uptrend.xyaxis", Theme.securityGold) }
            if age < 12 * 3600 { return ("BREAKING", "dot.radiowaves.left.and.right", Theme.bullGreen) }
        }
        return nil
    }

    var body: some View {
        Button(action: { HapticManager.selection()
            showDetail = true
        }) {
            VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                // ── Image / Hero ─────────────────────────────────────────
                ZStack(alignment: .bottom) {
                    if let imageUrl = article.imageUrl, let url = URL(string: imageUrl) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(maxWidth: .infinity)
                                    .frame(height: UIScreen.main.bounds.height * 0.13)
                                    .clipped()
                            case .failure(_), .empty:
                                newsFallbackImage
                            @unknown default:
                                EmptyView()
                            }
                        }
                    } else {
                        newsFallbackImage
                    }

                    // Gradient scrim at bottom
                    LinearGradient(
                        colors: [Theme.inkPrimary.opacity(0.0), Theme.inkPrimary.opacity(0.6)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                    .frame(height: 56)

                    // Bottom overlay row: source + time
                    HStack(spacing: Theme.Spacing.tight) {
                        Text(sourceLabel)
                            .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                            .tracking(1.0)
                            .foregroundStyle(Theme.securityGold)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.inkPrimary.opacity(0.55))
                            .cornerRadius(Theme.CornerRadius.small)

                        if !timeLabel.isEmpty {
                            Text(timeLabel)
                                .font(.caption2.monospaced())
                                .foregroundStyle(.white.opacity(0.9))
                                .padding(.horizontal, Theme.Spacing.tight)
                                .padding(.vertical, Theme.Spacing.xSmall)
                                .background(Theme.inkPrimary.opacity(0.45))
                                .cornerRadius(Theme.CornerRadius.small)
                        }

                        Spacer()

                        // Signal badge (HOT / TRENDING / BREAKING / RED FLAG)
                        if let badge = signalBadge {
                            HStack(spacing: Theme.Spacing.xSmall) {
                                Image(systemName: badge.icon)
                                    .font(Theme.officialStampFont(size: 8))
                                Text(badge.label)
                                    .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                                    .tracking(0.8)
                            }
                            .foregroundStyle(badge.color)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(badge.color.opacity(0.18))
                            .cornerRadius(Theme.CornerRadius.small)
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.medium)
                    .padding(.bottom, Theme.Spacing.medium)
                }
                .frame(height: UIScreen.main.bounds.height * 0.13)
                .clipped()
                .cornerRadius(Theme.CornerRadius.tight)

                // ── Body ─────────────────────────────────────────────────
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    // Signal row: sentiment + ticker chip
                    HStack(spacing: Theme.Spacing.tight) {
                        if let sentiment = article.sentiment, !sentiment.isEmpty {
                            HStack(spacing: Theme.Spacing.xSmall) {
                                Circle()
                                    .fill(sentimentColor)
                                    .frame(width: 6, height: 6)
                                Text(sentiment.uppercased())
                                    .font(.caption2.weight(.bold).monospaced())
                                    .tracking(0.6)
                                    .foregroundStyle(sentimentColor)
                            }
                            .padding(.horizontal, Theme.Spacing.small)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(sentimentColor.opacity(0.10))
                            .cornerRadius(Theme.CornerRadius.small)
                        }

                        if let ticker = article.ticker, !ticker.isEmpty {
                            HStack(spacing: Theme.Spacing.xSmall) {
                                Image(systemName: "chart.line.uptrend.xyaxis")
                                    .font(Theme.officialStampFont(size: 7))
                                Text(ticker)
                                    .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                            }
                            .foregroundStyle(Theme.bullGreen)
                            .padding(.horizontal, Theme.Spacing.small)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.bullGreen.opacity(0.10))
                            .cornerRadius(Theme.CornerRadius.small)
                        }

                        Spacer()
                    }

                    // Headline
                    Text(stripEmoji(article.headline))
                        .font(Theme.engravedSerif(size: 13, weight: .semibold, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkPrimary)
                        .lineLimit(3)
                        .lineSpacing(2.5)
                        .fixedSize(horizontal: false, vertical: true)

                    // Summary snippet
                    if let summary = article.summary, !summary.isEmpty {
                        Text(stripEmoji(summary))
                            .font(.caption)
                            .foregroundStyle(Theme.inkSecondary)
                            .lineLimit(2)
                            .lineSpacing(2)
                    }

                    Spacer(minLength: 0)

                    // Footer: Read more + red-flag indicator
                    HStack(spacing: Theme.Spacing.tight) {
                        if article.isRedFlag {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.caption2)
                                .foregroundStyle(Theme.bearRed)
                            Text("RED FLAG")
                                .font(Theme.officialStampFont(size: 7, relativeTo: .caption2))
                                .tracking(1.0)
                                .foregroundStyle(Theme.bearRed)
                        }
                        Spacer()
                        Text("TAP TO READ")
                            .font(Theme.officialStampFont(size: 7, relativeTo: .caption2))
                            .tracking(1.2)
                            .foregroundStyle(Theme.inkTertiary)
                        Image(systemName: "chevron.right")
                            .font(Theme.serialNumberFont(size: 7, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .padding(.horizontal, Theme.Spacing.medium)
                .padding(.top, Theme.Spacing.standard)
                .padding(.bottom, Theme.Spacing.medium)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .sheet(isPresented: $showDetail) {
            NewsDetailSheet(article: article, onTickerTap: onTickerTap)
        }
        // Item 20: Long-press context menu — Save to Reading List
        .contextMenu {
            if let url = URL(string: article.articleUrl) {
                Button {
                    try? SSReadingList.default()?.addItem(
                        with: url,
                        title: article.headline,
                        previewText: article.summary
                    )
                    HapticManager.success()
                } label: {
                    Label("Save to Reading List", systemImage: "bookmark")
                }
            }
            if let url = URL(string: article.articleUrl) {
                Button {
                    UIPasteboard.general.string = url.absoluteString
                } label: {
                    Label("Copy Link", systemImage: "link")
                }
            }
        }
    }

    private var newsFallbackImage: some View {
        Rectangle()
            .fill(
                LinearGradient(
                    colors: [Theme.canvasDeep, Theme.canvasShadow],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .frame(maxWidth: .infinity)
            .frame(height: UIScreen.main.bounds.height * 0.13)
            .overlay(
                VStack(spacing: Theme.Spacing.tight) {
                    Image(systemName: "newspaper.fill")
                        .font(.title)
                        .foregroundStyle(Theme.inkTertiary.opacity(0.35))
                    Text(sourceLabel)
                        .font(Theme.officialStampFont(size: 10))
                        .foregroundStyle(Theme.inkTertiary.opacity(0.5))
                        .tracking(1.5)
                }
            )
    }
}

// MARK: - News Detail Sheet (shared — used in HomeScreen & NewsMultimediaView)

struct NewsDetailSheet: View {
    let article: NewsArticleItem
    var onTickerTap: ((String) -> Void)? = nil
    @Environment(\.dismiss) var dismiss
    @State private var showSafari = false

    private var timeLabel: String {
        let f = ISO8601DateFormatter()
        if let date = f.date(from: article.publishedAt) {
            return IndianFormatter.elapsed(from: date)
        }
        return article.publishedAt
    }

    private var sourceLabel: String {
        switch article.source {
        case "moneycontrol": return "MoneyControl"
        case "economic_times": return "Economic Times"
        case "nse": return "NSE Official"
        case "business_standard": return "Business Standard"
        case "livemint": return "Livemint"
        case "reuters": return "Reuters"
        default: return article.source.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    private var sentimentColor: Color {
        guard let s = article.sentiment?.lowercased() else { return Theme.holdAmber }
        if s.contains("positive") || s.contains("bullish") { return Theme.bullGreen }
        if s.contains("negative") || s.contains("bearish") { return Theme.bearRed }
        return Theme.holdAmber
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()

                ScrollView {
                    VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                        // Hero image
                        if let imageUrl = article.imageUrl, let url = URL(string: imageUrl) {
                            AsyncImage(url: url) { phase in
                                switch phase {
                                case .success(let img):
                                    img.resizable()
                                        .aspectRatio(contentMode: .fill)
                                        .frame(maxWidth: .infinity)
                                        .frame(height: UIScreen.main.bounds.width * 0.55)
                                        .clipped()
                                case .failure(_), .empty:
                                    EmptyView()
                                @unknown default:
                                    EmptyView()
                                }
                            }
                        }

                        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                            // Source + time row
                            HStack(spacing: Theme.Spacing.small) {
                                Text(sourceLabel.uppercased())
                                    .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                                    .tracking(1.5)
                                    .foregroundStyle(Theme.securityGold)
                                    .padding(.horizontal, Theme.Spacing.small)
                                    .padding(.vertical, Theme.Spacing.xSmall)
                                    .background(Theme.securityGold.opacity(0.10))
                                    .cornerRadius(Theme.CornerRadius.small)

                                if let sentiment = article.sentiment, !sentiment.isEmpty {
                                    Text(sentiment.uppercased())
                                        .font(.caption2.weight(.bold).monospaced())
                                        .tracking(0.8)
                                        .foregroundStyle(sentimentColor)
                                        .padding(.horizontal, Theme.Spacing.small)
                                        .padding(.vertical, Theme.Spacing.xSmall)
                                        .background(sentimentColor.opacity(0.10))
                                        .cornerRadius(Theme.CornerRadius.small)
                                }

                                Spacer()

                                Text(timeLabel)
                                    .font(.caption2.monospaced())
                                    .foregroundStyle(Theme.inkTertiary)
                            }

                            GuillocheDivider()

                            // Headline
                            Text(stripEmoji(article.headline))
                                .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title3))
                                .foregroundStyle(Theme.inkPrimary)
                                .lineSpacing(4)

                            // Ticker chip
                            if let ticker = article.ticker, !ticker.isEmpty {
                                Button(action: { HapticManager.selection()
                                    dismiss()
                                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
                                        onTickerTap?(ticker)
                                    }
                                }) {
                                    HStack(spacing: Theme.Spacing.tight) {
                                        Image(systemName: "chart.line.uptrend.xyaxis")
                                            .font(.caption2.weight(.semibold))
                                        Text(ticker)
                                            .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                                        Image(systemName: "arrow.right")
                                            .font(.caption2)
                                    }
                                    .foregroundStyle(Theme.bullGreen)
                                    .padding(.horizontal, Theme.Spacing.standard)
                                    .padding(.vertical, Theme.Spacing.medium)
                                    .background(Theme.bullGreen.opacity(0.08))
                                    .cornerRadius(Theme.CornerRadius.medium)
                                }
                                .buttonStyle(EKPressStyle())
                            }

                            GuillocheDivider()

                            // Summary / body
                            if let summary = article.summary, !summary.isEmpty {
                                Text(stripEmoji(summary))
                                    .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                                    .foregroundStyle(Theme.inkPrimary.opacity(0.88))
                                    .lineSpacing(6)
                            } else {
                                Text("Full article available at source.")
                                    .font(.footnote)
                                    .foregroundStyle(Theme.inkSecondary)
                            }

                            // Read full article button
                            Button(action: { HapticManager.selection()
                                showSafari = true
                            }) {
                                HStack {
                                    Image(systemName: "safari.fill")
                                    Text("READ FULL ARTICLE")
                                        .font(Theme.officialStampFont(size: 11, relativeTo: .callout))
                                        .tracking(1.5)
                                }
                                .foregroundStyle(Theme.canvas)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, Theme.Spacing.card)
                                .background(Theme.inkPrimary)
                                .cornerRadius(Theme.CornerRadius.large)
                            }
                            .buttonStyle(EKPressStyle())
                            .padding(.top, Theme.Spacing.standard)
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.top, Theme.Spacing.card)
                        .padding(.bottom, Theme.Spacing.xLarge)
                    }
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { HapticManager.selection(); dismiss() }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(Theme.inkSecondary)
                            .font(.title3)
                    }
                    .accessibilityLabel("Close")
                }
            }
        }
        .sheet(isPresented: $showSafari) {
            if let url = SafeURL.web(article.articleUrl) {
                SafariSheetView(url: url)
            }
        }
    }
}
