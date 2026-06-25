import SwiftUI

struct AnalysisLoadingStateView: View {
    @ObservedObject var viewModel: AnalysisViewModel
    let ticker: String
    let userId: Int?
    let onCancel: () -> Void

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.sectionGap) {
                if let info = viewModel.quickInfo {
                    AnalysisStockHeaderCard(info: info)
                }

                AnalysisSkeletonView()

                VStack(spacing: Theme.Spacing.screen) {
                    let scanType = viewModel.jobStatus?.scanType ?? "standard"
                    if viewModel.isLoading || viewModel.jobStatus != nil {
                        HStack(spacing: Theme.Spacing.tight) {
                            Image(systemName: scanType == "extreme" ? "tornado" : "waveform.badge.magnifyingglass")
                                .font(Theme.microLabel())
                            Text(scanType == "extreme" ? "EXTREME ANALYSIS ACTIVE" : "ANALYSIS ACTIVE")
                                .font(Theme.sectionCapsLabel(size: 8))
                                .tracking(1.5)
                        }
                        .foregroundStyle(Theme.goldPrimary)
                        .padding(.horizontal, Theme.Spacing.standard)
                        .padding(.vertical, Theme.Spacing.tight)
                        .background(Theme.goldMuted.opacity(0.5))
                        .clipShape(Capsule())
                        .overlay(Capsule().stroke(Theme.goldMuted, lineWidth: 0.5))
                    }

                    if !viewModel.engineCheckpoints.isEmpty {
                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text("ENGINE ACTIVITY")
                                .font(Theme.officialStampFont(size: 10))
                                .foregroundStyle(Theme.inkTertiary)
                            ForEach(viewModel.engineCheckpoints.reversed().prefix(6)) { event in
                                CheckpointRow(event: event)
                            }
                        }
                        .padding(Theme.Spacing.card)
                        .background(Theme.canvasDeep)
                        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                            .stroke(Theme.borderFine, lineWidth: 0.5))
                        .cornerRadius(Theme.CornerRadius.card)
                    } else {
                        DialecticProgressView(
                            userId: userId,
                            ticker: ticker
                        )
                    }

                    Button(action: onCancel) {
                        Text("CANCEL ANALYSIS")
                            .font(Theme.sectionCapsLabel(size: 9))
                            .foregroundStyle(Theme.dataNegative)
                            .padding(.vertical, Theme.Spacing.medium)
                            .padding(.horizontal, Theme.Spacing.screen)
                            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                .stroke(Theme.dataNegative.opacity(0.3), lineWidth: 1))
                    }
                }
                .padding(.top, Theme.Spacing.screen)
                if let info = viewModel.quickInfo {
                    VStack(alignment: .leading, spacing: Theme.Spacing.screen) {
                        SectionHeaderView(title: "COMPANY PROFILE")
                        if let desc = info.description {
                            Text(desc)
                                .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                                .foregroundStyle(Theme.inkSecondary)
                                .lineSpacing(6)
                        }
                        GuillocheGuillocheDivider()
                        if let officers = info.officers, !officers.isEmpty {
                            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                                Text("KEY EXECUTIVES")
                                    .font(Theme.sectionCapsLabel(size: 8))
                                    .foregroundStyle(Theme.inkSecondary)
                                ForEach(officers, id: \.self) { officer in
                                    Text("• \(officer.uppercased())")
                                        .font(Theme.monoTabular(size: 13))
                                        .foregroundStyle(Theme.inkPrimary)
                                }
                            }
                        }
                    }
                    .padding(Theme.Spacing.card)
                    .background(Theme.surfaceElevated)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderSubtle, lineWidth: 0.5))
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.bottom, 100)
        }
    }
}

// MARK: - Skeleton View (matches Verdict + Factor Radar geometry)

private struct AnalysisSkeletonView: View {
    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            // Skeleton Card 1: Verdict card shape
            VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                HStack {
                    SkeletonPill(width: 90, height: 10)
                    Spacer()
                    SkeletonPill(width: 70, height: 8)
                }

                HStack(spacing: Theme.Spacing.standard) {
                    SkeletonPill(width: 100, height: 36)
                    Spacer()
                    SkeletonCircle(size: 64)
                }

                SkeletonPill(width: 140, height: 8)

                HStack(spacing: Theme.Spacing.xSmall) {
                    ForEach(0..<5, id: \.self) { _ in
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                            .fill(Theme.inkTertiary.opacity(0.08))
                            .frame(height: 6)
                    }
                }
            }
            .padding(Theme.Spacing.cardInset)
            .background(Theme.surfaceElevated)
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderSubtle, lineWidth: 0.5))
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
            .shimmerPlaceholder(isLoading: true)

            // Skeleton Card 2: Summary text shape
            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                SkeletonPill(width: 80, height: 8)
                SkeletonLine()
                SkeletonLine()
                SkeletonLine(widthFraction: 0.7)
            }
            .padding(Theme.Spacing.cardInset)
            .background(Theme.surfaceElevated)
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderSubtle, lineWidth: 0.5))
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
            .shimmerPlaceholder(isLoading: true)

            // Skeleton Card 3: Price targets shape
            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                SkeletonPill(width: 100, height: 8)
                ForEach(0..<3, id: \.self) { _ in
                    HStack {
                        SkeletonPill(width: 70, height: 12)
                        Spacer()
                        SkeletonPill(width: 60, height: 14)
                        SkeletonPill(width: 50, height: 12)
                    }
                }
            }
            .padding(Theme.Spacing.cardInset)
            .background(Theme.surfaceElevated)
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderSubtle, lineWidth: 0.5))
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
            .shimmerPlaceholder(isLoading: true)
        }
    }
}

private struct SkeletonPill: View {
    let width: CGFloat
    let height: CGFloat
    var body: some View {
        RoundedRectangle(cornerRadius: height / 2)
            .fill(Theme.inkTertiary.opacity(0.08))
            .frame(width: width, height: height)
    }
}

private struct SkeletonCircle: View {
    let size: CGFloat
    var body: some View {
        Circle()
            .fill(Theme.inkTertiary.opacity(0.08))
            .frame(width: size, height: size)
    }
}

private struct SkeletonLine: View {
    var widthFraction: CGFloat = 1.0
    var body: some View {
        RoundedRectangle(cornerRadius: 3)
            .fill(Theme.inkTertiary.opacity(0.08))
            .frame(maxWidth: .infinity)
            .frame(height: 12)
            .frame(maxWidth: widthFraction < 1.0 ? UIScreen.main.bounds.width * widthFraction : .infinity)
    }
}

struct AnalysisStockHeaderCard: View {
    let info: QuickInfo
    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            HStack(spacing: Theme.Spacing.card) {
                StockIcon(ticker: info.ticker, signal: info.signal)
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(info.ticker).font(Theme.serialNumberFont(size: 24)).foregroundStyle(Theme.inkPrimary)
                    Text(info.sector ?? info.industry ?? "").font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary)
                }
                Spacer()
            }
            GuillocheGuillocheDivider()
            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.small) {
                Text("₹").font(Theme.engravedSerif(size: 24, weight: .bold)).foregroundStyle(Theme.goldPrimary)
                Text((info.price ?? 0.0).inrFormatted.replacingOccurrences(of: "₹", with: ""))
                    .font(Theme.dataLarge()).foregroundStyle(Theme.inkPrimary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            HStack(spacing: Theme.Spacing.medium) {
                Text("\((info.change ?? 0.0) >= 0 ? "+" : "")\((info.change ?? 0.0).inrFormatted)")
                Text("(\((info.changePercent ?? 0.0).percentFormatted))")
            }
            .font(Theme.monoTabular(size: 16))
            .foregroundStyle((info.change ?? 0.0) >= 0 ? Theme.dataPositive : Theme.dataNegative)
        }
        .padding(Theme.Spacing.card)
        .background(Theme.surfaceElevated)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
        .padding(.top, Theme.Spacing.screen)
    }
}
