import Foundation

// MARK: - Home Feed Response Models

struct HomeFeedResponse: Codable {
    let news: [NewsArticleItem]
    let redFlagAlerts: [NewsArticleItem]
    let youtubeVideos: [YouTubeVideoItem]
    let generatedAt: String

    enum CodingKeys: String, CodingKey {
        case news
        case redFlagAlerts = "red_flag_alerts"
        case youtubeVideos = "youtube_videos"
        case generatedAt = "generated_at"
    }
}

struct NewsArticleItem: Codable, Identifiable {
    let id: Int
    let source: String
    let ticker: String?
    let headline: String
    let summary: String?
    let imageUrl: String?
    let articleUrl: String
    let publishedAt: String
    let isRedFlag: Bool
    let sentiment: String?

    enum CodingKeys: String, CodingKey {
        case id, source, ticker, headline, summary
        case imageUrl = "image_url"
        case articleUrl = "article_url"
        case publishedAt = "published_at"
        case isRedFlag = "is_red_flag"
        case sentiment
    }

    // Backend returns dates without "Z" timezone ("2026-06-08T21:04:26").
    // ISO8601DateFormatter requires timezone by default — use a fallback chain.
    var parsedDate: Date? {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = iso.date(from: publishedAt) { return d }
        iso.formatOptions = [.withInternetDateTime]
        if let d = iso.date(from: publishedAt) { return d }
        let f = DateFormatter()
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        if let d = f.date(from: publishedAt) { return d }
        f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return f.date(from: publishedAt)
    }
}

struct YouTubeVideoItem: Codable, Identifiable {
    let id: Int
    let videoId: String
    let channelName: String
    let title: String
    let thumbnailUrl: String?
    let videoUrl: String
    let publishedAt: String
    let viewCount: Int?
    let durationSeconds: Int?
    let tickersMentioned: [String]

    enum CodingKeys: String, CodingKey {
        case id
        case videoId = "video_id"
        case channelName = "channel_name"
        case title
        case thumbnailUrl = "thumbnail_url"
        case videoUrl = "video_url"
        case publishedAt = "published_at"
        case viewCount = "view_count"
        case durationSeconds = "duration_seconds"
        case tickersMentioned = "tickers_mentioned"
    }

    var formattedViewCount: String {
        let v = viewCount ?? 0
        if v >= 1_00_000 { return String(format: "%.1fL", Double(v) / 1_00_000.0) }
        if v >= 1000 { return String(format: "%.1fK", Double(v) / 1000.0) }
        return v > 0 ? "\(v)" : ""
    }

    var formattedDuration: String {
        let secs = durationSeconds ?? 0
        let m = secs / 60
        let s = secs % 60
        return String(format: "%d:%02d", m, s)
    }
}

// MARK: - Valuation Calendar Models

struct ValuationHistoryResponse: Codable {
    let userId: Int
    let days: Int
    let snapshots: [ValuationSnapshot]
    let summary: ValuationSummary

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case days, snapshots, summary
    }
}

struct ValuationSnapshot: Codable, Identifiable {
    var id: String { date }
    let date: String
    let totalValue: Double
    let totalInvested: Double
    let totalPnl: Double
    let pnlPercent: Double
    let niftyClose: Double?

    enum CodingKeys: String, CodingKey {
        case date
        case totalValue = "total_value"
        case totalInvested = "total_invested"
        case totalPnl = "total_pnl"
        case pnlPercent = "pnl_percent"
        case niftyClose = "nifty_close"
    }

    var parsedDate: Date {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f.date(from: date) ?? Date()
    }
}

struct ValuationSummary: Codable {
    let periodChangeValue: Double
    let periodChangePct: Double
    let peakValue: Double
    let troughValue: Double
    let dataPoints: Int

    enum CodingKeys: String, CodingKey {
        case periodChangeValue = "period_change_value"
        case periodChangePct = "period_change_pct"
        case peakValue = "peak_value"
        case troughValue = "trough_value"
        case dataPoints = "data_points"
    }
}
