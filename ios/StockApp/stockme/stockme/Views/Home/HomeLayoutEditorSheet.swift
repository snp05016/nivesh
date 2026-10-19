import SwiftUI

// MARK: - Home Layout Editor

struct HomeLayoutEditorSheet: View {
    @Environment(\.dismiss) var dismiss
    @State var currentOrder: [HomeSectionID]
    var onSave: ([HomeSectionID]) -> Void
    
    init(activeOrder: [HomeSectionID], onSave: @escaping ([HomeSectionID]) -> Void) {
        self._currentOrder = State(initialValue: activeOrder)
        self.onSave = onSave
    }
    
    var body: some View {
        NavigationStack {
            List {
                ForEach(currentOrder) { section in
                    HStack(spacing: Theme.Spacing.standard) {
                        Image(systemName: section.icon)
                            .foregroundStyle(Theme.securityGold)
                            .frame(width: 24)
                        Text(section.title)
                            .font(Theme.engravedSerif(size: 16, weight: .medium))
                            .foregroundStyle(Theme.inkPrimary)
                        Spacer()
                        Image(systemName: "line.3.horizontal")
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    .listRowBackground(Theme.canvasDeep)
                }
                .onMove { indices, newOffset in
                    currentOrder.move(fromOffsets: indices, toOffset: newOffset)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Theme.canvas)
            .navigationTitle("Edit Layout")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") { dismiss() }.buttonStyle(EKPressStyle())
                        .foregroundStyle(Theme.inkSecondary)
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Save") { HapticManager.selection()
                        onSave(currentOrder)
                        dismiss()
                    }
                    .font(.headline)
                    .foregroundStyle(Theme.securityGold)
                }
            }
        }
    }
}
