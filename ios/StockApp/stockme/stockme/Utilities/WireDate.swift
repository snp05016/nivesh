// Utilities/WireDate.swift
// Shared, locale-pinned formatters for dates on the wire. Building a
// DateFormatter is expensive, so hot paths (chart marks, sorts, decoding)
// reuse these instead of allocating one per access.

import Foundation

nonisolated enum WireDate {
    /// "yyyy-MM-dd" in the device time zone (matches how the app has always
    /// interpreted backend day strings), Gregorian + POSIX so a Buddhist or
    /// Japanese calendar device still parses and formats the wire year.
    static let dayFormatter: DateFormatter = posix("yyyy-MM-dd")

    /// "dd-MMM-yyyy" (e.g. "08-Oct-2026"): legacy purchase_date rows. New rows
    /// are sent as "yyyy-MM-dd" (the format backend portfolio_charts parses).
    static let ddMMMyyyy: DateFormatter = posix("dd-MMM-yyyy")

    /// "yyyy-MM-dd" in India Standard Time, for IST-keyed backend queries.
    static let istDayFormatter: DateFormatter = {
        let f = posix("yyyy-MM-dd")
        f.timeZone = TimeZone(identifier: "Asia/Kolkata")
        return f
    }()

    private static let isoFractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
    private static let isoPlain = ISO8601DateFormatter()

    /// Parses a backend ISO-8601 timestamp. Accepts microseconds (Python
    /// isoformat) and a missing offset, which the backend means as UTC.
    static func parseISO(_ s: String) -> Date? {
        var t = s.replacingOccurrences(of: #"(\.\d{3})\d+"#, with: "$1", options: .regularExpression)
        if !t.hasSuffix("Z"), t.range(of: #"[+-]\d{2}:?\d{2}$"#, options: .regularExpression) == nil {
            t += "Z"
        }
        return isoFractional.date(from: t) ?? isoPlain.date(from: t)
    }

    /// Parses a backend day string; tolerates a trailing time ("2026-10-08T00:00:00").
    static func day(_ s: String) -> Date? {
        dayFormatter.date(from: String(s.prefix(10)))
    }

    /// Formats a date as a "yyyy-MM-dd" key.
    static func dayKey(_ d: Date) -> String {
        dayFormatter.string(from: d)
    }

    private static func posix(_ format: String) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.calendar = Calendar(identifier: .gregorian)
        f.timeZone = TimeZone.current
        f.dateFormat = format
        return f
    }
}

/// A wire row whose `parsedDate` is `.distantPast` when its date string was unparseable.
protocol WireDated {
    var parsedDate: Date { get }
}

extension Array where Element: WireDated {
    /// Drops rows with an unparseable date instead of plotting them at a bogus x position.
    var droppingUndated: [Element] { filter { $0.parsedDate != .distantPast } }
}
