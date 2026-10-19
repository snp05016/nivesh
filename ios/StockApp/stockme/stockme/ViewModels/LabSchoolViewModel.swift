import Foundation
import Combine

/// Quiz state for one lesson: one pick per question, then POST .../grade.
@MainActor
final class LabQuizViewModel: ObservableObject {
    @Published var picks: [String: Int] = [:]
    @Published private(set) var grade: LabGrade?
    @Published private(set) var isGrading = false
    @Published private(set) var error: String?

    let lessonId: String
    let questions: [LabQuizQuestion]

    init(lessonId: String, questions: [LabQuizQuestion]) {
        self.lessonId = lessonId
        self.questions = questions
    }

    var canSubmit: Bool { !isGrading && grade == nil && picks.count == questions.count }

    func graded(_ questionId: String) -> LabGradedQuestion? {
        grade?.perQuestion?.first { $0.id == questionId }
    }

    func submit() async {
        guard canSubmit else { return }
        isGrading = true
        error = nil
        defer { isGrading = false }
        do {
            grade = try await NetworkManager.shared.labGrade(lessonId: lessonId,
                                                             answers: questions.map { picks[$0.id] ?? -1 })
            grade?.passed == true ? HapticManager.success() : HapticManager.warning()
        } catch where LabErrors.isCancellation(error) {
            return
        } catch {
            self.error = LabErrors.message(error)
        }
    }

    func retake() {
        picks = [:]
        grade = nil
    }
}

/// School home: curriculum, progress and the "recommended for you" list, loaded together.
struct LabSchoolHome {
    let curriculum: LabCurriculum
    let progress: LabProgress?
    let next: [LabRecommendation]

    static func fetch() async throws -> LabSchoolHome {
        async let cur = NetworkManager.shared.labCurriculum()
        async let prog = try? NetworkManager.shared.labProgress()
        async let nxt = try? NetworkManager.shared.labNextLessons()
        return LabSchoolHome(curriculum: try await cur, progress: await prog, next: await nxt?.lessons ?? [])
    }
}
