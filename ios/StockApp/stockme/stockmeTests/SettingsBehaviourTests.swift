import XCTest
@testable import stockme

/// UX-18: Settings values must map to the behaviour they promise.
@MainActor
final class SettingsBehaviourTests: XCTestCase {

    private let densityKey = "nivesh_layoutDensity"
    private var savedDensity: Any?

    override func setUp() {
        super.setUp()
        savedDensity = UserDefaults.standard.object(forKey: densityKey)
    }

    override func tearDown() {
        if let savedDensity {
            UserDefaults.standard.set(savedDensity, forKey: densityKey)
        } else {
            UserDefaults.standard.removeObject(forKey: densityKey)
        }
        super.tearDown()
    }

    func testSpaciousAndComfortableWidenSpacing() {
        // Settings offers "Spacious"; "Comfortable" is the legacy stored value.
        for value in ["Spacious", "Comfortable"] {
            UserDefaults.standard.set(value, forKey: densityKey)
            XCTAssertEqual(Theme.spacingMultiplier, 1.25, accuracy: 0.001, value)
        }
        UserDefaults.standard.set("Compact", forKey: densityKey)
        XCTAssertEqual(Theme.spacingMultiplier, 0.75, accuracy: 0.001)
    }

    func testQuietHoursWeekdayStartsAtSunday() {
        // Calendar: 1 = Sunday. QuietHoursView: 0 = "Sun".
        XCTAssertEqual(NotificationManager.quietHoursWeekday(fromCalendarWeekday: 1), 0)
        XCTAssertEqual(NotificationManager.quietHoursWeekday(fromCalendarWeekday: 2), 1)
        XCTAssertEqual(NotificationManager.quietHoursWeekday(fromCalendarWeekday: 7), 6)
    }
}
