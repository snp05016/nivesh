import SwiftUI

/// Trader School home: recommended lessons (with the reason), then each track with progress.
struct SchoolHomeView: View {
    @StateObject private var vm = LabLoadViewModel<LabSchoolHome>(isEmpty: { ($0.curriculum.lessons ?? []).isEmpty }) {
        try await LabSchoolHome.fetch()
    }

    var body: some View {
        LabScreen(title: "Trader School") {
            StateCard(title: "lessons", phase: vm.phase, emptyMessage: "No lessons are published yet.", onRetry: vm.load) {
                if let home = vm.value { LabSchoolContent(home: home) }
            }
        }
        .onAppear { vm.loadIfNeeded() }
        .onDisappear { vm.cancel() }
    }
}

private struct LabSchoolContent: View {
    let home: LabSchoolHome

    private var tracks: [String] {
        let lessons = home.curriculum.lessons ?? []
        let declared = home.curriculum.tracks ?? []
        let extra = lessons.compactMap(\.track).filter { !declared.contains($0) }
        return declared + Array(Set(extra)).sorted()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            if !home.next.isEmpty { LabRecommendedCard(items: home.next) }
            ForEach(tracks, id: \.self) { track in
                LabTrackCard(track: track,
                             lessons: (home.curriculum.lessons ?? []).filter { $0.track == track },
                             completed: Set(home.progress?.completed ?? []))
            }
        }
    }
}

private struct LabRecommendedCard: View {
    let items: [LabRecommendation]

    var body: some View {
        LabCard {
            LabCardTitle(title: "Recommended for you", icon: "sparkles")
            ForEach(items) { rec in
                if let id = rec.lessonId {
                    NavigationLink(value: LabRoute.lesson(id: id)) { LabRecommendationRow(rec: rec) }
                        .buttonStyle(EKPressStyle())
                        .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
                }
            }
        }
    }
}

private struct LabRecommendationRow: View {
    let rec: LabRecommendation

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(rec.title ?? "Lesson")
                    .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .subheadline))
                    .foregroundStyle(Theme.inkPrimary)
                Text("Why: \(rec.reason ?? "next in sequence")")
                    .font(Theme.microLabel())
                    .foregroundStyle(Theme.securityGold)
            }
            Spacer()
            Image(systemName: "chevron.right").font(.caption).foregroundStyle(Theme.inkTertiary).accessibilityHidden(true)
        }
        .frame(minHeight: 44)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
    }
}

private struct LabTrackCard: View {
    let track: String
    let lessons: [LabLessonSummary]
    let completed: Set<String>

    private var done: Int { lessons.filter { completed.contains($0.id) }.count }

    var body: some View {
        LabCard {
            HStack {
                LabCardTitle(title: track, icon: "graduationcap")
                Spacer()
                Text("\(done)/\(lessons.count)").font(Theme.monoTabular(size: 13)).foregroundStyle(Theme.inkSecondary)
            }
            ProgressView(value: lessons.isEmpty ? 0 : Double(done) / Double(lessons.count))
                .tint(Theme.bullGreen)
                .accessibilityLabel("\(track) track: \(done) of \(lessons.count) lessons complete")
            ForEach(lessons) { l in
                NavigationLink(value: LabRoute.lesson(id: l.id)) { LabLessonRow(lesson: l, done: completed.contains(l.id)) }
                    .buttonStyle(EKPressStyle())
                    .simultaneousGesture(TapGesture().onEnded { HapticManager.selection() })
            }
        }
    }
}

private struct LabLessonRow: View {
    let lesson: LabLessonSummary
    let done: Bool

    var body: some View {
        HStack(spacing: Theme.Spacing.medium) {
            Image(systemName: done ? "checkmark.circle.fill" : "circle")
                .foregroundStyle(done ? Theme.bullGreen : Theme.inkTertiary)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(lesson.title ?? lesson.id)
                    .font(Theme.engravedSerif(size: 14, relativeTo: .subheadline))
                    .foregroundStyle(Theme.inkPrimary)
                Text("\(lesson.minutes ?? 0) min").font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
            }
            Spacer()
        }
        .frame(minHeight: 44)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityValue(done ? "Completed" : "Not completed")
    }
}
