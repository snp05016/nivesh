import SwiftUI
import Combine

/// Sort options for the mutual fund discovery list.
enum MutualFundSortOption: String, CaseIterable, Identifiable {
    case returns1y = "1Y Returns"
    case returns3y = "3Y Returns"
    case aum = "AUM"
    case expenseRatio = "Expense Ratio"
    case name = "Name"

    var id: String { rawValue }
}

/// Drives MutualFundDiscoveryView — fetches the fund universe and applies
/// search, category, AUM, returns, and risk (rating) filters client-side,
/// mirroring IPOListViewModel's fetch/error/loading shape.
@MainActor
class MutualFundViewModel: ObservableObject {
    @Published var searchQuery: String = ""
    @Published var selectedCategory: String? = nil
    @Published var selectedRiskLevel: MutualFundRiskLevel? = nil
    @Published var minAumCr: Double = 0
    @Published var minReturns1y: Double = -100
    @Published var sortOption: MutualFundSortOption = .returns1y

    @Published var allFunds: [MutualFundDTO] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil

    var filteredFunds: [MutualFundDTO] {
        var result = allFunds

        if let category = selectedCategory, !category.isEmpty {
            result = result.filter { $0.category == category }
        }

        if let riskLevel = selectedRiskLevel {
            result = result.filter { $0.parsedRiskLevel == riskLevel }
        }

        if minAumCr > 0 {
            result = result.filter { ($0.aumCr ?? 0) >= minAumCr }
        }

        if minReturns1y > -100 {
            result = result.filter { ($0.returns1y ?? -Double.infinity) >= minReturns1y }
        }

        if !searchQuery.isEmpty {
            result = result.filter {
                $0.fundName.localizedCaseInsensitiveContains(searchQuery) ||
                $0.amc.localizedCaseInsensitiveContains(searchQuery)
            }
        }

        return sorted(result)
    }

    var availableCategories: [String] {
        Array(Set(allFunds.map { $0.category })).sorted()
    }

    private func sorted(_ funds: [MutualFundDTO]) -> [MutualFundDTO] {
        switch sortOption {
        case .returns1y:
            return funds.sorted { ($0.returns1y ?? -.infinity) > ($1.returns1y ?? -.infinity) }
        case .returns3y:
            return funds.sorted { ($0.returns3y ?? -.infinity) > ($1.returns3y ?? -.infinity) }
        case .aum:
            return funds.sorted { ($0.aumCr ?? 0) > ($1.aumCr ?? 0) }
        case .expenseRatio:
            return funds.sorted { ($0.expenseRatio ?? .infinity) < ($1.expenseRatio ?? .infinity) }
        case .name:
            return funds.sorted { $0.fundName < $1.fundName }
        }
    }

    func fetchFunds() async {
        isLoading = true
        errorMessage = nil
        do {
            allFunds = try await NetworkManager.shared.fetchMutualFunds()
            if allFunds.isEmpty {
                errorMessage = "Couldn't load mutual funds. Pull to retry."
            }
        } catch {
            errorMessage = "Couldn't load mutual funds. Pull to retry."
        }
        isLoading = false
    }

    func clearFilters() {
        searchQuery = ""
        selectedCategory = nil
        selectedRiskLevel = nil
        minAumCr = 0
        minReturns1y = -100
    }
}

/// Drives MutualFundDetailView — loads full fund detail, NAV history for the
/// selected chart range, and top holdings independently so partial failures
/// (e.g. holdings endpoint not live yet) don't block the rest of the screen.
@MainActor
class MutualFundDetailViewModel: ObservableObject {
    @Published var fund: MutualFundDTO
    @Published var navHistory: [MutualFundNAVPoint] = []
    @Published var holdings: [MutualFundHolding] = []
    @Published var selectedRange: MutualFundNAVRange = .oneYear
    @Published var isLoadingNAV: Bool = false
    @Published var isLoadingHoldings: Bool = false

    let fundId: Int
    /// Backend paths key off scheme_code (string), not the row id — nil when
    /// the seed fund has no scheme_code, in which case detail/history/holdings
    /// calls are skipped and the seed data is shown as-is.
    private let schemeCode: String?

    init(seed: MutualFundDTO) {
        self.fund = seed
        self.fundId = seed.id
        self.schemeCode = seed.schemeCode
    }

    func loadAll() {
        Task { await refreshDetail() }
        Task { await loadNAVHistory() }
        Task { await loadHoldings() }
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

    func loadHoldings() async {
        guard let schemeCode else { return }
        isLoadingHoldings = true
        holdings = (try? await NetworkManager.shared.getMutualFundHoldings(schemeCode: schemeCode)) ?? []
        isLoadingHoldings = false
    }

    func changeRange(_ range: MutualFundNAVRange) {
        guard range != selectedRange else { return }
        selectedRange = range
        Task { await loadNAVHistory() }
    }
}
