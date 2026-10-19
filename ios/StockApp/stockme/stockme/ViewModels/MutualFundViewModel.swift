import SwiftUI
import Combine

/// Drives MutualFundDiscoveryView over the real AMFI universe. The server pages, filters and
/// sorts (by name; there is no performance ranking); the view model only tracks the query,
/// the rows loaded so far and the load states.
@MainActor
class MutualFundViewModel: ObservableObject {
    @Published private(set) var query = MutualFundQuery()
    @Published private(set) var funds: [MutualFundDTO] = []
    @Published private(set) var totalCount: Int? = nil
    @Published private(set) var filters: MutualFundFilters? = nil
    @Published private(set) var isLoading: Bool = false
    @Published private(set) var isLoadingMore: Bool = false
    @Published private(set) var loadMoreFailed: Bool = false
    @Published private(set) var errorMessage: String? = nil
    @Published private(set) var isOffline: Bool = false

    private var generation = 0
    private var searchTask: Task<Void, Never>? = nil

    var canLoadMore: Bool { MutualFundQuery.canLoadMore(loaded: funds.count, total: totalCount) }

    var hasActiveFilters: Bool { query != MutualFundQuery(limit: query.limit) }

    /// Categories from /filters, else the distinct categories of the rows loaded so far.
    var availableCategories: [String] {
        if let filters { return filters.sortedCategories }
        return Array(Set(funds.map { $0.category })).sorted()
    }

    func subCategories(of category: String) -> [String] {
        filters?.categories[category] ?? []
    }

    // MARK: Query changes

    func setPlan(_ plan: MutualFundPlanFilter) {
        guard plan != query.plan else { return }
        query.plan = plan
        Task { await reload() }
    }

    func setOption(_ option: MutualFundOptionFilter) {
        guard option != query.option else { return }
        query.option = option
        Task { await reload() }
    }

    func setCategory(_ category: String?, subCategory: String? = nil) {
        query.category = category
        query.subCategory = subCategory
        Task { await reload() }
    }

    func setAMC(_ amc: String?) {
        query.amc = amc
        Task { await reload() }
    }

    /// Search reloads 350 ms after the last keystroke; a newer keystroke cancels the pending reload.
    func setSearch(_ text: String) {
        guard text != query.search else { return }
        query.search = text
        searchTask?.cancel()
        searchTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 350_000_000)
            guard !Task.isCancelled else { return }
            await self?.reload()
        }
    }

    func clearFilters() {
        searchTask?.cancel()
        query = MutualFundQuery(limit: query.limit)
        Task { await reload() }
    }

    // MARK: Loading

    /// First page for the current query. Rows from a different query are dropped on failure so
    /// stale funds never sit under new filters.
    func reload() async {
        generation += 1
        let mine = generation
        query.offset = 0
        isLoading = true
        isLoadingMore = false
        loadMoreFailed = false
        errorMessage = nil
        isOffline = false
        do {
            let page = try await NetworkManager.shared.fetchMutualFunds(query: query)
            guard mine == generation else { return }
            funds = page.funds
            totalCount = page.totalCount
        } catch {
            guard mine == generation, !Self.isCancellation(error) else { return }
            funds = []
            totalCount = nil
            applyFailure(error)
        }
        isLoading = false
    }

    /// Appends the next page at offset == rows held; a failure keeps the rows and shows a retry footer.
    func loadMore() async {
        guard canLoadMore, !isLoading, !isLoadingMore else { return }
        let mine = generation
        isLoadingMore = true
        loadMoreFailed = false
        var next = query
        next.offset = funds.count
        do {
            let page = try await NetworkManager.shared.fetchMutualFunds(query: next)
            guard mine == generation else { return }
            let known = Set(funds.map { $0.id })
            funds.append(contentsOf: page.funds.filter { !known.contains($0.id) })
            totalCount = page.totalCount ?? totalCount
        } catch {
            guard mine == generation, !Self.isCancellation(error) else { return }
            loadMoreFailed = true
        }
        isLoadingMore = false
    }

    /// Leaves `filters` nil on failure: the fund-house menu hides and categories come from loaded rows.
    func loadFilters() async {
        filters = try? await NetworkManager.shared.fetchMutualFundFilters()
    }

    private func applyFailure(_ error: Error) {
        if case NetworkError.fetchFailed(_, let status, _) = error, status == -1 {
            isOffline = true
            errorMessage = "You're offline. Reconnect and try again."
        } else {
            errorMessage = "Couldn't load mutual funds."
        }
    }

    private static func isCancellation(_ error: Error) -> Bool {
        error is CancellationError || (error as? URLError)?.code == .cancelled
    }
}

/// Drives MutualFundDetailView — loads full fund detail and NAV history for the
/// selected chart range independently so a partial failure doesn't block the
/// rest of the screen.
@MainActor
class MutualFundDetailViewModel: ObservableObject {
    @Published var fund: MutualFundDTO
    @Published var navHistory: [MutualFundNAVPoint] = []
    @Published var selectedRange: MutualFundNAVRange = .oneYear
    @Published var isLoadingNAV: Bool = false

    let fundId: Int
    /// Backend paths key off scheme_code (string), not the row id — nil when
    /// the seed fund has no scheme_code, in which case detail/history
    /// calls are skipped and the seed data is shown as-is.
    private let schemeCode: String?

    /// ISO date the backend first recorded a NAV for this fund, if it has.
    var historyStart: String? { fund.historyStart }

    init(seed: MutualFundDTO) {
        self.fund = seed
        self.fundId = seed.id
        self.schemeCode = seed.schemeCode
    }

    func loadAll() {
        Task { await refreshDetail() }
        Task { await loadNAVHistory() }
    }

    func refreshDetail() async {
        guard let schemeCode else { return }
        if let detail = try? await NetworkManager.shared.getMutualFundDetail(schemeCode: schemeCode) {
            fund = detail
        }
    }

    func loadNAVHistory() async {
        guard let schemeCode else { return }
        isLoadingNAV = true
        navHistory = (try? await NetworkManager.shared.getMutualFundNAVHistory(schemeCode: schemeCode, range: selectedRange)) ?? []
        isLoadingNAV = false
    }

    func changeRange(_ range: MutualFundNAVRange) {
        guard range != selectedRange else { return }
        selectedRange = range
        Task { await loadNAVHistory() }
    }
}
