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
        case .darkImmersive:   return Color(red: 0.122, green: 0.404, blue: 0.957) // #1F67F4 — deep electric blue (AA on canvas)
        case .chocolateBrown:  return Color(red: 0.55, green: 0.27, blue: 0.07)  // deep chocolate
        case .greenishYellow:  return Color(red: 0.306, green: 0.478, blue: 0.129) // #4E7A21 — forest green
        case .fluorescentBlue: return Color(red: 0.153, green: 0.404, blue: 0.847) // #2767D8 — royal blue
        case .lavender:        return Color(red: 0.490, green: 0.337, blue: 0.745) // #7D56BE — deep purple
        case .brightYellow:    return Color(red: 0.537, green: 0.412, blue: 0.031) // #896908 — dark amber gold
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

    // Every ink and accent below keeps WCAG AA (>= 4.5:1) on its canvas;
    // enforced by stockmeTests/ThemeContrastTests.swift.

    // MARK: - Ink — Dark mode (light text on dark backgrounds)

    var inkPrimaryDark: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.91, green: 0.92, blue: 0.94)  // #E8ECF0 near-white
        case .chocolateBrown:  return Color(red: 0.93, green: 0.88, blue: 0.84)  // warm cream
        case .greenishYellow:  return Color(red: 0.89, green: 0.94, blue: 0.85)  // pale chartreuse
        case .fluorescentBlue: return Color(red: 0.85, green: 0.91, blue: 0.97)  // pale sky
        case .lavender:        return Color(red: 0.92, green: 0.88, blue: 0.97)  // pale mauve
        case .brightYellow:    return Color(red: 0.96, green: 0.93, blue: 0.82)  // pale gold
        case .stoneGrey:       return Color(red: 0.91, green: 0.92, blue: 0.93)  // pale silver
        }
    }

    var inkSecondaryDark: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.53, green: 0.60, blue: 0.67)  // #8899AA
        case .chocolateBrown:  return Color(red: 0.616, green: 0.494, blue: 0.392) // #9D7E64 — warm tan
        case .greenishYellow:  return Color(red: 0.50, green: 0.58, blue: 0.42)  // sage
        case .fluorescentBlue: return Color(red: 0.45, green: 0.55, blue: 0.70)  // steel
        case .lavender:        return Color(red: 0.55, green: 0.48, blue: 0.68)  // mauve
        case .brightYellow:    return Color(red: 0.65, green: 0.58, blue: 0.40)  // khaki
        case .stoneGrey:       return Color(red: 0.55, green: 0.57, blue: 0.60)  // mid silver
        }
    }

    var inkTertiaryDark: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.431, green: 0.514, blue: 0.600) // #6E8399
        case .chocolateBrown:  return Color(red: 0.631, green: 0.482, blue: 0.380) // #A17B61 — muted terracotta
        case .greenishYellow:  return Color(red: 0.412, green: 0.541, blue: 0.361) // #698A5C — muted moss
        case .fluorescentBlue: return Color(red: 0.376, green: 0.494, blue: 0.663) // #607EA9 — muted sky
        case .lavender:        return Color(red: 0.537, green: 0.451, blue: 0.671) // #8973AB — muted mauve
        case .brightYellow:    return Color(red: 0.592, green: 0.494, blue: 0.345) // #977E58 — muted khaki
        case .stoneGrey:       return Color(red: 0.475, green: 0.498, blue: 0.533) // #797F88 — dim silver
        }
    }

    // MARK: - Ink — Light mode (dark text on light backgrounds)

    var inkPrimaryLight: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.10, green: 0.11, blue: 0.13)  // #1A1C20 near-black
        case .chocolateBrown:  return Color(red: 0.18, green: 0.10, blue: 0.06)  // espresso
        case .greenishYellow:  return Color(red: 0.12, green: 0.18, blue: 0.08)  // forest
        case .fluorescentBlue: return Color(red: 0.06, green: 0.12, blue: 0.24)  // midnight
        case .lavender:        return Color(red: 0.14, green: 0.08, blue: 0.24)  // deep violet
        case .brightYellow:    return Color(red: 0.20, green: 0.16, blue: 0.06)  // bronze
        case .stoneGrey:       return Color(red: 0.12, green: 0.12, blue: 0.13)  // charcoal
        }
    }

    var inkSecondaryLight: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.27, green: 0.30, blue: 0.34)  // slate
        case .chocolateBrown:  return Color(red: 0.35, green: 0.22, blue: 0.15)  // warm brown
        case .greenishYellow:  return Color(red: 0.22, green: 0.32, blue: 0.18)  // sage dark
        case .fluorescentBlue: return Color(red: 0.18, green: 0.25, blue: 0.40)  // steel blue
        case .lavender:        return Color(red: 0.28, green: 0.20, blue: 0.40)  // muted purple
        case .brightYellow:    return Color(red: 0.38, green: 0.30, blue: 0.16)  // olive
        case .stoneGrey:       return Color(red: 0.28, green: 0.29, blue: 0.31)  // mid grey
        }
    }

    var inkTertiaryLight: Color {
        switch self {
        case .darkImmersive:   return Color(red: 0.416, green: 0.443, blue: 0.478) // #6A717A — slate
        case .chocolateBrown:  return Color(red: 0.467, green: 0.341, blue: 0.251) // #775740 — terracotta
        case .greenishYellow:  return Color(red: 0.369, green: 0.459, blue: 0.322) // #5E7552 — moss
        case .fluorescentBlue: return Color(red: 0.333, green: 0.431, blue: 0.557) // #556E8E — sky slate
        case .lavender:        return Color(red: 0.48, green: 0.38, blue: 0.58)  // mauve grey
        case .brightYellow:    return Color(red: 0.494, green: 0.424, blue: 0.298) // #7E6C4C — khaki
        case .stoneGrey:       return Color(red: 0.408, green: 0.424, blue: 0.443) // #686C71 — silver
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

    func canvasDeep(for scheme: ColorScheme) -> Color {
        scheme == .dark ? current.canvasDeep : current.canvasLight.opacity(0.92)
    }

    func canvasShadow(for scheme: ColorScheme) -> Color {
        scheme == .dark ? current.canvasShadow : current.canvasLight.opacity(0.82)
    }

    func inkPrimary(for scheme: ColorScheme) -> Color {
        scheme == .dark ? current.inkPrimaryDark : current.inkPrimaryLight
    }

    func inkSecondary(for scheme: ColorScheme) -> Color {
        scheme == .dark ? current.inkSecondaryDark : current.inkSecondaryLight
    }

    func inkTertiary(for scheme: ColorScheme) -> Color {
        scheme == .dark ? current.inkTertiaryDark : current.inkTertiaryLight
    }

    func accent(for scheme: ColorScheme) -> Color {
        scheme == .dark ? current.accentDark : current.accentLight
    }
}
