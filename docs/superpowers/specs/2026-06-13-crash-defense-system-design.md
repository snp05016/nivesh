# Crash Defense System — Design Document

> Date: 13 June 2026 | Status: Design Approved | Scope: iOS crash interception + pre-flight linting + Crash Lab viewer

## 1. Architecture Overview

Three-layer defense against SwiftUI/iOS crashes:

| Layer | Component | File | When |
|-------|-----------|------|------|
| **Pre-Flight** | Shell script linter | `scripts/lint_crash_patterns.sh` | Manual / pre-build |
| **Runtime Guard** | View lifecycle logger | `Utilities/CrashGuard.swift` | Debug builds only |
| **Crash Intercept** | Signal/exception handlers + persistence | `Utilities/CrashInterceptor.swift`, `Utilities/CrashLog.swift` | Always on |

## 2. Crash Interception — Signals & Exceptions

### 2.1 Registration (AppDelegate.swift)

`AppDelegate.didFinishLaunching` registers:

**ObjC exceptions:** `NSSetUncaughtExceptionHandler` captures `NSException` objects — name, reason, callStackSymbols (first 20 frames).

**POSIX signals:** `signal()` for SIGABRT, SIGSEGV, SIGBUS, SIGILL, SIGTRAP, SIGFPE. Each handler calls `CrashInterceptor.record()`, then re-raises via `SIG_DFL` so the system crash reporter also fires.

### 2.2 CrashInterceptor.swift

```swift
struct CrashInterceptor {
    static func record(type: CrashType, signal: Int32?, name: String, reason: String?,
                       stackTrace: String, viewPath: String?) {
        let report = CrashReport(
            id: UUID().uuidString,
            timestamp: ISO8601DateFormatter().string(from: Date()),
            type: type,
            signalNumber: signal.map(Int.init),
            signalName: signal.map { String(cString: strsignal($0)) },
            exceptionName: type == .exception ? name : nil,
            exceptionReason: reason,
            stackTrace: stackTrace,
            viewPath: viewPath,
            swiftFile: parseSwiftFile(from: stackTrace),
            approxLine: parseApproxLine(from: stackTrace),
            device: deviceModel(),
            osVersion: UIDevice.current.systemVersion,
            appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?",
            buildNumber: Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "?",
            classification: classify(name: name, reason: reason ?? "")
        )
        CrashLog.shared.append(report)
    }
}
```

### 2.3 Swift File & Line Detection

Parse the first stack frame that contains the app's module name (e.g., "StockApp"). Extract:
- File name from symbol: `AnalysisScreen.(unknown context at 0x...)` → heuristic
- Approx line from the base offset: marked as `~1991` (approximate, since we don't have dSYM on-device)

### 2.4 Crash Classification

Auto-classify crash type from signal name + exception reason:
- "SIGABRT" + "Duplicate keys" → "Duplicate ForEach ID on [String] array"
- "SIGABRT" + "unexpectedly found nil" → "Force-unwrap on nil optional"
- "SIGABRT" + "Modifying state during view update" → "@State mutation in computed property"
- "SIGABRT" + "EnvironmentObject" → "Missing @EnvironmentObject"
- "SIGSEGV" → "Memory access violation (out-of-bounds or deallocated object)"
- Otherwise: raw signal/exception name

### 2.5 CrashLog.swift — Persistence

```swift
class CrashLog {
    static let shared = CrashLog()
    private let fileURL: URL
    private let maxCrashes = 10

    func append(_ report: CrashReport)
    func all() -> [CrashReport]       // newest first
    func count() -> Int
    func delete(id: String)
    func clearAll()
}
```

Stored as `Documents/nivesh_crashes.json`. Synchronous write in signal handler (atomic, minimal data). Older 10+ evicted. Thread-safe via `NSLock`.

## 3. Runtime Guard — View Lifecycle Logger

### 3.1 CrashGuard.swift

```swift
struct CrashGuard: ViewModifier {
    let name: String  // e.g. "aiVerdictCard"
    static private(set) var viewPathStack: [String] = []
    static var lastViewPath: String? { viewPathStack.joined(separator: " > ") }

    func body(content: Content) -> some View {
        content
            .onAppear {
                Self.viewPathStack.append(name)
                os_log(.debug, "CrashGuard: ENTER %{public}@", name)
            }
            .onDisappear {
                Self.viewPathStack.removeAll { $0 == name }
                os_log(.debug, "CrashGuard: EXIT %{public}@", name)
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

### 3.2 Usage

Applied to top-level views in each screen:

```swift
// AnalysisScreen.swift
ScrollView { ... }
    .crashGuard("aiReportScroll")

// HomeScreen.swift  
NavigationStack { ... }
    .crashGuard("HomeScreen")

// ExplainThisSignalCard
VStack { ... }
    .crashGuard("ExplainThisSignalCard")
```

Zero overhead in release builds (`#if DEBUG` guard). When a crash occurs, `CrashGuard.lastViewPath` shows the active view stack (e.g., `"HomeScreen > aiReportScroll > ExplainThisSignalCard"`), pinpointing which view was rendering.

## 4. Pre-Flight Linter — Shell Script

### 4.1 scripts/lint_crash_patterns.sh

```bash
#!/bin/bash
# Scans all .swift files for common crash patterns
cd "$(dirname "$0")/../ios/StockApp/stockme/stockme"

echo "=== Nivesh Crash Pattern Lint ==="
echo ""

# 1. ForEach with id: \.self on [String] arrays
echo "--- ForEach(id: \\.self) on String arrays ---"
grep -rn 'ForEach.*id: *\\\.self' --include="*.swift" Views/ Utilities/ Components/ | grep -v "0\.\." | grep -v "\.allCases"

# 2. Force unwraps (excluding common patterns)
echo ""
echo "--- Force-unwraps (!) ---"
grep -rn '!$' --include="*.swift" Views/ Utilities/ Components/ | grep -v 'import\|//\|nil!'

# 3. @State mutation in computed properties
echo ""
echo "--- @State mutation in computed vars ---"
# Complex: scan for 'var.*:.*\{' followed by '@State' property set
grep -rn '@State' --include="*.swift" Views/ | cut -d: -f1 | sort -u | while read f; do
    # Check if any computed property modifies a @State var
    awk '/var [a-zA-Z]+:.*\{/,/^\s{4}\}/' "$f" 2>/dev/null | grep -q '=.*true\|=.*false\|=.*""\|=.*\[\]' && echo "  $f: potential @State mutation in computed property"
done
```

### 4.2 Manual Execution

```bash
cd /Users/saumya/Desktop/nivesh
bash scripts/lint_crash_patterns.sh
```

Output to terminal. In Crash Lab, "RUN LINT SCAN" button executes this via `Process()` and displays output in a monospaced scroll view.

## 5. Crash Lab — Diagnostic Viewer

### 5.1 CrashLabView.swift

Full banknote-themed crash viewer at `Views/CrashLabView.swift`:

```
NavigationStack {
    DenominationBackground(.fifty)
    
    if crashes.isEmpty {
        // Empty state: "No crashes recorded" + Hindi reassurance
    } else {
        ScrollView {
            ForEach(crashes) { crash in
                CrashCard(report: crash)
            }
        }
    }
    
    // Lint Report card at bottom
    LintReportCard()
}
```

### 5.2 CrashCard — per-crash display

- Red "FATAL CRASH" badge
- Signal/exception name + timestamp
- "FILE: AnalysisScreen.swift:~1991"
- "VIEW: aiReportScroll > ExplainThisSignalCard"
- Auto-classification text (e.g., "Duplicate ForEach ID on [String] array")
- Collapsible stack trace in monospaced font
- "COPY DIAGNOSTIC" → UIPasteboard with full JSON
- "DELETE" → removes from CrashLog

### 5.3 LintReportCard

- "LINT REPORT" section header
- "Last run: [timestamp or 'never']"
- "RUN LINT SCAN" button → executes lint script
- Monospaced output display in scrollable section

### 5.4 Entry Point (SettingsScreen.swift)

In the Developer Tools Section (hidden behind triple-tap):
```swift
if showDevTools {
    Section {
        NavigationLink("Crash Lab (\(CrashLog.shared.count()))") {
            CrashLabView()
        }
        // existing dev tools...
    }
}
```

Crash count badge updates on appear via `CrashLog.shared.count()`.

### 5.5 Settings Badge (stockmeApp.swift)

On boot, check `CrashLog.shared.count()`. If > 0 and > last checked count, show a red badge on Settings tab. Badge clears when user opens Crash Lab.

## 6. CrashReport Model (Models.swift)

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

## 7. Files Created & Modified

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/lint_crash_patterns.sh` | Create | Shell linter |
| `Utilities/CrashGuard.swift` | Create | View lifecycle logger |
| `Utilities/CrashLog.swift` | Create | Crash persistence |
| `Utilities/CrashInterceptor.swift` | Create | Signal/exception handlers |
| `Views/CrashLabView.swift` | Create | Diagnostic viewer |
| `AppDelegate.swift` | Modify | Register handlers |
| `stockmeApp.swift` | Modify | Crash-on-restart detection |
| `Views/SettingsScreen.swift` | Modify | Add Crash Lab row |
| `Models.swift` | Modify | Add CrashReport struct |

---
