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
        case .darkImmersive:   return Color(red: 0.98, green: 0.97, blue: 0.95)  // warm beige — Reserve Bank bond paper
        case .chocolateBrown:  return Color(red: 0.91, green: 0.83, blue: 0.76)  // warm terracotta-brown tint
        case .greenishYellow:  return Color(red: 0.95, green: 0.96, blue: 0.86)  // chartreuse-sage tint
        case .fluorescentBlue: return Color(red: 0.91, green: 0.94, blue: 0.97)  // sky-blue tint
        case .lavender:        return Color(red: 0.94, green: 0.92, blue: 0.97)  // soft mauve tint
        case .brightYellow:    return Color(red: 0.97, green: 0.95, blue: 0.84)  // golden-wheat tint
        case .stoneGrey:       return Color(red: 0.93, green: 0.93, blue: 0.93)  // cool grey tint
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
        case .darkImmersive:   return Color(red: 0.38, green: 0.58, blue: 0.97)  // electric blue
        case .chocolateBrown:  return Color(red: 0.55, green: 0.27, blue: 0.07)  // deep chocolate
        case .greenishYellow:  return Color(red: 0.35, green: 0.55, blue: 0.15)  // forest green
        case .fluorescentBlue: return Color(red: 0.18, green: 0.42, blue: 0.85)  // royal blue
        case .lavender:        return Color(red: 0.50, green: 0.35, blue: 0.75)  // deep purple
        case .brightYellow:    return Color(red: 0.85, green: 0.65, blue: 0.05)  // amber gold
        case .stoneGrey:       return Color(red: 0.40, green: 0.40, blue: 0.42)  // charcoal
        }
    }

    var canvasDeep: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.066, green: 0.094, blue: 0.153) // #111827
        case .chocolateBrown:  return Color(red: 0.15, green: 0.09, blue: 0.06)
        case .greenishYellow:  return Color(red: 0.08, green: 0.10, blue: 0.06)
        case .fluorescentBlue: return Color(red: 0.04, green: 0.06, blue: 0.15)
        case .lavender:        return Color(red: 0.08, green: 0.06, blue: 0.15)
        case .brightYellow:    return Color(red: 0.12, green: 0.10, blue: 0.04)
        case .stoneGrey:       return Color(red: 0.08, green: 0.08, blue: 0.08)
        }
    }

    var canvasShadow: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.027, green: 0.043, blue: 0.070) // #070B12
        case .chocolateBrown:  return Color(red: 0.05, green: 0.03, blue: 0.02)
        case .greenishYellow:  return Color(red: 0.03, green: 0.04, blue: 0.02)
        case .fluorescentBlue: return Color(red: 0.01, green: 0.02, blue: 0.05)
        case .lavender:        return Color(red: 0.03, green: 0.02, blue: 0.05)
        case .brightYellow:    return Color(red: 0.04, green: 0.03, blue: 0.01)
        case .stoneGrey:       return Color(red: 0.02, green: 0.02, blue: 0.02)
        }
    }

    var inkPrimary: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.12, green: 0.12, blue: 0.14)  // deep ink black
        case .chocolateBrown:  return Color(red: 0.18, green: 0.10, blue: 0.05)  // espresso
        case .greenishYellow:  return Color(red: 0.08, green: 0.14, blue: 0.06)  // forest ink
        case .fluorescentBlue: return Color(red: 0.04, green: 0.10, blue: 0.22)  // midnight blue
        case .lavender:        return Color(red: 0.12, green: 0.06, blue: 0.22)  // deep violet
        case .brightYellow:    return Color(red: 0.18, green: 0.14, blue: 0.04)  // bronze ink
        case .stoneGrey:       return Color(red: 0.10, green: 0.10, blue: 0.10)  // charcoal ink
        }
    }

    var inkSecondary: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.28, green: 0.30, blue: 0.34)  // slate grey
        case .chocolateBrown:  return Color(red: 0.35, green: 0.22, blue: 0.14)  // warm brown
        case .greenishYellow:  return Color(red: 0.22, green: 0.30, blue: 0.18)  // sage green
        case .fluorescentBlue: return Color(red: 0.18, green: 0.24, blue: 0.38)  // steel blue
        case .lavender:        return Color(red: 0.28, green: 0.20, blue: 0.38)  // muted purple
        case .brightYellow:    return Color(red: 0.38, green: 0.30, blue: 0.15)  // olive brown
        case .stoneGrey:       return Color(red: 0.28, green: 0.28, blue: 0.30)  // mid grey
        }
    }

    var inkTertiary: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.45, green: 0.48, blue: 0.52)  // light slate
        case .chocolateBrown:  return Color(red: 0.50, green: 0.35, blue: 0.25)  // terracotta
        case .greenishYellow:  return Color(red: 0.38, green: 0.48, blue: 0.32)  // moss
        case .fluorescentBlue: return Color(red: 0.32, green: 0.40, blue: 0.55)  // sky slate
        case .lavender:        return Color(red: 0.45, green: 0.35, blue: 0.55)  // mauve grey
        case .brightYellow:    return Color(red: 0.55, green: 0.48, blue: 0.30)  // khaki
        case .stoneGrey:       return Color(red: 0.45, green: 0.45, blue: 0.48)  // silver
        }
    }
}

// MARK: - ThemeManager

@Observable
final class ThemeManager {
    static let shared = ThemeManager()

    var current: AppTheme {
        didSet {
            UserDefaults.standard.set(current.rawValue, forKey: "selectedTheme")
        }
    }

    private init() {
        let saved = UserDefaults.standard.string(forKey: "selectedTheme") ?? AppTheme.darkImmersive.rawValue
        self.current = AppTheme(rawValue: saved) ?? .darkImmersive
    }

    /// Explicit colour-scheme-aware accessors called from Theme.swift.
    func canvas(for scheme: ColorScheme) -> Color {
        scheme == .dark ? current.canvasDark : current.canvasLight
    }

    func accent(for scheme: ColorScheme) -> Color {
        scheme == .dark ? current.accentDark : current.accentLight
    }
}
