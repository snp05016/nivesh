import Foundation
import Combine

@MainActor
class UniversalSearchViewModel: ObservableObject {
    @Published var searchQuery: String = ""
    @Published var searchResults: [String] = []
    @Published var isSearching: Bool = false
    
    private var cancellables = Set<AnyCancellable>()
    
    init() {
        setupSearchDebounce()
    }
    
    private func setupSearchDebounce() {
        $searchQuery
            .dropFirst()
            .debounce(for: .milliseconds(300), scheduler: RunLoop.main)
            .removeDuplicates()
            .sink { [weak self] query in
                self?.performSearch(for: query)
            }
            .store(in: &cancellables)
    }
    
    private func performSearch(for query: String) {
        guard !query.isEmpty else {
            searchResults = []
            isSearching = false
            return
        }
        
        isSearching = true
        
        Task {
            let results = await NetworkManager.shared.searchStocks(q: query)
            
            // Check if query hasn't changed while we were fetching
            guard self.searchQuery == query else { return }
            
            self.searchResults = results.map { "\($0.companyName) (\($0.ticker))" }
            self.isSearching = false
        }
    }
}
