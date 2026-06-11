import SwiftUI

struct StockTapActionSheetModifier: ViewModifier {
    let ticker: String
    let companyName: String?
    @Binding var isPresented: Bool
    let onAIAnalysis: (String) -> Void
    let onStockProfile: (String) -> Void

    func body(content: Content) -> some View {
        content
            .confirmationDialog(
                companyName ?? (ticker.isEmpty ? "Stock" : ticker),
                isPresented: $isPresented,
                titleVisibility: .visible
            ) {
                if !ticker.isEmpty {
                    Button("✦ Generate AI Analysis") {
                        HapticManager.impact(.medium)
                        onAIAnalysis(ticker)
                    }
                    Button("◉ View Stock Info & Charts") {
                        HapticManager.impact(.medium)
                        onStockProfile(ticker)
                    }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                if !ticker.isEmpty {
                    Text("Choose how you want to explore \(ticker.uppercased())")
                }
            }
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
