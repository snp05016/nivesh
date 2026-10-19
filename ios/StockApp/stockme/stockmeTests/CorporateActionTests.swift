import XCTest
@testable import stockme

@MainActor
final class CorporateActionTests: XCTestCase {

    private func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T {
        try JSONDecoder().decode(type, from: Data(json.utf8))
    }

    private func itemJSON(id: Int = 7, status: String = "pending", group: String = #""group_id":3,"group_name":"Core Holdings""#,
                          undoUntil: String = "null") -> String {
        """
        {"id":\(id),"ticker":"RELIANCE",\(group),"action_label":"Share split or bonus","ratio":2.0,
         "ratio_text":"1 share became 2","ex_date":"2026-03-02","status":"\(status)","shares_before":100.0,
         "shares_after":200.0,"nse_confirmed":true,"source":"Yahoo Finance corporate actions",
         "decided_at":null,"undo_until":\(undoUntil)}
        """
    }

    private func item(status: String, undoUntil: String?) throws -> CorporateActionItem {
        let until = undoUntil.map { "\"\($0)\"" } ?? "null"
        return try decode(CorporateActionItem.self, itemJSON(status: status, undoUntil: until))
    }

    func testMutationResponseDecodesWithAndWithoutHolding() throws {
        let with = try decode(CorporateActionMutationResponse.self, """
        {"item":\(itemJSON(status: "applied")),"holding":{"ticker":"RELIANCE","shares":200.0,"avg_price":1000.0}}
        """)
        XCTAssertEqual(with.holding?.shares, 200)
        XCTAssertEqual(with.holding?.avgPrice, 1000)
        XCTAssertEqual(with.item.status, "applied")

        let without = try decode(CorporateActionMutationResponse.self, """
        {"item":\(itemJSON(status: "dismissed")),"holding":null}
        """)
        XCTAssertNil(without.holding)
    }

    func testListDecodesWithNilGroupFields() throws {
        let list = try decode(CorporateActionList.self, """
        {"items":[\(itemJSON(group: #""group_id":null,"group_name":null"#))]}
        """)
        XCTAssertEqual(list.items.count, 1)
        XCTAssertNil(list.items[0].groupId)
        XCTAssertNil(list.items[0].groupName)
        XCTAssertEqual(list.items[0].ratioText, "1 share became 2")
        XCTAssertEqual(list.items[0].nseConfirmed, true)
    }

    func testIsFeatureDisabled() {
        let disabled = NetworkError.fetchFailed(
            endpoint: "/api/v1/portfolio/corporate-actions", status: 404,
            body: #"{"detail":{"code":"FEATURE_DISABLED","feature":"data_corp_actions_confirm"}}"#)
        XCTAssertTrue(CorporateActionsViewModel.isFeatureDisabled(disabled))

        let notFound = NetworkError.fetchFailed(
            endpoint: "x", status: 404, body: #"{"detail":{"code":"NOT_FOUND"}}"#)
        XCTAssertFalse(CorporateActionsViewModel.isFeatureDisabled(notFound))

        let server = NetworkError.fetchFailed(endpoint: "x", status: 500, body: "FEATURE_DISABLED")
        XCTAssertFalse(CorporateActionsViewModel.isFeatureDisabled(server))
        XCTAssertFalse(CorporateActionsViewModel.isFeatureDisabled(NetworkError.invalidResponse))
    }

    func testPendingCountCountsPendingOnly() throws {
        let items = [
            try decode(CorporateActionItem.self, itemJSON(id: 1, status: "pending")),
            try decode(CorporateActionItem.self, itemJSON(id: 2, status: "applied")),
            try decode(CorporateActionItem.self, itemJSON(id: 3, status: "dismissed")),
            try decode(CorporateActionItem.self, itemJSON(id: 4, status: "pending")),
        ]
        XCTAssertEqual(CorporateActionsViewModel(items: items).pendingCount, 2)
    }

    func testCanUndoOnTheUndoUntilDayButNotAfter() throws {
        // 2026-04-01 12:00 IST
        let onTheDay = try XCTUnwrap(CorporateActionDates.parse("2026-04-01T06:30:00"))
        let nextDay = onTheDay.addingTimeInterval(24 * 3600)

        for status in ["applied", "dismissed"] {
            let candidate = try item(status: status, undoUntil: "2026-04-01T10:00:00")
            XCTAssertTrue(candidate.canUndo(today: onTheDay), "\(status) on the undo_until day")
            XCTAssertFalse(candidate.canUndo(today: nextDay), "\(status) the next day")
        }
        let pending = try item(status: "pending", undoUntil: "2026-04-01T10:00:00")
        XCTAssertFalse(pending.canUndo(today: onTheDay))
        let noDeadline = try item(status: "applied", undoUntil: nil)
        XCTAssertFalse(noDeadline.canUndo(today: onTheDay))
    }

    func testUndoDayIsAnISTCalendarDay() throws {
        // 20:00 UTC on 31 Mar is 01:30 IST on 1 Apr: still inside an undo_until of 1 Apr.
        let late = try XCTUnwrap(CorporateActionDates.parse("2026-03-31T20:00:00"))
        let candidate = try item(status: "applied", undoUntil: "2026-04-01")
        XCTAssertTrue(candidate.canUndo(today: late))
    }

    func testDayMonthFormatting() {
        XCTAssertEqual(CorporateActionDates.dayMonth("2026-10-09T06:00:00"), "9 Oct")
        XCTAssertNil(CorporateActionDates.dayMonth(nil))
        XCTAssertEqual(CorporateActionNumber.shares(100), "100")
        XCTAssertEqual(CorporateActionNumber.shares(12.5), "12.5")
    }
}
