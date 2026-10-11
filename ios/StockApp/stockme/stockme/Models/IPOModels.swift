import Foundation

// MARK: - IPO Domain Models
//
// Backed by GET /api/ipo, GET /api/ipo/{id}, GET /api/ipo/{id}/subscription-status,
// GET /api/ipo/calendar (see NetworkManager IPO Hub section). Field names below
// mirror backend/routers/ipo.py's IPOResponse / IPOSubscriptionResponse exactly —
// the backend is authoritative for shape; do not invent fields it doesn't return.

/// Lifecycle state of an IPO relative to today.
enum IPOStatus: String, Codable, CaseIterable {
    case upcoming
    case open
    case closed
    case listed

    var displayLabel: String {
        switch self {
        case .upcoming: return "Upcoming"
        case .open:     return "Open"
        case .closed:   return "Closed"
        case .listed:   return "Listed"
        }
    }
}

/// A single IPO — used both for list rows and the detail screen.
/// Mirrors backend/routers/ipo.py:IPOResponse.
struct IPOListing: Codable, Identifiable, Equatable {
    let id: Int
    let companyName: String
    let symbol: String?
    let priceBandLow: Double?
    let priceBandHigh: Double?
    let lotSize: Int?
    /// Total issue size in INR Crores (backend already reports this in Crores, not raw Rupees).
    let issueSizeCr: Double?
    let openDate: String?
    let closeDate: String?
    let listingDate: String?
    let status: IPOStatus?
    /// Grey Market Premium, in Rupees per share. Nil when no GMP feed is available for this IPO.
    let gmp: Double?
    /// True for the backend's fictional seed rows; the UI must label these as sample data.
    let isSample: Bool?

    enum CodingKeys: String, CodingKey {
        case id
        case companyName = "company_name"
        case symbol
        case priceBandLow = "price_band_low"
        case priceBandHigh = "price_band_high"
        case lotSize = "lot_size"
        case issueSizeCr = "issue_size_cr"
        case openDate = "open_date"
        case closeDate = "close_date"
        case listingDate = "listing_date"
        case status
        case gmp
        case isSample = "is_sample"
    }

    var priceBandDisplay: String {
        guard let low = priceBandLow, let high = priceBandHigh else { return "—" }
        return "\(IndianFormatter.price(low)) – \(IndianFormatter.price(high))"
    }

    var lotSizeDisplay: String {
        guard let lotSize else { return "—" }
        return "\(lotSize) Shares"
    }

    /// Issue size formatted via the shared Indian-numbering helper. `issueSizeCr` is already
    /// in Crores, so it's converted back to raw Rupees before going through
    /// IndianFormatter.formatLakhsCrores (the sole authorized currency formatter).
    var issueSizeDisplay: String {
        guard let issueSizeCr else { return "—" }
        return IndianFormatter.formatLakhsCrores(issueSizeCr * 1_00_00_000)
    }

    /// Estimated listing gain percentage implied by GMP over the price band ceiling.
    var estimatedListingGainPct: Double? {
        guard let gmp, let high = priceBandHigh, high > 0 else { return nil }
        return (gmp / high) * 100
    }
}

/// Live subscription snapshot (times subscribed by category) for a single IPO.
/// Mirrors backend/routers/ipo.py:IPOSubscriptionResponse.
struct IPOSubscriptionDetail: Codable, Equatable {
    let id: Int
    let companyName: String
    let symbol: String?
    let status: IPOStatus?
    let subscriptionQib: Double?
    let subscriptionNii: Double?
    let subscriptionRetail: Double?

    enum CodingKeys: String, CodingKey {
        case id
        case companyName = "company_name"
        case symbol
        case status
        case subscriptionQib = "subscription_qib"
        case subscriptionNii = "subscription_nii"
        case subscriptionRetail = "subscription_retail"
    }

    var qibTimes: Double { subscriptionQib ?? 0 }
    var niiTimes: Double { subscriptionNii ?? 0 }
    var retailTimes: Double { subscriptionRetail ?? 0 }

    /// Backend does not report an employee category or a refresh timestamp yet.
    var employeeTimes: Double? { nil }
    var asOf: String? { nil }
    // No "overall" figure: it must be weighted by category reservation, which the
    // backend does not report, so only per-category multiples are shown.
}
