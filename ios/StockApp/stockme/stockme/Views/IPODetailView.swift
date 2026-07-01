import SwiftUI

// MARK: - IPO Detail

struct IPODetailView: View {
    @StateObject private var vm: IPODetailViewModel

    init(seed: IPOListing) {
        _vm = StateObject(wrappedValue: IPODetailViewModel(ipoId: String(seed.id), seed: seed))
    }

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                if let listing = vm.listing {
                    IPODetailHeader(listing: listing)

                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                    IPOKeyFactsGrid(listing: listing)
                        .padding(.horizontal, Theme.screenPadding)

                    IPOTimelineSection(listing: listing)
                        .padding(.horizontal, Theme.screenPadding)

                    if let subscription = vm.subscription {
                        IPOSubscriptionSection(listing: listing, subscription: subscription)
                            .padding(.horizontal, Theme.screenPadding)
                    }
                } else if vm.isLoading {
                    ProgressView()
                        .tint(Theme.securityGold)
                        .frame(maxWidth: .infinity, minHeight: 240)
                } else if let error = vm.errorMessage {
                    IPOErrorState(message: error) { vm.fetchDetail() }
                        .padding(.horizontal, Theme.screenPadding)
                }
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle(vm.listing?.companyName ?? "IPO Detail")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            vm.fetchDetail()
            vm.startLiveSubscriptionUpdates()
        }
        .onDisappear { vm.stopLiveSubscriptionUpdates() }
        .refreshable { vm.fetchDetail() }
    }
}

// MARK: - Header

private struct IPODetailHeader: View {
    let listing: IPOListing

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .fill(Theme.canvasShadow)
                .frame(width: 56, height: 56)
                .overlay(
                    Text(String(listing.companyName.prefix(1)))
                        .font(Theme.officialStampFont(size: 20, relativeTo: .title3))
                        .foregroundColor(Theme.inkPrimary)
                )

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(listing.companyName)
                    .font(Theme.engravedSerif(size: 22, weight: .bold, relativeTo: .title2))
                    .foregroundColor(Theme.inkPrimary)

                if let symbol = listing.symbol {
                    Text(symbol)
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundColor(Theme.inkTertiary)
                }
            }

            Spacer()
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - Key Facts

private struct IPOKeyFactsGrid: View {
    let listing: IPOListing

    private let columns = [GridItem(.flexible()), GridItem(.flexible())]

    var body: some View {
        LazyVGrid(columns: columns, spacing: Theme.Spacing.card) {
            IPOFactTile(label: "Price Band", value: listing.priceBandDisplay)
            IPOFactTile(label: "Lot Size", value: listing.lotSizeDisplay)
            IPOFactTile(label: "Issue Size", value: listing.issueSizeDisplay)
            if let gmp = listing.gmp {
                IPOFactTile(
                    label: "GMP",
                    value: IndianFormatter.price(gmp),
                    valueColor: gmp >= 0 ? Theme.bullGreen : Theme.bearRed
                )
            }
            if let pct = listing.estimatedListingGainPct {
                IPOFactTile(
                    label: "Est. Listing Gain",
                    value: IndianFormatter.delta(pct),
                    valueColor: pct >= 0 ? Theme.bullGreen : Theme.bearRed
                )
            }
            IPOFactTile(label: "Status", value: listing.status?.displayLabel ?? "—")
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct IPOFactTile: View {
    let label: String
    let value: String
    var valueColor: Color = Theme.inkPrimary

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .tracking(1.5)
                .foregroundColor(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                .foregroundColor(valueColor)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Timeline

private struct IPOTimelineSection: View {
    let listing: IPOListing

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("TIMELINE")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)

            if let openDate = listing.openDate {
                IPOTimelineRow(label: "Opens", date: openDate)
            }
            if let closeDate = listing.closeDate {
                IPOTimelineRow(label: "Closes", date: closeDate)
            }
            if let listingDate = listing.listingDate {
                IPOTimelineRow(label: "Listing Date", date: listingDate)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct IPOTimelineRow: View {
    let label: String
    let date: String

    var body: some View {
        HStack {
            Text(label)
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundColor(Theme.inkSecondary)
            Spacer()
            Text(date)
                .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                .foregroundColor(Theme.inkPrimary)
        }
    }
}

// MARK: - Subscription

private struct IPOSubscriptionSection: View {
    let listing: IPOListing
    let subscription: IPOSubscriptionDetail

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            HStack {
                Text("SUBSCRIPTION STATUS")
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.5)
                    .foregroundColor(Theme.inkSecondary)
                Spacer()
                Text(String(format: "%.2fx overall", subscription.totalTimes))
                    .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                    .foregroundColor(subscription.totalTimes >= 1 ? Theme.bullGreen : Theme.holdAmber)
            }

            IPOSubscriptionRow(label: "QIB", times: subscription.qibTimes)
            IPOSubscriptionRow(label: "NII", times: subscription.niiTimes)
            IPOSubscriptionRow(label: "Retail", times: subscription.retailTimes)
            if let employee = subscription.employeeTimes {
                IPOSubscriptionRow(label: "Employee", times: employee)
            }

            if let asOf = subscription.asOf {
                Text("As of \(asOf)")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .foregroundColor(Theme.inkTertiary)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct IPOSubscriptionRow: View {
    let label: String
    let times: Double

    private var barColor: Color {
        times >= 1 ? Theme.bullGreen : Theme.holdAmber
    }

    private var fraction: Double {
        min(times / 5.0, 1.0)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            HStack {
                Text(label)
                    .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                    .foregroundColor(Theme.inkSecondary)
                Spacer()
                Text(String(format: "%.2fx", times))
                    .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                    .foregroundColor(barColor)
            }
            ProgressView(value: fraction)
                .tint(barColor)
                .frame(height: 6)
        }
    }
}

