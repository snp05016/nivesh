import SwiftUI

struct ManualTransactionEntrySheet: View {
    @Environment(\.dismiss) private var dismiss
    
    let userId: Int
    var onSave: (() -> Void)? = nil
    
    @State private var symbol: String = ""
    @State private var quantity: String = ""
    @State private var price: String = ""
    @State private var transactionType: TransactionType = .buy
    
    @State private var isSubmitting = false
    @State private var errorMessage: String? = nil
    
    enum TransactionType: String, CaseIterable {
        case buy = "BUY"
        case sell = "SELL"
    }
    
    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                
                ScrollView {
                    VStack(spacing: Theme.Spacing.xLarge) {
                        TypeSelectorSection(selectedType: $transactionType)
                        
                        InputFormSection(
                            symbol: $symbol,
                            quantity: $quantity,
                            price: $price
                        )
                        
                        if let errorMessage = errorMessage {
                            Text(errorMessage)
                                .foregroundColor(Theme.bearRed)
                                .font(.caption)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal)
                        }
                        
                        SubmitButtonSection(action: submitTransaction, isSubmitting: isSubmitting)
                    }
                    .padding(.vertical, Theme.Spacing.standard)
                }
            }
            .navigationTitle("Add Transaction")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") { HapticManager.selection(); 
                        HapticManager.selection()
                        dismiss()
                    }
                    .font(.subheadline)
                    .foregroundColor(Theme.inkSecondary)
                    .buttonStyle(EKPressStyle())
                }
            }
        }
    }
    
    private func submitTransaction() {
        guard let shares = Double(quantity), let buyPrice = Double(price), !symbol.isEmpty else {
            errorMessage = "Please enter valid values"
            HapticManager.error()
            return
        }
        
        isSubmitting = true
        errorMessage = nil
        HapticManager.selection()
        
        Task {
            do {
                try await NetworkManager.shared.addHolding(
                    userId: userId,
                    ticker: symbol.uppercased(),
                    companyName: symbol.uppercased(), // network layer expects this
                    shares: shares,
                    buyPrice: buyPrice,
                    purchaseDate: Date(),
                    notes: "Manual Entry",
                    targetPrice: 0.0,
                    transactionType: transactionType.rawValue
                )
                
                await MainActor.run {
                    HapticManager.success()
                    onSave?()
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isSubmitting = false
                    HapticManager.error()
                }
            }
        }
    }
}

struct TypeSelectorSection: View {
    @Binding var selectedType: ManualTransactionEntrySheet.TransactionType
    
    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            ForEach(ManualTransactionEntrySheet.TransactionType.allCases, id: \.self) { type in
                Button(action: { HapticManager.selection(); 
                    HapticManager.selection()
                    selectedType = type
                }) {
                    Text(type.rawValue)
                        .font(.subheadline.bold())
                        .fontDesign(.serif)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Theme.Spacing.standard)
                        .background(selectedType == type ? (type == .buy ? Theme.bullGreen : Theme.bearRed) : Theme.canvasDeep)
                        .foregroundColor(selectedType == type ? Theme.canvas : Theme.inkSecondary)
                        .cornerRadius(Theme.CornerRadius.medium)
                }
                .buttonStyle(EKPressStyle())
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct InputFormSection: View {
    @Binding var symbol: String
    @Binding var quantity: String
    @Binding var price: String
    
    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            InputRow(title: "Ticker Symbol", placeholder: "e.g. RELIANCE", text: $symbol)
            GuillocheDivider()
            InputRow(title: "Quantity", placeholder: "0", text: $quantity, keyboardType: .numberPad)
            GuillocheDivider()
            InputRow(title: "Average Price", placeholder: "₹ 0.00", text: $price, keyboardType: .decimalPad)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct InputRow: View {
    let title: String
    let placeholder: String
    @Binding var text: String
    var keyboardType: UIKeyboardType = .default
    
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(title)
                .font(.caption)
                .fontDesign(.serif)
                .foregroundColor(Theme.inkSecondary)
            
            TextField(placeholder, text: $text)
                .font(.body.monospaced())
                .foregroundColor(Theme.inkPrimary)
                .keyboardType(keyboardType)
        }
    }
}

struct SubmitButtonSection: View {
    let action: () -> Void
    var isSubmitting: Bool = false
    
    var body: some View {
        Button(action: action) { HapticManager.selection(); 
            Text(isSubmitting ? "Logging..." : "Confirm Transaction")
                .font(.headline)
                .fontDesign(.serif)
                .frame(maxWidth: .infinity)
                .padding(.vertical, Theme.Spacing.card)
                .background(isSubmitting ? Theme.inkSecondary : Theme.inkPrimary)
                .foregroundColor(Theme.canvas)
                .cornerRadius(Theme.CornerRadius.card)
        }
        .buttonStyle(EKPressStyle())
        .padding(.horizontal, Theme.screenPadding)
        .disabled(isSubmitting)
    }
}

struct ManualTransactionEntrySheet_Previews: PreviewProvider {
    static var previews: some View {
        ManualTransactionEntrySheet(userId: 1)
    }
}
