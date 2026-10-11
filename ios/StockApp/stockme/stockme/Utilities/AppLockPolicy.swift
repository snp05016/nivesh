import Foundation
import LocalAuthentication

/// Pure decisions for the app lock, kept out of the view so they can be unit-tested.
/// The lock never fails open: if the device cannot authenticate, the app stays locked
/// and the lock screen offers Sign out instead.
enum AppLockPolicy {
    /// Face ID / Touch ID with the device passcode as fallback (covers biometry lockout).
    static let policy: LAPolicy = .deviceOwnerAuthentication

    /// Lock on cold launch only when a session exists to protect.
    static func shouldLockOnLaunch(isLoggedIn: Bool, timeout: BiometricTimeout) -> Bool {
        isLoggedIn && timeout != .never
    }

    /// Re-lock on return from background once the configured timeout has elapsed.
    /// `.immediately` always relocks, and a negative elapsed (wall clock moved backwards
    /// while backgrounded) counts as elapsed so a clock change cannot skip the lock.
    static func shouldRelock(isLoggedIn: Bool, timeout: BiometricTimeout, elapsed: TimeInterval) -> Bool {
        guard isLoggedIn, let seconds = timeout.seconds else { return false }
        return seconds == 0 || elapsed < 0 || elapsed >= seconds
    }

    /// Message shown on the lock screen when the device cannot authenticate at all.
    static func unavailableMessage(_ error: NSError?) -> String {
        if let error, error.domain == LAErrorDomain, error.code == LAError.Code.passcodeNotSet.rawValue {
            return "Set a device passcode in iOS Settings to use App Lock, or sign out."
        }
        return "Authentication is unavailable. Try again or sign out."
    }
}
