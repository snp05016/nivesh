import Foundation

enum ServerURLPolicy {
    private static let legacyDefaultURLs: Set<String> = [
        "http://192.168.1.122:8000"
    ]

    static func resolve(storedURL: String?, defaultURL: String) -> String {
        guard let storedURL, !storedURL.isEmpty else {
            return defaultURL
        }
        guard !legacyDefaultURLs.contains(storedURL) else {
            return defaultURL
        }
        return storedURL
    }
}
