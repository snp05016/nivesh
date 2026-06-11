import SwiftUI
import OSLog
import Combine
// MARK: - Universal Error Diagnostic Context

/// Lightweight diagnostic context — attached to every error in the app.
/// Pass this alongside any error to get full telemetry in the UI.
struct ErrorDiagnostic: Equatable {
    let endpoint: String
    let httpStatus: Int?
    let correlationId: String?
    let failingContract: String?
    let swiftFile: String
    let classification: String
    let timestamp: Date

    init(endpoint: String = "",
         httpStatus: Int? = nil,
         correlationId: String? = nil,
         failingContract: String? = nil,
         swiftFile: String = #fileID,
         classification: String = "INFRASTRUCTURE_EXCEPTION") {
        self.endpoint = endpoint
        self.httpStatus = httpStatus
        self.correlationId = correlationId
        self.failingContract = failingContract
        self.swiftFile = swiftFile
        self.classification = classification
        self.timestamp = Date()
    }

    var summary: String {
        var lines: [String] = []
        if !endpoint.isEmpty { lines.append("Endpoint: \(endpoint)") }
        if let s = httpStatus { lines.append("HTTP Status: \(s)") }
        if let c = correlationId { lines.append("Correlation ID: \(c)") }
        if let c = failingContract { lines.append("Failing Contract: \(c)") }
        lines.append("Source: \((swiftFile as NSString).lastPathComponent)")
        lines.append("Classification: \(classification)")
        let df = DateFormatter(); df.dateFormat = "HH:mm:ss.SSS"
        lines.append("Time: \(df.string(from: timestamp))")
        return lines.joined(separator: "\n")
    }
}

// MARK: - Global Error Tracker

@MainActor
final class GlobalErrorDiagnoser: ObservableObject {
    static let shared = GlobalErrorDiagnoser()

    @Published var errors: [TrackedError] = []
    private let maxStored = 50

    struct TrackedError: Identifiable {
        let id = UUID()
        let message: String
        let diagnostic: ErrorDiagnostic
        let rawError: String
    }

    func track(_ message: String, diagnostic: ErrorDiagnostic? = nil, rawError: String = "") {
        let diagnostic = diagnostic ?? ErrorDiagnostic()
        let entry = TrackedError(message: message, diagnostic: diagnostic, rawError: rawError)
        errors.insert(entry, at: 0)
        if errors.count > maxStored { errors = Array(errors.prefix(maxStored)) }

        let log = """
        ╔══════════════════════════════════════════════════════════
        ║ NIVESH DIAGNOSTIC ERROR
        ╠══════════════════════════════════════════════════════════
        ║ Message: \(message)
        ║ \(diagnostic.summary.replacingOccurrences(of: "\n", with: "\n║ "))
        ║ Raw: \(rawError.prefix(500))
        ╚══════════════════════════════════════════════════════════
        """
        os_log(.error, "%{public}@", log)
        print(log)
    }

    func trackNetworkError(_ error: Error, endpoint: String, swiftFile: String = #fileID) {
        let diag = ErrorDiagnostic(
            endpoint: endpoint,
            httpStatus: extractHTTPStatus(from: error),
            failingContract: extractFailingContract(from: error),
            swiftFile: swiftFile,
            classification: classify(error)
        )
        track(error.localizedDescription, diagnostic: diag, rawError: String(describing: error))
    }

    private func extractHTTPStatus(from error: Error) -> Int? {
        if let ne = error as? NetworkError,
           case .fetchFailed(_, let status, _) = ne { return status }
        if let ne = error as? NetworkError,
           case .serverError(let code, _) = ne { return code }
        return nil
    }

    private func extractFailingContract(from error: Error) -> String? {
        if let ne = error as? NetworkError,
           case .decodingError(let detail) = ne { return detail }
        return nil
    }

    private func classify(_ error: Error) -> String {
        switch error {
        case let ne as NetworkError:
            switch ne {
            case .connectionFailed, .fetchFailed: return "INFRASTRUCTURE_EXCEPTION"
            case .decodingError: return "SCHEMA_DRIFT"
            case .unauthorized: return "AUTHENTICATION_FAILURE"
            default: return "INFRASTRUCTURE_EXCEPTION"
            }
        case is DecodingError: return "SCHEMA_DRIFT"
        default: return "INFRASTRUCTURE_EXCEPTION"
        }
    }
}

// MARK: - Error Diagnoser View (drop-in anywhere)

struct ErrorDiagnoserView: View {
    let error: String?
    let context: ErrorDiagnostic
    var retryAction: (() async -> Void)? = nil

    @State private var isRetrying = false
    @State private var showDiagnostics = false

    var body: some View {
        if let error = error {
            VStack(spacing: 0) {
                VStack(spacing: Theme.Spacing.card) {
                    currencyBand

                    VStack(spacing: Theme.Spacing.standard) {
                        Text("DATA FAULT")
                            .font(Theme.engravedSerif(size: 14, weight: .bold))
                            .foregroundStyle(Theme.bearRed)
                            .tracking(3)

                        Rectangle()
                            .fill(Theme.bearRed.opacity(0.15))
                            .frame(height: 1)
                            .overlay(
                                Text("ERROR VECTOR")
                                    .font(Theme.officialStampFont(size: 7))
                                    .tracking(2)
                                    .foregroundStyle(Theme.bearRed.opacity(0.6))
                                    .padding(.horizontal, Theme.Spacing.tight)
                                    .background(Theme.canvasDeep)
                            )

                        Text(error)
                            .font(Theme.serialNumberFont(size: 11))
                            .foregroundStyle(Theme.inkSecondary)
                            .multilineTextAlignment(.leading)
                            .lineSpacing(3)
                            .fixedSize(horizontal: false, vertical: true)

                        diagnosticExpander

                        if let retry = retryAction {
                            Button {
                                isRetrying = true
                                Task { await retry(); isRetrying = false }
                            } label: {
                                HStack(spacing: Theme.Spacing.tight) {
                                    if isRetrying { ProgressView().scaleEffect(0.7).tint(Theme.securityGold) }
                                    Text(isRetrying ? "RETRYING…" : "RETRY")
                                        .font(Theme.officialStampFont(size: 9)).tracking(3)
                                }
                                .foregroundStyle(Theme.securityGold)
                                .padding(.horizontal, Theme.Spacing.card).padding(.vertical, Theme.Spacing.tight)
                                .background(Theme.securityGold.opacity(0.06))
                                .overlay(RoundedRectangle(cornerRadius: 2)
                                    .stroke(Theme.securityGold.opacity(0.25), lineWidth: 1))
                            }
                            .disabled(isRetrying)
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.card).padding(.bottom, Theme.Spacing.card)
                }
                .background(
                    ZStack {
                        Theme.canvasDeep
                        Text("₹").font(Theme.engravedSerif(size: 140, weight: .bold))
                            .foregroundStyle(Theme.bearRed.opacity(0.02))
                            .offset(x: 50, y: 10).allowsHitTesting(false)
                    }
                )
                .overlay(RoundedRectangle(cornerRadius: 2).stroke(Theme.borderSage, lineWidth: 1))
                .cornerRadius(2)
                .shadow(color: Theme.canvasShadow.opacity(0.1), radius: 3, y: 2)

                Text("NIVESH APPAREL • RBI • \(context.classification.prefix(20).uppercased())")
                    .font(Theme.serialNumberFont(size: 6))
                    .foregroundStyle(Theme.inkTertiary)
                    .tracking(1.2).padding(.top, Theme.Spacing.tight)
            }
            .padding(Theme.cardPadding)
        }
    }

    private var currencyBand: some View {
        HStack(spacing: 0) {
            Rectangle().fill(Theme.bearRed.opacity(0.10)).frame(width: 32, height: 22)
                .overlay(HStack(spacing: 2) {
                    ForEach(0..<3, id: \.self) { _ in Circle().fill(Theme.bearRed.opacity(0.25)).frame(width: 3, height: 3) }
                })
            VStack(spacing: 0) {
                Rectangle().fill(Theme.bearRed.opacity(0.25)).frame(height: 1)
                Text("DIAGNOSTIC").font(Theme.officialStampFont(size: 8))
                    .tracking(3).foregroundStyle(Theme.bearRed.opacity(0.6))
                    .padding(.horizontal, Theme.Spacing.standard).padding(.vertical, Theme.Spacing.xSmall)
                Rectangle().fill(Theme.bearRed.opacity(0.25)).frame(height: 1)
            }
            Rectangle().fill(Theme.bearRed.opacity(0.10)).frame(width: 32, height: 22)
                .overlay(HStack(spacing: 2) {
                    ForEach(0..<3, id: \.self) { _ in Circle().fill(Theme.bearRed.opacity(0.25)).frame(width: 3, height: 3) }
                })
        }
    }

    private var diagnosticExpander: some View {
        VStack(spacing: 0) {
            Button { withAnimation(.easeInOut(duration: 0.2)) { showDiagnostics.toggle() } } label: {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: showDiagnostics ? "chevron.down" : "chevron.right").font(.caption.weight(.bold))
                    Text("DIAGNOSTICS").font(Theme.officialStampFont(size: 8)).tracking(2)
                    Spacer()
                    Text(context.correlationId ?? "no-id").font(Theme.serialNumberFont(size: 7))
                        .foregroundStyle(Theme.inkTertiary).lineLimit(1)
                }
                .foregroundStyle(Theme.securityGold.opacity(0.7)).padding(.vertical, Theme.Spacing.small)
            }
            if showDiagnostics {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    diagRow("Endpoint", context.endpoint)
                    if let s = context.httpStatus { diagRow("HTTP", "\(s)") }
                    if let c = context.correlationId { diagRow("Correlation ID", c) }
                    if let c = context.failingContract { diagRow("Contract", c) }
                    diagRow("Source", (context.swiftFile as NSString).lastPathComponent)
                    diagRow("Class", context.classification)
                    Button {
                        #if os(iOS)
                        UIPasteboard.general.string = "ERROR: \(error ?? "")\n\(context.summary)"
                        #endif
                    } label: {
                        HStack(spacing: Theme.Spacing.small) {
                            Image(systemName: "doc.on.doc").font(.caption2)
                            Text("COPY TO CLIPBOARD").font(Theme.officialStampFont(size: 7)).tracking(1)
                        }
                        .foregroundStyle(Theme.securityGold.opacity(0.6)).padding(.vertical, Theme.Spacing.small)
                    }
                }
                .padding(Theme.Spacing.medium).background(Theme.canvasShadow.opacity(0.3)).cornerRadius(2)
            }
        }
    }

    private func diagRow(_ label: String, _ value: String) -> some View {
        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
            Text(label.uppercased()).font(Theme.officialStampFont(size: 7))
                .foregroundStyle(Theme.inkTertiary).frame(minWidth: 60, alignment: .leading)
            Text(value).font(Theme.serialNumberFont(size: 7))
                .foregroundStyle(Theme.inkSecondary).frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

// MARK: - View Extension: Drop-in error diagnoser for any view

extension View {
    /// Attach to ANY view to display errors with full banknote diagnostics.
    func errorDiagnoser(
        error: String?,
        context: ErrorDiagnostic = ErrorDiagnostic(),
        retryAction: (() async -> Void)? = nil
    ) -> some View {
        VStack(spacing: 0) {
            self
            if error != nil {
                ErrorDiagnoserView(error: error, context: context, retryAction: retryAction)
                    .transition(.opacity.combined(with: .move(edge: .bottom)))
            }
        }
        .animation(.easeInOut(duration: 0.25), value: error)
    }
}
