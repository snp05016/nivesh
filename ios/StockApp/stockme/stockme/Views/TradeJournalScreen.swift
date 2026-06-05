import SwiftUI

struct TradeJournalScreen: View {
    let userId: Int
    @State private var entries: [TradeJournalEntry] = []
    @State private var selectedTab = 0  // 0=Journal, 1=Add Entry
    @State private var isLoading = false
    @State private var errorMessage: String? = nil

    // Add Entry form state
    @State private var newTicker = ""
    @State private var newAction = "BUY"
    @State private var newPrice = ""
    @State private var newReason = ""
    @State private var newMood: String? = nil
    @State private var isSubmitting = false

    let actions = ["BUY", "SELL", "HOLD", "WATCH"]
    let moods = ["Confident", "Uncertain", "FOMO", "Contrarian"]

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()

            VStack(spacing: 0) {
                // Header
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("व्यापार पत्रिका")
                            .font(Theme.hindiFont(size: 11))
                            .foregroundColor(Theme.inkSecondary)
                        Text("TRADE JOURNAL")
                            .font(Theme.engravedSerif(size: 24, weight: .bold))
                            .foregroundColor(Theme.inkPrimary)
                    }
                    Spacer()
                }
                .padding(.horizontal, Theme.screenPadding)
                .padding(.top, Theme.Spacing.card)
                .padding(.bottom, Theme.Spacing.standard)

                // Segmented picker
                Picker("Mode", selection: $selectedTab) {
                    Text("Journal").tag(0)
                    Text("Add Entry").tag(1)
                }
                .pickerStyle(.segmented)
                .padding(.horizontal)
                .padding(.bottom, 12)

                if selectedTab == 0 {
                    journalListView
                } else {
                    addEntryView
                }
            }
        }
        .task { await loadEntries() }
    }

    // MARK: - Journal List

    var journalListView: some View {
        ScrollView {
            LazyVStack(spacing: Theme.Spacing.standard) {
                if isLoading {
                    ProgressView()
                        .tint(Theme.securityGold)
                        .padding(.top, 40)
                } else if entries.isEmpty {
                    Text("No journal entries yet.\nTap 'Add Entry' to record your first trade decision.")
                        .font(.subheadline).fontDesign(.serif).italic()
                        .foregroundColor(Theme.inkSecondary)
                        .multilineTextAlignment(.center)
                        .padding(.top, 40)
                } else {
                    ForEach(entries) { entry in
                        JournalEntryCard(entry: entry)
                            .padding(.horizontal)
                    }
                }
            }
            .padding(.bottom, Theme.Spacing.screen)
        }
    }

    // MARK: - Add Entry

    var addEntryView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                // Ticker
                VStack(alignment: .leading, spacing: 4) {
                    Text("TICKER")
                        .font(.caption2).tracking(1).foregroundColor(Theme.inkSecondary)
                    TextField("e.g. RELIANCE", text: $newTicker)
                        .textFieldStyle(.plain)
                        .font(.system(.body, design: .monospaced))
                        .foregroundColor(Theme.inkPrimary)
                        .autocapitalization(.allCharacters)
                        .padding(Theme.Spacing.standard)
                        .background(Theme.canvasDeep)
                        .cornerRadius(Theme.CornerRadius.tight)
                        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderFine))
                }

                // Action picker
                VStack(alignment: .leading, spacing: 4) {
                    Text("ACTION")
                        .font(.caption2).tracking(1).foregroundColor(Theme.inkSecondary)
                    HStack(spacing: Theme.Spacing.medium) {
                        ForEach(actions, id: \.self) { action in
                            Button(action: { newAction = action }) {
                                Text(action)
                                    .font(.caption.weight(.semibold))
                                    .foregroundColor(newAction == action ? .white : Theme.inkSecondary)
                                    .padding(.horizontal, Theme.Spacing.standard).padding(.vertical, Theme.Spacing.tight)
                                    .background(newAction == action ? actionColor(action) : Theme.canvasDeep)
                                    .cornerRadius(Theme.CornerRadius.small)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }

                // Price
                VStack(alignment: .leading, spacing: 4) {
                    Text("PRICE AT TIME (₹)")
                        .font(.caption2).tracking(1).foregroundColor(Theme.inkSecondary)
                    TextField("0.00", text: $newPrice)
                        .textFieldStyle(.plain)
                        .keyboardType(.decimalPad)
                        .font(.system(.body, design: .monospaced))
                        .foregroundColor(Theme.inkPrimary)
                        .padding(Theme.Spacing.standard)
                        .background(Theme.canvasDeep)
                        .cornerRadius(Theme.CornerRadius.tight)
                        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderFine))
                }

                // Reason
                VStack(alignment: .leading, spacing: 4) {
                    Text("REASON / THESIS")
                        .font(.caption2).tracking(1).foregroundColor(Theme.inkSecondary)
                    TextEditor(text: $newReason)
                        .font(.subheadline).fontDesign(.serif)
                        .foregroundColor(Theme.inkPrimary)
                        .frame(minHeight: 80)
                        .padding(Theme.Spacing.medium)
                        .background(Theme.canvasDeep)
                        .cornerRadius(Theme.CornerRadius.tight)
                        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight).stroke(Theme.borderFine))
                        .scrollContentBackground(.hidden)
                }

                // Mood
                VStack(alignment: .leading, spacing: 4) {
                    Text("MOOD")
                        .font(.caption2).tracking(1).foregroundColor(Theme.inkSecondary)
                    HStack(spacing: Theme.Spacing.medium) {
                        ForEach(moods, id: \.self) { mood in
                            Button(action: { newMood = newMood == mood.lowercased() ? nil : mood.lowercased() }) {
                                Text(mood)
                                    .font(.caption)
                                    .foregroundColor(newMood == mood.lowercased() ? .white : Theme.inkSecondary)
                                    .padding(.horizontal, Theme.Spacing.medium).padding(.vertical, Theme.Spacing.small)
                                    .background(newMood == mood.lowercased() ? Theme.securityGold : Theme.canvasDeep)
                                    .cornerRadius(Theme.CornerRadius.small)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }

                // Submit
                Button(action: { Task { await submitEntry() } }) {
                    HStack {
                        if isSubmitting {
                            ProgressView().tint(.black).scaleEffect(0.7)
                        }
                        Text("STAMP ENTRY")
                            .font(.system(.subheadline, design: .default).weight(.semibold))
                            .tracking(1.5)
                    }
                    .foregroundColor(.black)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Spacing.standard)
                    .background(Theme.securityGold)
                    .cornerRadius(Theme.CornerRadius.tight)
                }
                .buttonStyle(.plain)
                .disabled(isSubmitting || newTicker.isEmpty || newReason.isEmpty)
                .padding(.top, Theme.Spacing.medium)
            }
            .padding()
        }
    }

    // MARK: - Helpers

    func actionColor(_ action: String) -> Color {
        switch action {
        case "BUY": return Theme.signalEmerald
        case "SELL": return Theme.signalRuby
        case "HOLD": return Theme.securityGold
        default: return Theme.inkSecondary
        }
    }

    func loadEntries() async {
        isLoading = true
        entries = (try? await NetworkManager.shared.fetchTradeJournal(userId: userId)) ?? []
        isLoading = false
    }

    func submitEntry() async {
        guard !newTicker.isEmpty, !newReason.isEmpty,
              let price = Double(newPrice), price > 0 else { return }
        isSubmitting = true
        let ticker = newTicker.uppercased().trimmingCharacters(in: .whitespaces)
        if let _ = try? await NetworkManager.shared.addTradeJournalEntry(
            userId: userId, ticker: ticker, companyName: nil,
            action: newAction, price: price, reason: newReason, mood: newMood
        ) {
            await loadEntries()
            newTicker = ""; newPrice = ""; newReason = ""; newMood = nil; newAction = "BUY"
            selectedTab = 0
        }
        isSubmitting = false
    }
}

// MARK: - Journal Entry Card

private struct JournalEntryCard: View {
    let entry: TradeJournalEntry

    var actionColor: Color {
        switch entry.action {
        case "BUY": return Theme.signalEmerald
        case "SELL": return Theme.signalRuby
        case "HOLD": return Theme.securityGold
        default: return Theme.inkSecondary
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack {
                Text(entry.ticker)
                    .font(.system(.subheadline, design: .monospaced).weight(.bold))
                    .foregroundColor(Theme.inkPrimary)
                Text(entry.action)
                    .font(.caption.weight(.bold))
                    .foregroundColor(.white)
                    .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                    .background(actionColor)
                    .cornerRadius(Theme.CornerRadius.small)
                Spacer()
                if let price = entry.priceAtTime {
                    Text("₹\(String(format: "%.2f", price))")
                        .font(.system(.caption, design: .monospaced))
                        .foregroundColor(Theme.inkSecondary)
                }
            }

            if let reason = entry.reasonText, !reason.isEmpty {
                Text(reason)
                    .font(.footnote).fontDesign(.serif).italic()
                    .foregroundColor(Theme.inkPrimary)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let outcome = entry.outcomeText, !outcome.isEmpty {
                let isProfit = outcome.lowercased().contains("profit")
                let isLoss = outcome.lowercased().contains("loss")
                Text("→ \(outcome)")
                    .font(.caption)
                    .foregroundColor(isProfit ? Theme.signalEmerald : isLoss ? Theme.signalRuby : Theme.inkSecondary)
            }

            HStack {
                if let mood = entry.mood {
                    Text(mood.uppercased())
                        .font(.caption2).tracking(0.5)
                        .foregroundColor(Theme.securityGold.opacity(0.7))
                }
                Spacer()
                if let date = entry.createdAt {
                    Text(date)
                        .font(.caption2)
                        .foregroundColor(Theme.inkSecondary)
                }
            }
        }
        .padding()
        .background(Theme.canvasDeep)
        .cornerRadius(Theme.CornerRadius.medium)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderFine, lineWidth: 0.5))
    }
}
