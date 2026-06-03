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
}

struct YouTubeVideoItem: Codable, Identifiable {
    let id: Int
    let videoId: String
    let channelName: String
    let title: String
    let thumbnailUrl: String?
    let videoUrl: String
    let publishedAt: String
    let viewCount: Int
    let durationSeconds: Int
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
        if viewCount >= 1_00_000 {
            return String(format: "%.1fL", Double(viewCount) / 1_00_000.0)
        } else if viewCount >= 1000 {
            return String(format: "%.1fK", Double(viewCount) / 1000.0)
        }
        return "\(viewCount)"
    }

    var formattedDuration: String {
        let m = durationSeconds / 60
        let s = durationSeconds % 60
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
