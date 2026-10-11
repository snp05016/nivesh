import Foundation

/// Field-level validation for the Record Trade sheet. Returns the first problem as a
/// user-facing hint, or nil when the trade can be submitted. The client-side SELL check is
/// UX only; the server remains the authority on oversell.
enum TradeEntryValidator {
    static func validate(hasStock: Bool,
                         type: String,
                         shares: Double,
                         price: Double,
                         date: Date,
                         heldShares: Double?,
                         now: Date = Date(),
                         calendar: Calendar = .current) -> String? {
        guard hasStock else { return "Select a stock first." }
        guard shares > 0 else { return "Enter the number of shares." }
        guard price > 0 else { return "Enter the price per share." }
        if calendar.startOfDay(for: date) > calendar.startOfDay(for: now) {
            return "Trade date can't be in the future."
        }
        if type == "SELL" {
            guard let held = heldShares else { return "You don't hold this stock." }
            if shares > held {
                let heldText = held.formatted(.number.precision(.fractionLength(0...4)).locale(Locale(identifier: "en_IN")))
                return "You hold only \(heldText) shares."
            }
        }
        return nil
    }
}
