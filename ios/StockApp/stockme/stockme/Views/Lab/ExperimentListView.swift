import SwiftUI

/// Research ledger. The trial count matters: every run makes a lucky result more likely,
/// so the deflated Sharpe in each report is measured against all of them.
struct ExperimentListView: View {
    @StateObject private var vm = LabLoadViewModel<LabList<LabExperimentSummary>>(isEmpty: { $0.items.isEmpty }) {
        try await NetworkManager.shared.labExperiments()
    }

    var body: some View {
        LabScreen(title: "My Experiments") {
            StateCard(title: "your experiments", phase: vm.phase,
                      emptyMessage: "No experiments yet. Test a hypothesis in the Hypothesis Lab.",
                      onRetry: vm.load) {
                if let list = vm.value {
                    LabTrialCounter(count: list.total ?? list.items.count)
                    ForEach(list.items.filter { !$0.id.isEmpty }) { e in
                        NavigationLink(value: LabRoute.experiment(id: e.id)) { LabExperimentRow(summary: e) }
                            .buttonStyle(EKPressStyle())
                            .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
                    }
                }
            }
            NavigationLink(value: LabRoute.hypothesisLab) { LabPrimaryLabel(title: "New hypothesis", icon: "plus") }
                .buttonStyle(EKPressStyle())
                .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
        }
        .onAppear { vm.loadIfNeeded() }
        .onDisappear { vm.cancel() }
        .refreshable { vm.load() }
    }
}

private struct LabTrialCounter: View {
    let count: Int

    var body: some View {
        HStack(spacing: Theme.Spacing.medium) {
            Text("\(count)")
                .font(Theme.dataLarge(size: 28))
                .foregroundStyle(Theme.securityGold)
            Text("You have run \(count) \(count == 1 ? "experiment" : "experiments"). Each one raises the bar.")
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
        .accessibilityElement(children: .combine)
    }
}

struct LabVerdictChip: View {
    let verdict: LabVerdict?

    var body: some View {
        switch verdict?.kind {
        case .supported: LabChip(text: "Supported", tint: Theme.bullGreen, icon: "checkmark.seal")
        case .fragile: LabChip(text: "Fragile", tint: Theme.holdAmber, icon: "exclamationmark.triangle")
        case .notSupported: LabChip(text: "Not supported", tint: Theme.bearRed, icon: "xmark.seal")
        case .insufficientData: LabChip(text: "Insufficient data", tint: Theme.inkSecondary, icon: "tray")
        default: LabChip(text: verdict?.label ?? "Pending", tint: Theme.inkSecondary)
        }
    }
}

private struct LabExperimentRow: View {
    let summary: LabExperimentSummary

    var body: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                Text(summary.question?.isEmpty == false ? summary.question! : (summary.score ?? "Experiment"))
                    .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .subheadline))
                    .foregroundStyle(Theme.inkPrimary)
                    .lineLimit(2)
                HStack(spacing: Theme.Spacing.small) {
                    LabVerdictChip(verdict: summary.verdict)
                    if let ic = summary.meanIc { Text("IC \(LabFormat.num(ic, digits: 4))").font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary) }
                }
                Text(LabFormat.day(summary.createdAt)).font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
            }
            Spacer()
            Image(systemName: "chevron.right").font(.caption).foregroundStyle(Theme.inkTertiary).accessibilityHidden(true)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
        .accessibilityElement(children: .combine)
    }
}
