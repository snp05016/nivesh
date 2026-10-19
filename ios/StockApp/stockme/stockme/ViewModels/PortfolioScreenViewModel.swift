import SwiftUI
import Combine

class WatchlistTagsManager: ObservableObject {
    @Published var tags: [String: [String]] = [:] {
        didSet {
            if let encoded = try? JSONEncoder().encode(tags) {
                UserDefaults.standard.set(encoded, forKey: "watchlistTags")
            }
        }
    }
    
    init() {
        if let data = UserDefaults.standard.data(forKey: "watchlistTags"),
           let decoded = try? JSONDecoder().decode([String: [String]].self, from: data) {
            tags = decoded
        }
    }

    func addTag(_ tag: String, to ticker: String) {
        let cleanTag = tag.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanTag.isEmpty else { return }
        var current = tags[ticker] ?? []
        if !current.contains(cleanTag) {
            current.append(cleanTag)
            tags[ticker] = current
        }
    }

    func removeTag(_ tag: String, from ticker: String) {
        var current = tags[ticker] ?? []
        current.removeAll { $0 == tag }
        if current.isEmpty {
            tags.removeValue(forKey: ticker)
        } else {
            tags[ticker] = current
        }
    }

    var allUniqueTags: [String] {
        let all = tags.values.flatMap { $0 }
        return Array(Set(all)).sorted()
    }
}

@MainActor
class PortfolioScreenViewModel: ObservableObject {
    @Published var holdings: [PortfolioHolding] = []
    @Published var totalValue: Double = 0
    @Published var investedValue: Double = 0
    @Published var todayPnL: Double = 0
    @Published var isLoading = false

    @Published var watchlistItems: [WatchlistItem] = []
    @Published var watchlistLoading = false
    @Published var watchlistError: String? = nil
    /// IOSCORE-06: a failed load is shown as an error, never as an empty portfolio or Rs 0.
    @Published var loadError: String? = nil
    /// True once holdings loaded successfully at least once; until then totals are unknown, not zero.
    @Published private(set) var hasLoaded = false
    @Published var watchlistLoadError: String? = nil

    /// A failed refresh keeps the last loaded holdings and totals.
    func fetchData(userId: Int) async {
        isLoading = true
        do {
            let data = try await NetworkManager.shared.getPortfolio(userId: userId)
            holdings = data
            totalValue = holdings.reduce(0) { $0 + $1.currentValue }
            investedValue = holdings.reduce(0) { $0 + $1.investedValue }
            todayPnL = holdings.reduce(0) { $0 + $1.dayPnL }
            loadError = nil
            hasLoaded = true
        } catch {
            loadError = error.localizedDescription
            GlobalErrorDiagnoser.shared.trackNetworkError(error, endpoint: "/portfolio/{user_id}")
        }
        isLoading = false
    }

    func fetchWatchlist(userId: Int) async {
        watchlistLoading = true
        do {
            watchlistItems = try await NetworkManager.shared.getWatchlist(userId: userId)
            watchlistLoadError = nil
        } catch {
            watchlistLoadError = error.localizedDescription
            GlobalErrorDiagnoser.shared.trackNetworkError(error, endpoint: "/watchlist/{user_id}")
        }
        watchlistLoading = false
    }

    /// Optimistic: the row disappears at once and comes back if the DELETE fails.
    func removeFromWatchlist(ticker: String, userId: Int) async {
        let old = watchlistItems
        watchlistItems.removeAll { $0.ticker == ticker }
        do {
            try await NetworkManager.shared.removeFromWatchlist(userId: userId, ticker: ticker)
            NotificationCenter.default.post(name: .watchlistUpdated, object: nil)
        } catch {
            watchlistItems = old
            watchlistError = "\(ticker) is still on your watchlist. Check your connection and try again."
        }
    }

    func addHolding(userId: Int, ticker: String, companyName: String, shares: Double, buyPrice: Double, purchaseDate: Date, notes: String, targetPrice: Double?, transactionType: String = "BUY") async throws {
        try await NetworkManager.shared.addHolding(userId: userId, ticker: ticker, companyName: companyName, shares: shares, buyPrice: buyPrice, purchaseDate: purchaseDate, notes: notes, targetPrice: targetPrice, transactionType: transactionType)
        await fetchData(userId: userId)
    }

    func removeHolding(ticker: String, userId: Int) async throws {
        try await NetworkManager.shared.removeHolding(userId: userId, ticker: ticker)
        await fetchData(userId: userId)
    }

    func updateHolding(userId: Int, ticker: String, shares: Double, buyPrice: Double) async throws {
        try await NetworkManager.shared.updateHolding(userId: userId, ticker: ticker, shares: shares, buyPrice: buyPrice)
        await fetchData(userId: userId)
    }
}
