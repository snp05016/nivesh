import XCTest
@testable import stockme

/// CMON-25: tapping a price-alert push routes its `ticker` to the Home tab's action hub.
@MainActor
final class NotificationRoutingTests: XCTestCase {

    override func tearDown() {
        DeepLinkRouter.shared.pendingTicker = nil
        super.tearDown()
    }

    func testRouteSetsPendingTicker() {
        DeepLinkRouter.shared.pendingTicker = nil
        NotificationManager.shared.route(userInfo: ["ticker": "tcs"])
        XCTAssertEqual(DeepLinkRouter.shared.pendingTicker, "TCS")
    }

    func testRouteIgnoresMissingTicker() {
        DeepLinkRouter.shared.pendingTicker = nil
        NotificationManager.shared.route(userInfo: ["aps": ["alert": "hi"]])
        XCTAssertNil(DeepLinkRouter.shared.pendingTicker)
    }

    func testRouteIgnoresUnknownTicker() {
        DeepLinkRouter.shared.pendingTicker = nil
        NotificationManager.shared.route(userInfo: ["ticker": "NOTAREALTICKER"])
        XCTAssertNil(DeepLinkRouter.shared.pendingTicker)
    }
}
