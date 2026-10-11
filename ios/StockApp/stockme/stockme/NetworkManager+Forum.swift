import Foundation

// MARK: - Community Forum: report / block (App Store 1.2 UGC controls)
//
// Endpoints match backend/routers/forum.py (prefix /api/forum), all auth:
// POST /posts/{post_id}/report, POST /posts/{post_id}/block-author,
// GET /blocks, DELETE /blocks/{block_id}. Same error shape as the other
// forum calls: non-2xx -> NetworkError.fetchFailed(endpoint, status, body).

extension NetworkManager {

    /// Reports a post. The server hides it for this viewer immediately.
    func reportForumPost(postId: Int, reason: ForumReportReason, details: String?) async throws {
        struct Req: Encodable {
            let reason: String
            let details: String?
        }
        let body = try JSONEncoder().encode(Req(reason: reason.rawValue, details: details))
        _ = try await sendForumModerationRequest("/api/forum/posts/\(postId)/report", method: "POST", body: body)
    }

    /// Blocks the author of a post — their threads and posts disappear for this viewer.
    func blockForumAuthor(postId: Int) async throws {
        _ = try await sendForumModerationRequest("/api/forum/posts/\(postId)/block-author", method: "POST")
    }

    /// Users this viewer has blocked.
    func getForumBlocks() async throws -> [ForumBlock] {
        let data = try await sendForumModerationRequest("/api/forum/blocks", method: "GET")
        do { return try JSONDecoder().decode([ForumBlock].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Removes one of this viewer's blocks.
    func unblockForumUser(blockId: Int) async throws {
        _ = try await sendForumModerationRequest("/api/forum/blocks/\(blockId)", method: "DELETE")
    }

    private func sendForumModerationRequest(_ endpoint: String, method: String, body: Data? = nil) async throws -> Data {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = method
        request.timeoutInterval = 15
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = body
        }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        return data
    }
}
