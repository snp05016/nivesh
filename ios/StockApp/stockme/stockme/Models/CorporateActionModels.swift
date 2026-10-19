import Foundation

// MARK: - Corporate actions (splits and bonus issues)
//
// Backed by /api/v1/portfolio/corporate-actions (backend/routers/corporate_actions.py,
// flag data_corp_actions_confirm). Error bodies are {"detail": {"code": ...}}.

/// One proposal for one portfolio group: the user decides whether a split or bonus is already in the quantity.
struct CorporateActionItem: Codable, Identifiable, Equatable {
    let id: Int
    let ticker: String
    let groupId: Int?
    let groupName: String?
    let actionLabel: String
    let ratio: Double
    let ratioText: String
    /// yyyy-MM-dd
    let exDate: String
    /// pending | applied | dismissed
    let status: String
    let sharesBefore: Double?
    let sharesAfter: Double?
    let nseConfirmed: Bool?
    let source: String
    let decidedAt: String?
    let undoUntil: String?

    enum CodingKeys: String, CodingKey {
        case id, ticker, ratio, status, source
        case groupId = "group_id"
        case groupName = "group_name"
        case actionLabel = "action_label"
        case ratioText = "ratio_text"
        case exDate = "ex_date"
        case sharesBefore = "shares_before"
        case sharesAfter = "shares_after"
        case nseConfirmed = "nse_confirmed"
        case decidedAt = "decided_at"
        case undoUntil = "undo_until"
    }

    var isPending: Bool { status == "pending" }

    /// Applied or dismissed, and `undo_until` is today (Asia/Kolkata calendar day) or later.
    func canUndo(today: Date = Date()) -> Bool {
        guard status == "applied" || status == "dismissed",
              let until = CorporateActionDates.parse(undoUntil) else { return false }
        return CorporateActionDates.istDay(until) >= CorporateActionDates.istDay(today)
    }
}

struct CorporateActionList: Codable, Equatable {
    let items: [CorporateActionItem]
}

struct CorporateActionHolding: Codable, Equatable {
    let ticker: String
    let shares: Double
    let avgPrice: Double

    enum CodingKeys: String, CodingKey {
        case ticker, shares
        case avgPrice = "avg_price"
    }
}

/// Response of apply, dismiss and undo. `holding` is nil when the ledger did not change.
struct CorporateActionMutationResponse: Codable, Equatable {
    let item: CorporateActionItem
    let holding: CorporateActionHolding?
}

enum CorporateActionMutation: String {
    case apply, dismiss, undo
}

/// Date helpers for the API's ISO strings. Timestamps without a zone are UTC (the backend stores naive UTC).
enum CorporateActionDates {
    private static let ist = TimeZone(identifier: "Asia/Kolkata") ?? TimeZone(secondsFromGMT: 19_800)!

    private static var istCalendar: Calendar {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = ist
        return cal
    }

    private static func formatter(_ format: String, zone: TimeZone) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = zone
        f.dateFormat = format
        return f
    }

    /// "2026-04-01", "2026-04-01T10:30:00" or "2026-04-01T10:30:00.123456+00:00" -> Date (date-only = IST midnight).
    static func parse(_ raw: String?) -> Date? {
        guard let raw, !raw.isEmpty else { return nil }
        if raw.count == 10 { return formatter("yyyy-MM-dd", zone: ist).date(from: raw) }
        let utc = TimeZone(secondsFromGMT: 0)!
        let trimmed = String(raw.prefix(19))
        return formatter("yyyy-MM-dd'T'HH:mm:ss", zone: utc).date(from: trimmed)
    }

    /// Start of the IST calendar day containing `date`.
    static func istDay(_ date: Date) -> Date {
        istCalendar.startOfDay(for: date)
    }

    /// "9 Apr" in IST.
    static func dayMonth(_ raw: String?) -> String? {
        guard let date = parse(raw) else { return nil }
        let f = formatter("d MMM", zone: ist)
        f.locale = Locale(identifier: "en_IN")
        return f.string(from: date)
    }
}
