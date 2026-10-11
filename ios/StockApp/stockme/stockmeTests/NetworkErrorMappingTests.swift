import XCTest
@testable import stockme

/// CMON-20: a non-2xx from the portfolio write routes carries FastAPI's
/// `detail` through to the user instead of a generic "invalid response".
@MainActor
final class NetworkErrorMappingTests: XCTestCase {

    private func response(_ status: Int) -> HTTPURLResponse {
        HTTPURLResponse(url: URL(string: "https://example.com/portfolio")!, statusCode: status, httpVersion: nil, headerFields: nil)!
    }

    func testEnsureOKSurfacesStringDetail() {
        let body = Data(#"{"detail":"Cannot SELL 20.0 of TCS: only 10.0 shares held."}"#.utf8)
        XCTAssertThrowsError(try NetworkError.ensureOK(data: body, response: response(400))) { error in
            XCTAssertEqual(error.localizedDescription, "Cannot SELL 20.0 of TCS: only 10.0 shares held.")
        }
    }

    func testEnsureOKSurfacesValidationList() {
        let body = Data(#"{"detail":[{"loc":["body","shares"],"msg":"Input should be greater than 0","type":"greater_than"}]}"#.utf8)
        XCTAssertThrowsError(try NetworkError.ensureOK(data: body, response: response(422))) { error in
            XCTAssertEqual(error.localizedDescription, "Input should be greater than 0")
        }
    }

    func testEnsureOKMaps401ToUnauthorized() {
        XCTAssertThrowsError(try NetworkError.ensureOK(data: Data(), response: response(401))) { error in
            guard case NetworkError.unauthorized = error else { return XCTFail("expected .unauthorized, got \(error)") }
        }
    }

    func testEnsureOK2xxPasses() {
        XCTAssertNoThrow(try NetworkError.ensureOK(data: Data(), response: response(200)))
        XCTAssertNoThrow(try NetworkError.ensureOK(data: Data(), response: response(204)))
    }
}
