import XCTest

/// Spec 10.3: no string literal in Views/Research/*.swift may phrase anything as a call
/// on a stock or as an accuracy claim, and no bull/bear colour may appear there.
/// Server strings (labels, display values, tier texts, disclaimers) are not literals in
/// these files, so they are outside this check by construction.
final class ResearchCopyLexiconTests: XCTestCase {

    /// Banned anywhere inside a literal, case-insensitive (so "threshold" fails on "hold").
    private static let bannedSubstrings = [
        "buy", "sell", "hold", "target", "signal", "bullish", "bearish", "accuracy",
        "confidence", "recommend", "coverage-checked", "of 100", "% chance",
    ]
    /// Banned as whole words only ("operating" is fine, "rating" is not).
    private static let bannedWords = ["call", "calls", "pick", "picks", "rating", "ratings"]
    private static let bannedColours = ["bullGreen", "bearRed", "signalEmerald", "signalRuby", "dataPositive", "dataNegative"]

    /// ios/StockApp/stockme/stockme/Views/Research, reached from this file.
    private static let researchDir = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // stockmeTests
        .deletingLastPathComponent()   // stockme (project folder)
        .appendingPathComponent("stockme/Views/Research", isDirectory: true)

    private func sources() throws -> [(name: String, text: String)] {
        let files = try FileManager.default.contentsOfDirectory(at: Self.researchDir, includingPropertiesForKeys: nil)
            .filter { $0.pathExtension == "swift" }
        return try files.map { ($0.lastPathComponent, try String(contentsOf: $0, encoding: .utf8)) }
    }

    func testNoBannedWordsInStringLiterals() throws {
        let files = try sources()
        XCTAssertGreaterThanOrEqual(files.count, 5, "expected the Research views in \(Self.researchDir.path)")
        var literalCount = 0
        for file in files {
            for literal in Self.stringLiterals(in: file.text) {
                literalCount += 1
                let lower = literal.lowercased()
                for word in Self.bannedSubstrings where lower.contains(word) {
                    XCTFail("\(file.name): \"\(literal)\" contains \"\(word)\"")
                }
                let words = Set(lower.split { !$0.isLetter }.map(String.init))
                for word in Self.bannedWords where words.contains(word) {
                    XCTFail("\(file.name): \"\(literal)\" contains the word \"\(word)\"")
                }
            }
        }
        XCTAssertGreaterThan(literalCount, 50, "the literal scanner found almost nothing")
    }

    func testNoBullOrBearColours() throws {
        for file in try sources() {
            for colour in Self.bannedColours where file.text.contains(colour) {
                XCTFail("\(file.name) uses \(colour)")
            }
        }
    }

    func testScannerSkipsCommentsAndInterpolatedCode() {
        let src = """
        // a "buy" in a comment
        let a = "Plain \\(model.holdAmber) text" /* "sell" */
        let b = "Escaped \\" quote"
        """
        XCTAssertEqual(Self.stringLiterals(in: src), ["Plain  text", "Escaped \\\" quote"])
    }

    /// Contents of every string literal (single-line, multi-line and raw), with
    /// comments skipped and the code inside `\( ... )` interpolations removed.
    static func stringLiterals(in source: String) -> [String] {
        let chars = Array(source)
        var literals: [String] = []
        var i = 0
        func starts(_ token: String, at index: Int) -> Bool {
            let t = Array(token)
            return index + t.count <= chars.count && Array(chars[index..<index + t.count]) == t
        }
        while i < chars.count {
            if starts("//", at: i) {
                while i < chars.count && chars[i] != "\n" { i += 1 }
            } else if starts("/*", at: i) {
                i += 2
                while i < chars.count && !starts("*/", at: i) { i += 1 }
                i += 2
            } else if chars[i] == "\"" || (chars[i] == "#" && starts("#\"", at: i)) {
                var hashes = 0
                while i < chars.count && chars[i] == "#" { hashes += 1; i += 1 }
                let multiline = starts("\"\"\"", at: i)
                let close = (multiline ? "\"\"\"" : "\"") + String(repeating: "#", count: hashes)
                i += multiline ? 3 : 1
                var content = ""
                while i < chars.count && !starts(close, at: i) {
                    if hashes == 0 && chars[i] == "\\" && i + 1 < chars.count {
                        if chars[i + 1] == "(" {
                            // Skip interpolated code up to the matching parenthesis.
                            var depth = 1
                            i += 2
                            while i < chars.count && depth > 0 {
                                if chars[i] == "(" { depth += 1 } else if chars[i] == ")" { depth -= 1 }
                                i += 1
                            }
                            continue
                        }
                        content.append(chars[i])
                        content.append(chars[i + 1])
                        i += 2
                        continue
                    }
                    content.append(chars[i])
                    i += 1
                }
                i += close.count
                literals.append(content)
            } else {
                i += 1
            }
        }
        return literals
    }
}
