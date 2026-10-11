import SwiftUI

struct TutorialStep {
    let number: Int
    let title: String
    let body: String
    let spotlightRect: CGRect?
}

struct TutorialOverlayView: View {
    @EnvironmentObject var tutorialManager: TutorialManager
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        GeometryReader { geo in
            let step = currentStep(geo: geo)
            ZStack {
                // ── Dim + spotlight ──────────────────────────────────────────
                if let rect = step.spotlightRect {
                    ZStack {
                        Rectangle()
                            .fill(Theme.inkPrimary.opacity(0.82))
                            .ignoresSafeArea()
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                            .frame(width: rect.width + Theme.Spacing.standard, height: rect.height + Theme.Spacing.standard)
                            .position(x: rect.midX, y: rect.midY)
                            .blendMode(.destinationOut)
                    }
                    .compositingGroup()
                    .ignoresSafeArea()
                    .animation(.spring(response: 0.5, dampingFraction: 0.8), value: tutorialManager.currentStep)
                } else {
                    Theme.inkPrimary.opacity(0.88)
                        .ignoresSafeArea()
                }

                // ── Card ─────────────────────────────────────────────────────
                cardLayout(step: step, geo: geo)
                    .id(tutorialManager.currentStep)
                    .transition(.asymmetric(
                        insertion: .opacity.combined(with: .move(edge: .bottom)),
                        removal:   .opacity
                    ))
                    .animation(.spring(response: 0.4, dampingFraction: 0.82), value: tutorialManager.currentStep)
            }
            .allowsHitTesting(true)
        }
        .ignoresSafeArea()
    }

    // MARK: - Geometry-aware helpers

    private func tabRect(index: Int, geo: GeometryProxy) -> CGRect {
        let w = geo.size.width
        let safeBottom = geo.safeAreaInsets.bottom
        let tabItemHeight: CGFloat = 49
        // 5 tabs in ContentView: Home(0), Markets(1), Ideas(2), News(3), Portfolio(4)
        let tabWidth = w / 5.0
        let centerX = tabWidth * (CGFloat(index) + 0.5)
        let spotWidth: CGFloat = tabWidth - 8
        let x = max(0, min(centerX - spotWidth / 2, w - spotWidth))
        // Tab items sit above the safe area at the top 49pt of the tab bar
        let y = geo.size.height - safeBottom - tabItemHeight
        return CGRect(x: x, y: y, width: spotWidth, height: tabItemHeight)
    }

    private func steps(geo: GeometryProxy) -> [TutorialStep] {
        return [
            TutorialStep(number: 1,  title: "Welcome to Nivesh",
                body: "Your personal investment companion. Built just for you. This quick tour shows you everything in 2 minutes.",
                spotlightRect: nil),
            TutorialStep(number: 2,  title: "Your Daily Dashboard",
                body: "Open here every morning. See today's most important action for your portfolio, live market indices, and your morning brief.",
                spotlightRect: tabRect(index: 0, geo: geo)),
            TutorialStep(number: 3,  title: "Your Morning Brief",
                body: "A personalised summary generated every morning. It tells you what changed overnight, which stocks need attention, and the market mood.",
                spotlightRect: CGRect(x: Theme.screenPadding, y: geo.size.height * 0.35, width: geo.size.width - Theme.screenPadding * 2, height: geo.size.height * 0.15)),
            TutorialStep(number: 4,  title: "Search & Discover",
                body: "Search any NSE or BSE stock by name or ticker. Long-press any result for a quick preview. Use Discover presets to find new investment ideas.",
                spotlightRect: tabRect(index: 1, geo: geo)),
            TutorialStep(number: 5,  title: "Your Portfolio",
                body: "See all your holdings with live profit and loss. The Risk Card tells you if your portfolio is too concentrated in one sector.",
                spotlightRect: tabRect(index: 4, geo: geo)),
            TutorialStep(number: 6,  title: "Red Flags",
                body: "Watches your holdings for danger signs — SEBI surveillance, bearish signal flips, or promoters pledging too many shares. Check this weekly.",
                spotlightRect: CGRect(x: Theme.screenPadding, y: geo.size.height * 0.52, width: geo.size.width - Theme.screenPadding * 2, height: geo.size.height * 0.125)),
            TutorialStep(number: 7,  title: "The Main Analysis",
                body: "Tap any stock to run a full AI analysis. It takes 30–90 seconds and analyses fundamentals, news, promoter activity, global macro, and Indian market sentiment together.",
                spotlightRect: CGRect(x: geo.size.width * 0.20, y: geo.size.height * 0.37, width: geo.size.width * 0.60, height: geo.size.width * 0.60)),
            TutorialStep(number: 8,  title: "Price Alerts",
                body: "Set a target price for any stock. The app tells you immediately when a stock crosses your target — every time you open the app.",
                spotlightRect: tabRect(index: 1, geo: geo)),
            TutorialStep(number: 9,  title: "Your Trade Journal",
                body: "Log every buy and sell with your reason. Over time you'll see your own patterns — which reasons led to profits, which didn't.",
                spotlightRect: tabRect(index: 4, geo: geo)),
            TutorialStep(number: 10, title: "You're all set\(authManager.currentUser.map { ", \($0.displayName)" } ?? "").",
                body: "Check the app every morning and run an analysis before any buy or sell decision. Happy investing.",
                spotlightRect: nil),
        ]
    }

    private func currentStep(geo: GeometryProxy) -> TutorialStep {
        let all = steps(geo: geo)
        return all.first { $0.number == tutorialManager.currentStep } ?? all[0]
    }

    // MARK: - Card layout

    @ViewBuilder
    private func cardLayout(step: TutorialStep, geo: GeometryProxy) -> some View {
        let h = geo.size.height
        if let rect = step.spotlightRect {
            if rect.midY > h * 0.55 {
                // Spotlight in bottom half → card floats ABOVE it
                VStack(spacing: Theme.Spacing.none) {
                    Spacer(minLength: 60)
                    cardBody(step: step)
                        .padding(.horizontal, Theme.Spacing.screen)
                    Spacer(minLength: h - rect.minY + 24)
                }
            } else {
                // Spotlight in top half → card floats BELOW it
                VStack(spacing: Theme.Spacing.none) {
                    Spacer(minLength: rect.maxY + 24)
                    cardBody(step: step)
                        .padding(.horizontal, Theme.Spacing.screen)
                    Spacer(minLength: 40)
                }
            }
        } else {
            VStack(spacing: Theme.Spacing.none) {
                Spacer()
                cardBody(step: step)
                    .padding(.horizontal, Theme.Spacing.large)
                Spacer()
            }
        }
    }

    // MARK: - Card content

    private func cardBody(step: TutorialStep) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            HStack {
                Text("\(tutorialManager.currentStep) of \(tutorialManager.totalSteps)")
                    .font(Theme.serialNumberFont(size: 10))
                    .foregroundStyle(Theme.inkTertiary)
                Spacer()
                Button("Skip") { tutorialManager.skip() }.buttonStyle(EKPressStyle())
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
            }
            .padding(.horizontal, Theme.Spacing.screen)
            .padding(.top, Theme.Spacing.card)
            .padding(.bottom, Theme.Spacing.standard)

            Rectangle()
                .fill(Theme.securityGold.opacity(0.3))
                .frame(height: 0.5)
                .padding(.horizontal, Theme.Spacing.screen)

            Text(step.title)
                .font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .headline))
                .foregroundStyle(Theme.inkPrimary)
                .padding(.horizontal, Theme.Spacing.screen)
                .padding(.top, Theme.Spacing.card)
                .padding(.bottom, Theme.Spacing.tight)

            Text(step.body)
                .font(Theme.officialStampFont(size: 14))
                .foregroundStyle(Theme.inkSecondary)
                .lineSpacing(4)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.horizontal, Theme.Spacing.screen)
                .padding(.bottom, Theme.Spacing.card)

            HStack(spacing: Theme.Spacing.standard) {
                if tutorialManager.currentStep > 1 {
                    Button(action: { HapticManager.selection(); tutorialManager.previous() }) {
                        Text("← Back")
                            .font(Theme.officialStampFont(size: 10))
                            .foregroundStyle(Theme.securityGold)
                            .padding(.horizontal, Theme.Spacing.card)
                            .padding(.vertical, Theme.Spacing.standard)
                            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                                .stroke(Theme.securityGold.opacity(0.5), lineWidth: 1))
                    }
                    .buttonStyle(EKPressStyle())
                }
                Spacer()
                Button(action: {
                    HapticManager.impact(.light)
                    tutorialManager.currentStep == tutorialManager.totalSteps
                        ? tutorialManager.complete()
                        : tutorialManager.next()
                }) {
                    Text(tutorialManager.currentStep == tutorialManager.totalSteps
                         ? "Start Investing →" : "Next →")
                        .font(Theme.officialStampFont(size: 10))
                        .foregroundStyle(Theme.canvasDeep)
                        .padding(.horizontal, Theme.Spacing.screen)
                        .padding(.vertical, Theme.Spacing.standard)
                        .background(Theme.securityGold)
                        .cornerRadius(Theme.CornerRadius.tight)
                }
                .buttonStyle(EKPressStyle())
            }
            .padding(.horizontal, Theme.Spacing.screen)
            .padding(.bottom, Theme.Spacing.screen)
        }
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
        .overlay(
            ZStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .stroke(Theme.securityGold.opacity(0.6), lineWidth: 1.2)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(Theme.securityGold.opacity(0.22), lineWidth: 0.5)
                    .padding(Theme.Spacing.small)
            }
        )
        .shadow(color: Theme.inkPrimary.opacity(0.5), radius: 24, x: 0, y: 8)
    }
}
