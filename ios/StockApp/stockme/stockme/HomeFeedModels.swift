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
    let description: String?

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
        case description
    }

    var formattedViewCount: String {
        let v = viewCount ?? 0
        if v >= 1_00_000 { return IndianFormatter.lakhsCroresNoSymbol(Double(v)) }
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
    let snapshots: [PortfolioValuationSnapshot]
    let summary: ValuationSummary

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case days, snapshots, summary
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        userId = try c.decode(Int.self, forKey: .userId)
        days = try c.decode(Int.self, forKey: .days)
        // Unparseable rows are dropped rather than plotted at a bogus date.
        snapshots = try c.decode([PortfolioValuationSnapshot].self, forKey: .snapshots).droppingUndated
        summary = try c.decode(ValuationSummary.self, forKey: .summary)
    }
}

struct PortfolioValuationSnapshot: Codable, Identifiable, WireDated {
    var id: String { date }
    let date: String
    let totalValue: Double
    let totalInvested: Double
    let totalPnl: Double
    let pnlPercent: Double
    let niftyClose: Double?
    /// Parsed once at decode; `.distantPast` when `date` is unparseable.
    let parsedDate: Date

    enum CodingKeys: String, CodingKey {
        case date
        case totalValue = "total_value"
        case totalInvested = "total_invested"
        case totalPnl = "total_pnl"
        case pnlPercent = "pnl_percent"
        case niftyClose = "nifty_close"
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        date = try c.decode(String.self, forKey: .date)
        totalValue = try c.decode(Double.self, forKey: .totalValue)
        totalInvested = try c.decode(Double.self, forKey: .totalInvested)
        totalPnl = try c.decode(Double.self, forKey: .totalPnl)
        pnlPercent = try c.decode(Double.self, forKey: .pnlPercent)
        niftyClose = try c.decodeIfPresent(Double.self, forKey: .niftyClose)
        parsedDate = WireDate.day(date) ?? .distantPast
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

// MARK: - YouTube AI Summary Models

struct YouTubeSummaryContent: Codable {
    let tldr: String
    let keyPoints: [String]
    let financeInsights: [String]
    let tickersMentioned: [String]
    let risksOrRedFlags: [String]
    let actionItems: [String]
    let sentiment: String
    let confidence: Double

    enum CodingKeys: String, CodingKey {
        case tldr
        case keyPoints = "key_points"
        case financeInsights = "finance_insights"
        case tickersMentioned = "tickers_mentioned"
        case risksOrRedFlags = "risks_or_red_flags"
        case actionItems = "action_items"
        case sentiment
        case confidence
    }
}

struct YouTubeSummaryTimestamp: Codable, Identifiable {
    var id: String { "\(startSeconds)-\(label)" }
    let startSeconds: Int
    let label: String
    let summary: String

    enum CodingKeys: String, CodingKey {
        case startSeconds = "start_seconds"
        case label
        case summary
    }
}

struct YouTubeSummarySource: Codable {
    let transcriptSource: String
    let summaryProvider: String
    let cached: Bool

    enum CodingKeys: String, CodingKey {
        case transcriptSource = "transcript_source"
        case summaryProvider = "summary_provider"
        case cached
    }
}

struct YouTubeVideoSummaryResponse: Codable {
    let videoId: String
    let url: String
    let title: String
    let channel: String
    let durationSeconds: Int
    let summary: YouTubeSummaryContent
    let timestamps: [YouTubeSummaryTimestamp]
    let source: YouTubeSummarySource

    enum CodingKeys: String, CodingKey {
        case videoId = "video_id"
        case url, title, channel
        case durationSeconds = "duration_seconds"
        case summary, timestamps, source
    }
}
