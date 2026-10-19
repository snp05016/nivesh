import XCTest
@testable import stockme

@MainActor
final class CASImportModelsTests: XCTestCase {

    private let previewJSON = """
    {"batch_id": 17, "expires_at": "2026-10-12T09:00:00Z",
     "statement": {"from": "2016-01-01", "to": "2026-10-08", "source": "CAMS", "type": "DETAILED"},
     "schemes": [
       {"isin": "INF179K01VC4", "name": "HDFC Flexi Cap Fund - Direct Plan - Growth", "amc": "HDFC Mutual Fund",
        "units": 123.456, "valuation": {"date": "2026-10-08", "nav": 45.67, "value_inr": 5638.07, "cost_inr": 5000.0},
        "mode": "balance", "reason": null, "flags": []},
       {"isin": "INF846K01DP8", "name": "Axis Bluechip Fund", "amc": null,
        "units": 50.0, "valuation": {"date": "2026-10-08", "nav": 60.0, "value_inr": 3000.0, "cost_inr": null},
        "mode": "balance", "reason": null, "flags": ["cost_unknown"]},
       {"isin": null, "name": "Mystery Fund", "amc": "X",
        "units": 5.0, "valuation": {"date": null, "nav": null, "value_inr": null, "cost_inr": null},
        "mode": "skipped", "reason": "isin_missing", "flags": null}
     ],
     "totals": {"schemes": 3, "balance": 2, "skipped": 1, "value_inr": 8638.07}}
    """

    func testRequestEncodesSnakeCaseAndBase64() throws {
        let pdf = Data("%PDF-1.4 test".utf8)
        let request = CASPreviewRequest(pdfBase64: pdf.base64EncodedString(), password: "pw",
                                        consentNoticeVersion: CASNotice.version, attestOwnStatement: true)

        let object = try JSONSerialization.jsonObject(with: JSONEncoder().encode(request)) as? [String: Any]

        XCTAssertEqual(Set(object?.keys.map { $0 } ?? []),
                       ["pdf_base64", "password", "consent_notice_version", "attest_own_statement"])
        XCTAssertEqual(object?["consent_notice_version"] as? String, "cas-v1")
        XCTAssertEqual(object?["attest_own_statement"] as? Bool, true)
        XCTAssertEqual(Data(base64Encoded: object?["pdf_base64"] as? String ?? ""), pdf)
    }

    func testPreviewDecodesWithNulls() throws {
        let preview = try JSONDecoder().decode(CASPreview.self, from: Data(previewJSON.utf8))

        XCTAssertEqual(preview.batchId, 17)
        XCTAssertEqual(preview.totals.balance, 2)
        XCTAssertEqual(preview.schemes[0].valuation.costInr, 5000.0)
        XCTAssertNil(preview.schemes[1].valuation.costInr)
        XCTAssertTrue(preview.schemes[1].costUnknown)
        XCTAssertNil(preview.schemes[2].isin)
        XCTAssertNil(preview.schemes[2].flags)
        XCTAssertFalse(preview.schemes[2].isBalance)
    }

    func testPreviewCopy() throws {
        let preview = try JSONDecoder().decode(CASPreview.self, from: Data(previewJSON.utf8))

        XCTAssertEqual(CASPreviewCopy.badge(preview.schemes[0]), "Added as a balance")
        XCTAssertEqual(CASPreviewCopy.reason(preview.schemes[0]),
                       "Imported as a balance on 8 Oct 2026. Returns for this fund aren't calculated yet.")
        XCTAssertEqual(CASPreviewCopy.reason(preview.schemes[1]),
                       "Imported as a balance on 8 Oct 2026. Returns for this fund aren't calculated yet. Cost not in statement: gains are measured from the statement date.")
        XCTAssertEqual(CASPreviewCopy.badge(preview.schemes[2]), "Skipped")
        XCTAssertEqual(CASPreviewCopy.reason(preview.schemes[2]), "No ISIN in the statement")
        XCTAssertEqual(CASPreviewCopy.done(5), "Added 5 funds.")
        XCTAssertEqual(CASPreviewCopy.done(1), "Added 1 fund.")
    }

    func testEveryCodeMapsToItsCopy() {
        let spec: [String: String] = [
            "WRONG_PASSWORD": "That password didn't open the statement. CAS passwords are set when you request the statement.",
            "UNSUPPORTED_STATEMENT": "This doesn't look like a CAMS or KFintech CAS. Request a Detailed CAS and try again.",
            "DEMAT_CAS_NOT_SUPPORTED": "Demat (NSDL/CDSL) statements aren't supported yet.",
            "ALREADY_IMPORTED": "You've already imported this statement.",
            "QUOTA_EXCEEDED": "You've reached today's import limit. Try again tomorrow.",
            "FILE_TOO_LARGE": "This file is larger than 10 MB.",
            "PARSE_TIMEOUT": "Reading the statement took too long. Please try again.",
            "PARSE_BUSY": "We're reading other statements. Try again in a minute."
        ]
        for (code, copy) in spec { XCTAssertEqual(CASImportErrorCode.message(for: code), copy, code) }
        for code in ["NOT_A_PDF", "INVALID_REQUEST", "CONSENT_REQUIRED", "PREVIEW_EXPIRED", "LEDGER_CONFLICT",
                     "UNDO_WOULD_OVERSELL", "ALREADY_COMMITTED", "FEATURE_DISABLED", "SOMETHING_NEW"] {
            XCTAssertEqual(CASImportErrorCode.message(for: code), "Something went wrong. Please try again.", code)
        }
    }

    func testElevenMegabyteFileIsRefusedBeforeUpload() async {
        var called = false
        let model = CASImportViewModel(client: CASImportClient(
            preview: { _, _ in called = true; throw CASImportError(code: "X", status: 500) },
            commit: { _ in throw CASImportError(code: "X", status: 500) },
            cancel: { _ in }
        ))

        model.fileChosen(Data(count: 11_000_000), name: "big.pdf")
        model.password = "pw"
        await model.upload()

        XCTAssertEqual(model.state, .failed(code: "FILE_TOO_LARGE", message: "This file is larger than 10 MB."))
        XCTAssertFalse(called)
    }

    func testPasswordIsClearedAfterTheRequest() async throws {
        let preview = try JSONDecoder().decode(CASPreview.self, from: Data(previewJSON.utf8))
        var sentPassword: String?
        let model = CASImportViewModel(client: CASImportClient(
            preview: { _, pw in sentPassword = pw; return preview },
            commit: { _ in throw CASImportError(code: "X", status: 500) },
            cancel: { _ in }
        ))
        model.fileChosen(Data("%PDF".utf8), name: "cas.pdf")
        model.password = "ABCDE1234F"

        await model.upload()

        XCTAssertEqual(sentPassword, "ABCDE1234F")
        XCTAssertEqual(model.password, "")
        XCTAssertEqual(model.state, .preview)
    }

    func testPasswordIsClearedAfterAFailedRequestAndRetryKeepsTheFile() async {
        let model = CASImportViewModel(client: CASImportClient(
            preview: { _, _ in throw CASImportError(code: "WRONG_PASSWORD", status: 422) },
            commit: { _ in throw CASImportError(code: "X", status: 500) },
            cancel: { _ in }
        ))
        model.fileChosen(Data("%PDF".utf8), name: "cas.pdf")
        model.password = "wrong"

        await model.upload()

        XCTAssertEqual(model.password, "")
        guard case .failed(let code, _) = model.state else { return XCTFail("expected failed") }
        XCTAssertEqual(code, "WRONG_PASSWORD")
        model.retry()
        XCTAssertEqual(model.state, .fileChosen)
    }

    func testCommitReportsFundsAndCancelResets() async throws {
        let preview = try JSONDecoder().decode(CASPreview.self, from: Data(previewJSON.utf8))
        var cancelled: Int?
        let model = CASImportViewModel(client: CASImportClient(
            preview: { _, _ in preview },
            commit: { id in
                let json = #"{"batch_id": \#(id), "inserted_transactions": 2, "skipped_duplicates": 0, "schemes_imported": 2}"#
                return try JSONDecoder().decode(CASCommitResult.self, from: Data(json.utf8))
            },
            cancel: { cancelled = $0 }
        ))
        model.fileChosen(Data("%PDF".utf8), name: "cas.pdf")
        model.password = "pw"
        await model.upload()

        await model.commit()
        XCTAssertEqual(model.state, .done(funds: 2))

        model.reset()
        model.fileChosen(Data("%PDF".utf8), name: "cas.pdf")
        model.password = "pw"
        await model.upload()
        await model.cancel()
        XCTAssertEqual(cancelled, 17)
        XCTAssertEqual(model.state, .idle)
    }

    func testChoosePDFNeedsBothToggles() {
        let model = CASImportViewModel(client: .live)
        XCTAssertFalse(model.canChooseFile)
        model.attestsOwnStatement = true
        XCTAssertFalse(model.canChooseFile)
        model.agreesToNotice = true
        XCTAssertTrue(model.canChooseFile)
    }

    func testOpenOnceHintIsIgnoredWhenFlagOff() {
        let defaults = UserDefaults(suiteName: "CASImportModelsTests.\(UUID().uuidString)")!
        defaults.set(true, forKey: CASNotice.openOnceKey)

        XCTAssertFalse(CASNotice.consumeOpenOnce(flagOn: false, defaults: defaults))
        XCTAssertTrue(defaults.bool(forKey: CASNotice.openOnceKey), "a flag-off launch must not consume the hint")

        XCTAssertTrue(CASNotice.consumeOpenOnce(flagOn: true, defaults: defaults))
        XCTAssertFalse(defaults.bool(forKey: CASNotice.openOnceKey))
        XCTAssertFalse(CASNotice.consumeOpenOnce(flagOn: true, defaults: defaults), "opens once")
    }
}
