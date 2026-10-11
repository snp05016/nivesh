import Combine
import SwiftUI

// MARK: - ML Signal Card (Stock Profile Overview)

struct StockMLSignalCard: View {
    let signal: MLSignalResponse?
    let isLoading: Bool
    let error: String?
    let onOpenQuantLab: () -> Void

    var body: some View {
        Group {
            if isLoading {
                MLSignalShimmerContent()
            } else if let error = error {
                MLSignalErrorContent(message: error)
            } else if let signal = signal, signal.status == "ready" {
                MLSignalLoadedContent(signal: signal, onOpenQuantLab: onOpenQuantLab)
            } else {
                // no_edge (no validated model) or unavailable: no direction or confidence
                MLSignalUnavailableContent(message: signal?.warning, onOpenQuantLab: onOpenQuantLab)
            }
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity)
        .banknoteCard()
    }
}

// MARK: - Loaded State

private struct MLSignalLoadedContent: View {
    let signal: MLSignalResponse
    let onOpenQuantLab: () -> Void

    private var directionColor: Color {
        switch signal.direction {
        case 1: return Theme.bullGreen
        case -1: return Theme.bearRed
        default: return Theme.inkTertiary
        }
    }

    private var directionText: String {
        switch signal.direction {
        case 1: return "\u{25B2} BULLISH"
        case -1: return "\u{25BC} BEARISH"
        default: return "\u{2014} NEUTRAL"
        }
    }

    private var engineLabel: String {
        switch signal.mlEngineMode {
        case "trained_lightgbm_baseline": return "LightGBM"
        case "fallback_technical_heuristic": return "Heuristic"
        default:
            return signal.mlEngineMode
                .replacingOccurrences(of: "_", with: " ")
                .capitalized
        }
    }

    private var isHeuristic: Bool {
        signal.mlEngineMode == "fallback_technical_heuristic"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            // Row 1: Header + Direction
            HStack(alignment: .center) {
                // ML SIGNAL label
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "waveform.path.ecg")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .foregroundStyle(Theme.securityGold)
                    Text("ML SIGNAL")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .tracking(1.5)
                        .foregroundStyle(Theme.securityGold)
                }

                Spacer()

                // Direction badge
                Text(directionText)
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.2)
                    .foregroundStyle(directionColor)
            }

            // Row 2: Confidence + Model. No hit rate: unverified accuracy claims
            // about the app's own calls stay out of user views (REG-11, PaRRVA).
            HStack(spacing: Theme.Spacing.standard) {
                // Confidence
                MLSignalConfidenceView(confidencePct: signal.confidencePct)

                // Model badge
                MLSignalModelBadge(label: engineLabel, isHeuristic: isHeuristic)

                Spacer()
            }

            // Row 3: CTA
            Button(action: { HapticManager.selection(); onOpenQuantLab() }) {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "flask")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                    Text("OPEN QUANT LAB")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .tracking(1.2)
                }
                .foregroundStyle(Theme.securityGold)
                .padding(.horizontal, Theme.Spacing.standard)
                .padding(.vertical, Theme.Spacing.tight)
                .background(Theme.securityGold.opacity(0.10))
                .clipShape(Capsule())
                .overlay(
                    Capsule()
                        .stroke(Theme.securityGold.opacity(0.35), lineWidth: 0.5)
                )
            }
            .buttonStyle(EKPressStyle())
            .frame(maxWidth: .infinity, alignment: .trailing)
        }
    }
}

// MARK: - Confidence View

private struct MLSignalConfidenceView: View {
    let confidencePct: Int?

    var body: some View {
        HStack(spacing: Theme.Spacing.small) {
            Text("CONF")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.0)
                .foregroundStyle(Theme.inkTertiary)
            Text(confidencePct != nil ? "\(confidencePct!)%" : "--")
                .font(Theme.serialNumberFont(size: 14, relativeTo: .footnote))
                .foregroundStyle(Theme.inkPrimary)
        }
    }
}

// MARK: - Model Badge

private struct MLSignalModelBadge: View {
    let label: String
    let isHeuristic: Bool

    private var badgeColor: Color {
        isHeuristic ? Theme.holdAmber : Theme.signalEmerald
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.xSmall) {
            if isHeuristic {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                    .foregroundStyle(badgeColor)
            }
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(0.8)
                .foregroundStyle(badgeColor)
        }
        .padding(.horizontal, Theme.Spacing.medium)
        .padding(.vertical, Theme.Spacing.xSmall)
        .background(badgeColor.opacity(0.10))
        .clipShape(Capsule())
    }
}

// MARK: - Shimmer (Loading) State

private struct MLSignalShimmerContent: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.inkTertiary.opacity(0.15))
                    .frame(width: 80, height: 12)
                Spacer()
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.inkTertiary.opacity(0.15))
                    .frame(width: 60, height: 12)
            }
            HStack(spacing: Theme.Spacing.standard) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.inkTertiary.opacity(0.12))
                    .frame(width: 48, height: 16)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.pill)
                    .fill(Theme.inkTertiary.opacity(0.12))
                    .frame(width: 64, height: 16)
                Spacer()
            }
        }
        .shimmerPlaceholder(isLoading: true)
    }
}

// MARK: - Unavailable State

private struct MLSignalUnavailableContent: View {
    var message: String? = nil
    let onOpenQuantLab: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack(spacing: Theme.Spacing.medium) {
                Image(systemName: "waveform.path.ecg")
                    .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.inkTertiary)
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("ML ENGINE")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .tracking(1.2)
                        .foregroundStyle(Theme.inkTertiary)
                    Text(message ?? "Signal unavailable — tap to explore Quant Lab")
                        .font(.caption2)
                        .foregroundStyle(Theme.inkTertiary.opacity(0.7))
                }
                Spacer()
            }
            Button(action: { HapticManager.selection(); onOpenQuantLab() }) {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "flask")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                    Text("OPEN QUANT LAB")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .tracking(1.2)
                }
                .foregroundStyle(Theme.securityGold)
                .padding(.horizontal, Theme.Spacing.standard)
                .padding(.vertical, Theme.Spacing.tight)
                .background(Theme.securityGold.opacity(0.10))
                .clipShape(Capsule())
                .overlay(Capsule().stroke(Theme.securityGold.opacity(0.35), lineWidth: 0.5))
            }
            .buttonStyle(EKPressStyle())
            .frame(maxWidth: .infinity, alignment: .trailing)
        }
    }
}

// MARK: - Error State

private struct MLSignalErrorContent: View {
    let message: String

    var body: some View {
        HStack(spacing: Theme.Spacing.medium) {
            Image(systemName: "exclamationmark.triangle")
                .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.bearRed)
            Text(message)
                .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
                .lineLimit(2)
            Spacer()
        }
    }
}

// MARK: - Preview

#Preview("Loaded — Bullish LightGBM") {
    ZStack {
        Theme.canvas.ignoresSafeArea()
        StockMLSignalCard(
            signal: MLSignalResponse(
                symbol: "RELIANCE",
                direction: 1,
                directionLabel: "BULLISH",
                confidence: 0.85,
                confidencePct: 85,
                modelVersion: "lightgbm_baseline_alpha158_v1",
                modelStatus: "active",
                mlEngineMode: "trained_lightgbm_baseline",
                lightgbmLoaded: true,
                predictionHorizon: "20d",
                generatedAt: "2026-06-27T10:00:00Z",
                featureDrivers: [
                    FeatureDriver(feature: "RSI_14", contribution: 0.32, direction: "positive"),
                    FeatureDriver(feature: "MACD_signal", contribution: 0.25, direction: "positive"),
                    FeatureDriver(feature: "Volume_SMA", contribution: -0.12, direction: "negative"),
                ],
                reliability: MLReliability(hitRate30d: 0.65, brierScore30d: 0.22, calibrationError30d: 0.10),
                status: "ready",
                warning: nil
            ),
            isLoading: false,
            error: nil,
            onOpenQuantLab: {}
        )
        .padding(.horizontal, Theme.screenPadding)
    }
}

#Preview("Loading") {
    ZStack {
        Theme.canvas.ignoresSafeArea()
        StockMLSignalCard(
            signal: nil,
            isLoading: true,
            error: nil,
            onOpenQuantLab: {}
        )
        .padding(.horizontal, Theme.screenPadding)
    }
}

#Preview("Error") {
    ZStack {
        Theme.canvas.ignoresSafeArea()
        StockMLSignalCard(
            signal: nil,
            isLoading: false,
            error: "Connection to ML engine timed out",
            onOpenQuantLab: {}
        )
        .padding(.horizontal, Theme.screenPadding)
    }
}
