import XCTest
@testable import stockme

@MainActor
final class DeepLinkTests: XCTestCase {

    private func ticker(_ string: String) -> String? {
        guard let url = URL(string: string) else { return nil }
        return DeepLink.ticker(from: url)
    }

    func testAnalyzeLinkUppercasesKnownTicker() {
        XCTAssertEqual(ticker("nivesh://analyze/reliance"), "RELIANCE")
    }

    func testWatchlistAddLinkOnlyResolvesTicker() {
        XCTAssertEqual(ticker("nivesh://watchlist/add/TCS"), "TCS")
    }

    func testTickerWithAmpersandResolves() {
        XCTAssertEqual(ticker("nivesh://analyze/M&M"), "M&M")
    }

    func testOtherSchemeIsRejected() {
        XCTAssertNil(ticker("https://evil.example/analyze/INFY"))
    }

    func testPathTraversalIsRejected() {
        XCTAssertNil(ticker("nivesh://analyze/../../"))
    }

    func testUnknownTickerIsRejected() {
        XCTAssertNil(ticker("nivesh://analyze/NOTAREALTICKER"))
    }

    func testUnknownRouteIsRejected() {
        XCTAssertNil(ticker("nivesh://watchlist/remove/TCS"))
        XCTAssertNil(ticker("nivesh://analyze/INFY/extra"))
    }

    func testPushTickerAndURLResolveToSameTicker() {
        // NotificationManager.didReceive validates userInfo["ticker"] the same way.
        XCTAssertEqual(DeepLink.validTicker("reliance"), ticker("nivesh://analyze/RELIANCE"))
    }

    func testPushPayloadTickerValidation() {
        XCTAssertEqual(DeepLink.validTicker("infy"), "INFY")
        XCTAssertNil(DeepLink.validTicker(""))
    }
}

final class ServerURLPolicyHTTPSTests: XCTestCase {

    func testPlainHTTPOverrideFallsBackToDefault() {
        let resolved = ServerURLPolicy.resolve(
            storedURL: "http://10.0.0.5:8000",
            defaultURL: "https://api.nivesh.qzz.io"
        )
        XCTAssertEqual(resolved, "https://api.nivesh.qzz.io")
    }
}
