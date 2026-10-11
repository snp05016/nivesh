import Foundation

/// Shadows `Swift.print` for the whole app module so the many diagnostic
/// `print(...)` calls (some include tokens and user data) are compiled out of
/// release builds. Use os_log / Logger for anything that must ship.
nonisolated func print(_ items: Any..., separator: String = " ", terminator: String = "\n") {
    #if DEBUG
    Swift.print(items.map { "\($0)" }.joined(separator: separator), terminator: terminator)
    #endif
}
