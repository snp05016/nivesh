# DENOMINATION COLOR PALETTE FIX — Dark & Light Mode

Paste this entire message into Claude Code. Execute without asking questions.

---

## THE PROBLEM

`AppTheme` (in ThemeManager.swift) defines only ONE color for semantic tokens like `inkPrimary`, `inkSecondary`, `inkTertiary`, `accentDark`, `accentLight`.

But the app operates in both dark AND light mode. Currently:
- In dark mode: dark canvas (#090B10) + dark ink (#1F1F24) = **invisible text** 
- In light mode: light canvas (#FAF8F2) + dark ink (#1F1F24) = readable, but accents and other tokens are wrong

Every denomination theme (₹10 through ₹2000) has the same bug — one color value where two are needed.

---

## THE FIX: Dual-Mode Semantic Tokens

Every AppTheme must define BOTH dark and light variants for each semantic token:

| Token | Dark Mode (bg=dark) | Light Mode (bg=light) |
|-------|---------------------|----------------------|
| `canvasDark` | Near-black tinted with note color | NOT USED (use canvasLight) |
| `canvasLight` | NOT USED (use canvasDark) | Near-white tinted with note color |
| `canvasDeep` | Slightly lighter than canvasDark (for cards) | Slightly darker than canvasLight (for cards) |
| `canvasShadow` | Darker than canvasDark (for depth) | Shadow grey |
| `inkPrimary` | **NEEDS: light text** (#E8ECF0) | **NEEDS: dark text** (#1A1C20) — CURRENTLY DEFINED |
| `inkSecondary` | **NEEDS: medium-light** (#8899AA) | **NEEDS: medium-dark** (#445566) |
| `inkTertiary` | **NEEDS: dim** (#556677) | **NEEDS: grey** (#778899) |
| `accentDark` | Vibrant note-color accent | Muted note-color accent |
| `accentLight` | Muted note-color accent | Vibrant note-color accent |

---

## IMPLEMENTATION: 3 files

### FILE 1: ThemeManager.swift — Add dark/light variants to AppTheme

Replace the current single-value properties with dual-mode pairs:

```swift
// REMOVE the existing single inkPrimary, inkSecondary, inkTertiary properties
// REPLACE with:

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

var inkSecondaryDark: Color {
    switch self {
    case .darkImmersive:   return Color(red: 0.53, green: 0.60, blue: 0.67)  // #8899AA
    case .chocolateBrown:  return Color(red: 0.60, green: 0.48, blue: 0.38)  // warm tan
    case .greenishYellow:  return Color(red: 0.50, green: 0.58, blue: 0.42)  // sage
    case .fluorescentBlue: return Color(red: 0.45, green: 0.55, blue: 0.70)  // steel
    case .lavender:        return Color(red: 0.55, green: 0.48, blue: 0.68)  // mauve
    case .brightYellow:    return Color(red: 0.65, green: 0.58, blue: 0.40)  // khaki
    case .stoneGrey:       return Color(red: 0.55, green: 0.57, blue: 0.60)  // mid silver
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

var inkTertiaryDark: Color {
    switch self {
    case .darkImmersive:   return Color(red: 0.33, green: 0.40, blue: 0.47)  // #556677
    case .chocolateBrown:  return Color(red: 0.42, green: 0.32, blue: 0.25)  // muted terracotta
    case .greenishYellow:  return Color(red: 0.32, green: 0.42, blue: 0.28)  // muted moss
    case .fluorescentBlue: return Color(red: 0.28, green: 0.38, blue: 0.52)  // muted sky
    case .lavender:        return Color(red: 0.38, green: 0.30, blue: 0.50)  // muted mauve
    case .brightYellow:    return Color(red: 0.48, green: 0.40, blue: 0.28)  // muted khaki
    case .stoneGrey:       return Color(red: 0.40, green: 0.42, blue: 0.45)  // dim silver
    }
}

var inkTertiaryLight: Color {
    switch self {
    case .darkImmersive:   return Color(red: 0.45, green: 0.48, blue: 0.52)  // light slate
    case .chocolateBrown:  return Color(red: 0.52, green: 0.38, blue: 0.28)  // terracotta
    case .greenishYellow:  return Color(red: 0.40, green: 0.50, blue: 0.35)  // moss
    case .fluorescentBlue: return Color(red: 0.35, green: 0.45, blue: 0.58)  // sky slate
    case .lavender:        return Color(red: 0.48, green: 0.38, blue: 0.58)  // mauve grey
    case .brightYellow:    return Color(red: 0.58, green: 0.50, blue: 0.35)  // khaki
    case .stoneGrey:       return Color(red: 0.48, green: 0.50, blue: 0.52)  // silver
    }
}
```

**Keep** `canvasDark`, `canvasLight`, `canvasDeep`, `canvasShadow`, `accentDark`, `accentLight` as they currently are — those are already correct.

**REMOVE** the old single-value `inkPrimary`, `inkSecondary`, `inkTertiary` properties from AppTheme.

### FILE 2: ThemeManager.swift — Add scheme-aware accessor methods

Add these methods to `ThemeManager`:

```swift
func inkPrimary(for scheme: ColorScheme) -> Color {
    scheme == .dark ? current.inkPrimaryDark : current.inkPrimaryLight
}

func inkSecondary(for scheme: ColorScheme) -> Color {
    scheme == .dark ? current.inkSecondaryDark : current.inkSecondaryLight
}

func inkTertiary(for scheme: ColorScheme) -> Color {
    scheme == .dark ? current.inkTertiaryDark : current.inkTertiaryLight
}
```

### FILE 3: Theme.swift — Update static vars to be scheme-aware

The current Theme.swift static vars always return the same value regardless of light/dark. They need to read the system color scheme.

Replace:

```swift
static var inkPrimary: Color { ThemeManager.shared.current.inkPrimary }
static var inkSecondary: Color { ThemeManager.shared.current.inkSecondary }
static var inkTertiary: Color { ThemeManager.shared.current.inkTertiary }
```

With SwiftUI environment-aware versions. Since `Theme` is an enum and can't use `@Environment`, use `UITraitCollection`:

```swift
static var inkPrimary: Color {
    let isDark = UITraitCollection.current.userInterfaceStyle == .dark
    return ThemeManager.shared.inkPrimary(for: isDark ? .dark : .light)
}

static var inkSecondary: Color {
    let isDark = UITraitCollection.current.userInterfaceStyle == .dark
    return ThemeManager.shared.inkSecondary(for: isDark ? .dark : .light)
}

static var inkTertiary: Color {
    let isDark = UITraitCollection.current.userInterfaceStyle == .dark
    return ThemeManager.shared.inkTertiary(for: isDark ? .dark : .light)
}
```

Also update `canvas`, `canvasDeep`, `canvasShadow`, `securityGold`, and `securityGoldLight` the same way:

```swift
static var canvas: Color {
    let isDark = UITraitCollection.current.userInterfaceStyle == .dark
    return isDark ? ThemeManager.shared.current.canvasDark : ThemeManager.shared.current.canvasLight
}

static var canvasDeep: Color {
    let isDark = UITraitCollection.current.userInterfaceStyle == .dark
    return isDark ? ThemeManager.shared.current.canvasDeep : ThemeManager.shared.current.canvasLight.opacity(0.95)
}

static var canvasShadow: Color {
    let isDark = UITraitCollection.current.userInterfaceStyle == .dark
    return isDark ? ThemeManager.shared.current.canvasShadow : Color.black.opacity(0.06)
}

static var securityGold: Color {
    let isDark = UITraitCollection.current.userInterfaceStyle == .dark
    return isDark ? ThemeManager.shared.current.accentDark : ThemeManager.shared.current.accentLight
}

static var securityGoldLight: Color {
    let isDark = UITraitCollection.current.userInterfaceStyle == .dark
    return isDark ? ThemeManager.shared.current.accentLight : ThemeManager.shared.current.accentDark
}
```

### FILE 4: DenominationBackground.swift — Render the denomination tint

Currently `DenominationBackground` only shows a flat canvas color. It should show the denomination's signature tint as a subtle gradient overlay. Replace the `body` with:

```swift
var body: some View {
    let isDark = colorScheme == .dark
    let baseColor = isDark ? currentTheme.canvasDark : currentTheme.canvasLight
    
    ZStack {
        baseColor
            .ignoresSafeArea()
        
        // Subtle diagonal gradient with the note's signature color
        LinearGradient(
            stops: [
                .init(color: tint.opacity(isDark ? 0.06 : 0.12), location: 0),
                .init(color: tint.opacity(isDark ? 0.02 : 0.04), location: 0.5),
                .init(color: .clear, location: 1),
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
        .ignoresSafeArea()
        .allowsHitTesting(false)
    }
    .animation(.easeInOut(duration: 0.6), value: selectedTheme)
}
```

### FILE 5: Theme.swift NoteTint — Add light-mode tints

The `NoteTint` colors are dark-mode fixed hex values. They need light-mode equivalents that are darker/more saturated (since on a light background, the same pale tint would wash out).

Replace the NoteTint enum with:

```swift
enum NoteTint {
    // Dark mode tints (subtle on dark backgrounds)
    private static let tenDark:        Color = Color(uiColor("8B5A42"))  // ₹10 Chocolate Brown
    private static let twentyDark:     Color = Color(uiColor("B8C840"))  // ₹20 Greenish Yellow
    private static let fiftyDark:      Color = Color(uiColor("3A72CC"))  // ₹50 Fluorescent Blue
    private static let hundredDark:    Color = Color(uiColor("9080C0"))  // ₹100 Lavender
    private static let twoHundredDark: Color = Color(uiColor("C8A800"))  // ₹200 Bright Yellow
    private static let fiveHundredDark:Color = Color(uiColor("7A8E8E"))  // ₹500 Stone Grey
    private static let twoThousandDark:Color = Color(uiColor("C050A0"))  // ₹2000 Magenta
    
    // Light mode tints (darker/more saturated for light backgrounds)
    private static let tenLight:        Color = Color(uiColor("6B3A22"))  // ₹10 Darker chocolate
    private static let twentyLight:     Color = Color(uiColor("6B8020"))  // ₹20 Olive green
    private static let fiftyLight:      Color = Color(uiColor("1A4AA0"))  // ₹50 Deep blue
    private static let hundredLight:    Color = Color(uiColor("6A50A0"))  // ₹100 Deep lavender
    private static let twoHundredLight: Color = Color(uiColor("A88800"))  // ₹200 Dark gold
    private static let fiveHundredLight:Color = Color(uiColor("5A6E6E"))  // ₹500 Dark stone
    private static let twoThousandLight:Color = Color(uiColor("A03080"))  // ₹2000 Deep magenta
    
    static var ten: Color {
        UITraitCollection.current.userInterfaceStyle == .dark ? tenDark : tenLight
    }
    static var twenty: Color {
        UITraitCollection.current.userInterfaceStyle == .dark ? twentyDark : twentyLight
    }
    static var fifty: Color {
        UITraitCollection.current.userInterfaceStyle == .dark ? fiftyDark : fiftyLight
    }
    static var hundred: Color {
        UITraitCollection.current.userInterfaceStyle == .dark ? hundredDark : hundredLight
    }
    static var twoHundred: Color {
        UITraitCollection.current.userInterfaceStyle == .dark ? twoHundredDark : twoHundredLight
    }
    static var fiveHundred: Color {
        UITraitCollection.current.userInterfaceStyle == .dark ? fiveHundredDark : fiveHundredLight
    }
    static var twoThousand: Color {
        UITraitCollection.current.userInterfaceStyle == .dark ? twoThousandDark : twoThousandLight
    }
}
```

---

## RBI NOTE COLOR REFERENCE (ground truth)

These are the actual RBI Mahatma Gandhi (New) Series note base colors:

| Denom | Hex | Color Name | Dark Mode Tint | Light Mode Tint |
|-------|-----|-----------|---------------|----------------|
| ₹10 | #8B5A42 | Chocolate Brown | #8B5A42 (original) | #6B3A22 (darker) |
| ₹20 | #B8C840 | Greenish Yellow | #B8C840 (original) | #6B8020 (olive) |
| ₹50 | #3A72CC | Fluorescent Blue | #3A72CC (original) | #1A4AA0 (deep blue) |
| ₹100 | #9080C0 | Lavender | #9080C0 (original) | #6A50A0 (deep lavender) |
| ₹200 | #FFA500 | Bright Orange/Yellow | #C8A800 (gold) | #A88800 (dark gold) |
| ₹500 | #808080 | Stone Grey | #7A8E8E (blue-grey) | #5A6E6E (dark stone) |
| ₹2000 | #C050A0 | Magenta (retired) | #C050A0 (original) | #A03080 (deep magenta) |

---

## VERIFICATION

1. Switch the app between light and dark mode
2. Cycle through all 7 denomination themes
3. Verify text is ALWAYS readable (dark text on light bg in light mode, light text on dark bg in dark mode)
4. Verify the denomination tint appears as a subtle gradient on the background
5. Verify cards, badges, and charts all use the correct ink colors
6. Verify the accent (securityGold) adapts — vibrant in dark mode, deeper in light mode

---

## CRITICAL "DO NOT" RULES

- Do NOT change the existing color hex values for canvasDark, canvasLight, canvasDeep, canvasShadow, accentDark, accentLight — those are correct
- Do NOT change the swatchColor values
- Do NOT change how `bullGreen`, `bearRed`, `holdAmber` work — those are mode-independent signal colors
- Do NOT change the `displayName` or `rawValue` of any AppTheme case
- Do NOT use `@Environment(\.colorScheme)` inside Theme static vars — use `UITraitCollection.current.userInterfaceStyle`
- Keep the RBI seal, micro-text, and guilloche patterns exactly as they are
