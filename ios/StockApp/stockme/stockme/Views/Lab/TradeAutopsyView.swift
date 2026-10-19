import SwiftUI
import Charts

/// One closed trade, split into what was knowable when it was placed and what only
/// hindsight shows. The verdict separates decision quality from outcome.
struct TradeAutopsyView: View {
    let sessionId: String
    let orderId: String
    @StateObject private var vm: LabLoadViewModel<LabAutopsyReport>

    init(sessionId: String, orderId: String) {
        self.sessionId = sessionId
        self.orderId = orderId
        _vm = StateObject(wrappedValue: LabLoadViewModel(isEmpty: { ($0.trades ?? []).isEmpty }) {
            try await NetworkManager.shared.labAutopsy(sessionId: sessionId, orderId: orderId)
        })
    }

    var body: some View {
        LabScreen(title: "Trade autopsy") {
            StateCard(title: "the autopsy", phase: vm.phase,
                      emptyMessage: "This trade has not closed yet. An autopsy is available once it is exited.",
                      onRetry: vm.load) {
                if let report = vm.value, let a = report.trades?.first {
                    LabAutopsyContent(sessionId: sessionId, orderId: orderId, autopsy: a, report: report)
                }
            }
        }
        .onAppear { vm.loadIfNeeded() }
        .onDisappear { vm.cancel() }
    }
}

private struct LabAutopsyContent: View {
    let sessionId: String
    let orderId: String
    let autopsy: LabAutopsy
    let report: LabAutopsyReport

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            LabCaveatBanner(warnings: report.provenance?.warnings ?? [])
            LabVerdictHeader(autopsy: autopsy)
            LabKnowableCard(autopsy: autopsy)
            if let process = autopsy.process { LabProcessCard(process: process) }
            if let h = autopsy.hindsight { LabHindsightCard(hindsight: h) }
            let cfs = (report.counterfactuals ?? []).filter { $0.valid != false && $0.deltaVsActual != nil }
            if !cfs.isEmpty { LabCounterfactualCard(items: cfs, note: report.counterfactualNote) }
            if let flags = report.behaviour, !flags.isEmpty { LabBehaviourCard(flags: flags) }
            NavigationLink(value: LabRoute.mentor(sessionId: sessionId, orderId: orderId)) {
                LabPrimaryLabel(title: "Ask the mentor about this trade", icon: "bubble.left.and.text.bubble.right")
            }
            .buttonStyle(EKPressStyle())
            .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
        }
    }
}

private struct LabVerdictHeader: View {
    let autopsy: LabAutopsy

    private var chip: (String, Color, String) {
        switch autopsy.verdict?.kind {
        case .earned: return ("Good process, good outcome", Theme.bullGreen, "checkmark.seal")
        case .badBreak: return ("Good process, bad break", Theme.holdAmber, "cloud.rain")
        case .lucky: return ("Weak process, lucky outcome", Theme.holdAmber, "dice")
        case .predictableLoss: return ("Weak process, predictable loss", Theme.bearRed, "xmark.seal")
        default: return ("Not classified", Theme.inkSecondary, "questionmark.circle")
        }
    }

    var body: some View {
        LabCard {
            Text("\(autopsy.symbol ?? "—") × \(LabFormat.qty(autopsy.qty))")
                .font(Theme.dataLarge(size: 22))
                .foregroundStyle(Theme.inkPrimary)
            LabChip(text: chip.0, tint: chip.1, icon: chip.2)
                .accessibilityLabel("Verdict: \(chip.0)")
            if let text = autopsy.verdict?.text {
                Text(text).font(Theme.engravedSerif(size: 13, relativeTo: .body)).foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let thesis = autopsy.thesis, !thesis.isEmpty {
                Text("Your thesis: “\(thesis)”")
                    .font(Theme.engravedSerif(size: 13, relativeTo: .footnote).italic())
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

private struct LabKnowableCard: View {
    let autopsy: LabAutopsy

    var body: some View {
        let k = autopsy.knowable
        LabCard {
            LabCardTitle(title: "Knowable at entry", icon: "lock.open")
            Text("Only data dated on or before \(LabFormat.day(k?.asof)), the day the order was placed.")
                .font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.medium) {
                LabStatTile(label: "5d return", value: LabFormat.pct(k?.ret5d), tint: LabFormat.tint(k?.ret5d))
                LabStatTile(label: "20d return", value: LabFormat.pct(k?.ret20d), tint: LabFormat.tint(k?.ret20d))
                LabStatTile(label: "60d return", value: LabFormat.pct(k?.ret60d), tint: LabFormat.tint(k?.ret60d))
                LabStatTile(label: "Vol (ann.)", value: LabFormat.share(k?.vol20dAnn))
                LabStatTile(label: "5d move (σ)", value: LabFormat.num(k?.ret5dZ))
                LabStatTile(label: "From 52w high", value: LabFormat.pct(k?.distFrom52wHigh), tint: LabFormat.tint(k?.distFrom52wHigh))
                LabStatTile(label: "Volume vs 20d", value: "\(LabFormat.num(k?.volumeVs20dAvg))×")
                LabStatTile(label: "Position weight", value: LabFormat.share(k?.positionWeight))
                LabStatTile(label: "Risk per trade", value: LabFormat.share(k?.riskPerTrade))
            }
            if let br = k?.baseRate, let share = br.beatBenchmarkShare {
                Text("Base rate: in \(br.windows ?? 0) past \(br.horizon ?? 0)-day windows, this stock beat the benchmark \(LabFormat.share(share)) of the time.")
                    .font(Theme.engravedSerif(size: 12, relativeTo: .footnote)).foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            LabPlanRow(autopsy: autopsy)
        }
    }
}

private struct LabPlanRow: View {
    let autopsy: LabAutopsy

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            LabKeyValueRow(key: "Planned stop", value: LabFormat.price(autopsy.plannedStop))
            LabKeyValueRow(key: "Planned exit", value: LabFormat.price(autopsy.plannedExit))
            LabKeyValueRow(key: "Conviction", value: autopsy.conviction.map { "\(Int(($0 * 100).rounded()))%" } ?? "—")
        }
    }
}

private struct LabProcessCard: View {
    let process: LabProcess

    var body: some View {
        LabCard {
            LabCardTitle(title: "Process score", icon: "checklist")
            HStack(alignment: .top, spacing: Theme.Spacing.card) {
                LabScoreRing(score: process.score ?? 0, label: "Process score")
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    ForEach(process.checks ?? [], id: \.self) { c in
                        Label {
                            Text(c.text ?? c.id ?? "").font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                                .foregroundStyle(Theme.inkSecondary).fixedSize(horizontal: false, vertical: true)
                        } icon: {
                            Image(systemName: c.passed == true ? "checkmark.circle.fill" : "xmark.circle")
                                .foregroundStyle(c.passed == true ? Theme.bullGreen : Theme.bearRed)
                        }
                        .accessibilityElement(children: .combine)
                        .accessibilityLabel("\(c.passed == true ? "Passed" : "Missed"): \(c.text ?? "")")
                    }
                }
            }
        }
    }
}

private struct LabHindsightCard: View {
    let hindsight: LabHindsight

    var body: some View {
        LabCard {
            LabCardTitle(title: "Hindsight", icon: "eye")
            Text("Known only after the fact. Useful for learning, not for judging the decision.")
                .font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.medium) {
                LabStatTile(label: "Net return", value: LabFormat.pct(hindsight.returnNet), tint: LabFormat.tint(hindsight.returnNet))
                LabStatTile(label: "Net P&L", value: LabFormat.money(hindsight.pnlNet), tint: LabFormat.tint(hindsight.pnlNet))
                LabStatTile(label: "vs benchmark", value: LabFormat.pct(hindsight.excessReturn), tint: LabFormat.tint(hindsight.excessReturn))
                LabStatTile(label: "Held", value: "\(hindsight.sessionsHeld ?? 0) sessions")
                LabStatTile(label: "Worst point", value: LabFormat.pct(hindsight.maxAdverseExcursion), tint: Theme.bearRed)
                LabStatTile(label: "Best point", value: LabFormat.pct(hindsight.maxFavourableExcursion), tint: Theme.bullGreen)
                LabStatTile(label: "Fees", value: LabFormat.money(hindsight.feesInr),
                            caption: "\(LabFormat.share(hindsight.feesShareOfGross)) of gross")
                LabStatTile(label: "Move size", value: "\(LabFormat.num(hindsight.moveInSigmas, digits: 1)) σ")
            }
        }
    }
}

private struct LabCounterfactualCard: View {
    let items: [LabCounterfactual]
    let note: String?

    var body: some View {
        LabCard {
            LabCardTitle(title: "What if (hindsight)", icon: "arrow.triangle.branch")
            Chart(items, id: \.self) { c in
                BarMark(x: .value("Change vs actual (₹)", c.deltaVsActual ?? 0),
                        y: .value("Variant", LabFormat.humanize(c.variant ?? "variant")))
                    .foregroundStyle((c.deltaVsActual ?? 0) >= 0 ? Theme.bullGreen : Theme.bearRed)
                    .annotation(position: .trailing) {
                        Text(c.deltaVsActual.map { IndianFormatter.signedPrice($0) } ?? "")
                            .font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary)
                    }
            }
            .chartXAxisLabel("Final equity vs what you did (₹)")
            .frame(height: CGFloat(44 * items.count + 40))
            .accessibilityLabel("Counterfactual outcomes: " + items.map { "\(LabFormat.humanize($0.variant ?? "")) \(LabFormat.money($0.deltaVsActual))" }.joined(separator: ", "))
            if let note {
                Text(note).font(Theme.microLabel()).foregroundStyle(Theme.holdAmber)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}
