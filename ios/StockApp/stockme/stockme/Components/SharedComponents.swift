import SwiftUI

// MARK: - Bilingual Banknote Header

struct AppHeader: View {
    let name: String
    let initials: String

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("भारतीय वित्तीय विश्लेषण")
                        .font(Theme.hindiFont(size: 11, relativeTo: .caption))
                        .foregroundColor(Theme.inkSecondary)
                    Text("RESERVE BANK OF INTELLIGENCE")
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .foregroundColor(Theme.inkPrimary)
                }
                Spacer()
                ZStack {
                    Circle()
                        .stroke(Theme.borderSage, lineWidth: 0.5)
                        .frame(width: 38, height: 38)
                    Text("₹")
                        .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title3))
                        .foregroundColor(Theme.inkPrimary)
                }
            }

            GuillocheDivider()

            HStack(alignment: .bottom) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("खाता धारक / ACCOUNT HOLDER")
                        .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                        .foregroundColor(Theme.inkSecondary)
                    Text(name.uppercased())
                        .font(Theme.engravedSerif(size: 24, weight: .bold, relativeTo: .title2))
                        .foregroundColor(Theme.inkPrimary)
                }
                Spacer()
                GovernorSealAvatar(initials: initials)
            }
        }
    }
}

// MARK: - Stock Long Press Preview

private struct StockPreviewCard: View {
    let stock: Stock

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(Theme.inkSecondary.opacity(0.08))
                        .frame(width: 48, height: 48)
                    Text(String(stock.ticker.prefix(2)))
                        .font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .headline))
                        .foregroundColor(Theme.inkPrimary)
                }
                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.borderFine, lineWidth: 0.5))

                VStack(alignment: .leading, spacing: 3) {
                    Text(stock.companyName)
                        .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .subheadline))
                        .foregroundColor(Theme.inkPrimary)
                    Text(stock.ticker + " • " + stock.exchange)
                        .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                        .foregroundColor(Theme.inkSecondary)
                }
                Spacer()
                if let signal = stock.signal {
                    BanknoteSignalBadge(signal: signal, rotation: -4)
                }
            }

            GuillocheDivider()

            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text("₹")
                    .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .callout))
                    .foregroundColor(Theme.securityGold)
                Text(stock.currentPrice.inrFormatted.replacingOccurrences(of: "₹", with: ""))
                    .font(Theme.serialNumberFont(size: 28, relativeTo: .title))
                    .foregroundColor(Theme.inkPrimary)
                Spacer()
                Text((stock.changePercent >= 0 ? "+" : "") + stock.changePercent.percentFormatted)
                    .font(Theme.serialNumberFont(size: 16, relativeTo: .callout))
                    .foregroundColor(stock.changePercent >= 0 ? Theme.bullGreen : Theme.bearRed)
                    .padding(.horizontal, Theme.Spacing.medium)
                    .padding(.vertical, Theme.Spacing.small)
                    .background((stock.changePercent >= 0 ? Theme.bullGreen : Theme.bearRed).opacity(0.08))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
            }

            Text("LONG PRESS · TAP TO ANALYSE")
                .font(Theme.officialStampFont(size: 7, relativeTo: .caption2))
                .foregroundColor(Theme.inkTertiary)
                .frame(maxWidth: .infinity, alignment: .center)
        }
        .padding(Theme.Spacing.screen)
        .frame(width: UIScreen.main.bounds.width * 0.85)
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.large).stroke(Theme.borderFine, lineWidth: 1))
    }
}

// MARK: - Banknote Stock Row

struct StockRow: View {
    let stock: Stock
    var asmGsmStatus: String? = nil
    var lastSignal: String? = nil
    var daysUntilEvent: Int? = nil

    var body: some View {
        HStack(spacing: 0) {
            Rectangle()
                .fill(Theme.inkSecondary.opacity(0.35))
                .frame(width: 1)
                .padding(.vertical, Theme.Spacing.standard)

            HStack(spacing: 16) {
                ZStack {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Theme.inkSecondary.opacity(0.05))
                        .frame(width: 44, height: 44)
                    Text(String(stock.ticker.prefix(2)))
                        .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .callout))
                        .foregroundColor(Theme.inkPrimary)
                }
                .overlay(RoundedRectangle(cornerRadius: 2).stroke(Theme.borderFine, lineWidth: 0.5))

                VStack(alignment: .leading, spacing: 2) {
                    Text(stock.companyName)
                        .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .callout))
                        .foregroundColor(Theme.inkPrimary)
                    Text(stock.ticker)
                        .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                        .foregroundColor(Theme.inkSecondary)

                    // ASM/GSM status chip
                    if let status = asmGsmStatus, status == "ASM" || status == "GSM" {
                        Text("⚠ \(status)")
                            .font(.caption2.weight(.semibold))
                            .foregroundColor(.white)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.signalRuby)
                            .cornerRadius(Theme.CornerRadius.small)
                    }

                    // Last signal badge
                    if let signal = lastSignal {
                        Text(signal.uppercased())
                            .font(.caption2.weight(.medium))
                            .foregroundColor(Theme.securityGold)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.securityGold.opacity(0.12))
                            .cornerRadius(Theme.CornerRadius.small)
                    }

                    // Upcoming event pill
                    if let days = daysUntilEvent, days <= 14 {
                        Text("Results in \(days)d")
                            .font(.caption2.weight(.medium))
                            .foregroundColor(.white)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(days <= 3 ? Theme.signalRuby : Theme.securityGold)
                            .cornerRadius(Theme.CornerRadius.small)
                    }
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 4) {
                    Text(stock.currentPrice.inrFormatted)
                        .font(Theme.serialNumberFont(size: 14, relativeTo: .footnote))
                        .foregroundColor(Theme.inkPrimary)
                        .contentTransition(.numericText())
                    Text((stock.changePercent >= 0 ? "+" : "") + stock.changePercent.percentFormatted)
                        .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                        .foregroundColor(stock.changePercent >= 0 ? Theme.bullGreen : Theme.bearRed)
                        .contentTransition(.numericText())
                }

                if let signal = stock.signal {
                    BanknoteSignalBadge(signal: signal)
                        .stampAppear()
                        .padding(.trailing, 4)
                }
            }
            .padding(.vertical, Theme.Spacing.standard)
            .padding(.leading, Theme.Spacing.standard)
            .padding(.trailing, Theme.Spacing.card)
        }
        .banknoteCard()
        .contextMenu {
            Button {
                HapticManager.selection()
            } label: {
                Label("Analyse \(stock.ticker)", systemImage: "chart.line.uptrend.xyaxis")
            }
            Button {
                HapticManager.light()
                UIPasteboard.general.string = stock.ticker
            } label: {
                Label("Copy Ticker", systemImage: "doc.on.doc")
            }
        } preview: {
            StockPreviewCard(stock: stock)
                .onAppear { HapticManager.impact(.medium) }
        }
    }
}

// MARK: - Market Index Chip

struct IndexChip: View {
    let name: String
    let value: String
    let change: String
    let isPositive: Bool

    @State private var pressed = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(name)
                .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                .foregroundColor(Theme.inkSecondary)
            HStack(spacing: 8) {
                Text(value)
                    .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                    .foregroundColor(Theme.inkPrimary)
                    .contentTransition(.numericText())
                Text(change)
                    .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                    .foregroundColor(isPositive ? Theme.bullGreen : Theme.bearRed)
                    .contentTransition(.numericText())
            }
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
        .banknoteCard()
        .scaleEffect(pressed ? 0.95 : 1.0)
        .animation(.spring(response: 0.2, dampingFraction: 0.7), value: pressed)
        .onLongPressGesture(minimumDuration: 0.3, pressing: { isPressing in
            pressed = isPressing
            if isPressing { HapticManager.impact(.soft) }
        }, perform: {
            HapticManager.impact(.medium)
        })
    }
}

// MARK: - Section Header (bilingual)

struct SectionHeader: View {
    let title: String
    var hindiTitle: String? = nil
    var actionLabel: String? = nil
    var action: (() -> Void)? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .bottom) {
                VStack(alignment: .leading, spacing: 2) {
                    if let hindi = hindiTitle {
                        Text(hindi)
                            .font(Theme.hindiFont(size: 11, relativeTo: .caption))
                            .foregroundColor(Theme.inkSecondary)
                    }
                    Text(title.uppercased())
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                        .foregroundColor(Theme.inkPrimary)
                }
                Spacer()
                if let label = actionLabel, let action = action {
                    Button(action: {
                        HapticManager.light()
                        action()
                    }) {
                        Text(label)
                            .font(.caption.weight(.bold))
                            .foregroundColor(Theme.securityGold)
                    }
                }
            }
            GuillocheDivider()
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - Stock Icon (ticker initial square)

struct StockIcon: View {
    let ticker: String
    let signal: Signal?

    var body: some View {
        ZStack {
            Rectangle()
                .fill(Theme.inkSecondary.opacity(0.05))
                .frame(width: 44, height: 44)
            Text(String(ticker.prefix(2)))
                .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .callout))
                .foregroundColor(Theme.inkPrimary)
        }
        .overlay(Rectangle().stroke(Theme.borderFine, lineWidth: 0.5))
    }
}
