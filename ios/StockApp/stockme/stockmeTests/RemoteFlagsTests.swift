import XCTest
@testable import stockme

@MainActor
final class RemoteFlagsTests: XCTestCase {

    private struct Offline: Error {}

    private func freshDefaults() -> UserDefaults {
        UserDefaults(suiteName: UUID().uuidString)!
    }

    private func decode(_ json: String) throws -> ClientFlagsResponse {
        try JSONDecoder().decode(ClientFlagsResponse.self, from: Data(json.utf8))
    }

    func testDecodesContractPayload() throws {
        let r = try decode(#"{"flags":{"analytics":true,"analytics_consented":false,"future_key":true},"analytics_retention_days":180}"#)
        XCTAssertEqual(r.flags, ["analytics": true, "analytics_consented": false, "future_key": true])
        XCTAssertEqual(r.analyticsRetentionDays, 180)
    }

    func testMissingRetentionDaysDecodesAsNil() throws {
        let r = try decode(#"{"flags":{"analytics":false}}"#)
        XCTAssertNil(r.analyticsRetentionDays)
    }

    func testUnknownKeyReadsFalse() async {
        let store = RemoteFlags(defaults: freshDefaults(), fetch: { ClientFlagsResponse(flags: ["analytics": true]) })
        XCTAssertFalse(store.isOn("analytics"))  // never fetched
        await store.refresh(force: true)
        XCTAssertTrue(store.isOn("analytics"))
        XCTAssertFalse(store.isOn("not_a_flag"))
    }

    func testFailedFetchKeepsCachedValues() async {
        let defaults = freshDefaults()
        let first = RemoteFlags(defaults: defaults, fetch: {
            ClientFlagsResponse(flags: ["analytics": true], analyticsRetentionDays: 90)
        })
        await first.refresh(force: true)

        let offline = RemoteFlags(defaults: defaults, fetch: { throw Offline() })
        XCTAssertTrue(offline.isOn("analytics"))   // served from the cache
        await offline.refresh(force: true)         // fails
        XCTAssertTrue(offline.isOn("analytics"))
        XCTAssertEqual(offline.analyticsRetentionDays, 90)
    }

    func testConsentIsNotPersistedButRetentionDaysAre() async {
        let defaults = freshDefaults()
        let first = RemoteFlags(defaults: defaults, fetch: {
            ClientFlagsResponse(flags: ["analytics": true, "analytics_consented": true], analyticsRetentionDays: 180)
        })
        await first.refresh(force: true)
        XCTAssertTrue(first.isOn("analytics_consented"))

        let second = RemoteFlags(defaults: defaults, fetch: { throw Offline() })
        XCTAssertTrue(second.isOn("analytics"))
        XCTAssertFalse(second.isOn("analytics_consented"))
        XCTAssertEqual(second.analyticsRetentionDays, 180)
    }

    func testRefreshIsSkippedWithin300sUnlessForced() async {
        var calls = 0
        var clock = Date(timeIntervalSince1970: 1_000)
        let store = RemoteFlags(defaults: freshDefaults(),
                                fetch: { calls += 1; return ClientFlagsResponse(flags: ["analytics": true]) },
                                now: { clock })
        await store.refresh()
        XCTAssertEqual(calls, 1)
        clock = clock.addingTimeInterval(299)
        await store.refresh()
        XCTAssertEqual(calls, 1)
        await store.refresh(force: true)
        XCTAssertEqual(calls, 2)
        clock = clock.addingTimeInterval(301)
        await store.refresh()
        XCTAssertEqual(calls, 3)
    }

    func testRetentionDaysKeepsLastValueWhenAbsent() async {
        var payloads = [ClientFlagsResponse(flags: [:], analyticsRetentionDays: 365),
                        ClientFlagsResponse(flags: [:], analyticsRetentionDays: nil)]
        let store = RemoteFlags(defaults: freshDefaults(), fetch: { payloads.removeFirst() })
        await store.refresh(force: true)
        await store.refresh(force: true)
        XCTAssertEqual(store.analyticsRetentionDays, 365)
    }
}
