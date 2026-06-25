import SwiftUI
import Charts

struct SentimentTrendTabView: View {
    let ticker: String
    @State private var trend: SentimentTrend?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.Spacing.card) {
                if isLoading {
                    SPSkeletonBlock(rows: 4)
                    SPSkeletonBlock(rows: 3)
                } else if let trend = trend {
                    SentimentScoreHeroCardView(trend: trend)
                    SentimentTrendChartView(scores: trend.sentiment_scores ?? [])
                    SentimentStatsSummaryView(scores: trend.sentiment_scores ?? [])
                } else if let error = errorMessage {
                    SPEmptyStateView(message: error)
                } else {
                    SPEmptyStateView(message: "Sentiment data unavailable")
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await loadSentimentTrend() }
    }

    private func loadSentimentTrend() async {
        guard trend == nil else { return }
        isLoading = true
        do {
            trend = try await NetworkManager.shared.fetchSentimentTrend(ticker: ticker)
        } catch {
            errorMessage = "Failed to load sentiment trend"
        }
        isLoading = false
    }
}

// MARK: - Sentiment Score Hero Card

struct SentimentScoreHeroCardView: View {
    let trend: SentimentTrend

    var body: some View {
        let scores = trend.sentiment_scores ?? []
        let currentScore = scores.last?.score ?? 50
        let avgScore = scores.isEmpty ? 50 : scores.map { $0.score ?? 50 }.reduce(0, +) / Double(scores.count)

        VStack(spacing: Theme.Spacing.standard) {
            Text("SENTIMENT SCORE")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            HStack(spacing: Theme.Spacing.card) {
                ZStack {
                    Circle()
                        .stroke(Theme.inkTertiary.opacity(0.12), lineWidth: 6)
                        .frame(width: UIScreen.main.bounds.width * 0.18, height: UIScreen.main.bounds.width * 0.18)
                    Circle()
                        .trim(from: 0, to: CGFloat(min(currentScore / 100.0, 1.0)))
                        .stroke(
                            currentScore >= 65 ? Theme.bullGreen :
                            currentScore >= 35 ? Theme.holdAmber : Theme.bearRed,
                            style: StrokeStyle(lineWidth: 6, lineCap: .round)
                        )
                        .frame(width: UIScreen.main.bounds.width * 0.18, height: UIScreen.main.bounds.width * 0.18)
                        .rotationEffect(.degrees(-90))
                    VStack(spacing: 0) {
                        Text(String(format: "%.0f", currentScore))
                            .font(Theme.serialNumberFont(size: 18, relativeTo: .title3))
                            .foregroundStyle(Theme.inkPrimary)
                        Text("/100")
                            .font(Theme.microLabel(size: 7))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(currentScore >= 65 ? "Bullish Sentiment" :
                         currentScore >= 35 ? "Neutral Sentiment" : "Bearish Sentiment")
                        .font(Theme.serialNumberFont(size: 14, relativeTo: .body))
                        .foregroundStyle(
                            currentScore >= 65 ? Theme.bullGreen :
                            currentScore >= 35 ? Theme.holdAmber : Theme.bearRed
                        )
                    HStack(spacing: Theme.Spacing.xSmall) {
                        Text("Avg:")
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkTertiary)
                        Text(String(format: "%.0f", avgScore))
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                    Text("Composite score from news, social media, and analyst consensus")
                        .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineLimit(3)
                }
                Spacer()
            }

            HStack(spacing: 0) {
                Text("0")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.inkTertiary)
                Spacer()
                Text("Bearish")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.bearRed.opacity(0.8))
                Spacer()
                Text("50")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.inkTertiary)
                Spacer()
                Text("Bullish")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.bullGreen.opacity(0.8))
                Spacer()
                Text("100")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .explainableTerm("Sentiment Score")
    }
}

// MARK: - Sentiment Trend Chart

struct SentimentTrendChartView: View {
    let scores: [SentimentPoint]

    var body: some View {
        if scores.count >= 2 {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("SENTIMENT TREND")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                Chart {
                    let minScore = scores.map { $0.score ?? 50 }.min() ?? 0
                    let maxScore = scores.map { $0.score ?? 50 }.max() ?? 100
                    RectangleMark(
                        xStart: .value("Start", scores.first!.date ?? ""),
                        xEnd: .value("End", scores.last!.date ?? ""),
                        yStart: .value("Low", 0),
                        yEnd: .value("High", 35)
                    )
                    .foregroundStyle(Theme.bearRed.opacity(0.06))

                    RectangleMark(
                        xStart: .value("Start", scores.first!.date ?? ""),
                        xEnd: .value("End", scores.last!.date ?? ""),
                        yStart: .value("Low", 35),
                        yEnd: .value("High", 65)
                    )
                    .foregroundStyle(Theme.holdAmber.opacity(0.06))

                    RectangleMark(
                        xStart: .value("Start", scores.first!.date ?? ""),
                        xEnd: .value("End", scores.last!.date ?? ""),
                        yStart: .value("Low", 65),
                        yEnd: .value("High", 100)
                    )
                    .foregroundStyle(Theme.bullGreen.opacity(0.06))

                    ForEach(scores) { point in
                        let val = point.score ?? 50
                        LineMark(
                            x: .value("Date", point.date ?? ""),
                            y: .value("Score", val)
                        )
                        .foregroundStyle(
                            val >= 65 ? Theme.bullGreen :
                            val >= 35 ? Theme.holdAmber : Theme.bearRed
                        )
                        .lineStyle(StrokeStyle(lineWidth: 2))
                    }

                    ForEach(scores) { point in
                        let val = point.score ?? 50
                        PointMark(
                            x: .value("Date", point.date ?? ""),
                            y: .value("Score", val)
                        )
                        .symbolSize(16)
                        .foregroundStyle(
                            val >= 65 ? Theme.bullGreen :
                            val >= 35 ? Theme.holdAmber : Theme.bearRed
                        )
                    }
                }
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 5)) { _ in
                        AxisValueLabel()
                            .font(Theme.microLabel(size: 8))
                    }
                }
                .chartYAxis {
                    AxisMarks(values: [0, 25, 50, 75, 100]) { value in
                        AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5))
                            .foregroundStyle(Theme.borderFine)
                        AxisValueLabel()
                            .font(Theme.microLabel(size: 8))
                    }
                }
                .chartYScale(domain: 0...100)
                .frame(height: UIScreen.main.bounds.height * 0.25)

                HStack(spacing: Theme.Spacing.small) {
                    Circle()
                        .fill(Theme.bearRed.opacity(0.4))
                        .frame(width: Theme.Spacing.medium, height: Theme.Spacing.medium)
                    Text("Bearish")
                        .font(Theme.microLabel(size: 8))
                        .foregroundStyle(Theme.inkTertiary)
                    Circle()
                        .fill(Theme.holdAmber.opacity(0.4))
                        .frame(width: Theme.Spacing.medium, height: Theme.Spacing.medium)
                    Text("Neutral")
                        .font(Theme.microLabel(size: 8))
                        .foregroundStyle(Theme.inkTertiary)
                    Circle()
                        .fill(Theme.bullGreen.opacity(0.4))
                        .frame(width: Theme.Spacing.medium, height: Theme.Spacing.medium)
                    Text("Bullish")
                        .font(Theme.microLabel(size: 8))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
            .explainableTerm("Sentiment Trend")
        }
    }
}

// MARK: - Sentiment Stats Summary

struct SentimentStatsSummaryView: View {
    let scores: [SentimentPoint]

    var body: some View {
        if scores.isEmpty { return AnyView(EmptyView()) }
        let values = scores.map { $0.score ?? 50 }
        let current = values.last ?? 50
        let avg = values.reduce(0, +) / Double(values.count)
        let minVal = values.min() ?? 50
        let maxVal = values.max() ?? 50
        let trendDirection = current - (values.first ?? 50)

        return AnyView(
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("STATS SUMMARY")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.standard) {
                    SentimentStatCellView(
                        label: "CURRENT",
                        value: String(format: "%.0f", current),
                        color: current >= 65 ? Theme.bullGreen : current >= 35 ? Theme.holdAmber : Theme.bearRed
                    )
                    SentimentStatCellView(
                        label: "AVERAGE",
                        value: String(format: "%.0f", avg),
                        color: Theme.inkSecondary
                    )
                    SentimentStatCellView(
                        label: "RANGE",
                        value: "\(String(format: "%.0f", minVal))-\(String(format: "%.0f", maxVal))",
                        color: Theme.inkSecondary
                    )
                }

                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: trendDirection > 0 ? "arrow.up.right" : trendDirection < 0 ? "arrow.down.right" : "arrow.right")
                        .font(.caption)
                        .foregroundStyle(
                            trendDirection > 0 ? Theme.bullGreen :
                            trendDirection < 0 ? Theme.bearRed : Theme.inkTertiary
                        )
                    Text("\(Int(abs(trendDirection))) pts from start")
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                    Spacer()
                }
                .padding(.top, Theme.Spacing.xSmall)
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        )
    }
}

// MARK: - Stat Cell

struct SentimentStatCellView: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(label)
                .font(Theme.officialStampFont(size: 7))
                .tracking(1.0)
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .body))
                .foregroundStyle(color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.standard)
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
    }
}
