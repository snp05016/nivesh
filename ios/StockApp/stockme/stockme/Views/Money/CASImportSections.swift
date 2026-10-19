import SwiftUI

/// Gold filled button label used by the import flow.
struct CASButtonLabel: View {
    let title: String
    var filled = true
    var body: some View {
        Text(title)
            .font(Theme.engravedSerif(size: 14, weight: .semibold, relativeTo: .body))
            .foregroundStyle(filled ? Theme.canvas : Theme.inkPrimary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, Theme.Spacing.standard)
            .background(filled ? Theme.securityGold : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(Theme.inkTertiary, lineWidth: filled ? 0 : 1)
            )
    }
}

/// Notice cas-v1 (verbatim, versioned) with the two toggles that enable "Choose PDF".
struct CASConsentCard: View {
    @Binding var attestsOwnStatement: Bool
    @Binding var agreesToNotice: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HoldingSectionTitle(text: "BEFORE YOU UPLOAD")
            noticeLine("What Nivesh keeps:", CASNotice.keeps)
            noticeLine("What Nivesh doesn't keep:", CASNotice.doesNotKeep)
            noticeLine("Why:", CASNotice.why)
            noticeLine("Your control:", CASNotice.control)
            Toggle(CASNotice.attestLabel, isOn: $attestsOwnStatement)
            Toggle(CASNotice.agreeLabel, isOn: $agreesToNotice)
        }
        .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
        .foregroundStyle(Theme.inkSecondary)
        .tint(Theme.securityGold)
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func noticeLine(_ label: String, _ text: String) -> some View {
        Text("**\(label)** \(text)")
            .fixedSize(horizontal: false, vertical: true)
    }
}

/// The parsed statement: totals, then one row per fund.
struct CASPreviewList: View {
    let preview: CASPreview
    var hideValues = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HoldingSectionTitle(text: "FROM YOUR STATEMENT")
            if let to = MoneyReturnCopy.day(preview.statement.to) {
                Text("Statement dated \(to). \(preview.totals.balance) of \(preview.totals.schemes) funds will be added as balances.")
                    .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkSecondary)
            }
            VStack(spacing: Theme.Spacing.none) {
                ForEach(Array(preview.schemes.enumerated()), id: \.element.id) { idx, scheme in
                    CASPreviewRow(scheme: scheme, hideValues: hideValues)
                    if idx != preview.schemes.count - 1 {
                        GuillocheDivider().padding(.horizontal, Theme.Spacing.card)
                    }
                }
            }
            .banknoteCard()
        }
    }
}

struct CASPreviewRow: View {
    let scheme: CASPreviewScheme
    var hideValues = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.standard) {
                Text(scheme.name)
                    .font(Theme.serialNumberFont(size: 14, relativeTo: .body).weight(.semibold))
                    .foregroundStyle(Theme.inkPrimary)
                    .lineLimit(2)
                Spacer(minLength: Theme.Spacing.medium)
                Text(CASPreviewCopy.badge(scheme))
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(scheme.isBalance ? Theme.bullGreen : Theme.inkTertiary)
            }
            if let amc = scheme.amc, !amc.isEmpty {
                Text(amc)
                    .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkTertiary)
            }
            HStack {
                Text("\(DecimalText.editable(scheme.units, maxFractionDigits: 3)) units")
                Spacer()
                Text(hideValues ? "₹ ••••" : IndianFormatter.price(scheme.valuation.valueInr))
            }
            .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .footnote))
            .foregroundStyle(Theme.inkSecondary)
            if let reason = CASPreviewCopy.reason(scheme) {
                Text(reason)
                    .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkTertiary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
    }
}

/// "Added 5 funds." with a way back.
struct CASImportResultView: View {
    let funds: Int
    let onDone: () -> Void

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            Image(systemName: "checkmark.circle")
                .font(.system(size: 40))
                .foregroundStyle(Theme.bullGreen)
            Text(CASPreviewCopy.done(funds))
                .font(Theme.engravedSerif(size: 17, weight: .semibold, relativeTo: .headline))
                .foregroundStyle(Theme.inkPrimary)
            Button(action: onDone) { CASButtonLabel(title: "Done") }
                .buttonStyle(EKPressStyle())
        }
        .frame(maxWidth: .infinity)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

/// A tappable row in the Portfolio money section.
struct MoneyLinkRow: View {
    let icon: String
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: { HapticManager.selection(); action() }) {
            HStack(spacing: Theme.Spacing.standard) {
                Image(systemName: icon)
                    .font(Theme.engravedSerif(size: 18, weight: .medium))
                    .foregroundStyle(Theme.inkPrimary)
                    .frame(width: 36, height: 36)
                Text(title)
                    .font(Theme.engravedSerif(size: 14, weight: .medium, relativeTo: .body))
                    .foregroundStyle(Theme.inkPrimary)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(Theme.inkTertiary)
            }
            .padding(.horizontal, Theme.Spacing.card)
            .padding(.vertical, Theme.Spacing.standard)
        }
        .buttonStyle(EKPressStyle())
    }
}
