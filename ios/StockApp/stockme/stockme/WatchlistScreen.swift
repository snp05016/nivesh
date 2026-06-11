import SwiftUI

// MARK: - WatchlistScreen (Phase 6 — Bloomberg-Terminal dark redesign)
// Standalone watchlist surface. Fetches the user's watchlist via NetworkManager,
// renders dark `WatchlistRow`s with avatar + sparkline + price + signal pill.
// Search, empty-state, swipe-to-remove and deep-link-add behaviour preserved.

struct WatchlistScreen: View {
    @EnvironmentObject var authManager: AuthManager

    @State private var items: [WatchlistItem] = []
    @State private var searchText: String = ""
    @State private var isLoading = false
    @State private var errorMessage: String?

    private var filteredItems: [WatchlistItem] {
        let query = searchText.trimmingCharacters(in: .whitespaces).lowercased()
        guard !query.isEmpty else { return items }
        return items.filter {
            $0.ticker.lowercased().contains(query) ||
            $0.companyName.lowercased().contains(query)
        }
    }

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            ScrollView {
                LazyVStack(spacing: 0) {
                    header

                    searchField
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.bottom, Theme.Spacing.standard)

                    if filteredItems.isEmpty {
                        emptyState
                            .padding(.top, Theme.Spacing.xLarge)
                    } else {
                        ForEach(filteredItems) { item in
                            NavigationLink(value: item.ticker) {
                                WatchlistRow(item: item, onTap: { _ in
                                    HapticManager.selection()
                                })
                            }
                            .buttonStyle(EKPressStyle())
                            .contextMenu {
                                Button(role: .destructive) {
                                    remove(item)
                                } label: {
                                    Label("Remove from Watchlist", systemImage: "trash")
                                }
                            }

                            Rectangle()
                                .fill(Color.white.opacity(0.05))
                                .frame(height: 0.5)
                                .padding(.horizontal, Theme.screenPadding)
                        }
                    }
                }
            }
            .background(Theme.canvas)
            .refreshable { await load() }
        }
        .task { await load() }
        .onReceive(NotificationCenter.default.publisher(for: Notification.Name("DeepLinkWatchlistAdd"))) { _ in
            // A stock was added via deep link elsewhere — refresh to reflect it.
            Task { await load() }
        }
    }

    // MARK: - Header (4c)

    private var header: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text("\(items.count) instruments")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(0.5)
                .foregroundStyle(Theme.inkSecondary)
            HStack(alignment: .center) {
                Text("Watchlist")
                    .font(Theme.engravedSerif(size: 28, weight: .bold, relativeTo: .largeTitle))
                    .foregroundStyle(Theme.inkPrimary)
                Spacer()
                HStack(spacing: Theme.Spacing.xSmall) {
                    Text("Nivesh")
                        .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .callout))
                        .foregroundStyle(Theme.securityGold)
                    Text("निवेश")
                        .font(Theme.hindiFont(size: 14, relativeTo: .callout))
                        .foregroundStyle(Theme.inkPrimary)
                }
            }
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.top, Theme.Spacing.large)
        .padding(.bottom, Theme.Spacing.standard)
    }

    // MARK: - Search

    private var searchField: some View {
        HStack(spacing: Theme.Spacing.medium) {
            Image(systemName: "magnifyingglass")
                .font(.footnote.weight(.semibold))
                .foregroundStyle(Theme.inkTertiary)
            TextField("", text: $searchText, prompt:
                Text("Search ticker or company")
                    .foregroundColor(Theme.inkTertiary)
            )
            .font(Theme.serialNumberFont(size: 14, relativeTo: .callout))
            .foregroundStyle(Theme.inkPrimary)
            .autocorrectionDisabled()
            .textInputAutocapitalization(.characters)
            if !searchText.isEmpty {
                Button {
                    HapticManager.selection()
                    searchText = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(Theme.inkTertiary)
                }
                .buttonStyle(EKPressStyle())
            }
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(Color.white.opacity(0.06), lineWidth: 1)
        )
    }

    // MARK: - Empty state

    private var emptyState: some View {
        VStack(spacing: Theme.Spacing.card) {
            Image(systemName: searchText.isEmpty ? "binoculars" : "magnifyingglass")
                .font(.largeTitle.weight(.light))
                .foregroundStyle(Theme.inkTertiary.opacity(0.4))
            Text(searchText.isEmpty ? "NO STOCKS ON WATCHLIST" : "NO MATCHES")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
            Text(searchText.isEmpty
                 ? "Add stocks from Search to track them here."
                 : "No watchlist instrument matches “\(searchText)”.")
                .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body))
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Spacing.xLarge)
        .padding(.horizontal, Theme.screenPadding)
    }

    // MARK: - Data wiring

    private func load() async {
        guard let userId = authManager.currentUser?.userId else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            items = try await NetworkManager.shared.getWatchlist(userId: userId)
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func remove(_ item: WatchlistItem) {
        guard let userId = authManager.currentUser?.userId else { return }
        HapticManager.selection()
        // Optimistic removal — restore on failure.
        let snapshot = items
        items.removeAll { $0.ticker == item.ticker }
        Task {
            do {
                try await NetworkManager.shared.removeFromWatchlist(userId: userId, ticker: item.ticker)
                HapticManager.success()
            } catch {
                items = snapshot
                HapticManager.error()
            }
        }
    }
}

// MARK: - WatchlistRow (4a)

struct WatchlistRow: View {
    let item: WatchlistItem
    let onTap: (WatchlistItem) -> Void

    private var isPositive: Bool { item.dayChangePct >= 0 }

    /// The flat `WatchlistItem` model carries no price-history array, so derive a
    /// tiny directional series for the sparkline from the day change.
    private var sparklineSeries: [Double] {
        let base = item.currentPrice
        let delta = base * (item.dayChangePct / 100.0)
        let start = base - delta
        return [start, start + delta * 0.4, start + delta * 0.25, start + delta * 0.8, base]
    }

    private var initials: String {
        String(item.ticker.prefix(2)).uppercased()
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {

            // 2-letter avatar — rounded square, dark teal bg (#0D2432)
            ZStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .fill(Color(UIColor(red: 0.051, green: 0.141, blue: 0.196, alpha: 1)))
                    .frame(width: 42, height: 42)
                Text(initials)
                    .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .callout))
                    .foregroundStyle(Theme.securityGold)
            }

            // Ticker + company name
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(item.ticker)
                    .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .body))
                    .foregroundStyle(Theme.inkPrimary)
                Text(item.companyName.isEmpty ? "—" : item.companyName)
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(0.5)
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(1)
            }

            Spacer(minLength: Theme.Spacing.medium)

            // Sparkline (mini directional line)
            WatchlistMiniSparkline(dataPoints: sparklineSeries, isPositive: isPositive)
                .frame(width: 56, height: 28)

            // Price + signal badge
            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text(IndianFormatter.price(item.currentPrice))
                    .font(Theme.serialNumberFont(size: 14, relativeTo: .callout))
                    .foregroundStyle(Theme.inkPrimary)
                SignalBadgePill(value: item.dayChangePct, isPercent: true)
            }
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.vertical, Theme.Spacing.standard)
        .contentShape(Rectangle())
        .onTapGesture { onTap(item) }
    }
}

// MARK: - WatchlistMiniSparkline (4b) — file-local wrapper over the shared GlowLineChart
// Named distinctly to avoid colliding with the public `MiniSparkline` in EarningsDashboardView.

private struct WatchlistMiniSparkline: View {
    let dataPoints: [Double]
    let isPositive: Bool

    var body: some View {
        GlowLineChart(
            dataPoints: dataPoints.isEmpty ? [1, 1, 1, 1, 1] : dataPoints,
            isPositive: isPositive
        )
    }
}
