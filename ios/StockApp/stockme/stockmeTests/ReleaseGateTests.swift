import XCTest
@testable import stockme

/// REG-08: demo-only regulated flows must be hidden from Release builds.
@MainActor
final class ReleaseGateTests: XCTestCase {

    func test_hidden_sections_in_release() {
        for section in [MarketSection.financeTracker, .loanMarketplace, .fixedDeposits] {
            XCTAssertFalse(ReleaseGate.isVisible(section, demoFeatures: false), "\(section) must be hidden in Release")
        }
    }

    func test_core_sections_visible_in_release() {
        for section in [MarketSection.ipo, .forum, .screener] {
            XCTAssertTrue(ReleaseGate.isVisible(section, demoFeatures: false), "\(section) must stay visible")
        }
    }

    func test_debug_shows_all() {
        XCTAssertTrue(ReleaseGate.isVisible(.loanMarketplace, demoFeatures: true))
        for section in MarketSection.allCases {
            XCTAssertTrue(ReleaseGate.isVisible(section, demoFeatures: true))
        }
    }
}
