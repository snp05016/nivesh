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

    /// CMON-06: a 402 from require_entitlement becomes the typed paywall error.
    func testEnsureOK402MapsToPaymentRequired() {
        let body = Data(#"{"detail":{"message":"x","required_tier":"pro"}}"#.utf8)
        XCTAssertThrowsError(try NetworkError.ensureOK(data: body, response: response(402))) { error in
            guard case NetworkError.paymentRequired(let tier, let message) = error else {
                return XCTFail("expected .paymentRequired, got \(error)")
            }
            XCTAssertEqual(tier, "pro")
            XCTAssertEqual(message, "x")
        }
    }

    /// CMON-06: the options payoff route is entitlement-gated, so it must carry the Bearer token.
    func testOptionsPayoffRequestCarriesBearer() throws {
        let nm = NetworkManager.shared
        let saved = nm.authToken
        defer { nm.authToken = saved }
        nm.authToken = "hdr.payload.sig"
        let legs = [OptionLeg(type: "CALL", position: "LONG", strike: 100, premium: 5)]
        let request = try nm.makeOptionsPayoffRequest(spotPrice: 100, legs: legs)
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer hdr.payload.sig")
        XCTAssertEqual(request.httpMethod, "POST")
    }

    func testEnsureOK2xxPasses() {
        XCTAssertNoThrow(try NetworkError.ensureOK(data: Data(), response: response(200)))
        XCTAssertNoThrow(try NetworkError.ensureOK(data: Data(), response: response(204)))
    }
}
