// Models/XRayModels.swift
// Domain: Portfolio X-ray (I28, GET /api/v1/me/portfolio/xray), regular-plan costs (I34, spec 3.6)
// and the COVID replay (I35, GET /api/v1/me/portfolio/crisis-replay, spec 3.9).

import Foundation

// MARK: - X-ray

nonisolated struct XRayResponse: Decodable {
    let asOf: String
    let totalValueInr: Double
    let unpriced: [XRayUnpriced]
    let allocation: [XRaySlice]
    let amcs: [XRayAMC]
    /// nil when the user holds no funds.
    let plans: XRayPlans?
    let topHoldings: [XRayHolding]
    let concentration: XRayConcentration
    let facts: [XRayFact]
    let commissionDrag: CommissionDrag?

    /// Nothing to analyse: no holdings at all.
    var isEmpty: Bool { allocation.isEmpty && topHoldings.isEmpty }

    enum CodingKeys: String, CodingKey {
        case unpriced, allocation, amcs, plans, concentration, facts
        case asOf = "as_of"
        case totalValueInr = "total_value_inr"
        case topHoldings = "top_holdings"
        case commissionDrag = "commission_drag"
    }
}

nonisolated struct XRayUnpriced: Decodable {
    let ticker: String
    let name: String
}

nonisolated struct XRaySlice: Decodable, Identifiable {
    var id: String { key }
    let key: String
    let label: String
    let valueInr: Double
    let pct: Double

    enum CodingKeys: String, CodingKey {
        case key, label, pct
        case valueInr = "value_inr"
    }
}

nonisolated struct XRayAMC: Decodable, Identifiable {
    var id: String { name }
    let name: String
    let valueInr: Double
    let pct: Double

    enum CodingKeys: String, CodingKey {
        case name, pct
        case valueInr = "value_inr"
    }
}

nonisolated struct XRayPlans: Decodable {
    let directPct: Double
    let regularPct: Double
    let unknownPct: Double

    enum CodingKeys: String, CodingKey {
        case directPct = "direct_pct"
        case regularPct = "regular_pct"
        case unknownPct = "unknown_pct"
    }
}

nonisolated struct XRayHolding: Decodable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let name: String
    let assetClass: String
    let valueInr: Double
    let pct: Double

    enum CodingKeys: String, CodingKey {
        case ticker, name, pct
        case assetClass = "asset_class"
        case valueInr = "value_inr"
    }
}

nonisolated struct XRayConcentration: Decodable {
    let largestTicker: String?
    let largestPct: Double
    let top5Pct: Double

    enum CodingKeys: String, CodingKey {
        case largestTicker = "largest_ticker"
        case largestPct = "largest_pct"
        case top5Pct = "top5_pct"
    }
}

nonisolated struct XRayFact: Decodable, Identifiable {
    var id: String { code }
    let code: String
    /// Fixed server template, shown verbatim.
    let text: String
}

// MARK: - Regular-plan costs (spec 3.6)

nonisolated struct CommissionDrag: Decodable {
    let available: Bool
    /// ter_data_missing | ter_data_stale when not available.
    let reason: String?
    let asOf: String?
    let totalAnnualCostInr: Double?
    let uncoveredRegularFunds: Int?
    let funds: [CommissionDragFund]?
    let source: String?
    let sourceUrl: String?

    enum CodingKeys: String, CodingKey {
        case available, reason, funds, source
        case asOf = "as_of"
        case totalAnnualCostInr = "total_annual_cost_inr"
        case uncoveredRegularFunds = "uncovered_regular_funds"
        case sourceUrl = "source_url"
    }
}

nonisolated struct CommissionDragFund: Decodable, Identifiable {
    var id: String { isin ?? name }
    let isin: String?
    let name: String
    let valueInr: Double?
    let regularTerPct: Double?
    let directTerPct: Double?
    /// Regular minus direct expense ratio, in percentage points.
    let gapPp: Double?
    let annualCostInr: Double?

    enum CodingKeys: String, CodingKey {
        case isin, name
        case valueInr = "value_inr"
        case regularTerPct = "regular_ter_pct"
        case directTerPct = "direct_ter_pct"
        case gapPp = "gap_pp"
        case annualCostInr = "annual_cost_inr"
    }
}

// MARK: - COVID replay (spec 3.9)

nonisolated struct CrisisReplayResponse: Decodable {
    let scenario: CrisisScenario
    let niftyReturnPct: Double?
    let portfolioReturnPct: Double?
    let portfolioChangeInr: Double?
    let coveredValueInr: Double?
    let holdings: [CrisisReplayHolding]
    let notIncluded: [CrisisNotIncluded]
    let notes: [String]

    enum CodingKeys: String, CodingKey {
        case scenario, holdings, notes
        case niftyReturnPct = "nifty_return_pct"
        case portfolioReturnPct = "portfolio_return_pct"
        case portfolioChangeInr = "portfolio_change_inr"
        case coveredValueInr = "covered_value_inr"
        case notIncluded = "not_included"
    }
}

nonisolated struct CrisisScenario: Decodable {
    let id: String
    let label: String
    let start: String
    let end: String
}

nonisolated struct CrisisReplayHolding: Decodable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let name: String
    let valueInr: Double
    let returnPct: Double

    enum CodingKeys: String, CodingKey {
        case ticker, name
        case valueInr = "value_inr"
        case returnPct = "return_pct"
    }
}

nonisolated struct CrisisNotIncluded: Decodable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let name: String
    let valueInr: Double?
    /// listed_after_window | not_traded_at_window_end | mutual_fund | unpriced
    let reason: String

    enum CodingKeys: String, CodingKey {
        case ticker, name, reason
        case valueInr = "value_inr"
    }
}

// MARK: - Copy

nonisolated enum XRayCopy {
    /// "Rs 8,450", "Rs 4.12 lakh", "Rs 1.20 crore": Indian scale, rounded on the printed value.
    static func rupees(_ value: Double) -> String {
        let v = abs(value)
        let lakhs = (v / 1_00_000 * 100).rounded() / 100
        if lakhs >= 100 { return String(format: "Rs %.2f crore", (v / 1_00_00_000 * 100).rounded() / 100) }
        if v >= 1_00_000 { return String(format: "Rs %.2f lakh", lakhs) }
        return "Rs " + grouped(v.rounded())
    }

    private static func grouped(_ whole: Double) -> String {
        let digits = String(Int(whole))
        guard digits.count > 3 else { return digits }
        let tail = String(digits.suffix(3))
        var head = String(digits.dropLast(3))
        var parts: [String] = []
        while head.count > 2 {
            parts.insert(String(head.suffix(2)), at: 0)
            head = String(head.dropLast(2))
        }
        if !head.isEmpty { parts.insert(head, at: 0) }
        return (parts + [tail]).joined(separator: ",")
    }

    // Regular-plan costs

    static let dragTitle = "Regular-plan costs"
    static let dragLinkTitle = "About expense ratios (AMFI)"

    /// "Published expense ratios of your regular-plan funds are 0.6-1.1 points higher than the same
    /// funds' direct plans. On your current value that's about Rs 8,450 a year." nil when unavailable.
    static func dragBody(_ d: CommissionDrag) -> String? {
        guard d.available, let total = d.totalAnnualCostInr else { return nil }
        let gaps = (d.funds ?? []).compactMap(\.gapPp)
        var range = ""
        if let lo = gaps.min(), let hi = gaps.max() {
            let a = String(format: "%.1f", lo), b = String(format: "%.1f", hi)
            range = a == b ? "\(a) points" : "\(a)-\(b) points"
        }
        let gap = range.isEmpty ? "higher" : "\(range) higher"
        return "Published expense ratios of your regular-plan funds are \(gap) than the same funds' direct plans. On your current value that's about \(rupees(total)) a year."
    }

    static func dragFootnote(_ d: CommissionDrag) -> String {
        var line = "Regular plans include a distributor commission in their expense ratio. Moving between plans counts as a redemption for tax."
        if let when = MoneyReturnCopy.day(d.asOf) { line += " Expense ratios as of \(when)." }
        return line
    }

    // COVID replay

    static func replayTitle(_ r: CrisisReplayResponse) -> String {
        r.scenario.id == "covid_2020" ? "COVID crash replay (19 Feb - 23 Mar 2020)" : r.scenario.label
    }

    /// "If your current stocks moved as they did then, they'd be worth Rs 4.12 lakh less (-33%). The Nifty 50
    /// fell 37% in the same period." nil without a portfolio figure.
    static func replaySummary(_ r: CrisisReplayResponse) -> String? {
        guard let change = r.portfolioChangeInr, let pct = r.portfolioReturnPct else { return nil }
        let more = change >= 0
        var line = "If your current stocks moved as they did then, they'd be worth \(rupees(change)) \(more ? "more" : "less") (\(signedPct(pct)))."
        if let nifty = r.niftyReturnPct {
            line += " The Nifty 50 \(nifty >= 0 ? "rose" : "fell") \(pct0(abs(nifty))) in the same period."
        }
        return line
    }

    static func notIncludedReason(_ reason: String) -> String {
        switch reason {
        case "mutual_fund": return "Mutual funds aren't included."
        case "listed_after_window": return "Not listed on 19 Feb 2020."
        case "not_traded_at_window_end": return "Not trading at the end of the period."
        case "unpriced": return "No current price."
        default: return "Not included."
        }
    }

    private static func signedPct(_ v: Double) -> String {
        let r = v.rounded()
        return (r > 0 ? "+" : "") + String(format: "%.0f%%", r == 0 ? 0 : r)
    }

    private static func pct0(_ v: Double) -> String { String(format: "%.0f%%", v) }
}
