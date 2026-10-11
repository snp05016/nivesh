import XCTest
@testable import stockme

/// IOSCORE-06 / GH-639: search must fail loudly on contract drift instead of
/// silently returning no results.
@MainActor
final class SearchDecodingTests: XCTestCase {

    private let row = #"{"ticker":"TCS","company_name":"Tata Consultancy Services","sector":"IT","exchange":"NSE"}"#

    func testBareArrayDecodes() throws {
        let entries = try NetworkManager.decodeSearchResults(Data("[\(row)]".utf8))
        XCTAssertEqual(entries, [StockEntry(ticker: "TCS", companyName: "Tata Consultancy Services", exchange: "NSE", sector: "IT")])
    }

    func testResultsEnvelopeDecodes() throws {
        let entries = try NetworkManager.decodeSearchResults(Data(#"{"status":"success","results":[\#(row)]}"#.utf8))
        XCTAssertEqual(entries.map(\.ticker), ["TCS"])
    }

    func testEmptyArrayIsNoMatchesNotAnError() throws {
        XCTAssertEqual(try NetworkManager.decodeSearchResults(Data("[]".utf8)), [])
    }

    func testUnknownShapeThrowsDecodingError() {
        XCTAssertThrowsError(try NetworkManager.decodeSearchResults(Data(#"{"detail":"boom"}"#.utf8))) { error in
            guard case NetworkError.decodingError = error else {
                return XCTFail("expected decodingError, got \(error)")
            }
        }
        XCTAssertThrowsError(try NetworkManager.decodeSearchResults(Data("not json".utf8)))
    }
}
