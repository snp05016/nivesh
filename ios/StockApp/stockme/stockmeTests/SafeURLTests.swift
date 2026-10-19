import XCTest
@testable import stockme

/// IOSCORE-33: only https links from backend content may be opened.
final class SafeURLTests: XCTestCase {

    func testAcceptsHTTPS() {
        XCTAssertEqual(SafeURL.web("https://www.youtube.com/watch?v=x")?.absoluteString,
                       "https://www.youtube.com/watch?v=x")
    }

    func testRejectsHTTP() {
        XCTAssertNil(SafeURL.web("http://example.com/a"))
    }

    func testRejectsTelSmsJavascriptCustom() {
        for raw in ["tel:123", "sms:1", "javascript:alert(1)", "nivesh://x", "itms-apps://x"] {
            XCTAssertNil(SafeURL.web(raw), raw)
        }
    }

    func testRejectsHostlessEmptyAndNil() {
        XCTAssertNil(SafeURL.web("https:///path"))
        XCTAssertNil(SafeURL.web(""))
        XCTAssertNil(SafeURL.web(nil))
    }

    func testTrimsWhitespace() {
        XCTAssertEqual(SafeURL.web("  https://example.com/a \n")?.absoluteString, "https://example.com/a")
    }

    func testSchemeIsCaseInsensitive() {
        XCTAssertNotNil(SafeURL.web("HTTPS://example.com"))
    }
}
