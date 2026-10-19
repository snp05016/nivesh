import SwiftUI
import Charts

/// Shared card chrome for the X-ray: gold caps title, content, banknote card.
struct XRayCard<Content: View>: View {
    let title: String
    private let content: Content

    init(title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HoldingSectionTitle(text: title.uppercased())
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private func xrayBody(_ text: String) -> some View {
    Text(text)
        .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
        .foregroundStyle(Theme.inkSecondary)
        .fixedSize(horizontal: false, vertical: true)
}

/// One bar per asset type. A Swift Charts bar scaled 0-100; no GeometryReader.
struct XRayShareBar: View {
    let pct: Double

    var body: some View {
        Chart {
            BarMark(x: .value("Share", min(max(pct, 0), 100)))
                .foregroundStyle(Theme.securityGold)
        }
        .chartXScale(domain: 0...100)
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .frame(height: 10)
    }
}

struct XRayAllocationCard: View {
    let slices: [XRaySlice]
    var hideValues = false

    var body: some View {
        XRayCard(title: "Where your money is") {
            ForEach(slices) { slice in
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    HStack(alignment: .firstTextBaseline) {
                        Text(slice.label)
                            .font(Theme.engravedSerif(size: 14, weight: .medium, relativeTo: .body))
                            .foregroundStyle(Theme.inkPrimary)
                        Spacer(minLength: Theme.Spacing.medium)
                        Text("\(String(format: "%.1f", slice.pct))%")
                            .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    XRayShareBar(pct: slice.pct)
                    Text(hideValues ? "₹ ••••" : IndianFormatter.formatLakhsCrores(slice.valueInr))
                        .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
        }
    }
}

struct XRayAMCCard: View {
    let amcs: [XRayAMC]
    var hideValues = false

    var body: some View {
        XRayCard(title: "Fund houses") {
            ForEach(amcs) { amc in
                HStack(alignment: .firstTextBaseline) {
                    Text(amc.name)
                        .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                        .foregroundStyle(Theme.inkPrimary)
                    Spacer(minLength: Theme.Spacing.medium)
                    Text("\(String(format: "%.1f", amc.pct))% of fund value")
                        .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkSecondary)
                }
            }
        }
    }
}

struct XRayPlanMixRow: View {
    let plans: XRayPlans

    var body: some View {
        XRayCard(title: "Direct and regular plans") {
            xrayBody("Direct \(String(format: "%.0f", plans.directPct))%, regular \(String(format: "%.0f", plans.regularPct))%, unknown \(String(format: "%.0f", plans.unknownPct))% of your fund value.")
        }
    }
}

struct XRayTopHoldingsCard: View {
    let holdings: [XRayHolding]
    var hideValues = false

    var body: some View {
        XRayCard(title: "Largest holdings") {
            ForEach(holdings) { h in
                HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.standard) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text(h.name)
                            .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                            .foregroundStyle(Theme.inkPrimary)
                            .lineLimit(2)
                        Text(h.assetClass == "MF" ? "Mutual fund" : h.ticker)
                            .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    Spacer(minLength: Theme.Spacing.medium)
                    VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                        Text("\(String(format: "%.1f", h.pct))%")
                            .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkPrimary)
                        Text(hideValues ? "₹ ••••" : IndianFormatter.formatLakhsCrores(h.valueInr))
                            .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
            }
        }
    }
}

/// The server's fixed-template facts, verbatim.
struct XRayFactsCard: View {
    let facts: [XRayFact]

    var body: some View {
        XRayCard(title: "At a glance") {
            ForEach(facts) { fact in xrayBody(fact.text) }
        }
    }
}

/// Spec 3.6: factual copy, a neutral AMFI link, no switch button. Hidden unless the data is available.
struct CommissionDragCard: View {
    let drag: CommissionDrag

    var body: some View {
        if let text = XRayCopy.dragBody(drag) {
            XRayCard(title: XRayCopy.dragTitle) {
                xrayBody(text)
                Text(XRayCopy.dragFootnote(drag))
                    .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkTertiary)
                    .fixedSize(horizontal: false, vertical: true)
                if let url = SafeURL.web(drag.sourceUrl) {
                    Link(XRayCopy.dragLinkTitle, destination: url)
                        .font(Theme.engravedSerif(size: 12, weight: .medium, relativeTo: .footnote))
                        .tint(Theme.securityGold)
                }
            }
        }
    }
}

/// Spec 3.9: how today's stocks moved in the COVID window. Not a forecast; the server's notes are shown as bullets.
struct CrisisReplayCard: View {
    let replay: CrisisReplayResponse

    var body: some View {
        XRayCard(title: XRayCopy.replayTitle(replay)) {
            if let summary = XRayCopy.replaySummary(replay) { xrayBody(summary) }
            ForEach(replay.notes, id: \.self) { note in
                xrayBody("• " + note)
            }
            if replay.notIncluded.contains(where: { $0.reason == "mutual_fund" }) {
                xrayBody(XRayCopy.notIncludedReason("mutual_fund"))
            }
        }
    }
}

/// "N holdings have no current price" footnote with the names.
struct XRayUnpricedFootnote: View {
    let unpriced: [XRayUnpriced]

    var body: some View {
        Text("Unpriced: \(unpriced.map(\.name).joined(separator: ", ")). Counted at cost.")
            .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
            .foregroundStyle(Theme.inkTertiary)
            .fixedSize(horizontal: false, vertical: true)
    }
}
