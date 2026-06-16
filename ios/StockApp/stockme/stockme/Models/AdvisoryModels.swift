// Models/AdvisoryModels.swift
// Domain: Advisor intelligence, consensus, biographies, ideas feed, harvester (market intelligence microservice)

import SwiftUI

// MARK: - Advisor Consensus

struct AdvisoryConsensusResponse: Codable {
    let generatedAt: String
    let windowDays: Int
    let sectorSignals: [SectorSignal]
    let trendingTickers: [TrendingTicker]
    let totalVideosProcessed: Int
    let lastHarvestAt: String?

    enum CodingKeys: String, CodingKey {
        case generatedAt = "generated_at"
        case windowDays = "window_days"
        case sectorSignals = "sector_signals"
        case trendingTickers = "trending_tickers"
        case totalVideosProcessed = "total_videos_processed"
        case lastHarvestAt = "last_harvest_at"
    }
}

struct SectorSignal: Codable, Identifiable {
    var id: String { theme }
    let theme: String
    let bullishCount: Int
    let bearishCount: Int
    let neutralCount: Int
    let topAdvisors: [String]

    enum CodingKeys: String, CodingKey {
        case theme
        case bullishCount = "bullish_count"
        case bearishCount = "bearish_count"
        case neutralCount = "neutral_count"
        case topAdvisors = "top_advisors"
    }
}

struct TrendingTicker: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let companyName: String
    let mentionCount: Int
    let dominantStance: String
    let totalViewCount: Int
    let advisors: [String]

    enum CodingKeys: String, CodingKey {
        case ticker, advisors
        case companyName = "company_name"
        case mentionCount = "mention_count"
        case dominantStance = "dominant_stance"
        case totalViewCount = "total_view_count"
    }
}

struct AdvisorInsightRow: Codable, Identifiable {
    var id: String { videoUrl }
    let advisorName: String
    let stance: String
    let confidence: String
    let catalystSummary: String
    let videoTitle: String
    let videoUrl: String
    let publishedAt: String
    let transcriptSource: String

    enum CodingKeys: String, CodingKey {
        case stance, confidence
        case advisorName = "advisor_name"
        case catalystSummary = "catalyst_summary"
        case videoTitle = "video_title"
        case videoUrl = "video_url"
        case publishedAt = "published_at"
        case transcriptSource = "transcript_source"
    }
}

// MARK: - Advisor Biographies

struct AdvisorBiography: Codable, Identifiable {
    let id: Int
    let advisorName: String
    let sebiRegNumber: String
    let experienceYears: Int
    let analyticalFramework: String?
    let fullBiographyText: String
    let createdAt: String?
    enum CodingKeys: String, CodingKey {
        case id
        case advisorName = "advisor_name"
        case sebiRegNumber = "sebi_reg_number"
        case experienceYears = "experience_years"
        case analyticalFramework = "analytical_framework"
        case fullBiographyText = "full_biography_text"
        case createdAt = "created_at"
    }
}

struct AdvisorsResponse: Codable {
    let advisors: [AdvisorBiography]
    let count: Int
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case advisors, count
        case fetchedAt = "fetched_at"
    }
}

// MARK: - Ideas Feed

struct TextAdvisoryInsight: Codable, Identifiable {
    let id: Int
    let advisorName: String?
    let timestamp: String?
    let contentText: String
    let targetTicker: String?
    let extractedSentiment: String?
    enum CodingKeys: String, CodingKey {
        case id
        case advisorName = "advisor_name"
        case timestamp
        case contentText = "content_text"
        case targetTicker = "target_ticker"
        case extractedSentiment = "extracted_sentiment"
    }
}

struct IdeasFeedResponse: Codable {
    let insights: [TextAdvisoryInsight]
    let count: Int
    let fetchedAt: String
    enum CodingKeys: String, CodingKey {
        case insights, count
        case fetchedAt = "fetched_at"
    }
}

// MARK: - Harvester (Market Intelligence) — port 8001 microservice

struct HarvestedCard: Codable, Identifiable {
    let id: Int
    let sourceType: String
    let sourceName: String
    let sourceUrl: String
    let originalAuthor: String?
    let publishedAt: String?
    let title: String
    let reformattedSummary: String?
    let keyTakeaways: [String]?
    let tickers: [String]?
    let sentiment: String?
    let credibilityScore: Int
    let cardType: String
    let expertCredential: String?
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case sourceType = "source_type"
        case sourceName = "source_name"
        case sourceUrl = "source_url"
        case originalAuthor = "original_author"
        case publishedAt = "published_at"
        case title
        case reformattedSummary = "reformatted_summary"
        case keyTakeaways = "key_takeaways"
        case tickers
        case sentiment
        case credibilityScore = "credibility_score"
        case cardType = "card_type"
        case expertCredential = "expert_credential"
        case createdAt = "created_at"
    }
}

struct HarvesterFeedResponse: Codable {
    let cards: [HarvestedCard]
    let total: Int
    let sources: [String]
}

struct HarvesterSourceStatus: Codable, Identifiable {
    var id: String { sourceName }
    let sourceName: String
    let lastSuccess: String?
    let lastFailure: String?
    let itemsScraped: Int
    let isHealthy: Bool
    let errorMessage: String?

    enum CodingKeys: String, CodingKey {
        case sourceName = "source_name"
        case lastSuccess = "last_success"
        case lastFailure = "last_failure"
        case itemsScraped = "items_scraped"
        case isHealthy = "is_healthy"
        case errorMessage = "error_message"
    }
}

// MARK: - Expert Network

struct MarketExpert: Identifiable {
    let id: String
    let name: String
    let sebiRegId: String?
    let yearsExperience: Int
    let strategy: String          // e.g. "Harmonic Trading Strategy"
    let focusTags: [String]       // e.g. ["Charts", "Currency", "Gold"]
    let postCount: Int
    let isVerified: Bool
    let bio: String
}

struct ExpertPost: Identifiable {
    let id: String
    let expertId: String
    let expertName: String
    let content: String           // unhedged plain-english analysis
    let ticker: String?
    let chartImageUrl: String?
    let publishedAt: Date
    let likeCount: Int
    let isPremium: Bool
    var isLiked: Bool = false
    var isBookmarked: Bool = false
}

// MARK: - OTC Advisory

struct OTCAdvisory: Identifiable {
    let id: String
    let companyName: String
    let entryPrice: Double
    let targetPrice: Double
    let stopLoss: Double
    let rationale: String
    let isPremium: Bool
}
