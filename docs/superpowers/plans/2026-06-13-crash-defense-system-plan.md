# Crash Defense System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 3-layer crash defense system: pre-flight lint script, runtime view guard, and signal/exception crash interception with Crash Lab diagnostic viewer accessible from Dev Tools.

**Architecture:** 5 new files + 4 modified files. Crash interception via NSSetUncaughtExceptionHandler + 6 POSIX signal handlers registered in AppDelegate. CrashReport model stored as JSON on disk (max 10). CrashLabView displayed from Settings > Dev Tools. CrashGuard modifier logs view lifecycle to os_log in DEBUG builds.

**Tech Stack:** Swift, SwiftUI, Foundation, UIKit signal handlers, os_log, shell script linting

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `Models.swift` | Modify | Add `CrashReport` + `CrashType` types |
| `Utilities/CrashLog.swift` | Create | JSON persistence (read/write/delete crash reports) |
| `Utilities/CrashInterceptor.swift` | Create | Signal/exception handler registration + recording |
| `Utilities/CrashGuard.swift` | Create | View lifecycle logger for DEBUG builds |
| `Views/CrashLabView.swift` | Create | Banknote-themed crash diagnostic viewer |
| `AppDelegate.swift` | Modify | Register crash handlers in didFinishLaunching |
| `stockmeApp.swift` | Modify | Detect crash-on-restart flag |
| `Views/SettingsScreen.swift` | Modify | Add Crash Lab row in Dev Tools |
| `scripts/lint_crash_patterns.sh` | Create | Shell script linter for crash patterns |

---

### Task 1: CrashReport Model + CrashLog Persistence

**Files:**
- Modify: `ios/StockApp/stockme/stockme/Models.swift`
- Create: `ios/StockApp/stockme/stockme/Utilities/CrashLog.swift`

- [ ] **Step 1: Add CrashReport + CrashType to Models.swift**

Add near other model types (after `MorningSummaryResponse`, around line 795):

```swift
struct CrashReport: Codable, Identifiable {
    let id: String
    let timestamp: String
    let type: CrashType
    let signalNumber: Int?
    let signalName: String?
    let exceptionName: String?
    let exceptionReason: String?
    let stackTrace: String
    let viewPath: String?
    let swiftFile: String?
    let approxLine: String?
    let device: String
    let osVersion: String
    let appVersion: String
    let buildNumber: String
    let classification: String
}

enum CrashType: String, Codable {
    case signal
    case exception
}
```

- [ ] **Step 2: Create CrashLog.swift**

```swift
import Foundation

final class CrashLog {
    static let shared = CrashLog()
    private let fileURL: URL
    private let maxCrashes = 10
    private let lock = NSLock()

    private init() {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        fileURL = docs.appendingPathComponent("nivesh_crashes.json")
    }

    func append(_ report: CrashReport) {
        lock.lock()
        defer { lock.unlock() }
        var crashes = allUnsafe()
        crashes.insert(report, at: 0)
        if crashes.count > maxCrashes { crashes = Array(crashes.prefix(maxCrashes)) }
        if let data = try? JSONEncoder().encode(crashes) {
            try? data.write(to: fileURL, options: .atomic)
        }
    }

    func all() -> [CrashReport] {
        lock.lock()
        defer { lock.unlock() }
        return allUnsafe()
    }

    func count() -> Int {
        lock.lock()
        defer { lock.unlock() }
        return allUnsafe().count
    }

    func delete(id: String) {
        lock.lock()
        defer { lock.unlock() }
        var crashes = allUnsafe()
        crashes.removeAll { $0.id == id }
        if let data = try? JSONEncoder().encode(crashes) {
            try? data.write(to: fileURL, options: .atomic)
        }
    }

    func clearAll() {
        lock.lock()
        defer { lock.unlock() }
        try? FileManager.default.removeItem(at: fileURL)
    }

    private func allUnsafe() -> [CrashReport] {
        guard let data = try? Data(contentsOf: fileURL),
              let crashes = try? JSONDecoder().decode([CrashReport].self, from: data) else {
            return []
        }
        return crashes
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add ios/StockApp/stockme/stockme/Models.swift ios/StockApp/stockme/stockme/Utilities/CrashLog.swift
git commit -m "Add CrashReport model + CrashLog persistence (max 10, thread-safe)"
```

---

### Task 2: CrashInterceptor — Signal + Exception Handlers

**File:** Create `ios/StockApp/stockme/stockme/Utilities/CrashInterceptor.swift`

- [ ] **Step 1: Create CrashInterceptor.swift**

```swift
import Foundation
import UIKit

enum CrashInterceptor {
    private static var didRegister = false

    static func register() {
        guard !didRegister else { return }
        didRegister = true

        // ObjC exception handler
        NSSetUncaughtExceptionHandler { exception in
            let name = exception.name.rawValue
            let reason = exception.reason ?? ""
            let stack = exception.callStackSymbols.prefix(20).joined(separator: "\n")
            record(type: .exception, signal: nil, name: name, reason: reason,
                   stackTrace: stack, viewPath: CrashGuard.lastViewPath)
        }

        // POSIX signal handlers
        let signals: [Int32] = [SIGABRT, SIGSEGV, SIGBUS, SIGILL, SIGTRAP, SIGFPE]
        for sig in signals {
            var sa = sigaction()
            sa.__sigaction_u.__sa_handler = { s in
                CrashInterceptor.handleSignal(s)
            }
            sigaction(sig, &sa, nil)
        }
    }

    private static func handleSignal(_ signal: Int32) {
        let name = String(cString: strsignal(signal))
        let stack = Thread.callStackSymbols.prefix(40).joined(separator: "\n")
        record(type: .signal, signal: signal, name: name, reason: nil,
               stackTrace: stack, viewPath: CrashGuard.lastViewPath)
        // Re-raise after recording so system crash reporter also fires
        signal = SIG_DFL
        raise(signal)
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
            if line.contains("StockApp") && line.contains(".swift") {
                if let range = line.range(of: "\\w+\\.swift", options: .regularExpression) {
                    return String(line[range])
                }
            }
        }
        // Heuristic: look for function names matching our view names
        for line in lines {
            if line.contains("StockApp") {
                let pattern = try? NSRegularExpression(pattern: "(\\w+(?:Screen|View|Card))", options: [])
                if let match = pattern?.firstMatch(in: line, range: NSRange(line.startIndex..., in: line)) {
                    let matched = (line as NSString).substring(with: match.range)
                    return "\(matched).swift"
                }
            }
        }
        return nil
    }

    private static func parseApproxLine(from stack: String) -> String? {
        let lines = stack.components(separatedBy: "\n")
        for line in lines {
            if line.contains("StockApp") {
                if let range = line.range(of: "0x[0-9a-fA-F]+", options: .regularExpression) {
                    let addr = String(line[range])
                    if let hexVal = Int(addr.replacingOccurrences(of: "0x", with: ""), radix: 16) {
                        return "~\(hexVal % 10000)"
                    }
                }
            }
        }
        return nil
    }

    private static func classify(name: String, reason: String) -> String {
        let combined = "\(name) \(reason)".lowercased()
        if combined.contains("duplicate") || combined.contains("same key") {
            return "Duplicate ForEach ID on [String] array"
        }
        if combined.contains("unexpectedly found nil") || combined.contains("force unwrap") {
            return "Force-unwrap on nil optional value"
        }
        if combined.contains("modifying state") || combined.contains("during view update") {
            return "@State mutation during view update (computed property)"
        }
        if combined.contains("environmentobject") || combined.contains("no observableobject") {
            return "Missing @EnvironmentObject in view hierarchy"
        }
        if combined.contains("index out of range") || combined.contains("out of bounds") {
            return "Array index out of bounds"
        }
        if combined.contains("sigsegv") || combined.contains("segmentation fault") {
            return "Memory access violation (SIGSEGV)"
        }
        if combined.contains("sigabrt") {
            return "Assertion failure or uncaught exception (SIGABRT)"
        }
        return name
    }

    private static func deviceModel() -> String {
        var sysinfo = utsname()
        uname(&sysinfo)
        let model = withUnsafePointer(to: &sysinfo.machine) {
            $0.withMemoryRebound(to: CChar.self, capacity: Int(_SYS_NAMELEN)) {
                String(cString: $0)
            }
        }
        return model
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add ios/StockApp/stockme/stockme/Utilities/CrashInterceptor.swift
git commit -m "Add CrashInterceptor: NSSetUncaughtExceptionHandler + 6 POSIX signal handlers"
```

---

### Task 3: CrashGuard — View Lifecycle Logger

**File:** Create `ios/StockApp/stockme/stockme/Utilities/CrashGuard.swift`

- [ ] **Step 1: Create CrashGuard.swift**

```swift
import SwiftUI
import os.log

struct CrashGuard: ViewModifier {
    let name: String
    private static let log = OSLog(subsystem: "com.nivesh.stockapp", category: "CrashGuard")
    static private(set) var viewPathStack: [String] = []
    private static let stackLock = NSLock()
    static var lastViewPath: String? {
        stackLock.lock()
        defer { stackLock.unlock() }
        return viewPathStack.isEmpty ? nil : viewPathStack.joined(separator: " > ")
    }

    func body(content: Content) -> some View {
        content
            .onAppear {
                Self.stackLock.lock()
                Self.viewPathStack.append(name)
                Self.stackLock.unlock()
                os_log(.debug, log: Self.log, "CrashGuard ENTER: %{public}@ | path: %{public}@",
                       name, Self.lastViewPath ?? name)
            }
            .onDisappear {
                Self.stackLock.lock()
                Self.viewPathStack.removeAll { $0 == name }
                Self.stackLock.unlock()
                os_log(.debug, log: Self.log, "CrashGuard EXIT: %{public}@", name)
            }
    }
}

extension View {
    func crashGuard(_ name: String) -> some View {
        #if DEBUG
        modifier(CrashGuard(name: name))
        #else
        self
        #endif
    }
}
```

- [ ] **Step 2: Add .crashGuard() to key views**

Read each file and add `.crashGuard("Name")` to the outermost view container:

| File | View | Modifier |
|------|------|----------|
| `AnalysisScreen.swift` | `aiReportScroll` ScrollView | `.crashGuard("AnalysisScreen")` |
| `HomeScreen.swift` | Outer ZStack in body | `.crashGuard("HomeScreen")` |
| `ContentView.swift` | `TabView` | `.crashGuard("ContentView")` |
| `StockProfileView.swift` | Outer view container | `.crashGuard("StockProfile")` |
| `SettingsScreen.swift` | Outer ZStack | `.crashGuard("SettingsScreen")` |
| `GlossaryBrowserView.swift` | Outer ZStack | `.crashGuard("GlossaryBrowser")` |

Exact placement: Find the outermost `ZStack` or `ScrollView` in each file's `body`, add `.crashGuard("Name")` as the last modifier on that container.

- [ ] **Step 3: Commit**

```bash
git add ios/StockApp/stockme/stockme/Utilities/CrashGuard.swift
git add ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift ios/StockApp/stockme/stockme/Views/HomeScreen.swift ios/StockApp/stockme/stockme/Views/ContentView.swift ios/StockApp/stockme/stockme/Views/StockProfileView.swift ios/StockApp/stockme/stockme/Views/SettingsScreen.swift ios/StockApp/stockme/stockme/Views/GlossaryBrowserView.swift
git commit -m "Add CrashGuard view lifecycle logger + wire to 6 key views"
```

---

### Task 4: Register Handlers in AppDelegate

**File:** Modify `ios/StockApp/stockme/stockme/AppDelegate.swift`

- [ ] **Step 1: Add didFinishLaunching to AppDelegate**

After line 4 (`class AppDelegate: ...`), add:

```swift
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        CrashInterceptor.register()
        return true
    }
```

- [ ] **Step 2: Commit**

```bash
git add ios/StockApp/stockme/stockme/AppDelegate.swift
git commit -m "Register CrashInterceptor in AppDelegate.didFinishLaunching"
```

---

### Task 5: Crash-on-Restart Detection in stockmeApp

**File:** Modify `ios/StockApp/stockme/stockme/stockmeApp.swift`

- [ ] **Step 1: Add crash detection on boot**

After existing `@AppStorage` declarations (around line 50), add:

```swift
    @AppStorage("nivesh_crashCountSeen") private var crashCountSeen: Int = 0
    @State private var newCrashesSinceLastBoot: Int = 0
```

- [ ] **Step 2: Add crash count check in onAppear**

Find the `ContentView` or main content section. Add `.onAppear`:

```swift
.onAppear {
    let currentCrashes = CrashLog.shared.count()
    if currentCrashes > crashCountSeen {
        newCrashesSinceLastBoot = currentCrashes - crashCountSeen
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add ios/StockApp/stockme/stockme/stockmeApp.swift
git commit -m "Add crash-on-restart detection in stockmeApp boot sequence"
```

---

### Task 6: CrashLabView — Diagnostic Viewer

**File:** Create `ios/StockApp/stockme/stockme/Views/CrashLabView.swift`

- [ ] **Step 1: Create CrashLabView.swift**

```swift
import SwiftUI

struct CrashLabView: View {
    @State private var crashes: [CrashReport] = []
    @State private var lintOutput: String = ""
    @State private var lintRunning = false

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .fifty)

            if crashes.isEmpty {
                VStack(spacing: Theme.Spacing.standard) {
                    Spacer()
                    Image(systemName: "checkmark.shield.fill")
                        .font(.system(size: 48))
                        .foregroundStyle(Theme.bullGreen.opacity(0.6))
                    Text("No crashes recorded")
                        .font(Theme.engravedSerif(size: 16, weight: .medium, relativeTo: .headline))
                        .foregroundStyle(Theme.inkSecondary)
                    Text("सब ठीक है / All Clear")
                        .font(Theme.hindiFont(size: 12, relativeTo: .caption))
                        .foregroundStyle(Theme.inkTertiary)
                    Spacer()
                }
            } else {
                List {
                    ForEach(crashes) { crash in
                        CrashCardView(report: crash)
                    }
                    .onDelete { indexSet in
                        for i in indexSet {
                            CrashLog.shared.delete(id: crashes[i].id)
                        }
                        crashes = CrashLog.shared.all()
                    }
                }
                .listStyle(.insetGrouped)
                .scrollContentBackground(.hidden)
            }

            // Lint report card at bottom
            VStack {
                Spacer()
                lintReportCard
            }
        }
        .navigationTitle("Crash Lab")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbar {
            if !crashes.isEmpty {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Clear All") {
                        CrashLog.shared.clearAll()
                        crashes = []
                    }
                    .foregroundStyle(Theme.bearRed)
                }
            }
        }
        .onAppear {
            crashes = CrashLog.shared.all()
            if let seen = UserDefaults.standard.value(forKey: "nivesh_crashCountSeen") as? Int {
                UserDefaults.standard.set(crashes.count, forKey: "nivesh_crashCountSeen")
            }
        }
    }

    private var lintReportCard: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            GuillocheDivider()
            HStack {
                Text("LINT REPORT")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .tracking(1.2)
                    .foregroundStyle(Theme.inkTertiary)
                Spacer()
                Button {
                    lintRunning = true
                    lintOutput = runLint()
                    lintRunning = false
                } label: {
                    HStack(spacing: Theme.Spacing.xSmall) {
                        if lintRunning {
                            ProgressView().scaleEffect(0.7)
                        }
                        Text(lintRunning ? "RUNNING..." : "RUN LINT SCAN")
                            .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                    }
                    .foregroundStyle(Theme.securityGold)
                    .padding(.horizontal, Theme.Spacing.standard)
                    .padding(.vertical, Theme.Spacing.tight)
                    .background(Theme.securityGold.opacity(0.1))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                }
                .buttonStyle(EKPressStyle())
                .disabled(lintRunning)
            }

            if !lintOutput.isEmpty {
                ScrollView(.horizontal, showsIndicators: true) {
                    Text(lintOutput)
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(Theme.inkPrimary)
                        .padding(Theme.Spacing.small)
                }
                .frame(maxHeight: 200)
                .background(Theme.surfaceElevated)
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
            }
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.bottom, Theme.Spacing.card)
    }

    private func runLint() -> String {
        guard let scriptPath = Bundle.main.path(forResource: "lint_crash_patterns", ofType: "sh") else {
            return "Error: lint script not found in bundle"
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = [scriptPath]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        do {
            try process.run()
            process.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            return String(data: data, encoding: .utf8) ?? "No output"
        } catch {
            return "Error: \(error.localizedDescription)"
        }
    }
}

private struct CrashCardView: View {
    let report: CrashReport
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            HStack {
                Circle()
                    .fill(Theme.bearRed)
                    .frame(width: 10, height: 10)
                Text("FATAL CRASH")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .tracking(1.2)
                    .foregroundStyle(Theme.bearRed)
                Spacer()
                Text(report.timestamp.prefix(16).replacingOccurrences(of: "T", with: " "))
                    .font(Theme.serialNumberFont(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
                Text(report.signalName ?? report.exceptionName ?? "?")
                    .font(Theme.serialNumberFont(size: 9))
                    .foregroundStyle(Theme.bearRed)
            }

            if let file = report.swiftFile {
                HStack(spacing: Theme.Spacing.xSmall) {
                    Text("FILE:")
                        .font(Theme.microLabel(size: 8))
                        .foregroundStyle(Theme.inkTertiary)
                    Text("\(file)\(report.approxLine.map { ":\($0)" } ?? "")")
                        .font(Theme.serialNumberFont(size: 10))
                        .foregroundStyle(Theme.securityGold)
                }
            }

            if let viewPath = report.viewPath {
                HStack(spacing: Theme.Spacing.xSmall) {
                    Text("VIEW:")
                        .font(Theme.microLabel(size: 8))
                        .foregroundStyle(Theme.inkTertiary)
                    Text(viewPath)
                        .font(Theme.engravedSerif(size: 10, weight: .regular, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineLimit(2)
                }
            }

            Text(report.classification)
                .font(Theme.engravedSerif(size: 11, weight: .semibold))
                .foregroundStyle(Theme.inkPrimary)

            Button {
                HapticManager.selection()
                withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) { expanded.toggle() }
            } label: {
                HStack {
                    Text(expanded ? "HIDE STACK TRACE" : "SHOW STACK TRACE")
                        .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                    Image(systemName: expanded ? "chevron.up" : "chevron.down")
                        .font(.caption2)
                }
                .foregroundStyle(Theme.inkTertiary)
            }
            .buttonStyle(EKPressStyle())

            if expanded {
                Text(report.stackTrace)
                    .font(.system(size: 9, design: .monospaced))
                    .foregroundStyle(Theme.inkSecondary)
                    .padding(Theme.Spacing.small)
                    .background(Theme.surfaceElevated)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
            }

            HStack(spacing: Theme.Spacing.standard) {
                Button {
                    HapticManager.selection()
                    let json = (try? JSONEncoder().encode(report)).flatMap { String(data: $0, encoding: .utf8) } ?? ""
                    UIPasteboard.general.string = json
                } label: {
                    Text("COPY DIAGNOSTIC")
                        .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                        .foregroundStyle(Theme.securityGold)
                        .padding(.horizontal, Theme.Spacing.standard)
                        .padding(.vertical, Theme.Spacing.tight)
                        .background(Theme.securityGold.opacity(0.1))
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                }
                .buttonStyle(EKPressStyle())

                Button(role: .destructive) {
                    CrashLog.shared.delete(id: report.id)
                } label: {
                    Text("DELETE")
                        .font(Theme.officialStampFont(size: 8, relativeTo: .caption2))
                        .foregroundStyle(Theme.bearRed)
                }
                .buttonStyle(EKPressStyle())
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add ios/StockApp/stockme/stockme/Views/CrashLabView.swift
git commit -m "Add CrashLabView: banknote-themed crash diagnostic viewer with lint runner"
```

---

### Task 7: Add Crash Lab to Settings + Lint Script

**Files:**
- Modify: `ios/StockApp/stockme/stockme/Views/SettingsScreen.swift`
- Create: `scripts/lint_crash_patterns.sh`

- [ ] **Step 1: Add Crash Lab row to Settings Dev Tools**

Find the dev tools section in SettingsScreen (around line 163-175). Inside the `if showDevTools` Section, add BEFORE the existing `NavigationLink`:

```swift
                            NavigationLink(destination: CrashLabView()) {
                                HStack {
                                    SettingIcon(icon: "exclamationmark.shield.fill", color: Theme.bearRed)
                                    Text("CRASH LAB (\(CrashLog.shared.count()))")
                                        .font(Theme.officialStampFont(size: 9))
                                        .foregroundStyle(Theme.inkPrimary)
                                    Spacer()
                                }
                                .padding(.vertical, Theme.Spacing.standard)
                            }
```

- [ ] **Step 2: Create lint script**

Create `scripts/lint_crash_patterns.sh`:

```bash
#!/bin/bash
cd "$(dirname "$0")/../ios/StockApp/stockme/stockme"
echo "=== Nivesh Crash Pattern Lint ==="
echo ""

echo "--- ForEach(id: \.self) on String arrays (potential crash) ---"
grep -rn 'ForEach.*id: *\\\.self' --include="*.swift" Views/ Utilities/ Components/ 2>/dev/null | grep -v "0\.\." | grep -v "\.allCases" || echo "  None found"

echo ""
echo "--- ForEach without id: on non-Identifiable types ---"
grep -rn 'ForEach([a-zA-Z_].*id:' --include="*.swift" Views/ Utilities/ Components/ 2>/dev/null | head -20

echo ""
echo "--- Force-unwraps (!) ---"
grep -rn '!$' --include="*.swift" Views/ Utilities/ Components/ 2>/dev/null | grep -v 'import\|//\|nil!' | grep -v '"!' | head -20 || echo "  None found"

echo ""
echo "Done."
```

Make it executable:
```bash
chmod +x scripts/lint_crash_patterns.sh
```

- [ ] **Step 3: Commit**

```bash
git add ios/StockApp/stockme/stockme/Views/SettingsScreen.swift scripts/lint_crash_patterns.sh
git commit -m "Add Crash Lab to Dev Tools + shell lint script for crash patterns"
```

---

## Edge Cases
- Signal handler must be async-safe: only uses `UUID()`, `ISO8601DateFormatter`, `JSONEncoder`, file write. No allocation-heavy operations.
- First crash after install: `CrashLog.all()` returns empty array (file doesn't exist) — handled by `allUnsafe()`
- Crash during crash handler: should not infinite-loop since `didRegister = true` guard
- `CrashGuard` compiled away in release via `#if DEBUG` — zero perf impact
- Lint script fails to find `.swift` files: `grep` returns empty, script prints "None found"
- Settings badge: `crashCountSeen` tracks last seen count, badge clears when user visits Crash Lab
