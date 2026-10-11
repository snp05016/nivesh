import SwiftUI

// MARK: - Bilingual Banknote Header

struct AppHeader: View {
    let name: String
    let initials: String
    var isScrolled: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack(alignment: .center) {
                // Left: Bilingual brand
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("निवेश")
                        .font(Theme.hindiFont(size: 18, relativeTo: .title3))
                        .foregroundStyle(Theme.goldPrimary)
                    Text("NIVESH")
                        .font(Theme.monoTabular(size: 9, relativeTo: .caption2))
                        .foregroundStyle(Theme.inkTertiary)
                }

                Spacer()

                // Right: notification + avatar
                HStack(spacing: Theme.Spacing.standard) {
                    Image(systemName: "bell.fill")
                        .font(.footnote)
                        .foregroundStyle(Theme.inkSecondary)
                        .frame(width: Theme.Spacing.xLarge, height: Theme.Spacing.xLarge)
                        .background(Theme.surfaceElevated)
                        .clipShape(Circle())

                    GovernorSealAvatar(initials: initials)
                }
            }

            GuillocheDivider()
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.top, Theme.Spacing.standard)
        .background(.ultraThinMaterial.opacity(isScrolled ? 1.0 : 0.0))
    }
}

// MARK: - Stock Long Press Preview

private struct StockPreviewCard: View {
    let stock: Stock

    private var avatarSize: CGFloat { UIScreen.main.bounds.width * 0.11 }

    var body: some View {
        GeometryReader { geo in
            VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                HStack(spacing: Theme.Spacing.standard) {
                    ZStack {
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                            .fill(Theme.inkSecondary.opacity(0.08))
                            .frame(width: avatarSize, height: avatarSize)
                        Text(String(stock.ticker.prefix(2)))
                            .font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .headline))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.borderFine, lineWidth: 0.5))

                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text(stock.companyName)
                            .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .subheadline))
                            .foregroundStyle(Theme.inkPrimary)
                        Text(stock.ticker + " • " + stock.exchange)
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    Spacer()
                    if let signal = stock.signal {
                        BanknoteSignalBadge(signal: signal, rotation: -4)
                    }
                }

                GuillocheDivider()

                HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.small) {
                    Text("₹")
                        .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .callout))
                        .foregroundStyle(Theme.goldPrimary)
                    Text(stock.currentPrice.inrFormatted.replacingOccurrences(of: "₹", with: ""))
                        .font(Theme.dataLarge(size: 24, relativeTo: .title2))
                        .foregroundStyle(Theme.inkPrimary)
                    Spacer()
                    PnlBadge(value: stock.changePercent, showPercentage: true)
                }

                Text("LONG PRESS · TAP TO ANALYSE")
                    .font(Theme.officialStampFont(size: 7, relativeTo: .caption2))
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, alignment: .center)
            }
            .padding(Theme.Spacing.screen)
            .frame(width: geo.size.width * 0.85)
            .glassCard()
            .background(Theme.canvasDeep)
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.large).stroke(Theme.borderFine, lineWidth: 1))
        }
    }
}

// MARK: - Banknote Stock Row

struct StockRow: View {
    let stock: Stock
    var asmGsmStatus: String? = nil
    var lastSignal: String? = nil
    var daysUntilEvent: Int? = nil

    private var hasQuote: Bool { stock.currentPrice > 0 }

    var body: some View {
        HStack(spacing: Theme.Spacing.none) {
            // Left border stripe — 3pt, colored by return direction
            // No quote yet (price <= 0): neutral stripe, never a fabricated green "+0.00%".
            Rectangle()
                .fill(hasQuote ? (stock.changePercent >= 0 ? Theme.dataPositive : Theme.dataNegative) : Theme.inkTertiary)
                .frame(width: 3)
                .padding(.vertical, Theme.Spacing.standard)

            HStack(spacing: Theme.Spacing.card) {
                // Stock icon
                ZStack {
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(Theme.inkSecondary.opacity(0.08))
                        .frame(width: 44, height: 44) // 44pt minimum touch target per Apple HIG
                    Text(String(stock.ticker.prefix(2)))
                        .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .callout))
                        .foregroundStyle(Theme.inkPrimary)
                }
                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.borderFine, lineWidth: 0.5))

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(stock.companyName)
                        .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .subheadline))
                        .foregroundStyle(Theme.inkPrimary)
                    Text(stock.ticker)
                        .font(Theme.monoTabular(size: 10, relativeTo: .caption2))
                        .foregroundStyle(Theme.inkSecondary)

                    // ASM/GSM status chip
                    if let status = asmGsmStatus, status == "ASM" || status == "GSM" {
                        Text("⚠ \(status)")
                            .font(Theme.microLabel(size: 9).weight(.semibold))
                            .foregroundStyle(Theme.onStatus)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.dataNegative)
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
                    }

                    // Last signal badge
                    if let signal = lastSignal {
                        Text(signal.uppercased())
                            .font(Theme.microLabel(size: 9))
                            .foregroundStyle(Theme.goldPrimary)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.goldMuted)
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
                    }

                    // Upcoming event pill
                    if let days = daysUntilEvent, days <= 14 {
                        Text("Results in \(days)d")
                            .font(Theme.microLabel(size: 9))
                            .foregroundStyle(Theme.onStatus)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(days <= 3 ? Theme.dataNegative : Theme.goldPrimary)
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
                    }
                }

                Spacer()

                // Price + Change
                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                    Text(hasQuote ? stock.currentPrice.inrFormatted : "—")
                        .font(Theme.monoTabular(size: 15, relativeTo: .subheadline))
                        .foregroundStyle(Theme.inkPrimary)
                        .contentTransition(.numericText())

                    if hasQuote {
                        PnlBadge(value: stock.changePercent, showPercentage: true)
                    }
                }

                if let signal = stock.signal {
                    BanknoteSignalBadge(signal: signal)
                        .stampAppear()
                        .padding(.trailing, Theme.Spacing.small)
                }
            }
            .padding(.vertical, Theme.Spacing.standard)
            .padding(.leading, Theme.Spacing.standard)
            .padding(.trailing, Theme.Spacing.card)
        }
        .frame(minHeight: 64)
        .background(Theme.surfaceElevated)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(Theme.borderSubtle, lineWidth: 0.5)
        )
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
        HStack(spacing: Theme.Spacing.tight) {
            Text(name)
                .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote).weight(.bold))
                .foregroundStyle(Theme.inkPrimary)

            Text(value)
                .font(Theme.monoTabular(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
                .contentTransition(.numericText())

            Text(change)
                .font(Theme.monoTabular(size: 11, relativeTo: .caption2))
                .foregroundStyle(isPositive ? Theme.dataPositive : Theme.dataNegative)
                .padding(.horizontal, Theme.Spacing.tight)
                .padding(.vertical, Theme.Spacing.xSmall)
                .background((isPositive ? Theme.dataPositive : Theme.dataNegative).opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
                .contentTransition(.numericText())
        }
        .padding(.horizontal, Theme.Spacing.standard)
        .padding(.vertical, Theme.Spacing.medium)
        .background(Theme.surfaceElevated)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.pill)
                .stroke(Theme.goldMuted.opacity(0.6), lineWidth: 0.5)
        )
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.pill))
        .scaleEffect(pressed ? 0.97 : 1.0)
        .animation(.spring(response: 0.25, dampingFraction: 0.85), value: pressed)
        .onLongPressGesture(minimumDuration: 0.3, pressing: { isPressing in
            pressed = isPressing
            if isPressing { HapticManager.impact(.soft) }
        }, perform: {
            HapticManager.impact(.medium)
        })
        // One VoiceOver element; direction spoken, not only coloured.
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(name) \(value), \(isPositive ? "up" : "down") \(change.trimmingCharacters(in: CharacterSet(charactersIn: "+-")))")
    }
}

// MARK: - Section Header (bilingual)

struct SectionHeader: View {
    let title: String
    var hindiTitle: String? = nil
    var actionLabel: String? = nil
    var action: (() -> Void)? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            HStack(alignment: .bottom) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    if let hindi = hindiTitle {
                        Text(hindi)
                            .font(Theme.hindiFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    Text(title.uppercased())
                        .font(Theme.sectionCapsLabel())
                        .tracking(1.2)
                        .foregroundStyle(Theme.inkPrimary)
                }
                Spacer()
                if let label = actionLabel, let action = action {
                    Button(action: {
                        HapticManager.selection()
                        action()
                    }) {
                        Text(label)
                            .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                            .foregroundStyle(Theme.goldPrimary)
                    }
                    .buttonStyle(EKPressStyle())
                }
            }

            // Gold underline — 2pt × 24pt, left-aligned
            Rectangle()
                .fill(Theme.goldPrimary.opacity(0.6))
                .frame(width: 24, height: 2)
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
                .foregroundStyle(Theme.inkPrimary)
        }
        .overlay(Rectangle().stroke(Theme.borderFine, lineWidth: 0.5))
    }
}
