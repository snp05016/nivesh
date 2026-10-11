import SwiftUI

// MARK: - IPO Calendar
//
// Month-grid view of IPO open/close/listing dates, backed by GET /api/ipo/calendar?month=YYYY-MM
// (falls back to filtering the already-fetched hub list when the dedicated endpoint isn't needed).

struct IPOCalendarView: View {
    @ObservedObject var vm: IPOListViewModel
    @State private var selectedMonth: Date = Date()
    @State private var selectedDay: Date? = nil

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                IPOCalendarMonthGrid(
                    ipos: vm.allIPOs,
                    selectedMonth: $selectedMonth,
                    selectedDay: $selectedDay
                )
                .padding(.horizontal, Theme.screenPadding)

                IPOCalendarDayList(
                    ipos: eventsForSelectedDay,
                    day: selectedDay
                )
                .padding(.horizontal, Theme.screenPadding)
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("IPO Calendar")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if vm.allIPOs.isEmpty { vm.fetchIPOs() }
        }
    }

    private var eventsForSelectedDay: [IPOListing] {
        guard let selectedDay else { return [] }
        return vm.allIPOs.filter { ipo in
            IPOCalendarMonthGrid.dates(for: ipo).contains { Calendar.current.isDate($0, inSameDayAs: selectedDay) }
        }
    }
}

// MARK: - Month Grid

struct IPOCalendarMonthGrid: View {
    let ipos: [IPOListing]
    @Binding var selectedMonth: Date
    @Binding var selectedDay: Date?

    private let columns = Array(repeating: GridItem(.flexible(), spacing: Theme.Spacing.small), count: 7)
    private let dayLabels = ["M", "T", "W", "T", "F", "S", "S"]

    /// Maps every day in the visible month to the IPO events landing on it.
    private var eventsByDay: [Date: [IPOListing]] {
        var map: [Date: [IPOListing]] = [:]
        for ipo in ipos {
            for date in Self.dates(for: ipo) {
                let day = Calendar.current.startOfDay(for: date)
                map[day, default: []].append(ipo)
            }
        }
        return map
    }

    private var daysInMonth: [Date?] {
        let cal = Calendar.current
        guard let range = cal.range(of: .day, in: .month, for: selectedMonth),
              let firstDay = cal.date(from: cal.dateComponents([.year, .month], from: selectedMonth)) else {
            return []
        }
        let weekdayOffset = (cal.component(.weekday, from: firstDay) + 5) % 7 // Monday = 0
        var days: [Date?] = Array(repeating: nil, count: weekdayOffset)
        for day in 1...range.count {
            if let d = cal.date(byAdding: .day, value: day - 1, to: firstDay) {
                days.append(d)
            }
        }
        return days
    }

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            IPOCalendarMonthHeader(selectedMonth: $selectedMonth)

            LazyVGrid(columns: columns, spacing: Theme.Spacing.small) {
                ForEach(dayLabels.indices, id: \.self) { idx in
                    Text(dayLabels[idx])
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .foregroundColor(Theme.inkTertiary)
                        .frame(maxWidth: .infinity)
                }
            }

            LazyVGrid(columns: columns, spacing: Theme.Spacing.small) {
                ForEach(daysInMonth.indices, id: \.self) { idx in
                    if let date = daysInMonth[idx] {
                        IPOCalendarDayCell(
                            date: date,
                            events: eventsByDay[Calendar.current.startOfDay(for: date)] ?? [],
                            isSelected: selectedDay.map { Calendar.current.isDate($0, inSameDayAs: date) } ?? false
                        )
                        .onTapGesture {
                            HapticManager.selection()
                            selectedDay = date
                        }
                    } else {
                        Color.clear.frame(minHeight: 36)
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    /// All dates an IPO occupies on the calendar (open, close, listing).
    static func dates(for ipo: IPOListing) -> [Date] {
        [ipo.openDate, ipo.closeDate, ipo.listingDate]
            .compactMap { $0 }
            .compactMap { DateFormatter.ipoDate.date(from: $0) }
    }
}

private struct IPOCalendarMonthHeader: View {
    @Binding var selectedMonth: Date

    var body: some View {
        HStack {
            Button {
                HapticManager.selection()
                changeMonth(-1)
            } label: {
                Image(systemName: "chevron.left")
                    .font(Theme.officialStampFont(size: 11))
                    .foregroundColor(Theme.inkSecondary)
            }
            .accessibilityLabel("Previous month")
            .buttonStyle(EKPressStyle())

            Spacer()

            Text(selectedMonth, format: .dateTime.month(.wide).year())
                .font(Theme.serialNumberFont(size: 13, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)

            Spacer()

            Button {
                HapticManager.selection()
                changeMonth(1)
            } label: {
                Image(systemName: "chevron.right")
                    .font(Theme.officialStampFont(size: 11))
                    .foregroundColor(Theme.inkSecondary)
            }
            .buttonStyle(EKPressStyle())
            .accessibilityLabel("Next month")
        }
    }

    private func changeMonth(_ delta: Int) {
        selectedMonth = Calendar.current.date(byAdding: .month, value: delta, to: selectedMonth) ?? selectedMonth
    }
}

private struct IPOCalendarDayCell: View {
    let date: Date
    let events: [IPOListing]
    let isSelected: Bool

    private var dotColor: Color? {
        guard let first = events.first else { return nil }
        switch first.status {
        case .open:     return Theme.bullGreen
        case .upcoming: return Theme.holdAmber
        case .closed:   return Theme.inkTertiary
        case .listed:   return Theme.securityGold
        case .none:     return nil
        }
    }

    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text("\(Calendar.current.component(.day, from: date))")
                .font(Theme.serialNumberFont(size: 12, relativeTo: .footnote))
                .foregroundColor(events.isEmpty ? Theme.inkTertiary : Theme.inkPrimary)

            if let dotColor {
                Circle().fill(dotColor).frame(width: 5, height: 5)
            } else {
                Circle().fill(Color.clear).frame(width: 5, height: 5)
            }
        }
        .frame(minHeight: 36)
        .frame(maxWidth: .infinity)
        .background(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                .fill(isSelected ? Theme.securityGoldLight : Color.clear)
        )
    }
}

// MARK: - Selected Day Event List

struct IPOCalendarDayList: View {
    let ipos: [IPOListing]
    let day: Date?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text(headerText)
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)

            if ipos.isEmpty {
                Text(day == nil ? "Tap a date to see IPO activity." : "No IPO activity on this date.")
                    .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                    .foregroundColor(Theme.inkTertiary)
            } else {
                ForEach(ipos) { ipo in
                    NavigationLink {
                        IPODetailView(seed: ipo)
                    } label: {
                        IPOCard(ipo: ipo)
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
        }
    }

    private var headerText: String {
        guard let day else { return "SELECT A DATE" }
        let formatter = DateFormatter()
        formatter.dateFormat = "d MMMM yyyy"
        return formatter.string(from: day).uppercased()
    }
}
