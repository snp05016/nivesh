import XCTest
@testable import stockme

/// UX-11: HTTP 402 from core/entitlement_gate.py must surface as a typed,
/// user-friendly paymentRequired error, and client entitlement checks fail closed.
@MainActor
final class NetworkErrorEntitlementTests: XCTestCase {

    private let body402 = Data(#"{"detail":{"message":"'comprehensive_stock_insights' requires the 'pro' tier or higher","required_tier":"pro","current_tier":"free"}}"#.utf8)

    func test402MapsToPaymentRequired() {
        let err = NetworkError.fromHTTP(status: 402, data: body402, endpoint: "/api/v1/fundamentals/valuation")
        guard case .paymentRequired(let tier, let message) = err else {
            return XCTFail("expected paymentRequired, got \(err)")
        }
        XCTAssertEqual(tier, "pro")
        XCTAssertNotNil(message)
        XCTAssertEqual(err.requiredTier, .pro)
    }

    func test402CopyIsFriendly() {
        let copy = NetworkError.fromHTTP(status: 402, data: body402, endpoint: "/api/v1/fundamentals/valuation")
            .errorDescription ?? ""
        XCTAssertTrue(copy.contains("PRO"), copy)
        for token in ["HTTP", "/api/", "{", "402"] {
            XCTAssertFalse(copy.contains(token), "'\(copy)' contains '\(token)'")
        }
    }

    func test402SuperProTier() {
        let data = Data(#"{"detail":{"message":"x","required_tier":"super_pro","current_tier":"pro"}}"#.utf8)
        let err = NetworkError.fromHTTP(status: 402, data: data, endpoint: "/x")
        XCTAssertEqual(err.requiredTier, .superPro)
        XCTAssertTrue((err.errorDescription ?? "").contains("Super PRO"))
    }

    /// CMON-22: a plan-cap 402 shows the server's cap message plus the upgrade tier;
    /// non-402 errors have no upgradeMessage so callers keep their own copy.
    func testQuotaUpgradeMessage() {
        let data = Data(#"{"detail":{"message":"Your plan allows 10 watchlist stocks.","required_tier":"pro","current_tier":"free"}}"#.utf8)
        let err = NetworkError.fromHTTP(status: 402, data: data, endpoint: "/watchlist/add")
        XCTAssertEqual(err.upgradeMessage, "Your plan allows 10 watchlist stocks. Upgrade to Nivesh PRO for more.")
        XCTAssertEqual(NetworkError.paymentRequired(requiredTier: nil, message: nil).upgradeMessage,
                       NetworkError.paymentRequired(requiredTier: nil, message: nil).errorDescription)
        XCTAssertNil(NetworkError.fromHTTP(status: 500, data: Data(), endpoint: "/x").upgradeMessage)
    }

    func test402WithUnparseableBodyDefaultsToPro() {
        let err = NetworkError.fromHTTP(status: 402, data: Data("<html>".utf8), endpoint: "/x")
        XCTAssertEqual(err.requiredTier, .pro)
    }

    func test401MapsToUnauthorized() {
        guard case .unauthorized = NetworkError.fromHTTP(status: 401, data: Data(), endpoint: "/x") else {
            return XCTFail("expected unauthorized")
        }
    }

    func test500MapsToFetchFailed() {
        let err = NetworkError.fromHTTP(status: 500, data: Data("boom".utf8), endpoint: "/api/v1/x")
        guard case .fetchFailed(let endpoint, let status, let body) = err else {
            return XCTFail("expected fetchFailed, got \(err)")
        }
        XCTAssertEqual(endpoint, "/api/v1/x")
        XCTAssertEqual(status, 500)
        XCTAssertEqual(body, "boom")
        XCTAssertNil(err.requiredTier)
    }

    func testFeatureLockedWhenEntitlementsNotLoaded() {
        let vm = SubscriptionViewModel()
        XCTAssertNil(vm.entitlements)
        XCTAssertFalse(vm.isFeatureUnlocked(.sectorRotation))
    }

    func testFeatureFollowsServerEntitlements() {
        let vm = SubscriptionViewModel()
        vm.entitlements = EntitlementsDTO(tier: "pro", features: ["technical_picks": true, "swot_analysis": false])
        XCTAssertTrue(vm.isFeatureUnlocked(.technicalPicks))
        XCTAssertFalse(vm.isFeatureUnlocked(.swotAnalysis))
        // Fail closed: a key the server did not return stays locked.
        XCTAssertFalse(vm.isFeatureUnlocked(.sectorRotation))
    }

    /// UX-12: the paywall matrix is built from the server catalogue, not a client list.
    func testPaywallRowsComeFromServerCatalog() throws {
        let json = Data(#"{"tier":"free","features":{"sector_rotation":false},"catalog":[{"key":"sector_rotation","title":"Sector rotation analytics","min_tier":"pro"}]}"#.utf8)
        let dto = try JSONDecoder().decode(EntitlementsDTO.self, from: json)
        let rows = SubscriptionFeatureRow.rows(from: dto.catalog ?? [])
        XCTAssertEqual(rows.map(\.title), ["Sector rotation analytics"])
        XCTAssertNil(rows[0].values[.free] ?? nil)
        XCTAssertEqual(rows[0].values[.pro] ?? nil, "yes")
        XCTAssertEqual(rows[0].values[.superPro] ?? nil, "yes")
    }

    func testEntitlementsDecodeWithoutCatalog() throws {
        let json = Data(#"{"tier":"pro","features":{}}"#.utf8)
        XCTAssertNil(try JSONDecoder().decode(EntitlementsDTO.self, from: json).catalog)
    }
}
