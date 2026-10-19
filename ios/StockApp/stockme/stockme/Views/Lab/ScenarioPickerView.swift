import SwiftUI

/// Time Machine start screen: resume a session, pick a curated scenario (briefing only;
/// the debrief and timeline stay hidden until the session ends) or a custom period.
struct ScenarioPickerView: View {
    private struct Catalog {
        let scenarios: [LabScenario]
        let sessions: [LabSessionSummary]
    }

    @StateObject private var vm = LabLoadViewModel<Catalog>(isEmpty: { $0.scenarios.isEmpty && $0.sessions.isEmpty }) {
        async let catalog = NetworkManager.shared.labScenarios()
        async let sessions = try? NetworkManager.shared.labSessions()
        let c = try await catalog
        return Catalog(scenarios: c.scenarios ?? [], sessions: await sessions?.items ?? [])
    }

    @State private var capitalText = "1000000"
    @State private var blind = false
    @State private var customStart = Calendar.current.date(byAdding: .year, value: -3, to: Date()) ?? Date()
    @State private var customEnd = Calendar.current.date(byAdding: .day, value: -400, to: Date()) ?? Date()
    @State private var startingId: String?
    @State private var startError: String?
    @State private var createdSession: String?

    private var capital: Double? {
        Double(capitalText.filter { $0.isNumber || $0 == "." }).flatMap { (10_000...1_000_000_000).contains($0) ? $0 : nil }
    }

    var body: some View {
        LabScreen(title: "Time Machine") {
            LabSessionSettingsCard(capitalText: $capitalText, blind: $blind, capitalValid: capital != nil)
            if let startError { LabInlineError(message: startError) }
            StateCard(title: "scenarios", phase: vm.phase, emptyMessage: "No scenarios are available yet.",
                      onRetry: vm.load) {
                LabScenarioSections(sessions: vm.value?.sessions ?? [], scenarios: vm.value?.scenarios ?? [],
                                    startingId: startingId, canStart: capital != nil && startingId == nil,
                                    onStart: { scenario in Task { await start(scenario) } })
            }
            LabCustomPeriodCard(start: $customStart, end: $customEnd, busy: startingId == "custom",
                                enabled: capital != nil && startingId == nil,
                                onStart: { Task { await startCustom() } })
        }
        .onAppear { vm.loadIfNeeded() }
        .onDisappear { vm.cancel() }
        .navigationDestination(item: $createdSession) { id in TimeMachineSessionView(sessionId: id) }
    }

    private func start(_ scenario: LabScenario) async {
        guard let capital else { return }
        let config = LabSimConfig(start: scenario.start, end: scenario.end,
                                  universe: Array((scenario.universeHint ?? []).prefix(30)),
                                  capital: capital, hideIdentity: blind)
        await create(id: scenario.id, title: scenario.title, scenarioId: scenario.id, config: config)
    }

    private func startCustom() async {
        guard let capital else { return }
        let start = WireDate.dayFormatter.string(from: customStart)
        let end = WireDate.dayFormatter.string(from: customEnd)
        guard customEnd > customStart else { startError = "The end date must be after the start date."; return }
        guard customEnd.timeIntervalSince(customStart) <= 5 * 366 * 86_400 else {
            startError = "A simulation can span at most five years."
            return
        }
        startingId = "custom"
        defer { startingId = nil }
        do {
            let universe = try await NetworkManager.shared.labUniverse(start: start, n: 20)
            let config = LabSimConfig(start: start, end: end, universe: universe.symbols ?? [],
                                      capital: capital, hideIdentity: blind)
            await create(id: "custom", title: "Custom: \(LabFormat.day(start)) to \(LabFormat.day(end))",
                         scenarioId: nil, config: config)
        } catch {
            startError = LabErrors.message(error)
        }
    }

    private func create(id: String, title: String?, scenarioId: String?, config: LabSimConfig) async {
        HapticManager.selection()
        startingId = id
        startError = nil
        defer { startingId = nil }
        do {
            let session = try await NetworkManager.shared.labCreateSession(title: title, scenarioId: scenarioId, config: config)
            if let newId = session.id?.value { createdSession = newId } else { vm.load() }
        } catch {
            startError = LabErrors.message(error)
            HapticManager.warning()
        }
    }
}

private struct LabSessionSettingsCard: View {
    @Binding var capitalText: String
    @Binding var blind: Bool
    let capitalValid: Bool

    var body: some View {
        LabCard {
            LabCardTitle(title: "Your starting point", icon: "slider.horizontal.3")
            HStack {
                Text("Capital (₹)")
                    .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                    .foregroundStyle(Theme.inkPrimary)
                Spacer()
                TextField("10,00,000", text: $capitalText)
                    .keyboardType(.numberPad)
                    .multilineTextAlignment(.trailing)
                    .font(Theme.monoTabular(size: 15))
                    .foregroundStyle(Theme.inkPrimary)
                    .accessibilityLabel("Starting capital in rupees")
            }
            Text(capitalValid ? LabFormat.money(Double(capitalText.filter(\.isNumber))) : "Enter between ₹10,000 and ₹100 Cr.")
                .font(Theme.microLabel())
                .foregroundStyle(capitalValid ? Theme.inkTertiary : Theme.bearRed)
            Toggle(isOn: $blind) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("Blind mode: hide company names")
                        .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                        .foregroundStyle(Theme.inkPrimary)
                    Text("Stocks appear as aliases so memory of what happened cannot steer you.")
                        .font(Theme.microLabel())
                        .foregroundStyle(Theme.inkSecondary)
                }
            }
            .tint(Theme.securityGold)
            .onChange(of: blind) { _, _ in HapticManager.selection() }
        }
    }
}

private struct LabScenarioSections: View {
    let sessions: [LabSessionSummary]
    let scenarios: [LabScenario]
    let startingId: String?
    let canStart: Bool
    let onStart: (LabScenario) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            if !sessions.isEmpty {
                LabCardTitle(title: "Resume", icon: "play.circle")
                ForEach(sessions.filter { !$0.id.isEmpty }) { s in
                    NavigationLink(value: LabRoute.session(id: s.id)) { LabSessionSummaryRow(summary: s) }
                        .buttonStyle(EKPressStyle())
                        .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
                }
                GuillocheDivider()
            }
            LabCardTitle(title: "Curated scenarios", icon: "books.vertical")
            // Playable first, then the ones whose data is not loaded yet.
            ForEach(scenarios.filter { $0.dataAvailable != false } + scenarios.filter { $0.dataAvailable == false }) { sc in
                LabScenarioCard(scenario: sc, busy: startingId == sc.id,
                                enabled: canStart && sc.dataAvailable != false, onStart: { onStart(sc) })
            }
        }
    }
}

private struct LabSessionSummaryRow: View {
    let summary: LabSessionSummary

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(summary.title ?? "Session")
                    .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .subheadline))
                    .foregroundStyle(Theme.inkPrimary)
                    .lineLimit(1)
                Text("Clock \(LabFormat.day(summary.clock)) · \(summary.finished == true ? "finished" : "in progress")")
                    .font(Theme.microLabel())
                    .foregroundStyle(Theme.inkSecondary)
            }
            Spacer()
            Text(LabFormat.money(summary.equity))
                .font(Theme.monoTabular(size: 14))
                .foregroundStyle(Theme.inkPrimary)
            Image(systemName: "chevron.right").font(.caption).foregroundStyle(Theme.inkTertiary).accessibilityHidden(true)
        }
        .padding(Theme.Spacing.standard)
        .frame(minHeight: 44)
        .banknoteCard()
        .accessibilityElement(children: .combine)
    }
}

private struct LabScenarioCard: View {
    let scenario: LabScenario
    let busy: Bool
    let enabled: Bool
    let onStart: () -> Void

    var body: some View {
        LabCard {
            Text(scenario.title ?? scenario.id)
                .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .headline))
                .foregroundStyle(Theme.inkPrimary)
            LabFlowLayout {
                if let c = scenario.category { LabChip(text: c) }
                if let d = scenario.difficulty { LabChip(text: d, tint: Theme.inkSecondary) }
                LabChip(text: "\(LabFormat.day(scenario.start)) – \(LabFormat.day(scenario.end))", tint: Theme.inkSecondary, icon: "calendar")
                if scenario.dataAvailable == false { LabChip(text: "Data not loaded", tint: Theme.holdAmber, icon: "exclamationmark.triangle") }
            }
            Text(scenario.briefing ?? "")
                .font(Theme.engravedSerif(size: 13, relativeTo: .body))
                .foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
            if let goals = scenario.learningGoals, !goals.isEmpty { LabGoalList(goals: goals) }
            if let missing = scenario.missingSymbols, !missing.isEmpty, scenario.dataAvailable != false {
                Text("Not in this dataset, so left out: \(missing.joined(separator: ", ")).")
                    .font(Theme.engravedSerif(size: 11, relativeTo: .caption))
                    .foregroundStyle(Theme.holdAmber)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Button { onStart() } label: { LabPrimaryLabel(title: "Start this scenario", icon: "play.fill", busy: busy, enabled: enabled) }
                .buttonStyle(EKPressStyle())
                .disabled(!enabled)
        }
    }
}

private struct LabGoalList: View {
    let goals: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text("You will practise")
                .font(Theme.microLabel())
                .foregroundStyle(Theme.inkTertiary)
            ForEach(goals, id: \.self) { g in
                Label(g, systemImage: "checkmark.seal")
                    .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkSecondary)
            }
        }
    }
}

private struct LabCustomPeriodCard: View {
    @Binding var start: Date
    @Binding var end: Date
    let busy: Bool
    let enabled: Bool
    let onStart: () -> Void

    /// Price data younger than 30 days is never simulated.
    private var latest: Date { Calendar.current.date(byAdding: .day, value: -31, to: Date()) ?? Date() }

    var body: some View {
        LabCard {
            LabCardTitle(title: "Custom period", icon: "calendar.badge.clock")
            DatePicker("Start", selection: $start, in: ...latest, displayedComponents: .date)
                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
            DatePicker("End", selection: $end, in: start...latest, displayedComponents: .date)
                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
            Text("Up to five years, ending at least 30 days ago. The 20 most liquid stocks on the start date make up the universe, chosen with data available on that day.")
                .font(Theme.microLabel())
                .foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
            Button { onStart() } label: { LabPrimaryLabel(title: "Start custom session", icon: "play.fill", busy: busy, enabled: enabled) }
                .buttonStyle(EKPressStyle())
                .disabled(!enabled)
        }
        .tint(Theme.securityGold)
    }
}
