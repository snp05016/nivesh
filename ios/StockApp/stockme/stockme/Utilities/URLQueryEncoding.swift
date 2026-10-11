import Foundation

extension CharacterSet {
    /// `.urlQueryAllowed` minus the characters that delimit query parameters.
    /// `.urlQueryAllowed` keeps `&`, `=` and `+`, so a ticker like M&M would split the query.
    nonisolated static let urlQueryValueAllowed: CharacterSet = {
        var set = CharacterSet.urlQueryAllowed
        set.remove(charactersIn: "&=+?#/")
        return set
    }()
}

extension String {
    /// Percent-encoded for use as a single query-string value (`M&M` -> `M%26M`).
    nonisolated var urlQueryValue: String {
        addingPercentEncoding(withAllowedCharacters: .urlQueryValueAllowed) ?? self
    }
}
