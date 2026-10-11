import XCTest
import LocalAuthentication
@testable import stockme

@MainActor
final class AppLockPolicyTests: XCTestCase {

    func testNeverLocksOnLaunchWhenLoggedOut() {
        for timeout in BiometricTimeout.allCases {
            XCTAssertFalse(AppLockPolicy.shouldLockOnLaunch(isLoggedIn: false, timeout: timeout))
        }
    }

    func testLocksOnLaunchWhenLoggedInUnlessNever() {
        XCTAssertTrue(AppLockPolicy.shouldLockOnLaunch(isLoggedIn: true, timeout: .immediately))
        XCTAssertFalse(AppLockPolicy.shouldLockOnLaunch(isLoggedIn: true, timeout: .never))
    }

    func testRelockRespectsTimeout() {
        XCTAssertFalse(AppLockPolicy.shouldRelock(isLoggedIn: true, timeout: .oneMin, elapsed: 30))
        XCTAssertTrue(AppLockPolicy.shouldRelock(isLoggedIn: true, timeout: .oneMin, elapsed: 61))
        XCTAssertTrue(AppLockPolicy.shouldRelock(isLoggedIn: true, timeout: .immediately, elapsed: 0))
        XCTAssertFalse(AppLockPolicy.shouldRelock(isLoggedIn: true, timeout: .never, elapsed: 10_000))
        XCTAssertFalse(AppLockPolicy.shouldRelock(isLoggedIn: false, timeout: .immediately, elapsed: 10_000))
    }

    func testRelockWhenClockMovesBackwards() {
        XCTAssertTrue(AppLockPolicy.shouldRelock(isLoggedIn: true, timeout: .immediately, elapsed: -100))
        XCTAssertTrue(AppLockPolicy.shouldRelock(isLoggedIn: true, timeout: .fiveMin, elapsed: -100))
    }

    func testPolicyHasPasscodeFallback() {
        XCTAssertEqual(AppLockPolicy.policy, .deviceOwnerAuthentication)
    }

    func testUnavailableMessageForMissingPasscode() {
        let error = NSError(domain: LAErrorDomain, code: LAError.Code.passcodeNotSet.rawValue)
        XCTAssertTrue(AppLockPolicy.unavailableMessage(error).contains("passcode"))
        XCTAssertTrue(AppLockPolicy.unavailableMessage(nil).contains("sign out"))
    }
}
