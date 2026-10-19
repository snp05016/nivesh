import Foundation

/// GET /api/v1/stocks/{symbol}/risk-flags. `unavailable` is ignored on iOS; `checks` is optional so older servers decode.
struct RiskFlagsDTO: Decodable, Equatable {
    let symbol: String
    let checks: [String]?
    let flags: [RiskFlagDTO]
}

struct RiskFlagDTO: Decodable, Equatable, Identifiable {
    let id: String
    let title: String
    let text: String
    let source: String
    let sourceUrl: String?
    let asOf: String?

    enum CodingKeys: String, CodingKey {
        case id, title, text, source
        case sourceUrl = "source_url"
        case asOf = "as_of"
    }
}
