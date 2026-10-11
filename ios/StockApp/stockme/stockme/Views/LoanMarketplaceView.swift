import SwiftUI

// MARK: - Loan Marketplace
//
// MOCK DATA - simulated for demo purposes, not a real integration. Every
// lender shown is a fictional demo NBFC persona backed by a mock endpoint
// (see NetworkManager+Finance.swift) — no real credit-bureau pull happens
// anywhere in this feature.

struct LoanMarketplaceView: View {
    @StateObject private var vm = LoanViewModel()
    @State private var showFilters = false

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                LoanMarketplaceHeader(offerCount: vm.allOffers.count)

                GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                LoanTypeSelector(selectedType: $vm.selectedLoanType, showFilters: $showFilters)

                if vm.isLoading && vm.allOffers.isEmpty {
                    ProgressView()
                        .tint(Theme.securityGold)
                        .frame(maxWidth: .infinity, minHeight: 160)
                } else if let error = vm.errorMessage, vm.allOffers.isEmpty {
                    LoanErrorState(message: error) { Task { await vm.fetchOffers() } }
                        .padding(.horizontal, Theme.screenPadding)
                } else {
                    LoanOfferListSection(offers: vm.filteredOffers)
                }
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Loan Marketplace")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.fetchOffers() }
        .refreshable { await vm.fetchOffers() }
        .sheet(isPresented: $showFilters) {
            LoanFilterSheet(vm: vm)
                .presentationDetents([.medium])
                .presentationDragIndicator(.visible)
        }
    }
}

// MARK: - Header

struct LoanMarketplaceHeader: View {
    let offerCount: Int

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("Loan Marketplace")
                .font(Theme.engravedSerif(size: 28, weight: .bold, relativeTo: .title))
                .foregroundColor(Theme.inkPrimary)

            Text("Compare personal, home, car, and gold loan offers side by side.")
                .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                .foregroundColor(Theme.inkSecondary)

            Text("DEMO OFFERS · NO REAL CREDIT-BUREAU PULL")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .padding(.horizontal, Theme.Spacing.medium)
                .padding(.vertical, Theme.Spacing.small)
                .foregroundColor(Theme.holdAmber)
                .background(Theme.holdAmber.opacity(0.12))
                .cornerRadius(Theme.CornerRadius.badge)

            Text("\(offerCount) offers available")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.0)
                .foregroundColor(Theme.inkTertiary)
        }
        .padding(.horizontal, Theme.screenPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Type Selector

struct LoanTypeSelector: View {
    @Binding var selectedType: LoanType?
    @Binding var showFilters: Bool

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: Theme.Spacing.standard) {
                    LoanFilterChip(label: "All", isSelected: selectedType == nil) {
                        selectedType = nil
                    }
                    ForEach(LoanType.allCases) { type in
                        LoanFilterChip(label: type.displayName, isSelected: selectedType == type) {
                            selectedType = type
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

struct LoanFilterChip: View {
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

// MARK: - Offer List

struct LoanOfferListSection: View {
    let offers: [LoanOfferDTO]

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            if offers.isEmpty {
                LoanEmptyState()
            } else {
                ForEach(offers) { offer in
                    LoanOfferRowCard(offer: offer)
                }
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct LoanEmptyState: View {
    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text("No Offers Match Your Filters")
                .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)
            Text("Try widening your loan type, amount, or tenure filters.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 160)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct LoanErrorState: View {
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

// MARK: - Offer Row Card

struct LoanOfferRowCard: View {
    let offer: LoanOfferDTO

    var body: some View {
        NavigationLink {
            LoanApplicationView(offer: offer)
        } label: {
            VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                LoanOfferRowHeader(offer: offer)
                GuillocheDivider()
                LoanOfferRowStats(offer: offer)
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
    }
}

private struct LoanOfferRowHeader: View {
    let offer: LoanOfferDTO

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(Theme.canvasShadow)
                .frame(width: 44, height: 44)
                .overlay(
                    Image(systemName: offer.parsedLoanType.icon)
                        .foregroundColor(Theme.inkPrimary)
                )

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(offer.nbfcName)
                    .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
                    .lineLimit(1)
                Text(offer.parsedLoanType.displayName)
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.2)
                    .foregroundColor(Theme.inkSecondary)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text(offer.interestRateDisplay)
                    .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                    .foregroundColor(Theme.bullGreen)
                Text("INTEREST")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .foregroundColor(Theme.inkTertiary)
            }
        }
    }
}

private struct LoanOfferRowStats: View {
    let offer: LoanOfferDTO

    var body: some View {
        HStack(spacing: Theme.Spacing.large) {
            LoanStatColumn(label: "Amount", value: offer.amountRangeDisplay)
            LoanStatColumn(label: "Tenure", value: offer.tenureRangeDisplay)
            LoanStatColumn(label: "Processing Fee", value: String(format: "%.1f%%", offer.processingFeePct))
            Spacer()
        }
    }
}

private struct LoanStatColumn: View {
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

struct LoanFilterSheet: View {
    @ObservedObject var vm: LoanViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                    LoanRangeFilter(
                        title: "Minimum Loan Amount Needed",
                        value: $vm.minAmount,
                        range: 0...1_00_00_000,
                        display: { $0 <= 0 ? "Any" : IndianFormatter.formatLakhsCrores($0) }
                    )
                    LoanRangeFilter(
                        title: "Maximum Loan Amount",
                        value: $vm.maxAmount,
                        range: 0...1_00_00_000,
                        display: { $0 >= 1_00_00_000 ? "Any" : IndianFormatter.formatLakhsCrores($0) }
                    )
                    LoanRangeFilter(
                        title: "Maximum Tenure",
                        value: $vm.maxTenureMonths,
                        range: 0...360,
                        display: { $0 >= 360 ? "Any" : "\(Int($0 / 12)) yrs" }
                    )
                }
                .padding(Theme.screenPadding)
            }
            .background(Theme.canvas.ignoresSafeArea())
            .navigationTitle("Filter Offers")
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

private struct LoanRangeFilter: View {
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
                .accessibilityLabel(title)
                .accessibilityValue(display(value))
        }
    }
}
