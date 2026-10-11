import Foundation

/// Release gate for demo-only flows (App Review 2.1(a), 2.2, 3.1.1).
///
/// Loans, fixed deposits, finance tracker and the mock subscription upgrade are
/// portfolio demos with no real underwriting, payment or IAP. They stay
/// reachable in Debug builds and are hidden from Release builds.
enum ReleaseGate {
    #if DEBUG
    static let demoFeatures = true
    #else
    static let demoFeatures = false
    #endif

    static let hiddenInRelease: Set<MarketSection> = [.financeTracker, .loanMarketplace, .fixedDeposits]

    static func isVisible(_ section: MarketSection, demoFeatures: Bool = ReleaseGate.demoFeatures) -> Bool {
        demoFeatures || !hiddenInRelease.contains(section)
    }
}
