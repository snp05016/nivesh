import XCTest
import SwiftUI
import UIKit
@testable import stockme

/// UX-09: every text colour keeps WCAG AA (>= 4.5:1) on its canvas, for every
/// theme in both light and dark mode.
@MainActor
final class ThemeContrastTests: XCTestCase {

    private func luminance(_ color: Color, _ style: UIUserInterfaceStyle) -> Double {
        let resolved = UIColor(color).resolvedColor(with: UITraitCollection(userInterfaceStyle: style))
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        XCTAssertTrue(resolved.getRed(&r, green: &g, blue: &b, alpha: &a))
        func lin(_ c: CGFloat) -> Double {
            let c = Double(min(max(c, 0), 1))
            return c <= 0.04045 ? c / 12.92 : pow((c + 0.055) / 1.055, 2.4)
        }
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    }

    private func ratio(_ fg: Color, _ bg: Color, _ style: UIUserInterfaceStyle) -> Double {
        let l1 = luminance(fg, style), l2 = luminance(bg, style)
        return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)
    }

    private func assertAA(_ fg: Color, on bg: Color, _ style: UIUserInterfaceStyle, _ label: String) {
        let r = ratio(fg, bg, style)
        XCTAssertGreaterThanOrEqual(r, 4.5, "\(label): \(String(format: "%.2f", r)):1")
    }

    func test_text_colours_meet_AA_on_every_theme_and_scheme() {
        let manager = ThemeManager.shared
        let saved = manager.current
        defer { manager.current = saved }

        for theme in AppTheme.allCases {
            manager.current = theme
            for (scheme, style) in [(ColorScheme.light, UIUserInterfaceStyle.light), (.dark, .dark)] {
                // canvasDeep light is canvasLight at 0.92 opacity; approximate with canvasLight.
                let backgrounds = scheme == .dark
                    ? [manager.canvas(for: scheme), manager.canvasDeep(for: scheme)]
                    : [manager.canvas(for: scheme)]
                let inks: [(String, Color)] = [
                    ("inkPrimary", manager.inkPrimary(for: scheme)),
                    ("inkSecondary", manager.inkSecondary(for: scheme)),
                    ("inkTertiary", manager.inkTertiary(for: scheme)),
                    ("accent", manager.accent(for: scheme)),
                    ("bullGreen", Theme.bullGreen),
                    ("bearRed", Theme.bearRed),
                    ("holdAmber", Theme.holdAmber),
                ]
                for (bgIndex, bg) in backgrounds.enumerated() {
                    for (name, ink) in inks {
                        assertAA(ink, on: bg, style, "\(theme.rawValue)/\(scheme)/bg\(bgIndex)/\(name)")
                    }
                }
                assertAA(Theme.onAccent, on: manager.accent(for: scheme), style, "\(theme.rawValue)/\(scheme)/onAccent")
            }
        }
    }

    func test_onStatus_meets_AA_on_status_fills() {
        for style in [UIUserInterfaceStyle.light, .dark] {
            for (name, fill) in [("bullGreen", Theme.bullGreen), ("bearRed", Theme.bearRed), ("holdAmber", Theme.holdAmber)] {
                assertAA(Theme.onStatus, on: fill, style, "\(style.rawValue)/onStatus on \(name)")
            }
        }
    }
}
