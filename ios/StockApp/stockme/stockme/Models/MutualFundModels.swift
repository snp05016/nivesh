import Foundation

// MARK: - Mutual Fund Domain Models
//
// Backed by GET /api/mutual-funds, GET /api/mutual-funds/{scheme_code},
// GET /api/mutual-funds/{scheme_code}/nav-history?days= (see NetworkManager
// Mutual Fund Hub section). Field names below mirror
// backend/routers/mutual_funds.py:MutualFundResponse exactly (id, scheme_code,
// scheme_name, amc_name, category, sub_category, nav, nav_date, aum_cr,
// expense_ratio, returns_1y/3y/5y, risk_level, fund_manager, is_direct_plan,
// is_growth_plan, is_sample) — the backend is authoritative for shape; do not
// invent fields it doesn't return. There are no holdings or sip-calculator
// endpoints: the SIP projection is computed locally
// (SIPCalculationResult.computeLocally).

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
    /// True when the backend serves this row from its seeded sample catalog
    /// (frozen illustrative figures, not a live AMFI feed). The UI must label it.
    let isSample: Bool?

    // Data foundation (AMFI universe). All optional: older backends omit them.
    let schemeType: String?
    let navSource: String?
    let isActive: Bool?
    let isinGrowth: String?
    let isinReinvest: String?
    /// ISO date (yyyy-MM-dd) of the first NAV Nivesh recorded for this fund. Detail only.
    let historyStart: String?

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
        case isSample = "is_sample"
        case schemeType = "scheme_type"
        case navSource = "nav_source"
        case isActive = "is_active"
        case isinGrowth = "isin_growth"
        case isinReinvest = "isin_reinvest"
        case historyStart = "history_start"
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
        isGrowthPlan: Bool? = nil,
        isSample: Bool? = nil,
        schemeType: String? = nil,
        navSource: String? = nil,
        isActive: Bool? = nil,
        isinGrowth: String? = nil,
        isinReinvest: String? = nil,
        historyStart: String? = nil
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
        self.isSample = isSample
        self.schemeType = schemeType
        self.navSource = navSource
        self.isActive = isActive
        self.isinGrowth = isinGrowth
        self.isinReinvest = isinReinvest
        self.historyStart = historyStart
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
        isSample = try c.decodeIfPresent(Bool.self, forKey: .isSample)
        schemeType = try c.decodeIfPresent(String.self, forKey: .schemeType)
        navSource = try c.decodeIfPresent(String.self, forKey: .navSource)
        isActive = try c.decodeIfPresent(Bool.self, forKey: .isActive)
        isinGrowth = try c.decodeIfPresent(String.self, forKey: .isinGrowth)
        isinReinvest = try c.decodeIfPresent(String.self, forKey: .isinReinvest)
        historyStart = try c.decodeIfPresent(String.self, forKey: .historyStart)
    }

    var navDisplay: String {
        guard let nav else { return "—" }
        return String(format: "₹%.2f", nav)
    }

    /// Four-decimal NAV as AMFI publishes it, e.g. "₹123.4567".
    var navPreciseDisplay: String {
        guard let nav else { return "—" }
        return String(format: "₹%.4f", nav)
    }

    /// True when this row's NAV comes straight from the AMFI file.
    var isAMFISourced: Bool { navSource == "amfi" }

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

// MARK: - Discovery query, filters and paging

/// GET /api/mutual-funds/filters — categories with their sub-categories, and fund houses.
struct MutualFundFilters: Codable, Equatable {
    let categories: [String: [String]]
    let amcs: [String]

    var sortedCategories: [String] { categories.keys.sorted() }
}

enum MutualFundPlanFilter: String, CaseIterable, Identifiable {
    case direct, regular, all

    var id: String { rawValue }
    var label: String {
        switch self {
        case .direct:  return "Direct"
        case .regular: return "Regular"
        case .all:     return "All plans"
        }
    }
}

enum MutualFundOptionFilter: String, CaseIterable, Identifiable {
    case growth, idcw, all

    var id: String { rawValue }
    var label: String {
        switch self {
        case .growth: return "Growth"
        case .idcw:   return "IDCW"
        case .all:    return "All options"
        }
    }
}

/// One page request for the discovery list. Defaults match the backend's: Direct, Growth, 50 per page.
struct MutualFundQuery: Equatable {
    var search: String = ""
    var plan: MutualFundPlanFilter = .direct
    var option: MutualFundOptionFilter = .growth
    var category: String? = nil
    var subCategory: String? = nil
    var amc: String? = nil
    var limit: Int = 50
    var offset: Int = 0

    /// Always plan, option, limit and offset; the rest only when non-empty (search trimmed).
    var queryItems: [URLQueryItem] {
        var items = [
            URLQueryItem(name: "plan", value: plan.rawValue),
            URLQueryItem(name: "option", value: option.rawValue),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "offset", value: String(offset)),
        ]
        let term = search.trimmingCharacters(in: .whitespacesAndNewlines)
        if !term.isEmpty { items.append(URLQueryItem(name: "search", value: term)) }
        if let category, !category.isEmpty { items.append(URLQueryItem(name: "category", value: category)) }
        if let subCategory, !subCategory.isEmpty { items.append(URLQueryItem(name: "sub_category", value: subCategory)) }
        if let amc, !amc.isEmpty { items.append(URLQueryItem(name: "amc_name", value: amc)) }
        return items
    }

    /// Query items with every reserved character (including '&', '+', '=') percent-encoded;
    /// URLComponents leaves '&' and '+' in values untouched, which would split "L&T Mutual Fund".
    var percentEncodedQueryItems: [URLQueryItem] {
        var allowed = CharacterSet.urlQueryAllowed
        allowed.remove(charactersIn: "&+=#;")
        return queryItems.map { item in
            URLQueryItem(name: item.name, value: item.value?.addingPercentEncoding(withAllowedCharacters: allowed))
        }
    }

    func url(baseURL: String) -> URL? {
        guard var comps = URLComponents(string: "\(baseURL)/api/mutual-funds/") else { return nil }
        comps.percentEncodedQueryItems = percentEncodedQueryItems
        return comps.url
    }

    /// X-Total-Count, or nil when the header is absent or not a number (an old backend sends one page only).
    static func totalCount(from response: HTTPURLResponse) -> Int? {
        guard let raw = response.value(forHTTPHeaderField: "X-Total-Count") else { return nil }
        return Int(raw.trimmingCharacters(in: .whitespaces))
    }

    /// More pages exist only when the backend reported a total and we hold fewer rows than it.
    static func canLoadMore(loaded: Int, total: Int?) -> Bool {
        total.map { loaded < $0 } ?? false
    }
}

/// "2026-10-09" -> "9 Oct 2026". Returns the input unchanged when it is not an ISO date.
enum MutualFundDateText {
    private static let iso: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
    private static let display: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_IN")
        f.dateFormat = "d MMM yyyy"
        return f
    }()

    static func short(_ isoDate: String) -> String {
        guard let date = iso.date(from: isoDate) else { return isoDate }
        return display.string(from: date)
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

/// Selectable chart ranges for the NAV history view. Every range must fit the
/// backend's `days` limit (1-365) — no 3Y/5Y until the backend serves them.
enum MutualFundNAVRange: String, CaseIterable, Identifiable {
    case oneMonth = "1M"
    case sixMonths = "6M"
    case oneYear = "1Y"

    var id: String { rawValue }

    /// Days of history to request/trim to for this range.
    var approxDays: Int {
        switch self {
        case .oneMonth:   return 30
        case .sixMonths:  return 182
        case .oneYear:    return 365
        }
    }
}

// MARK: - SIP Calculator

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

    /// The SIP calculator's only engine (there is no backend route) —
    /// mirrors mutual_fund_calculators.py:calculate_sip_returns exactly.
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
