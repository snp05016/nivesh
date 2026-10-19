import SwiftUI
import Combine

@MainActor
class AlertsViewModel: ObservableObject {
    @Published var alerts: [PriceAlert] = []
    @Published var isLoading = false
    @Published var triggeredBanner: [TriggeredAlert] = []
    @Published var showTriggeredBanner = false
    /// IOSCORE-06: a failed load is shown as an error, never as "NO ALERTS SET".
    @Published var loadError: String? = nil
    @Published var actionError: String? = nil

    /// Keeps the last loaded alerts when a refresh fails.
    func fetchAlerts(userId: Int) async {
        isLoading = true
        do {
            alerts = try await NetworkManager.shared.getAlerts(userId: userId)
            loadError = nil
        } catch {
            loadError = error.localizedDescription
            GlobalErrorDiagnoser.shared.trackNetworkError(error, endpoint: "/alerts/{user_id}")
        }
        isLoading = false
    }

    func removeAlert(alertId: Int, userId: Int) async {
        do {
            try await NetworkManager.shared.removeAlert(userId: userId, alertId: alertId)
        } catch {
            actionError = "The alert wasn't removed. \(error.localizedDescription)"
        }
        await fetchAlerts(userId: userId)
    }

    func checkTriggers(userId: Int) async {
        let triggered = (try? await NetworkManager.shared.checkAlerts(userId: userId)) ?? []
        if !triggered.isEmpty {
            triggeredBanner = triggered
            showTriggeredBanner = true
            if let first = triggered.first {
                A11y.announce("Alert triggered. \(first.ticker) reached \(IndianFormatter.price(first.currentPrice))")
            }
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
        Group {
            ZStack {
                DenominationBackground(denomination: .fifty)

                VStack(spacing: Theme.Spacing.none) {
                    // Bilingual header
                    VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                        Text("मूल्य चेतावनी")
                            .font(Theme.hindiFont(size: 11))
                            .foregroundStyle(Theme.inkSecondary)
                        Text("PRICE ALERTS")
                            .font(Theme.engravedSerif(size: 28, weight: .bold))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, Theme.Spacing.standard)
                    .padding(.bottom, Theme.screenPadding)

                    if viewModel.isLoading {
                        Spacer()
                        ProgressView().tint(Theme.securityGold)
                        Spacer()
                    } else if viewModel.alerts.isEmpty, let loadError = viewModel.loadError {
                        Spacer()
                        BanknoteErrorCanvas(title: "Couldn't load your alerts", detail: loadError, retryAction: {
                            if let user = authManager.currentUser { await viewModel.fetchAlerts(userId: user.userId) }
                        })
                        Spacer()
                    } else if viewModel.alerts.isEmpty {
                        // Empty state
                        Spacer()
                        VStack(spacing: Theme.Spacing.card) {
                            Image(systemName: "bell.slash")
                                .font(.largeTitle)
                                .foregroundStyle(Theme.inkSecondary.opacity(0.3))
                            Text("NO ALERTS SET")
                                .font(Theme.officialStampFont(size: 10))
                                .foregroundStyle(Theme.inkSecondary)
                            Text("Set a target price from any stock's analysis to get notified.")
                                .font(Theme.serialNumberFont(size: 13))
                                .foregroundStyle(Theme.inkTertiary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 40)
                        }
                        Spacer()
                    } else {
                        ScrollView {
                            VStack(spacing: Theme.Spacing.large) {
                                // Active alerts
                                if !activeAlerts.isEmpty {
                                    VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                                        SectionHeader(title: "Active Alerts", hindiTitle: "सक्रिय अलर्ट")
                                        ScrollView(.horizontal) {
                                            HStack(spacing: Theme.Spacing.standard) {
                                                ForEach(activeAlerts) { alert in
                                                    AlertRow(alert: alert, onDelete: {
                                                        if let user = authManager.currentUser {
                                                            Task { await viewModel.removeAlert(alertId: alert.id, userId: user.userId) }
                                                        }
                                                    })
                                                    .frame(width: UIScreen.main.bounds.width * 0.62)
                                                }
                                            }
                                            .padding(.horizontal, Theme.screenPadding)
                                        }
                                        .scrollIndicators(.hidden)
                                    }
                                }

                                    // Triggered alerts
                                if !triggeredAlerts.isEmpty {
                                    VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                                        SectionHeader(title: "Triggered", hindiTitle: "लक्ष्य पहुंचा")
                                        ScrollView(.horizontal) {
                                            HStack(spacing: Theme.Spacing.standard) {
                                                ForEach(triggeredAlerts) { alert in
                                                    AlertRow(alert: alert, isTriggered: true, onDelete: {
                                                        if let user = authManager.currentUser {
                                                            Task { await viewModel.removeAlert(alertId: alert.id, userId: user.userId) }
                                                        }
                                                    })
                                                    .frame(width: UIScreen.main.bounds.width * 0.62)
                                                }
                                            }
                                            .padding(.horizontal, Theme.screenPadding)
                                        }
                                        .scrollIndicators(.hidden)
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
                        HStack(spacing: Theme.Spacing.standard) {
                            Image(systemName: "bell.fill").foregroundStyle(Theme.securityGold)
                            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                Text("ALERT TRIGGERED")
                                    .font(Theme.officialStampFont(size: 8))
                                    .foregroundStyle(Theme.inkSecondary)
                                Text("\(first.ticker) reached \(IndianFormatter.price(first.currentPrice))")
                                    .font(Theme.serialNumberFont(size: 13))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                            Spacer()
                            Button { viewModel.showTriggeredBanner = false } label: {
                                Text("Dismiss").minTapTarget()
                            }
                            .buttonStyle(EKPressStyle())
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.securityGold)
                        }
                        .padding(Theme.Spacing.card)
                        .background(Theme.canvas)
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
                        .shadow(color: .black.opacity(0.12), radius: 8, x: 0, y: 4)
                        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.large).stroke(Theme.securityGold.opacity(0.4), lineWidth: 1))
                        .padding(.horizontal, Theme.Spacing.card)
                        .padding(.top, Theme.Spacing.medium)
                        Spacer()
                    }
                    .zIndex(10)
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .animation(.spring(response: 0.4), value: viewModel.showTriggeredBanner)
                }

                // FAB — sit left of chatbot button, same vertical plane
                VStack {
                    Spacer()
                    HStack {
                        Spacer()
                        Button { HapticManager.selection();  showAddAlert = true } label: {
                            ZStack {
                                Circle().fill(Theme.securityGold).frame(width: 56, height: 56)
                                    .shadow(color: Theme.securityGold.opacity(0.3), radius: 10, x: 0, y: 5)
                                Image(systemName: "bell.badge.plus").font(.title2.weight(.bold)).foregroundStyle(Theme.onAccent)
                            }
                        }
                        .padding(.trailing, Theme.Spacing.xLarge + Theme.Spacing.large + Theme.Spacing.standard)
                        .accessibilityLabel("Add alert")
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
                .padding(.bottom, Theme.Spacing.standard)
                .background(Theme.canvas.opacity(0.85))
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
        .banknoteDialog(
            "Couldn't remove alert",
            isPresented: Binding(get: { viewModel.actionError != nil }, set: { if !$0 { viewModel.actionError = nil } }),
            message: viewModel.actionError,
            buttons: [.init("OK")]
        )
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                NavigationLink(destination: NotificationInboxView()) {
                    Image(systemName: "tray")
                        .foregroundStyle(Theme.securityGold)
                }
                .accessibilityLabel("Notification inbox")
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
        HStack(spacing: Theme.Spacing.none) {
            Rectangle()
                .fill(isTriggered ? Theme.bullGreen.opacity(0.4) : Theme.securityGold.opacity(0.3))
                .frame(width: 1)
                .padding(.vertical, Theme.Spacing.standard)

            HStack(spacing: Theme.Spacing.card) {
                // Direction icon
                VStack {
                    Image(systemName: alert.isAbove ? "arrow.up.circle.fill" : "arrow.down.circle.fill")
                        .font(.title)
                        .foregroundStyle(alert.isAbove ? Theme.bullGreen : Theme.bearRed)
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(alert.ticker)
                        .font(Theme.engravedSerif(size: 16, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                    Text(alert.companyName.isEmpty ? alert.ticker : alert.companyName)
                        .font(Theme.serialNumberFont(size: 10))
                        .foregroundStyle(Theme.inkSecondary)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: Theme.Spacing.small) {
                    // Target price
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: alert.isAbove ? "chevron.up" : "chevron.down")
                            .font(.caption2)
                        Text(IndianFormatter.price(alert.targetPrice))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                    }
                    .font(Theme.serialNumberFont(size: 14))
                    .foregroundStyle(Theme.inkPrimary)

                    if isTriggered {
                        BanknoteSignalBadge(text: "HIT", color: Theme.bullGreen, rotation: -2)
                    } else if let dist = alert.distancePct {
                        Text(String(format: "%.1f%% away", dist))
                            .font(Theme.serialNumberFont(size: 10))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }

                // Delete button (visible on card, since swipe actions don't work in horizontal scroll)
                Button(action: { HapticManager.selection(); onDelete() }) { Image(systemName: "trash.circle.fill")
                        .font(.title2)
                        .foregroundStyle(Theme.bearRed.opacity(0.7))
                }
                .buttonStyle(.plain)
                .padding(.leading, Theme.Spacing.small)
                .accessibilityLabel("Delete alert")
            }
            .padding(.vertical, Theme.Spacing.standard)
            .padding(.leading, Theme.Spacing.standard)
            .padding(.trailing, Theme.Spacing.card)
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
    @State private var inputMode = "fixed" // "fixed" or "percentage"
    @State private var percentageText = ""
    @State private var currentPrice: Double? = nil
    @State private var priceLoading = false

    var searchResults: [StockEntry] {
        searchText.isEmpty ? [] : StockDatabase.search(searchText)
    }
    // Fix 3.12: Disable Save if target price is invalid or zero
    var calculatedTargetPrice: Double? {
        if inputMode == "fixed" {
            return DecimalText.parse(targetPriceText)
        } else {
            guard let pct = DecimalText.parse(percentageText), pct > 0, let current = currentPrice else { return nil }
            if direction == "above" {
                return current * (1 + pct / 100.0)
            } else {
                return current * (1 - pct / 100.0)
            }
        }
    }

    var targetError: String? {
        InputValidation.alertTargetError(target: calculatedTargetPrice, direction: direction, current: currentPrice)
    }

    var canAdd: Bool {
        !selectedTicker.isEmpty && targetError == nil
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                ScrollView {
                    VStack(spacing: Theme.Spacing.screen) {
                        // Stock search
                        if selectedTicker.isEmpty {
                            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                                Text("SEARCH STOCK")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                                HStack {
                                    Image(systemName: "magnifyingglass").foregroundStyle(Theme.inkSecondary)
                                    TextField("Ticker or company...", text: $searchText)
                                        .foregroundStyle(Theme.inkPrimary)
                                }
                                .padding(Theme.Spacing.standard)
                                .banknoteCard()

                                if !searchResults.isEmpty {
                                    VStack(spacing: Theme.Spacing.none) {
                                        ForEach(searchResults.prefix(5)) { entry in
                                            Button {
                                                HapticManager.selection()
                                                selectedTicker = entry.ticker
                                                selectedCompany = entry.companyName
                                                searchText = ""
                                                priceLoading = true
                                                Task {
                                                    let info = await NetworkManager.shared.quickInfo(ticker: entry.ticker)
                                                    currentPrice = info?.price
                                                    priceLoading = false
                                                }
                                            } label: {
                                                HStack {
                                                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                                        Text(entry.ticker).font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkPrimary)
                                                        Text(entry.companyName).font(.caption).foregroundStyle(Theme.inkSecondary)
                                                    }
                                                    Spacer()
                                                    Image(systemName: "plus.circle").foregroundStyle(Theme.securityGold)
                                                }
                                                .padding(Theme.Spacing.standard)
                                            }
                                            Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                                        }
                                    }
                                    .banknoteCard()
                                }
                            }
                        } else {
                            // Selected stock display
                            HStack {
                                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                    Text(selectedTicker).font(Theme.engravedSerif(size: 16, weight: .bold)).foregroundStyle(Theme.inkPrimary)
                                    Text(selectedCompany).font(.caption).foregroundStyle(Theme.inkSecondary)
                                    if priceLoading {
                                        ProgressView().scaleEffect(0.5)
                                    } else if let price = currentPrice {
                                        Text("Current: \(IndianFormatter.price(price))").font(Theme.serialNumberFont(size: 11)).foregroundStyle(Theme.inkTertiary)
                                    }
                                }
                                Spacer()
                                Button { HapticManager.selection();  selectedTicker = ""; selectedCompany = ""; currentPrice = nil } label: {
                                    Image(systemName: "xmark.circle.fill").foregroundStyle(Theme.inkTertiary)
                                }
                                .accessibilityLabel("Clear selected stock")
                            }
                            .padding(Theme.Spacing.card)
                            .banknoteCard()
                        }

                        // Direction toggle
                        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                            Text("ALERT WHEN PRICE GOES")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                            HStack(spacing: Theme.Spacing.none) {
                                Button { HapticManager.selection();  direction = "above" } label: {
                                    HStack { Image(systemName: "arrow.up"); Text("Above Target") }
                                        .frame(maxWidth: .infinity)
                                        .padding(.vertical, Theme.Spacing.standard)
                                        .background(direction == "above" ? Theme.bullGreen.opacity(0.1) : Color.clear)
                                        .foregroundStyle(direction == "above" ? Theme.bullGreen : Theme.inkTertiary)
                                }
                                Button { HapticManager.selection();  direction = "below" } label: {
                                    HStack { Image(systemName: "arrow.down"); Text("Below Target") }
                                        .frame(maxWidth: .infinity)
                                        .padding(.vertical, Theme.Spacing.standard)
                                        .background(direction == "below" ? Theme.bearRed.opacity(0.1) : Color.clear)
                                        .foregroundStyle(direction == "below" ? Theme.bearRed : Theme.inkTertiary)
                                }
                            }
                            .font(Theme.serialNumberFont(size: 13))
                            .banknoteCard()
                        }

                        // Input Mode Toggle
                        Picker("Input Mode", selection: $inputMode) {
                            Text("Fixed Price").tag("fixed")
                            Text("Percentage").tag("percentage")
                        }
                        .pickerStyle(.segmented)

                        // Target value
                        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                            if inputMode == "fixed" {
                                Text("TARGET PRICE (₹)")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                                TextField("e.g. 72.00", text: $targetPriceText)
                                    .keyboardType(.decimalPad)
                                    .font(Theme.serialNumberFont(size: 18))
                                    .foregroundStyle(Theme.inkPrimary)
                                    .padding(Theme.Spacing.card)
                                    .banknoteCard()
                            } else {
                                Text("PERCENTAGE MOVE (%)")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                                TextField("e.g. 5 for 5%", text: $percentageText)
                                    .keyboardType(.decimalPad)
                                    .font(Theme.serialNumberFont(size: 18))
                                    .foregroundStyle(Theme.inkPrimary)
                                    .padding(Theme.Spacing.card)
                                    .banknoteCard()
                                if let target = calculatedTargetPrice {
                                    Text("Implied target price: \(IndianFormatter.price(target))")
                                        .font(Theme.serialNumberFont(size: 11))
                                        .foregroundStyle(Theme.securityGold)
                                }
                            }
                        }

                        if !selectedTicker.isEmpty, (inputMode == "fixed" ? !targetPriceText.isEmpty : !percentageText.isEmpty),
                           let hint = targetError {
                            Text(hint).font(.caption).foregroundStyle(Theme.bearRed)
                        }

                        if !errorText.isEmpty {
                            Text(errorText).font(.caption).foregroundStyle(Theme.bearRed)
                        }

                        Button {
                            HapticManager.selection()
                            guard let price = calculatedTargetPrice, canAdd else { return }
                            guard let user = authManager.currentUser else {
                                errorText = "Sign in to set alerts."
                                return
                            }
                            isAdding = true
                            errorText = ""
                            Task {
                                do {
                                    _ = try await NetworkManager.shared.addAlert(userId: user.userId, ticker: selectedTicker, targetPrice: price, direction: direction, companyName: selectedCompany)
                                    EventLogger.shared.log(.alertCreate, ["direction": direction == "above" ? "above" : "below"])
                                    onAdded()
                                    dismiss()
                                } catch {
                                    errorText = (error as? NetworkError)?.upgradeMessage ?? "Failed to set alert. Try again."
                                }
                                isAdding = false
                            }
                        } label: {
                            HStack {
                                if isAdding { ProgressView().tint(Theme.inkPrimary) }
                                else { Text("SET ALERT").font(Theme.officialStampFont(size: 10)) }
                            }
                            .frame(maxWidth: .infinity)
                            .padding(Theme.Spacing.card)
                            .background(canAdd ? Theme.inkPrimary : Theme.inkPrimary.opacity(0.15))
                            .foregroundStyle(canAdd ? Theme.canvas : Theme.inkPrimary.opacity(0.3))
                            .banknoteCard()
                        }
                        .disabled(!canAdd || isAdding)
                    }
                    .padding(Theme.Spacing.screen)
                }
            }
            .navigationTitle("Set Price Alert")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }.buttonStyle(EKPressStyle())
                }
            }
        }
        .onAppear {
            if !prefilledTicker.isEmpty {
                selectedTicker = prefilledTicker
                selectedCompany = prefilledCompany
                priceLoading = true
                Task {
                    let info = await NetworkManager.shared.quickInfo(ticker: prefilledTicker)
                    currentPrice = info?.price
                    priceLoading = false
                }
            }
        }
    }
}
