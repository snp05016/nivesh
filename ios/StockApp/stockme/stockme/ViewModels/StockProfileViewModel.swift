import Foundation
import Combine

enum StockProfileTab: String, CaseIterable, Identifiable {
    case overview = "Overview"
    case chart = "Chart"
    case financials = "Financials"
    case analysis = "AI Analysis"
    
    var id: String { self.rawValue }
}

@MainActor
class StockProfileViewModel: ObservableObject {
    @Published var selectedTab: StockProfileTab = .overview
    @Published var ticker: String
    @Published var exchange: String
    
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil
    
    // Tab-specific data (lazy loaded)
    @Published var quickInfo: QuickInfo? = nil
    
    private var cancellables = Set<AnyCancellable>()
    private var dataLoadedForTabs: Set<StockProfileTab> = []
    
    init(ticker: String, exchange: String = "NSE") {
        self.ticker = ticker
        self.exchange = exchange
        
        setupTabSwitching()
    }
    
    private func setupTabSwitching() {
        $selectedTab
            .removeDuplicates()
            .sink { [weak self] newTab in
                self?.loadDataIfNeeded(for: newTab)
            }
            .store(in: &cancellables)
    }
    
    func switchTab(to tab: StockProfileTab) {
        selectedTab = tab
    }
    
    private func loadDataIfNeeded(for tab: StockProfileTab) {
        guard !dataLoadedForTabs.contains(tab) else { return }
        
        Task {
            self.isLoading = true
            self.errorMessage = nil
            
            switch tab {
            case .overview:
                self.quickInfo = await NetworkManager.shared.quickInfo(ticker: self.ticker, exchange: self.exchange)
                self.dataLoadedForTabs.insert(tab)
            case .chart, .financials, .analysis:
                // Other tabs will handle their own lazy loading in their respective ViewModels or sub-views.
                // We just mark them as loaded for the parent coordinator if needed.
                self.dataLoadedForTabs.insert(tab)
            }
            
            self.isLoading = false
        }
    }
}
