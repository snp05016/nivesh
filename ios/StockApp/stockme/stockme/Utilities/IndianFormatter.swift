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
}
