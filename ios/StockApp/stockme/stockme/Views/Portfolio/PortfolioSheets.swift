import SwiftUI

struct TaggingSheet: View {
    let ticker: String
    @ObservedObject var tagsManager: WatchlistTagsManager
    @Environment(\.dismiss) var dismiss
    @State private var newTag = ""

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                VStack(alignment: .leading, spacing: Theme.Spacing.large) {
                    Text("TAG \(ticker)")
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .foregroundStyle(Theme.inkSecondary)
                    
                    HStack {
                        TextField("New Tag (e.g. Tech)", text: $newTag)
                            .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                            .foregroundStyle(Theme.inkPrimary)
                        Button("Add") { HapticManager.selection()
                            tagsManager.addTag(newTag, to: ticker)
                            newTag = ""
                        }
                        .disabled(newTag.trimmingCharacters(in: .whitespaces).isEmpty)
                        .foregroundStyle(Theme.securityGold)
                    }
                    .padding(Theme.Spacing.card)
                    .banknoteCard()
                    
                    let currentTags = tagsManager.tags[ticker] ?? []
                    if !currentTags.isEmpty {
                        Text("CURRENT TAGS")
                            .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkSecondary)
                        
                        ForEach(currentTags, id: \.self) { tag in
                            HStack {
                                Text(tag).font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline)).foregroundStyle(Theme.inkPrimary)
                                Spacer()
                                Button(action: { HapticManager.selection(); tagsManager.removeTag(tag, from: ticker) }) {
                                    Image(systemName: "minus.circle.fill").foregroundStyle(Theme.bearRed)
                                }
                                .accessibilityLabel("Remove tag \(tag)")
                            }
                            .padding(Theme.Spacing.standard)
                            .banknoteCard()
                        }
                    }
                    Spacer()
                }
                .padding(Theme.Spacing.screen)
            }
            .navigationTitle("Tags")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }.buttonStyle(EKPressStyle())
                }
            }
        }
    }
}

struct AddHoldingSheet: View {
    let viewModel: PortfolioScreenViewModel
    let authManager: AuthManager
    @Environment(\.dismiss) private var dismiss

    @State private var searchText = ""
    @State private var selectedEntry: StockEntry? = nil
    @State private var sharesText = ""
    @State private var buyPriceText = ""
    @State private var purchaseDate = Date()
    @State private var notes = ""
    @State private var targetPriceText = ""
    @State private var errorText: String? = nil
    @State private var isAdding = false
    @State private var transactionType = "BUY"
    @State private var backendHits: [StockEntry] = []
    
    /// Backend /search hits first (listed tickers the bundled list lacks), then local matches.
    private var searchResults: [StockEntry] {
        let backendTickers = Set(backendHits.map(\.ticker))
        return backendHits + StockDatabase.search(searchText).filter { !backendTickers.contains($0.ticker) }
    }
    
    private var shares: Double { DecimalText.parse(sharesText) ?? 0 }
    private var buyPrice: Double { DecimalText.parse(buyPriceText) ?? 0 }
    private var canAdd: Bool { selectedEntry != nil && shares > 0 && buyPrice > 0 && !isAdding }
    
    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                VStack(spacing: Theme.Spacing.none) {
                    // Stock search
                    VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                        HStack {
                            Image(systemName: "magnifyingglass").foregroundStyle(Theme.inkTertiary)
                            if let entry = selectedEntry {
                                HStack(spacing: Theme.Spacing.tight) {
                                    Text(entry.ticker)
                                        .font(Theme.serialNumberFont(size: 14))
                                        .foregroundStyle(Theme.inkPrimary)
                                    Text(entry.companyName)
                                        .font(Theme.serialNumberFont(size: 12))
                                        .foregroundStyle(Theme.inkSecondary)
                                        .lineLimit(1)
                                    Spacer()
                                    Button {
                                        HapticManager.selection()
                                        selectedEntry = nil
                                        searchText = ""
                                    } label: {
                                        Image(systemName: "xmark.circle.fill")
                                            .foregroundStyle(Theme.inkTertiary)
                                    }
                                    .accessibilityLabel("Clear selection")
                                }
                            } else {
                                TextField("Search stock…", text: $searchText)
                                    .font(Theme.serialNumberFont(size: 14))
                                    .foregroundStyle(Theme.inkPrimary)
                                    .autocorrectionDisabled()
                                    .textInputAutocapitalization(.characters)
                            }
                        }
                        .padding(Theme.Spacing.standard)
                        .background(Theme.inkPrimary.opacity(0.05))
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.top, Theme.Spacing.card)
                        
                        if selectedEntry == nil && !searchResults.isEmpty {
                            List(searchResults) { entry in
                                Button {
                                    HapticManager.selection()
                                    selectedEntry = entry
                                    searchText = entry.ticker
                                } label: {
                                    HStack(spacing: Theme.Spacing.small) {
                                        StockIcon(ticker: entry.ticker, signal: nil)
                                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                            Text(entry.companyName)
                                                .font(Theme.engravedSerif(size: 13, weight: .bold))
                                                .foregroundStyle(Theme.inkPrimary)
                                            Text(entry.ticker)
                                                .font(Theme.serialNumberFont(size: 10))
                                                .foregroundStyle(Theme.inkSecondary)
                                        }
                                        Spacer()
                                        Image(systemName: "checkmark.circle")
                                            .foregroundStyle(Theme.securityGold)
                                    }
                                    .padding(.vertical, Theme.Spacing.small)
                                }
                                .listRowBackground(Theme.canvas)
                            }
                            .listStyle(.plain)
                            .frame(maxHeight: 220)
                        }
                    }
                    
                    // Trade type + inputs
                    VStack(spacing: Theme.Spacing.card) {
                        // BUY / SELL selector
                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text("TRANSACTION TYPE")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                            Picker("Transaction type", selection: $transactionType) {
                                Text("BUY").tag("BUY")
                                Text("SELL").tag("SELL")
                            }
                            .labelsHidden()
                            .pickerStyle(.segmented)
                            .tint(transactionType == "BUY" ? Theme.bullGreen : Theme.bearRed)
                        }

                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text("NUMBER OF SHARES")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                            TextField("e.g. 100", text: $sharesText)
                                .accessibilityLabel("Number of shares")
                                .keyboardType(.decimalPad)
                                .font(Theme.serialNumberFont(size: 16))
                                .foregroundStyle(Theme.inkPrimary)
                                .padding(Theme.Spacing.standard)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                        }

                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text(transactionType == "BUY" ? "BUY PRICE (₹)" : "SELL PRICE (₹)")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                            TextField("e.g. 1530.00", text: $buyPriceText)
                                .accessibilityLabel(transactionType == "BUY" ? "Buy price in rupees" : "Sell price in rupees")
                                .keyboardType(.decimalPad)
                                .font(Theme.serialNumberFont(size: 16))
                                .foregroundStyle(Theme.inkPrimary)
                                .padding(Theme.Spacing.standard)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                        }
                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text(transactionType == "BUY" ? "PURCHASE DATE" : "SALE DATE")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                            DatePicker("Trade date", selection: $purchaseDate, in: ...Date(), displayedComponents: .date)
                                .labelsHidden()
                                .accentColor(Theme.securityGold)
                                .padding(Theme.Spacing.medium)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .cornerRadius(Theme.CornerRadius.medium)
                        }
                        
                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text("TARGET PRICE (₹)")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                            TextField("optional...", text: $targetPriceText)
                                .accessibilityLabel("Target price in rupees, optional")
                                .keyboardType(.decimalPad)
                                .font(Theme.serialNumberFont(size: 16))
                                .foregroundStyle(Theme.inkPrimary)
                                .padding(Theme.Spacing.standard)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                        }
                        
                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text("NOTES / INVESTMENT REASON")
                                .font(Theme.officialStampFont(size: 9))
                                .foregroundStyle(Theme.inkSecondary)
                            TextField(transactionType == "BUY" ? "Why did you buy this?" : "Why did you sell?", text: $notes)
                                .font(Theme.serialNumberFont(size: 14))
                                .foregroundStyle(Theme.inkPrimary)
                                .padding(Theme.Spacing.standard)
                                .background(Theme.inkPrimary.opacity(0.05))
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                        }
                        
                        if let err = errorText {
                            Text(err)
                                .font(Theme.serialNumberFont(size: 12))
                                .foregroundStyle(Theme.bearRed)
                                .multilineTextAlignment(.center)
                        }
                        
                        Button {
                            HapticManager.selection()
                            // Enabled even when incomplete so the user sees why a trade can't be recorded.
                            if let problem = TradeEntryValidator.validate(
                                hasStock: selectedEntry != nil,
                                type: transactionType,
                                shares: shares,
                                price: buyPrice,
                                date: purchaseDate,
                                heldShares: viewModel.holdings.first(where: { $0.stock.ticker == selectedEntry?.ticker })?.shares
                            ) {
                                errorText = problem
                                return
                            }
                            guard let entry = selectedEntry else { return }
                            guard let user = authManager.currentUser else {
                                errorText = "Sign in to record trades."
                                return
                            }
                            isAdding = true
                            errorText = nil
                            Task {
                                do {
                                    try await viewModel.addHolding(
                                        userId: user.userId,
                                        ticker: entry.ticker,
                                        companyName: entry.companyName,
                                        shares: shares,
                                        buyPrice: buyPrice,
                                        purchaseDate: purchaseDate,
                                        notes: notes,
                                        targetPrice: DecimalText.parse(targetPriceText).flatMap { $0 > 0 ? $0 : nil },
                                        transactionType: transactionType
                                    )
                                    dismiss()
                                } catch {
                                    errorText = error.localizedDescription
                                }
                                isAdding = false
                            }
                        } label: {
                            HStack(spacing: Theme.Spacing.medium) {
                                if isAdding {
                                    ProgressView().tint(Theme.onAccent)
                                }
                                Text(isAdding ? "RECORDING…" : "RECORD \(transactionType)")
                                    .font(Theme.officialStampFont(size: 11))
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, Theme.Spacing.standard)
                            .background(canAdd ? Theme.securityGold : Theme.inkTertiary.opacity(0.3))
                            .foregroundStyle(Theme.onAccent)
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
                        }
                        .disabled(isAdding)
                    }
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, Theme.Spacing.large)
                    
                    Spacer()
                }
            }
            .navigationTitle("Record Trade")
            .navigationBarTitleDisplayMode(.inline)
            .task(id: searchText) {
                backendHits = []
                let q = searchText.trimmingCharacters(in: .whitespaces)
                guard selectedEntry == nil, !q.isEmpty else { return }
                try? await Task.sleep(nanoseconds: 350_000_000)
                guard !Task.isCancelled else { return }
                do {
                    let hits = try await NetworkManager.shared.searchStocks(q: q)
                    guard !Task.isCancelled else { return }
                    backendHits = hits
                } catch {
                    // Local StockDatabase matches stay; record the failure instead of hiding it.
                    guard !Task.isCancelled else { return }
                    GlobalErrorDiagnoser.shared.trackNetworkError(error, endpoint: "/api/v1/search")
                }
            }
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("Done") { HapticManager.selection()
                        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
                    }
                    .font(.subheadline.weight(.bold))
                    .foregroundStyle(Theme.securityGold)
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }.buttonStyle(EKPressStyle())
                        .font(Theme.serialNumberFont(size: 13))
                        .foregroundStyle(Theme.inkSecondary)
                }
            }
        }
    }
}

struct EditHoldingSheet: View {
        let holding: PortfolioHolding
        let viewModel: PortfolioScreenViewModel
        let authManager: AuthManager
        @Environment(\.dismiss) private var dismiss
        
        @State private var sharesText: String
        @State private var buyPriceText: String
        // Seeded text: an untouched field sends the stored value byte-exact.
        private let initialSharesText: String
        private let initialBuyPriceText: String
        @State private var errorText: String? = nil
        @State private var isSaving = false
        
        init(holding: PortfolioHolding, viewModel: PortfolioScreenViewModel, authManager: AuthManager) {
            self.holding = holding
            self.viewModel = viewModel
            self.authManager = authManager
            let sharesSeed = DecimalText.editable(holding.shares, maxFractionDigits: 4)
            let priceSeed = DecimalText.editable(holding.buyPrice, maxFractionDigits: 4)
            initialSharesText = sharesSeed
            initialBuyPriceText = priceSeed
            _sharesText = State(initialValue: sharesSeed)
            _buyPriceText = State(initialValue: priceSeed)
        }
        
        private var shares: Double {
            sharesText == initialSharesText ? holding.shares : DecimalText.parse(sharesText) ?? 0
        }
        private var buyPrice: Double {
            buyPriceText == initialBuyPriceText ? holding.buyPrice : DecimalText.parse(buyPriceText) ?? 0
        }
        private var canSave: Bool { shares > 0 && buyPrice > 0 && !isSaving }
        
        var body: some View {
            NavigationStack {
                ZStack {
                    Theme.canvas.ignoresSafeArea()
                    VStack(spacing: Theme.Spacing.small) {
                        // Read-only stock info
                        HStack(spacing: Theme.Spacing.card) {
                            StockIcon(ticker: holding.stock.ticker, signal: nil)
                            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                Text(holding.stock.companyName.uppercased())
                                    .font(Theme.engravedSerif(size: 15, weight: .bold))
                                    .foregroundStyle(Theme.inkPrimary)
                                Text(holding.stock.ticker)
                                    .font(Theme.serialNumberFont(size: 10))
                                    .foregroundStyle(Theme.inkSecondary)
                            }
                            Spacer()
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.top, Theme.Spacing.large)
                        
                        VStack(spacing: Theme.Spacing.card) {
                            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                                Text("NUMBER OF SHARES")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                                TextField("Shares", text: $sharesText)
                                    .keyboardType(holding.shares.rounded() == holding.shares ? .numberPad : .decimalPad)
                                    .font(Theme.serialNumberFont(size: 16))
                                    .foregroundStyle(Theme.inkPrimary)
                                    .padding(Theme.Spacing.standard)
                                    .background(Theme.inkPrimary.opacity(0.05))
                                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                            }
                            
                            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                                Text("BUY PRICE (₹)")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                                TextField("Buy Price", text: $buyPriceText)
                                    .keyboardType(.decimalPad)
                                    .font(Theme.serialNumberFont(size: 16))
                                    .foregroundStyle(Theme.inkPrimary)
                                    .padding(Theme.Spacing.standard)
                                    .background(Theme.inkPrimary.opacity(0.05))
                                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                            }
                            
                            if let err = errorText {
                                Text(err)
                                    .font(Theme.serialNumberFont(size: 12))
                                    .foregroundStyle(Theme.bearRed)
                                    .multilineTextAlignment(.center)
                            }
                            
                            Button {
                                HapticManager.selection()
                                guard let user = authManager.currentUser else { return }
                                isSaving = true
                                errorText = nil
                                Task {
                                    do {
                                        try await viewModel.updateHolding(
                                            userId: user.userId,
                                            ticker: holding.stock.ticker,
                                            shares: shares,
                                            buyPrice: buyPrice
                                        )
                                        dismiss()
                                    } catch {
                                        errorText = error.localizedDescription
                                    }
                                    isSaving = false
                                }
                            } label: {
                                HStack(spacing: Theme.Spacing.medium) {
                                    if isSaving {
                                        ProgressView().tint(Theme.onAccent)
                                    }
                                    Text(isSaving ? "SAVING…" : "SAVE CHANGES")
                                        .font(Theme.officialStampFont(size: 11))
                                }
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, Theme.Spacing.standard)
                                .background(canSave ? Theme.securityGold : Theme.inkTertiary.opacity(0.3))
                                .foregroundStyle(Theme.onAccent)
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
                            }
                            .disabled(!canSave)
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        
                        Spacer()
                    }
                }
                .navigationTitle("Edit Holding")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItemGroup(placement: .keyboard) {
                        Spacer()
                        Button("Done") { HapticManager.selection()
                            UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
                        }
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(Theme.securityGold)
                    }
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { dismiss() }.buttonStyle(EKPressStyle())
                            .font(Theme.serialNumberFont(size: 13))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }
            }
        }
}

struct NoteEditorSheet: View {
            let holding: PortfolioHolding
            @Binding var noteText: String
            let onSave: (String) -> Void
            @Environment(\.dismiss) var dismiss
            
            var body: some View {
                NavigationStack {
                    ZStack {
                        Theme.canvas.ignoresSafeArea()
                        VStack(spacing: Theme.Spacing.xSmall) {
                            // Header
                            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                                Text("अपना नोट / PERSONAL NOTE")
                                    .font(Theme.officialStampFont(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                                Text(holding.stock.companyName.uppercased())
                                    .font(Theme.engravedSerif(size: 18, weight: .bold))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, Theme.screenPadding)
                            
                            // Text editor
                            TextEditor(text: $noteText)
                                .font(Theme.engravedSerif(size: 15))
                                .foregroundStyle(Theme.inkPrimary)
                                .frame(minHeight: 150)
                                .padding(Theme.Spacing.card)
                                .background(Theme.canvasDeep)
                                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderSage, lineWidth: 1))
                                .padding(.horizontal, Theme.screenPadding)
                            
                            // Character count
                            Text("\(noteText.count)/280 characters")
                                .font(Theme.serialNumberFont(size: 11))
                                .foregroundStyle(noteText.count > 280 ? Theme.bearRed : Theme.inkTertiary)
                                .frame(maxWidth: .infinity, alignment: .trailing)
                                .padding(.horizontal, Theme.screenPadding)
                            
                            Spacer()
                        }
                        .padding(.top, Theme.screenPadding)
                    }
                    .navigationTitle("Note")
                    .navigationBarTitleDisplayMode(.inline)
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Cancel") { dismiss() }.buttonStyle(EKPressStyle())
                        }
                        ToolbarItem(placement: .confirmationAction) {
                            Button("Save") { HapticManager.selection()
                                onSave(String(noteText.prefix(280)))
                                dismiss()
                            }
                            .disabled(noteText.count > 280)
                        }
                    }
                }
            }
        }

struct AddWatchlistSheet: View {
    @Binding var searchText: String
    let onAdd: (StockEntry) -> Void
    @Environment(\.dismiss) private var dismiss
    
    private var results: [StockEntry] {
        if searchText.trimmingCharacters(in: .whitespaces).isEmpty { return StockDatabase.all }
        let q = searchText.uppercased()
        return StockDatabase.all.filter {
            $0.ticker.contains(q) || $0.companyName.uppercased().contains(q) || $0.sector.uppercased().contains(q)
        }
    }
    
    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                
                VStack(spacing: Theme.Spacing.none) {
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundStyle(Theme.inkTertiary)
                        TextField("Search stocks…", text: $searchText)
                            .font(Theme.serialNumberFont(size: 14))
                            .foregroundStyle(Theme.inkPrimary)
                            .autocorrectionDisabled()
                            .textInputAutocapitalization(.characters)
                    }
                    .padding(Theme.Spacing.standard)
                    .background(Theme.inkPrimary.opacity(0.05))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, Theme.Spacing.card)
                    .padding(.bottom, Theme.Spacing.medium)
                    
                    List(results) { entry in
                        Button {
                            HapticManager.selection()
                            onAdd(entry)
                        } label: {
                            HStack(spacing: Theme.Spacing.small) {
                                StockIcon(ticker: entry.ticker, signal: nil)
                                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                                    Text(entry.companyName)
                                        .font(Theme.engravedSerif(size: 14, weight: .bold))
                                        .foregroundStyle(Theme.inkPrimary)
                                    HStack(spacing: Theme.Spacing.tight) {
                                        Text(entry.ticker)
                                            .font(Theme.serialNumberFont(size: 10))
                                            .foregroundStyle(Theme.inkSecondary)
                                        Text("·")
                                            .foregroundStyle(Theme.inkTertiary)
                                        Text(entry.sector)
                                            .font(Theme.serialNumberFont(size: 10))
                                            .foregroundStyle(Theme.inkTertiary)
                                    }
                                }
                                Spacer()
                                Image(systemName: "plus.circle")
                                    .foregroundStyle(Theme.securityGold)
                            }
                            .padding(.vertical, Theme.Spacing.tight)
                        }
                        .listRowBackground(Theme.canvas)
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle("Add to Watchlist")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }.buttonStyle(EKPressStyle())
                        .font(Theme.serialNumberFont(size: 13))
                        .foregroundStyle(Theme.inkSecondary)
                }
            }
        }
    }
}
