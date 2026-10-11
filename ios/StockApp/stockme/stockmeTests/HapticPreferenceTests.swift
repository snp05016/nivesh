import XCTest
@testable import stockme

/// UX-33: Settings > Haptic Feedback gates every HapticManager call.
final class HapticPreferenceTests: XCTestCase {

    private func freshDefaults() -> UserDefaults {
        UserDefaults(suiteName: UUID().uuidString)!
    }

    func testDefaultsToEnabled() {
        XCTAssertTrue(HapticManager.isEnabled(freshDefaults()))
    }

    func testDisabledWhenFalse() {
        let defaults = freshDefaults()
        defaults.set(false, forKey: HapticManager.enabledKey)
        XCTAssertFalse(HapticManager.isEnabled(defaults))
    }

    func testEnabledWhenTrue() {
        let defaults = freshDefaults()
        defaults.set(true, forKey: HapticManager.enabledKey)
        XCTAssertTrue(HapticManager.isEnabled(defaults))
    }
}
