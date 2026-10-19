import SwiftUI

/// Portfolio X-ray (I28): allocation across stocks and funds, fund-house and plan mix, largest holdings
/// and fixed facts. Pushed inside PortfolioScreen's NavigationStack; shown only while money_xray is on.
struct PortfolioXRayView: View {
    @StateObject private var model = PortfolioXRayViewModel()
    @ObservedObject private var flags = FeatureFlags.shared
    @AppStorage("nivesh_hidePortfolioValues") private var hideValues = false

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.card) {
                switch model.state {
                case .loading where model.xray == nil:
                    ProgressView().tint(Theme.securityGold).padding(.top, Theme.Spacing.xLarge)
                case .empty:
                    Text(PortfolioXRayViewModel.emptyMessage)
                        .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                        .foregroundStyle(Theme.inkSecondary)
                        .multilineTextAlignment(.center)
                        .padding(.top, Theme.Spacing.xLarge)
                case .failed(let message) where model.xray == nil:
                    BanknoteErrorCanvas(title: "Couldn't load your X-ray.", detail: message, retryAction: { await model.load() })
                default:
                    if model.state == .offline {
                        HoldingStatusBanner(text: "You're offline. Showing your last loaded values.")
                    }
                    if let xray = model.xray {
                        XRayContent(xray: xray, replay: model.replay, hideValues: hideValues,
                                    showDrag: flags.isOn(.moneyCommissionDrag), showReplay: flags.isOn(.moneyCrisisReplay))
                    } else if model.state == .offline {
                        Text("Connect to the internet to see your X-ray.")
                            .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }
                Spacer(minLength: Theme.Spacing.sectionBreath)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, Theme.Spacing.standard)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Portfolio X-ray")
        .navigationBarTitleDisplayMode(.inline)
        .task { await model.load() }
        .refreshable { await model.load() }
    }
}

private struct XRayContent: View {
    let xray: XRayResponse
    let replay: CrisisReplayResponse?
    let hideValues: Bool
    let showDrag: Bool
    let showReplay: Bool

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            XRayAllocationCard(slices: xray.allocation, hideValues: hideValues)
            if !xray.amcs.isEmpty { XRayAMCCard(amcs: xray.amcs, hideValues: hideValues) }
            if let plans = xray.plans { XRayPlanMixRow(plans: plans) }
            if !xray.topHoldings.isEmpty { XRayTopHoldingsCard(holdings: xray.topHoldings, hideValues: hideValues) }
            if !xray.facts.isEmpty { XRayFactsCard(facts: xray.facts) }
            if showDrag, let drag = xray.commissionDrag, drag.available { CommissionDragCard(drag: drag) }
            if showReplay, let replay { CrisisReplayCard(replay: replay) }
            NavigationLink {
                StressTestScreen()
            } label: {
                MoneyNavLabel(title: "Run a stress test (stocks only)")
            }
            .buttonStyle(EKPressStyle())
            if !xray.unpriced.isEmpty { XRayUnpricedFootnote(unpriced: xray.unpriced) }
            Text("As of \(MoneyReturnCopy.day(String(xray.asOf.prefix(10))) ?? xray.asOf)")
                .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                .foregroundStyle(Theme.inkTertiary)
        }
    }
}

/// Label for a navigation row with a trailing chevron.
private struct MoneyNavLabel: View {
    let title: String

    var body: some View {
        HStack {
            Text(title)
                .font(Theme.engravedSerif(size: 14, weight: .medium, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
            Spacer()
            Image(systemName: "chevron.right")
                .font(.caption2.weight(.semibold))
                .foregroundStyle(Theme.inkTertiary)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}
