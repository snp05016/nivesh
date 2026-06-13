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
