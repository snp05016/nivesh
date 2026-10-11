import SwiftUI

// MARK: - Mutual Fund Discovery

struct MutualFundDiscoveryView: View {
    @StateObject private var vm = MutualFundViewModel()
    @State private var showFilters = false

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                MutualFundDiscoveryHeader(fundCount: vm.allFunds.count)

                GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                MutualFundSearchBar(query: $vm.searchQuery, showFilters: $showFilters)
                    .padding(.horizontal, Theme.screenPadding)

                MutualFundCategorySelector(selectedCategory: $vm.selectedCategory, categories: vm.availableCategories)

                if vm.isLoading && vm.allFunds.isEmpty {
                    ProgressView()
                        .tint(Theme.securityGold)
                        .frame(maxWidth: .infinity, minHeight: 160)
                } else if let error = vm.errorMessage, vm.allFunds.isEmpty {
                    MutualFundErrorState(message: error) { Task { await vm.fetchFunds() } }
                        .padding(.horizontal, Theme.screenPadding)
                } else {
                    MutualFundListSection(funds: vm.filteredFunds)
                }
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Mutual Funds")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.fetchFunds() }
        .refreshable { await vm.fetchFunds() }
        .sheet(isPresented: $showFilters) {
            MutualFundFilterSheet(vm: vm)
                .presentationDetents([.medium])
                .presentationDragIndicator(.visible)
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

            Text("Browse, compare, and track mutual fund schemes across every category.")
                .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                .foregroundColor(Theme.inkSecondary)

            HStack(spacing: Theme.Spacing.standard) {
                MutualFundStatBox(title: "Schemes Tracked", value: "\(fundCount)")
                MutualFundStatBox(title: "Powered By", value: "AMFI NAV Feed")
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
    var isPositive: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(title)
                .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkTertiary)

            Text(value)
                .font(Theme.serialNumberFont(size: 18, relativeTo: .headline))
                .foregroundColor(isPositive ? Theme.bullGreen : Theme.inkPrimary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Search Bar

struct MutualFundSearchBar: View {
    @Binding var query: String
    @Binding var showFilters: Bool

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            HStack(spacing: Theme.Spacing.small) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(Theme.inkSecondary)
                TextField("Search fund name or AMC...", text: $query)
                    .foregroundStyle(Theme.inkPrimary)
                    .tint(Theme.securityGold)
                    .font(Theme.serialNumberFont(size: 14))
                    .disableAutocorrection(true)
            }
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.medium)
            .banknoteCard()

            Button {
                HapticManager.selection()
                showFilters = true
            } label: {
                Image(systemName: "slider.horizontal.3")
                    .font(Theme.serialNumberFont(size: 16, relativeTo: .body))
                    .foregroundColor(Theme.securityGold)
                    .padding(Theme.Spacing.medium)
                    .banknoteCard()
            }
            .buttonStyle(EKPressStyle())
            .accessibilityLabel("Filters")
        }
    }
}

// MARK: - Category Selector

struct MutualFundCategorySelector: View {
    @Binding var selectedCategory: String?
    let categories: [String]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Theme.Spacing.standard) {
                MutualFundCategoryChip(label: "All", isSelected: selectedCategory == nil) {
                    selectedCategory = nil
                }
                ForEach(categories, id: \.self) { category in
                    MutualFundCategoryChip(label: category, isSelected: selectedCategory == category) {
                        selectedCategory = category
                    }
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}

private struct MutualFundCategoryChip: View {
    let label: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button {
            HapticManager.selection()
            action()
        } label: {
            Text(label)
                .font(Theme.officialStampFont(size: 14, relativeTo: .subheadline))
                .tracking(1.5)
                .padding(.horizontal, Theme.Spacing.card)
                .padding(.vertical, Theme.Spacing.medium)
                .background(isSelected ? Theme.inkPrimary : Color.clear)
                .foregroundColor(isSelected ? Theme.canvas : Theme.inkSecondary)
                .cornerRadius(Theme.CornerRadius.small)
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .stroke(Theme.borderFine, lineWidth: isSelected ? 0 : 1)
                )
        }
        .buttonStyle(EKPressStyle())
    }
}

// MARK: - List Section

struct MutualFundListSection: View {
    let funds: [MutualFundDTO]

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            if funds.isEmpty {
                MutualFundEmptyState()
            } else {
                ForEach(funds) { fund in
                    MutualFundRowCard(fund: fund)
                }
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct MutualFundEmptyState: View {
    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text("No Funds Match Your Filters")
                .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)
            Text("Try widening your category, AUM, or returns filters.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)
                .multilineTextAlignment(.center)
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
            VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                MutualFundRowHeader(fund: fund)
                if fund.isSample == true {
                    MutualFundSampleDataStamp()
                }
                GuillocheDivider()
                MutualFundRowStats(fund: fund)
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
    }
}

private struct MutualFundRowHeader: View {
    let fund: MutualFundDTO

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(Theme.canvasShadow)
                .frame(width: 44, height: 44)
                .overlay(
                    Text(String(fund.fundName.prefix(1)))
                        .font(Theme.officialStampFont(size: 16, relativeTo: .subheadline))
                        .foregroundColor(Theme.inkPrimary)
                )

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(fund.fundName)
                    .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
                    .lineLimit(1)
                Text("\(fund.category) · \(fund.amc)")
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.2)
                    .foregroundColor(Theme.inkSecondary)
                    .lineLimit(1)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text(fund.navDisplay)
                    .font(Theme.serialNumberFont(size: 15, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
                Text("NAV")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .foregroundColor(Theme.inkTertiary)
            }
        }
    }
}

private struct MutualFundRowStats: View {
    let fund: MutualFundDTO

    var body: some View {
        HStack(spacing: Theme.Spacing.large) {
            MutualFundStatColumn(label: "1Y Return", value: fund.returns1y.map(IndianFormatter.delta), valueColor: colorFor(fund.returns1y))
            MutualFundStatColumn(label: "3Y CAGR", value: fund.returns3y.map(IndianFormatter.delta), valueColor: colorFor(fund.returns3y))
            MutualFundStatColumn(label: "AUM", value: fund.aumCr != nil ? fund.aumDisplay : nil)

            Spacer()

            if let riskLevel = fund.parsedRiskLevel {
                MutualFundRiskBadge(riskLevel: riskLevel)
            }
        }
    }

    private func colorFor(_ value: Double?) -> Color {
        guard let value else { return Theme.inkPrimary }
        return value >= 0 ? Theme.bullGreen : Theme.bearRed
    }
}

private struct MutualFundStatColumn: View {
    let label: String
    let value: String?
    var valueColor: Color = Theme.inkPrimary

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundColor(Theme.inkTertiary)
            Text(value ?? "—")
                .font(Theme.serialNumberFont(size: 13, relativeTo: .subheadline))
                .foregroundColor(value == nil ? Theme.inkTertiary : valueColor)
        }
    }
}

/// Compact risk-o-meter tag shown on discovery rows — full gauge lives on the detail screen.
struct MutualFundRiskBadge: View {
    let riskLevel: MutualFundRiskLevel

    private var color: Color {
        switch riskLevel {
        case .low, .lowToModerate: return Theme.bullGreen
        case .moderate, .moderatelyHigh: return Theme.holdAmber
        case .high, .veryHigh: return Theme.bearRed
        }
    }

    var body: some View {
        Text(riskLevel.rawValue)
            .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
            .tracking(1.0)
            .padding(.horizontal, Theme.Spacing.medium)
            .padding(.vertical, Theme.Spacing.small)
            .foregroundColor(color)
            .background(color.opacity(0.12))
            .cornerRadius(Theme.CornerRadius.badge)
    }
}

// MARK: - Filter Sheet

struct MutualFundFilterSheet: View {
    @ObservedObject var vm: MutualFundViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                    MutualFundSortPicker(sortOption: $vm.sortOption)
                    MutualFundRiskFilter(selectedRiskLevel: $vm.selectedRiskLevel)
                    MutualFundRangeFilter(
                        title: "Minimum AUM",
                        value: $vm.minAumCr,
                        range: 0...50_000,
                        display: { IndianFormatter.formatLakhsCrores($0 * 1_00_00_000) }
                    )
                    MutualFundRangeFilter(
                        title: "Minimum 1Y Return",
                        value: $vm.minReturns1y,
                        range: -20...50,
                        display: { $0 <= -20 ? "Any" : IndianFormatter.delta($0) }
                    )
                }
                .padding(Theme.screenPadding)
            }
            .background(Theme.canvas.ignoresSafeArea())
            .navigationTitle("Filter Funds")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Reset") {
                        HapticManager.selection()
                        vm.clearFilters()
                    }
                    .foregroundStyle(Theme.inkSecondary)
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        HapticManager.selection()
                        dismiss()
                    }
                    .foregroundStyle(Theme.securityGold)
                }
            }
        }
    }
}

private struct MutualFundSortPicker: View {
    @Binding var sortOption: MutualFundSortOption

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("SORT BY")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: Theme.Spacing.standard) {
                    ForEach(MutualFundSortOption.allCases) { option in
                        MutualFundCategoryChipInline(label: option.rawValue, isSelected: sortOption == option) {
                            sortOption = option
                        }
                    }
                }
            }
        }
    }
}

private struct MutualFundRiskFilter: View {
    @Binding var selectedRiskLevel: MutualFundRiskLevel?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("RISK LEVEL")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: Theme.Spacing.standard) {
                    MutualFundCategoryChipInline(label: "All", isSelected: selectedRiskLevel == nil) {
                        selectedRiskLevel = nil
                    }
                    ForEach(MutualFundRiskLevel.allCases, id: \.self) { level in
                        MutualFundCategoryChipInline(label: level.rawValue, isSelected: selectedRiskLevel == level) {
                            selectedRiskLevel = level
                        }
                    }
                }
            }
        }
    }
}

private struct MutualFundRangeFilter: View {
    let title: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    let display: (Double) -> String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack {
                Text(title.uppercased())
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.5)
                    .foregroundColor(Theme.inkSecondary)
                Spacer()
                Text(display(value))
                    .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                    .foregroundColor(Theme.securityGold)
            }
            Slider(value: $value, in: range)
                .tint(Theme.securityGold)
        }
    }
}

/// Shared filter-sheet chip (distinct from the screen-level category chip above).
private struct MutualFundCategoryChipInline: View {
    let label: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button {
            HapticManager.selection()
            action()
        } label: {
            Text(label)
                .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                .tracking(1.0)
                .padding(.horizontal, Theme.Spacing.standard)
                .padding(.vertical, Theme.Spacing.small)
                .background(isSelected ? Theme.inkPrimary : Color.clear)
                .foregroundColor(isSelected ? Theme.canvas : Theme.inkSecondary)
                .cornerRadius(Theme.CornerRadius.badge)
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.badge)
                        .stroke(Theme.borderFine, lineWidth: isSelected ? 0 : 1)
                )
        }
        .buttonStyle(EKPressStyle())
    }
}
