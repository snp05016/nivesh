import XCTest
@testable import stockme

@MainActor
final class MotionPolicyTests: XCTestCase {

    private func freshDefaults() -> UserDefaults {
        let suite = "MotionPolicyTests-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        addTeardownBlock { defaults.removePersistentDomain(forName: suite) }
        return defaults
    }

    func testReducedWhenSystemFlagOn() {
        XCTAssertTrue(MotionPolicy.isReduced(systemReduceMotion: true, defaults: freshDefaults()))
    }

    func testReducedWhenAppSettingOn() {
        let defaults = freshDefaults()
        defaults.set(true, forKey: "nivesh_reduceAnimations")
        XCTAssertTrue(MotionPolicy.isReduced(systemReduceMotion: false, defaults: defaults))
    }

    func testNotReducedByDefault() {
        XCTAssertFalse(MotionPolicy.isReduced(systemReduceMotion: false, defaults: freshDefaults()))
    }
}
