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
