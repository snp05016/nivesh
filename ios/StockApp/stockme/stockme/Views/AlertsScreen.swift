import SwiftUI
import Combine

@MainActor
class AlertsViewModel: ObservableObject {
    @Published var alerts: [PriceAlert] = []
    @Published var isLoading = false
    @Published var triggeredBanner: [TriggeredAlert] = []
    @Published var showTriggeredBanner = false

    func fetchAlerts(userId: Int) async {
        isLoading = true
        alerts = (try? await NetworkManager.shared.getAlerts(userId: userId)) ?? []
        isLoading = false
    }

    func removeAlert(alertId: Int, userId: Int) async {
        try? await NetworkManager.shared.removeAlert(userId: userId, alertId: alertId)
        await fetchAlerts(userId: userId)
    }

    func checkTriggers(userId: Int) async {
        let triggered = (try? await NetworkManager.shared.checkAlerts(userId: userId)) ?? []
        if !triggered.isEmpty {
            triggeredBanner = triggered
            showTriggeredBanner = true
            await fetchAlerts(userId: userId)
        }
    }
}

struct AlertsScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @StateObject private var viewModel = AlertsViewModel()
    @State private var showAddAlert = false

    var activeAlerts: [PriceAlert] { viewModel.alerts.filter { !$0.triggered } }
    var triggeredAlerts: [PriceAlert] { viewModel.alerts.filter { $0.triggered } }

    var body: some View {
        NavigationStack {
            ZStack {
                DenominationBackground(denomination: .fifty)

                VStack(spacing: 0) {
                    // Bilingual header
                    VStack(alignment: .leading, spacing: 4) {
                        Text("मूल्य चेतावनी")
                            .font(Theme.hindiFont(size: 11))
                            .foregroundColor(Theme.inkSecondary)
                        Text("PRICE ALERTS")
                            .font(Theme.engravedSerif(size: 28, weight: .bold))
                            .foregroundColor(Theme.inkPrimary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, 12)
                    .padding(.bottom, 20)

                    if viewModel.isLoading {
                        Spacer()
                        ProgressView().tint(Theme.securityGold)
                        Spacer()
                    } else if viewModel.alerts.isEmpty {
                        // Empty state
                        Spacer()
                        VStack(spacing: 16) {
                            Image(systemName: "bell.slash")
                                .font(.system(size: 40))
                                .foregroundColor(Theme.inkSecondary.opacity(0.3))
                            Text("NO ALERTS SET")
                                .font(Theme.officialStampFont(size: 10))
                                .foregroundColor(Theme.inkSecondary)
                            Text("Set a target price from any stock's analysis to get notified.")
                                .font(Theme.serialNumberFont(size: 13))
                                .foregroundColor(Theme.inkTertiary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 40)
                        }
                        Spacer()
                    } else {
                        ScrollView {
                            VStack(spacing: 24) {
                                // Active alerts
                                if !activeAlerts.isEmpty {
                                    VStack(alignment: .leading, spacing: 12) {
                                        SectionHeader(title: "Active Alerts", hindiTitle: "सक्रिय अलर्ट")
                                        ScrollView(.horizontal, showsIndicators: false) {
                                            HStack(spacing: 12) {
                                                ForEach(activeAlerts) { alert in
                                                    AlertRow(alert: alert, onDelete: {
                                                        if let user = authManager.currentUser {
                                                            Task { await viewModel.removeAlert(alertId: alert.id, userId: user.userId) }
                                                        }
                                                    })
                                                    .frame(width: 320)
                                                }
                                            }
                                            .padding(.horizontal, Theme.screenPadding)
                                        }
                                    }
                                }

                                // Triggered alerts
                                if !triggeredAlerts.isEmpty {
                                    VStack(alignment: .leading, spacing: 12) {
                                        SectionHeader(title: "Triggered", hindiTitle: "लक्ष्य पहुंचा")
                                        ScrollView(.horizontal, showsIndicators: false) {
                                            HStack(spacing: 12) {
                                                ForEach(triggeredAlerts) { alert in
                                                    AlertRow(alert: alert, isTriggered: true, onDelete: {
                                                        if let user = authManager.currentUser {
                                                            Task { await viewModel.removeAlert(alertId: alert.id, userId: user.userId) }
                                                        }
                                                    })
                                                    .frame(width: 320)
                                                }
                                            }
                                            .padding(.horizontal, Theme.screenPadding)
                                        }
                                    }
                                }

                                Spacer(minLength: 100)
                            }
                        }
                    }
                }

                // Triggered banner
                if viewModel.showTriggeredBanner, let first = viewModel.triggeredBanner.first {
                    VStack {
                        HStack(spacing: 10) {
                            Image(systemName: "bell.fill").foregroundColor(Theme.securityGold)
                            VStack(alignment: .leading, spacing: 2) {
                                Text("ALERT TRIGGERED")
                                    .font(Theme.officialStampFont(size: 8))
                                    .foregroundColor(Theme.inkSecondary)
                                Text("\(first.ticker) reached ₹\(String(format: "%.2f", first.currentPrice))")
                                    .font(Theme.serialNumberFont(size: 13))
                                    .foregroundColor(Theme.inkPrimary)
                            }
                            Spacer()
                            Button("Dismiss") { viewModel.showTriggeredBanner = false }
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundColor(Theme.securityGold)
                        }
                        .padding(16)
                        .background(Theme.canvas)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .shadow(color: .black.opacity(0.12), radius: 8, x: 0, y: 4)
                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.securityGold.opacity(0.4), lineWidth: 1))
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                        Spacer()
                    }
                    .zIndex(10)
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .animation(.spring(response: 0.4), value: viewModel.showTriggeredBanner)
                }

                // FAB
                VStack {
                    Spacer()
                    HStack {
                        Spacer()
                        Button { showAddAlert = true } label: {
                            ZStack {
                                Circle().fill(Theme.securityGold).frame(width: 56, height: 56)
                                    .shadow(color: Theme.securityGold.opacity(0.3), radius: 10, x: 0, y: 5)
                                Image(systemName: "bell.badge.plus").font(.system(size: 22, weight: .bold)).foregroundColor(.white)
                            }
                        }
                        .padding(Theme.screenPadding)
                    }
                }
            }
        }
        .onAppear {
            if let user = authManager.currentUser {
                Task {
                    await viewModel.fetchAlerts(userId: user.userId)
                    await viewModel.checkTriggers(userId: user.userId)
                }
            }
        }
        .sheet(isPresented: $showAddAlert) {
            AddAlertSheet(authManager: authManager) {
                if let user = authManager.currentUser {
                    Task { await viewModel.fetchAlerts(userId: user.userId) }
                }
            }
        }
    }
}

private struct AlertRow: View {
    let alert: PriceAlert
    var isTriggered: Bool = false
    let onDelete: () -> Void

    var body: some View {
        HStack(spacing: 0) {
            Rectangle()
                .fill(isTriggered ? Theme.bullGreen.opacity(0.4) : Theme.securityGold.opacity(0.3))
                .frame(width: 1)
                .padding(.vertical, 12)

            HStack(spacing: 16) {
                // Direction icon
                VStack {
                    Image(systemName: alert.isAbove ? "arrow.up.circle.fill" : "arrow.down.circle.fill")
                        .font(.system(size: 28))
                        .foregroundColor(alert.isAbove ? Theme.bullGreen : Theme.bearRed)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text(alert.ticker)
                        .font(Theme.engravedSerif(size: 16, weight: .bold))
                        .foregroundColor(Theme.inkPrimary)
                    Text(alert.companyName.isEmpty ? alert.ticker : alert.companyName)
                        .font(Theme.serialNumberFont(size: 10))
                        .foregroundColor(Theme.inkSecondary)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 4) {
                    // Target price
                    HStack(spacing: 4) {
                        Image(systemName: alert.isAbove ? "chevron.up" : "chevron.down")
                            .font(.system(size: 10))
                        Text(IndianFormatter.price(alert.targetPrice))
                    }
                    .font(Theme.serialNumberFont(size: 14))
                    .foregroundColor(Theme.inkPrimary)

                    if isTriggered {
                        BanknoteSignalBadge(text: "HIT", color: Theme.bullGreen, rotation: -2)
                    } else if let dist = alert.distancePct {
                        Text(String(format: "%.1f%% away", dist))
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundColor(Theme.inkTertiary)
                    }
                }

                // Delete button (visible on card, since swipe actions don't work in horizontal scroll)
                Button(action: onDelete) {
                    Image(systemName: "trash.circle.fill")
                        .font(.system(size: 22))
                        .foregroundColor(Theme.bearRed.opacity(0.7))
                }
                .buttonStyle(.plain)
                .padding(.leading, 4)
            }
            .padding(.vertical, 14)
            .padding(.leading, 12)
            .padding(.trailing, 16)
        }
        .banknoteCard()
    }
}

struct AddAlertSheet: View {
    let authManager: AuthManager
    let onAdded: () -> Void
    var prefilledTicker: String = ""
    var prefilledCompany: String = ""
    @Environment(\.dismiss) var dismiss
    @State private var searchText = ""
    @State private var selectedTicker = ""
    @State private var selectedCompany = ""
    @State private var targetPriceText = ""
    @State private var direction = "above"
    @State private var isAdding = false
    @State private var errorText = ""

    var searchResults: [StockEntry] {
        searchText.isEmpty ? [] : StockDatabase.search(searchText)
    }
    var canAdd: Bool { !selectedTicker.isEmpty && Double(targetPriceText) != nil && (Double(targetPriceText) ?? 0) > 0 }

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                ScrollView {
                    VStack(spacing: 20) {
                        // Stock search
                        if selectedTicker.isEmpty {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("SEARCH STOCK")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundColor(Theme.inkSecondary)
                                HStack {
                                    Image(systemName: "magnifyingglass").foregroundColor(Theme.inkSecondary)
                                    TextField("Ticker or company...", text: $searchText)
                                        .foregroundColor(Theme.inkPrimary)
                                }
                                .padding(14)
                                .banknoteCard()

                                if !searchResults.isEmpty {
                                    VStack(spacing: 0) {
                                        ForEach(searchResults.prefix(5)) { entry in
                                            Button {
                                                selectedTicker = entry.ticker
                                                selectedCompany = entry.companyName
                                                searchText = ""
                                            } label: {
                                                HStack {
                                                    VStack(alignment: .leading, spacing: 2) {
                                                        Text(entry.ticker).font(Theme.serialNumberFont(size: 13)).foregroundColor(Theme.inkPrimary)
                                                        Text(entry.companyName).font(.system(size: 11)).foregroundColor(Theme.inkSecondary)
                                                    }
                                                    Spacer()
                                                    Image(systemName: "plus.circle").foregroundColor(Theme.securityGold)
                                                }
                                                .padding(12)
                                            }
                                            Divider().background(Theme.borderFine)
                                        }
                                    }
                                    .banknoteCard()
                                }
                            }
                        } else {
                            // Selected stock display
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(selectedTicker).font(Theme.engravedSerif(size: 16, weight: .bold)).foregroundColor(Theme.inkPrimary)
                                    Text(selectedCompany).font(.system(size: 12)).foregroundColor(Theme.inkSecondary)
                                }
                                Spacer()
                                Button { selectedTicker = ""; selectedCompany = "" } label: {
                                    Image(systemName: "xmark.circle.fill").foregroundColor(Theme.inkTertiary)
                                }
                            }
                            .padding(16)
                            .banknoteCard()
                        }

                        // Direction toggle
                        VStack(alignment: .leading, spacing: 8) {
                            Text("ALERT WHEN PRICE GOES")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundColor(Theme.inkSecondary)
                            HStack(spacing: 0) {
                                Button { direction = "above" } label: {
                                    HStack { Image(systemName: "arrow.up"); Text("Above Target") }
                                        .frame(maxWidth: .infinity)
                                        .padding(.vertical, 12)
                                        .background(direction == "above" ? Theme.bullGreen.opacity(0.1) : Color.clear)
                                        .foregroundColor(direction == "above" ? Theme.bullGreen : Theme.inkTertiary)
                                }
                                Button { direction = "below" } label: {
                                    HStack { Image(systemName: "arrow.down"); Text("Below Target") }
                                        .frame(maxWidth: .infinity)
                                        .padding(.vertical, 12)
                                        .background(direction == "below" ? Theme.bearRed.opacity(0.1) : Color.clear)
                                        .foregroundColor(direction == "below" ? Theme.bearRed : Theme.inkTertiary)
                                }
                            }
                            .font(Theme.serialNumberFont(size: 13))
                            .banknoteCard()
                        }

                        // Target price
                        VStack(alignment: .leading, spacing: 8) {
                            Text("TARGET PRICE (₹)")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundColor(Theme.inkSecondary)
                            TextField("e.g. 72.00", text: $targetPriceText)
                                .keyboardType(.decimalPad)
                                .font(Theme.serialNumberFont(size: 18))
                                .foregroundColor(Theme.inkPrimary)
                                .padding(16)
                                .banknoteCard()
                        }

                        if !errorText.isEmpty {
                            Text(errorText).font(.system(size: 12)).foregroundColor(Theme.bearRed)
                        }

                        Button {
                            guard let price = Double(targetPriceText), canAdd else { return }
                            isAdding = true
                            Task {
                                if let user = authManager.currentUser {
                                    do {
                                        _ = try await NetworkManager.shared.addAlert(userId: user.userId, ticker: selectedTicker, targetPrice: price, direction: direction, companyName: selectedCompany)
                                        onAdded()
                                        dismiss()
                                    } catch {
                                        errorText = "Failed to set alert. Try again."
                                    }
                                }
                                isAdding = false
                            }
                        } label: {
                            HStack {
                                if isAdding { ProgressView().tint(Theme.inkPrimary) }
                                else { Text("SET ALERT").font(Theme.officialStampFont(size: 10)) }
                            }
                            .frame(maxWidth: .infinity)
                            .padding(18)
                            .background(canAdd ? Theme.inkPrimary : Theme.inkPrimary.opacity(0.15))
                            .foregroundColor(canAdd ? Theme.canvas : Theme.inkPrimary.opacity(0.3))
                            .banknoteCard()
                        }
                        .disabled(!canAdd || isAdding)
                    }
                    .padding(20)
                }
            }
            .navigationTitle("Set Price Alert")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
        .onAppear {
            if !prefilledTicker.isEmpty {
                selectedTicker = prefilledTicker
                selectedCompany = prefilledCompany
            }
        }
    }
}
