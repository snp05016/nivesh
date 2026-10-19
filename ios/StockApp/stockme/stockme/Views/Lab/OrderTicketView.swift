import SwiftUI

/// Order ticket sheet. A written thesis is required: the autopsy later grades the
/// decision against what was knowable when it was made.
struct OrderTicketView: View {
    let request: LabTicketRequest
    let lastClose: Double?
    let onSubmit: (LabOrderDraft) async -> Bool

    @Environment(\.dismiss) private var dismiss
    @State private var side: String
    @State private var qtyText = ""
    @State private var orderType = "MARKET"
    @State private var limitText = ""
    @State private var stopText = ""
    @State private var tif = "DAY"
    @State private var thesis = ""
    @State private var plannedStopText = ""
    @State private var plannedExitText = ""
    @State private var conviction = 0.5
    @State private var sending = false
    @State private var failed = false

    init(request: LabTicketRequest, lastClose: Double?, onSubmit: @escaping (LabOrderDraft) async -> Bool) {
        self.request = request
        self.lastClose = lastClose
        self.onSubmit = onSubmit
        _side = State(initialValue: request.side)
    }

    private var draft: LabOrderDraft {
        LabOrderDraft(symbol: request.symbol, side: side, qty: Int(qtyText) ?? 0, orderType: orderType,
                      limit: Double(limitText), stop: Double(stopText), tif: tif, thesis: thesis,
                      plannedStop: Double(plannedStopText), plannedExit: Double(plannedExitText),
                      horizonDays: nil, conviction: conviction)
    }

    private var notional: Double? {
        let px = orderType == "LIMIT" ? Double(limitText) : orderType == "STOP" ? Double(stopText) : lastClose
        guard let px, let q = Int(qtyText), q > 0 else { return nil }
        return px * Double(q)
    }

    var body: some View {
        NavigationStack {
            Form {
                LabTicketOrderSection(symbol: request.symbol, lastClose: lastClose, side: $side, qtyText: $qtyText,
                                      orderType: $orderType, limitText: $limitText, stopText: $stopText, tif: $tif)
                LabTicketThesisSection(thesis: $thesis, plannedStopText: $plannedStopText,
                                       plannedExitText: $plannedExitText, conviction: $conviction)
                Section {
                    LabKeyValueRow(key: "Approx. value", value: LabFormat.money(notional))
                    Text("Statutory charges + brokerage applied at fill. Fills happen from the next session at the earliest, with slippage that grows with order size.")
                        .font(Theme.microLabel())
                        .foregroundStyle(Theme.inkSecondary)
                    if let problem = draft.problem { LabInlineError(message: problem) }
                    if failed { LabInlineError(message: "The simulator did not accept this order. See the message on the session screen.") }
                }
            }
            .scrollContentBackground(.hidden)
            .background(Theme.canvas.ignoresSafeArea())
            .tint(Theme.securityGold)
            .navigationTitle("\(side == "BUY" ? "Buy" : "Sell") \(request.symbol)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { HapticManager.selection(); dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(sending ? "Placing…" : "Place order") { Task { await submit() } }
                        .disabled(draft.problem != nil || sending)
                }
            }
        }
    }

    private func submit() async {
        HapticManager.selection()
        sending = true
        failed = false
        let ok = await onSubmit(draft)
        sending = false
        if ok { dismiss() } else { failed = true }
    }
}

private struct LabTicketOrderSection: View {
    let symbol: String
    let lastClose: Double?
    @Binding var side: String
    @Binding var qtyText: String
    @Binding var orderType: String
    @Binding var limitText: String
    @Binding var stopText: String
    @Binding var tif: String

    var body: some View {
        Section {
            LabKeyValueRow(key: "Last close (simulated date)", value: LabFormat.price(lastClose))
            Picker("Side", selection: $side) {
                Text("Buy").tag("BUY")
                Text("Sell").tag("SELL")
            }
            .pickerStyle(.segmented)
            TextField("Quantity (shares)", text: $qtyText)
                .keyboardType(.numberPad)
                .font(Theme.monoTabular(size: 15))
            Picker("Order type", selection: $orderType) {
                Text("Market").tag("MARKET")
                Text("Limit").tag("LIMIT")
                Text("Stop").tag("STOP")
            }
            .pickerStyle(.segmented)
            if orderType == "LIMIT" {
                TextField("Limit price (₹)", text: $limitText).keyboardType(.decimalPad).font(Theme.monoTabular(size: 15))
            }
            if orderType == "STOP" {
                TextField("Stop trigger (₹)", text: $stopText).keyboardType(.decimalPad).font(Theme.monoTabular(size: 15))
            }
            Picker("Validity", selection: $tif) {
                Text("Day").tag("DAY")
                Text("Good till cancelled").tag("GTC")
            }
        } header: {
            Text("Order")
        }
        .onChange(of: side) { _, _ in HapticManager.selection() }
        .onChange(of: orderType) { _, _ in HapticManager.selection() }
    }
}

private struct LabTicketThesisSection: View {
    @Binding var thesis: String
    @Binding var plannedStopText: String
    @Binding var plannedExitText: String
    @Binding var conviction: Double

    var body: some View {
        Section {
            TextField("Why this trade, and what would prove you wrong?", text: $thesis, axis: .vertical)
                .lineLimit(3...6)
                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
            TextField("Planned stop (₹, optional)", text: $plannedStopText).keyboardType(.decimalPad)
            TextField("Planned exit (₹, optional)", text: $plannedExitText).keyboardType(.decimalPad)
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                Text("Conviction: \(Int((conviction * 100).rounded()))%")
                    .font(Theme.monoTabular(size: 13))
                    .foregroundStyle(Theme.inkPrimary)
                Slider(value: $conviction, in: 0...1, step: 0.05)
                    .accessibilityLabel("Conviction")
                    .accessibilityValue("\(Int((conviction * 100).rounded())) percent")
                Text("Used later to check how well your confidence matched outcomes.")
                    .font(Theme.microLabel())
                    .foregroundStyle(Theme.inkTertiary)
            }
        } header: {
            Text("Thesis (required)")
        }
    }
}
