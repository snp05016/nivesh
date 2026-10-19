// Models/HoldingDetailModels.swift
// Domain: holding detail (C11, GET /api/v1/me/holdings/{ticker}) and the
// portfolio return card (I30, GET /portfolio/benchmark). spec_money 3.2-3.3.

import Foundation

// MARK: - Holding detail

nonisolated struct HoldingDetailResponse: Decodable {
    let ticker: String
    let name: String?
    let assetClass: String
    let position: HoldingPosition
    let returns: HoldingReturns
    let transactions: [HoldingLedgerTransaction]
    let dividends: HoldingDividends?
    let notes: String?
    let targetPrice: Double?
    let journal: [HoldingJournalExcerpt]
    let stockReportAvailable: Bool

    var isEquity: Bool { assetClass == "EQ" }

    enum CodingKeys: String, CodingKey {
        case ticker, name, position, returns, transactions, dividends, notes, journal
        case assetClass = "asset_class"
        case targetPrice = "target_price"
        case stockReportAvailable = "stock_report_available"
    }
}

nonisolated struct HoldingPosition: Decodable {
    let quantity: Double
    let avgCost: Double
    let investedInr: Double
    let price: Double?
    /// live | stale | nav | unavailable (unavailable: price = avg cost, value = invested, P&L 0).
    let priceStatus: String
    let priceAsOf: String?
    let valueInr: Double
    let pnlInr: Double
    let pnlPct: Double?

    enum CodingKeys: String, CodingKey {
        case quantity, price
        case avgCost = "avg_cost"
        case investedInr = "invested_inr"
        case priceStatus = "price_status"
        case priceAsOf = "price_as_of"
        case valueInr = "value_inr"
        case pnlInr = "pnl_inr"
        case pnlPct = "pnl_pct"
    }
}

extension HoldingPosition {
    /// The portfolio list row, shown while the detail loads or when offline.
    @MainActor init(seed h: PortfolioHolding) {
        self.init(quantity: h.shares, avgCost: h.buyPrice, investedInr: h.investedValue,
                  price: h.priceAvailable ? h.stock.currentPrice : nil,
                  priceStatus: h.priceStatus, priceAsOf: h.priceAsOf,
                  valueInr: h.currentValue, pnlInr: h.pnl, pnlPct: h.pnlPercent)
    }
}

nonisolated struct HoldingReturns: Decodable {
    /// annualized_xirr | absolute (under 365 days, never annualised) | unavailable
    let basis: String
    let valuePct: Double?
    let niftySameFlowsPct: Double?
    let niftyAvailable: Bool
    let since: String?
    let periodDays: Int?
    let approximateStart: Bool
    /// nil | user_entered_date | since_edit
    let startReason: String?
    /// price_unavailable | start_date_unknown | edited_position | imported_without_history | nil
    let unavailableReason: String?
    let benchmarkLabel: String

    enum CodingKeys: String, CodingKey {
        case basis, since
        case valuePct = "value_pct"
        case niftySameFlowsPct = "nifty_same_flows_pct"
        case niftyAvailable = "nifty_available"
        case periodDays = "period_days"
        case approximateStart = "approximate_start"
        case startReason = "start_reason"
        case unavailableReason = "unavailable_reason"
        case benchmarkLabel = "benchmark_label"
    }
}

nonisolated struct HoldingLedgerTransaction: Decodable, Identifiable {
    let id: Int
    let type: String
    let quantity: Double
    let price: Double
    let fees: Double
    let date: String?
    let imported: Bool
    let notes: String?
}

nonisolated struct HoldingDividends: Decodable {
    let totalInr: Double
    let count: Int

    enum CodingKeys: String, CodingKey {
        case count
        case totalInr = "total_inr"
    }
}

nonisolated struct HoldingJournalExcerpt: Decodable, Identifiable {
    let id: Int
    let action: String
    let createdAt: String?
    let reasonExcerpt: String

    enum CodingKeys: String, CodingKey {
        case id, action
        case createdAt = "created_at"
        case reasonExcerpt = "reason_excerpt"
    }
}

// MARK: - Portfolio return (GET /portfolio/benchmark)

/// Every key optional: older servers send only the MATH-04 keys. Independent of BenchmarkData.
nonisolated struct PortfolioReturnDTO: Decodable {
    let portfolioCagrPct: Double?
    let niftyCagrPct: Double?
    let returnBasis: String?
    let periodDays: Int?
    let earliestHoldingDate: String?
    let niftyAvailable: Bool?
    let unpricedTickers: [String]?
    let excludedTickers: [ExcludedTicker]?
    let benchmarkLabel: String?
    let approximateStart: Bool?
    let coveragePct: Double?
    let fundsExcluded: Bool?
    /// insufficient_history | no_dated_holdings | nil
    let unavailableReason: String?

    nonisolated struct ExcludedTicker: Decodable, Equatable {
        let ticker: String
        let reason: String
    }

    enum CodingKeys: String, CodingKey {
        case portfolioCagrPct = "portfolio_cagr_pct"
        case niftyCagrPct = "nifty_cagr_pct"
        case returnBasis = "return_basis"
        case periodDays = "period_days"
        case earliestHoldingDate = "earliest_holding_date"
        case niftyAvailable = "nifty_available"
        case unpricedTickers = "unpriced_tickers"
        case excludedTickers = "excluded_tickers"
        case benchmarkLabel = "benchmark_label"
        case approximateStart = "approximate_start"
        case coveragePct = "coverage_pct"
        case fundsExcluded = "funds_excluded"
        case unavailableReason = "unavailable_reason"
    }
}

// MARK: - Copy (spec 3.2 / 3.3 wording; fixed templates, no advice)

/// The text lines a return card shows. `headline` is the return or the unavailable message.
nonisolated struct ReturnCopy: Equatable {
    var headline: String
    var nifty: String? = nil
    var notes: [String] = []
}

nonisolated enum MoneyReturnCopy {
    static let mask = "••••"

    private static let displayDay: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.calendar = Calendar(identifier: .gregorian)
        f.timeZone = WireDate.dayFormatter.timeZone
        f.dateFormat = "d MMM yyyy"
        return f
    }()

    /// "2024-02-01" -> "1 Feb 2024"; nil when absent or unparsable.
    static func day(_ wire: String?) -> String? {
        guard let wire, let d = WireDate.day(wire) else { return nil }
        return displayDay.string(from: d)
    }

    /// One decimal, "11.3%"; `signed` adds "+" (absolute returns). Masked when values are hidden.
    static func pct(_ v: Double, signed: Bool = false, masked: Bool = false) -> String {
        if masked { return mask }
        var r = (v * 10).rounded() / 10
        if r == 0 { r = 0 }  // no "-0.0%"
        return (signed && r >= 0 ? "+" : "") + String(format: "%.1f%%", r)
    }

    static func holdingUnavailable(_ reason: String?) -> String? {
        switch reason {
        case "start_date_unknown": return "Return unavailable: add this holding's purchase date to see it."
        case "edited_position": return "Return unavailable: this holding was edited, so its purchase history is incomplete."
        case "imported_without_history": return "Return unavailable: imported as a balance without purchase history."
        case "price_unavailable": return "Return unavailable: no current price."
        default: return nil
        }
    }

    /// The holding return card, or nil when there is nothing to say (no reason and no figure).
    static func holding(_ r: HoldingReturns, masked: Bool = false) -> ReturnCopy? {
        guard r.basis != "unavailable", let value = r.valuePct else {
            return holdingUnavailable(r.unavailableReason).map { ReturnCopy(headline: $0) }
        }
        let annualised = r.basis == "annualized_xirr"
        let edited = r.startReason == "since_edit"
        let since = day(r.since)
        var copy: ReturnCopy
        if annualised {
            var lead = "Your return (XIRR)"
            if edited, let since { lead += " since you edited this holding on \(since)" }
            copy = ReturnCopy(headline: "\(lead): \(pct(value, masked: masked))")
            if r.niftyAvailable, let n = r.niftySameFlowsPct {
                copy.nifty = "Same rupees in the Nifty 50: \(pct(n, masked: masked)) a year"
            }
        } else if edited, let since {
            copy = ReturnCopy(headline: "Return since you edited this holding on \(since): \(pct(value, signed: true, masked: masked))",
                              notes: ["Not annualised: under 12 months."])
        } else {
            let lead = since.map { "Return since \($0)" } ?? "Return"
            copy = ReturnCopy(headline: "\(lead): \(pct(value, signed: true, masked: masked)) (under 12 months, not annualised)")
        }
        if !annualised, r.niftyAvailable, let n = r.niftySameFlowsPct {
            copy.nifty = "Nifty 50, same cash flows: \(pct(n, signed: true, masked: masked))"
        }
        if r.startReason == "user_entered_date" { copy.notes.append("Start date is the purchase date you entered.") }
        if copy.nifty != nil { copy.notes.append(r.benchmarkLabel) }
        return copy
    }

    static func excludedReason(_ reason: String) -> String? {
        switch reason {
        case "price_unavailable": return "no current price"
        case "start_date_unknown": return "purchase date unknown"
        case "edited_position": return "edited, purchase history incomplete"
        case "imported_without_history": return "imported without purchase history"
        default: return nil
        }
    }

    /// The portfolio return card. Always returns copy: unavailable bodies get the unavailable message.
    static func portfolio(_ d: PortfolioReturnDTO, masked: Bool = false) -> ReturnCopy {
        var copy: ReturnCopy
        let niftyOK = (d.niftyAvailable ?? (d.niftyCagrPct != nil)) && d.niftyCagrPct != nil
        let since = day(d.earliestHoldingDate)
        if d.returnBasis == "unavailable" || d.returnBasis == nil || d.portfolioCagrPct == nil {
            copy = ReturnCopy(headline: "Add purchase dates to your holdings to see your yearly return.")
        } else if d.returnBasis == "annualized_xirr", let v = d.portfolioCagrPct {
            copy = ReturnCopy(headline: "Your yearly return (XIRR): \(pct(v, masked: masked))")
            if niftyOK, let n = d.niftyCagrPct {
                copy.nifty = "Same rupees in the Nifty 50: \(pct(n, masked: masked)) a year"
            }
            let sinceText = since.map { "Since \($0)." }
            copy.notes.append([niftyOK ? "Nifty 50 price index, excludes dividends." : nil, sinceText]
                .compactMap { $0 }.joined(separator: " "))
        } else {
            let v = d.portfolioCagrPct ?? 0
            copy = ReturnCopy(headline: (since.map { "Your return since \($0)" } ?? "Your return") + ": \(pct(v, signed: true, masked: masked))")
            if niftyOK, let n = d.niftyCagrPct {
                copy.nifty = "Nifty 50, same cash flows: \(pct(n, signed: true, masked: masked))"
            }
            copy.notes.append("Not annualised: under 12 months.")
            if niftyOK { copy.notes.append(d.benchmarkLabel ?? "Nifty 50 price index (excludes dividends)") }
        }
        copy.notes.removeAll { $0.isEmpty }
        if let c = d.coveragePct, c.rounded() < 100, d.returnBasis != "unavailable" {
            copy.notes.append("Covers holdings worth \(Int(c.rounded()))% of your stocks.")
        }
        let excluded = d.excludedTickers ?? []
        if !excluded.isEmpty {
            let shown = excluded.prefix(5).map { e in excludedReason(e.reason).map { "\(e.ticker) (\($0))" } ?? e.ticker }
            let more = excluded.count > 5 ? " and \(excluded.count - 5) more" : ""
            copy.notes.append("Not included: \(shown.joined(separator: ", "))\(more)")
        }
        if d.approximateStart == true { copy.notes.append("Some start dates are approximate.") }
        if d.fundsExcluded == true { copy.notes.append("Mutual funds aren't included yet.") }
        return copy
    }
}
