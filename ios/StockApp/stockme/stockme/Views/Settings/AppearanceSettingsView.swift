import SwiftUI

struct AppearanceSettingsView: View {
    @AppStorage("selectedTheme") private var selectedThemeRaw = AppTheme.darkImmersive.rawValue
    @AppStorage("darkMode") private var darkMode = false
    @AppStorage("nivesh_fontSize") private var fontSize = "Standard"
    @AppStorage("nivesh_layoutDensity") private var layoutDensity = "Standard"
    @AppStorage("nivesh_defaultChartRange") private var defaultChartRange = "1M"
    @AppStorage("nivesh_reduceAnimations") private var reduceAnimations = false
    @AppStorage("nivesh_showHindiLabels") private var showHindiLabels = true

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .fifty)
            
            List {
                Section {
                    ForEach(AppTheme.allCases, id: \.self) { theme in
                        HStack {
                            Circle().fill(theme.swatchColor).frame(width: 24, height: 24)
                            Text(theme.displayName).font(Theme.engravedSerif(size: 14)).foregroundStyle(Theme.inkPrimary)
                            Spacer()
                            if theme.rawValue == selectedThemeRaw {
                                Image(systemName: "checkmark").foregroundStyle(Theme.securityGold)
                            }
                        }
                        .contentShape(Rectangle())
                        .onTapGesture {
                            HapticManager.impact(.medium)
                            withAnimation(.spring(response: 0.4, dampingFraction: 0.72)) {
                                selectedThemeRaw = theme.rawValue
                                ThemeManager.shared.current = theme
                            }
                        }
                    }

                    ToggleNoteRow(icon: "moon.fill", color: .indigo, title: "Dark Inks", isOn: $darkMode)
                    PickerNoteRow(icon: "textformat.size", color: Theme.inkSecondary, title: "Font Size", selection: $fontSize, options: ["Small", "Standard", "Large"])
                    PickerNoteRow(icon: "rectangle.3.group", color: Theme.inkSecondary, title: "Layout Density", selection: $layoutDensity, options: ["Compact", "Standard", "Spacious"])
                    PickerNoteRow(icon: "chart.xyaxis.line", color: Theme.securityGold, title: "Default Chart Range", selection: $defaultChartRange, options: ["1M", "3M", "6M", "1Y"])
                    ToggleNoteRow(icon: "hare", color: Theme.inkSecondary, title: "Reduce Animations", isOn: $reduceAnimations)
                    ToggleNoteRow(icon: "character.bubble", color: Theme.inkSecondary, title: "Show Hindi Labels", isOn: $showHindiLabels)
                } header: {
                    Text("APPEARANCE").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Appearance")
        .navigationBarTitleDisplayMode(.inline)
    }
}
