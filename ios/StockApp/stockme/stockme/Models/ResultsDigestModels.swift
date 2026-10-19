import Foundation

// MARK: - Latest results digest
//
// Backed by GET /api/v1/stocks/{symbol}/results-digest (backend/routers/results_digest.py,
// flag data_results_digest). Three figures from Yahoo Finance and a link to the exchange
// filing; no generated text. Error bodies are {"detail": {"code": ...}}.

struct ResultsDigest: Codable, Equatable {
    let symbol: String
    let periodEnd: String
    let periodLabel: String
    let filingUrl: String?
    let filingTitle: String?
    let announcedAt: String?
    /// ok | pending | unavailable
    let numbersStatus: String
    let revenueInr: Double?
    let revenueYoyPct: Double?
    let netProfitInr: Double?
    let netProfitYoyPct: Double?
    let eps: Double?
    let epsYoyPct: Double?
    let numbersSourceText: String

    enum CodingKeys: String, CodingKey {
        case symbol, eps
        case periodEnd = "period_end"
        case periodLabel = "period_label"
        case filingUrl = "filing_url"
        case filingTitle = "filing_title"
        case announcedAt = "announced_at"
        case numbersStatus = "numbers_status"
        case revenueInr = "revenue_inr"
        case revenueYoyPct = "revenue_yoy_pct"
        case netProfitInr = "net_profit_inr"
        case netProfitYoyPct = "net_profit_yoy_pct"
        case epsYoyPct = "eps_yoy_pct"
        case numbersSourceText = "numbers_source_text"
    }

    var isPending: Bool { numbersStatus == "pending" }
    var isUnavailable: Bool { numbersStatus == "unavailable" }

    /// The filing link, only when it is a plain https URL.
    var filingURL: URL? {
        guard let filingUrl, let url = URL(string: filingUrl), url.scheme?.lowercased() == "https" else { return nil }
        return url
    }

    /// "+8.2% YoY"; a fall uses the true minus sign ("−3.1% YoY"); nil is "—".
    static func yoyText(_ value: Double?) -> String {
        guard let value else { return "—" }
        let rounded = (value * 10).rounded() / 10
        let magnitude = String(format: "%.1f", abs(rounded))
        if rounded < 0 { return "\u{2212}\(magnitude)% YoY" }
        return "+\(magnitude)% YoY"
    }

    /// EPS in rupees with two decimals, e.g. "₹5.50".
    static func epsText(_ value: Double?) -> String {
        guard let value else { return "—" }
        return String(format: "₹%.2f", value)
    }

    /// True when the card should disappear: the feature is off for this user, or there is no digest.
    static func shouldHide(_ error: Error) -> Bool {
        if case NetworkError.fetchFailed(_, let status, let body) = error {
            return status == 404 && (body.contains("FEATURE_DISABLED") || body.contains("NO_DIGEST"))
        }
        return false
    }
}
