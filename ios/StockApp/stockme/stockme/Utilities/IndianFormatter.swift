import Foundation

struct IndianFormatter {
    private static let priceFormatter: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.currencySymbol = "₹"
        f.locale = Locale(identifier: "en_IN")
        f.maximumFractionDigits = 2
        return f
    }()

    private static let percentFormatter: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .percent
        f.maximumFractionDigits = 2
        f.positivePrefix = "+"
        return f
    }()

    static func price(_ value: Double) -> String {
        priceFormatter.string(from: NSNumber(value: value)) ?? "₹0.00"
    }

    static func percent(_ value: Double) -> String {
        let val = value / 100
        return percentFormatter.string(from: NSNumber(value: val)) ?? "0.00%"
    }

    static func priceWithoutSymbol(_ value: Double) -> String {
        price(value).replacingOccurrences(of: "₹", with: "").trimmingCharacters(in: .whitespaces)
    }

    static func priceCompact(_ value: Double) -> String {
        let absVal = abs(value)
        let sign = value < 0 ? "-" : ""

        if absVal >= 10_000_000 {
            return "₹\(sign)\(String(format: "%.2f", absVal / 10_000_000))Cr"
        } else if absVal >= 100_000 {
            return "₹\(sign)\(String(format: "%.2f", absVal / 100_000))L"
        } else {
            return price(value)
        }
    }

    /// Formats a large number using Indian scale: Crores > Lakhs > plain.
    /// ALL currency output from views MUST go through this function.
    /// Never outputs Millions or Billions.
    static func formatLakhsCrores(_ value: Double) -> String {
        let absVal = abs(value)
        let sign = value < 0 ? "-" : ""
        if absVal >= 1_00_00_000 { // 1 Crore = 1,00,00,000
            let crores = absVal / 1_00_00_000
            if crores >= 1000 {
                return "₹\(sign)\(String(format: "%.0f", crores)) Cr"
            } else if crores >= 100 {
                return "₹\(sign)\(String(format: "%.1f", crores)) Cr"
            } else {
                return "₹\(sign)\(String(format: "%.2f", crores)) Cr"
            }
        } else if absVal >= 1_00_000 { // 1 Lakh = 1,00,000
            let lakhs = absVal / 1_00_000
            return "₹\(sign)\(String(format: "%.2f", lakhs)) L"
        } else {
            return price(value)
        }
    }

    /// Same as formatLakhsCrores but without the ₹ symbol, for use inside compound labels.
    static func lakhsCroresNoSymbol(_ value: Double) -> String {
        formatLakhsCrores(value).replacingOccurrences(of: "₹", with: "").trimmingCharacters(in: .whitespaces)
    }

    /// Formats a percentage delta with sign, 2 decimal places.
    static func delta(_ value: Double) -> String {
        let sign = value >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.2f", value))%"
    }

    /// Elapsed time label for timestamps (e.g. "2 minutes ago").
    static func elapsed(from date: Date) -> String {
        let seconds = Int(Date().timeIntervalSince(date))
        if seconds < 60 { return "just now" }
        let minutes = seconds / 60
        if minutes < 60 { return "\(minutes) \(minutes == 1 ? "minute" : "minutes") ago" }
        let hours = minutes / 60
        if hours < 24 { return "\(hours) \(hours == 1 ? "hour" : "hours") ago" }
        let days = hours / 24
        return "\(days) \(days == 1 ? "day" : "days") ago"
    }
}
