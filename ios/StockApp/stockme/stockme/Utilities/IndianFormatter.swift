import Foundation

struct IndianFormatter {
    static var useAbsoluteFormat: Bool {
        UserDefaults.standard.string(forKey: "currencyDisplay") == "Absolute"
    }

    private static let priceFormatter: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.currencySymbol = "₹"
        f.locale = Locale(identifier: "en_IN")
        f.maximumFractionDigits = 2
        return f
    }()

    /// Grouped en_IN decimal with exactly 2 fraction digits and no currency symbol (index points).
    private static let pointsFormatter: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .decimal
        f.locale = Locale(identifier: "en_IN")
        f.minimumFractionDigits = 2
        f.maximumFractionDigits = 2
        return f
    }()

    /// Grouped en_IN whole number, for large crore figures ("1,90,000 Cr").
    private static let wholeFormatter: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .decimal
        f.locale = Locale(identifier: "en_IN")
        f.maximumFractionDigits = 0
        return f
    }()

    private static let percentFormatter: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .percent
        f.locale = Locale(identifier: "en_IN")
        f.maximumFractionDigits = 2
        f.positivePrefix = "+"
        return f
    }()

    /// Rounds to 2 decimals and folds -0 into 0, so a unit is chosen on the value actually printed.
    private static func r2(_ value: Double) -> Double {
        let x = (value * 100).rounded() / 100
        return x == 0 ? 0 : x
    }

    static func price(_ value: Double) -> String {
        priceFormatter.string(from: NSNumber(value: value)) ?? "₹0.00"
    }

    /// Missing quote renders as an em dash, never as ₹0.00.
    static func price(_ value: Double?) -> String {
        guard let value else { return "—" }
        return price(value)
    }

    /// Price with an explicit sign before the symbol: "+₹12.00" / "-₹12.00".
    static func signedPrice(_ value: Double) -> String {
        (value < 0 ? "-" : "+") + price(abs(value))
    }

    /// Index levels are points, not rupees: 22450.5 -> "22,450.50".
    static func points(_ value: Double) -> String {
        pointsFormatter.string(from: NSNumber(value: value)) ?? String(format: "%.2f", value)
    }

    /// Signed index-point change: "+120.50" / "-120.50".
    static func signedPoints(_ value: Double) -> String {
        (value < 0 ? "-" : "+") + points(abs(value))
    }

    /// Plain quantities such as share volume, on the Indian scale with no ₹:
    /// 12_300_000 -> "1.23 Cr", 456_000 -> "4.56 L", 12_345 -> "12,345".
    static func count(_ value: Double) -> String {
        guard value.isFinite else { return "—" }
        let absVal = abs(value)
        let sign = value < 0 ? "-" : ""
        let lakhs = r2(absVal / 1_00_000)
        if lakhs >= 100 { return "\(sign)\(String(format: "%.2f", r2(absVal / 1_00_00_000))) Cr" }
        if absVal >= 1_00_000 { return "\(sign)\(String(format: "%.2f", lakhs)) L" }
        return wholeFormatter.string(from: NSNumber(value: value)) ?? String(format: "%.0f", value)
    }

    static func percent(_ value: Double) -> String {
        let val = r2(value) / 100
        return percentFormatter.string(from: NSNumber(value: val)) ?? "0.00%"
    }

    static func priceWithoutSymbol(_ value: Double) -> String {
        price(value).replacingOccurrences(of: "₹", with: "").trimmingCharacters(in: .whitespaces)
    }

    static func priceCompact(_ value: Double) -> String {
        formatLakhsCrores(value)
    }

    /// Formats a large number using Indian scale: Crores > Lakhs > plain.
    /// ALL currency output from views MUST go through this function.
    /// Never outputs Millions or Billions.
    static func formatLakhsCrores(_ value: Double) -> String {
        if useAbsoluteFormat { return price(value) }
        let absVal = abs(value)
        let sign = value < 0 ? "-" : ""
        // Pick the unit on the rounded value: 99,99,999.6 prints "₹1.00 Cr", never "₹100.00 L".
        let lakhs = r2(absVal / 1_00_000)
        if lakhs >= 100 { // 1 Crore = 1,00,00,000
            let crores = absVal / 1_00_00_000
            if (crores * 10).rounded() / 10 >= 1000 {
                return "\(sign)₹\(wholeFormatter.string(from: NSNumber(value: crores)) ?? String(format: "%.0f", crores)) Cr"
            } else if r2(crores) >= 100 {
                return "\(sign)₹\(String(format: "%.1f", crores)) Cr"
            } else {
                return "\(sign)₹\(String(format: "%.2f", r2(crores))) Cr"
            }
        } else if absVal >= 1_00_000 { // 1 Lakh = 1,00,000
            return "\(sign)₹\(String(format: "%.2f", lakhs)) L"
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
        let x = r2(value)
        return "\(x >= 0 ? "+" : "")\(String(format: "%.2f", x))%"
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
