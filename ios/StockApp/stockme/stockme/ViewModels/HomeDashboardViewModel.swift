import Foundation
import Combine

struct DashboardMockData {
    let indices: [String]
    let portfolioValue: String
    let topGainers: [String]
}

@MainActor
class HomeDashboardViewModel: ObservableObject {
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil
    
    @Published var marketIndices: [String] = []
    @Published var portfolioSummary: String = "₹ 0.00"
    @Published var daysGain: String = "+₹ 0.00"
    @Published var topGainers: [String] = []
    
    init() {
        fetchDashboardData()
    }
    
    func fetchDashboardData() {
        isLoading = true
        errorMessage = nil
        
        Task {
            do {
                let pulse = try await NetworkManager.shared.fetchDashboardPulse()
                
                let userId = AuthManager.shared.currentUser?.userId ?? 1
                let portfolio = try? await NetworkManager.shared.getPortfolio(userId: userId)
                
                let totalValue = portfolio?.reduce(0) { $0 + ($1.stock.currentPrice * $1.shares) } ?? 0.0
                let totalBuyValue = portfolio?.reduce(0) { $0 + ($1.buyPrice * $1.shares) } ?? 0.0
                let gain = totalValue - totalBuyValue
                
                let formatter = NumberFormatter()
                formatter.numberStyle = .currency
                formatter.currencySymbol = "₹"
                formatter.maximumFractionDigits = 2
                
                let formattedValue = formatter.string(from: NSNumber(value: totalValue)) ?? "₹ 0.00"
                let formattedGain = formatter.string(from: NSNumber(value: gain)) ?? "₹ 0.00"
                let prefix = gain >= 0 ? "+" : ""
                
                self.marketIndices = pulse.indices.map { "\($0.name) \($0.value ?? 0.0)" }
                self.portfolioSummary = formattedValue
                self.daysGain = "\(prefix)\(formattedGain)"
                self.topGainers = pulse.momentum_signals.filter { $0.signal == "GOLDEN_CROSS" }.map { $0.ticker }
                
                self.isLoading = false
            } catch {
                self.errorMessage = "Failed to load dashboard data. Please try again."
                self.isLoading = false
            }
        }
    }
}
