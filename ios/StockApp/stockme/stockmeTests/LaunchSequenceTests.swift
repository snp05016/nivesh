import XCTest
@testable import stockme

/// UX-20: the splash plays once per install and never under Reduce Motion / Reduce Animations.
@MainActor
final class LaunchSequenceTests: XCTestCase {

    private func freshDefaults() -> UserDefaults {
        let suite = "LaunchSequenceTests-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        addTeardownBlock { defaults.removePersistentDomain(forName: suite) }
        return defaults
    }

    func testFirstLaunchAnimates() {
        XCTAssertTrue(LaunchSequenceView.shouldAnimate(hasSeenSplash: false, systemReduceMotion: false, defaults: freshDefaults()))
    }

    func testSecondLaunchSkips() {
        XCTAssertFalse(LaunchSequenceView.shouldAnimate(hasSeenSplash: true, systemReduceMotion: false, defaults: freshDefaults()))
    }

    func testSystemReduceMotionSkips() {
        XCTAssertFalse(LaunchSequenceView.shouldAnimate(hasSeenSplash: false, systemReduceMotion: true, defaults: freshDefaults()))
    }

    func testAppReduceAnimationsSkips() {
        let defaults = freshDefaults()
        defaults.set(true, forKey: "nivesh_reduceAnimations")
        XCTAssertFalse(LaunchSequenceView.shouldAnimate(hasSeenSplash: false, systemReduceMotion: false, defaults: defaults))
    }
}
