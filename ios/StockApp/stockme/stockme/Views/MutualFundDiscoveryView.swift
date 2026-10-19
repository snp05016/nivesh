import SwiftUI

// MARK: - Mutual Fund Discovery

struct MutualFundDiscoveryView: View {
    @StateObject private var vm = MutualFundViewModel()

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                MutualFundDiscoveryHeader(fundCount: vm.totalCount ?? vm.funds.count)

                GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                MutualFundSearchBar(
                    query: Binding(get: { vm.query.search }, set: { vm.setSearch($0) })
                )
                .padding(.horizontal, Theme.screenPadding)

                MutualFundFilterBar(vm: vm)

                MutualFundDiscoveryContent(vm: vm)
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Mutual Funds")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await vm.loadFilters()
            await vm.reload()
        }
        .refreshable {
            await vm.loadFilters()
            await vm.reload()
        }
    }
}

// MARK: - Content states

private struct MutualFundDiscoveryContent: View {
    @ObservedObject var vm: MutualFundViewModel

    var body: some View {
        Group {
            if vm.isLoading && vm.funds.isEmpty {
                SPSkeletonBlock(rows: 6)
                    .padding(.horizontal, Theme.screenPadding)
            } else if let message = vm.errorMessage, vm.funds.isEmpty {
                MutualFundErrorState(message: message) { Task { await vm.reload() } }
                    .padding(.horizontal, Theme.screenPadding)
            } else if vm.funds.isEmpty {
                MutualFundEmptyState { vm.clearFilters() }
                    .padding(.horizontal, Theme.screenPadding)
            } else {
                MutualFundListSection(funds: vm.funds)
                MutualFundListFooter(
                    canLoadMore: vm.canLoadMore,
                    isLoadingMore: vm.isLoadingMore,
                    loadMoreFailed: vm.loadMoreFailed
                ) { Task { await vm.loadMore() } }
                    .padding(.horizontal, Theme.screenPadding)
            }
        }
    }
}

// MARK: - Header

struct MutualFundDiscoveryHeader: View {
    let fundCount: Int

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("Discover Funds")
                .font(Theme.engravedSerif(size: 28, weight: .bold, relativeTo: .title))
                .foregroundColor(Theme.inkPrimary)

            Text("Browse mutual fund schemes by category and fund house, with the official NAV and date.")
                .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                .foregroundColor(Theme.inkSecondary)

            HStack(spacing: Theme.Spacing.standard) {
                MutualFundStatBox(title: "Matching Schemes", value: "\(fundCount)")
                MutualFundStatBox(title: "NAV Source", value: "AMFI")
            }
            .padding(.top, Theme.Spacing.medium)
        }
        .padding(.horizontal, Theme.screenPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct MutualFundStatBox: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(title)
                .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkTertiary)

            Text(value)
                .font(Theme.serialNumberFont(size: 18, relativeTo: .headline))
                .foregroundColor(Theme.inkPrimary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Search Bar

struct MutualFundSearchBar: View {
    @Binding var query: String

    var body: some View {
        HStack(spacing: Theme.Spacing.small) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(Theme.inkSecondary)
            TextField("Search fund name, scheme code or ISIN...", text: $query)
                .foregroundStyle(Theme.inkPrimary)
                .tint(Theme.securityGold)
                .font(Theme.serialNumberFont(size: 14))
                .disableAutocorrection(true)
        }
        .padding(.horizontal, Theme.Spacing.standard)
        .padding(.vertical, Theme.Spacing.medium)
        .banknoteCard()
    }
}

// MARK: - Filter Bar

struct MutualFundFilterBar: View {
    @ObservedObject var vm: MutualFundViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Picker("Plan", selection: Binding(get: { vm.query.plan }, set: { vm.setPlan($0) })) {
                ForEach(MutualFundPlanFilter.allCases) { Text($0.label).tag($0) }
            }
            .pickerStyle(.segmented)

            Picker("Option", selection: Binding(get: { vm.query.option }, set: { vm.setOption($0) })) {
                ForEach(MutualFundOptionFilter.allCases) { Text($0.label).tag($0) }
            }
            .pickerStyle(.segmented)

            HStack(spacing: Theme.Spacing.standard) {
                MutualFundCategoryMenu(vm: vm)
                if let amcs = vm.filters?.amcs, !amcs.isEmpty {
                    MutualFundAMCMenu(vm: vm, amcs: amcs)
                }
                Spacer()
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

private struct MutualFundCategoryMenu: View {
    @ObservedObject var vm: MutualFundViewModel

    private var title: String {
        if let sub = vm.query.subCategory { return sub }
        return vm.query.category ?? "Category"
    }

    var body: some View {
        Menu {
            Button("All categories") { vm.setCategory(nil) }
            ForEach(vm.availableCategories, id: \.self) { category in
                let subs = vm.subCategories(of: category)
                if subs.isEmpty {
                    Button(category) { vm.setCategory(category) }
                } else {
                    Menu(category) {
                        Button("All \(category)") { vm.setCategory(category) }
                        ForEach(subs, id: \.self) { sub in
                            Button(sub) { vm.setCategory(category, subCategory: sub) }
                        }
                    }
                }
            }
        } label: {
            MutualFundMenuChip(label: title, isActive: vm.query.category != nil)
        }
        .accessibilityLabel("Category")
    }
}

private struct MutualFundAMCMenu: View {
    @ObservedObject var vm: MutualFundViewModel
    let amcs: [String]

    var body: some View {
        Menu {
            Button("All fund houses") { vm.setAMC(nil) }
            ForEach(amcs, id: \.self) { amc in
                Button(amc) { vm.setAMC(amc) }
            }
        } label: {
            MutualFundMenuChip(label: vm.query.amc ?? "Fund house", isActive: vm.query.amc != nil)
        }
        .accessibilityLabel("Fund house")
    }
}

private struct MutualFundMenuChip: View {
    let label: String
    let isActive: Bool

    var body: some View {
        HStack(spacing: Theme.Spacing.small) {
            Text(label)
                .lineLimit(1)
            Image(systemName: "chevron.down")
                .font(.caption2)
        }
        .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
        .tracking(1.0)
        .padding(.horizontal, Theme.Spacing.standard)
        .padding(.vertical, Theme.Spacing.medium)
        .background(isActive ? Theme.inkPrimary : Color.clear)
        .foregroundColor(isActive ? Theme.canvas : Theme.inkSecondary)
        .cornerRadius(Theme.CornerRadius.small)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .stroke(Theme.borderFine, lineWidth: isActive ? 0 : 1)
        )
    }
}

// MARK: - List Section

struct MutualFundListSection: View {
    let funds: [MutualFundDTO]

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            ForEach(funds) { fund in
                MutualFundRowCard(fund: fund)
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct MutualFundListFooter: View {
    let canLoadMore: Bool
    let isLoadingMore: Bool
    let loadMoreFailed: Bool
    let loadMore: () -> Void

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            if isLoadingMore {
                ProgressView().tint(Theme.securityGold)
            } else if loadMoreFailed {
                Button {
                    HapticManager.selection()
                    loadMore()
                } label: {
                    Text("Couldn't load more. Tap to retry.")
                        .font(Theme.labelStyle)
                        .foregroundColor(Theme.bearRed)
                }
                .buttonStyle(EKPressStyle())
            } else if canLoadMore {
                Button {
                    HapticManager.selection()
                    loadMore()
                } label: {
                    Text("Show more funds")
                        .font(Theme.labelStyle)
                        .foregroundColor(Theme.securityGold)
                }
                .buttonStyle(EKPressStyle())
            }

            Text("NAVs are published by AMFI (amfiindia.com) after each business day. For information only, not a recommendation.")
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption))
                .foregroundColor(Theme.inkTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
    }
}

struct MutualFundEmptyState: View {
    let clearFilters: () -> Void

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            Text("No funds match these filters.")
                .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)
            Button {
                HapticManager.selection()
                clearFilters()
            } label: {
                Text("Clear filters")
                    .font(Theme.labelStyle)
                    .foregroundColor(Theme.securityGold)
            }
            .buttonStyle(EKPressStyle())
        }
        .frame(maxWidth: .infinity, minHeight: 160)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct MutualFundErrorState: View {
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

// MARK: - Fund Row Card

struct MutualFundRowCard: View {
    let fund: MutualFundDTO

    var body: some View {
        NavigationLink {
            MutualFundDetailView(fund: fund)
        } label: {
            MutualFundRow(fund: fund)
                .padding(Theme.Spacing.card)
                .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
    }
}

/// Name, "AMC · sub-category" and the official NAV with its date. No returns, AUM or ranking.
struct MutualFundRow: View {
    let fund: MutualFundDTO

    private var subtitle: String {
        let detail = fund.subCategory ?? fund.category
        return "\(fund.amc) · \(detail)"
    }

    private var navLine: String {
        guard fund.nav != nil else { return "NAV unavailable" }
        guard let date = fund.navDate else { return "NAV \(fund.navPreciseDisplay)" }
        return "NAV \(fund.navPreciseDisplay) · \(MutualFundDateText.short(date))"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(fund.fundName)
                .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .body))
                .foregroundColor(Theme.inkPrimary)
                .lineLimit(2)
            Text(subtitle)
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.0)
                .foregroundColor(Theme.inkSecondary)
                .lineLimit(1)
            Text(navLine)
                .font(Theme.serialNumberFont(size: 13, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)
            if fund.isSample == true {
                MutualFundSampleDataStamp()
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
