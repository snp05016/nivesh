import SwiftUI

struct StockTapActionSheetModifier: ViewModifier {
    let ticker: String
    let companyName: String?
    @Binding var isPresented: Bool
    let onAIAnalysis: (String) -> Void
    let onStockProfile: (String) -> Void

    func body(content: Content) -> some View {
        content
            .banknoteDialog(
                companyName ?? (ticker.isEmpty ? "Stock" : ticker),
                isPresented: $isPresented,
                message: ticker.isEmpty ? nil : "Choose how you want to explore \(ticker.uppercased())",
                buttons: dialogButtons
            )
    }

    private var dialogButtons: [BanknoteDialogButton] {
        var buttons: [BanknoteDialogButton] = []
        if !ticker.isEmpty {
            buttons.append(.init("Generate AI Analysis") {
                HapticManager.impact(.medium)
                onAIAnalysis(ticker)
            })
            buttons.append(.init("View Stock Info & Charts") {
                HapticManager.impact(.medium)
                onStockProfile(ticker)
            })
        }
        buttons.append(.cancel())
        return buttons
    }
}

extension View {
    func stockTapActionSheet(
        ticker: String,
        companyName: String? = nil,
        isPresented: Binding<Bool>,
        onAIAnalysis: @escaping (String) -> Void,
        onStockProfile: @escaping (String) -> Void
    ) -> some View {
        modifier(StockTapActionSheetModifier(
            ticker: ticker,
            companyName: companyName,
            isPresented: isPresented,
            onAIAnalysis: onAIAnalysis,
            onStockProfile: onStockProfile
        ))
    }
}
