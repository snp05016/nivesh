import SwiftUI

struct CompareScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @Environment(\.dismiss) var dismiss

    @State private var tickerA = ""
    @State private var tickerB = ""
    @State private var infoA: QuickInfo? = nil
    @State private var infoB: QuickInfo? = nil
    @State private var infoC: QuickInfo? = nil
    @State private var loading = false
    @State private var searchTextA = ""
    @State private var searchTextB = ""
    @State private var searchTextC = ""
    @State private var selectedA: StockEntry? = nil
    @State private var selectedB: StockEntry? = nil
    @State private var selectedC: StockEntry? = nil

    var body: some View {
        NavigationStack {
            ZStack {
                DenominationBackground(denomination: .twoHundred)

                ScrollView {
                    VStack(spacing: 20) {
                        // Picker row
                        HStack(spacing: Theme.Spacing.small) {
                            StockPickerButton(label: "Stock A", selected: selectedA, searchText: $searchTextA) { entry in
                                selectedA = entry
                                searchTextA = ""
                            }
                            Image(systemName: "arrow.left.arrow.right")
                                .foregroundStyle(Theme.securityGold)
                                .font(.caption.weight(.bold))
                            StockPickerButton(label: "Stock B", selected: selectedB, searchText: $searchTextB) { entry in
                                selectedB = entry
                                searchTextB = ""
                            }
                            if selectedB != nil || selectedC != nil {
                                Image(systemName: "arrow.left.arrow.right")
                                    .foregroundStyle(Theme.securityGold)
                                    .font(.caption.weight(.bold))
                                StockPickerButton(label: "Stock C", selected: selectedC, searchText: $searchTextC) { entry in
                                    selectedC = entry
                                    searchTextC = ""
                                }
                            }
                        }
                        .padding(.horizontal, Theme.screenPadding)

                        if loading {
                            VStack(spacing: 12) {
                                ProgressView().tint(Theme.securityGold).scaleEffect(1.2)
                                Text("Fetching data…")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                            }
                            .padding(40)
                        } else if let a = infoA, let b = infoB {
                            compareGrid(a: a, b: b, c: infoC)
                        } else {
                            VStack(spacing: 10) {
                                Image(systemName: "chart.bar.xaxis.ascending")
                                    .font(.largeTitle).foregroundStyle(Theme.inkTertiary)
                                Text("Select two stocks to compare")
                                    .font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkTertiary)
                            }
                            .padding(60)
                        }

                        Spacer(minLength: 80)
                    }
                    .padding(.top, 12)
                }
            }
            .navigationTitle("COMPARE")
            .navigationBarTitleDisplayMode(.inline)
            .navigationBarBackButtonHidden(true)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button { dismiss() } label: {
                        Image(systemName: "chevron.left")
                            .foregroundStyle(Theme.inkPrimary).padding(Theme.Spacing.medium)
                            .background(Theme.canvasDeep).clipShape(Circle())
                    }
                    .accessibilityLabel("Back")
                }
            }
            .onChange(of: selectedA) { _, _ in fetchBoth() }
            .onChange(of: selectedB) { _, _ in fetchBoth() }
            .onChange(of: selectedC) { _, _ in fetchBoth() }
        }
    }

    private func fetchBoth() {
        guard let a = selectedA, let b = selectedB else { return }
        loading = true
        infoA = nil; infoB = nil; infoC = nil
        Task {
            async let qa = NetworkManager.shared.quickInfo(ticker: a.ticker)
            async let qb = NetworkManager.shared.quickInfo(ticker: b.ticker)
            infoA = await qa
            infoB = await qb
            if let c = selectedC {
                infoC = try? await NetworkManager.shared.quickInfo(ticker: c.ticker)
            }
            loading = false
        }
    }

    @ViewBuilder
    private func compareGrid(a: QuickInfo, b: QuickInfo, c: QuickInfo?) -> some View {
        let aUp = (a.changePercent ?? 0.0) >= 0
        let bUp = (b.changePercent ?? 0.0) >= 0
        let cUp = (c?.changePercent ?? 0.0) >= 0
        
        let a52: Double = {
            guard let h = a.week52High, let l = a.week52Low, (h - l) != 0 else { return 0 }
            return ((a.price ?? 0.0) - l) / (h - l) * 100
        }()
        let b52: Double = {
            guard let h = b.week52High, let l = b.week52Low, (h - l) != 0 else { return 0 }
            return ((b.price ?? 0.0) - l) / (h - l) * 100
        }()
        let c52: Double = {
            guard let c = c, let h = c.week52High, let l = c.week52Low, (h - l) != 0 else { return 0 }
            return ((c.price ?? 0.0) - l) / (h - l) * 100
        }()

        VStack(spacing: 0) {
            // Header row
            HStack(spacing: 0) {
                Text("").frame(maxWidth: .infinity)
                CompareHeaderCell(text: a.ticker)
                CompareHeaderCell(text: b.ticker)
                if let c = c {
                    CompareHeaderCell(text: c.ticker)
                }
            }
            .padding(.horizontal, Theme.screenPadding)

            GuillocheDivider().padding(.horizontal, Theme.screenPadding)

            // Rows
            Group {
                CompareRow(label: "PRICE", valA: (a.price ?? 0.0).inrFormatted, valB: (b.price ?? 0.0).inrFormatted, valC: c?.price?.inrFormatted)
                CompareRow(label: "TODAY", valA: (a.changePercent ?? 0.0).percentFormatted, valB: (b.changePercent ?? 0.0).percentFormatted, valC: c?.changePercent?.percentFormatted,
                           colorA: aUp ? Theme.bullGreen : Theme.bearRed, colorB: bUp ? Theme.bullGreen : Theme.bearRed, colorC: cUp ? Theme.bullGreen : Theme.bearRed)
                CompareRow(label: "P/E RATIO",
                           valA: a.peRatio.map { String(format: "%.1f", $0) } ?? "—",
                           valB: b.peRatio.map { String(format: "%.1f", $0) } ?? "—",
                           valC: c?.peRatio.map { String(format: "%.1f", $0) })
                CompareRow(label: "52W POSITION",
                           valA: String(format: "%.0f%%", a52),
                           valB: String(format: "%.0f%%", b52),
                           valC: c != nil ? String(format: "%.0f%%", c52) : nil)
                CompareRow(label: "52W HIGH", valA: a.week52High?.inrFormatted ?? "—", valB: b.week52High?.inrFormatted ?? "—", valC: c?.week52High?.inrFormatted)
                CompareRow(label: "52W LOW",  valA: a.week52Low?.inrFormatted ?? "—",  valB: b.week52Low?.inrFormatted ?? "—", valC: c?.week52Low?.inrFormatted)
                CompareRow(label: "SECTOR",   valA: a.sector ?? "—", valB: b.sector ?? "—", valC: c?.sector)
                if let sigA = a.signal, let sigB = b.signal {
                    CompareRow(label: "AI SIGNAL",
                               valA: sigA.rawValue, valB: sigB.rawValue, valC: c?.signal?.rawValue,
                               colorA: sigA.color, colorB: sigB.color, colorC: c?.signal?.color ?? Theme.inkPrimary)
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - Sub-views

private struct CompareHeaderCell: View {
    let text: String
    var body: some View {
        Text(text)
            .font(Theme.serialNumberFont(size: 13))
            .foregroundStyle(Theme.securityGold)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
    }
}

private struct CompareRow: View {
    let label: String
    let valA: String
    let valB: String
    var valC: String? = nil
    var colorA: Color = Theme.inkPrimary
    var colorB: Color = Theme.inkPrimary
    var colorC: Color = Theme.inkPrimary

    var body: some View {
        HStack(spacing: 0) {
            Text(label)
                .font(Theme.officialStampFont(size: 8))
                .foregroundStyle(Theme.inkSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .financeTerm(label)
            Text(valA)
                .font(Theme.serialNumberFont(size: 11))
                .foregroundStyle(colorA)
                .frame(maxWidth: .infinity, alignment: .center)
                .multilineTextAlignment(.center)
            Text(valB)
                .font(Theme.serialNumberFont(size: 11))
                .foregroundStyle(colorB)
                .frame(maxWidth: .infinity, alignment: .center)
                .multilineTextAlignment(.center)
            if let vc = valC {
                Text(vc)
                    .font(Theme.serialNumberFont(size: 11))
                    .foregroundStyle(colorC)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .multilineTextAlignment(.center)
            }
        }
        .padding(.vertical, 10)
        .overlay(Rectangle().fill(Theme.borderFine).frame(height: 0.5), alignment: .bottom)
    }
}

private struct StockPickerButton: View {
    let label: String
    let selected: StockEntry?
    @Binding var searchText: String
    let onSelect: (StockEntry) -> Void

    @State private var showPicker = false

    private var results: [StockEntry] {
        guard !searchText.isEmpty else { return Array(StockDatabase.all.prefix(20)) }
        let q = searchText.uppercased()
        return StockDatabase.all.filter { $0.ticker.contains(q) || $0.companyName.uppercased().contains(q) }
    }

    var body: some View {
        Button { showPicker = true } label: {
            VStack(alignment: .leading, spacing: 4) {
                Text(label).font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                Text(selected?.ticker ?? "Tap to select")
                    .font(Theme.serialNumberFont(size: 13))
                    .foregroundStyle(selected != nil ? Theme.inkPrimary : Theme.inkSecondary)
                if let s = selected {
                    Text(s.companyName).font(.caption2).foregroundStyle(Theme.inkTertiary).lineLimit(1)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(Theme.Spacing.standard)
            .banknoteCard()
        }
        .sheet(isPresented: $showPicker) {
            NavigationStack {
                ZStack {
                    Theme.canvas.ignoresSafeArea()
                    VStack(spacing: 0) {
                        HStack {
                            Image(systemName: "magnifyingglass").foregroundStyle(Theme.inkTertiary)
                            TextField("Search stock…", text: $searchText)
                                .autocorrectionDisabled().textInputAutocapitalization(.characters)
                                .foregroundStyle(Theme.inkPrimary)
                        }
                        .padding(Theme.Spacing.standard)
                        .background(Theme.inkPrimary.opacity(0.05))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .padding()

                        List(results) { entry in
                            Button {
                                onSelect(entry)
                                showPicker = false
                            } label: {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(entry.ticker).font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkPrimary)
                                    Text(entry.companyName).font(.caption).foregroundStyle(Theme.inkSecondary)
                                }
                                .padding(.vertical, 4)
                            }
                            .listRowBackground(Theme.canvas)
                        }
                        .listStyle(.plain)
                    }
                }
                .navigationTitle("Select \(label)")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { showPicker = false }.foregroundStyle(Theme.inkSecondary)
                    }
                }
            }
        }
    }
}
