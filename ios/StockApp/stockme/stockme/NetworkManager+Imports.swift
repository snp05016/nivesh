import Foundation

extension NetworkManager {
    private static let importsPath = "/api/v1/me/imports"

    /// POST /api/v1/me/imports/cas/preview. The password is sent once and never stored or logged.
    /// 90 s: the server parses the PDF in a child process (up to 30 s) before answering.
    func previewCAS(pdf: Data, password: String) async throws -> CASPreview {
        let body = CASPreviewRequest(pdfBase64: pdf.base64EncodedString(), password: password,
                                     consentNoticeVersion: CASNotice.version, attestOwnStatement: true)
        let data = try await importRequest("POST", "/cas/preview", body: try JSONEncoder().encode(body), timeout: 90)
        return try Self.decodeImport(CASPreview.self, from: data)
    }

    func commitImport(batchId: Int) async throws -> CASCommitResult {
        let data = try await importRequest("POST", "/\(batchId)/commit")
        return try Self.decodeImport(CASCommitResult.self, from: data)
    }

    /// 204 No Content.
    func cancelImport(batchId: Int) async throws {
        _ = try await importRequest("POST", "/\(batchId)/cancel")
    }

    func undoImport(batchId: Int) async throws -> CASUndoResult {
        let data = try await importRequest("DELETE", "/\(batchId)")
        return try Self.decodeImport(CASUndoResult.self, from: data)
    }

    func listImports() async throws -> [ImportBatchSummary] {
        let data = try await importRequest("GET", "", timeout: 20)
        return try Self.decodeImport([ImportBatchSummary].self, from: data)
    }

    // MARK: - Plumbing

    private static func decodeImport<T: Decodable>(_ type: T.Type, from data: Data) throws -> T {
        do { return try JSONDecoder().decode(type, from: data) }
        catch { throw NetworkError.decodingError("imports: \(error)") }
    }

    /// Non-2xx answers carrying `detail.code` become `CASImportError`; 401/402 keep their shared typing.
    private func importRequest(_ method: String, _ path: String, body: Data? = nil, timeout: TimeInterval = 20) async throws -> Data {
        guard let url = URL(string: "\(baseURL)\(Self.importsPath)\(path)") else { throw NetworkError.invalidURL }
        var req = authRequest(url)
        req.httpMethod = method
        req.timeoutInterval = timeout
        if let body {
            req.httpBody = body
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let data: Data, response: URLResponse
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            if error is CancellationError || (error as? URLError)?.code == .cancelled { throw error }
            throw NetworkError.connectionFailed
        }
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        if (200...299).contains(http.statusCode) { return data }
        if http.statusCode == 401 || http.statusCode == 402 {
            throw NetworkError.fromHTTP(status: http.statusCode, data: data, endpoint: Self.importsPath + path)
        }
        let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        if let code = (obj?["detail"] as? [String: Any])?["code"] as? String {
            throw CASImportError(code: code, status: http.statusCode)
        }
        throw NetworkError.serverError(http.statusCode, nil)
    }
}
