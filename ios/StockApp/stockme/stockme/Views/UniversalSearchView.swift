import SwiftUI

struct UniversalSearchView: View {
    @StateObject private var viewModel = UniversalSearchViewModel()
    
    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(Theme.inkSecondary)
            
            TextField("Search stocks, indices, or ask AI...", text: $viewModel.searchQuery)
                .font(.body.monospaced())
                .foregroundColor(Theme.inkPrimary)
                .tint(Theme.inkPrimary)
            
            if !viewModel.searchQuery.isEmpty {
                Button(action: { HapticManager.selection(); 
                    viewModel.searchQuery = ""
                    HapticManager.selection()
                }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(Theme.inkTertiary)
                }
                .buttonStyle(EKPressStyle())
                .accessibilityLabel("Clear search")
            }
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct UniversalSearchView_Previews: PreviewProvider {
    static var previews: some View {
        UniversalSearchView()
    }
}
