import Foundation

/// Field checks for money-entry forms that TradeEntryValidator does not cover (IOSUI-22).
enum InputValidation {
    /// The problem with a price-alert target as a user-facing hint, or nil when it can be saved.
    /// With a known current price the target must sit on the chosen side of it; otherwise the
    /// alert would fire on the next check (or never, if the user meant the other side).
    static func alertTargetError(target: Double?, direction: String, current: Double?) -> String? {
        guard let target, target.isFinite, target > 0 else { return "Enter a valid target price." }
        guard let current, current > 0 else { return nil }
        if direction == "above" && target <= current {
            return "Target must be above the current price \(IndianFormatter.price(current))."
        }
        if direction == "below" && target >= current {
            return "Target must be below the current price \(IndianFormatter.price(current))."
        }
        return nil
    }
}
