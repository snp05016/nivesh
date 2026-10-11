import XCTest
@testable import stockme

/// UX-22: mock/demo hubs must not appear in Release navigation or in the
/// copilot's Markets map; real hubs stay listed.
@MainActor
final class MarketSectionGatingTests: XCTestCase {

    private let demoHubs: Set<MarketSection> = [.financeTracker, .loanMarketplace, .fixedDeposits]

    func test_demo_hub_set_is_exactly_the_mock_backed_hubs() {
        XCTAssertEqual(ReleaseGate.hiddenInRelease, demoHubs)
    }

    func test_release_markets_list_has_no_demo_hubs() {
        for category in MarketSection.Category.allCases {
            let visible = category.sections.filter { ReleaseGate.isVisible($0, demoFeatures: false) }
            XCTAssertTrue(demoHubs.isDisjoint(with: visible), "\(category) lists a demo hub in Release")
        }
    }

    func test_release_keeps_live_hubs() {
        let visible = MarketSection.allCases.filter { ReleaseGate.isVisible($0, demoFeatures: false) }
        XCTAssertEqual(Set(visible), Set(MarketSection.allCases).subtracting(demoHubs))
        XCTAssertTrue(visible.contains(.ipo))
        XCTAssertTrue(visible.contains(.mutualFunds))
    }

    func test_debug_lists_every_hub() {
        let visible = MarketSection.allCases.filter { ReleaseGate.isVisible($0, demoFeatures: true) }
        XCTAssertEqual(visible, MarketSection.allCases)
    }
}
