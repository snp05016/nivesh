import Foundation
import Combine

/// Question -> (translate) -> editable feature program -> live compile check -> run.
@MainActor
final class LabHypothesisViewModel: ObservableObject {
    static let horizons = [1, 5, 10, 20]

    @Published var question = ""
    @Published var program = "" { didSet { if program != oldValue { scheduleCompile() } } }
    @Published var score = ""
    @Published var horizon = 5
    @Published var direction = 1
    @Published var start = "2015-01-01"
    @Published var end = LabHypothesisViewModel.defaultEnd()
    @Published var useHoldout = false

    @Published private(set) var templates: [LabTemplate] = []
    @Published private(set) var templatesNote: String?
    @Published private(set) var translation: LabTranslation?
    @Published private(set) var isTranslating = false
    @Published private(set) var compile: LabCompileResult?
    @Published private(set) var isCompiling = false
    @Published private(set) var isRunning = false
    @Published var error: String?
    @Published var lastRun: LabExperimentRecord?
    @Published var showReport = false

    private var compileTask: Task<Void, Never>?
    private var templatesTask: Task<Void, Never>?

    var compiles: Bool { compile?.ok == true }
    var outputNames: [String] { compile?.outputs?.compactMap(\.name) ?? [] }
    var canRun: Bool { compiles && !score.isEmpty && outputNames.contains(score) && !isRunning }

    func loadTemplatesIfNeeded() {
        guard templates.isEmpty, templatesTask == nil else { return }
        templatesTask = Task { [weak self] in
            let result = try? await NetworkManager.shared.labTemplates()
            self?.templates = result?.templates ?? []
            self?.templatesNote = result?.unavailableFieldsNote
            self?.templatesTask = nil
        }
    }

    func cancel() {
        compileTask?.cancel()
        templatesTask?.cancel()
        templatesTask = nil
    }

    func apply(_ t: LabTemplate) {
        program = t.program ?? ""
        score = t.score ?? ""
        if let h = t.horizon, Self.horizons.contains(h) { horizon = h }
        if question.isEmpty { question = t.title ?? "" }
    }

    func translate() async {
        let q = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty, !isTranslating else { return }
        isTranslating = true
        error = nil
        defer { isTranslating = false }
        do {
            let t = try await NetworkManager.shared.labTranslate(question: q)
            translation = t
            if let spec = t.spec {
                if let p = spec.program { program = p }
                if let s = spec.score { score = s }
                if let h = spec.horizon, Self.horizons.contains(h) { horizon = h }
                if let d = spec.direction, d == 1 || d == -1 { direction = d }
            }
        } catch where LabErrors.isCancellation(error) {
            return
        } catch {
            self.error = LabErrors.message(error)
        }
    }

    /// Debounced: compiles 0.6 s after the last edit.
    private func scheduleCompile() {
        compileTask?.cancel()
        let source = program
        guard !source.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { compile = nil; return }
        compileTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 600_000_000)
            guard !Task.isCancelled else { return }
            await self?.runCompile(source)
        }
    }

    private func runCompile(_ source: String) async {
        isCompiling = true
        defer { isCompiling = false }
        guard let result = try? await NetworkManager.shared.labCompile(program: source), !Task.isCancelled else { return }
        compile = result
        if result.ok == true, !outputNames.contains(score), let first = outputNames.first { score = first }
    }

    var specJSON: [String: Any] {
        ["question": question, "program": program, "score": score, "start": start, "end": end,
         "horizon": horizon, "direction": direction, "universe_n": 50, "use_holdout": useHoldout]
    }

    func run() async {
        guard canRun else { return }
        isRunning = true
        error = nil
        defer { isRunning = false }
        do {
            lastRun = try await NetworkManager.shared.labRunExperiment(spec: specJSON)
            HapticManager.success()
            showReport = true
        } catch where LabErrors.isCancellation(error) {
            return
        } catch {
            self.error = LabErrors.message(error)
            HapticManager.warning()
        }
    }

    /// Price data younger than 30 days is not used (LAB_MIN_DATA_AGE_DAYS).
    static func defaultEnd(now: Date = Date()) -> String {
        WireDate.dayFormatter.string(from: now.addingTimeInterval(-45 * 86_400))
    }
}
