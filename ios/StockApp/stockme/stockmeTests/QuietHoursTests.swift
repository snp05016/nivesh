import XCTest
@testable import stockme

/// IOSCORE-35: quiet-hour day indices match QuietHoursView (0 = Sun) and an overnight
/// window belongs to the day it started.
@MainActor
final class QuietHoursTests: XCTestCase {

    private let night = (start: 79200.0, end: 25200.0) // 22:00-07:00

    private var calendar: Calendar {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "Asia/Kolkata")!
        return cal
    }

    /// 2026-10-11 is a Sunday; `dayOffset` 0...6 walks Sun...Sat.
    private func date(dayOffset: Int, hour: Int, minute: Int = 0) -> Date {
        calendar.date(from: DateComponents(year: 2026, month: 10, day: 11 + dayOffset, hour: hour, minute: minute))!
    }

    private func quiet(_ now: Date, start: Double, end: Double, days: Set<Int>) -> Bool {
        NotificationManager.isInQuietHours(now: now, calendar: calendar, startSecs: start, endSecs: end, activeDays: days)
    }

    func testFixtureStartsOnSunday() {
        XCTAssertEqual(calendar.component(.weekday, from: date(dayOffset: 0, hour: 12)), 1)
    }

    func testSundayIsZero() {
        let sunday23 = date(dayOffset: 0, hour: 23)
        XCTAssertTrue(quiet(sunday23, start: night.start, end: night.end, days: [0]))
        XCTAssertFalse(quiet(sunday23, start: night.start, end: night.end, days: [1]))
    }

    func testMondayIsOne() {
        let monday23 = date(dayOffset: 1, hour: 23)
        XCTAssertTrue(quiet(monday23, start: night.start, end: night.end, days: [1]))
        XCTAssertFalse(quiet(monday23, start: night.start, end: night.end, days: [0]))
    }

    func testOvernightAttributesToStartDay() {
        let saturday02 = date(dayOffset: 6, hour: 2)
        XCTAssertTrue(quiet(saturday02, start: night.start, end: night.end, days: [5]), "Friday night's window")
        XCTAssertFalse(quiet(saturday02, start: night.start, end: night.end, days: [6]))
    }

    func testSameDayWindow() {
        let (start, end) = (46800.0, 50400.0) // 13:00-14:00
        XCTAssertTrue(quiet(date(dayOffset: 0, hour: 13, minute: 30), start: start, end: end, days: [0]))
        XCTAssertFalse(quiet(date(dayOffset: 0, hour: 14), start: start, end: end, days: [0]))
        XCTAssertFalse(quiet(date(dayOffset: 0, hour: 12, minute: 59), start: start, end: end, days: [0]))
    }

    func testStartEqualsEndDisabled() {
        XCTAssertFalse(quiet(date(dayOffset: 0, hour: 0), start: 0, end: 0, days: Set(0...6)))
        XCTAssertFalse(quiet(date(dayOffset: 0, hour: 22), start: 79200, end: 79200, days: Set(0...6)))
    }

    func testOutsideWindowIsNotQuiet() {
        XCTAssertFalse(quiet(date(dayOffset: 2, hour: 12), start: night.start, end: night.end, days: Set(0...6)))
    }

    func test7DayMatrix() {
        for offset in 0..<7 {
            let at23 = date(dayOffset: offset, hour: 23)
            for day in 0..<7 {
                XCTAssertEqual(
                    quiet(at23, start: night.start, end: night.end, days: [day]),
                    day == offset,
                    "offset \(offset), active day \(day)"
                )
            }
        }
    }
}
