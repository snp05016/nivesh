import SwiftUI

// MARK: - Advisory Matrix Card

struct AdvisoryMatrixCard: View {
    let insights: [AdvisorInsightRow]
    let ticker: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            // Header
            HStack(alignment: .top, spacing: Theme.Spacing.none) {
                SecurityThread()

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("STREET INTELLIGENCE")
                        .font(Theme.officialStampFont(size: 10))
                        .tracking(0.8)
                        .foregroundStyle(Theme.inkPrimary)
                    Text("सलाहकार मत")
                        .font(Theme.hindiFont(size: 8))
                        .foregroundStyle(Theme.inkSecondary)
                }
                .padding(.leading, Theme.Spacing.medium)

                Spacer()

                Text("POWERED BY AI")
                    .font(Theme.officialStampFont(size: 7))
                    .tracking(0.5)
                    .foregroundStyle(Theme.securityGold)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Theme.securityGold.opacity(0.10))
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                            .stroke(Theme.securityGold.opacity(0.35), lineWidth: 0.5)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
            }
            .padding(.top, Theme.Spacing.standard)
            .padding(.trailing, 16)

            SectionDivider()
                .padding(.horizontal, 4)

            if insights.isEmpty {
                emptyState
            } else {
                insightRows
            }
        }
        .banknoteCard()
    }

    // MARK: - Empty State

    private var emptyState: some View {
        Text("No advisor commentary found for \(ticker) in the last 14 days.")
            .font(Theme.officialStampFont(size: 14))
            .foregroundStyle(Theme.inkTertiary)
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity)
            .padding(.vertical, Theme.Spacing.screen)
            .padding(.horizontal, Theme.Spacing.card)
    }

    // MARK: - Insight Rows

    private var insightRows: some View {
        VStack(spacing: Theme.Spacing.none) {
            ForEach(Array(insights.enumerated()), id: \.element.id) { index, insight in
                AdvisorInsightRowView(insight: insight)

                if index < insights.count - 1 {
                    Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                        .background(Theme.borderFine)
                        .padding(.horizontal, 16)
                }
            }
        }
        .padding(.bottom, 8)
    }

    // MARK: - Stance Chip Color

    private func stanceColor(_ stance: String) -> Color {
        switch stance.uppercased() {
        case "BULLISH": return Theme.bullGreen
        case "BEARISH": return Theme.bearRed
        default: return Theme.holdAmber
        }
    }
}

// MARK: - Single Advisor Insight Row

private struct AdvisorInsightRowView: View {
    let insight: AdvisorInsightRow

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            // Name + Stance chip
            HStack(alignment: .center, spacing: Theme.Spacing.medium) {
                Text(insight.advisorName)
                    .font(.headline)
                    .foregroundStyle(Theme.inkPrimary)

                Spacer()

                stanceChip(insight.stance)
            }

            // Catalyst summary
            Text(insight.catalystSummary)
                .font(Theme.officialStampFont(size: 14))
                .foregroundStyle(Theme.inkPrimary)
                .lineLimit(2)

            // Video title + Watch button
            HStack(alignment: .center, spacing: Theme.Spacing.medium) {
                Text(insight.videoTitle)
                    .font(Theme.officialStampFont(size: 12))
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(1)
                    .truncationMode(.tail)

                Spacer()

                watchButton
            }

            // Date · Confidence · Source
            HStack(spacing: Theme.Spacing.tight) {
                Text(formatDate(insight.publishedAt))
                    .font(Theme.serialNumberFont(size: 10))
                    .foregroundStyle(Theme.inkTertiary)

                Text("·")
                    .font(Theme.officialStampFont(size: 10))
                    .foregroundStyle(Theme.inkTertiary)

                Text(insight.confidence.uppercased())
                    .font(Theme.officialStampFont(size: 10))
                    .foregroundStyle(confidenceColor(insight.confidence))

                Text("·")
                    .font(Theme.officialStampFont(size: 10))
                    .foregroundStyle(Theme.inkTertiary)

                Text(transcriptSourceLabel(insight.transcriptSource))
                    .font(Theme.officialStampFont(size: 10))
                    .foregroundStyle(Theme.inkTertiary)
                    .lineLimit(1)
            }
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
    }

    // MARK: - Stance Chip

    private func stanceChip(_ stance: String) -> some View {
        let color = stanceColor(stance)
        return HStack(spacing: Theme.Spacing.small) {
            Circle()
                .fill(color)
                .frame(width: 6, height: 6)
            Text(stance.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .tracking(0.5)
                .foregroundStyle(color)
        }
        .padding(.horizontal, Theme.Spacing.medium)
        .padding(.vertical, Theme.Spacing.small)
        .background(color.opacity(0.10))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .stroke(color.opacity(0.35), lineWidth: 0.5)
        )
    }

    // MARK: - Watch Button

    private var watchButton: some View {
        Button {
            if let url = URL(string: insight.videoUrl) {
                UIApplication.shared.open(url)
            }
        } label: {
            HStack(spacing: Theme.Spacing.small) {
                Image(systemName: "play.fill").font(Theme.officialStampFont(size: 9))
                Text("WATCH").font(Theme.officialStampFont(size: 10))
            }
            .foregroundStyle(Theme.securityGold)
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, 5)
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.securityGold.opacity(0.6), lineWidth: 0.8))
        }
        .buttonStyle(EKPressStyle())
    }

    // MARK: - Helpers

    private func stanceColor(_ stance: String) -> Color {
        switch stance.uppercased() {
        case "BULLISH": return Theme.bullGreen
        case "BEARISH": return Theme.bearRed
        default: return Theme.holdAmber
        }
    }

    private func confidenceColor(_ confidence: String) -> Color {
        switch confidence.uppercased() {
        case "HIGH": return Theme.bullGreen
        case "LOW": return Theme.inkSecondary
        default: return Theme.holdAmber
        }
    }

    private func transcriptSourceLabel(_ source: String) -> String {
        source == "whisper_local" ? "Whisper transcript" : "YouTube captions"
    }

    private func formatDate(_ isoString: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: isoString) {
            let display = DateFormatter()
            display.dateFormat = "MMM d"
            return display.string(from: date)
        }
        // Fallback: try without fractional seconds
        formatter.formatOptions = [.withInternetDateTime]
        if let date = formatter.date(from: isoString) {
            let display = DateFormatter()
            display.dateFormat = "MMM d"
            return display.string(from: date)
        }
        return isoString.prefix(10).description
    }
}
