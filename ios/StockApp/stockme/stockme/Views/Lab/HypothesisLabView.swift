import SwiftUI

/// Question -> feature program (FDL) -> compile check -> experiment with skeptic review.
struct HypothesisLabView: View {
    @StateObject private var vm = LabHypothesisViewModel()

    var body: some View {
        LabScreen(title: "Hypothesis Lab") {
            LabQuestionCard(vm: vm)
            if !vm.templates.isEmpty { LabTemplateChips(templates: vm.templates, note: vm.templatesNote, onPick: vm.apply) }
            LabProgramCard(vm: vm)
            LabRunSettingsCard(vm: vm)
            if let error = vm.error { LabInlineError(message: error) }
            Button {
                HapticManager.selection()
                Task { await vm.run() }
            } label: {
                LabPrimaryLabel(title: vm.isRunning ? "Running the experiment…" : "Run experiment", icon: "play.fill",
                                busy: vm.isRunning, enabled: vm.canRun)
            }
            .buttonStyle(EKPressStyle())
            .disabled(!vm.canRun)
            Text("Each run is logged in your ledger and raises the bar for the next one (the deflated Sharpe accounts for every trial).")
                .font(Theme.microLabel())
                .foregroundStyle(Theme.inkTertiary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .onAppear { vm.loadTemplatesIfNeeded() }
        .onDisappear { vm.cancel() }
        .navigationDestination(isPresented: $vm.showReport) {
            if let run = vm.lastRun { ExperimentReportView(record: run) }
        }
    }
}

private struct LabQuestionCard: View {
    @ObservedObject var vm: LabHypothesisViewModel

    var body: some View {
        LabCard {
            LabCardTitle(title: "Your question", icon: "questionmark.bubble")
            TextField("e.g. Do stocks near their 52-week high keep outperforming over the next month?",
                      text: $vm.question, axis: .vertical)
                .lineLimit(2...5)
                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
            Button {
                HapticManager.selection()
                Task { await vm.translate() }
            } label: {
                LabPrimaryLabel(title: vm.isTranslating ? "Translating…" : "Translate into a testable score",
                                icon: "wand.and.stars", busy: vm.isTranslating,
                                enabled: !vm.question.isEmpty && !vm.isTranslating)
            }
            .buttonStyle(EKPressStyle())
            .disabled(vm.question.isEmpty || vm.isTranslating)
            if let t = vm.translation { LabTranslationNote(translation: t) }
        }
    }
}

private struct LabTranslationNote: View {
    let translation: LabTranslation

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            if let mode = translation.mode {
                LabChip(text: mode == "llm" ? "AI draft" : "Rules draft", tint: Theme.inkSecondary, icon: "doc.text")
            }
            if let e = translation.explanation {
                Text(LabFormat.markdown(e)).font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkSecondary).fixedSize(horizontal: false, vertical: true)
            }
            if let missing = translation.missingData, !missing.isEmpty {
                Label("Not testable yet, data missing: \(missing.joined(separator: ", "))", systemImage: "externaldrive.badge.xmark")
                    .font(Theme.microLabel()).foregroundStyle(Theme.holdAmber)
            }
        }
    }
}

private struct LabTemplateChips: View {
    let templates: [LabTemplate]
    let note: String?
    let onPick: (LabTemplate) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            LabCardTitle(title: "Start from a published hypothesis", icon: "books.vertical")
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: Theme.Spacing.small) {
                    ForEach(templates) { t in
                        Button {
                            HapticManager.selection()
                            onPick(t)
                        } label: { LabChip(text: t.title ?? t.id).frame(minHeight: 44) }
                        .buttonStyle(EKPressStyle())
                        .accessibilityHint(t.reference.map { "Based on \($0)" } ?? "")
                    }
                }
            }
            if let note {
                Text(note).font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary).fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

private struct LabProgramCard: View {
    @ObservedObject var vm: LabHypothesisViewModel

    var body: some View {
        LabCard {
            HStack {
                LabCardTitle(title: "Feature program", icon: "chevron.left.forwardslash.chevron.right")
                Spacer()
                LabCompileBadge(compiling: vm.isCompiling, result: vm.compile)
            }
            TextEditor(text: $vm.program)
                .font(Theme.monoTabular(size: 13))
                .foregroundStyle(Theme.inkPrimary)
                .scrollContentBackground(.hidden)
                .frame(minHeight: 120)
                .padding(Theme.Spacing.small)
                .background(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).fill(Theme.canvas.opacity(0.05)))
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)
                .accessibilityLabel("Feature program")
            if let r = vm.compile, r.ok == false {
                LabInlineError(message: "Line \(r.line ?? 0), column \(r.col ?? 0): \(r.error ?? "does not compile")")
            }
            if !vm.outputNames.isEmpty {
                Picker("Score to test", selection: $vm.score) {
                    ForEach(vm.outputNames, id: \.self) { Text($0).tag($0) }
                }
                .tint(Theme.securityGold)
            }
            if let out = vm.compile?.outputs?.first(where: { $0.name == vm.score }) { LabLineageNote(output: out) }
        }
    }
}

private struct LabCompileBadge: View {
    let compiling: Bool
    let result: LabCompileResult?

    var body: some View {
        if compiling {
            ProgressView().accessibilityLabel("Checking the program")
        } else if let result {
            LabChip(text: result.ok == true ? "Compiles" : "Error",
                    tint: result.ok == true ? Theme.bullGreen : Theme.bearRed,
                    icon: result.ok == true ? "checkmark" : "xmark")
        }
    }
}

private struct LabLineageNote: View {
    let output: LabCompileOutput

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            LabKeyValueRow(key: "Uses fields", value: (output.lineage ?? []).joined(separator: ", "))
            LabKeyValueRow(key: "Warm-up", value: "\(output.warmupBars ?? 0) bars")
            LabKeyValueRow(key: "Known at", value: output.availability?.display ?? "—")
        }
    }
}

private struct LabRunSettingsCard: View {
    @ObservedObject var vm: LabHypothesisViewModel

    var body: some View {
        LabCard {
            LabCardTitle(title: "Test design", icon: "slider.horizontal.3")
            Picker("Holding horizon", selection: $vm.horizon) {
                ForEach(LabHypothesisViewModel.horizons, id: \.self) { Text("\($0)d").tag($0) }
            }
            .pickerStyle(.segmented)
            .accessibilityLabel("Holding horizon in trading days")
            Picker("Direction", selection: $vm.direction) {
                Text("Higher score is better").tag(1)
                Text("Lower score is better").tag(-1)
            }
            .pickerStyle(.segmented)
            HStack {
                LabDateField(label: "From", text: $vm.start)
                LabDateField(label: "To", text: $vm.end)
            }
            Toggle("Also run the untouched holdout (single use)", isOn: $vm.useHoldout)
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .tint(Theme.securityGold)
        }
        .onChange(of: vm.horizon) { _, _ in HapticManager.selection() }
    }
}

private struct LabDateField: View {
    let label: String
    @Binding var text: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(label).font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary)
            TextField("YYYY-MM-DD", text: $text)
                .font(Theme.monoTabular(size: 13))
                .keyboardType(.numbersAndPunctuation)
                .accessibilityLabel("\(label) date, year month day")
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
