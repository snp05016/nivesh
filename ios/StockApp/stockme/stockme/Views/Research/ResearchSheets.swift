import SwiftUI

// MARK: - Model card (spec 10.1 item 7): tier text, data period, universe, limitations.
// The statistical checks behind each tier are admin-only and never shown here.

struct ModelCardSheet: View {
    let card: ResearchModelCard?
    let outlooks: [ResearchOutlook]

    private func tierText(_ horizon: ResearchModelCardHorizon) -> String {
        horizon.tierText
            ?? outlooks.first { $0.horizonDays == horizon.horizonDays }?.tierText
            ?? "The outlook is unavailable for this report."
    }

    private var universeText: String {
        switch card?.universeQuality {
        case .pit:
            return "The 200 most-traded NSE stocks, ranked on each past date by the value traded over the previous six months, so stocks that were later delisted are included."
        case .survivorshipBiased:
            return "Today's most-traded NSE stocks only. Past results on such a list look better than they were, so no edge is claimed."
        default:
            return "The 200 most-traded NSE stocks."
        }
    }

    var body: some View {
        ResearchSheetScaffold(title: "What we tested") {
            if let card {
                ForEach(Array((card.horizons ?? []).enumerated()), id: \.offset) { _, horizon in
                    ResearchSheetSection(title: "Next \(horizon.horizonDays ?? 0) trading days") {
                        Text(tierText(horizon))
                    }
                }
                if let label = card.labelDefinition {
                    ResearchSheetSection(title: "What the method ranks") { Text(label) }
                }
                ResearchSheetSection(title: "Data period") {
                    Text(card.dataPeriod ?? "Not recorded")
                }
                ResearchSheetSection(title: "Stocks compared") { Text(universeText) }
                if let limitations = card.limitations, !limitations.isEmpty {
                    ResearchSheetSection(title: "Limitations") {
                        ForEach(Array(limitations.enumerated()), id: \.offset) { _, item in
                            Text("• \(item)")
                        }
                    }
                }
            } else {
                Text("The method description is unavailable for this report.")
            }
        }
    }
}

// MARK: - Provenance

struct ProvenanceSheet: View {
    let report: ResearchReport

    private var proseText: String {
        switch report.narrative?.status {
        case .llmValidated:
            return "Written by an AI language model from the computed figures and accepted by an automated checker (\(report.narrative?.validatorVersion ?? "checker"))."
        case .template:
            return "A fixed template filled with the computed figures."
        default:
            return "No written summary for this report."
        }
    }

    var body: some View {
        ResearchSheetScaffold(title: "Where the figures come from") {
            ResearchSheetSection(title: "Sources") {
                ForEach(Array((report.provenance?.sources ?? []).enumerated()), id: \.offset) { _, source in
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        ResearchKeyValueRow(key: ResearchFormat.sourceName(source.id),
                                            value: ResearchFormat.sourceStatus(source))
                        if let note = source.note {
                            Text(note).foregroundStyle(Theme.inkTertiary)
                        }
                    }
                }
            }
            ResearchSheetSection(title: "Report") {
                ResearchKeyValueRow(key: "Market date", value: ResearchFormat.day(report.asOf.marketDate))
                ResearchKeyValueRow(key: "Built", value: report.origin == .onDemand ? "On request" : "Nightly run")
                ResearchKeyValueRow(key: "Report id", value: report.reportId ?? "Not recorded")
                ResearchKeyValueRow(key: "Engine version", value: report.engineVersion ?? "Not recorded")
            }
            if let provenance = report.provenance {
                ResearchProvenanceIDs(provenance: provenance)
            }
            ResearchPipelineSection(stages: report.pipeline ?? [])
            ResearchSheetSection(title: "Written summary") { Text(proseText) }
        }
    }
}

private struct ResearchProvenanceIDs: View {
    let provenance: ResearchProvenance

    var body: some View {
        ResearchSheetSection(title: "Versions") {
            ResearchKeyValueRow(key: "Data snapshot", value: provenance.dataSnapshotId ?? "Not recorded")
            ResearchKeyValueRow(key: "Feature set", value: provenance.featureVersion ?? "Not recorded")
            ResearchKeyValueRow(key: "Cost model", value: provenance.costModelVersion ?? "Not recorded")
            ResearchKeyValueRow(key: "Code", value: String((provenance.gitSha ?? "Not recorded").prefix(12)))
        }
    }
}

private struct ResearchPipelineSection: View {
    let stages: [ResearchPipelineStage]

    private func status(_ stage: ResearchPipelineStage) -> String {
        switch stage.status {
        case .ok: return "Done"
        case .degraded: return "Partly done"
        case .failed: return "Failed"
        case .skipped: return "Skipped"
        default: return "Unknown"
        }
    }

    var body: some View {
        if !stages.isEmpty {
            ResearchSheetSection(title: "Steps") {
                ForEach(Array(stages.enumerated()), id: \.offset) { _, stage in
                    ResearchKeyValueRow(key: (stage.stage?.rawValue ?? "step").capitalized, value: status(stage))
                }
            }
        }
    }
}

// MARK: - Fact detail (long-press on any number)

struct FactDetailSheet: View {
    let fact: ResearchFact

    private var statusText: String {
        switch fact.status {
        case .ok: return "Current"
        case .stale: return "Out of date"
        case .unavailable: return "Not available: \(ResearchFormat.reason(fact.reason))"
        default: return "Unknown"
        }
    }

    private var methodText: String {
        switch fact.method {
        case "historical_500d"?: return "Historical, last 500 trading days"
        case "fhs_ewma"?: return "Filtered historical simulation, recent-weighted"
        case let method?: return method
        case nil: return "Standard calculation"
        }
    }

    var body: some View {
        ResearchSheetScaffold(title: fact.label ?? "Figure") {
            ResearchSheetSection(title: "Value") {
                Text(fact.display ?? "Not available")
                    .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
            }
            ResearchSheetSection(title: "Details") {
                ResearchKeyValueRow(key: "As of", value: ResearchFormat.day(fact.asOf))
                ResearchKeyValueRow(key: "Source", value: ResearchFormat.sourceName(fact.source))
                ResearchKeyValueRow(key: "Method", value: methodText)
                ResearchKeyValueRow(key: "Status", value: statusText)
            }
        }
    }
}

private struct ResearchFactDetailModifier: ViewModifier {
    let fact: ResearchFact?
    @State private var showing = false

    @ViewBuilder
    func body(content: Content) -> some View {
        if let fact {
            content
                .contentShape(Rectangle())
                .onLongPressGesture { showing = true }
                .accessibilityAction(named: "Show details") { showing = true }
                .sheet(isPresented: $showing) { FactDetailSheet(fact: fact) }
        } else {
            content
        }
    }
}

extension View {
    /// Long-press (or the "Show details" accessibility action) opens `FactDetailSheet`.
    func researchFactDetail(_ fact: ResearchFact?) -> some View {
        modifier(ResearchFactDetailModifier(fact: fact))
    }
}

// MARK: - Sheet chrome

private struct ResearchSheetScaffold<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.large) {
                HStack(alignment: .firstTextBaseline) {
                    Text(title)
                        .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title3))
                        .foregroundStyle(Theme.inkPrimary)
                        .accessibilityAddTraits(.isHeader)
                    Spacer(minLength: Theme.Spacing.medium)
                    Button("Done") { dismiss() }
                        .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .body))
                        .foregroundStyle(Theme.securityGold)
                }
                content
                    .font(Theme.engravedSerif(size: 14, relativeTo: .subheadline))
                    .foregroundStyle(Theme.inkPrimary)
            }
            .padding(Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }
}

private struct ResearchSheetSection<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            ResearchSectionTitle(title: title)
            content.fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
