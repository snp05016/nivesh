import SwiftUI
#if os(iOS)
import UIKit
#endif

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
    var diagnosticPayload: DiagnosticErrorPayload? = nil

    @State private var isRetrying = false
    @State private var showDiagnostics = false

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

                    // Diagnostic drawer (when payload is present)
                    if let payload = diagnosticPayload {
                        DiagnosticErrorDrawer(payload: payload, isExpanded: $showDiagnostics)
                    }

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

// MARK: - Diagnostic Error Drawer

/// Expandable diagnostic telemetry panel styled with banknote aesthetic.
/// Shows correlation_id, error_uuid, classification, failing_node_contract,
/// exception message, and cleaned traceback in monospaced font.
/// Includes a "COPY TO CLIPBOARD" button for the full JSON payload.
struct DiagnosticErrorDrawer: View {
    let payload: DiagnosticErrorPayload
    @Binding var isExpanded: Bool

    var body: some View {
        VStack(spacing: 0) {
            // ── Tappable header row ────────────────────────────────────
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    isExpanded.toggle()
                }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: isExpanded ? "chevron.down" : "chevron.right")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(Theme.securityGold)
                    Text("DIAGNOSTICS")
                        .font(.system(size: 10, weight: .bold, design: .monospaced))
                        .tracking(2)
                        .foregroundColor(Theme.securityGold)
                    Spacer()
                    Text(isExpanded ? "▾" : "▸")
                        .font(.system(size: 10, weight: .bold, design: .monospaced))
                        .foregroundColor(Theme.securityGold.opacity(0.6))
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(Theme.securityGold.opacity(0.04))
            }

            // ── Expanded diagnostic details ────────────────────────────
            if isExpanded {
                VStack(alignment: .leading, spacing: 10) {
                    // Divider
                    Rectangle()
                        .fill(Theme.borderSage)
                        .frame(height: 1)

                    // Correlation ID
                    diagnosticRow(label: "correlation_id", value: payload.correlationId)
                    // Error UUID
                    diagnosticRow(label: "error_uuid", value: payload.errorUuid)
                    // Classification
                    diagnosticRow(label: "classification", value: payload.classification)
                    // Failing node contract
                    if let contract = payload.telemetry?.failingNodeContract {
                        diagnosticRow(label: "failing_node", value: contract)
                    }
                    // Exception
                    if let exc = payload.exception {
                        if let type = exc.type {
                            diagnosticRow(label: "exception_type", value: type)
                        }
                        if let msg = exc.message {
                            diagnosticRow(label: "exception_msg", value: msg)
                        }
                        if let traceback = exc.cleanedTraceback, !traceback.isEmpty {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("cleaned_traceback")
                                    .font(.system(size: 9, weight: .bold, design: .monospaced))
                                    .foregroundColor(Theme.inkTertiary)
                                ForEach(traceback, id: \.self) { line in
                                    Text(line)
                                        .font(.system(size: 9, weight: .regular, design: .monospaced))
                                        .foregroundColor(Theme.inkSecondary)
                                        .lineLimit(3)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    }

                    // ── Copy to Clipboard button ───────────────────────
                    Button {
                        copyPayloadToClipboard()
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: "doc.on.doc")
                                .font(.system(size: 9))
                            Text("COPY TO CLIPBOARD")
                                .font(.system(size: 9, weight: .bold, design: .monospaced))
                                .tracking(1)
                        }
                        .foregroundColor(Theme.securityGold)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .frame(maxWidth: .infinity)
                        .background(Theme.securityGold.opacity(0.06))
                        .overlay(
                            RoundedRectangle(cornerRadius: 2)
                                .stroke(Theme.securityGold.opacity(0.2), lineWidth: 1)
                        )
                    }
                }
                .padding(12)
                .background(Theme.canvasDeep)
                .overlay(
                    RoundedRectangle(cornerRadius: 2)
                        .stroke(Theme.borderSage, lineWidth: 1)
                )
            }
        }
    }

    // MARK: - Row helper

    private func diagnosticRow(label: String, value: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text(label)
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .foregroundColor(Theme.inkTertiary)
                .frame(width: 110, alignment: .leading)
            Text(value)
                .font(.system(size: 10, weight: .regular, design: .monospaced))
                .foregroundColor(Theme.inkPrimary)
                .multilineTextAlignment(.leading)
            Spacer()
        }
    }

    // MARK: - Clipboard

    private func copyPayloadToClipboard() {
        guard let data = try? JSONEncoder().encode(payload),
              let json = String(data: data, encoding: .utf8) else { return }
        #if os(iOS)
        UIPasteboard.general.string = json
        #endif
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

            BanknoteErrorCanvas(
                title: "Earnings Feed Failed",
                detail: "Earnings feed aggregation failed due to NSE API rate limit.",
                diagnosticPayload: DiagnosticErrorPayload(
                    errorUuid: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    correlationId: "nivesh_ios_earnings_a1b2c3d4",
                    timestamp: "2026-06-05T03:30:00Z",
                    subsystem: "EARNINGS_FEED",
                    classification: "API_RATE_LIMIT",
                    context: DiagnosticContext(
                        targetTicker: "RELIANCE",
                        marketHoursState: "REGULAR",
                        activeDataProvider: "nse_data_provider"
                    ),
                    telemetry: DiagnosticTelemetry(
                        httpMethod: "GET",
                        requestRoute: "/api/v1/earnings/feed",
                        iosSwiftFile: "EarningsDashboardView.swift",
                        failingNodeContract: "GET /api/v1/earnings/feed -> EarningsFeedResponse"
                    ),
                    exception: DiagnosticException(
                        type: "ConnectionError",
                        message: "NSE API returned 429 Too Many Requests",
                        cleanedTraceback: [
                            "File backend/routers/earnings.py line 142 in get_earnings_feed",
                            "File backend/services/nse_data_provider.py line 89 in fetch_earnings_data",
                            "requests.exceptions.HTTPError: 429 Client Error"
                        ]
                    ),
                    automatedRecoveryAction: "Exponential backoff retry scheduled (attempt 2/3)"
                )
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
