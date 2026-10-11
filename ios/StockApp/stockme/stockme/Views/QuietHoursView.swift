import SwiftUI

struct QuietHoursView: View {
    @AppStorage("nivesh_quietHoursStart") private var startSeconds: Double = 79200
    @AppStorage("nivesh_quietHoursEnd") private var endSeconds: Double = 25200
    @AppStorage("nivesh_quietHoursDays") private var quietDaysData: Data = Data()
    @State private var activeDays: Set<Int> = [0, 1, 2, 3, 4, 5, 6]

    private let dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    private var startDate: Binding<Date> {
        Binding(get: {
            Calendar.current.startOfDay(for: Date()).addingTimeInterval(startSeconds)
        }, set: {
            let comps = Calendar.current.dateComponents([.hour, .minute], from: $0)
            startSeconds = Double((comps.hour ?? 22) * 3600 + (comps.minute ?? 0) * 60)
        })
    }

    private var endDate: Binding<Date> {
        Binding(get: {
            Calendar.current.startOfDay(for: Date()).addingTimeInterval(endSeconds)
        }, set: {
            let comps = Calendar.current.dateComponents([.hour, .minute], from: $0)
            endSeconds = Double((comps.hour ?? 7) * 3600 + (comps.minute ?? 0) * 60)
        })
    }

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .twoHundred)

            List {
                Section {
                    DatePicker("From", selection: startDate, displayedComponents: .hourAndMinute)
                        .font(Theme.engravedSerif(size: 14))
                        .tint(Theme.securityGold)
                    DatePicker("Until", selection: endDate, displayedComponents: .hourAndMinute)
                        .font(Theme.engravedSerif(size: 14))
                        .tint(Theme.securityGold)
                } header: {
                    Text("QUIET HOURS WINDOW").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                }

                Section {
                    HStack(spacing: Theme.Spacing.small) {
                        ForEach(0..<7, id: \.self) { day in
                            Button {
                                HapticManager.selection()
                                if activeDays.contains(day) {
                                    activeDays.remove(day)
                                } else {
                                    activeDays.insert(day)
                                }
                                saveDays()
                            } label: {
                                Text(dayNames[day])
                                    .font(Theme.serialNumberFont(size: 11))
                                    .foregroundStyle(activeDays.contains(day) ? Theme.canvas : Theme.inkSecondary)
                                    .frame(width: 38, height: 38)
                                    .background(
                                        Circle()
                                            .fill(activeDays.contains(day) ? Theme.securityGold : Theme.surfaceElevated)
                                    )
                            }
                            .buttonStyle(EKPressStyle())
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Spacing.small)
                } header: {
                    Text("ACTIVE DAYS").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Quiet Hours")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .onAppear { loadDays() }
    }

    private func loadDays() {
        if let decoded = try? JSONDecoder().decode(Set<Int>.self, from: quietDaysData) {
            activeDays = decoded
        }
    }

    private func saveDays() {
        if let encoded = try? JSONEncoder().encode(activeDays) {
            quietDaysData = encoded
        }
    }
}
