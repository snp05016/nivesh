import SwiftUI

// Shared settings row components — used by SettingsScreen and Settings/ sub-views

struct SettingIcon: View {
    let icon: String
    let color: Color

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(color.opacity(0.05))
                .frame(width: 32, height: 32)
            Image(systemName: icon)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(color.opacity(0.6))
        }
        .padding(.trailing, Theme.Spacing.standard)
    }
}

struct ToggleNoteRow: View {
    let icon: String
    let color: Color
    let title: String
    @Binding var isOn: Bool

    var body: some View {
        HStack {
            SettingIcon(icon: icon, color: color)
            Toggle(isOn: $isOn) {
                Text(title.uppercased())
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(Theme.inkPrimary)
            }
            .tint(Theme.securityGold)
        }
        .padding(.vertical, Theme.Spacing.standard)
        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
    }
}

struct PickerNoteRow: View {
    let icon: String
    let color: Color
    let title: String
    @Binding var selection: String
    let options: [String]

    var body: some View {
        HStack {
            SettingIcon(icon: icon, color: color)
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(Theme.inkPrimary)
            Spacer()
            Picker("", selection: $selection) {
                ForEach(options, id: \.self) { option in
                    Text(option).tag(option)
                }
            }
            .tint(Theme.inkSecondary)
        }
        .padding(.vertical, Theme.Spacing.standard)
        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
    }
}

struct DatePickerNoteRow: View {
    let icon: String
    let color: Color
    let title: String
    @Binding var selection: Date

    var body: some View {
        HStack {
            SettingIcon(icon: icon, color: color)
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(Theme.inkPrimary)
            Spacer()
            DatePicker("", selection: $selection, displayedComponents: .hourAndMinute)
                .labelsHidden()
                .tint(Theme.securityGold)
        }
        .padding(.vertical, Theme.Spacing.standard)
        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
    }
}
