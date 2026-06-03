import UIKit
import SwiftUI

// Extensions to the HapticManager defined in Extensions.swift

extension HapticManager {
    static func selection() {
        #if targetEnvironment(simulator)
        return
        #else
        UISelectionFeedbackGenerator().selectionChanged()
        #endif
    }

    static func soft()    { impact(.soft) }
    static func light()   { impact(.light) }
    static func rigid()   { impact(.rigid) }
    static func heavy()   { impact(.heavy) }
    static func success() { notification(.success) }
    static func warning() { notification(.warning) }
    static func error()   { notification(.error) }
}

// MARK: - View modifier: haptic on tap

struct HapticTapModifier: ViewModifier {
    let style: UIImpactFeedbackGenerator.FeedbackStyle
    func body(content: Content) -> some View {
        content.simultaneousGesture(
            TapGesture().onEnded { HapticManager.impact(style) }
        )
    }
}

extension View {
    func hapticTap(_ style: UIImpactFeedbackGenerator.FeedbackStyle = .light) -> some View {
        modifier(HapticTapModifier(style: style))
    }
}

// MARK: - EK Press with haptic

struct EKPressHapticStyle: ButtonStyle {
    var haptic: UIImpactFeedbackGenerator.FeedbackStyle = .light

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.96 : 1.0)
            .opacity(configuration.isPressed ? 0.88 : 1.0)
            .animation(.spring(response: 0.22, dampingFraction: 0.80), value: configuration.isPressed)
            .onChange(of: configuration.isPressed) { _, pressed in
                if pressed { HapticManager.impact(haptic) }
            }
    }
}

extension View {
    func ekPressHaptic(_ style: UIImpactFeedbackGenerator.FeedbackStyle = .light) -> some View {
        buttonStyle(EKPressHapticStyle(haptic: style))
    }
}
