import Foundation

enum ServerURLPolicy {
    private static let legacyDefaultURLs: Set<String> = [
        "http://192.168.1.122:8000"
    ]

    static func resolve(storedURL: String?, defaultURL: String) -> String {
        guard let storedURL, !storedURL.isEmpty else {
            return defaultURL
        }
        // ATS is enforced (no NSAllowsArbitraryLoads), so a plain-http override can never connect.
        guard !legacyDefaultURLs.contains(storedURL), storedURL.hasPrefix("https://") else {
            return defaultURL
        }
        return storedURL
    }
}
