import SwiftUI

/// `GET /api/v1/market/status`: open/closed from the backend's NSE holiday calendar.
struct MarketStatusDTO: Decodable {
    let isOpen: Bool
    let reason: String

    enum CodingKeys: String, CodingKey {
        case isOpen = "is_open", reason
    }
}

/// Home header pill. The server decides (holidays, special sessions); the local IST clock
/// is only the fallback when the status call fails.
struct MarketStatusStrip: View {
    @State private var server: MarketStatusDTO?

    private static let ist = TimeZone(identifier: "Asia/Kolkata")!

    private static let istFormatter: DateFormatter = {
        let f = DateFormatter()
        f.timeZone = ist
        f.dateFormat = "EEE, d MMM · HH:mm IST"
        return f
    }()

    /// Mon-Fri 09:15-15:30 IST, with no holiday knowledge.
    static func clockSaysOpen(at now: Date) -> Bool {
        let comps = Calendar(identifier: .gregorian).dateComponents(in: ist, from: now)
        guard let weekday = comps.weekday, weekday != 1, weekday != 7 else { return false }
        let totalMinutes = (comps.hour ?? 0) * 60 + (comps.minute ?? 0)
        return totalMinutes >= 555 && totalMinutes < 930
    }

    var body: some View {
        TimelineView(.periodic(from: .now, by: 60)) { context in
            let isOpen = server?.isOpen ?? Self.clockSaysOpen(at: context.date)
            let statusColor = isOpen ? Theme.bullGreen : Theme.bearRed
            let statusLabel = isOpen ? "NSE OPEN" : (server?.reason == "holiday" ? "NSE CLOSED · HOLIDAY" : "NSE CLOSED")
            HStack(spacing: Theme.Spacing.standard) {
                HStack(spacing: Theme.Spacing.small) {
                    Circle()
                        .fill(statusColor)
                        .frame(width: 6, height: 6)
                        .shadow(color: statusColor.opacity(0.5), radius: 3)
                    Text(statusLabel)
                        .font(Theme.officialStampFont(size: 9))
                        .tracking(1.2)
                        .foregroundStyle(statusColor)
                }
                .padding(.horizontal, Theme.Spacing.standard)
                .padding(.vertical, Theme.Spacing.medium)
                .background(statusColor.opacity(0.08))
                .cornerRadius(Theme.CornerRadius.small)
                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(statusColor.opacity(0.25), lineWidth: 0.5))

                Text(Self.istFormatter.string(from: context.date).uppercased())
                    .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                    .foregroundStyle(Theme.inkTertiary)

                Spacer()
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.bottom, Theme.Spacing.small)
        }
        .task {
            // Same cadence as the clock tick, so the pill flips within a minute of 09:15 / 15:30.
            while !Task.isCancelled {
                server = try? await NetworkManager.shared._fetchDecode(MarketStatusDTO.self, endpoint: "/api/v1/market/status")
                try? await Task.sleep(for: .seconds(60))
            }
        }
    }
}
