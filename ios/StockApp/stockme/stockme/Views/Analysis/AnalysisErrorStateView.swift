import SwiftUI

struct AnalysisErrorStateView: View {
    let info: AnalysisErrorInfo
    let quickInfo: QuickInfo?
    let onRetry: () -> Void

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.screen) {
                if let qi = quickInfo {
                    VStack(spacing: Theme.Spacing.card) {
                        HStack(spacing: Theme.Spacing.card) {
                            StockIcon(ticker: qi.ticker, signal: qi.signal)
                            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                                Text(qi.ticker)
                                    .font(Theme.serialNumberFont(size: 24))
                                    .foregroundStyle(Theme.inkPrimary)
                                Text("OFFICIAL QUOTATION")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                            }
                            Spacer()
                        }
                        GuillocheDivider()
                        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.small) {
                                Text("₹")
                                    .font(Theme.engravedSerif(size: 24, weight: .bold))
                                    .foregroundStyle(Theme.securityGold)
                                Text(qi.price.map { IndianFormatter.priceWithoutSymbol($0) } ?? "—")
                                    .font(Theme.serialNumberFont(size: 44))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                            if let change = qi.change {
                                HStack(spacing: Theme.Spacing.medium) {
                                    Text(IndianFormatter.signedPrice(change))
                                    Text("(\(qi.changePercent.map { $0.percentFormatted } ?? "—"))")
                                }
                                .font(Theme.serialNumberFont(size: 16))
                                .foregroundStyle(change >= 0 ? Theme.bullGreen : Theme.bearRed)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(Theme.Spacing.large)
                        .banknoteCard()
                    }
                    .padding(.top, Theme.screenPadding)
                }

                VStack(spacing: Theme.Spacing.card) {
                    HStack(spacing: Theme.Spacing.standard) {
                        Image(systemName: info.iconName)
                            .font(.title)
                            .foregroundStyle(info.isRateLimit ? Theme.holdAmber : Theme.bearRed)
                        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                            Text(info.displayTitle)
                                .font(Theme.engravedSerif(size: 16, weight: .bold))
                                .foregroundStyle(Theme.inkPrimary)
                            BanknoteSignalBadge(text: info.badgeText, color: info.isRateLimit ? Theme.holdAmber : Theme.bearRed, rotation: -3)
                        }
                        Spacer()
                        #if DEBUG
                        if let code = info.diagnostic?.errorCode {
                            Text(code)
                                .font(Theme.officialStampFont(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                                .padding(.horizontal, Theme.Spacing.medium).padding(.vertical, Theme.Spacing.small)
                                .background(Theme.inkTertiary.opacity(0.1))
                                .clipShape(Capsule())
                        }
                        #endif
                    }

                    GuillocheDivider()

                    Text(info.suggestedActionText)
                        .font(.footnote.weight(.medium))
                        .foregroundStyle(info.isRateLimit ? Theme.holdAmber : Theme.securityGold)
                        .lineSpacing(4)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(Theme.Spacing.screen)
                .banknoteCard()

                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    Label {
                        Text("WHAT WENT WRONG")
                            .font(Theme.officialStampFont(size: 11))
                            .foregroundStyle(Theme.inkPrimary)
                    } icon: {
                        Image(systemName: "magnifyingglass")
                            .foregroundStyle(Theme.bearRed)
                            .font(.footnote)
                    }

                    Text(info.userMessage)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineSpacing(5)

                    // Developer diagnostics (raw detail, phase, traces) are DEBUG-only.
                    #if DEBUG
                    Text(info.displayDetail)
                        .font(Theme.serialNumberFont(size: 11))
                        .foregroundStyle(Theme.inkTertiary)
                        .lineSpacing(3)

                    if let phase = info.diagnostic?.phaseFailed {
                        HStack(spacing: Theme.Spacing.tight) {
                            Text("FAILED PHASE:")
                                .font(Theme.officialStampFont(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                            Text(phase.replacingOccurrences(of: "_", with: " ").uppercased())
                                .font(Theme.serialNumberFont(size: 10))
                                .foregroundStyle(Theme.bearRed)
                        }
                    }
                    #endif
                }
                .padding(Theme.Spacing.screen)
                .banknoteCard()

                #if DEBUG
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    Label {
                        Text("PERFORMANCE TRACE")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                    } icon: {
                        Image(systemName: "stopwatch")
                            .foregroundStyle(Theme.securityGold)
                            .font(.footnote)
                    }

                    VStack(spacing: Theme.Spacing.medium) {
                        HStack {
                            Text("Total elapsed:")
                                .font(Theme.serialNumberFont(size: 11))
                                .foregroundStyle(Theme.inkTertiary)
                            Spacer()
                            Text(String(format: "%.1fs", info.elapsedSeconds))
                                .font(Theme.serialNumberFont(size: 11))
                                .foregroundStyle(info.elapsedSeconds > 30 ? Theme.bearRed : Theme.inkPrimary)
                        }
                        if let qiElapsed = info.quickInfoElapsed {
                            HStack {
                                Text("Parallel data fetch:")
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundStyle(Theme.inkTertiary)
                                Spacer()
                                Text(String(format: "%.1fs", qiElapsed))
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundStyle(Theme.bullGreen)
                            }
                            let analyzeElapsed = info.elapsedSeconds - qiElapsed
                            if analyzeElapsed > 0 {
                                HStack {
                                    Text("Analyze API call:")
                                        .font(Theme.serialNumberFont(size: 11))
                                        .foregroundStyle(Theme.inkTertiary)
                                    Spacer()
                                    Text(String(format: "%.1fs", analyzeElapsed))
                                        .font(Theme.serialNumberFont(size: 11))
                                        .foregroundStyle(Theme.bearRed)
                                }
                            }
                        }
                        if let ts = info.diagnostic?.timestamp {
                            HStack {
                                Text("Failed at:")
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundStyle(Theme.inkTertiary)
                                Spacer()
                                Text(ts)
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundStyle(Theme.inkSecondary)
                            }
                        }
                    }
                }
                .padding(Theme.Spacing.screen)
                .banknoteCard()

                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    Label {
                        Text("NETWORK TRACE")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                    } icon: {
                        Image(systemName: "network")
                            .foregroundStyle(Theme.inkSecondary)
                            .font(.footnote)
                    }

                    VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                        TraceRow(label: "URL", value: info.requestUrl)
                        TraceRow(label: "Method", value: "POST")
                        TraceRow(label: "HTTP Status", value: "\(info.httpStatusCode)")
                        if !info.responseHeaders.isEmpty {
                            CollapsibleSection(header: "RESPONSE HEADERS") {
                                Text(info.responseHeaders)
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundStyle(Theme.inkTertiary)
                                    .lineSpacing(3)
                            }
                        }
                        if !info.responseBody.isEmpty {
                            CollapsibleSection(header: "RAW RESPONSE BODY") {
                                Text(info.responseBody)
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundStyle(Theme.inkTertiary)
                                    .lineSpacing(3)
                            }
                        }
                    }
                }
                .padding(Theme.Spacing.screen)
                .banknoteCard()

                if let diagInfo = info.diagnostic?.diagnosticInfo, !diagInfo.isEmpty {
                    VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                        Label {
                            Text("BACKEND DIAGNOSTIC")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkPrimary)
                        } icon: {
                            Image(systemName: "gearshape.2")
                                .foregroundStyle(Theme.holdAmber)
                                .font(.footnote)
                        }

                        CollapsibleSection(header: "SERVER TRACE (tap to expand)") {
                            Text(diagInfo)
                                .font(Theme.serialNumberFont(size: 10))
                                .foregroundStyle(Theme.inkTertiary)
                                .lineSpacing(4)
                        }
                    }
                    .padding(Theme.Spacing.screen)
                    .banknoteCard()
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    Label {
                        Text("CLIENT CONTEXT")
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(Theme.inkPrimary)
                    } icon: {
                        Image(systemName: "iphone")
                            .foregroundStyle(Theme.inkSecondary)
                            .font(.footnote)
                    }

                    VStack(spacing: Theme.Spacing.tight) {
                        TraceRow(label: "App", value: "StockMe v\(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?.?.?")")
                        TraceRow(label: "Mock Mode", value: info.isMockMode ? "ON" : "OFF")
                        TraceRow(label: "Deep Scan", value: info.isDeepScan ? "ON" : "OFF")
                        TraceRow(label: "Base URL", value: info.requestUrl)
                    }
                }
                .padding(Theme.Spacing.screen)
                .banknoteCard()
                #endif

                VStack(spacing: Theme.Spacing.standard) {
                    Button(action: { HapticManager.selection(); onRetry() }) {
                        HStack(spacing: Theme.Spacing.medium) {
                            Image(systemName: "arrow.clockwise")
                            Text("RETRY ANALYSIS")
                        }
                        .font(Theme.officialStampFont(size: 12))
                        .foregroundStyle(Theme.inkPrimary)
                        .padding(.vertical, Theme.Spacing.standard)
                        .frame(maxWidth: .infinity)
                        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.inkPrimary, lineWidth: 1))
                    }
                }
                .padding(.top, Theme.Spacing.medium)

                Spacer(minLength: 80)
            }
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}
