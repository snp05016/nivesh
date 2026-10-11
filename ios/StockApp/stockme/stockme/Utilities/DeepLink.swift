import Foundation
import Combine

/// Parses `nivesh://` URLs (registered in Info.plist CFBundleURLTypes).
/// Every supported route only opens the stock's action hub — a URL never
/// performs a side effect (such as adding to the watchlist) on its own.
enum DeepLink {
    static let scheme = "nivesh"

    /// `nivesh://analyze/TICKER` or `nivesh://watchlist/add/TICKER` -> `TICKER`.
    static func ticker(from url: URL) -> String? {
        guard url.scheme?.lowercased() == scheme else { return nil }
        let parts = url.path.split(separator: "/").map(String.init)
        switch (url.host?.lowercased(), parts.count) {
        case ("analyze", 1):
            return validTicker(parts[0])
        case ("watchlist", 2) where parts[0].lowercased() == "add":
            return validTicker(parts[1])
        default:
            return nil
        }
    }

    /// Uppercased ticker if it is a known listing, else nil (rejects junk and path tricks).
    static func validTicker(_ raw: String) -> String? {
        let ticker = raw.uppercased()
        return StockDatabase.all.contains(where: { $0.ticker == ticker }) ? ticker : nil
    }
}

/// Holds a ticker requested by a deep link or a push-notification tap until the
/// Home tab consumes it. A stored value (not a fire-and-forget notification) so a
/// cold launch or the biometric lock screen does not drop the request.
final class DeepLinkRouter: ObservableObject {
    static let shared = DeepLinkRouter()
    @Published var pendingTicker: String?
    private init() {}
}
