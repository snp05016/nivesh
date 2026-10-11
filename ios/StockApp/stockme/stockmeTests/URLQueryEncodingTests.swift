import XCTest
@testable import stockme

/// IOSCORE-15: tickers such as M&M must survive as one query value.
final class URLQueryEncodingTests: XCTestCase {

    func testAmpersandEncoded() {
        XCTAssertEqual("M&M".urlQueryValue, "M%26M")
    }

    func testPlusAndEqualsEncoded() {
        XCTAssertEqual("A+B=C".urlQueryValue, "A%2BB%3DC")
    }

    @MainActor
    func testAllReservedTickersRoundTrip() throws {
        let reserved = CharacterSet(charactersIn: "&=+?#/ ")
        let tickers = StockDatabase.all.map(\.ticker).filter { $0.rangeOfCharacter(from: reserved) != nil }
        XCTAssertTrue(tickers.contains("M&M"))
        for ticker in tickers {
            let url = try XCTUnwrap(URL(string: "https://x/q?ticker=\(ticker.urlQueryValue)&exchange=NSE"))
            let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
            XCTAssertEqual(items.first { $0.name == "ticker" }?.value, ticker)
            XCTAssertEqual(items.first { $0.name == "exchange" }?.value, "NSE")
            XCTAssertEqual(items.count, 2, ticker)
        }
    }
}
