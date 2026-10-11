import Foundation

struct StockEntry: Identifiable, Equatable {
    var id: String { ticker }
    let ticker: String
    let companyName: String
    let exchange: String
    let sector: String
}

enum StockDatabase {
    /// Decoded once from the bundled Resources/nse_bse_symbols.json, a byte copy of
    /// backend/data/nse_bse_symbols.json (backend/scripts/refresh_nse_symbols.py
    /// writes both), so iOS search and the backend share one stock universe.
    static let all: [StockEntry] = load()

    private static func load() -> [StockEntry] {
        guard let url = Bundle.main.url(forResource: "nse_bse_symbols", withExtension: "json")
                ?? Bundle.main.url(forResource: "nse_bse_symbols", withExtension: "json", subdirectory: "Resources"),
              let data = try? Data(contentsOf: url),
              let rows = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] else {
            print("[StockDatabase] nse_bse_symbols.json missing or unreadable; stock list is empty")
            return []
        }
        return rows.compactMap { row in
            guard let ticker = row["ticker"] as? String,
                  let name = row["name"] as? String,
                  let sector = row["sector"] as? String else { return nil }
            return StockEntry(ticker: ticker, companyName: name,
                              exchange: row["exchange"] as? String ?? "NSE", sector: sector)
        }
    }

    static func search(_ query: String) -> [StockEntry] {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        guard !q.isEmpty else { return [] }
        let prefix = all.filter {
            $0.ticker.lowercased().hasPrefix(q) || $0.companyName.lowercased().hasPrefix(q)
        }
        let contains = all.filter {
            !($0.ticker.lowercased().hasPrefix(q) || $0.companyName.lowercased().hasPrefix(q)) &&
            ($0.ticker.lowercased().contains(q) || $0.companyName.lowercased().contains(q) || $0.sector.lowercased().contains(q))
        }
        return Array((prefix + contains).prefix(50))
    }
}