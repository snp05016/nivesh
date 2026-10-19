import SwiftUI
import Combine

@MainActor
class HomeViewModel: ObservableObject {

    @Published var stockCount: Int = 0
    @Published var watchlist: [Stock] = []
    @Published var indices: [LiveMarketIndex] = []
    @Published var indicesLoading = false
    @Published var indicesFetchFailed = false
    @Published var morningBriefData: MorningSummaryResponse? = nil
    @Published var sectorData: [SectorPerformance] = []
    @Published var earningsEvents: [EarningsEvent] = []
    @Published var isLoading = false
    @Published var dashboard: MarketDashboardResponse? = nil
    @Published var dashboardLoading = false

    private var indicesTimer: Timer?

    func fetchDashboard() {
        guard !dashboardLoading else { return }
        dashboardLoading = true
        Task {
            dashboard = await NetworkManager.shared.fetchMarketDashboard()
            dashboardLoading = false
        }
    }

    func fetchData(userId: Int) async {
        isLoading = true
        defer { isLoading = false }
        // Independent requests run concurrently; one failing no longer blocks the others.
        // An expired token signs out centrally (AuthAwareSession -> AuthManager, IOSCORE-05).
        async let holdings = NetworkManager.shared.getPortfolio(userId: userId)
        async let brief = NetworkManager.shared.getMorningSummary(userId: userId)
        async let watch: Void = fetchWatchlist(userId: userId)

        do {
            stockCount = try await holdings.count
        } catch {
            print("Home fetch error: \(error)")
        }

        do {
            morningBriefData = try await brief
        } catch {
            morningBriefData = nil
        }

        do {
            try await watch
        } catch {
            // watchlist unavailable — non-fatal
        }
    }

    func fetchWatchlist(userId: Int) async throws {
        let watchlistItems = try await NetworkManager.shared.getWatchlist(userId: userId)
        watchlist = watchlistItems.map { item in
            Stock(
                ticker: item.ticker,
                companyName: item.companyName,
                exchange: item.exchange,
                currentPrice: item.currentPrice,
                changePercent: item.dayChangePct,
                signal: nil
            )
        }
    }

    /// Awaitable version — safe to call from .task {} and .refreshable {}
    @MainActor
    func fetchIndices() async {
        indicesLoading = indices.isEmpty
        do {
            let resp = try await NetworkManager.shared.getMarketIndices()
            indices = resp.indices
            indicesFetchFailed = false
        } catch {
            print("Indices fetch error: \(error)")
            indicesFetchFailed = indices.isEmpty   // only mark failed if we have no data at all
        }
        indicesLoading = false
    }

    func startIndicesTimer() {
        indicesTimer?.invalidate()
        indicesTimer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                await self?.fetchIndices()
            }
        }
    }

    func fetchSectors() {
        Task {
            sectorData = (try? await NetworkManager.shared.getSectorPerformance()) ?? []
        }
    }

    func fetchEarnings() {
        Task {
            earningsEvents = await NetworkManager.shared.getEarningsCalendar()
        }
    }

    func stopIndicesTimer() {
        indicesTimer?.invalidate()
        indicesTimer = nil
    }
}
