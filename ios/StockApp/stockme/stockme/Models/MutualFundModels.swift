import Foundation

// MARK: - Mutual Fund Domain Models
//
// Backed by GET /api/mutual-funds, GET /api/mutual-funds/{scheme_code},
// GET /api/mutual-funds/{scheme_code}/nav-history?days= (see NetworkManager
// Mutual Fund Hub section). Field names below mirror
// backend/routers/mutual_funds.py:MutualFundResponse exactly (id, scheme_code,
// scheme_name, amc_name, category, sub_category, nav, nav_date, aum_cr,
// expense_ratio, returns_1y/3y/5y, risk_level, fund_manager, is_direct_plan,
// is_growth_plan) — the backend is authoritative for shape; do not invent
// fields it doesn't return. NOTE: the backend response has NO holdings or
// sip-calculator endpoints yet — getMutualFundHoldings()/calculateSIP() below
// hit routes that don't exist server-side and are expected to 404 until a
// future backend pass adds them; callers already degrade gracefully (empty
// holdings list, locally-computed SIP projection).

/// Risk-o-meter classification (SEBI standard six-tier scale). Backend reports
/// a subset of these as free text in `risk_level` — parsed defensively.
enum MutualFundRiskLevel: String, Codable, CaseIterable {
    case low = "Low"
    case lowToModerate = "Low to Moderate"
    case moderate = "Moderate"
    case moderatelyHigh = "Moderately High"
    case high = "High"
    case veryHigh = "Very High"

    /// Fraction along the riskometer arc, 0 (Low) → 1 (Very High).
    var gaugeFraction: Double {
        switch self {
        case .low:            return 1.0 / 6
        case .lowToModerate:  return 2.0 / 6
        case .moderate:       return 3.0 / 6
        case .moderatelyHigh: return 4.0 / 6
        case .high:           return 5.0 / 6
        case .veryHigh:       return 6.0 / 6
        }
    }
}

/// A single mutual fund scheme — used both for list/discovery rows and as the
/// seed for the detail screen. Mirrors backend/routers/mutual_funds.py's
/// (forthcoming) MutualFundResponse, which in turn mirrors the MutualFund ORM
/// model's non-legacy columns.
struct MutualFundDTO: Codable, Identifiable, Equatable {
    let id: Int
    let fundName: String
    let amc: String
    let category: String
    let nav: Double?

    // MF Router fields — optional because the live endpoint hasn't been
    // upgraded to return them yet; UI degrades gracefully when nil.
    let schemeCode: String?
    let subCategory: String?
    let navDate: String?
    let aumCr: Double?
    let expenseRatio: Double?
    let returns1y: Double?
    let returns3y: Double?
    let returns5y: Double?
    let riskLevel: String?
    let fundManager: String?
    let isDirectPlan: Bool?
    let isGrowthPlan: Bool?

    enum CodingKeys: String, CodingKey {
        case id
        // Backend (MutualFundResponse) sends scheme_name/amc_name, not the
        // legacy fund_name/amc DB column names — decode from those.
        case fundName = "scheme_name"
        case amc = "amc_name"
        case category
        case nav
        case schemeCode = "scheme_code"
        case subCategory = "sub_category"
        case navDate = "nav_date"
        case aumCr = "aum_cr"
        case expenseRatio = "expense_ratio"
        case returns1y = "returns_1y"
        case returns3y = "returns_3y"
        case returns5y = "returns_5y"
        case riskLevel = "risk_level"
        case fundManager = "fund_manager"
        case isDirectPlan = "is_direct_plan"
        case isGrowthPlan = "is_growth_plan"
    }

    init(
        id: Int,
        fundName: String,
        amc: String,
        category: String,
        nav: Double? = nil,
        schemeCode: String? = nil,
        subCategory: String? = nil,
        navDate: String? = nil,
        aumCr: Double? = nil,
        expenseRatio: Double? = nil,
        returns1y: Double? = nil,
        returns3y: Double? = nil,
        returns5y: Double? = nil,
        riskLevel: String? = nil,
        fundManager: String? = nil,
        isDirectPlan: Bool? = nil,
        isGrowthPlan: Bool? = nil
    ) {
        self.id = id
        self.fundName = fundName
        self.amc = amc
        self.category = category
        self.nav = nav
        self.schemeCode = schemeCode
        self.subCategory = subCategory
        self.navDate = navDate
        self.aumCr = aumCr
        self.expenseRatio = expenseRatio
        self.returns1y = returns1y
        self.returns3y = returns3y
        self.returns5y = returns5y
        self.riskLevel = riskLevel
        self.fundManager = fundManager
        self.isDirectPlan = isDirectPlan
        self.isGrowthPlan = isGrowthPlan
    }

    // Decode defensively: allow the current minimal router payload (no MF
    // Router fields) as well as the richer future payload without failing.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int.self, forKey: .id)
        // scheme_name/amc_name are Optional on the backend response model;
        // decode defensively rather than failing the whole list on a null.
        fundName = try c.decodeIfPresent(String.self, forKey: .fundName) ?? "—"
        amc = try c.decodeIfPresent(String.self, forKey: .amc) ?? "—"
        category = try c.decodeIfPresent(String.self, forKey: .category) ?? "—"
        nav = try c.decodeIfPresent(Double.self, forKey: .nav)
        schemeCode = try c.decodeIfPresent(String.self, forKey: .schemeCode)
        subCategory = try c.decodeIfPresent(String.self, forKey: .subCategory)
        navDate = try c.decodeIfPresent(String.self, forKey: .navDate)
        aumCr = try c.decodeIfPresent(Double.self, forKey: .aumCr)
        expenseRatio = try c.decodeIfPresent(Double.self, forKey: .expenseRatio)
        returns1y = try c.decodeIfPresent(Double.self, forKey: .returns1y)
        returns3y = try c.decodeIfPresent(Double.self, forKey: .returns3y)
        returns5y = try c.decodeIfPresent(Double.self, forKey: .returns5y)
        riskLevel = try c.decodeIfPresent(String.self, forKey: .riskLevel)
        fundManager = try c.decodeIfPresent(String.self, forKey: .fundManager)
        isDirectPlan = try c.decodeIfPresent(Bool.self, forKey: .isDirectPlan)
        isGrowthPlan = try c.decodeIfPresent(Bool.self, forKey: .isGrowthPlan)
    }

    var navDisplay: String {
        guard let nav else { return "—" }
        return String(format: "₹%.2f", nav)
    }

    var aumDisplay: String {
        guard let aumCr else { return "—" }
        return IndianFormatter.formatLakhsCrores(aumCr * 1_00_00_000)
    }

    var expenseRatioDisplay: String {
        guard let expenseRatio else { return "—" }
        return String(format: "%.2f%%", expenseRatio)
    }

    var parsedRiskLevel: MutualFundRiskLevel? {
        guard let riskLevel else { return nil }
        return MutualFundRiskLevel(rawValue: riskLevel)
    }

    var planLabel: String {
        let plan = (isDirectPlan ?? true) ? "Direct" : "Regular"
        let option = (isGrowthPlan ?? true) ? "Growth" : "IDCW"
        return "\(plan) · \(option)"
    }
}

// MARK: - NAV History

/// A single historical NAV observation, used to draw the NAV history chart.
/// Mirrors GET /api/mutual-funds/{id}/nav-history's `[{date, nav}]` payload.
struct MutualFundNAVPoint: Codable, Identifiable, Equatable {
    var id: String { date }
    let date: String
    let nav: Double

    var parsedDate: Date? {
        DateFormatter.ipoDate.date(from: date) ?? ISO8601DateFormatter().date(from: date)
    }
}

/// Selectable chart ranges for the NAV history view.
enum MutualFundNAVRange: String, CaseIterable, Identifiable {
    case oneMonth = "1M"
    case sixMonths = "6M"
    case oneYear = "1Y"
    case threeYears = "3Y"
    case fiveYears = "5Y"

    var id: String { rawValue }

    /// Days of history to request/trim to for this range.
    var approxDays: Int {
        switch self {
        case .oneMonth:   return 30
        case .sixMonths:  return 182
        case .oneYear:    return 365
        case .threeYears: return 365 * 3
        case .fiveYears:  return 365 * 5
        }
    }
}

// MARK: - Holdings

/// A single top-holding line item within a fund's portfolio.
/// Mirrors GET /api/mutual-funds/{id}/holdings.
struct MutualFundHolding: Codable, Identifiable, Equatable {
    var id: String { stockName }
    let stockName: String
    let sector: String?
    let allocationPct: Double

    enum CodingKeys: String, CodingKey {
        case stockName = "stock_name"
        case sector
        case allocationPct = "allocation_pct"
    }
}

// MARK: - SIP Calculator

/// Request body for POST /api/mutual-funds/sip-calculator (proxies
/// backend/services/mutual_fund_calculators.py:calculate_sip_returns).
struct SIPCalculationRequest: Codable {
    let monthlyAmount: Double
    let annualReturnPct: Double
    let years: Double

    enum CodingKeys: String, CodingKey {
        case monthlyAmount = "monthly_amount"
        case annualReturnPct = "annual_return_pct"
        case years
    }
}

/// Mirrors backend/services/mutual_fund_calculators.py:SIPResult.
struct SIPCalculationResult: Codable, Equatable {
    let investedAmount: Double
    let estimatedReturns: Double
    let totalValue: Double

    enum CodingKeys: String, CodingKey {
        case investedAmount = "invested_amount"
        case estimatedReturns = "estimated_returns"
        case totalValue = "total_value"
    }

    /// Local fallback so the SIP calculator still works if the backend
    /// endpoint isn't live yet — mirrors the server formula exactly.
    static func computeLocally(monthlyAmount: Double, annualReturnPct: Double, years: Double) -> SIPCalculationResult {
        let nMonths = years * 12
        let invested = monthlyAmount * nMonths
        let monthlyRate = (annualReturnPct / 100.0) / 12.0

        let totalValue: Double
        if monthlyRate == 0 {
            totalValue = invested
        } else {
            let nWhole = nMonths.rounded()
            totalValue = monthlyAmount * (((pow(1 + monthlyRate, nWhole)) - 1) / monthlyRate) * (1 + monthlyRate)
        }

        return SIPCalculationResult(
            investedAmount: (invested * 100).rounded() / 100,
            estimatedReturns: ((totalValue - invested) * 100).rounded() / 100,
            totalValue: (totalValue * 100).rounded() / 100
        )
    }
}
