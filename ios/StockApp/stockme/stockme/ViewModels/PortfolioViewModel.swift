import Foundation
import Combine

@MainActor
class PortfolioViewModel: ObservableObject {
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil
    
    @Published var holdings: [PortfolioHolding] = []
    
    // Real-time P&L properties
    @Published var totalInvested: Double = 0.0
    @Published var currentValue: Double = 0.0
    @Published var totalPnL: Double = 0.0
    @Published var totalPnLPercent: Double = 0.0
    
    // Formatted strings for the UI complying with Indian numbering (Lakhs/Crores)
    @Published var portfolioSummaryString: String = "₹0.00"
    @Published var totalInvestedString: String = "₹0.00"
    @Published var totalPnLString: String = "₹0.00"
    @Published var totalPnLPercentString: String = "0.00%"
    
    private var timer: AnyCancellable?
    
    init() {
        fetchPortfolioData()
        startRealTimeUpdates()
    }
    
    deinit {
        timer?.cancel()
    }
    
    /// Polls the portfolio data every 15 seconds for real-time P&L updates
    func startRealTimeUpdates() {
        timer = Timer.publish(every: 15.0, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.fetchPortfolioData(isBackground: true)
            }
    }
    
    func fetchPortfolioData(isBackground: Bool = false) {
        if !isBackground {
            isLoading = true
        }
        errorMessage = nil
        
        Task {
            do {
                let userId = AuthManager.shared.currentUser?.userId ?? 1
                let portfolio = try await NetworkManager.shared.getPortfolio(userId: userId)
                
                self.holdings = portfolio
                self.calculateMetrics()
                
                if !isBackground {
                    self.isLoading = false
                }
            } catch {
                if !isBackground {
                    self.errorMessage = "Failed to load portfolio data. Please try again."
                    self.isLoading = false
                }
            }
        }
    }
    
    private func calculateMetrics() {
        var invested = 0.0
        var current = 0.0
        
        for holding in holdings {
            invested += holding.investedValue
            current += holding.currentValue
        }
        
        self.totalInvested = invested
        self.currentValue = current
        self.totalPnL = current - invested
        self.totalPnLPercent = invested > 0 ? (self.totalPnL / invested) * 100 : 0.0
        
        // Use IndianFormatter for strict Lakhs/Crores formatting as per AGENTS.md rules
        self.portfolioSummaryString = IndianFormatter.formatLakhsCrores(self.currentValue)
        self.totalInvestedString = IndianFormatter.formatLakhsCrores(self.totalInvested)
        self.totalPnLString = IndianFormatter.formatLakhsCrores(self.totalPnL)
        self.totalPnLPercentString = IndianFormatter.delta(self.totalPnLPercent)
    }
}
