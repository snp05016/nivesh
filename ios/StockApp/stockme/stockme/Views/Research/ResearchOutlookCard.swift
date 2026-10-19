import SwiftUI

/// "What testing found" at one horizon (spec 10.1 item 3): a neutral evidence badge,
/// the server's tier text and tested event, and a link to the model card. v1 shows no
/// stock-level number here: no cohort, frequency or dot grid.
struct ResearchOutlookCard: View {
    let outlook: ResearchOutlook
    let onModelCard: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.medium) {
                Text(outlook.horizonLabel ?? horizonFallback)
                    .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .headline))
                    .foregroundStyle(Theme.inkPrimary)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: Theme.Spacing.medium)
                ResearchTierBadge(tier: outlook.evidenceTier)
            }
            Text(outlook.tierText ?? "The outlook is unavailable for this report.")
                .font(Theme.engravedSerif(size: 14, relativeTo: .subheadline))
                .foregroundStyle(Theme.inkPrimary)
                .fixedSize(horizontal: false, vertical: true)
            if let event = outlook.event {
                Text("Tested question: whether a stock \(event).")
                    .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            ResearchLinkButton(title: "What we tested", action: onModelCard)
        }
        .researchCardStyle()
    }

    private var horizonFallback: String {
        guard let days = outlook.horizonDays else { return "Outlook" }
        return "Next \(days) trading days"
    }
}

/// Neutral by design: secondary ink with a gold outline for every tier, so no tier
/// reads as good or bad news about the stock.
struct ResearchTierBadge: View {
    let tier: ResearchEvidenceTier?

    private var text: String {
        switch tier {
        case .validatedEdge: return "Passed pre-set checks"
        case .weakEvidence: return "Some evidence"
        case .noReliableEdge: return "No reliable edge"
        case .outOfUniverse: return "Not computed"
        case .unavailable, .unknown, nil: return "Unavailable"
        }
    }

    var body: some View {
        Text(text.uppercased())
            .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
            .tracking(0.8)
            .foregroundStyle(Theme.inkSecondary)
            .padding(.horizontal, Theme.Spacing.medium)
            .padding(.vertical, Theme.Spacing.small)
            .overlay(Capsule().stroke(Theme.securityGold, lineWidth: 1))
            .accessibilityLabel("Evidence: \(text)")
    }
}
