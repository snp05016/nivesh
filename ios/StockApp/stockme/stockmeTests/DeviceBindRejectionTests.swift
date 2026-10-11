import XCTest
@testable import stockme

/// GH-665: POST /api/kyc/device-binding rejects with 409
/// `{"detail": {"reason", "fraud_signal"}}`; the client maps fraud_signal to friendly copy.
final class DeviceBindRejectionTests: XCTestCase {

    private func message(_ json: String) -> String {
        NetworkManager.deviceBindRejectionMessage(from: Data(json.utf8))
    }

    func testCrossUserReuse() {
        XCTAssertEqual(
            message(#"{"detail":{"reason":"x (mock cross-user device reuse check)","fraud_signal":"cross_user_device_reuse"}}"#),
            "This device is already registered to another account."
        )
    }

    func testRateLimit() {
        XCTAssertEqual(
            message(#"{"detail":{"reason":"x","fraud_signal":"rebind_rate_limit_exceeded"}}"#),
            "Too many device bind attempts in the last 24 hours. Please try again later."
        )
    }

    func testUnknownSignalAndGarbageFallBack() {
        let fallback = "This device couldn't be bound right now."
        XCTAssertEqual(message(#"{"detail":{"reason":"x","fraud_signal":"something_new"}}"#), fallback)
        XCTAssertEqual(message(#"{"detail":"plain string"}"#), fallback)
        XCTAssertEqual(message("not json"), fallback)
    }
}
