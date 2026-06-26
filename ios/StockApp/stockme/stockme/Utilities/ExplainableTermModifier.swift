import SwiftUI

struct ExplainableTermModifier: ViewModifier {
    let term: String
    @State private var showSheet = false

    func body(content: Content) -> some View {
        if let entry = FinanceTerms.shared.lookup(term) {
            Button {
    HapticManager.selection()
                HapticManager.selection()
                showSheet = true
            } label: {
                content
                    .underline(true, color: Theme.securityGold.opacity(0.5))
            }
            .buttonStyle(EKPressStyle())
            .accessibilityHint("Tap to view definition")
            .sheet(isPresented: $showSheet) {
                TermDefinitionSheet(entry: entry)
            }
        } else {
            content
        }
    }
}

extension View {
    public func explainableTerm(_ term: String) -> some View {
        modifier(ExplainableTermModifier(term: term))
    }

    @ViewBuilder
    public func explainableTermOptional(_ term: String?) -> some View {
        if let term, FinanceTerms.shared.lookup(term) != nil {
            modifier(ExplainableTermModifier(term: term))
        } else {
            self
        }
    }
}
