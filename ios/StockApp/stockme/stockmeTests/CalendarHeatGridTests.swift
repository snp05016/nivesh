import XCTest
@testable import stockme

/// IOSUI-20: heat-grid cells use local-day keys and colour by the daily move.
@MainActor
final class CalendarHeatGridTests: XCTestCase {

    private func snap(_ date: String, value: Double, pnl: Double) throws -> PortfolioValuationSnapshot {
        let json = #"{"date":"\#(date)","total_value":\#(value),"total_invested":100,"total_pnl":\#(pnl),"pnl_percent":\#(pnl),"nifty_close":null}"#
        return try JSONDecoder().decode(PortfolioValuationSnapshot.self, from: Data(json.utf8))
    }

    func testLocalMidnightKeysToSameDay() {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone.current
        let midnight = cal.date(from: DateComponents(year: 2026, month: 10, day: 8))!
        // ISO8601DateFormatter (UTC) gave "2026-10-07" here for IST users.
        XCTAssertEqual(WireDate.dayKey(midnight), "2026-10-08")
    }

    func testDailyChangeFromConsecutiveSnapshots() throws {
        let snaps = [
            try snap("2026-10-08", value: 99, pnl: -1),
            try snap("2026-10-06", value: 100, pnl: 0),
            try snap("2026-10-07", value: 101, pnl: 1),
        ]
        let changes = CalendarHeatGrid.dailyChangeByDate(snaps)
        XCTAssertNil(changes["2026-10-06"], "first day has no previous value")
        XCTAssertEqual(changes["2026-10-07"]!, 1.0, accuracy: 1e-9)
        XCTAssertEqual(changes["2026-10-08"]!, -2.0 / 101 * 100, accuracy: 1e-9)
    }

    func testEmptyAndSingleSnapshot() throws {
        XCTAssertTrue(CalendarHeatGrid.dailyChangeByDate([]).isEmpty)
        XCTAssertTrue(CalendarHeatGrid.dailyChangeByDate([try snap("2026-10-08", value: 100, pnl: 5)]).isEmpty)
    }
}
