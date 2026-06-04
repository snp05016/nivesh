import SwiftUI

// MARK: - Banknote Error Canvas

/// Renders API/data fetch failures using the banknote design aesthetic.
/// Displays a failure vector description cleanly — never an empty grey canvas.
///
/// Usage:
///   BanknoteErrorCanvas(title: "Market Data Unavailable",
///                       detail: "NSE connection timed out after 15 seconds.\nComponent: nse_data_provider",
///                       retryAction: { await vm.refresh() })
struct BanknoteErrorCanvas: View {
    let title: String
    let detail: String
    var retryAction: (() async -> Void)? = nil

    @State private var isRetrying = false

    var body: some View {
        VStack(spacing: 0) {
            // ── Paper texture card ──────────────────────────────────────
            VStack(spacing: 20) {
                // Currency band header
                currencyBand

                // Error content
                VStack(spacing: 12) {
                    // Denomination-style error title
                    Text(title)
                        .font(Font.custom("Georgia-Bold", size: 16))
                        .foregroundColor(Theme.bearRed)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)

                    // RBI-style security separator
                    Rectangle()
                        .fill(Theme.bearRed.opacity(0.15))
                        .frame(height: 1)
                        .overlay(
                            Text("ERROR VECTOR")
                                .font(.system(size: 8, weight: .bold, design: .monospaced))
                                .tracking(2)
                                .foregroundColor(Theme.bearRed.opacity(0.5))
                                .padding(.horizontal, 8)
                                .background(Theme.canvasDeep)
                        )

                    // Detail text — clean monospace for diagnostic traces
                    Text(detail)
                        .font(.system(size: 11, weight: .regular, design: .monospaced))
                        .foregroundColor(Theme.inkSecondary)
                        .multilineTextAlignment(.leading)
                        .lineSpacing(4)
                        .fixedSize(horizontal: false, vertical: true)

                    // Retry button (if provided)
                    if let retryAction = retryAction {
                        Button {
                            isRetrying = true
                            Task {
                                await retryAction()
                                isRetrying = false
                            }
                        } label: {
                            HStack(spacing: 6) {
                                if isRetrying {
                                    ProgressView()
                                        .scaleEffect(0.7)
                                        .tint(Theme.securityGold)
                                }
                                Text(isRetrying ? "Retrying…" : "RETRY")
                                    .font(.system(size: 10, weight: .bold))
                                    .tracking(2)
                            }
                            .foregroundColor(Theme.securityGold)
                            .padding(.horizontal, 20)
                            .padding(.vertical, 8)
                            .background(Theme.securityGold.opacity(0.08))
                            .overlay(
                                RoundedRectangle(cornerRadius: 2)
                                    .stroke(Theme.securityGold.opacity(0.3), lineWidth: 1)
                            )
                        }
                        .disabled(isRetrying)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 20)
            }
            .background(
                ZStack {
                    Theme.canvasDeep
                    // Subtle watermark
                    Text("₹")
                        .font(Font.custom("Georgia-Bold", size: 180))
                        .foregroundColor(Theme.bearRed.opacity(0.025))
                        .offset(x: 60, y: 20)
                        .allowsHitTesting(false)
                }
            )
            .overlay(
                RoundedRectangle(cornerRadius: 2)
                    .stroke(Theme.borderSage, lineWidth: 1)
            )
            .cornerRadius(2)
            .shadow(color: Theme.canvasShadow.opacity(0.12), radius: 4, y: 2)

            // ── Serial number footer ────────────────────────────────────
            Text("NIVESH APPAREL • RESERVE BANK OF INDIA • ERROR: \(title.prefix(18).uppercased())")
                .font(.system(size: 7, weight: .medium, design: .monospaced))
                .foregroundColor(Theme.inkTertiary.opacity(0.5))
                .tracking(1.5)
                .padding(.top, 8)
        }
        .padding(Theme.cardPadding)
    }

    // MARK: - Currency Band

    private var currencyBand: some View {
        HStack(spacing: 0) {
            // Left guilloche block
            Rectangle()
                .fill(Theme.bearRed.opacity(0.12))
                .frame(width: 40, height: 28)
                .overlay(
                    HStack(spacing: 2) {
                        ForEach(0..<3, id: \.self) { _ in
                            Circle()
                                .fill(Theme.bearRed.opacity(0.3))
                                .frame(width: 4, height: 4)
                        }
                    }
                )

            // Center label
            VStack(spacing: 0) {
                Rectangle().fill(Theme.bearRed.opacity(0.3)).frame(height: 1)
                Text("DATA FAULT")
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .tracking(4)
                    .foregroundColor(Theme.bearRed.opacity(0.7))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 3)
                Rectangle().fill(Theme.bearRed.opacity(0.3)).frame(height: 1)
            }

            // Right guilloche block (mirror)
            Rectangle()
                .fill(Theme.bearRed.opacity(0.12))
                .frame(width: 40, height: 28)
                .overlay(
                    HStack(spacing: 2) {
                        ForEach(0..<3, id: \.self) { _ in
                            Circle()
                                .fill(Theme.bearRed.opacity(0.3))
                                .frame(width: 4, height: 4)
                        }
                    }
                )
        }
    }
}

// MARK: - Convenience Error Row for Dashboard Sections

/// Displays a compact inline error for a single dashboard section.
/// Use inside VStack alongside other cards.
struct MarketSectionErrorRow: View {
    let sectionLabel: String
    let errorMessage: String

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.holdAmber)
                Text(sectionLabel)
                    .font(Theme.labelStyle)
                    .foregroundColor(Theme.inkSecondary)
                Spacer()
                Text("UNAVAILABLE")
                    .font(.system(size: 8, weight: .bold, design: .monospaced))
                    .tracking(1.5)
                    .foregroundColor(Theme.bearRed.opacity(0.6))
            }
            Text(errorMessage)
                .font(.system(size: 10, weight: .regular, design: .monospaced))
                .foregroundColor(Theme.inkTertiary)
                .multilineTextAlignment(.leading)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(10)
                .background(Theme.bearRed.opacity(0.04))
                .overlay(
                    RoundedRectangle(cornerRadius: 2)
                        .stroke(Theme.bearRed.opacity(0.1), lineWidth: 1)
                )
                .cornerRadius(2)
        }
    }
}

// MARK: - Preview

#if DEBUG
struct BanknoteErrorCanvas_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 24) {
            BanknoteErrorCanvas(
                title: "Market Data Unavailable",
                detail: "NSE connection timed out after 15 seconds.\nComponent: nse_data_provider\nTicker: RELIANCE\n\nError: HTTPSConnectionPool(host='nseindia.com', port=443): Read timed out.",
                retryAction: { try? await Task.sleep(nanoseconds: 1_000_000_000) }
            )

            MarketSectionErrorRow(
                sectionLabel: "LIVE REPORTING SYNC",
                errorMessage: "filings_extractor: NSE API returned 503 Service Unavailable"
            )
        }
        .padding()
        .background(Theme.canvas)
    }
}
#endif
