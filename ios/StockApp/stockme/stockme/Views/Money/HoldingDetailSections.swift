import SwiftUI

// Sections of HoldingDetailView (C11, spec 3.2). Each renders only with data.

struct HoldingSectionTitle: View {
    let text: String
    var body: some View {
        Text(text).font(Theme.sectionCapsLabel()).tracking(1.5).foregroundStyle(Theme.securityGold)
    }
}

/// "You're offline. Showing your last loaded values."
struct HoldingStatusBanner: View {
    let text: String
    var body: some View {
        HStack(spacing: Theme.Spacing.tight) {
            Image(systemName: "wifi.slash").foregroundStyle(Theme.bearRed)
            Text(text)
                .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
                .foregroundStyle(Theme.inkPrimary)
            Spacer(minLength: 0)
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
        .accessibilityElement(children: .combine)
    }
}

/// Label / value line inside a card.
struct HoldingFigureRow: View {
    let label: String
    let value: String
    var valueColor: Color = Theme.inkPrimary
    var body: some View {
        HStack {
            Text(label)
                .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
            Spacer()
            Text(value)
                .font(Theme.monoTabular(size: 13, relativeTo: .footnote))
                .foregroundStyle(valueColor)
        }
    }
}

struct HoldingPositionCard: View {
    let position: HoldingPosition
    var notes: String? = nil
    var targetPrice: Double? = nil
    let hideValues: Bool

    private func money(_ v: Double) -> String { hideValues ? "₹ \(MoneyReturnCopy.mask)" : IndianFormatter.formatLakhsCrores(v) }
    private var quantity: String { DecimalText.editable(position.quantity, maxFractionDigits: 3) }
    private var priceText: String {
        guard position.priceStatus != "unavailable", let p = position.price else { return "Unavailable" }
        return IndianFormatter.price(p)
    }
    private var priceNote: String? {
        let asOf = MoneyReturnCopy.day(position.priceAsOf)
        switch position.priceStatus {
        case "stale": return asOf.map { "Last available price, as of \($0)." } ?? "Last available price."
        case "nav": return asOf.map { "NAV as of \($0)." } ?? "Latest NAV."
        case "unavailable": return "No current price: valued at what you paid."
        default: return nil
        }
    }
    private var pnlText: String {
        if hideValues { return "₹ \(MoneyReturnCopy.mask)" }
        let pct = position.pnlPct.map { " (\(IndianFormatter.delta($0)))" } ?? ""
        return (position.pnlInr >= 0 ? "+" : "") + IndianFormatter.formatLakhsCrores(position.pnlInr) + pct
    }
    private var summary: String {
        var parts = ["My position", "\(quantity) units", "average cost \(IndianFormatter.price(position.avgCost))",
                     "current price \(priceText)", "value \(money(position.valueInr))", "profit or loss \(pnlText)"]
        if let priceNote { parts.append(priceNote) }
        return parts.joined(separator: ", ")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HoldingSectionTitle(text: "MY POSITION")
            Text(money(position.valueInr))
                .font(.title.weight(.bold)).monospaced()
                .foregroundStyle(Theme.inkPrimary)
            HoldingFigureRow(label: "Profit / loss", value: pnlText,
                             valueColor: hideValues ? Theme.inkPrimary : (position.pnlInr >= 0 ? Theme.bullGreen : Theme.bearRed))
            GuillocheDivider()
            HoldingFigureRow(label: "Units", value: quantity)
            HoldingFigureRow(label: "Average cost", value: IndianFormatter.price(position.avgCost))
            HoldingFigureRow(label: "Invested", value: money(position.investedInr))
            HoldingFigureRow(label: "Current price", value: priceText)
            if let priceNote {
                Text(priceNote)
                    .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                    .foregroundStyle(Theme.inkTertiary)
            }
            if let targetPrice, targetPrice > 0 {
                HoldingFigureRow(label: "Your target price", value: IndianFormatter.price(targetPrice))
            }
            if let notes, !notes.isEmpty {
                Text("Your note: \(notes)")
                    .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkSecondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(summary + (notes.flatMap { $0.isEmpty ? nil : ", your note: \($0)" } ?? ""))
    }
}

/// Lines from MoneyReturnCopy (holding or portfolio). Shared by HoldingReturnCard and PortfolioReturnCard.
struct ReturnCopyLines: View {
    let copy: ReturnCopy
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(copy.headline)
                .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .headline))
                .foregroundStyle(Theme.inkPrimary)
            if let nifty = copy.nifty {
                Text(nifty)
                    .font(Theme.serialNumberFont(size: 13, relativeTo: .subheadline))
                    .foregroundStyle(Theme.inkSecondary)
            }
            ForEach(copy.notes, id: \.self) { note in
                Text(note)
                    .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .fixedSize(horizontal: false, vertical: true)
        .accessibilityElement(children: .combine)
    }
}

struct HoldingReturnCard: View {
    let copy: ReturnCopy
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HoldingSectionTitle(text: "YOUR RETURN")
            ReturnCopyLines(copy: copy)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

/// Free actions only: the stock report is the existing String destination (no paid run here).
struct HoldingActionsBar: View {
    let ticker: String
    let showReport: Bool
    let onAlert: () -> Void
    let onTrade: () -> Void

    var body: some View {
        HStack(spacing: Theme.Spacing.medium) {
            if showReport {
                NavigationLink(value: ticker) { HoldingActionLabel(icon: "doc.text.magnifyingglass", title: "Stock report") }
                    .buttonStyle(EKPressStyle())
            }
            Button { HapticManager.selection(); onAlert() } label: { HoldingActionLabel(icon: "bell", title: "Set alert") }
                .buttonStyle(EKPressStyle())
            Button { HapticManager.selection(); onTrade() } label: { HoldingActionLabel(icon: "plus.circle", title: "Add transaction") }
                .buttonStyle(EKPressStyle())
        }
    }
}

struct HoldingActionLabel: View {
    let icon: String
    let title: String
    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Image(systemName: icon).font(.body.weight(.semibold))
            Text(title).font(Theme.officialStampFont(size: 10, relativeTo: .caption2)).multilineTextAlignment(.center)
        }
        .foregroundStyle(Theme.securityGold)
        .frame(maxWidth: .infinity, minHeight: 44)
        .padding(.vertical, Theme.Spacing.medium)
        .banknoteCard()
        .accessibilityElement(children: .combine)
    }
}

struct HoldingTransactionsCard: View {
    let transactions: [HoldingLedgerTransaction]
    let hideValues: Bool
    @State private var showAll = false
    private static let collapsed = 10

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HoldingSectionTitle(text: "TRANSACTIONS")
            let rows = showAll ? transactions : Array(transactions.prefix(Self.collapsed))
            ForEach(rows) { tx in
                HoldingTransactionRow(tx: tx, hideValues: hideValues)
                if tx.id != rows.last?.id { GuillocheDivider() }
            }
            if transactions.count > Self.collapsed && !showAll {
                Button("Show all \(transactions.count)") { HapticManager.selection(); showAll = true }
                    .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                    .foregroundStyle(Theme.securityGold)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct HoldingTransactionRow: View {
    let tx: HoldingLedgerTransaction
    let hideValues: Bool

    private var title: String {
        switch tx.type {
        case "BUY": return "Bought"
        case "SELL": return "Sold"
        case "DIVIDEND": return "Dividend"
        case "SPLIT": return "Split"
        case "BONUS": return "Bonus"
        case "ADJUST": return "Edited holding"
        default: return tx.type.capitalized
        }
    }
    private var detail: String {
        let qty = DecimalText.editable(tx.quantity, maxFractionDigits: 3)
        switch tx.type {
        case "BUY", "SELL":
            let fees = tx.fees > 0 ? " + \(IndianFormatter.price(tx.fees)) fees" : ""
            return "\(qty) at \(IndianFormatter.price(tx.price))" + fees
        case "DIVIDEND":
            return hideValues ? "₹ \(MoneyReturnCopy.mask)" : IndianFormatter.formatLakhsCrores(tx.quantity * tx.price)
        case "ADJUST":
            return "\(qty) units at \(IndianFormatter.price(tx.price)) average cost"
        default:
            return qty
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            HStack(spacing: Theme.Spacing.tight) {
                Text(title)
                    .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .subheadline))
                    .foregroundStyle(Theme.inkPrimary)
                if tx.imported {
                    Text("Imported")
                        .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                        .foregroundStyle(Theme.inkSecondary)
                        .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                        .background(Theme.inkSecondary.opacity(0.12))
                        .clipShape(Capsule())
                }
                Spacer()
                Text(MoneyReturnCopy.day(tx.date) ?? "Date unknown")
                    .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                    .foregroundStyle(Theme.inkTertiary)
            }
            Text(detail)
                .font(Theme.monoTabular(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
            if let notes = tx.notes, !notes.isEmpty {
                Text(notes)
                    .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                    .foregroundStyle(Theme.inkTertiary)
                    .lineLimit(2)
            }
        }
        .accessibilityElement(children: .combine)
    }
}

struct HoldingDividendsRow: View {
    let dividends: HoldingDividends
    let hideValues: Bool
    var body: some View {
        HoldingFigureRow(label: dividends.count == 1 ? "Dividends (1 payment)" : "Dividends (\(dividends.count) payments)",
                         value: hideValues ? "₹ \(MoneyReturnCopy.mask)" : IndianFormatter.formatLakhsCrores(dividends.totalInr))
            .padding(Theme.Spacing.card)
            .banknoteCard()
            .accessibilityElement(children: .combine)
    }
}

/// The user's own journal entries for this holding (their words, not AI text).
struct HoldingJournalCard: View {
    let entries: [HoldingJournalExcerpt]
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HoldingSectionTitle(text: "YOUR JOURNAL")
            ForEach(entries) { entry in
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text([entry.action.capitalized, MoneyReturnCopy.day(entry.createdAt)].compactMap { $0 }.joined(separator: " · "))
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .foregroundStyle(Theme.inkSecondary)
                    Text(entry.reasonExcerpt)
                        .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkPrimary)
                }
                .accessibilityElement(children: .combine)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}
