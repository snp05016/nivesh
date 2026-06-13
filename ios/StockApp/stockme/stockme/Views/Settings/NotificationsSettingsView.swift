import SwiftUI

struct NotificationsSettingsView: View {
    @AppStorage("pushNotifications") private var pushNotifications = true
    @AppStorage("nivesh_signalChangeAlerts") private var signalChangeAlerts = false
    @AppStorage("morningBriefTime") private var morningBriefTime: Double = 0 // storing seconds from midnight
    @AppStorage("notificationSound") private var notificationSound = "Default"

    private var morningBriefDate: Binding<Date> {
        Binding(
            get: {
                let calendar = Calendar.current
                let startOfDay = calendar.startOfDay(for: Date())
                return startOfDay.addingTimeInterval(morningBriefTime)
            },
            set: { newDate in
                let calendar = Calendar.current
                let components = calendar.dateComponents([.hour, .minute], from: newDate)
                let hours = components.hour ?? 0
                let minutes = components.minute ?? 0
                morningBriefTime = Double(hours * 3600 + minutes * 60)
            }
        )
    }

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .fifty)
            
            List {
                Section {
                    ToggleNoteRow(icon: "bell.badge", color: Theme.bearRed, title: "Signal Change Alerts", isOn: $signalChangeAlerts)
                    DatePickerNoteRow(icon: "clock.fill", color: Theme.securityGold, title: "Morning Brief Time", selection: morningBriefDate)
                    PickerNoteRow(icon: "speaker.wave.2", color: Theme.bearRed, title: "Notification Sound", selection: $notificationSound, options: ["Default", "rupee_rustle.mp3"])
                    NavigationLink(destination: QuietHoursView()) {
                        HStack {
                            SettingIcon(icon: "moon.zzz", color: Theme.inkSecondary)
                            Text("QUIET HOURS")
                                .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                            Spacer()
                        }
                        .padding(.vertical, Theme.Spacing.standard)
                    }
                } header: {
                    Text("NOTIFICATIONS").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.inline)
    }
}
