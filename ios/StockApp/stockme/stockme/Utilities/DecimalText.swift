// Utilities/DecimalText.swift
// Lossless number <-> text for editable numeric fields (IOSUI-05). printf "%g"
// keeps 6 significant digits, so 1234567 shares became "1.23457e+06" -> 1234570.

import Foundation

nonisolated enum DecimalText {
    /// Plain POSIX digits ("1234567", "0.5"): no grouping, no exponent, at most
    /// `maxFractionDigits` decimals, trailing zeros dropped.
    static func editable(_ v: Double, maxFractionDigits: Int) -> String {
        v.formatted(.number
            .grouping(.never)
            .precision(.fractionLength(0...maxFractionDigits))
            .locale(Locale(identifier: "en_US_POSIX")))
    }

    /// Parses user input: POSIX form first ("72.5"), then the locale's separators
    /// ("72,50" in de_DE, "1,00,000" in en_IN). nil when it is not a number.
    static func parse(_ s: String, locale: Locale = .current) -> Double? {
        let t = s.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty else { return nil }
        if let d = Double(t) { return d }
        var normalized = t
        if let g = locale.groupingSeparator, !g.isEmpty {
            normalized = normalized.replacingOccurrences(of: g, with: "")
        }
        if let dec = locale.decimalSeparator, dec != "." {
            normalized = normalized.replacingOccurrences(of: dec, with: ".")
        }
        return Double(normalized)
    }
}
