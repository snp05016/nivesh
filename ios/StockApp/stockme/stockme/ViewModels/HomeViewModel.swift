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
    /// C9: the stored, friendly message of each section's last failed fetch (shown verbatim).
    @Published var sectionErrors: [HomeSectionID: String] = [:]
    /// C9: an entry means the last fetch for that section succeeded, and when.
    @Published var sectionUpdatedAt: [HomeSectionID: Date] = [:]

    /// The sections filled by the one market-dashboard response.
    static let dashboardSections: Set<HomeSectionID> = [.marketPulse, .momentum, .macroAlt, .institutional]

    enum RetryTarget: Equatable { case dashboard, sectors, earnings, indices, morning, none }

    static func retryTarget(for id: HomeSectionID) -> RetryTarget {
        switch id {
        case .marketPulse, .momentum, .macroAlt, .institutional: return .dashboard
        case .sectors:  return .sectors
        case .earnings: return .earnings
        case .indices:  return .indices
        case .morning:  return .morning
        case .top, .portfolio, .watchlist, .news, .youtube: return .none
        }
    }

    private var indicesTimer: Timer?

    /// Re-runs the fetch behind a section. Its stale errors are cleared first so the
    /// card shows the skeleton while the retry is in flight.
    func retry(_ id: HomeSectionID, userId: Int?) {
        let target = Self.retryTarget(for: id)
        for section in HomeSectionID.allCases where Self.retryTarget(for: section) == target {
            sectionErrors[section] = nil
        }
        switch target {
        case .dashboard: fetchDashboard()
        case .sectors:   fetchSectors()
        case .earnings:  fetchEarnings()
        case .indices:   Task { await fetchIndices() }
        case .morning:
            if let userId { Task { await fetchMorningBrief(userId: userId) } }
        case .none: break
        }
    }

    private func markLoaded(_ id: HomeSectionID) {
        sectionErrors[id] = nil
        sectionUpdatedAt[id] = Date()
    }

    private func markFailed(_ id: HomeSectionID, _ error: Error) {
        // A cancelled load (view went away, task replaced) is not a failure.
        if error is CancellationError || (error as? URLError)?.code == .cancelled { return }
        sectionUpdatedAt[id] = nil
        sectionErrors[id] = (error as? NetworkError)?.displayDetail ?? "Couldn't load \(id.title)."
    }

    func fetchDashboard() {
        guard !dashboardLoading else { return }
        dashboardLoading = true
        Task {
            if let result = await NetworkManager.shared.fetchMarketDashboard() {
                dashboard = result
                for id in Self.dashboardSections { markLoaded(id) }
            } else {
                for id in Self.dashboardSections {
                    sectionUpdatedAt[id] = nil
                    sectionErrors[id] = "Couldn't load market data."
                }
            }
            dashboardLoading = false
        }
    }

    func fetchData(userId: Int) async {
        isLoading = true
        defer { isLoading = false }
        // Independent requests run concurrently; one failing no longer blocks the others.
        // An expired token signs out centrally (AuthAwareSession -> AuthManager, IOSCORE-05).
        async let holdings = NetworkManager.shared.getPortfolio(userId: userId)
        async let brief: Void = fetchMorningBrief(userId: userId)
        async let watch: Void = fetchWatchlist(userId: userId)

        do {
            stockCount = try await holdings.count
        } catch {
            print("Home fetch error: \(error)")
        }

        await brief

        do {
            try await watch
        } catch {
            // watchlist unavailable — non-fatal
        }
    }

    func fetchMorningBrief(userId: Int) async {
        do {
            morningBriefData = try await NetworkManager.shared.getMorningSummary(userId: userId)
            markLoaded(.morning)
        } catch {
            morningBriefData = nil
            markFailed(.morning, error)
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
            markLoaded(.indices)
        } catch {
            print("Indices fetch error: \(error)")
            markFailed(.indices, error)
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
            do {
                sectorData = try await NetworkManager.shared.getSectorPerformance()
                markLoaded(.sectors)
            } catch {
                markFailed(.sectors, error)   // keeps any sectors already shown
            }
        }
    }

    func fetchEarnings() {
        Task {
            do {
                earningsEvents = try await NetworkManager.shared.getEarningsCalendar()
                markLoaded(.earnings)
            } catch {
                markFailed(.earnings, error)  // keeps any events already shown
            }
        }
    }

    func stopIndicesTimer() {
        indicesTimer?.invalidate()
        indicesTimer = nil
    }
}
