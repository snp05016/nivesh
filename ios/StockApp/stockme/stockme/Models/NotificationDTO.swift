import Foundation

// MARK: - Notification DTO

struct NotificationDTO: Codable, Identifiable {
    let id: Int
    let type: String
    let title: String
    let body: String
    let isRead: Bool
    let actionUrl: String?
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id, type, title, body
        case isRead = "is_read"
        case actionUrl = "action_url"
        case createdAt = "created_at"
    }

    var typeIcon: String {
        switch type.lowercased() {
        case "ai_alert": return "brain.head.profile"
        case "earnings": return "chart.bar.doc.horizontal"
        case "system": return "bell.badge"
        default: return "bell"
        }
    }

    var typeColor: String {
        switch type.lowercased() {
        case "ai_alert": return "securityGold"
        case "earnings": return "bullGreen"
        case "system": return "inkSecondary"
        default: return "inkTertiary"
        }
    }

    private static let display: DateFormatter = {
        let f = DateFormatter()
        f.dateStyle = .short
        f.timeStyle = .short
        return f
    }()

    var formattedTime: String {
        guard let raw = createdAt else { return "" }
        guard let date = WireDate.parseISO(raw) else { return raw }
        return Self.display.string(from: date)
    }
}

// MARK: - Preference DTO

struct PreferenceDTO: Codable {
    let userId: Int
    let theme: String
    let alertsEnabled: Bool

    enum CodingKeys: String, CodingKey {
        case theme
        case userId = "user_id"
        case alertsEnabled = "alerts_enabled"
    }
}

// MARK: - Preferences Update Request

struct PreferenceUpdateRequest: Codable {
    let theme: String?
    let alertsEnabled: Bool?

    enum CodingKeys: String, CodingKey {
        case theme
        case alertsEnabled = "alerts_enabled"
    }
}
