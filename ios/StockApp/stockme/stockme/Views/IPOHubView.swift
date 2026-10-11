import SwiftUI

// MARK: - IPO Hub

struct IPOHubView: View {
    @StateObject private var vm = IPOListViewModel()
    @State private var selectedTab: IPOStatus = .open

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                IPOHubHeader(showsSampleStamp: vm.allIPOs.contains { $0.isSample == true })

                GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                IPOTabSelector(selectedTab: $selectedTab, counts: tabCounts)

                IPOListSection(status: selectedTab, vm: vm)
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("IPO Hub")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                NavigationLink {
                    IPOCalendarView(vm: vm)
                } label: {
                    Image(systemName: "calendar")
                        .foregroundStyle(Theme.securityGold)
                }
            }
        }
        .onAppear { vm.startLiveUpdates() }
        .onDisappear { vm.stopLiveUpdates() }
        .refreshable { vm.fetchIPOs() }
    }

    private var tabCounts: [IPOStatus: Int] {
        Dictionary(grouping: vm.allIPOs.filter { $0.status != nil }, by: { $0.status! }).mapValues(\.count)
    }
}

// MARK: - Header

struct IPOHubHeader: View {
    var showsSampleStamp = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack {
                Text("IPO Central")
                    .font(Theme.engravedSerif(size: 28, weight: .bold, relativeTo: .title))
                    .foregroundColor(Theme.inkPrimary)
                Spacer()
                if showsSampleStamp {
                    IPOSampleDataStamp()
                }
            }

            Text("Track, analyze, and apply for the latest Initial Public Offerings.")
                .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                .foregroundColor(Theme.inkSecondary)
        }
        .padding(.horizontal, Theme.screenPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Tab Selector

struct IPOTabSelector: View {
    @Binding var selectedTab: IPOStatus
    let counts: [IPOStatus: Int]

    private let tabs: [IPOStatus] = [.open, .upcoming, .closed]

    var body: some View {
        HStack(spacing: 0) {
            ForEach(tabs, id: \.self) { tab in
                IPOTabButton(tab: tab, isSelected: selectedTab == tab, count: counts[tab] ?? 0) {
                    selectedTab = tab
                }
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

private struct IPOTabButton: View {
    let tab: IPOStatus
    let isSelected: Bool
    let count: Int
    let action: () -> Void

    var body: some View {
        Button {
            HapticManager.selection()
            action()
        } label: {
            VStack(spacing: Theme.Spacing.medium) {
                HStack(spacing: Theme.Spacing.xSmall) {
                    Text(tab.displayLabel)
                        .font(Theme.officialStampFont(size: 14, relativeTo: .subheadline))
                        .tracking(1.5)
                    if count > 0 {
                        Text("\(count)")
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                    }
                }
                .foregroundColor(isSelected ? Theme.inkPrimary : Theme.inkSecondary)

                Rectangle()
                    .fill(isSelected ? Theme.inkPrimary : Color.clear)
                    .frame(height: 2)
            }
        }
        .buttonStyle(EKPressStyle())
        .frame(maxWidth: .infinity)
    }
}

// MARK: - List Section

struct IPOListSection: View {
    let status: IPOStatus
    @ObservedObject var vm: IPOListViewModel

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            if vm.isLoading && vm.allIPOs.isEmpty {
                ProgressView()
                    .tint(Theme.securityGold)
                    .frame(maxWidth: .infinity, minHeight: 160)
            } else if let error = vm.errorMessage {
                IPOErrorState(message: error) { vm.fetchIPOs() }
            } else {
                let ipos = vm.ipos(for: status)
                if ipos.isEmpty {
                    IPOEmptyState(status: status)
                } else {
                    ForEach(ipos) { ipo in
                        NavigationLink {
                            IPODetailView(seed: ipo)
                        } label: {
                            IPOCard(ipo: ipo)
                        }
                        .buttonStyle(EKPressStyle())
                    }
                }
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct IPOErrorState: View {
    let message: String
    let retry: () -> Void

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            Text(message)
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundColor(Theme.inkSecondary)
                .multilineTextAlignment(.center)
            Button {
                HapticManager.selection()
                retry()
            } label: {
                Text("Retry")
                    .font(Theme.labelStyle)
                    .foregroundColor(Theme.securityGold)
            }
            .buttonStyle(EKPressStyle())
        }
        .frame(maxWidth: .infinity, minHeight: 160)
    }
}

struct IPOEmptyState: View {
    let status: IPOStatus

    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text("No \(status.displayLabel) IPOs")
                .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)
            Text("Check back soon — new listings are added as they're announced.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 160)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - IPO Card

struct IPOCard: View {
    let ipo: IPOListing

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            IPOCardHeader(ipo: ipo)
            GuillocheDivider()
            IPOCardStats(ipo: ipo)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct IPOCardHeader: View {
    let ipo: IPOListing

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(Theme.canvasShadow)
                .frame(width: 40, height: 40)
                .overlay(
                    Text(String(ipo.companyName.prefix(1)))
                        .font(Theme.officialStampFont(size: 14, relativeTo: .subheadline))
                        .foregroundColor(Theme.inkPrimary)
                )

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(ipo.companyName)
                    .font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .headline))
                    .foregroundColor(Theme.inkPrimary)
                    .lineLimit(1)

                if let symbol = ipo.symbol {
                    Text(symbol)
                        .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                        .tracking(1.5)
                        .foregroundColor(Theme.inkSecondary)
                }
            }

            Spacer()

            IPOStatusBadge(ipo: ipo)
        }
    }
}

private struct IPOStatusBadge: View {
    let ipo: IPOListing

    var body: some View {
        switch ipo.status {
        case .open:
            Text("Apply Now")
                .font(Theme.labelStyle)
                .padding(.horizontal, Theme.Spacing.medium)
                .padding(.vertical, Theme.Spacing.small)
                .background(Theme.bullGreen)
                .foregroundColor(Theme.canvas)
                .cornerRadius(Theme.CornerRadius.small)
        case .upcoming:
            Text(ipo.openDate ?? "—")
                .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                .foregroundColor(Theme.inkSecondary)
        case .closed, .listed:
            Text(ipo.status?.displayLabel ?? "—")
                .font(Theme.labelStyle)
                .foregroundColor(Theme.inkTertiary)
        case .none:
            EmptyView()
        }
    }
}

private struct IPOCardStats: View {
    let ipo: IPOListing

    var body: some View {
        HStack(spacing: Theme.Spacing.large) {
            IPOStatColumn(label: "Price Band", value: ipo.priceBandDisplay, alignment: .leading)
            IPOStatColumn(label: "Lot Size", value: ipo.lotSizeDisplay, alignment: .leading)

            Spacer()

            if let gmp = ipo.gmp {
                IPOStatColumn(
                    label: "GMP",
                    value: IndianFormatter.price(gmp),
                    alignment: .trailing,
                    valueColor: gmp >= 0 ? Theme.bullGreen : Theme.bearRed
                )
            } else if ipo.status == .open, let closeDateStr = ipo.closeDate,
                      let closeDate = ISO8601DateFormatter().date(from: closeDateStr) ?? DateFormatter.ipoDate.date(from: closeDateStr) {
                IPOStatColumn(
                    label: "Closes In",
                    value: daysRemaining(until: closeDate),
                    alignment: .trailing,
                    valueColor: Theme.bearRed
                )
            }
        }
    }

    private func daysRemaining(until date: Date) -> String {
        let days = Calendar.current.dateComponents([.day], from: Date(), to: date).day ?? 0
        return days <= 0 ? "Today" : "\(days) Day\(days == 1 ? "" : "s")"
    }
}

private struct IPOStatColumn: View {
    let label: String
    let value: String
    let alignment: HorizontalAlignment
    var valueColor: Color = Theme.inkPrimary

    var body: some View {
        VStack(alignment: alignment, spacing: Theme.Spacing.small) {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .tracking(1.5)
                .foregroundColor(Theme.inkTertiary)

            Text(value)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                .foregroundColor(valueColor)
        }
    }
}

/// Marks the backend's fictional seed IPOs so they are never mistaken for live listings.
struct IPOSampleDataStamp: View {
    var body: some View {
        Text("SAMPLE DATA")
            .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
            .tracking(1.5)
            .foregroundColor(Theme.holdAmber)
            .padding(.horizontal, Theme.Spacing.small)
            .padding(.vertical, Theme.Spacing.xSmall)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .stroke(Theme.holdAmber, lineWidth: 1)
            )
    }
}

extension DateFormatter {
    static let ipoDate: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.locale = Locale(identifier: "en_US_POSIX")
        return f
    }()
}
