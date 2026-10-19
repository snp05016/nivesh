import SwiftUI
import Combine
import UserNotifications
import EventKit

// MARK: - Main Earnings Dashboard

struct EarningsDashboardView: View {
    @StateObject private var vm = EarningsDashboardViewModel()
    @EnvironmentObject var authManager: AuthManager
    @State private var selectedTab: Int = 0  // 0=Progress, 1=Calendar, 2=Feed, 3=Screeners, 4=Variance, 5=PostResult

    let tabs = ["Progress", "Calendar", "Feed", "Screeners", "Variance", "Post-Result"]

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            VStack(spacing: Theme.Spacing.none) {
                headerBar
                tabBar
                tabContent
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .frame(maxHeight: .infinity, alignment: .top)
        }
        .task { vm.load() }
        .onChange(of: vm.selectedSort) { _, _ in vm.load() }
    }

    // MARK: Header

    private var headerBar: some View {
        HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("EARNINGS DASHBOARD")
                    .font(.caption.weight(.bold).monospaced())
                    .tracking(2)
                    .foregroundStyle(Theme.securityGold)
            }
            Spacer()
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.top, Theme.Spacing.standard)
        .padding(.bottom, Theme.Spacing.medium)
        .background(Theme.canvasDeep)
    }

    // MARK: Tab Bar

    private var tabBar: some View {
        ScrollView(.horizontal) {
            HStack(spacing: Theme.Spacing.small) {
                ForEach(Array(tabs.enumerated()), id: \.offset) { idx, name in
                    Button(action: { HapticManager.selection(); selectedTab = idx }) {
                        Text(name)
                            .font(.caption.weight(selectedTab == idx ? .bold : .regular))
                            .foregroundStyle(selectedTab == idx ? Theme.securityGold : Theme.inkTertiary)
                            .padding(.horizontal, Theme.Spacing.standard)
                            .padding(.vertical, Theme.Spacing.medium)
                            .background(
                                selectedTab == idx
                                    ? Theme.securityGold.opacity(0.10)
                                    : Color.clear
                            )
                            .cornerRadius(Theme.CornerRadius.tight)
                    }
                }
            }
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.tight)
        }
        .scrollIndicators(.hidden)
        .background(Theme.canvasDeep)
        .overlay(Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5), alignment: .bottom)
    }

    // MARK: Tab Content

    @ViewBuilder
    private var tabContent: some View {
        switch selectedTab {
        case 0: EarningsProgressView(vm: vm)
        case 1: EarningsCalendarView(vm: vm)
        case 2: EarningsFeedView(vm: vm)
        case 3: ScreenerView(vm: vm)
        case 4: VarianceTrackerView(vm: vm)
        case 5: PostResultMonitorView(vm: vm)
        default: EmptyView()
        }
    }
}

// MARK: - SwiftUI Previews (Section 15)

#Preview("Earnings Dashboard") {
    EarningsDashboardView()
        .environmentObject(AuthManager())
}
