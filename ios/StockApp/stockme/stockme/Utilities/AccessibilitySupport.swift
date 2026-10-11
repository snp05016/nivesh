import SwiftUI
import UIKit

/// Single source of truth for "should motion be reduced": the system
/// Reduce Motion setting OR the in-app Settings > Reduce Animations toggle.
/// Every infinite (`repeatForever`) animation must check this before starting.
enum MotionPolicy {
    static func isReduced(
        systemReduceMotion: Bool = UIAccessibility.isReduceMotionEnabled,
        defaults: UserDefaults = .standard
    ) -> Bool {
        systemReduceMotion || defaults.bool(forKey: "nivesh_reduceAnimations")
    }
}

enum A11y {
    /// Speaks a transient message (toast / banner) to VoiceOver users.
    static func announce(_ text: String) {
        AccessibilityNotification.Announcement(text).post()
    }
}
