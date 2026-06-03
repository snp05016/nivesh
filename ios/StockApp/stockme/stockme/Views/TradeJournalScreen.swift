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
                    Text("TRADE JOURNAL")
                        .font(.system(.headline, design: .default).weight(.semibold))
                        .tracking(2)
                        .foregroundColor(Theme.securityGold)
                    Spacer()
                }
                .padding(.horizontal)
                .padding(.top, 16)
                .padding(.bottom, 12)

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
            LazyVStack(spacing: 10) {
                if isLoading {
                    ProgressView()
                        .tint(Theme.securityGold)
                        .padding(.top, 40)
                } else if entries.isEmpty {
                    Text("No journal entries yet.\nTap 'Add Entry' to record your first trade decision.")
                        .font(.system(size: 14, design: .serif).italic())
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
            .padding(.bottom, 20)
        }
    }

    // MARK: - Add Entry

    var addEntryView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // Ticker
                VStack(alignment: .leading, spacing: 4) {
                    Text("TICKER")
                        .font(.caption2).tracking(1).foregroundColor(Theme.inkSecondary)
                    TextField("e.g. RELIANCE", text: $newTicker)
                        .textFieldStyle(.plain)
                        .font(.system(.body, design: .monospaced))
                        .foregroundColor(Theme.inkPrimary)
                        .autocapitalization(.allCharacters)
                        .padding(10)
                        .background(Theme.canvasDeep)
                        .cornerRadius(6)
                        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.borderFine))
                }

                // Action picker
                VStack(alignment: .leading, spacing: 4) {
                    Text("ACTION")
                        .font(.caption2).tracking(1).foregroundColor(Theme.inkSecondary)
                    HStack(spacing: 8) {
                        ForEach(actions, id: \.self) { action in
                            Button(action: { newAction = action }) {
                                Text(action)
                                    .font(.caption.weight(.semibold))
                                    .foregroundColor(newAction == action ? .white : Theme.inkSecondary)
                                    .padding(.horizontal, 12).padding(.vertical, 6)
                                    .background(newAction == action ? actionColor(action) : Theme.canvasDeep)
                                    .cornerRadius(4)
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
                        .padding(10)
                        .background(Theme.canvasDeep)
                        .cornerRadius(6)
                        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.borderFine))
                }

                // Reason
                VStack(alignment: .leading, spacing: 4) {
                    Text("REASON / THESIS")
                        .font(.caption2).tracking(1).foregroundColor(Theme.inkSecondary)
                    TextEditor(text: $newReason)
                        .font(.system(size: 14, design: .serif))
                        .foregroundColor(Theme.inkPrimary)
                        .frame(minHeight: 80)
                        .padding(8)
                        .background(Theme.canvasDeep)
                        .cornerRadius(6)
                        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.borderFine))
                        .scrollContentBackground(.hidden)
                }

                // Mood
                VStack(alignment: .leading, spacing: 4) {
                    Text("MOOD")
                        .font(.caption2).tracking(1).foregroundColor(Theme.inkSecondary)
                    HStack(spacing: 8) {
                        ForEach(moods, id: \.self) { mood in
                            Button(action: { newMood = newMood == mood.lowercased() ? nil : mood.lowercased() }) {
                                Text(mood)
                                    .font(.caption)
                                    .foregroundColor(newMood == mood.lowercased() ? .white : Theme.inkSecondary)
                                    .padding(.horizontal, 8).padding(.vertical, 5)
                                    .background(newMood == mood.lowercased() ? Theme.securityGold : Theme.canvasDeep)
                                    .cornerRadius(4)
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
                    .padding(.vertical, 14)
                    .background(Theme.securityGold)
                    .cornerRadius(6)
                }
                .buttonStyle(.plain)
                .disabled(isSubmitting || newTicker.isEmpty || newReason.isEmpty)
                .padding(.top, 8)
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
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(entry.ticker)
                    .font(.system(.subheadline, design: .monospaced).weight(.bold))
                    .foregroundColor(Theme.inkPrimary)
                Text(entry.action)
                    .font(.caption.weight(.bold))
                    .foregroundColor(.white)
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .background(actionColor)
                    .cornerRadius(3)
                Spacer()
                if let price = entry.priceAtTime {
                    Text("₹\(String(format: "%.2f", price))")
                        .font(.system(.caption, design: .monospaced))
                        .foregroundColor(Theme.inkSecondary)
                }
            }

            if let reason = entry.reasonText, !reason.isEmpty {
                Text(reason)
                    .font(.system(size: 13, design: .serif).italic())
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
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.borderFine, lineWidth: 0.5))
    }
}
