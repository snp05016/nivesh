import SwiftUI

// MARK: - Launch Sequence View

struct LaunchSequenceView: View {
    let onComplete: () -> Void

    // Phase 1 — Guilloche
    @State private var guillocheProgress: CGFloat = 0

    // Phase 2 — Security thread
    @State private var threadXFraction: CGFloat = 0
    @State private var threadVisible = false
    @State private var flashOpacity: CGFloat = 0

    // Phase 3 — Wordmark
    @State private var wordmarkOpacity: CGFloat = 0
    @State private var hindiOpacity: CGFloat = 0

    // Phase 4 — Subtitle
    @State private var subtitleOpacity: CGFloat = 0
    @State private var subtitleTracking: CGFloat = 6

    // Phase 5 — Underline
    @State private var wordmarkMeasuredWidth: CGFloat = 0
    @State private var underlineWidth: CGFloat = 0

    // Phase 7 — Dissolution
    @State private var contentOpacity: CGFloat = 1

    var body: some View {
        ZStack {
            // Persistent black — catches the dissolution fade
            Color.black.ignoresSafeArea()

            ZStack {
                // ── Phase 1 ─────────────────────────────────────────────
                LaunchGuillocheCanvas(progress: guillocheProgress)
                    .frame(maxWidth: .infinity)
                    .frame(height: 120)

                // ── Phase 2 ─────────────────────────────────────────────
                if threadVisible {
                    LaunchThreadCanvas(
                        xFraction: threadXFraction,
                        flashOpacity: flashOpacity
                    )
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .ignoresSafeArea()
                    .allowsHitTesting(false)
                }

                // ── Phase 3–5 ────────────────────────────────────────────
                VStack(spacing: Theme.Spacing.none) {
                    // "NIVESH" — stamps in, never scales
                    Text("NIVESH")
                        .font(Theme.officialStampFont(size: 42, relativeTo: .largeTitle))
                        .fontWeight(.black)
                        .tracking(8)
                        .foregroundStyle(Theme.inkPrimary)
                        .opacity(wordmarkOpacity)
                        .background(
                            GeometryReader { geo in
                                Color.clear.onAppear {
                                    wordmarkMeasuredWidth = geo.size.width
                                }
                            }
                        )

                    // Phase 5 — underline grows from leading edge
                    Rectangle()
                        .fill(Theme.securityGold)
                        .frame(width: underlineWidth, height: 0.75)
                        .frame(width: wordmarkMeasuredWidth, alignment: .leading)
                        .padding(.top, 12)

                    // "निवेश"
                    Text("निवेश")
                        .font(Theme.hindiFont(size: 16, relativeTo: .subheadline))
                        .foregroundStyle(Theme.inkSecondary)
                        .opacity(hindiOpacity)
                        .padding(.top, 6)

                    // "RESERVE BANK OF INTELLIGENCE" — tracking collapses like a stamp
                    Text("RESERVE BANK OF INTELLIGENCE")
                        .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                        .foregroundStyle(Theme.inkTertiary)
                        .modifier(LaunchTrackingModifier(tracking: subtitleTracking))
                        .opacity(subtitleOpacity)
                        .padding(.top, 8)
                }
            }
            .opacity(contentOpacity)
        }
        .preferredColorScheme(.dark)
        .onAppear { runSequence() }
    }

    private func runSequence() {
        // Phase 1 — Guilloche emerges 0.4 → 2.2 s
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
            withAnimation(.easeInOut(duration: 1.8)) { guillocheProgress = 1 }
        }

        // Phase 2 — Security thread 1.6 → 2.4 s (overlaps guilloche)
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) {
            threadVisible = true
            threadXFraction = 0
            withAnimation(.easeInOut(duration: 0.8)) { threadXFraction = 1 }
        }
        // Flash fires when thread crosses centre (~2.0 s)
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
            flashOpacity = 1
            withAnimation(.linear(duration: 0.2)) { flashOpacity = 0 }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.45) {
            threadVisible = false
        }

        // Phase 3a — "NIVESH" 2.2 s, 0.4 s easeOut
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.2) {
            withAnimation(.easeOut(duration: 0.4)) { wordmarkOpacity = 1 }
        }

        // Phase 3b — "निवेश" 2.4 s, 0.35 s easeOut
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.4) {
            withAnimation(.easeOut(duration: 0.35)) { hindiOpacity = 1 }
        }

        // Phase 4 — Subtitle stamp 2.9 s, tracking 6 → 2 with opacity
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.9) {
            withAnimation(.easeOut(duration: 0.5)) {
                subtitleOpacity = 1
                subtitleTracking = 2
            }
        }

        // Phase 5 — Gold underline 3.5 s, 0.6 s easeInOut, leading edge
        DispatchQueue.main.asyncAfter(deadline: .now() + 3.5) {
            withAnimation(.easeInOut(duration: 0.6)) {
                underlineWidth = wordmarkMeasuredWidth
            }
        }

        // Phase 7 — Dissolution 5.0 s, 0.6 s easeIn → black
        DispatchQueue.main.asyncAfter(deadline: .now() + 5.0) {
            withAnimation(.easeIn(duration: 0.6)) { contentOpacity = 0 }
        }

        // onComplete fires at 5.6 s — home screen reveals beneath
        DispatchQueue.main.asyncAfter(deadline: .now() + 5.6) {
            onComplete()
        }
    }
}

// MARK: - Animatable Tracking Modifier

private struct LaunchTrackingModifier: AnimatableModifier {
    var tracking: CGFloat

    var animatableData: CGFloat {
        get { tracking }
        set { tracking = newValue }
    }

    func body(content: Content) -> some View {
        content.tracking(tracking)
    }
}

// MARK: - Guilloche Canvas
// Three sine waves 120° apart, expand outward from screen centre.

private struct LaunchGuillocheCanvas: View {
    let progress: CGFloat

    var body: some View {
        Canvas { context, size in
            let cx = size.width / 2
            let cy = size.height / 2
            let halfW = (size.width / 2) * progress
            let amplitude: CGFloat = 8
            let freq: Double = .pi * 20 / Double(size.width)

            for phase in [0.0, Double.pi * 2 / 3, Double.pi * 4 / 3] {
                var path = Path()
                let x0 = cx - halfW
                let x1 = cx + halfW
                guard x0 < x1 else { continue }

                path.move(to: CGPoint(
                    x: x0,
                    y: cy + CGFloat(sin(Double(x0) * freq + phase)) * amplitude
                ))
                var x = x0 + 1.5
                while x <= x1 {
                    path.addLine(to: CGPoint(
                        x: x,
                        y: cy + CGFloat(sin(Double(x) * freq + phase)) * amplitude
                    ))
                    x += 1.5
                }

                context.stroke(
                    path,
                    with: .color(Theme.securityGold.opacity(0.18)),
                    lineWidth: 0.75
                )
            }
        }
    }
}

// MARK: - Thread Canvas
// Vertical 1.5 pt security thread sweeps L→R; brief centre flash.

private struct LaunchThreadCanvas: View {
    let xFraction: CGFloat
    let flashOpacity: CGFloat

    var body: some View {
        Canvas { context, size in
            let x = size.width * xFraction

            // Light catch as thread crosses centre
            if flashOpacity > 0 {
                let band = CGRect(
                    x: size.width * 0.5 - 20,
                    y: 0,
                    width: 40,
                    height: size.height
                )
                context.fill(
                    Path(band),
                    with: .color(Theme.securityGold.opacity(Double(flashOpacity) * 0.04))
                )
            }

            // Thread line
            let line = CGRect(x: x - 0.75, y: 0, width: 1.5, height: size.height)
            context.fill(Path(line), with: .color(Theme.securityGold))
        }
    }
}
