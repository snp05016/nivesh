import SwiftUI

/// Multiple-choice check at the end of a lesson. Answers are graded server-side;
/// after submitting, each question shows correct / not and the explanation.
struct QuizView: View {
    @StateObject private var vm: LabQuizViewModel

    init(lessonId: String, questions: [LabQuizQuestion]) {
        _vm = StateObject(wrappedValue: LabQuizViewModel(lessonId: lessonId, questions: questions))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            LabCardTitle(title: "Check your understanding", icon: "checkmark.bubble")
            ForEach(Array(vm.questions.enumerated()), id: \.element.id) { index, q in
                LabQuestionCard(number: index + 1, question: q, pick: vm.picks[q.id], graded: vm.graded(q.id),
                                locked: vm.grade != nil) { choice in
                    HapticManager.selection()
                    vm.picks[q.id] = choice
                }
            }
            if let grade = vm.grade { LabGradeSummary(grade: grade, onRetake: vm.retake) }
            if let error = vm.error { LabInlineError(message: error) }
            if vm.grade == nil {
                Button {
                    HapticManager.selection()
                    Task { await vm.submit() }
                } label: {
                    LabPrimaryLabel(title: "Submit answers", icon: "paperplane", busy: vm.isGrading, enabled: vm.canSubmit)
                }
                .buttonStyle(EKPressStyle())
                .disabled(!vm.canSubmit)
            }
        }
    }
}

private struct LabQuestionCard: View {
    let number: Int
    let question: LabQuizQuestion
    let pick: Int?
    let graded: LabGradedQuestion?
    let locked: Bool
    let onPick: (Int) -> Void

    var body: some View {
        LabCard {
            Text("\(number). \(question.q ?? "")")
                .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
                .fixedSize(horizontal: false, vertical: true)
            ForEach(Array((question.choices ?? []).enumerated()), id: \.offset) { i, choice in
                Button { onPick(i) } label: {
                    LabChoiceRow(text: choice, selected: pick == i, isAnswer: graded?.answer == i, graded: graded != nil)
                }
                .buttonStyle(EKPressStyle())
                .disabled(locked)
            }
            if let g = graded { LabExplanation(graded: g) }
        }
    }
}

private struct LabChoiceRow: View {
    let text: String
    let selected: Bool
    let isAnswer: Bool
    let graded: Bool

    private var tint: Color {
        if graded && isAnswer { return Theme.bullGreen }
        if graded && selected { return Theme.bearRed }
        return selected ? Theme.securityGold : Theme.inkTertiary
    }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
            Image(systemName: selected ? "largecircle.fill.circle" : "circle")
                .foregroundStyle(tint)
                .accessibilityHidden(true)
            Text(text)
                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
                .multilineTextAlignment(.leading)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(Theme.Spacing.medium)
        .frame(minHeight: 44)
        .background(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).fill(tint.opacity(selected || (graded && isAnswer) ? 0.12 : 0.04)))
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(selected ? .isSelected : [])
        .accessibilityValue(graded && isAnswer ? "Correct answer" : "")
    }
}

private struct LabExplanation: View {
    let graded: LabGradedQuestion

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Label(graded.correct == true ? "Correct" : "Not quite",
                  systemImage: graded.correct == true ? "checkmark.circle.fill" : "xmark.circle.fill")
                .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .footnote))
                .foregroundStyle(graded.correct == true ? Theme.bullGreen : Theme.bearRed)
            if let e = graded.explain {
                Text(LabFormat.markdown(e))
                    .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

private struct LabGradeSummary: View {
    let grade: LabGrade
    let onRetake: () -> Void

    var body: some View {
        LabCard {
            HStack {
                LabScoreRing(score: (grade.score ?? 0) * 100, label: "Quiz score")
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(grade.passed == true ? "Lesson complete" : "Review and try again")
                        .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .headline))
                        .foregroundStyle(grade.passed == true ? Theme.bullGreen : Theme.holdAmber)
                    Button {
                        HapticManager.selection()
                        onRetake()
                    } label: {
                        Text("Retake quiz").font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .footnote))
                            .foregroundStyle(Theme.securityGold).frame(minHeight: 44)
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
        }
    }
}
