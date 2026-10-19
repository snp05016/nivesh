import XCTest
@testable import stockme

/// IOSCORE-34: raw response bodies, endpoints and decode detail stay out of user-facing copy.
@MainActor
final class NetworkErrorMessageTests: XCTestCase {

    func testFetchFailedDescriptionHidesBodyAndEndpoint() {
        let error = NetworkError.fetchFailed(endpoint: "/x", status: 500, body: "<html>secret</html>")
        let copy = error.errorDescription ?? ""
        XCTAssertFalse(copy.contains("secret"))
        XCTAssertFalse(copy.contains("/x"))
        XCTAssertTrue(error.diagnosticDetail.contains("secret"))
        XCTAssertTrue(error.diagnosticDetail.contains("/x"))
    }

    func testDecodingErrorDescriptionHidesDetail() {
        let copy = NetworkError.decodingError("keyNotFound portfolio_value").errorDescription ?? ""
        XCTAssertFalse(copy.contains("portfolio_value"))
    }

    func testConnectionFailedTextIsUserFacing() {
        XCTAssertFalse((NetworkError.connectionFailed.errorDescription ?? "").contains("your computer"))
    }
}
