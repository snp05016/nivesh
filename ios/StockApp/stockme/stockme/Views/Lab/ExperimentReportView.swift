import SwiftUI
import Charts

/// One experiment report: verdict, key statistics, IC over time and by year,
/// baselines, skeptic review, costs and the research / holdout windows.
struct ExperimentReportView: View {
    @StateObject private var vm: LabLoadViewModel<LabExperimentRecord>

    init(experimentId: String) {
        _vm = StateObject(wrappedValue: LabLoadViewModel { try await NetworkManager.shared.labExperiment(id: experimentId) })
    }

    /// Straight after a run: show the returned record without a refetch.
    init(record: LabExperimentRecord) {
        let id = record.id?.value ?? ""
        _vm = StateObject(wrappedValue: LabLoadViewModel(initial: record) { try await NetworkManager.shared.labExperiment(id: id) })
    }

    var body: some View {
        LabScreen(title: "Experiment report") {
            StateCard(title: "the report", phase: vm.phase, onRetry: vm.load) {
                if let r = vm.value?.report { LabReportContent(report: r, question: vm.value?.question) }
            }
        }
        .onAppear { vm.loadIfNeeded() }
        .onDisappear { vm.cancel() }
    }
}

private struct LabReportContent: View {
    let report: LabExperimentReport
    let question: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            LabCaveatBanner(warnings: report.provenance?.warnings ?? [])
            if let q = question ?? report.spec?.question, !q.isEmpty {
                Text(q).font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .headline)).foregroundStyle(Theme.inkPrimary)
            }
            LabVerdictBanner(verdict: report.verdict, status: report.status, error: report.error)
            if let res = report.result { LabKeyStatsGrid(result: res, report: report) }
            if let series = report.series, series.count > 1 { LabICChart(series: series) }
            if let years = report.icByYear, !years.isEmpty { LabICByYear(years: years) }
            if let base = report.baselines, !base.isEmpty { LabBaselinesTable(baselines: base, own: report.result?.meanIc) }
            if let sk = report.skeptics, !sk.isEmpty { LabSkepticPanel(skeptics: sk) }
            LabCostsWindowsCard(report: report)
            if let h = report.holdout { LabHoldoutCard(holdout: h) }
        }
    }
}

private struct LabVerdictBanner: View {
    let verdict: LabVerdict?
    let status: String?
    let error: String?

    private var style: (title: String, tint: Color, icon: String) {
        if status == "invalid" { return ("Could not run", Theme.bearRed, "exclamationmark.octagon") }
        switch verdict?.kind {
        case .supported: return ("Supported by the evidence", Theme.bullGreen, "checkmark.seal.fill")
        case .fragile: return ("Fragile", Theme.holdAmber, "exclamationmark.triangle.fill")
        case .notSupported: return ("Not supported", Theme.bearRed, "xmark.seal.fill")
        case .insufficientData: return ("Insufficient data", Theme.inkSecondary, "tray")
        default: return ("No verdict", Theme.inkSecondary, "questionmark.circle")
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
            Image(systemName: style.icon).font(.title2).foregroundStyle(style.tint).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                Text(style.title)
                    .font(Theme.engravedSerif(size: 17, weight: .bold, relativeTo: .headline))
                    .foregroundStyle(style.tint)
                Text(verdict?.text ?? error ?? "")
                    .font(Theme.engravedSerif(size: 13, relativeTo: .body))
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
                if let failed = verdict?.failedChecks, !failed.isEmpty {
                    Text("Failed: \(failed.joined(separator: ", "))").font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(Theme.Spacing.card)
        .background(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).fill(style.tint.opacity(0.1)))
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(style.tint.opacity(0.5), lineWidth: 1))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Verdict: \(style.title). \(verdict?.text ?? error ?? "")")
    }
}

private struct LabKeyStatsGrid: View {
    let result: LabExperimentResult
    let report: LabExperimentReport

    private var ci: String {
        guard let lo = result.icCi95?.first ?? nil, let hi = result.icCi95?.last ?? nil else { return "95% CI —" }
        return "95% CI \(LabFormat.num(lo, digits: 3)) to \(LabFormat.num(hi, digits: 3))"
    }

    var body: some View {
        LabCard {
            LabCardTitle(title: "Key statistics", icon: "sum")
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.medium) {
                LabStatTile(label: "Mean IC", value: LabFormat.num(result.meanIc, digits: 4), caption: ci, tint: LabFormat.tint(result.meanIc))
                LabStatTile(label: "Permutation p", value: LabFormat.num(report.permutationP, digits: 3),
                            caption: "Chance of an IC this high with shuffled scores")
                LabStatTile(label: "HAC t-stat", value: LabFormat.num(result.icHacT), caption: "Autocorrelation-robust")
                LabStatTile(label: "Net excess / period", value: LabFormat.pct(result.topExcessNetPerPeriod),
                            caption: "Top quantile, after costs", tint: LabFormat.tint(result.topExcessNetPerPeriod))
                LabStatTile(label: "Turnover / period", value: LabFormat.share(result.avgTurnover))
                LabStatTile(label: "Deflated Sharpe", value: LabFormat.share(report.deflatedSharpe?.value),
                            caption: "Across \(report.deflatedSharpe?.trials ?? 1) trials so far")
                LabStatTile(label: "Periods", value: "\(result.periods ?? 0)", caption: "≈\(LabFormat.num(result.meanNames, digits: 0)) names each")
                LabStatTile(label: "IC > 0 share", value: LabFormat.share(result.icPositiveShare))
            }
            if let note = report.deflatedSharpe?.note {
                Text(note).font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary).fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

private struct LabICChart: View {
    let series: [LabSeriesPoint]

    var body: some View {
        LabCard {
            LabCardTitle(title: "IC over time", icon: "chart.bar")
            Chart(series, id: \.date) { p in
                BarMark(x: .value("Date", p.day), y: .value("IC", p.ic ?? 0))
                    .foregroundStyle((p.ic ?? 0) >= 0 ? Theme.bullGreen : Theme.bearRed)
            }
            .chartYAxisLabel("Rank IC")
            .chartXAxisLabel("Rebalance date")
            .frame(height: UIScreen.main.bounds.height * 0.25)
            .accessibilityLabel("Information coefficient for \(series.count) rebalance dates; \(series.filter { ($0.ic ?? 0) > 0 }.count) were positive")
        }
    }
}

private struct LabICByYear: View {
    let years: [String: Double]

    var body: some View {
        LabCard {
            LabCardTitle(title: "IC by year", icon: "calendar")
            ForEach(years.keys.sorted(), id: \.self) { y in
                LabKeyValueRow(key: y, value: LabFormat.num(years[y], digits: 4), tint: LabFormat.tint(years[y]))
            }
        }
    }
}

private struct LabBaselinesTable: View {
    let baselines: [String: LabBaseline]
    let own: Double?

    var body: some View {
        LabCard {
            LabCardTitle(title: "Against simple baselines", icon: "scalemass")
            Text("Does your score add anything beyond well-known effects? A positive difference with |t| above 2 is evidence it does.")
                .font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary).fixedSize(horizontal: false, vertical: true)
            LabKeyValueRow(key: "Your score", value: "IC \(LabFormat.num(own, digits: 4))", tint: Theme.securityGold)
            ForEach(baselines.keys.sorted(), id: \.self) { k in
                let b = baselines[k]
                LabKeyValueRow(key: LabFormat.baselineName(k),
                               value: "IC \(LabFormat.num(b?.meanIc, digits: 4)) · diff \(LabFormat.num(b?.icDiffMean, digits: 4)) (t \(LabFormat.num(b?.icDiffT)))")
            }
        }
    }
}

private struct LabSkepticPanel: View {
    let skeptics: [LabSkeptic]

    var body: some View {
        LabCard {
            LabCardTitle(title: "Skeptic panel", icon: "person.3")
            ForEach(skeptics, id: \.self) { s in LabSkepticRow(skeptic: s) }
        }
    }
}

private struct LabSkepticRow: View {
    let skeptic: LabSkeptic

    private var icon: (String, Color, String) {
        switch skeptic.statusKind {
        case .pass: return ("checkmark.circle.fill", Theme.bullGreen, "Pass")
        case .warn: return ("exclamationmark.triangle.fill", Theme.holdAmber, "Warning")
        case .fail: return ("xmark.octagon.fill", Theme.bearRed, "Fail")
        case .unknown: return ("questionmark.circle", Theme.inkSecondary, "Unrated")
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
            Image(systemName: icon.0).foregroundStyle(icon.1).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                HStack(spacing: Theme.Spacing.small) {
                    Text(skeptic.agent ?? "Skeptic")
                        .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .subheadline))
                        .foregroundStyle(Theme.inkPrimary)
                    if skeptic.critical == true { LabChip(text: "critical", tint: Theme.inkSecondary) }
                }
                Text(skeptic.finding ?? "").font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkSecondary).fixedSize(horizontal: false, vertical: true)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(skeptic.agent ?? "Skeptic"): \(icon.2). \(skeptic.finding ?? "")")
    }
}

private struct LabCostsWindowsCard: View {
    let report: LabExperimentReport

    private func window(_ w: [String?]?) -> String {
        guard let w, w.count == 2 else { return "—" }
        return "\(LabFormat.day(w[0])) to \(LabFormat.day(w[1]))"
    }

    var body: some View {
        LabCard {
            LabCardTitle(title: "Costs and windows", icon: "indianrupeesign.circle")
            LabKeyValueRow(key: "Round-trip cost", value: LabFormat.share(report.costs?.roundTrip))
            LabKeyValueRow(key: "Slippage per side", value: "\(LabFormat.num(report.costs?.slippageBpsPerSide, digits: 0)) bps")
            LabKeyValueRow(key: "Research window", value: window(report.researchWindow))
            LabKeyValueRow(key: "Holdout window", value: window(report.holdoutWindow))
            if let note = report.costs?.note {
                Text(note).font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary).fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

private struct LabHoldoutCard: View {
    let holdout: LabHoldout

    var body: some View {
        LabCard {
            LabCardTitle(title: "Holdout result", icon: "lock")
            LabKeyValueRow(key: "Mean IC", value: LabFormat.num(holdout.result?.meanIc, digits: 4), tint: LabFormat.tint(holdout.result?.meanIc))
            LabKeyValueRow(key: "Net excess / period", value: LabFormat.pct(holdout.result?.topExcessNetPerPeriod))
            LabKeyValueRow(key: "Periods", value: "\(holdout.result?.periods ?? 0)")
            if let note = holdout.note {
                Text(note).font(Theme.microLabel()).foregroundStyle(Theme.holdAmber).fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}
