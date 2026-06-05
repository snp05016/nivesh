import SwiftUI

struct LaunchSequenceView: View {
    let onComplete: () -> Void

    @State private var medallionVisible = false
    @State private var innerRingVisible = false
    @State private var hindiVisible = false
    @State private var titleVisible = false
    @State private var subtitleVisible = false
    @State private var guillocheProgress: CGFloat = 0
    @State private var fadingOut = false

    @Environment(\.colorScheme) var colorScheme
    private let guillocheHeight: CGFloat = 20

    var body: some View {
        ZStack {
            PaperTexture()

            VStack(spacing: 0) {
                Spacer()

                // ₹ Medallion — springs in first
                GeometryReader { geo in
                    ZStack {
                        // Outer ring
                        Circle()
                            .stroke(Theme.borderSage, lineWidth: 0.5)
                            .frame(width: geo.size.width * 0.25, height: geo.size.width * 0.25)
                            .scaleEffect(medallionVisible ? 1 : 0.5)
                            .opacity(medallionVisible ? 1 : 0)

                        // Inner ring
                        Circle()
                            .stroke(Theme.borderSage.opacity(0.5), lineWidth: 0.5)
                            .frame(width: geo.size.width * 0.20, height: geo.size.width * 0.20)
                            .scaleEffect(innerRingVisible ? 1 : 0.6)
                            .opacity(innerRingVisible ? 1 : 0)

                        // ₹ symbol
                        Text("₹")
                            .font(Theme.engravedSerif(size: 44, weight: .bold, relativeTo: .largeTitle))
                            .foregroundStyle(Theme.inkPrimary)
                            .scaleEffect(medallionVisible ? 1 : 0.4)
                            .opacity(medallionVisible ? 1 : 0)
                    }
                    .frame(maxWidth: .infinity)
                }
                .aspectRatio(1, contentMode: .fit)

                Spacer().frame(height: Theme.Spacing.xLarge)

                // Text stack
                VStack(spacing: Theme.Spacing.standard) {
                    // Hindi above
                    Text("निवेश")
                        .font(Theme.hindiFont(size: 14, relativeTo: .subheadline))
                        .foregroundStyle(Theme.inkSecondary)
                        .opacity(hindiVisible ? 1 : 0)
                        .offset(y: hindiVisible ? 0 : 5)

                    // Main title
                    Text("NIVESH")
                        .font(Theme.engravedSerif(size: 42, weight: .bold, relativeTo: .largeTitle))
                        .foregroundStyle(Theme.inkPrimary)
                        .tracking(4)
                        .opacity(titleVisible ? 1 : 0)
                        .offset(y: titleVisible ? 0 : 8)

                    // Subtitle
                    Text("RESERVE BANK OF INTELLIGENCE")
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .tracking(2)
                        .foregroundStyle(Theme.inkSecondary)
                        .opacity(subtitleVisible ? 1 : 0)
                }

                Spacer().frame(height: Theme.Spacing.xLarge)

                // Guilloché line draws itself in
                ZStack {
                    AnimatedGuilloche(progress: guillocheProgress)
                        .opacity(guillocheProgress > 0 ? 1 : 0)
                }
                .frame(height: guillocheHeight)
                .padding(.horizontal, Theme.Spacing.xLarge)

                Spacer()
            }
        }
        .opacity(fadingOut ? 0 : 1)
        .scaleEffect(fadingOut ? 0.97 : 1)
        .onAppear {
            startSequence()
        }
    }

    private func startSequence() {
        // Phase 1: Medallion springs in (Emil Kowalski spring — bouncy feel)
        withAnimation(.spring(response: 0.7, dampingFraction: 0.62)) {
            medallionVisible = true
        }
        withAnimation(.spring(response: 0.8, dampingFraction: 0.65).delay(0.12)) {
            innerRingVisible = true
        }

        // Phase 2: Hindi + title fade in
        withAnimation(.easeOut(duration: 0.35).delay(0.42)) {
            hindiVisible = true
        }
        withAnimation(.spring(response: 0.5, dampingFraction: 0.8).delay(0.5)) {
            titleVisible = true
        }

        // Phase 3: Subtitle + guilloché
        withAnimation(.easeOut(duration: 0.3).delay(0.72)) {
            subtitleVisible = true
        }
        withAnimation(.easeInOut(duration: 0.5).delay(0.85)) {
            guillocheProgress = 1.0
        }

        // Phase 4: Exit
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.55) {
            withAnimation(.easeIn(duration: 0.28)) {
                fadingOut = true
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.28) {
                onComplete()
            }
        }
    }
}

// MARK: - Animated Guilloché (draws itself in via trim)

private struct AnimatedGuilloche: View {
    let progress: CGFloat

    var body: some View {
        ZStack {
            GeometryReader { geo in
                let w = geo.size.width

                Path { path in
                    path.move(to: .zero)
                    for x in stride(from: 0, through: w, by: 4) {
                        path.addLine(to: CGPoint(x: x, y: sin(x / 4.0) * 2))
                    }
                }
                .trim(from: 0, to: progress)
                .stroke(Theme.inkSecondary.opacity(0.25), lineWidth: 0.5)

                Path { path in
                    path.move(to: CGPoint(x: 0, y: 4))
                    for x in stride(from: 0, through: w, by: 4) {
                        path.addLine(to: CGPoint(x: x, y: cos(x / 4.0) * 2 + 4))
                    }
                }
                .trim(from: 0, to: progress)
                .stroke(Theme.inkSecondary.opacity(0.10), lineWidth: 0.5)
            }
        }
    }
}
