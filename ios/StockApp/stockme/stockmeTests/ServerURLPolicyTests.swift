import XCTest
@testable import stockme

/// IOSCORE-19: only well-formed https overrides are honoured; ATS stays enforced.
final class ServerURLPolicyTests: XCTestCase {

    private let defaultURL = "https://api.nivesh.qzz.io"

    func testLegacyLocalServerOverrideMigratesToProductionURL() {
        XCTAssertEqual(ServerURLPolicy.resolve(storedURL: "http://192.168.1.122:8000", defaultURL: defaultURL), defaultURL)
    }

    func testCustomHTTPSOverrideRemainsSelected() {
        XCTAssertEqual(
            ServerURLPolicy.resolve(storedURL: "https://staging.nivesh.example", defaultURL: defaultURL),
            "https://staging.nivesh.example"
        )
    }

    func testRejectsPlainHTTP() {
        XCTAssertEqual(ServerURLPolicy.resolve(storedURL: "http://example.com", defaultURL: defaultURL), defaultURL)
    }

    func testRejectsOtherSchemesAndMissingHost() {
        for stored in ["ftp://x", "javascript:x", "https://", "api.nivesh.qzz.io"] {
            XCTAssertEqual(ServerURLPolicy.resolve(storedURL: stored, defaultURL: defaultURL), defaultURL, stored)
        }
    }

    func testEmptyAndNilReturnDefault() {
        XCTAssertEqual(ServerURLPolicy.resolve(storedURL: nil, defaultURL: defaultURL), defaultURL)
        XCTAssertEqual(ServerURLPolicy.resolve(storedURL: "", defaultURL: defaultURL), defaultURL)
    }

    func testATSArbitraryLoadsDisabled() {
        // Unit tests are hosted in the app, so Bundle.main is the app's Info.plist.
        let ats = Bundle.main.infoDictionary?["NSAppTransportSecurity"] as? [String: Any]
        XCTAssertNotEqual(ats?["NSAllowsArbitraryLoads"] as? Bool, true)
    }
}
