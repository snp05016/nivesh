import XCTest
@testable import stockme

/// GET /api/v1/subscription payloads with exactly the backend
/// SubscriptionResponse keys (backend/routers/subscription.py) (TEST-17).
final class SubscriptionDecodingTests: XCTestCase {
    private func decode(_ json: String) throws -> CurrentSubscriptionDTO {
        try JSONDecoder().decode(CurrentSubscriptionDTO.self, from: Data(json.utf8))
    }

    private func payload(tier: String, isActive: Bool, cancelledAt: String?) -> String {
        let cancelled = cancelledAt.map { "\"\($0)\"" } ?? "null"
        return """
        {"user_id": 42, "tier": "\(tier)", "billing_cycle": "monthly",
         "started_at": "2026-10-01T09:30:00", "renews_at": "2026-11-01T09:30:00",
         "is_active": \(isActive), "cancelled_at": \(cancelled)}
        """
    }

    func testActiveProSubscription() throws {
        let dto = try decode(payload(tier: "pro", isActive: true, cancelledAt: nil))
        XCTAssertEqual(dto.userId, 42)
        XCTAssertEqual(dto.parsedTier, .pro)
        XCTAssertEqual(dto.parsedStatus, .active)
        XCTAssertTrue(dto.autoRenew)
        XCTAssertEqual(dto.renewalDate, "2026-11-01T09:30:00")
    }

    func testCancelledSubscriptionKeepsTierUntilPeriodEnd() throws {
        let dto = try decode(payload(tier: "super_pro", isActive: true, cancelledAt: "2026-10-05T12:00:00"))
        XCTAssertEqual(dto.parsedTier, .superPro)
        XCTAssertEqual(dto.parsedStatus, .cancelled)
        XCTAssertFalse(dto.autoRenew)
    }

    func testInactiveSubscriptionHasNoStatus() throws {
        let dto = try decode(payload(tier: "pro", isActive: false, cancelledAt: nil))
        XCTAssertEqual(dto.parsedStatus, SubscriptionStatus.none)
    }

    func testFreeUserWithNullDates() throws {
        let json = """
        {"user_id": 7, "tier": "free", "billing_cycle": null, "started_at": null,
         "renews_at": null, "is_active": true, "cancelled_at": null}
        """
        let dto = try decode(json)
        XCTAssertEqual(dto.parsedTier, .free)
        XCTAssertNil(dto.billingCycle)
        XCTAssertNil(dto.renewalDate)
    }

    func testUnknownTierFallsBackToFree() throws {
        let dto = try decode(payload(tier: "platinum", isActive: true, cancelledAt: nil))
        XCTAssertEqual(dto.parsedTier, .free)
    }
}
