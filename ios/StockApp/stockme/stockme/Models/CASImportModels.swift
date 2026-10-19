// Models/CASImportModels.swift
// Domain: CAS import (I28, /api/v1/me/imports). spec_money 3.5: copy and the notice text are fixed.

import Foundation

// MARK: - Wire types

nonisolated struct CASPreviewRequest: Encodable {
    let pdfBase64: String
    let password: String
    let consentNoticeVersion: String
    let attestOwnStatement: Bool

    enum CodingKeys: String, CodingKey {
        case pdfBase64 = "pdf_base64"
        case password
        case consentNoticeVersion = "consent_notice_version"
        case attestOwnStatement = "attest_own_statement"
    }
}

nonisolated struct CASPreview: Decodable {
    let batchId: Int
    let expiresAt: String
    let statement: CASStatement
    let schemes: [CASPreviewScheme]
    let totals: CASPreviewTotals

    enum CodingKeys: String, CodingKey {
        case statement, schemes, totals
        case batchId = "batch_id"
        case expiresAt = "expires_at"
    }
}

nonisolated struct CASStatement: Decodable {
    let from: String?
    let to: String?
    let source: String?
    let type: String?
}

nonisolated struct CASValuation: Decodable {
    let date: String?
    let nav: Double?
    let valueInr: Double?
    let costInr: Double?

    enum CodingKeys: String, CodingKey {
        case date, nav
        case valueInr = "value_inr"
        case costInr = "cost_inr"
    }
}

nonisolated struct CASPreviewScheme: Decodable, Identifiable {
    var id: String { isin ?? name }
    let isin: String?
    let name: String
    let amc: String?
    let units: Double
    let valuation: CASValuation
    /// balance | skipped
    let mode: String
    let reason: String?
    let flags: [String]?

    var isBalance: Bool { mode == "balance" }
    var costUnknown: Bool { flags?.contains("cost_unknown") == true }
}

nonisolated struct CASPreviewTotals: Decodable {
    let schemes: Int
    let balance: Int
    let skipped: Int
    let valueInr: Double

    enum CodingKeys: String, CodingKey {
        case schemes, balance, skipped
        case valueInr = "value_inr"
    }
}

nonisolated struct CASCommitResult: Decodable {
    let batchId: Int
    let insertedTransactions: Int
    let skippedDuplicates: Int
    let schemesImported: Int

    enum CodingKeys: String, CodingKey {
        case batchId = "batch_id"
        case insertedTransactions = "inserted_transactions"
        case skippedDuplicates = "skipped_duplicates"
        case schemesImported = "schemes_imported"
    }
}

nonisolated struct CASUndoResult: Decodable {
    let deletedTransactions: Int

    enum CodingKeys: String, CodingKey { case deletedTransactions = "deleted_transactions" }
}

nonisolated struct ImportBatchSummary: Decodable, Identifiable {
    var id: Int { batchId }
    let batchId: Int
    let source: String
    let statementTo: String?
    /// previewed | committed
    let status: String
    let schemesImported: Int
    let insertedTransactions: Int
    let createdAt: String

    var isCommitted: Bool { status == "committed" }

    enum CodingKeys: String, CodingKey {
        case source, status
        case batchId = "batch_id"
        case statementTo = "statement_to"
        case schemesImported = "schemes_imported"
        case insertedTransactions = "inserted_transactions"
        case createdAt = "created_at"
    }
}

// MARK: - Errors

/// A non-2xx answer from the import routes: `{"detail": {"code", "message"}}`.
nonisolated struct CASImportError: Error, Equatable {
    let code: String
    let status: Int
}

nonisolated enum CASImportErrorCode: String {
    case wrongPassword = "WRONG_PASSWORD"
    case unsupportedStatement = "UNSUPPORTED_STATEMENT"
    case dematNotSupported = "DEMAT_CAS_NOT_SUPPORTED"
    case alreadyImported = "ALREADY_IMPORTED"
    case quotaExceeded = "QUOTA_EXCEEDED"
    case fileTooLarge = "FILE_TOO_LARGE"
    case parseTimeout = "PARSE_TIMEOUT"
    case parseBusy = "PARSE_BUSY"
    case notAPdf = "NOT_A_PDF"
    case invalidRequest = "INVALID_REQUEST"
    case consentRequired = "CONSENT_REQUIRED"
    case previewExpired = "PREVIEW_EXPIRED"
    case ledgerConflict = "LEDGER_CONFLICT"
    case undoWouldOversell = "UNDO_WOULD_OVERSELL"
    case alreadyCommitted = "ALREADY_COMMITTED"
    case featureDisabled = "FEATURE_DISABLED"

    static let generic = "Something went wrong. Please try again."

    var userMessage: String {
        switch self {
        case .wrongPassword: return "That password didn't open the statement. CAS passwords are set when you request the statement."
        case .unsupportedStatement: return "This doesn't look like a CAMS or KFintech CAS. Request a Detailed CAS and try again."
        case .dematNotSupported: return "Demat (NSDL/CDSL) statements aren't supported yet."
        case .alreadyImported: return "You've already imported this statement."
        case .quotaExceeded: return "You've reached today's import limit. Try again tomorrow."
        case .fileTooLarge: return "This file is larger than 10 MB."
        case .parseTimeout: return "Reading the statement took too long. Please try again."
        case .parseBusy: return "We're reading other statements. Try again in a minute."
        case .notAPdf, .invalidRequest, .consentRequired, .previewExpired, .ledgerConflict,
             .undoWouldOversell, .alreadyCommitted, .featureDisabled:
            return Self.generic
        }
    }

    /// User-facing text for a server code; unknown codes get the generic line.
    static func message(for code: String) -> String {
        CASImportErrorCode(rawValue: code)?.userMessage ?? generic
    }

    /// Codes where choosing the same file again (or retyping the password) can succeed.
    var isRetryable: Bool {
        switch self {
        case .wrongPassword, .parseTimeout, .parseBusy: return true
        default: return false
        }
    }
}

// MARK: - Notice and copy (fixed, versioned)

nonisolated enum CASNotice {
    static let version = "cas-v1"
    static let maxPDFBytes = 10_000_000
    /// UserDefaults flag set by onboarding; the Portfolio screen opens the import once and clears it.
    static let openOnceKey = "nivesh_openCASImport"

    static let keeps = "for each fund in your statement, its name, ISIN, units, cost value and the statement's valuation date and NAV."
    static let doesNotKeep = "the PDF, its password, your PAN, name, address, email, phone, folio numbers, nominee details or transactions. The file is read in memory and discarded."
    static let why = "to show these funds with your holdings and in your Portfolio X-ray. Imported funds are never sent to AI features."
    static let control = "undo any import from \"Your imports\". You can download or erase your data from Settings."
    static let attestLabel = "This statement is mine."
    static let agreeLabel = "I agree to Nivesh keeping these fund balances for these purposes."

    /// Whether the Portfolio screen should open the import now. Clears the key only when the flag is on,
    /// so a flag-off launch never consumes (or acts on) the onboarding hint.
    static func consumeOpenOnce(flagOn: Bool, defaults: UserDefaults = .standard) -> Bool {
        guard flagOn, defaults.bool(forKey: openOnceKey) else { return false }
        defaults.set(false, forKey: openOnceKey)
        return true
    }
}

nonisolated enum CASPreviewCopy {
    /// Badge on a preview row.
    static func badge(_ s: CASPreviewScheme) -> String { s.isBalance ? "Added as a balance" : "Skipped" }

    /// The reason line under a preview row, or nil when there is nothing to add.
    static func reason(_ s: CASPreviewScheme) -> String? {
        if s.isBalance {
            let when = MoneyReturnCopy.day(s.valuation.date) ?? "the statement date"
            var line = "Imported as a balance on \(when). Returns for this fund aren't calculated yet."
            if s.costUnknown { line += " Cost not in statement: gains are measured from the statement date." }
            return line
        }
        switch s.reason {
        case "isin_missing": return "No ISIN in the statement"
        case "manual_entries_exist": return "You've added this fund by hand"
        case "zero_balance": return "No units left"
        case "older_statement": return "A newer statement is already imported"
        default: return nil
        }
    }

    static func done(_ funds: Int) -> String { "Added \(funds) \(funds == 1 ? "fund" : "funds")." }
}
