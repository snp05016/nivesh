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
            } else if let signal = signal {
                MLSignalLoadedContent(signal: signal, onOpenQuantLab: onOpenQuantLab)
            } else {
                MLSignalUnavailableContent()
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

            // Row 2: Confidence + Model + Hit Rate
            HStack(spacing: Theme.Spacing.standard) {
                // Confidence
                MLSignalConfidenceView(confidencePct: signal.confidencePct)

                // Model badge
                MLSignalModelBadge(label: engineLabel, isHeuristic: isHeuristic)

                // Hit rate (if available)
                if let reliability = signal.reliability,
                   let hitRate = reliability.hitRate30d {
                    MLSignalHitRateView(hitRate: hitRate)
                }

                Spacer()
            }

            // Row 3: CTA
            Button(action: {
                HapticManager.selection()
                onOpenQuantLab()
            }) {
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

// MARK: - Hit Rate View

private struct MLSignalHitRateView: View {
    let hitRate: Double

    var body: some View {
        HStack(spacing: Theme.Spacing.small) {
            Text("30d Hit")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(0.5)
                .foregroundStyle(Theme.inkTertiary)
            Text(String(format: "%.1f%%", hitRate * 100))
                .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
        }
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
    var body: some View {
        HStack(spacing: Theme.Spacing.medium) {
            Image(systemName: "waveform.path.ecg")
                .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkTertiary)
            Text("ML ENGINE UNAVAILABLE")
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundStyle(Theme.inkTertiary)
            Spacer()
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
            signal: nil,
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
