// Models/TaxReportModels.swift
// Domain: FY capital-gains working for listed shares (I29, GET /api/v1/me/tax/capital-gains). spec_money 3.7.
// Informational only; the screen never suggests ways to reduce tax.

import Foundation

nonisolated struct CapitalGainsReport: Decodable {
    let fy: String
    let rulesVersion: String
    let asOf: String
    let summary: CapitalGainsSummary
    let rows: [CapitalGainsRow]
    let notComputed: [NotComputedRow]
    let scopeNote: String
    let disclaimer: String

    enum CodingKeys: String, CodingKey {
        case fy, summary, rows, disclaimer
        case rulesVersion = "rules_version"
        case asOf = "as_of"
        case notComputed = "not_computed"
        case scopeNote = "scope_note"
    }
}

nonisolated struct GainsByPeriod: Decodable {
    let pre: Double
    let post: Double

    enum CodingKeys: String, CodingKey {
        case pre = "pre_2024_07_23"
        case post = "post_2024_07_23"
    }
}

nonisolated struct CapitalGainsSummary: Decodable {
    let stcg: GainsByPeriod
    let ltcg: GainsByPeriod
    let ltcgExemptionLimitInr: Double
    let ltcgAboveExemptionInr: Double
    let rows: Int
    let notComputed: Int
    let needsReview: Int

    enum CodingKeys: String, CodingKey {
        case stcg, ltcg, rows
        case ltcgExemptionLimitInr = "ltcg_exemption_limit_inr"
        case ltcgAboveExemptionInr = "ltcg_above_exemption_inr"
        case notComputed = "not_computed"
        case needsReview = "needs_review"
    }
}

nonisolated struct CapitalGainsRow: Decodable, Identifiable {
    var id: String { "\(symbol)|\(soldOn)|\(acquiredOn)|\(quantity)" }
    /// STCG | LTCG
    let term: String
    let section: String
    let ratePeriod: String
    let symbol: String
    let name: String
    let quantity: Double
    let acquiredOn: String
    let soldOn: String
    let saleValueInr: Double
    let costOfAcquisitionInr: Double
    let fmvPerUnit: Double?
    let fmvTotalInr: Double?
    let costUsedInr: Double
    let transferExpensesInr: Double
    let gainInr: Double
    let needsReview: Bool
    let reviewReasons: [String]

    var isLongTerm: Bool { term == "LTCG" }

    enum CodingKeys: String, CodingKey {
        case term, section, symbol, name, quantity
        case ratePeriod = "rate_period"
        case acquiredOn = "acquired_on"
        case soldOn = "sold_on"
        case saleValueInr = "sale_value_inr"
        case costOfAcquisitionInr = "cost_of_acquisition_inr"
        case fmvPerUnit = "fmv_per_unit"
        case fmvTotalInr = "fmv_total_inr"
        case costUsedInr = "cost_used_inr"
        case transferExpensesInr = "transfer_expenses_inr"
        case gainInr = "gain_inr"
        case needsReview = "needs_review"
        case reviewReasons = "review_reasons"
    }
}

nonisolated struct NotComputedRow: Decodable, Identifiable {
    var id: String { "\(symbol)|\(soldOn)|\(reason)|\(quantity)" }
    let symbol: String
    let soldOn: String
    let quantity: Double
    let reason: String

    enum CodingKeys: String, CodingKey {
        case symbol, quantity, reason
        case soldOn = "sold_on"
    }
}

// MARK: - Copy

nonisolated enum TaxReason {
    /// Every review or not-computed reason the server can send, with its fixed text.
    static let all: [String: String] = [
        "acquisition_date_uncertain": "Purchase date unknown (edited holding or no date entered)",
        "etf_category_unverified": "ETF: check its tax category",
        "fmv_unavailable": "Bought before 1 Feb 2018: 31 Jan 2018 price unavailable",
        "fmv_nse_high": "Uses the NSE high on 31 Jan 2018: verify",
        "corporate_action_review": "Split or bonus applied: verify",
        "possible_intraday": "Bought and sold the same day: may be business income",
        "user_entered_date": "Uses the purchase date you entered: verify",
        "stt_on_acquisition_unverified": "Check STT was paid when acquired (bonus or pre-app holding)",
        "ledger_inconsistent": "Your transactions don't add up for this sale: check the quantity held",
    ]

    static func userText(_ code: String) -> String { all[code] ?? "Needs review" }
}

nonisolated enum TaxCopy {
    static let disclaimer = "Informational working from your Nivesh transactions. Not tax advice. Verify with a chartered accountant before filing."
    static let scopeNote = "Listed shares only. Mutual funds are not covered yet."
    static let notApplied = "Set-off of losses, surcharge, cess and your slab rate are not applied."

    static func empty(fy: String) -> String { "No sales recorded in FY \(fy)." }

    /// "Rs 1.25 lakh" from the server's exemption limit for that FY.
    static func shortTermLabel(rate: Int) -> String { "Short-term gains (\(rate)%)" }
    static func longTermLabel(rate: String, limit: Double) -> String { "Long-term gains (\(rate)% above \(XRayCopy.rupees(limit)))" }

    static func signedRupees(_ v: Double) -> String { (v < 0 ? "-" : "") + XRayCopy.rupees(v) }
}

/// Financial-year choices (April to March, IST).
nonisolated enum TaxFY {
    static let firstStartYear = 2018

    private static let ist: Calendar = {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "Asia/Kolkata") ?? .current
        return c
    }()

    static func label(_ startYear: Int) -> String { String(format: "%d-%02d", startYear, (startYear + 1) % 100) }

    static func currentStartYear(_ now: Date = Date()) -> Int {
        let c = ist.dateComponents([.year, .month], from: now)
        return (c.month ?? 4) >= 4 ? (c.year ?? 2018) : (c.year ?? 2019) - 1
    }

    /// Current FY back to 2018-19, newest first.
    static func options(_ now: Date = Date()) -> [String] {
        let current = currentStartYear(now)
        return stride(from: current, through: firstStartYear, by: -1).map(label)
    }

    /// The previous FY from 1 April to 31 July (returns are filed then), otherwise the current one.
    static func defaultFY(_ now: Date = Date()) -> String {
        let c = ist.dateComponents([.month], from: now)
        let current = currentStartYear(now)
        let month = c.month ?? 1
        return label(month >= 4 && month <= 7 ? current - 1 : current)
    }
}
