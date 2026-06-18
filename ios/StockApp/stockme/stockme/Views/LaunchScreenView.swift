import SwiftUI

// Launch screen forced to dark mode — all Theme.* tokens resolve to dark variants

// MARK: - Icon canvas (N + rising chart + dot + निवेश)

private struct NiveshIconCanvas: View {
    // Normalised chart waypoints (fraction of icon frame)
    private let chartPoints: [(x: CGFloat, y: CGFloat)] = [
        (0.082, 0.873),
        (0.218, 0.736),
        (0.355, 0.773),
        (0.468, 0.627),
        (0.582, 0.527),
        (0.718, 0.400),
        (0.909, 0.255),
    ]

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let h = geo.size.height
            let pts = chartPoints.map { CGPoint(x: $0.x * w, y: $0.y * h) }

            ZStack {
                // Chart fill — semi-transparent gold area
                Canvas { ctx, _ in
                    var fill = Path()
                    fill.move(to: pts[0])
                    for p in pts.dropFirst() { fill.addLine(to: p) }
                    fill.addLine(to: CGPoint(x: pts.last!.x, y: h))
                    fill.addLine(to: CGPoint(x: pts[0].x, y: h))
                    fill.closeSubpath()
                    ctx.fill(fill, with: .linearGradient(
                        Gradient(stops: [
                            .init(color: Theme.securityGold.opacity(0.22), location: 0),
                            .init(color: Theme.securityGold.opacity(0), location: 1),
                        ]),
                        startPoint: CGPoint(x: w / 2, y: 0),
                        endPoint: CGPoint(x: w / 2, y: h)
                    ))
                }

                // Chart backdrop line (low opacity, behind "N")
                Canvas { ctx, _ in
                    var path = Path()
                    path.move(to: pts[0])
                    for p in pts.dropFirst() { path.addLine(to: p) }
                    ctx.stroke(path, with: .color(Theme.securityGold.opacity(0.18)),
                               style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))
                }

                // "N" — Georgia Bold, gold gradient mask
                Text("N")
                    .font(Font.custom("Georgia-Bold", size: w * 0.78))
                    .overlay(Theme.securityGoldGradient)
                    .mask(Text("N").font(Font.custom("Georgia-Bold", size: w * 0.78)))
                    .frame(width: w, height: h, alignment: .center)
                    .offset(y: -h * 0.02)

                // Main chart line (on top of "N")
                Canvas { ctx, _ in
                    var path = Path()
                    path.move(to: pts[0])
                    for p in pts.dropFirst() { path.addLine(to: p) }
                    ctx.stroke(path, with: .linearGradient(
                        Gradient(colors: [Theme.securityGold, Theme.securityGold]),
                        startPoint: pts[0],
                        endPoint: pts.last!
                    ), style: StrokeStyle(lineWidth: 3, lineCap: .round, lineJoin: .round))
                }

                // Dot at chart peak + halo
                let peak = pts.last!
                Canvas { ctx, _ in
                    let haloRect = CGRect(x: peak.x - 10.5, y: peak.y - 10.5, width: 21, height: 21)
                    ctx.stroke(Path(ellipseIn: haloRect),
                               with: .color(Theme.securityGold.opacity(0.35)),
                               lineWidth: 1.2)
                    let dotRect = CGRect(x: peak.x - 6, y: peak.y - 6, width: 12, height: 12)
                    ctx.fill(Path(ellipseIn: dotRect), with: .color(Theme.securityGold))
                }

                // निवेश — below centre
                Text("निवेश")
                    .font(Font.custom("Georgia", size: w * 0.12).italic())
                    .tracking(2)
                    .foregroundStyle(Theme.securityGold.opacity(0.65))
                    .frame(width: w, height: h, alignment: .bottom)
                    .padding(.bottom, h * 0.06)
            }
        }
    }
}

// MARK: - Launch Screen

struct LaunchScreenView: View {
    @State private var markVisible  = false
    @State private var loadProgress: CGFloat = 0

    var body: some View {
        GeometryReader { geo in
            ZStack {
                Theme.canvas.ignoresSafeArea()

                VStack(spacing: Theme.Spacing.none) {
                    Spacer()

                    // ── Mark + wordmark stack ──────────────────────────────
                    VStack(spacing: Theme.Spacing.screen) {
                        // Icon mark — 130×130 with double border
                        ZStack {
                            RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                                .fill(Theme.canvasDeep)
                                .frame(width: geo.size.width * 0.35, height: geo.size.width * 0.35)

                            RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                                .stroke(Theme.securityGold.opacity(0.55), lineWidth: 1.2)
                                .frame(width: geo.size.width * 0.35, height: geo.size.width * 0.35)

                            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                                .stroke(Theme.securityGold.opacity(0.25), lineWidth: 0.5)
                                .frame(width: geo.size.width * 0.35 * (122.0 / 130.0), height: geo.size.width * 0.35 * (122.0 / 130.0))

                            NiveshIconCanvas()
                                .frame(width: 100, height: 100)
                        }

                        // Wordmark row
                        VStack(spacing: Theme.Spacing.medium) {
                            // NIVESH + flanking rules
                            HStack(spacing: Theme.Spacing.standard) {
                                Rectangle()
                                    .fill(Theme.securityGold.opacity(0.35))
                                    .frame(width: geo.size.width * 0.056, height: 0.6)

                                Text("NIVESH")
                                    .font(Font.custom("Georgia-Bold", size: 24, relativeTo: .title))
                                    .tracking(24 * 0.20)
                                    .overlay(Theme.securityGoldGradient)
                                    .mask(
                                        Text("NIVESH")
                                            .font(Font.custom("Georgia-Bold", size: 24, relativeTo: .title))
                                            .tracking(24 * 0.20)
                                    )

                                Rectangle()
                                    .fill(Theme.securityGold.opacity(0.35))
                                    .frame(width: geo.size.width * 0.056, height: 0.6)
                            }

                            // Subtitle
                            Text("निवेश · Invest with Clarity")
                                .font(Font.custom("Georgia", size: 13, relativeTo: .footnote).italic())
                                .tracking(13 * 0.08)
                                .foregroundStyle(Theme.inkSecondary)
                        }
                    }
                    .scaleEffect(markVisible ? 1.0 : 0.88)
                    .opacity(markVisible ? 1.0 : 0.0)
                    .animation(.easeOut(duration: 0.65), value: markVisible)

                    Spacer()

                    // ── Loading bar ─────────────────────────────────────────
                    ZStack(alignment: .leading) {
                        Capsule()
                            .fill(Theme.canvasShadow)
                            .frame(width: geo.size.width * 0.164, height: 3.5)

                        Capsule()
                            .fill(Theme.securityGold)
                            .frame(width: loadProgress, height: 3.5)
                    }
                    .padding(.bottom, Theme.Spacing.sectionGap)

                    // ── Disclaimer ──────────────────────────────────────────
                    Text("For informational purposes only")
                        .font(.caption2)
                        .tracking(8.5 * 0.05)
                        .foregroundStyle(Theme.inkTertiary)
                        .padding(.bottom, Theme.Spacing.xLarge)
                }
            }
            .preferredColorScheme(.dark)
        }
        .onAppear {
            markVisible = true
            withAnimation(.easeInOut(duration: 0.9)) {
                loadProgress = 32
            }
        }
    }
}
