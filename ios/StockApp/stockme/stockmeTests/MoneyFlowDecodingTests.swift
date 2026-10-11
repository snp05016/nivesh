import XCTest
@testable import stockme

/// FINSEC-27: money-flow DTOs decode JSON shaped exactly like the backend
/// serializers (routers/finance.py, compliance.py, subscription.py), and the
/// loan request encodes the keys the backend expects.
@MainActor
final class MoneyFlowDecodingTests: XCTestCase {

    private func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T {
        try JSONDecoder().decode(type, from: Data(json.utf8))
    }

    func testLoanApplicationWithKFSSnapshot() throws {
        let app = try decode(LoanApplicationResponse.self, """
        {"id": 7, "user_id": 3, "loan_offer_id": 2, "requested_amount": 1000000.0,
         "requested_tenure_months": 60, "status": "approved",
         "mock_credit_score_at_application": 812, "decision_reason": "MOCK DECISION: approved",
         "submitted_at": "2026-10-11T10:00:00+00:00", "decided_at": "2026-10-11T10:00:00+00:00",
         "kfs_apr_pct": 12.62, "kfs_total_fees": 25000.0,
         "kfs_acknowledged_at": "2026-10-11T10:00:00+00:00"}
        """)
        XCTAssertEqual(app.parsedStatus, .approved)
        XCTAssertEqual(app.kfsAprPct ?? 0, 12.62, accuracy: 0.001)
        XCTAssertEqual(app.kfsTotalFees ?? 0, 25000, accuracy: 0.001)
        XCTAssertNotNil(app.kfsAcknowledgedAt)
    }

    func testLoanApplicationFromOlderServerHasNoKFS() throws {
        let app = try decode(LoanApplicationResponse.self, """
        {"id": 1, "user_id": 3, "loan_offer_id": 2, "requested_amount": 50000.0,
         "requested_tenure_months": 12, "status": "under_review",
         "mock_credit_score_at_application": null, "decision_reason": null,
         "submitted_at": null, "decided_at": null}
        """)
        XCTAssertEqual(app.parsedStatus, .underReview)
        XCTAssertNil(app.kfsAprPct)
        XCTAssertNil(app.kfsAcknowledgedAt)
    }

    func testLoanApplicationRequestSendsKFSAcknowledgment() throws {
        let body = LoanApplicationRequest(
            loanOfferId: 2, requestedAmount: 1_000_000, requestedTenureMonths: 60,
            deviceId: "dev-1", kfsAcknowledged: true
        )
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: JSONEncoder().encode(body)) as? [String: Any])
        XCTAssertEqual(json["kfs_acknowledged"] as? Bool, true)
        XCTAssertEqual(json["loan_offer_id"] as? Int, 2)
        XCTAssertEqual(json["requested_tenure_months"] as? Int, 60)
    }

    func testKeyFactStatementForLoan() throws {
        let kfs = try decode(KeyFactStatementDTO.self, """
        {"source": "loan_offer", "loan_offer_id": 2, "nbfc_name": "Demo Lender A (fictional)",
         "loan_type": "personal", "loan_amount": 1000000.0, "interest_rate": 11.5,
         "all_fees": 25000.0, "apr": 12.62, "emi": 21992.61, "total_repayable": 1344556.6,
         "tenure_months": 60, "disclaimer": "MOCK/DEMO CONTENT"}
        """)
        XCTAssertFalse(kfs.isFixedDeposit)
        XCTAssertEqual(kfs.apr, 12.62, accuracy: 0.001)
        XCTAssertEqual(kfs.tenureMonths, 60)
        XCTAssertNotNil(kfs.emi)
    }

    func testKeyFactStatementForFixedDeposit() throws {
        let kfs = try decode(KeyFactStatementDTO.self, """
        {"source": "fixed_deposit_scheme", "scheme_id": 4, "issuer_name": "Demo Issuer (fictional)",
         "loan_amount": 100000.0, "interest_rate": 7.1, "all_fees": 0.0, "apr": 7.1,
         "tenure_months": 12, "disclaimer": "MOCK/DEMO CONTENT"}
        """)
        XCTAssertTrue(kfs.isFixedDeposit)
        XCTAssertNil(kfs.emi)
    }

    func testDisbursement() throws {
        let d = try decode(DisbursementDTO.self, """
        {"id": 5, "loan_application_id": 7, "user_id": 3, "linked_bank_account_id": 9,
         "nbfc_name": "Demo Lender A (fictional)", "disbursed_amount": 975000.0,
         "status": "completed", "disbursed_at": "2026-10-11T10:05:00+00:00", "failure_reason": null}
        """)
        XCTAssertEqual(d.parsedStatus, .completed)
        XCTAssertEqual(d.disbursedAmount ?? 0, 975000, accuracy: 0.001)
    }

    func testLoanBankAccount() throws {
        let a = try decode(LoanBankAccountDTO.self, """
        {"id": 9, "bank_name": "Demo Bank", "account_type": "savings",
         "masked_account_number": "XXXX1234", "ifsc_code": null, "is_primary": true,
         "linked_at": "2026-10-11T09:00:00+00:00"}
        """)
        XCTAssertTrue(a.isPrimary)
        XCTAssertEqual(a.maskedAccountNumber, "XXXX1234")
    }

    func testEntitlementsFailClosedForUnknownKey() throws {
        let e = try decode(EntitlementsDTO.self, """
        {"tier": "free", "features": {"sector_rotation": false},
         "catalog": [{"key": "sector_rotation", "title": "Sector Rotation", "min_tier": "pro"}]}
        """)
        XCTAssertEqual(e.parsedTier, .free)
        XCTAssertFalse(e.isUnlocked("sector_rotation"))
        XCTAssertFalse(e.isUnlocked("not_a_feature"))
        XCTAssertEqual(e.catalog?.first?.minTier, "pro")
    }
}
