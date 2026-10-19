import SwiftUI

// MARK: - Banner (Holdings)

struct CorporateActionsBanner: View {
    let count: Int
    let onTap: () -> Void

    private var title: String {
        count == 1 ? "1 corporate action to review" : "\(count) corporate actions to review"
    }

    var body: some View {
        Button {
            HapticManager.selection()
            onTap()
        } label: {
            HStack(spacing: Theme.Spacing.card) {
                Image(systemName: "arrow.triangle.branch")
                    .font(Theme.serialNumberFont(size: 18, relativeTo: .headline))
                    .foregroundStyle(Theme.securityGold)
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(title)
                        .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .headline))
                        .foregroundColor(Theme.inkPrimary)
                    Text("Splits or bonus issues on your holdings")
                        .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                        .foregroundColor(Theme.inkSecondary)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Theme.securityGold.opacity(0.6))
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title). Splits or bonus issues on your holdings.")
        .accessibilityHint("Opens the review sheet")
    }
}

// MARK: - Review sheet

struct CorporateActionsReviewSheet: View {
    @ObservedObject var vm: CorporateActionsViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: Theme.Spacing.none) {
            HStack {
                Text("Review corporate actions")
                    .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title3))
                    .foregroundColor(Theme.inkPrimary)
                Spacer()
                Button("Done") {
                    HapticManager.selection()
                    dismiss()
                }
                .foregroundStyle(Theme.securityGold)
            }
            .padding(Theme.screenPadding)

            ScrollView {
                VStack(spacing: Theme.Spacing.card) {
                    if let message = vm.errorMessage {
                        Text(message)
                            .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                            .foregroundColor(Theme.bearRed)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    ForEach(vm.items) { item in
                        CorporateActionRow(
                            item: item,
                            isWorking: vm.isWorking,
                            onApply: { Task { await vm.apply(item) } },
                            onDismiss: { Task { await vm.dismiss(item) } },
                            onUndo: { Task { await vm.undo(item) } }
                        )
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
                .padding(.bottom, Theme.screenPadding)
            }
        }
        .background(Theme.canvas.ignoresSafeArea())
    }
}

// MARK: - Row

struct CorporateActionRow: View {
    let item: CorporateActionItem
    let isWorking: Bool
    let onApply: () -> Void
    let onDismiss: () -> Void
    let onUndo: () -> Void

    private var headline: String {
        var parts = [item.ticker]
        if let group = item.groupName, !group.isEmpty { parts.append(group) }
        parts.append("ex-date \(MutualFundDateText.short(item.exDate))")
        return parts.joined(separator: " · ")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text(headline)
                .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                .tracking(1.0)
                .foregroundColor(Theme.inkSecondary)
            Text(item.ratioText)
                .font(Theme.engravedSerif(size: 17, weight: .bold, relativeTo: .headline))
                .foregroundColor(Theme.inkPrimary)

            CorporateActionStatusBody(
                item: item, isWorking: isWorking, onApply: onApply, onDismiss: onDismiss, onUndo: onUndo
            )

            CorporateActionProvenance(item: item)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .accessibilityElement(children: .contain)
    }
}

private struct CorporateActionStatusBody: View {
    let item: CorporateActionItem
    let isWorking: Bool
    let onApply: () -> Void
    let onDismiss: () -> Void
    let onUndo: () -> Void

    var body: some View {
        if item.isPending {
            CorporateActionPendingBody(item: item, isWorking: isWorking, onApply: onApply, onDismiss: onDismiss)
        } else {
            CorporateActionDecidedBody(item: item, isWorking: isWorking, onUndo: onUndo)
        }
    }
}

private struct CorporateActionPendingBody: View {
    let item: CorporateActionItem
    let isWorking: Bool
    let onApply: () -> Void
    let onDismiss: () -> Void

    private var quantityLine: String? {
        guard let before = item.sharesBefore, let after = item.sharesAfter else { return nil }
        return "If you held these shares before the ex-date: \(CorporateActionNumber.shares(before)) → \(CorporateActionNumber.shares(after)) shares. Your average price adjusts so the amount you invested stays the same."
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("This holding was added after the ex-date, so Nivesh can't tell whether its quantity already includes this split or bonus.")
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundColor(Theme.inkSecondary)
            if let quantityLine {
                Text(quantityLine)
                    .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                    .foregroundColor(Theme.inkPrimary)
            }
            HStack(spacing: Theme.Spacing.standard) {
                CorporateActionButton(title: "Apply", isPrimary: true, isDisabled: isWorking, action: onApply)
                CorporateActionButton(title: "I've already updated it", isPrimary: false, isDisabled: isWorking, action: onDismiss)
            }
        }
    }
}

private struct CorporateActionDecidedBody: View {
    let item: CorporateActionItem
    let isWorking: Bool
    let onUndo: () -> Void

    private var statusLine: String {
        let day = CorporateActionDates.dayMonth(item.decidedAt)
        let suffix = day.map { " on \($0)" } ?? ""
        if item.status == "applied" {
            return day.map { "Applied \($0)." } ?? "Applied."
        }
        return "Marked as already updated\(suffix)."
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Text(statusLine)
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundColor(Theme.inkSecondary)
            Spacer()
            if item.canUndo() {
                CorporateActionButton(title: "Undo", isPrimary: false, isDisabled: isWorking, action: onUndo)
            }
        }
    }
}

private struct CorporateActionProvenance: View {
    let item: CorporateActionItem

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            if item.nseConfirmed == true {
                Text("Matches NSE closing prices")
                    .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                    .tracking(1.0)
                    .padding(.horizontal, Theme.Spacing.medium)
                    .padding(.vertical, Theme.Spacing.small)
                    .foregroundColor(Theme.bullGreen)
                    .background(Theme.bullGreen.opacity(0.12))
                    .cornerRadius(Theme.CornerRadius.badge)
            }
            Text("Source: \(item.source)")
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption))
                .foregroundColor(Theme.inkTertiary)
        }
    }
}

private struct CorporateActionButton: View {
    let title: String
    let isPrimary: Bool
    let isDisabled: Bool
    let action: () -> Void

    var body: some View {
        Button {
            HapticManager.selection()
            action()
        } label: {
            Text(title)
                .font(Theme.labelStyle)
                .padding(.horizontal, Theme.Spacing.card)
                .padding(.vertical, Theme.Spacing.medium)
                .foregroundColor(isPrimary ? Theme.canvas : Theme.inkPrimary)
                .background(isPrimary ? Theme.inkPrimary : Color.clear)
                .cornerRadius(Theme.CornerRadius.small)
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .stroke(Theme.borderFine, lineWidth: isPrimary ? 0 : 1)
                )
        }
        .buttonStyle(EKPressStyle())
        .disabled(isDisabled)
        .opacity(isDisabled ? 0.5 : 1)
        .accessibilityLabel(title)
    }
}

/// Share counts without trailing zeros: 100 -> "100", 12.5 -> "12.5".
enum CorporateActionNumber {
    private static let formatter: NumberFormatter = {
        let f = NumberFormatter()
        f.locale = Locale(identifier: "en_IN")
        f.numberStyle = .decimal
        f.maximumFractionDigits = 4
        f.minimumFractionDigits = 0
        return f
    }()

    static func shares(_ value: Double) -> String {
        formatter.string(from: NSNumber(value: value)) ?? String(value)
    }
}
