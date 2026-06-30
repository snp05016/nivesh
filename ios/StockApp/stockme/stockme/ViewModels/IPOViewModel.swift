import SwiftUI
import Combine

struct IPOListing: Identifiable, Equatable {
    let id = UUID()
    let name: String
    let issuePrice: String
    let closeDate: String
    var qibSubscription: Double
    var niiSubscription: Double
    var retailSubscription: Double
    var totalSubscription: Double
    var gmp: Double // Grey market premium
}

@MainActor
class IPOViewModel: ObservableObject {
    @Published var activeIPOs: [IPOListing] = []
    @Published var isRefreshing: Bool = false
    
    private var timer: Timer?
    
    init() {
        fetchActiveIPOs()
    }
    
    func fetchActiveIPOs() {
        self.activeIPOs = [
            IPOListing(name: "TechNova Solutions", issuePrice: "₹350 - 375", closeDate: "15 Oct", qibSubscription: 2.5, niiSubscription: 5.1, retailSubscription: 12.3, totalSubscription: 6.4, gmp: 85),
            IPOListing(name: "GreenEnergy Ltd", issuePrice: "₹120 - 125", closeDate: "18 Oct", qibSubscription: 0.8, niiSubscription: 1.2, retailSubscription: 3.5, totalSubscription: 1.8, gmp: 12),
            IPOListing(name: "Alpha Retail", issuePrice: "₹80 - 85", closeDate: "20 Oct", qibSubscription: 0.2, niiSubscription: 0.5, retailSubscription: 1.1, totalSubscription: 0.6, gmp: 4)
        ]
        startLiveUpdates()
    }
    
    func startLiveUpdates() {
        timer?.invalidate()
        // Simulate live subscription updates every 5 seconds
        timer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.simulateLiveSubscriptionIncrease()
            }
        }
    }
    
    func stopLiveUpdates() {
        timer?.invalidate()
        timer = nil
    }
    
    private func simulateLiveSubscriptionIncrease() {
        for i in 0..<activeIPOs.count {
            activeIPOs[i].qibSubscription += Double.random(in: 0...0.5)
            activeIPOs[i].niiSubscription += Double.random(in: 0...1.0)
            activeIPOs[i].retailSubscription += Double.random(in: 0...2.0)
            
            // Recalculate total as a weighted average mock
            let total = (activeIPOs[i].qibSubscription + activeIPOs[i].niiSubscription + activeIPOs[i].retailSubscription) / 3.0
            activeIPOs[i].totalSubscription = total
            
            // Random GMP fluctuations
            activeIPOs[i].gmp += Double.random(in: -2...5)
        }
    }
    
    deinit {
        timer?.invalidate()
    }
}
