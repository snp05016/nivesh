import XCTest
@testable import stockme

final class AuthDecodingTests: XCTestCase {

    func testRegisterResponseDecodesIntoLoggedInUser() throws {
        // NetworkManager.register decodes POST /register into LoggedInUser, which requires
        // access_token, so the backend must return the same payload as /login (CMON-01).
        let json = """
        {
            "user_id": 42,
            "username": "ravi",
            "display_name": "Ravi",
            "access_token": "header.payload.signature",
            "token_type": "bearer"
        }
        """.data(using: .utf8)!

        let user = try JSONDecoder().decode(LoggedInUser.self, from: json)

        XCTAssertEqual(user.userId, 42)
        XCTAssertEqual(user.username, "ravi")
        XCTAssertEqual(user.displayName, "Ravi")
        XCTAssertEqual(user.token, "header.payload.signature")
    }
}
