import XCTest
@testable import stockme

/// UX-13: user-facing NetworkError copy must never leak developer diagnostics.
@MainActor
final class NetworkErrorCopyTests: XCTestCase {

    private let forbidden = ["HTTP", "/api/", "JSON", "backend", "Server URL", "running on your computer", "{"]

    private func assertFriendly(_ error: NetworkError, file: StaticString = #filePath, line: UInt = #line) {
        let copy = error.errorDescription ?? ""
        XCTAssertFalse(copy.isEmpty, "empty copy for \(error)", file: file, line: line)
        for token in forbidden {
            XCTAssertFalse(copy.contains(token), "'\(copy)' contains '\(token)'", file: file, line: line)
        }
    }

    func testEveryCaseHasFriendlyCopy() {
        assertFriendly(.invalidURL)
        assertFriendly(.invalidResponse)
        assertFriendly(.serverError(500, "{\"detail\":\"x\"}"))
        assertFriendly(.serverError(429, nil))
        assertFriendly(.decodingError("keyNotFound CodingKeys(stringValue: \"ticker\") | Raw keys: a, b | Body: {\"a\":1}"))
        assertFriendly(.connectionFailed)
        assertFriendly(.unauthorized)
        assertFriendly(.invalidCredentials)
        for status in [-1, 0, 401, 404, 422, 500, 503] {
            assertFriendly(.fetchFailed(endpoint: "/api/v1/x", status: status, body: "{\"detail\":\"boom\"}"))
        }
    }

    func testRateLimitCopy() {
        let copy = NetworkError.serverError(429, nil).errorDescription ?? ""
        XCTAssertTrue(copy.contains("Too many"))
    }

    func testShortPlainServerDetailPassesThroughForValidation() {
        XCTAssertEqual(NetworkError.serverError(400, "Username already exists").errorDescription,
                       "Username already exists")
    }

    func testServerDetailFromStringDetail() {
        let data = Data(#"{"detail":"Username already exists"}"#.utf8)
        XCTAssertEqual(NetworkError.serverDetail(from: data), "Username already exists")
    }

    func testServerDetailFromFastAPIValidationList() {
        let data = Data(#"{"detail":[{"loc":["body","password"],"msg":"Field required","type":"missing"}]}"#.utf8)
        XCTAssertEqual(NetworkError.serverDetail(from: data), "Field required")
    }

    func testServerDetailFromNestedMessage() {
        let data = Data(#"{"detail":{"message":"Upgrade required"}}"#.utf8)
        XCTAssertEqual(NetworkError.serverDetail(from: data), "Upgrade required")
    }

    func testServerDetailNilForNonJSON() {
        XCTAssertNil(NetworkError.serverDetail(from: Data("<html>502</html>".utf8)))
    }

    func testDiagnosticDetailKeepsEndpointForDevelopers() {
        let detail = NetworkError.fetchFailed(endpoint: "/api/v1/x", status: 500, body: "boom").diagnosticDetail
        XCTAssertTrue(detail.contains("/api/v1/x"))
        XCTAssertTrue(detail.contains("500"))
    }
}
