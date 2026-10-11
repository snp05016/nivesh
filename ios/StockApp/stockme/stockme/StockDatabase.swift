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

    /// Lowercased ticker/name/sector, computed once so a keystroke does not
    /// re-lowercase ~3.7k entries several times over.
    private static let index: [(entry: StockEntry, ticker: String, name: String, sector: String)] =
        all.map { ($0, $0.ticker.lowercased(), $0.companyName.lowercased(), $0.sector.lowercased()) }

    static func search(_ query: String) -> [StockEntry] {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        guard !q.isEmpty else { return [] }
        var prefix: [StockEntry] = []
        var contains: [StockEntry] = []
        for row in index {
            if row.ticker.hasPrefix(q) || row.name.hasPrefix(q) {
                prefix.append(row.entry)
            } else if row.ticker.contains(q) || row.name.contains(q) || row.sector.contains(q) {
                contains.append(row.entry)
            }
        }
        return Array((prefix + contains).prefix(50))
    }
}