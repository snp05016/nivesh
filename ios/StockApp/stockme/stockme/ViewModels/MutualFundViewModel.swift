import SwiftUI
import Combine

@MainActor
class MutualFundViewModel: ObservableObject {
    @Published var searchQuery: String = ""
    @Published var selectedCategory: String? = nil
    @Published var allFunds: [MutualFundDTO] = []
    
    var filteredFunds: [MutualFundDTO] {
        var result = allFunds
        
        if let category = selectedCategory, !category.isEmpty {
            result = result.filter { $0.category == category }
        }
        
        if !searchQuery.isEmpty {
            result = result.filter { $0.fundName.localizedCaseInsensitiveContains(searchQuery) }
        }
        
        return result
    }
    
    var availableCategories: [String] {
        Array(Set(allFunds.map { $0.category })).sorted()
    }
    
    func fetchFunds() async {
        do {
            self.allFunds = try await NetworkManager.shared.fetchMutualFunds()
            if selectedCategory == nil, let first = availableCategories.first {
                selectedCategory = first
            }
        } catch {
            print("Error fetching mutual funds: \(error)")
        }
    }
    
    func clearFilters() {
        searchQuery = ""
        selectedCategory = nil
    }
}
