import SwiftUI

struct UpdatesTabView: View {
    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.card) {
                Text("CORPORATE UPDATES")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, Theme.Spacing.small)
                SPEmptyStateView(message: "Earnings calendar & corporate actions available via EarningsDashboard")
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
    }
}
