import XCTest
@testable import stockme

/// IOSCORE-17: money POSTs carry an Idempotency-Key, a 30 s timeout, never send an
/// empty body on encode failure, and map failures to non-misleading copy.
final class MoneyPostRequestTests: XCTestCase {

    private struct Body: Encodable { let amount: Double }

    private struct Unencodable: Encodable {
        struct Boom: Error {}
        func encode(to encoder: Encoder) throws { throw Boom() }
    }

    @MainActor
    func testMakeJSONPOSTSetsIdempotencyKeyAndTimeout() throws {
        let req = try NetworkManager.shared.makeJSONPOST(endpoint: "/api/fixed-deposits/bookings", body: Body(amount: 1), idempotencyKey: "k-1")
        XCTAssertEqual(req.httpMethod, "POST")
        XCTAssertEqual(req.timeoutInterval, 30)
        XCTAssertEqual(req.value(forHTTPHeaderField: "Content-Type"), "application/json")
        XCTAssertEqual(req.value(forHTTPHeaderField: "Idempotency-Key"), "k-1")
        XCTAssertNotNil(req.httpBody)
    }

    @MainActor
    func testMakeJSONPOSTOmitsKeyWhenNil() throws {
        let req = try NetworkManager.shared.makeJSONPOST(endpoint: "/x", body: Optional<Body>.none, idempotencyKey: nil)
        XCTAssertNil(req.value(forHTTPHeaderField: "Idempotency-Key"))
        XCTAssertNil(req.httpBody)
    }

    @MainActor
    func testMakeJSONPOSTPropagatesEncodeFailure() {
        XCTAssertThrowsError(try NetworkManager.shared.makeJSONPOST(endpoint: "/x", body: Unencodable(), idempotencyKey: "k"))
    }

    func testMoneyActionMessageMapsTimeout() {
        let msg = URLError(.timedOut).moneyActionMessage(fallback: "fallback")
        XCTAssertTrue(msg.contains("timed out"), msg)
    }

    func testMoneyActionMessageMaps4xx() {
        let err = NetworkError.fetchFailed(endpoint: "/x", status: 422, body: "")
        XCTAssertEqual(err.moneyActionMessage(fallback: "fallback"), "The request was rejected (code 422).")
    }

    func testMoneyActionMessageFallsBack() {
        XCTAssertEqual(NetworkError.invalidResponse.moneyActionMessage(fallback: "fallback"), "fallback")
    }
}
