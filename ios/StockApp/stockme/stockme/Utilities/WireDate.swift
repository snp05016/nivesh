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

    /// "dd-MMM-yyyy" (e.g. "08-Oct-2026") as sent by POST /portfolio.
    static let ddMMMyyyy: DateFormatter = posix("dd-MMM-yyyy")

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
