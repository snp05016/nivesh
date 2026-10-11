import Foundation
import WidgetKit

/// Writes the signed-in user's portfolio snapshot to the App Group container
/// that the NiveshWidget extension reads. Keys must stay in sync with the
/// widget Provider (NiveshWidget/NiveshWidget.swift), which cannot import this
/// app-only file.
enum WidgetSnapshotStore {
    static let suite = "group.saumypatel.stockme"

    private static let valueKey = "w_portfolio_value"
    private static let pnlKey = "w_pnl"
    private static let updatedAtKey = "w_updated_at"
    private static let topKey = "w_top"

    static func save(holdings: [PortfolioHolding]) {
        guard let defaults = UserDefaults(suiteName: suite) else { return }
        // JSONSerialization raises (not throws) on NaN/Infinity, so keep only finite rows.
        let top = holdings
            .filter { $0.pnl.isFinite && $0.currentValue.isFinite }
            .sorted { $0.currentValue > $1.currentValue }
            .prefix(3)
            .map { ["ticker": $0.stock.ticker, "pnl": $0.pnl] as [String: Any] }
        defaults.set(holdings.reduce(0) { $0 + $1.currentValue }, forKey: valueKey)
        defaults.set(holdings.reduce(0) { $0 + $1.pnl }, forKey: pnlKey)
        defaults.set(Date().timeIntervalSince1970, forKey: updatedAtKey)
        defaults.set(try? JSONSerialization.data(withJSONObject: Array(top)), forKey: topKey)
        WidgetCenter.shared.reloadAllTimelines()
    }

    /// Called on logout so the next user never sees the previous user's holdings.
    static func clear() {
        guard let defaults = UserDefaults(suiteName: suite) else { return }
        for key in [valueKey, pnlKey, updatedAtKey, topKey] {
            defaults.removeObject(forKey: key)
        }
        WidgetCenter.shared.reloadAllTimelines()
    }
}
