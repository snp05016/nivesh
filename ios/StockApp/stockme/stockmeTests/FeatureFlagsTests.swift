import XCTest
@testable import stockme

@MainActor
final class FeatureFlagsTests: XCTestCase {

    private struct Offline: Error {}

    private func freshDefaults() -> UserDefaults {
        UserDefaults(suiteName: UUID().uuidString)!
    }

    private func json(_ s: String) -> Data { Data(s.utf8) }

    func testValidPayloadDecodes() {
        let flags = FeatureFlags.decode(json(#"{"flags":{"money_xray":true,"money_tax_report":false},"version":1}"#))
        XCTAssertEqual(flags, ["money_xray": true, "money_tax_report": false])
    }

    func testNonBoolValueFailsAndLeavesValuesUnchanged() async {
        XCTAssertNil(FeatureFlags.decode(json(#"{"flags":{"money_xray":"yes"}}"#)))
        XCTAssertNil(FeatureFlags.decode(json("not json")))

        var payload = json(#"{"flags":{"money_xray":true}}"#)
        let store = FeatureFlags(defaults: freshDefaults(), fetch: {
            guard let flags = FeatureFlags.decode(payload) else { throw Offline() }
            return flags
        })
        await store.refresh(force: true)
        XCTAssertTrue(store.isOn(.moneyXray))

        payload = json(#"{"flags":{"money_xray":1}}"#)
        await store.refresh(force: true)
        XCTAssertTrue(store.isOn(.moneyXray))
        XCTAssertEqual(store.values, ["money_xray": true])
    }

    func testMissingAndNeverFetchedKeysAreOff() async {
        let empty = FeatureFlags(defaults: freshDefaults(), fetch: { throw Offline() })
        for key in FeatureKey.allCases { XCTAssertEqual(empty.isOn(key), key.defaultValue, key.rawValue) }

        let store = FeatureFlags(defaults: freshDefaults(), fetch: { ["money_holding_detail": true] })
        await store.refresh()
        XCTAssertTrue(store.isOn(.moneyHoldingDetail))
        XCTAssertFalse(store.isOn(.moneyCasImport))
    }

    func testCorruptCacheReadsAllOff() {
        let defaults = freshDefaults()
        defaults.set(json("{oops"), forKey: FeatureFlags.cacheKey)
        let store = FeatureFlags(defaults: defaults, fetch: { throw Offline() })
        XCTAssertEqual(store.values, [:])
    }

    func testCacheRoundTrip() async {
        let defaults = freshDefaults()
        let first = FeatureFlags(defaults: defaults, fetch: { ["money_xirr_card": true, "money_xray": false] })
        await first.refresh()

        let reopened = FeatureFlags(defaults: defaults, fetch: { throw Offline() })
        XCTAssertEqual(reopened.values, ["money_xirr_card": true, "money_xray": false])
        XCTAssertTrue(reopened.isOn(.moneyXirrCard))

        await reopened.refresh()  // failure keeps the cached values
        XCTAssertTrue(reopened.isOn(.moneyXirrCard))
    }

    func testRefreshSkippedWithin600sUnlessForced() async {
        var clock = Date(timeIntervalSince1970: 1_000_000)
        var calls = 0
        let store = FeatureFlags(defaults: freshDefaults(),
                                 fetch: { calls += 1; return [:] },
                                 now: { clock })
        await store.refresh()
        XCTAssertEqual(calls, 1)

        clock.addTimeInterval(599)
        await store.refresh()
        XCTAssertEqual(calls, 1)

        await store.refresh(force: true)
        XCTAssertEqual(calls, 2)

        clock.addTimeInterval(601)
        await store.refresh()
        XCTAssertEqual(calls, 3)
    }

    // MARK: Habit cluster (spec_habit 0.2)

    func testHabitContractDecodes() {
        let body = #"{"flags":{"notif_prefs_v2":true,"today_brief":false,"event_radar":false,"watchlist_v2":true,"widget_snapshot":false},"version":1,"ttl_seconds":300}"#
        XCTAssertEqual(FeatureFlags.decode(json(body)), [
            "notif_prefs_v2": true, "today_brief": false, "event_radar": false,
            "watchlist_v2": true, "widget_snapshot": false,
        ])
    }

    func testDefaultsAreOffExceptWidgetSnapshot() {
        for key in FeatureKey.allCases {
            XCTAssertEqual(key.defaultValue, key == .widgetSnapshot, key.rawValue)
        }
    }

    func testCachedIsOnReadsStoredFlags() async {
        let defaults = UserDefaults(suiteName: "test.flags.\(UUID())")!
        XCTAssertTrue(FeatureFlags.cachedIsOn(.widgetSnapshot, defaults: defaults))  // nothing stored
        XCTAssertFalse(FeatureFlags.cachedIsOn(.todayBrief, defaults: defaults))

        let store = FeatureFlags(defaults: defaults, fetch: { ["widget_snapshot": false, "today_brief": true] })
        await store.refresh()
        XCTAssertFalse(FeatureFlags.cachedIsOn(.widgetSnapshot, defaults: defaults))
        XCTAssertTrue(FeatureFlags.cachedIsOn(.todayBrief, defaults: defaults))
    }

    func testUnknownKeysIgnoredAndMissingKeysUseDefaults() async {
        let defaults = freshDefaults()
        let store = FeatureFlags(defaults: defaults, fetch: { ["some_future_flag": true, "event_radar": true] })
        await store.refresh()
        XCTAssertTrue(store.isOn(.eventRadar))
        XCTAssertTrue(store.isOn(.widgetSnapshot))  // missing -> default on
        XCTAssertFalse(store.isOn(.watchlistV2))    // missing -> default off
        XCTAssertTrue(FeatureFlags.cachedIsOn(.widgetSnapshot, defaults: defaults))
        XCTAssertFalse(FeatureFlags.cachedIsOn(.notifPrefsV2, defaults: defaults))
    }

    func testFailedRefreshIsRetriedNextTime() async {
        var fail = true
        var calls = 0
        let store = FeatureFlags(defaults: freshDefaults(), fetch: {
            calls += 1
            if fail { throw Offline() }
            return ["money_xray": true]
        })
        await store.refresh()
        fail = false
        await store.refresh()  // no success yet, so no throttle
        XCTAssertEqual(calls, 2)
        XCTAssertTrue(store.isOn(.moneyXray))
    }
}
