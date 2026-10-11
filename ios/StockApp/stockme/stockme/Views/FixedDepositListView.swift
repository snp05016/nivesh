import SwiftUI

// MARK: - Fixed Deposit Discovery & Comparison
//
// MOCK DATA - simulated for demo purposes, not a real integration. Every
// issuer shown is a fictional demo NBFC FD issuer persona backed by a mock
// endpoint (see NetworkManager+FixedDeposits.swift) — no real underwriting
// or payment processing happens anywhere in this feature.

struct FixedDepositListView: View {
    @StateObject private var vm = FixedDepositViewModel()
    @State private var showFilters = false
    @State private var showCalculator = false

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                FixedDepositHeader(schemeCount: vm.filteredSchemes.count)

                GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                FDSortAndFilterBar(sortOrder: $vm.sortOrder, showFilters: $showFilters)

                if vm.isLoading && vm.allSchemes.isEmpty {
                    ProgressView()
                        .tint(Theme.securityGold)
                        .frame(maxWidth: .infinity, minHeight: 160)
                } else if let error = vm.errorMessage, vm.allSchemes.isEmpty {
                    FDErrorState(message: error) { Task { await vm.fetchSchemes() } }
                        .padding(.horizontal, Theme.screenPadding)
                } else {
                    FDSchemeListSection(schemes: vm.filteredSchemes)
                }
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Fixed Deposits")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    HapticManager.selection()
                    showCalculator = true
                } label: {
                    Image(systemName: "function")
                        .foregroundStyle(Theme.securityGold)
                }
                .accessibilityLabel("FD calculator")
            }
        }
        .task { await vm.fetchSchemes() }
        .refreshable { await vm.fetchSchemes() }
        .sheet(isPresented: $showFilters) {
            FDFilterSheet(vm: vm)
                .presentationDetents([.medium])
                .presentationDragIndicator(.visible)
        }
        .sheet(isPresented: $showCalculator) {
            FixedDepositCalculatorView()
        }
    }
}

// MARK: - Header

struct FixedDepositHeader: View {
    let schemeCount: Int

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("Fixed Deposits")
                .font(Theme.engravedSerif(size: 28, weight: .bold, relativeTo: .title))
                .foregroundColor(Theme.inkPrimary)

            Text("Compare NBFC fixed deposit schemes by rate and tenure, then book in minutes.")
                .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                .foregroundColor(Theme.inkSecondary)

            Text("DEMO SCHEMES · NO REAL PAYMENT COLLECTED")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .padding(.horizontal, Theme.Spacing.medium)
                .padding(.vertical, Theme.Spacing.small)
                .foregroundColor(Theme.holdAmber)
                .background(Theme.holdAmber.opacity(0.12))
                .cornerRadius(Theme.CornerRadius.badge)

            Text("\(schemeCount) schemes available")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.0)
                .foregroundColor(Theme.inkTertiary)
        }
        .padding(.horizontal, Theme.screenPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Sort & Filter Bar

struct FDSortAndFilterBar: View {
    @Binding var sortOrder: FixedDepositViewModel.SortOrder
    @Binding var showFilters: Bool

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: Theme.Spacing.standard) {
                    ForEach(FixedDepositViewModel.SortOrder.allCases) { order in
                        FDFilterChip(label: order.rawValue, isSelected: sortOrder == order) {
                            sortOrder = order
                        }
                    }
                }
            }

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
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct FDFilterChip: View {
    let label: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button {
            HapticManager.selection()
            action()
        } label: {
            Text(label)
                .font(Theme.officialStampFont(size: 13, relativeTo: .subheadline))
                .tracking(1.2)
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

// MARK: - Scheme List

struct FDSchemeListSection: View {
    let schemes: [FDSchemeDTO]

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            if schemes.isEmpty {
                FDEmptyState()
            } else {
                ForEach(schemes) { scheme in
                    FDSchemeRowCard(scheme: scheme)
                }
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct FDEmptyState: View {
    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text("No Schemes Match Your Filters")
                .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)
            Text("Try widening your tenure filter.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 160)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct FDErrorState: View {
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

// MARK: - Scheme Row Card

struct FDSchemeRowCard: View {
    let scheme: FDSchemeDTO

    var body: some View {
        NavigationLink {
            FixedDepositBookingView(scheme: scheme)
        } label: {
            VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                FDSchemeRowHeader(scheme: scheme)
                GuillocheDivider()
                FDSchemeRowStats(scheme: scheme)
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
    }
}

private struct FDSchemeRowHeader: View {
    let scheme: FDSchemeDTO

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(Theme.canvasShadow)
                .frame(width: 44, height: 44)
                .overlay(
                    Image(systemName: "banknote.fill")
                        .foregroundColor(Theme.inkPrimary)
                )

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(scheme.issuerName)
                    .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
                    .lineLimit(1)
                Text("Fixed Deposit")
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.2)
                    .foregroundColor(Theme.inkSecondary)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text(scheme.interestRateDisplay)
                    .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                    .foregroundColor(Theme.bullGreen)
                Text("INTEREST")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .foregroundColor(Theme.inkTertiary)
            }
        }
    }
}

private struct FDSchemeRowStats: View {
    let scheme: FDSchemeDTO

    var body: some View {
        HStack(spacing: Theme.Spacing.large) {
            FDStatColumn(label: "Amount", value: scheme.amountRangeDisplay)
            FDStatColumn(label: "Tenure", value: scheme.tenureRangeDisplay)
            FDStatColumn(label: "Senior Citizen", value: scheme.seniorCitizenRateDisplay)
            Spacer()
        }
    }
}

private struct FDStatColumn: View {
    let label: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundColor(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 13, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)
        }
    }
}

// MARK: - Filter Sheet

struct FDFilterSheet: View {
    @ObservedObject var vm: FixedDepositViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                    FDRangeFilter(
                        title: "Minimum Tenure Needed",
                        value: $vm.minTenureMonths,
                        range: 0...120,
                        display: { $0 <= 0 ? "Any" : "\(Int($0)) mo" }
                    )
                    FDRangeFilter(
                        title: "Maximum Tenure",
                        value: $vm.maxTenureMonths,
                        range: 0...120,
                        display: { $0 >= 120 ? "Any" : "\(Int($0)) mo" }
                    )
                }
                .padding(Theme.screenPadding)
            }
            .background(Theme.canvas.ignoresSafeArea())
            .navigationTitle("Filter Schemes")
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

private struct FDRangeFilter: View {
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
