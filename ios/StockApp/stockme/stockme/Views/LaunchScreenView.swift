import SwiftUI

// MARK: - Theme tokens (dark-mode fixed — launch screen always dark)

private enum NiveshTheme {
    static let background    = Color(hex: "1C1A14")
    static let canvasDeep    = Color(hex: "242018")
    static let canvasShadow  = Color(hex: "141210")
    static let inkSecondary  = Color(hex: "9BAF92")
    static let inkTertiary   = Color(hex: "8A8A7A")
    static let goldBright    = Color(hex: "C8A84A")
    static let goldDull      = Color(hex: "B8973A")
    static let goldGradient  = LinearGradient(
        colors: [Color(hex: "C8A84A"), Color(hex: "B8973A")],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )
    static let outerBorder   = Color(hex: "C8A84A").opacity(0.55)
    static let innerBorder   = Color(hex: "C8A84A").opacity(0.25)
    static let ruleColor     = Color(hex: "C8A84A").opacity(0.35)
    static let iconCornerRadius: CGFloat = 22
}

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
                            .init(color: NiveshTheme.goldDull.opacity(0.28), location: 0),
                            .init(color: NiveshTheme.goldDull.opacity(0), location: 1),
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
                    ctx.stroke(path, with: .color(NiveshTheme.goldBright.opacity(0.18)),
                               style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))
                }

                // "N" — Georgia Bold, gold gradient mask
                Text("N")
                    .font(Font.custom("Georgia-Bold", size: w * 0.78))
                    .overlay(NiveshTheme.goldGradient)
                    .mask(Text("N").font(Font.custom("Georgia-Bold", size: w * 0.78)))
                    .frame(width: w, height: h, alignment: .center)
                    .offset(y: -h * 0.02)

                // Main chart line (on top of "N")
                Canvas { ctx, _ in
                    var path = Path()
                    path.move(to: pts[0])
                    for p in pts.dropFirst() { path.addLine(to: p) }
                    ctx.stroke(path, with: .linearGradient(
                        Gradient(colors: [NiveshTheme.goldBright, NiveshTheme.goldDull]),
                        startPoint: pts[0],
                        endPoint: pts.last!
                    ), style: StrokeStyle(lineWidth: 3, lineCap: .round, lineJoin: .round))
                }

                // Dot at chart peak + halo
                let peak = pts.last!
                Canvas { ctx, _ in
                    let haloRect = CGRect(x: peak.x - 10.5, y: peak.y - 10.5, width: 21, height: 21)
                    ctx.stroke(Path(ellipseIn: haloRect),
                               with: .color(NiveshTheme.goldBright.opacity(0.35)),
                               lineWidth: 1.2)
                    let dotRect = CGRect(x: peak.x - 6, y: peak.y - 6, width: 12, height: 12)
                    ctx.fill(Path(ellipseIn: dotRect), with: .color(NiveshTheme.goldBright))
                }

                // निवेश — below centre
                Text("निवेश")
                    .font(Font.custom("Georgia", size: w * 0.12).italic())
                    .tracking(2)
                    .foregroundColor(NiveshTheme.goldBright.opacity(0.65))
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
        ZStack {
            NiveshTheme.background.ignoresSafeArea()

            VStack(spacing: 0) {
                Spacer()

                // ── Mark + wordmark stack ──────────────────────────────
                VStack(spacing: 20) {
                    // Icon mark — 130×130 with double border
                    ZStack {
                        RoundedRectangle(cornerRadius: NiveshTheme.iconCornerRadius)
                            .fill(NiveshTheme.canvasDeep)
                            .frame(width: UIScreen.main.bounds.width * 0.35, height: UIScreen.main.bounds.width * 0.35)

                        RoundedRectangle(cornerRadius: NiveshTheme.iconCornerRadius)
                            .stroke(NiveshTheme.outerBorder, lineWidth: 1.2)
                            .frame(width: UIScreen.main.bounds.width * 0.35, height: UIScreen.main.bounds.width * 0.35)

                        RoundedRectangle(cornerRadius: 19)
                            .stroke(NiveshTheme.innerBorder, lineWidth: 0.5)
                            .frame(width: UIScreen.main.bounds.width * 0.35 * (122.0 / 130.0), height: UIScreen.main.bounds.width * 0.35 * (122.0 / 130.0))

                        NiveshIconCanvas()
                            .frame(width: 100, height: 100)
                    }

                    // Wordmark row
                    VStack(spacing: 8) {
                        // NIVESH + flanking rules
                        HStack(spacing: 14) {
                            Rectangle()
                                .fill(NiveshTheme.ruleColor)
                                .frame(width: UIScreen.main.bounds.width * 0.056, height: 0.6)

                            Text("NIVESH")
                                .font(Font.custom("Georgia-Bold", size: 24, relativeTo: .title))
                                .tracking(24 * 0.20)
                                .overlay(NiveshTheme.goldGradient)
                                .mask(
                                    Text("NIVESH")
                                        .font(Font.custom("Georgia-Bold", size: 24, relativeTo: .title))
                                        .tracking(24 * 0.20)
                                )

                            Rectangle()
                                .fill(NiveshTheme.ruleColor)
                                .frame(width: UIScreen.main.bounds.width * 0.056, height: 0.6)
                        }

                        // Subtitle
                        Text("निवेश · Invest with Clarity")
                            .font(Font.custom("Georgia", size: 13, relativeTo: .footnote).italic())
                            .tracking(13 * 0.08)
                            .foregroundColor(NiveshTheme.inkSecondary)
                    }
                }
                .scaleEffect(markVisible ? 1.0 : 0.88)
                .opacity(markVisible ? 1.0 : 0.0)
                .animation(.easeOut(duration: 0.65), value: markVisible)

                Spacer()

                // ── Loading bar ─────────────────────────────────────────
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(NiveshTheme.canvasShadow)
                        .frame(width: UIScreen.main.bounds.width * 0.164, height: 3.5)

                    Capsule()
                        .fill(NiveshTheme.goldBright)
                        .frame(width: loadProgress, height: 3.5)
                }
                .padding(.bottom, 28)

                // ── Disclaimer ──────────────────────────────────────────
                Text("For informational purposes only")
                    .font(.caption2)
                    .tracking(8.5 * 0.05)
                    .foregroundColor(NiveshTheme.inkTertiary)
                    .padding(.bottom, 40)
            }
        }
        .onAppear {
            markVisible = true
            withAnimation(.easeInOut(duration: 0.9)) {
                loadProgress = 32
            }
        }
    }
}
