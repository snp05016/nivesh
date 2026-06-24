import SwiftUI

// MARK: - Corporate Action Type

enum CorporateActionType: String, CaseIterable {
    case dividend = "DIVIDEND"
    case split    = "SPLIT"
    case bonus    = "BONUS"
    case buyback  = "BUYBACK"
    case rights   = "RIGHTS"

    var badgeColor: Color {
        switch self {
        case .dividend: return Theme.bullGreen
        case .split:    return Theme.securityGold
        case .bonus:    return Theme.holdAmber
        case .buyback:  return Theme.bearRedLight
        case .rights:   return Theme.inkSecondary
        }
    }

    var badgeTextColor: Color {
        switch self {
        case .dividend: return Theme.inkPrimary.opacity(0.92)
        case .split:    return Theme.inkPrimary.opacity(0.92)
        case .bonus:    return Theme.inkPrimary.opacity(0.92)
        case .buyback:  return Theme.inkPrimary.opacity(0.92)
        case .rights:   return Theme.inkPrimary.opacity(0.92)
        }
    }

    var iconName: String {
        switch self {
        case .dividend: return "indianrupeesign"
        case .split:    return "arrow.triangle.branch"
        case .bonus:    return "gift"
        case .buyback:  return "arrow.uturn.down"
        case .rights:   return "ticket"
        }
    }

    init(from string: String) {
        let uppercased = string.uppercased()
        switch uppercased {
        case "DIVIDEND": self = .dividend
        case "SPLIT":    self = .split
        case "BONUS":    self = .bonus
        case "BUYBACK":  self = .buyback
        case "RIGHTS":   self = .rights
        default:         self = .dividend
        }
    }
}

// MARK: - Main View

struct StockCorporateActionsView: View {
    let ticker: String
    let data: CorporateActionsResponse

    private var sortedActions: [CorporateAction] {
        data.actions.sorted { a, b in
            (parsedDate(a.exDate) ?? .distantPast) > (parsedDate(b.exDate) ?? .distantPast)
        }
    }

    private var upcomingSorted: [CorporateAction] {
        data.upcoming.sorted { a, b in
            (parsedDate(a.exDate) ?? .distantFuture) < (parsedDate(b.exDate) ?? .distantFuture)
        }
    }

    var body: some View {
        VStack(spacing: Theme.Spacing.none) {
            dividendSummarySection

            if !upcomingSorted.isEmpty {
                SectionDivider()
                    .padding(.top, Theme.sectionSpacing)
                    .padding(.bottom, Theme.Spacing.xLarge)
                upcomingActionsSection
            }

            if !sortedActions.isEmpty {
                SectionDivider()
                    .padding(.top, Theme.sectionSpacing)
                    .padding(.bottom, Theme.Spacing.xLarge)
                historicalTimelineSection
            }
        }
    }

    // MARK: - Dividend Summary

    private var dividendSummarySection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            SectionHeaderView(title: "DIVIDEND SUMMARY")

            VStack(spacing: Theme.Spacing.standard) {
                // Yield row
                HStack(alignment: .firstTextBaseline) {
                    Text("Dividend Yield (TTM)")
                        .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .subheadline))
                        .foregroundStyle(Theme.inkSecondary)

                    Spacer()

                    if let yield = data.dividendYieldTtm {
                        Text(String(format: "%.2f%%", yield))
                            .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                            .foregroundStyle(Theme.bullGreen)
                    } else {
                        Text("—")
                            .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }

                Rectangle()
                    .fill(Theme.borderFine)
                    .frame(height: 0.5)

                // Payout ratio row
                HStack {
                    Text("Payout Ratio")
                        .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .subheadline))
                        .foregroundStyle(Theme.inkSecondary)

                    Spacer()

                    if let ratio = data.dividendPayoutRatio {
                        Text(String(format: "%.1f%%", ratio))
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                            .foregroundStyle(Theme.inkPrimary)
                    } else {
                        Text("—")
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }

                // Last dividend
                if let lastDividend = sortedActions.first(where: {
                    CorporateActionType(from: $0.type) == .dividend
                }) {
                    Rectangle()
                        .fill(Theme.borderFine)
                        .frame(height: 0.5)

                    lastDividendRow(lastDividend)
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }

    @ViewBuilder
    private func lastDividendRow(_ action: CorporateAction) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text("LAST DIVIDEND")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.2)
                .foregroundStyle(Theme.inkTertiary)

            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(action.details)
                        .font(Theme.serialNumberFont(size: 15, relativeTo: .body))
                        .foregroundStyle(Theme.inkPrimary)

                    HStack(spacing: Theme.Spacing.tight) {
                        Text("Ex-Date:")
                            .font(Theme.officialStampFont(size: 9))
                            .tracking(0.8)
                            .foregroundStyle(Theme.inkTertiary)
                        Text(formattedDate(action.exDate))
                            .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }

                Spacer()

                if let amount = action.amount {
                    Text(IndianFormatter.price(amount))
                        .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                        .foregroundStyle(Theme.bullGreen)
                }
            }
        }
    }

    // MARK: - Upcoming Actions

    private var upcomingActionsSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            SectionHeaderView(title: "UPCOMING ACTIONS")

            VStack(spacing: Theme.Spacing.standard) {
                ForEach(Array(upcomingSorted.enumerated()), id: \.element.id) { index, action in
                    upcomingActionCard(action, isLast: index == upcomingSorted.count - 1)

                    if index < upcomingSorted.count - 1 {
                        Rectangle()
                            .fill(Theme.borderFine)
                            .frame(height: 0.5)
                            .padding(.leading, Theme.Spacing.xLarge)
                    }
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }

    private func upcomingActionCard(_ action: CorporateAction, isLast: Bool) -> some View {
        let actionType = CorporateActionType(from: action.type)
        let isFuture = isDateInFuture(action.exDate)

        return VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack {
                CorporateActionBadge(type: actionType)

                Spacer()

                if isFuture {
                    HStack(spacing: Theme.Spacing.small) {
                        Circle()
                            .fill(Theme.securityGold)
                            .frame(width: 6, height: 6)
                        Text("UPCOMING")
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(1.2)
                            .foregroundStyle(Theme.securityGold)
                    }
                }
            }

            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                // Ex-date highlighted if upcoming
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "calendar.badge.clock")
                        .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                        .foregroundStyle(isFuture ? Theme.securityGold : Theme.inkTertiary)

                    Text("Ex-Date:")
                        .font(Theme.officialStampFont(size: 9))
                        .tracking(0.8)
                        .foregroundStyle(Theme.inkTertiary)

                    Text(formattedDate(action.exDate))
                        .font(Theme.serialNumberFont(size: 15, relativeTo: .body))
                        .fontWeight(isFuture ? .bold : .medium)
                        .foregroundStyle(isFuture ? Theme.securityGold : Theme.inkPrimary)
                }

                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "doc.text")
                        .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                        .foregroundStyle(Theme.inkTertiary)

                    Text("Record Date:")
                        .font(Theme.officialStampFont(size: 9))
                        .tracking(0.8)
                        .foregroundStyle(Theme.inkTertiary)

                    Text(formattedDate(action.recordDate))
                        .font(Theme.serialNumberFont(size: 14, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                }

                if !action.details.isEmpty {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: actionType.iconName)
                            .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                            .foregroundStyle(Theme.inkTertiary)

                        Text(action.details)
                            .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .subheadline))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                }
            }
        }
    }

    // MARK: - Historical Timeline

    private var historicalTimelineSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            SectionHeaderView(title: "HISTORICAL ACTIONS")

            VStack(spacing: Theme.Spacing.none) {
                ForEach(Array(sortedActions.enumerated()), id: \.element.id) { index, action in
                    TimelineRow(
                        action: action,
                        isFirst: index == 0,
                        isLast: index == sortedActions.count - 1
                    )
                }
            }
            .padding(.vertical, Theme.Spacing.card)
            .padding(.horizontal, Theme.Spacing.card)
            .banknoteCard()
        }
    }

    // MARK: - Helpers

    private func parsedDate(_ dateStr: String) -> Date? {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_IN")
        formatter.timeZone = TimeZone(identifier: "Asia/Kolkata")

        let formats = [
            "yyyy-MM-dd",
            "dd-MMM-yyyy",
            "dd MMM yyyy",
            "MMM dd, yyyy",
            "yyyy/MM/dd"
        ]
        for fmt in formats {
            formatter.dateFormat = fmt
            if let d = formatter.date(from: dateStr) { return d }
        }
        return nil
    }

    private func formattedDate(_ dateStr: String) -> String {
        guard let date = parsedDate(dateStr) else { return dateStr }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_IN")
        formatter.dateFormat = "dd MMM yyyy"
        return formatter.string(from: date)
    }

    private func isDateInFuture(_ dateStr: String) -> Bool {
        guard let date = parsedDate(dateStr) else { return false }
        return date > Date()
    }
}

// MARK: - Corporate Action Badge

struct CorporateActionBadge: View {
    let type: CorporateActionType

    var body: some View {
        HStack(spacing: Theme.Spacing.xSmall) {
            Image(systemName: type.iconName)
                .font(Theme.officialStampFont(size: 9))

            Text(type.rawValue)
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.0)
        }
        .foregroundStyle(type.badgeTextColor)
        .padding(.horizontal, Theme.Spacing.medium)
        .padding(.vertical, Theme.Spacing.tight)
        .background(type.badgeColor.opacity(0.15))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.pill)
                .stroke(type.badgeColor.opacity(0.45), lineWidth: 0.5)
        )
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.pill))
    }
}

// MARK: - Timeline Row

struct TimelineRow: View {
    let action: CorporateAction
    let isFirst: Bool
    let isLast: Bool

    private let actionType: CorporateActionType

    init(action: CorporateAction, isFirst: Bool, isLast: Bool) {
        self.action = action
        self.isFirst = isFirst
        self.isLast = isLast
        self.actionType = CorporateActionType(from: action.type)
    }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
            // Timeline connector
            VStack(spacing: Theme.Spacing.none) {
                // Top connector line
                Rectangle()
                    .fill(isFirst ? Color.clear : Theme.borderSage)
                    .frame(width: 1.5)

                // Dot
                ZStack {
                    Circle()
                        .fill(actionType.badgeColor.opacity(0.18))
                        .frame(width: 12, height: 12)

                    Circle()
                        .fill(actionType.badgeColor)
                        .frame(width: 7, height: 7)
                }

                // Bottom connector line
                Rectangle()
                    .fill(isLast ? Color.clear : Theme.borderSage)
                    .frame(width: 1.5)
            }
            .frame(width: 14)

            // Content
            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                HStack(spacing: Theme.Spacing.small) {
                    Text(formattedDate(action.exDate))
                        .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkPrimary)

                    CorporateActionBadge(type: actionType)
                        .scaleEffect(0.9)
                }

                if !action.details.isEmpty {
                    Text(action.details)
                        .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineLimit(2)
                }

                if let amount = action.amount, amount != 0 {
                    Text(amountLabel)
                        .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                        .foregroundStyle(actionType == .dividend ? Theme.bullGreen : Theme.inkPrimary)
                }

                if let ratio = action.ratio, !ratio.isEmpty {
                    Text(ratio)
                        .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                        .foregroundStyle(Theme.securityGold)
                }

                // Announcement date in micro text
                Text("Announced \(formattedDate(action.announcementDate))")
                    .font(Theme.microLabel())
                    .foregroundStyle(Theme.inkTertiary)
            }
            .padding(.bottom, isLast ? Theme.Spacing.none : Theme.Spacing.card)
        }
    }

    private var amountLabel: String {
        guard let amount = action.amount else { return "" }
        return IndianFormatter.price(amount)
    }

    private func formattedDate(_ dateStr: String) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_IN")
        formatter.timeZone = TimeZone(identifier: "Asia/Kolkata")

        let formats = [
            "yyyy-MM-dd",
            "dd-MMM-yyyy",
            "dd MMM yyyy",
            "MMM dd, yyyy",
            "yyyy/MM/dd"
        ]
        for fmt in formats {
            formatter.dateFormat = fmt
            if let d = formatter.date(from: dateStr) {
                let out = DateFormatter()
                out.dateFormat = "dd MMM yyyy"
                return out.string(from: d)
            }
        }
        return dateStr
    }
}

// MARK: - Preview

#if DEBUG
struct StockCorporateActionsView_Previews: PreviewProvider {
    static var previews: some View {
        let sampleActions: [CorporateAction] = [
            CorporateAction(
                type: "DIVIDEND",
                announcementDate: "2025-03-15",
                exDate: "2025-03-28",
                recordDate: "2025-03-29",
                details: "Interim dividend ₹12 per equity share",
                amount: 12.0,
                ratio: nil
            ),
            CorporateAction(
                type: "SPLIT",
                announcementDate: "2025-01-20",
                exDate: "2025-02-05",
                recordDate: "2025-02-06",
                details: "Sub-division of shares from ₹10 to ₹2 face value",
                amount: nil,
                ratio: "1:5"
            ),
            CorporateAction(
                type: "BONUS",
                announcementDate: "2024-11-10",
                exDate: "2024-11-25",
                recordDate: "2024-11-26",
                details: "Bonus issue in the ratio of 1:2",
                amount: nil,
                ratio: "1:2"
            ),
            CorporateAction(
                type: "BUYBACK",
                announcementDate: "2024-08-01",
                exDate: "2024-08-18",
                recordDate: "2024-08-19",
                details: "Buyback of up to 50,00,000 shares at ₹2,500 per share",
                amount: 1_25_00_00_000,
                ratio: nil
            ),
            CorporateAction(
                type: "DIVIDEND",
                announcementDate: "2024-05-10",
                exDate: "2024-05-24",
                recordDate: "2024-05-25",
                details: "Final dividend ₹18 per equity share",
                amount: 18.0,
                ratio: nil
            )
        ]

        let sampleUpcoming: [CorporateAction] = [
            CorporateAction(
                type: "RIGHTS",
                announcementDate: "2025-06-20",
                exDate: "2025-07-10",
                recordDate: "2025-07-11",
                details: "Rights issue in the ratio of 1:4 at ₹150 per share",
                amount: nil,
                ratio: "1:4"
            ),
            CorporateAction(
                type: "DIVIDEND",
                announcementDate: "2025-06-15",
                exDate: "2025-07-05",
                recordDate: "2025-07-06",
                details: "Final dividend ₹15 per equity share",
                amount: 15.0,
                ratio: nil
            )
        ]

        let response = CorporateActionsResponse(
            ticker: "RELIANCE",
            actions: sampleActions,
            upcoming: sampleUpcoming,
            dividendYieldTtm: 0.42,
            dividendPayoutRatio: 28.5
        )

        ScrollView {
            StockCorporateActionsView(ticker: "RELIANCE", data: response)
                .padding(.horizontal, Theme.screenPadding)
                .padding(.vertical, Theme.Spacing.card)
        }
        .background(Theme.canvas)
        .preferredColorScheme(.dark)
    }
}
#endif
