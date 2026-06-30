import SwiftUI

/// Live view of the running analysis — checkpoint list, progress, cancel button.
/// Presented as a sheet from the global running pill; also reachable from any screen
/// by tapping the pill. Survives navigation/backgrounding.
struct EngineActivityView: View {
    @EnvironmentObject var engineManager: AnalysisEngineManager
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                DenominationBackground(denomination: .hundred)

                ScrollView {
                    VStack(alignment: .leading, spacing: Theme.Spacing.sectionGap) {
                        // Header
                        headerSection

                        // Progress bar
                        progressSection

                        GuillocheDivider()
                            .padding(.horizontal, Theme.screenPadding)

                        // Live checkpoints
                        if !engineManager.checkpoints.isEmpty {
                            checkpointsSection
                        } else if engineManager.isRunning {
                            emptyCheckpointsPlaceholder
                        }

                        // Error / terminal state
                        if let err = engineManager.error, !err.isEmpty {
                            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                                Text("ERROR")
                                    .font(Theme.officialStampFont(size: 10))
                                    .foregroundStyle(Theme.signalRuby)
                                Text(err)
                                    .font(.caption)
                                    .foregroundStyle(Theme.inkSecondary)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.vertical, Theme.Spacing.card)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Theme.signalRuby.opacity(0.06))
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                                    .stroke(Theme.signalRuby.opacity(0.2), lineWidth: 0.5)
                            )
                            .cornerRadius(Theme.CornerRadius.card)
                            .padding(.horizontal, Theme.screenPadding)
                        }

                        Spacer(minLength: Theme.Spacing.large)
                    }
                }

                // Cancel button pinned to bottom
                if engineManager.isRunning {
                    VStack {
                        Spacer()
                        cancelButton
                    }
                }
            }
            .navigationTitle("Engine Activity")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button { dismiss() } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
            }
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(spacing: Theme.Spacing.tight) {
            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(engineManager.ticker ?? "ANALYSIS")
                        .font(Theme.engravedSerif(size: 22, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                    Text(engineManager.status ?? "---")
                        .font(Theme.officialStampFont(size: 10))
                        .foregroundStyle(statusColor)
                }
                Spacer()
                if let st = engineManager.scanType {
                    Text(st.uppercased())
                        .font(Theme.officialStampFont(size: 8))
                        .tracking(1.2)
                        .foregroundStyle(Theme.inkTertiary)
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .background(Theme.canvasDeep)
                        .clipShape(Capsule())
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
        .padding(.top, Theme.Spacing.standard)
    }

    // MARK: - Progress

    private var progressSection: some View {
        VStack(spacing: Theme.Spacing.tight) {
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Theme.inkTertiary.opacity(0.15))
                        .frame(height: 6)
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Theme.securityGold)
                        .frame(width: geo.size.width * min(engineManager.progressPct / 100.0, 1.0), height: 6)
                        .animation(.linear(duration: 0.3), value: engineManager.progressPct)
                }
            }
            .frame(height: 6)
            HStack {
                if let stage = engineManager.stage {
                    Text(stage)
                        .font(.caption).foregroundStyle(Theme.inkSecondary)
                }
                Spacer()
                Text("\(Int(engineManager.progressPct))%")
                    .font(Theme.serialNumberFont(size: 14))
                    .foregroundStyle(Theme.securityGold)
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }

    // MARK: - Checkpoints

    private var checkpointsSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            Text("LIVE ACTIVITY")
                .font(Theme.officialStampFont(size: 10))
                .foregroundStyle(Theme.inkTertiary)
                .padding(.horizontal, Theme.screenPadding)

            ForEach(engineManager.checkpoints.reversed().prefix(12)) { event in
                CheckpointRow(event: event)
            }
        }
    }

    private var emptyCheckpointsPlaceholder: some View {
        VStack(spacing: Theme.Spacing.standard) {
            ProgressView()
                .tint(Theme.securityGold)
            Text("Analysis starting…")
                .font(.caption).foregroundStyle(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Spacing.large)
    }

    // MARK: - Cancel

    private var cancelButton: some View {
        Button {
    HapticManager.selection()
            HapticManager.warning()
            engineManager.cancelActiveJob()
        } label: {
            HStack(spacing: Theme.Spacing.tight) {
                Image(systemName: "stop.fill")
                Text("STOP ANALYSIS")
                    .font(Theme.officialStampFont(size: 12))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, Theme.Spacing.standard)
            .background(Theme.signalRuby.opacity(0.12))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(Theme.signalRuby.opacity(0.4), lineWidth: 0.5)
            )
            .cornerRadius(Theme.CornerRadius.medium)
        }
        .buttonStyle(EKPressStyle())
        .padding(.horizontal, Theme.screenPadding)
        .padding(.bottom, Theme.Spacing.screen)
    }

    private var statusColor: Color {
        switch engineManager.status {
        case "SUCCEEDED": Theme.signalEmerald
        case "FAILED", "TIMEOUT", "CANCELLED": Theme.signalRuby
        default: Theme.securityGold
        }
    }
}

// MARK: - Checkpoint Row

struct CheckpointRow: View {
    let event: CheckpointEvent

    private var stateIcon: String {
        switch event.state {
        case "ok": "checkmark.circle.fill"
        case "error": "xmark.circle.fill"
        default: "circle.dotted"
        }
    }

    private var stateColor: Color {
        switch event.state {
        case "ok": Theme.signalEmerald
        case "error": Theme.signalRuby
        default: Theme.securityGold
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
            Image(systemName: stateIcon)
                .font(.caption)
                .foregroundStyle(stateColor)
                .padding(.top, Theme.Spacing.xSmall)

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(event.message)
                    .font(.caption)
                    .foregroundStyle(Theme.inkPrimary)
                    .fixedSize(horizontal: false, vertical: true)
                HStack(spacing: Theme.Spacing.xSmall) {
                    Text(event.agent)
                        .font(.caption2).foregroundStyle(Theme.securityGold)
                    Text("·")
                        .foregroundStyle(Theme.inkTertiary)
                    Text(event.ts)
                        .font(.caption2).foregroundStyle(Theme.inkTertiary)
                }
            }
            Spacer()
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.vertical, Theme.Spacing.xSmall)
    }
}
