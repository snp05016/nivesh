import SwiftUI

// MARK: - Advisory Matrix Card

struct AdvisoryMatrixCard: View {
    let insights: [AdvisorInsightRow]
    let ticker: String

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack(alignment: .top, spacing: 0) {
                SecurityThread()

                VStack(alignment: .leading, spacing: 2) {
                    Text("STREET INTELLIGENCE")
                        .font(Theme.officialStampFont(size: 10))
                        .tracking(0.8)
                        .foregroundColor(Theme.inkPrimary)
                    Text("सलाहकार मत")
                        .font(Theme.hindiFont(size: 8))
                        .foregroundColor(Theme.inkSecondary)
                }
                .padding(.leading, 10)

                Spacer()

                Text("POWERED BY AI")
                    .font(Theme.officialStampFont(size: 7))
                    .tracking(0.5)
                    .foregroundColor(Theme.securityGold)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Theme.securityGold.opacity(0.10))
                    .overlay(
                        RoundedRectangle(cornerRadius: 3)
                            .stroke(Theme.securityGold.opacity(0.35), lineWidth: 0.5)
                    )
                    .clipShape(RoundedRectangle(cornerRadius: 3))
            }
            .padding(.top, 14)
            .padding(.trailing, 16)

            GuillocheDivider()
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
            .font(.system(size: 14))
            .foregroundColor(Theme.inkTertiary)
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 20)
            .padding(.horizontal, 16)
    }

    // MARK: - Insight Rows

    private var insightRows: some View {
        VStack(spacing: 0) {
            ForEach(Array(insights.enumerated()), id: \.element.id) { index, insight in
                AdvisorInsightRowView(insight: insight)

                if index < insights.count - 1 {
                    Divider()
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
        case "BULLISH": return Color(red: 0.10, green: 0.53, blue: 0.24)
        case "BEARISH": return Color(red: 0.72, green: 0.09, blue: 0.09)
        default: return Color(red: 0.80, green: 0.55, blue: 0.05)
        }
    }
}

// MARK: - Single Advisor Insight Row

private struct AdvisorInsightRowView: View {
    let insight: AdvisorInsightRow

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            // Name + Stance chip
            HStack(alignment: .center, spacing: 8) {
                Text(insight.advisorName)
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(Theme.inkPrimary)

                Spacer()

                stanceChip(insight.stance)
            }

            // Catalyst summary
            Text(insight.catalystSummary)
                .font(.system(size: 14))
                .foregroundColor(Theme.inkPrimary)
                .lineLimit(2)

            // Video title + Watch button
            HStack(alignment: .center, spacing: 8) {
                Text(insight.videoTitle)
                    .font(.system(size: 12))
                    .foregroundColor(Theme.inkSecondary)
                    .lineLimit(1)
                    .truncationMode(.tail)

                Spacer()

                watchButton
            }

            // Date · Confidence · Source
            HStack(spacing: 6) {
                Text(formatDate(insight.publishedAt))
                    .font(Theme.serialNumberFont(size: 10))
                    .foregroundColor(Theme.inkTertiary)

                Text("·")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.inkTertiary)

                Text(insight.confidence.uppercased())
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundColor(confidenceColor(insight.confidence))

                Text("·")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.inkTertiary)

                Text(transcriptSourceLabel(insight.transcriptSource))
                    .font(.system(size: 10))
                    .foregroundColor(Theme.inkTertiary)
                    .lineLimit(1)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    // MARK: - Stance Chip

    private func stanceChip(_ stance: String) -> some View {
        let color = stanceColor(stance)
        return HStack(spacing: 4) {
            Circle()
                .fill(color)
                .frame(width: 6, height: 6)
            Text(stance.uppercased())
                .font(.system(size: 9, weight: .semibold))
                .tracking(0.5)
                .foregroundColor(color)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(color.opacity(0.10))
        .clipShape(RoundedRectangle(cornerRadius: 4))
        .overlay(
            RoundedRectangle(cornerRadius: 4)
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
            HStack(spacing: 4) {
                Image(systemName: "play.fill").font(.system(size: 9))
                Text("WATCH").font(.system(size: 10, weight: .semibold))
            }
            .foregroundColor(Theme.securityGold)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .overlay(RoundedRectangle(cornerRadius: 4).stroke(Theme.securityGold.opacity(0.6), lineWidth: 0.8))
        }
        .buttonStyle(EKPressStyle())
    }

    // MARK: - Helpers

    private func stanceColor(_ stance: String) -> Color {
        switch stance.uppercased() {
        case "BULLISH": return Color(red: 0.10, green: 0.53, blue: 0.24)
        case "BEARISH": return Color(red: 0.72, green: 0.09, blue: 0.09)
        default: return Color(red: 0.80, green: 0.55, blue: 0.05)
        }
    }

    private func confidenceColor(_ confidence: String) -> Color {
        switch confidence.uppercased() {
        case "HIGH": return Color(red: 0.10, green: 0.53, blue: 0.24)
        case "LOW": return Color.gray.opacity(0.7)
        default: return Color(red: 0.80, green: 0.55, blue: 0.05)
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
