import SwiftUI

/// Every push inside the Lab. Registered once, at the Markets stack root (ContentView).
enum LabRoute: Hashable {
    case hub
    case timeMachine
    case session(id: String)
    case chart(sessionId: String, symbol: String)
    case autopsy(sessionId: String, orderId: String)
    case mentor(sessionId: String, orderId: String?)
    case hypothesisLab
    case experiments
    case experiment(id: String)
    case school
    case lesson(id: String)
    case eventExplorer
}

/// Markets entry point. Hidden unless the server turns on `research_lab`.
struct LabEntryCard: View {
    @ObservedObject private var flags = FeatureFlags.shared

    var body: some View {
        if flags.isOn(.researchLab) || NetworkManager.labDevURL != nil {
            NavigationLink(value: LabRoute.hub) { LabEntryCardLabel() }
                .buttonStyle(EKPressStyle())
                .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
                .padding(.horizontal, Theme.screenPadding)
        }
    }
}

private struct LabEntryCardLabel: View {
    var body: some View {
        HStack(spacing: Theme.Spacing.card) {
            Image(systemName: "flask")
                .font(Theme.serialNumberFont(size: 20, relativeTo: .headline))
                .foregroundStyle(Theme.securityGold)
                .frame(width: 48, height: 48)
                .background(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).fill(Theme.securityGold.opacity(0.12)))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("The Lab")
                    .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .headline))
                    .foregroundStyle(Theme.inkPrimary)
                Text("Replay past markets, test hypotheses on Indian data, learn how trading really works.")
                    .font(Theme.engravedSerif(size: 11, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(2)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.caption.weight(.semibold))
                .foregroundStyle(Theme.securityGold.opacity(0.5))
                .accessibilityHidden(true)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
        .accessibilityElement(children: .combine)
        .accessibilityHint("Opens the Lab")
    }
}

struct LabHubView: View {
    private struct Tile: Identifiable {
        let route: LabRoute
        let title: String
        let icon: String
        let blurb: String
        var id: String { title }
    }

    private let tiles: [Tile] = [
        Tile(route: .timeMachine, title: "Time Machine", icon: "clock.arrow.circlepath",
             blurb: "Trade a past market one day at a time, with real costs and no peeking ahead."),
        Tile(route: .hypothesisLab, title: "Hypothesis Lab", icon: "function",
             blurb: "Turn a market question into a testable score and see what the evidence says."),
        Tile(route: .school, title: "Trader School", icon: "graduationcap",
             blurb: "Short lessons with worked examples, calculators and quizzes."),
        Tile(route: .experiments, title: "My Experiments", icon: "list.bullet.rectangle",
             blurb: "Your research ledger. Every test you run is counted."),
        Tile(route: .eventExplorer, title: "Event Explorer", icon: "waveform.path.ecg",
             blurb: "Reconstruct what moved a stock: price and volume anomalies, corporate actions, sourced events."),
    ]

    var body: some View {
        LabScreen(title: "The Lab") {
            Text("A practice space. Nothing here is investment advice, and no real money moves.")
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
            LazyVGrid(columns: [GridItem(.flexible(), spacing: Theme.Spacing.standard),
                                GridItem(.flexible(), spacing: Theme.Spacing.standard)],
                      spacing: Theme.Spacing.standard) {
                ForEach(tiles) { tile in
                    NavigationLink(value: tile.route) { LabHubTile(title: tile.title, icon: tile.icon, blurb: tile.blurb) }
                        .buttonStyle(EKPressStyle())
                        .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
                }
            }
        }
    }
}

private struct LabHubTile: View {
    let title: String
    let icon: String
    let blurb: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(Theme.securityGold)
                .accessibilityHidden(true)
            Text(title)
                .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .headline))
                .foregroundStyle(Theme.inkPrimary)
            Text(blurb)
                .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, minHeight: 160, alignment: .topLeading)
        .banknoteCard()
        .accessibilityElement(children: .combine)
    }
}

struct LabRouteDestination: View {
    let route: LabRoute

    var body: some View {
        switch route {
        case .hub: LabHubView()
        case .timeMachine: ScenarioPickerView()
        case .session(let id): TimeMachineSessionView(sessionId: id)
        case .chart(let sid, let symbol): SimChartView(sessionId: sid, symbol: symbol)
        case .autopsy(let sid, let oid): TradeAutopsyView(sessionId: sid, orderId: oid)
        case .mentor(let sid, let oid): MentorChatView(sessionId: sid, orderId: oid)
        case .hypothesisLab: HypothesisLabView()
        case .experiments: ExperimentListView()
        case .experiment(let id): ExperimentReportView(experimentId: id)
        case .school: SchoolHomeView()
        case .lesson(let id): LessonView(lessonId: id)
        case .eventExplorer: EventTimelineView()
        }
    }
}
