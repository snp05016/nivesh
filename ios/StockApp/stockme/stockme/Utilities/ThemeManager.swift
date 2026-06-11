import SwiftUI

// MARK: - AppTheme

/// Seven theme presets based on Indian rupee banknote series colours.
/// Persisted in UserDefaults via @AppStorage.
enum AppTheme: String, CaseIterable, Codable {
    case darkImmersive  = "dark_immersive"
    case chocolateBrown = "chocolate_brown"
    case greenishYellow = "greenish_yellow"
    case fluorescentBlue = "fluorescent_blue"
    case lavender       = "lavender"
    case brightYellow   = "bright_yellow"
    case stoneGrey      = "stone_grey"

    var displayName: String {
        switch self {
        case .darkImmersive:   return "Dark Immersive"
        case .chocolateBrown:  return "₹10 · Chocolate Brown"
        case .greenishYellow:  return "₹20 · Greenish Yellow"
        case .fluorescentBlue: return "₹50 · Fluorescent Blue"
        case .lavender:        return "₹100 · Lavender"
        case .brightYellow:    return "₹200 · Bright Yellow"
        case .stoneGrey:       return "₹500 · Stone Grey"
        }
    }

    /// Swatch colour shown ONLY in the settings picker.
    var swatchColor: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.83, green: 0.66, blue: 0.09)
        case .chocolateBrown:  return Color(red: 0.55, green: 0.27, blue: 0.07)
        case .greenishYellow:  return Color(red: 0.60, green: 0.72, blue: 0.13)
        case .fluorescentBlue: return Color(red: 0.00, green: 0.40, blue: 0.80)
        case .lavender:        return Color(red: 0.59, green: 0.48, blue: 0.71)
        case .brightYellow:    return Color(red: 1.00, green: 0.84, blue: 0.00)
        case .stoneGrey:       return Color(red: 0.50, green: 0.50, blue: 0.50)
        }
    }

    var canvasDark: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.035, green: 0.043, blue: 0.063) // #090B10 — deep navy-black
        case .chocolateBrown:  return Color(red: 0.10, green: 0.06, blue: 0.04)
        case .greenishYellow:  return Color(red: 0.05, green: 0.07, blue: 0.04)
        case .fluorescentBlue: return Color(red: 0.02, green: 0.04, blue: 0.10)
        case .lavender:        return Color(red: 0.05, green: 0.04, blue: 0.10)
        case .brightYellow:    return Color(red: 0.08, green: 0.07, blue: 0.02)
        case .stoneGrey:       return Color(red: 0.05, green: 0.05, blue: 0.05)
        }
    }

    var canvasLight: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.96, green: 0.94, blue: 0.91)
        case .chocolateBrown:  return Color(red: 0.95, green: 0.92, blue: 0.88)
        case .greenishYellow:  return Color(red: 0.95, green: 0.96, blue: 0.90)
        case .fluorescentBlue: return Color(red: 0.93, green: 0.95, blue: 0.98)
        case .lavender:        return Color(red: 0.95, green: 0.94, blue: 0.97)
        case .brightYellow:    return Color(red: 0.97, green: 0.96, blue: 0.89)
        case .stoneGrey:       return Color(red: 0.94, green: 0.94, blue: 0.93)
        }
    }

    var accentDark: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.357, green: 0.565, blue: 0.965) // #5B90F6 — electric blue
        case .chocolateBrown:  return Color(red: 0.55, green: 0.65, blue: 0.95)    // warm blue
        case .greenishYellow:  return Color(red: 0.30, green: 0.85, blue: 0.65)    // teal
        case .fluorescentBlue: return Color(red: 0.20, green: 0.55, blue: 1.00)    // pure blue
        case .lavender:        return Color(red: 0.70, green: 0.55, blue: 0.95)    // purple-blue
        case .brightYellow:    return Color(red: 0.95, green: 0.85, blue: 0.20)    // yellow-gold
        case .stoneGrey:       return Color(red: 0.65, green: 0.70, blue: 0.80)    // blue-grey
        }
    }

    var accentLight: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.357, green: 0.565, blue: 0.965)
        case .chocolateBrown:  return Color(red: 0.45, green: 0.55, blue: 0.85)
        case .greenishYellow:  return Color(red: 0.25, green: 0.72, blue: 0.55)
        case .fluorescentBlue: return Color(red: 0.15, green: 0.45, blue: 0.90)
        case .lavender:        return Color(red: 0.60, green: 0.45, blue: 0.85)
        case .brightYellow:    return Color(red: 0.85, green: 0.75, blue: 0.15)
        case .stoneGrey:       return Color(red: 0.55, green: 0.60, blue: 0.70)
        }
    }
}

// MARK: - ThemeManager

@Observable
final class ThemeManager {
    static let shared = ThemeManager()

    @ObservationIgnored @AppStorage("selectedTheme") var selectedTheme: String = AppTheme.darkImmersive.rawValue

    var current: AppTheme {
        get { AppTheme(rawValue: selectedTheme) ?? .darkImmersive }
        set { selectedTheme = newValue.rawValue }
    }

    /// Explicit colour-scheme-aware accessors called from Theme.swift.
    func canvas(for scheme: ColorScheme) -> Color {
        scheme == .dark ? current.canvasDark : current.canvasLight
    }

    func accent(for scheme: ColorScheme) -> Color {
        scheme == .dark ? current.accentDark : current.accentLight
    }
}
