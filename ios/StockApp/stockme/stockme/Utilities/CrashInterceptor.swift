import Foundation
import UIKit

// Global bridge for the C function pointer — must be top-level, zero context capture
private var _exceptionBridge: ((NSException) -> Void)?

private func _niveshOnException(_ e: NSException) { _exceptionBridge?(e) }

enum CrashInterceptor {
    private static var didRegister = false

    static func register() {
        guard !didRegister else { return }
        didRegister = true

        // ObjC exception handler — via global bridge (C function pointer)
        _exceptionBridge = { exception in
            let name = exception.name.rawValue
            let reason = exception.reason ?? ""
            let stack = exception.callStackSymbols.prefix(20).joined(separator: "\n")
            record(type: .exception, signal: nil, name: name, reason: reason,
                   stackTrace: stack, viewPath: CrashGuard.lastViewPath)
        }
        NSSetUncaughtExceptionHandler(_niveshOnException)

        // No POSIX signal handlers: allocation, JSON and file IO are not
        // async-signal-safe and can deadlock a crashing process (e.g. SIGSEGV
        // inside malloc). Signal crashes go to the OS crash reporter (Xcode
        // Organizer / TestFlight). CrashType.signal stays so old logs decode.
        // ponytail: add an MXMetricManagerSubscriber (MXCrashDiagnostic) if in-app signal crash lists matter.
    }

    static func record(type: CrashType, signal: Int32?, name: String, reason: String?,
                        stackTrace: String, viewPath: String?) {
        let swiftFile = parseSwiftFile(from: stackTrace)
        let approxLine = parseApproxLine(from: stackTrace)
        let classification = classify(name: name, reason: reason ?? "")
        let report = CrashReport(
            id: UUID().uuidString,
            timestamp: ISO8601DateFormatter().string(from: Date()),
            type: type,
            signalNumber: signal.map(Int.init),
            signalName: type == .signal ? name : nil,
            exceptionName: type == .exception ? name : nil,
            exceptionReason: reason,
            stackTrace: stackTrace,
            viewPath: viewPath,
            swiftFile: swiftFile,
            approxLine: approxLine,
            device: deviceModel(),
            osVersion: UIDevice.current.systemVersion,
            appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?",
            buildNumber: Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "?",
            classification: classification
        )
        CrashLog.shared.append(report)
    }

    private static func parseSwiftFile(from stack: String) -> String? {
        let lines = stack.components(separatedBy: "\n")
        for line in lines {
            if line.contains("StockApp") {
                if let range = line.range(of: "\\w+\\.swift", options: .regularExpression) {
                    return String(line[range])
                }
                let pattern = try? NSRegularExpression(pattern: "(\\w+(?:Screen|View|Card))", options: [])
                if let match = pattern?.firstMatch(in: line, range: NSRange(line.startIndex..., in: line)) {
                    return "\((line as NSString).substring(with: match.range)).swift"
                }
            }
        }
        return nil
    }

    private static func parseApproxLine(from stack: String) -> String? {
        for line in stack.components(separatedBy: "\n") {
            if line.contains("StockApp"), let range = line.range(of: "0x[0-9a-fA-F]+", options: .regularExpression) {
                let addr = String(line[range]).replacingOccurrences(of: "0x", with: "")
                if let hexVal = Int(addr, radix: 16) { return "~\(hexVal % 10000)" }
            }
        }
        return nil
    }

    private static func classify(name: String, reason: String) -> String {
        let combined = "\(name) \(reason)".lowercased()
        if combined.contains("duplicate") || combined.contains("same key") { return "Duplicate ForEach ID" }
        if combined.contains("unexpectedly found nil") || combined.contains("force unwrap") { return "Force-unwrap on nil optional" }
        if combined.contains("modifying state") || combined.contains("during view update") { return "@State mutation during view update" }
        if combined.contains("environmentobject") { return "Missing @EnvironmentObject" }
        if combined.contains("index out of range") || combined.contains("out of bounds") { return "Array index out of bounds" }
        if combined.contains("sigsegv") { return "Memory access violation (SIGSEGV)" }
        if combined.contains("sigabrt") { return "Uncaught exception (SIGABRT)" }
        return name
    }

    private static func deviceModel() -> String {
        var sysinfo = utsname()
        uname(&sysinfo)
        return withUnsafePointer(to: &sysinfo.machine) {
            $0.withMemoryRebound(to: CChar.self, capacity: Int(_SYS_NAMELEN)) { String(cString: $0) }
        }
    }
}
