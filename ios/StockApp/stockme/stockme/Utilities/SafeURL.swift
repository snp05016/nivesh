import UIKit

/// IOSCORE-33: links from harvested third-party content (news, videos, governance
/// sources) open only as https web pages, never tel:, sms:, javascript: or app schemes.
enum SafeURL {
    /// The https URL in `raw` (trimmed), or nil for any other scheme, a missing host
    /// or a malformed string. No host allow-list: news and video sources are open-ended.
    nonisolated static func web(_ raw: String?) -> URL? {
        guard let trimmed = raw?.trimmingCharacters(in: .whitespacesAndNewlines),
              let components = URLComponents(string: trimmed),
              components.scheme?.lowercased() == "https",
              let host = components.host, !host.isEmpty else { return nil }
        return components.url
    }

    /// Opens `raw` externally when it passes `web(_:)`; otherwise does nothing.
    @MainActor static func open(_ raw: String?) {
        if let url = web(raw) { UIApplication.shared.open(url) }
    }
}
