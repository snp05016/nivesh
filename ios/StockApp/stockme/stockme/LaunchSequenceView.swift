import SwiftUI

// MARK: - Launch Sequence View (v2 — Unified Timeline)

struct LaunchSequenceView: View {
    @Binding var isAnimationComplete: Bool

    @State private var timelineProgress: CGFloat = 0
    @State private var dissolveOpacity: CGFloat = 1
    @State private var triggerDissolve = false

    private let totalDuration: TimeInterval = 3.2
    private let dissolveDuration: TimeInterval = 0.4

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            ZStack {
                // Guilloche canvas
                LaunchGuillocheV2(progress: timelineProgress)
                    .frame(maxWidth: .infinity)
                    .frame(height: 140)

                // Wordmark stack
                wordmarkStack
            }
            .opacity(dissolveOpacity)
        }
        .preferredColorScheme(.dark)
        .onAppear { runTimeline() }
    }

    // MARK: - Wordmark + subtitle + shimmer

    private var wordmarkStack: some View {
        VStack(spacing: Theme.Spacing.none) {
            // "NIVESH" — mask-scaled reveal from center
            ZStack {
                Text("NIVESH")
                    .font(Font.custom("Georgia-Bold", size: 42, relativeTo: .largeTitle))
                    .tracking(8)
                    .foregroundStyle(Theme.inkPrimary)
                    .opacity(wordmarkBaseOpacity)
                    .mask(
                        Color.black
                            .frame(width: wordmarkMaskWidth, alignment: .leading)
                            .frame(maxWidth: wordmarkMeasuredWidth, alignment: .leading)
                    )
            }
            .background(
                GeometryReader { geo in
                    Color.clear.onAppear {
                        wordmarkMeasuredWidth = geo.size.width
                    }
                }
            )

            // Shimmer underline
            Rectangle()
                .fill(
                    LinearGradient(
                        gradient: Gradient(colors: [.clear, Theme.securityGold, .clear]),
                        startPoint: UnitPoint(x: shimmerPosition - 0.15, y: 0.5),
                        endPoint: UnitPoint(x: shimmerPosition + 0.15, y: 0.5)
                    )
                )
                .frame(width: wordmarkMeasuredWidth, height: 1.5)
                .padding(.top, 14)
                .opacity(shimmerOpacity)

            // "निवेश"
            Text("निवेश")
                .font(Font.custom("Georgia", size: 16, relativeTo: .subheadline).italic())
                .foregroundStyle(Theme.inkSecondary)
                .opacity(hindiOpacity)
                .padding(.top, 8)

            // "RESERVE BANK OF INTELLIGENCE"
            Text("RESERVE BANK OF INTELLIGENCE")
                .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                .foregroundStyle(Theme.inkTertiary)
                .opacity(subtitleOpacity)
                .padding(.top, 10)
        }
    }

    // MARK: - Computed animation properties

    @State private var wordmarkMeasuredWidth: CGFloat = 200

    private var wordmarkBaseOpacity: CGFloat {
        if timelineProgress < 0.15 { return 0 }
        if timelineProgress < 0.25 { return (timelineProgress - 0.15) / 0.10 }
        return 1
    }

    private var wordmarkMaskWidth: CGFloat {
        if timelineProgress < 0.19 { return 0 }
        if timelineProgress < 0.50 { return wordmarkMeasuredWidth * (timelineProgress - 0.19) / 0.31 }
        return wordmarkMeasuredWidth
    }

    private var hindiOpacity: CGFloat {
        if timelineProgress < 0.35 { return 0 }
        if timelineProgress < 0.45 { return (timelineProgress - 0.35) / 0.10 }
        return 1
    }

    private var subtitleOpacity: CGFloat {
        if timelineProgress < 0.45 { return 0 }
        if timelineProgress < 0.55 { return (timelineProgress - 0.45) / 0.10 }
        return 1
    }

    private var shimmerOpacity: CGFloat {
        if timelineProgress < 0.55 { return 0 }
        if timelineProgress < 0.65 { return (timelineProgress - 0.55) / 0.10 }
        return 1
    }

    private var shimmerPosition: CGFloat {
        guard timelineProgress >= 0.55 else { return -0.5 }
        return (timelineProgress - 0.55) / 0.45 * 2.0 - 0.5
    }

    // MARK: - Timeline driver

    private func runTimeline() {
        let start = Date()
        let interval = 1.0 / 60.0
        Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { timer in
            let elapsed = Date().timeIntervalSince(start)
            let p = min(CGFloat(elapsed / totalDuration), 1.0)
            timelineProgress = p

            if p >= 1.0, !triggerDissolve {
                triggerDissolve = true
                timer.invalidate()
                startDissolve()
            }
        }
    }

    private func startDissolve() {
        let start = Date()
        Timer.scheduledTimer(withTimeInterval: 1.0 / 60.0, repeats: true) { timer in
            let elapsed = Date().timeIntervalSince(start)
            let d = min(CGFloat(elapsed / dissolveDuration), 1.0)
            dissolveOpacity = 1.0 - d

            if d >= 1.0 {
                timer.invalidate()
                isAnimationComplete = true
            }
        }
    }
}

// MARK: - Guilloche Canvas V2 — Amplitude Envelope

private struct LaunchGuillocheV2: View {
    let progress: CGFloat

    var body: some View {
        Canvas { context, size in
            guard progress > 0 else { return }

            let cx = size.width / 2
            let cy = size.height / 2
            let halfW = (size.width / 2) * progress
            let amplitude: CGFloat = 10
            let freq: Double = .pi * 18 / Double(size.width)
            let x0 = max(cx - halfW, 0)
            let x1 = min(cx + halfW, size.width)

            guard x0 < x1 else { return }

            for phase in [0.0, Double.pi * 2 / 3, Double.pi * 4 / 3] {
                var path = Path()
                let step: CGFloat = 1.5

                // First point
                let firstY = cy + envelopeAmplitude(x: x0, cx: cx, w: halfW, amp: amplitude, phase: phase, freq: freq)
                path.move(to: CGPoint(x: x0, y: firstY))

                var x = x0 + step
                while x <= x1 {
                    let y = cy + envelopeAmplitude(x: x, cx: cx, w: halfW, amp: amplitude, phase: phase, freq: freq)
                    path.addLine(to: CGPoint(x: x, y: y))
                    x += step
                }

                context.stroke(
                    path,
                    with: .color(Theme.securityGold.opacity(0.14)),
                    lineWidth: 0.75
                )
            }
        }
    }

    /// Amplitude modulated by a cosine window — waves collapse at edges
    private func envelopeAmplitude(x: CGFloat, cx: CGFloat, w: CGFloat, amp: CGFloat, phase: Double, freq: Double) -> CGFloat {
        let envelope = w > 0 ? 1.0 - abs(x - cx) / w : 0
        let clamped = max(envelope, 0)
        return CGFloat(sin(Double(x) * freq + phase)) * amp * clamped
    }
}
