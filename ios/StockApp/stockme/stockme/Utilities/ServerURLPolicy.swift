import Foundation

enum ServerURLPolicy {
    /// IOSCORE-19: a stored override is honoured only if it is a well-formed https URL
    /// with a host. ATS is enforced (no NSAllowsArbitraryLoads), so plain http, the old
    /// LAN default, other schemes and malformed strings all fall back to `defaultURL`.
    static func resolve(storedURL: String?, defaultURL: String) -> String {
        guard let storedURL, !storedURL.isEmpty,
              let components = URLComponents(string: storedURL),
              components.scheme?.lowercased() == "https",
              let host = components.host, !host.isEmpty else {
            return defaultURL
        }
        return storedURL
    }
}
