import SwiftUI

extension View {
    /// Grows the hit area to at least `size` x `size` points (Apple HIG minimum: 44pt)
    /// without changing the visual. Apply to a Button/NavigationLink label.
    func minTapTarget(_ size: CGFloat = 44) -> some View {
        frame(minWidth: size, minHeight: size)
            .contentShape(Rectangle())
    }
}
