import SwiftUI

// MARK: - Factor profile (spec 10.1 item 5)

/// Five neutral 0-100 bars, one per family, each comparing the stock with the 200
/// most-traded NSE stocks. The family label carries its "higher = ..." meaning; a row
/// expands to its member metrics.
struct ResearchFactorProfileCard: View {
    let profile: ResearchFactorProfile?
    let narrative: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            ResearchSectionTitle(title: "Factor profile")
            Text("Each bar places this stock between 0 and 100 compared with the 200 most-traded NSE stocks. Higher is not better or worse; the label says what it measures.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
            ResearchNarrativeText(text: narrative)
            let families = profile?.families ?? []
            if families.isEmpty {
                ResearchUnavailableText(reason: nil)
            }
            ForEach(Array(families.enumerated()), id: \.offset) { _, family in
                ResearchFactorFamilyRow(family: family)
            }
        }
        .researchCardStyle()
    }
}

private struct ResearchFactorFamilyRow: View {
    let family: ResearchFactorFamily
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Button {
                withAnimation(.easeInOut(duration: 0.2)) { expanded.toggle() }
            } label: {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.medium) {
                        Text(family.label ?? "")
                            .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkPrimary)
                            .multilineTextAlignment(.leading)
                            .fixedSize(horizontal: false, vertical: true)
                        Spacer(minLength: Theme.Spacing.medium)
                        Image(systemName: expanded ? "chevron.up" : "chevron.down")
                            .font(.caption)
                            .foregroundStyle(Theme.inkTertiary)
                            .accessibilityHidden(true)
                    }
                    ResearchPercentileBar(fact: family.pctl)
                }
            }
            .buttonStyle(EKPressStyle())
            .accessibilityHint(expanded ? "Hides the measures behind this bar" : "Shows the measures behind this bar")
            if expanded {
                ForEach(Array((family.metrics ?? []).enumerated()), id: \.offset) { _, metric in
                    ResearchFactorMetricRow(metric: metric)
                }
            }
        }
        .padding(.vertical, Theme.Spacing.small)
    }
}

/// A 0-100 bar in one neutral colour plus the server's percentile text.
private struct ResearchPercentileBar: View {
    let fact: ResearchFact?

    var body: some View {
        if let fact, let value = fact.value, fact.display != nil {
            HStack(spacing: Theme.Spacing.medium) {
                ProgressView(value: min(max(value, 0), 100), total: 100)
                    .tint(Theme.securityGold)
                    .accessibilityHidden(true)
                ResearchFactValue(fact: fact, size: 13)
            }
        } else {
            ResearchUnavailableText(reason: fact?.reason)
        }
    }
}

private struct ResearchFactorMetricRow: View {
    let metric: ResearchFactorMetric

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(metric.label ?? metric.featureId ?? "")
                .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack(spacing: Theme.Spacing.medium) {
                if let value = metric.value {
                    ResearchFactValue(fact: value, size: 13)
                }
                Spacer(minLength: Theme.Spacing.medium)
                if let pctl = metric.pctl {
                    ResearchFactValue(fact: pctl, size: 12)
                }
            }
        }
        .padding(.leading, Theme.Spacing.standard)
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Fundamentals (spec 10.1 item 6; display only)

struct ResearchFundamentalsCard: View {
    let fundamentals: ResearchFundamentals?
    let narrative: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            ResearchSectionTitle(title: "Fundamentals")
            if let fundamentals, fundamentals.status != .unavailable {
                ResearchFundamentalsBody(fundamentals: fundamentals, narrative: narrative)
            } else {
                ResearchUnavailableText(reason: fundamentals?.reason)
            }
        }
        .researchCardStyle()
    }
}

private struct ResearchFundamentalsBody: View {
    let fundamentals: ResearchFundamentals
    let narrative: String?

    private var sourceBanner: String {
        "Source: Yahoo Finance, fetched \(ResearchFormat.day(fundamentals.fetchedAt)), not point-in-time; display only, not used in the outlook"
    }

    private var valuationFacts: [ResearchFact] {
        let v = fundamentals.valuation
        return [v?.peTtm, v?.pb, v?.evEbitda, v?.dividendYieldPct, v?.peSectorPctl].compactMap { $0 }
    }

    private var qualityFacts: [ResearchFact] {
        let q = fundamentals.quality
        return [q?.roePct, q?.operatingMarginPct, q?.debtToEquity, q?.cfoToPat].compactMap { $0 }
    }

    var body: some View {
        ResearchNoticeBanner(icon: "info.circle", text: sourceBanner)
        if fundamentals.status == .stale {
            Text("The latest statements on record are more than 15 months old.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
        }
        ResearchNarrativeText(text: narrative)
        ResearchFactGroup(title: "Valuation", facts: valuationFacts)
        ResearchFactGroup(title: "Quality", facts: qualityFacts)
        ResearchPiotroskiRow(piotroski: fundamentals.piotroski)
        ResearchAccountingScores(fundamentals: fundamentals)
    }
}

private struct ResearchFactGroup: View {
    let title: String
    let facts: [ResearchFact]

    var body: some View {
        if !facts.isEmpty {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                Text(title)
                    .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkSecondary)
                ForEach(Array(facts.enumerated()), id: \.offset) { _, fact in
                    ResearchFactRow(fact: fact)
                }
            }
        }
    }
}

/// "6 of 8 available checks": no grade or zone.
private struct ResearchPiotroskiRow: View {
    let piotroski: ResearchPiotroski?

    var body: some View {
        if let score = piotroski?.fScore?.display, let available = piotroski?.maxPossible?.display {
            ResearchKeyValueRow(key: "Piotroski F-score", value: "\(score) of \(available) available checks")
                .researchFactDetail(piotroski?.fScore)
        } else {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("Piotroski F-score")
                    .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkSecondary)
                ResearchUnavailableText(reason: piotroski?.fScore?.reason)
            }
        }
    }
}

/// Altman Z''-EM and Beneish M as values only; never zones or flag words.
private struct ResearchAccountingScores: View {
    let fundamentals: ResearchFundamentals

    private var notApplicable: Bool {
        fundamentals.isFinancial == true
            || fundamentals.altmanZEm?.applicable == false
            || fundamentals.beneishM?.applicable == false
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text("Accounting scores")
                .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
            if notApplicable {
                Text("Not applicable to banks, NBFCs and insurers")
                    .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkPrimary)
            } else {
                if let altman = fundamentals.altmanZEm?.value {
                    ResearchFactRow(fact: altman)
                }
                if let beneish = fundamentals.beneishM?.value {
                    ResearchFactRow(fact: beneish)
                }
                Text("Accounting ratios from Yahoo Finance; descriptive, not a judgement on the company.")
                    .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                    .foregroundStyle(Theme.inkTertiary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}
