import SwiftUI

// MARK: - Create Thread

struct CreateThreadView: View {
    @StateObject private var vm: CreateThreadViewModel
    @Environment(\.dismiss) private var dismiss

    /// Invoked with the newly created thread right before the sheet dismisses,
    /// so the caller (board thread list, forum hub) can refresh in place.
    var onCreated: ((ForumThreadDetail) -> Void)? = nil

    init(preselectedBoard: ForumBoard? = nil, onCreated: ((ForumThreadDetail) -> Void)? = nil) {
        _vm = StateObject(wrappedValue: CreateThreadViewModel(preselectedBoard: preselectedBoard))
        self.onCreated = onCreated
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                    BoardPickerSection(vm: vm)
                        .padding(.horizontal, Theme.screenPadding)

                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                    ThreadFieldsSection(vm: vm)
                        .padding(.horizontal, Theme.screenPadding)

                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                    PollComposerSection(vm: vm)
                        .padding(.horizontal, Theme.screenPadding)

                    if let error = vm.errorMessage {
                        Text(error)
                            .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                            .foregroundColor(Theme.bearRed)
                            .padding(.horizontal, Theme.screenPadding)
                    }
                }
                .padding(.vertical, Theme.screenPadding)
            }
            .background(Theme.canvas.ignoresSafeArea())
            .navigationTitle("New Thread")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        HapticManager.selection()
                        dismiss()
                    }
                    .foregroundColor(Theme.inkSecondary)
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        HapticManager.selection()
                        vm.submit { success in
                            if success {
                                HapticManager.success()
                                if let created = vm.createdThread {
                                    onCreated?(created)
                                }
                                dismiss()
                            } else {
                                HapticManager.error()
                            }
                        }
                    } label: {
                        if vm.isSubmitting {
                            ProgressView().tint(Theme.securityGold)
                        } else {
                            Text("Post")
                                .font(Theme.labelStyle)
                        }
                    }
                    .disabled(!vm.isValid || vm.isSubmitting)
                    .foregroundColor(vm.isValid ? Theme.securityGold : Theme.inkTertiary)
                }
            }
        }
    }
}

// MARK: - Board Picker

private struct BoardPickerSection: View {
    @ObservedObject var vm: CreateThreadViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("BOARD")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)

            Menu {
                ForEach(vm.boards) { board in
                    Button(board.name) {
                        HapticManager.selection()
                        vm.selectedBoardId = board.id
                    }
                }
            } label: {
                HStack {
                    Text(vm.boards.first(where: { $0.id == vm.selectedBoardId })?.name ?? "Select a board")
                        .font(Theme.engravedSerif(size: 15, relativeTo: .body))
                        .foregroundColor(Theme.inkPrimary)
                    Spacer()
                    Image(systemName: "chevron.up.chevron.down")
                        .font(.system(size: 12))
                        .foregroundColor(Theme.inkTertiary)
                }
                .padding(Theme.Spacing.card)
                .banknoteCard()
            }
            .buttonStyle(EKPressStyle())
        }
    }
}

// MARK: - Title / Body

private struct ThreadFieldsSection: View {
    @ObservedObject var vm: CreateThreadViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                Text("TITLE")
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.5)
                    .foregroundColor(Theme.inkSecondary)
                TextField("What's your thread about?", text: $vm.title)
                    .font(Theme.engravedSerif(size: 15, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
                    .padding(Theme.Spacing.card)
                    .banknoteCard()
            }

            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                Text("BODY")
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.5)
                    .foregroundColor(Theme.inkSecondary)
                TextField("Share your analysis, question, or view…", text: $vm.body, axis: .vertical)
                    .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
                    .lineLimit(4...10)
                    .padding(Theme.Spacing.card)
                    .banknoteCard()
            }
        }
    }
}

// MARK: - Poll Composer

private struct PollComposerSection: View {
    @ObservedObject var vm: CreateThreadViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Toggle(isOn: $vm.includesPoll.animation()) {
                Text("Add a poll")
                    .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .subheadline))
                    .foregroundColor(Theme.inkPrimary)
            }
            .tint(Theme.securityGold)
            .onChange(of: vm.includesPoll) { _, _ in HapticManager.selection() }

            if vm.includesPoll {
                TextField("Poll question", text: $vm.pollQuestion)
                    .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
                    .padding(Theme.Spacing.card)
                    .banknoteCard()

                ForEach($vm.pollOptions) { $option in
                    let number = (vm.pollOptions.firstIndex { $0.id == option.id } ?? 0) + 1
                    HStack(spacing: Theme.Spacing.standard) {
                        TextField("Option \(number)", text: $option.text)
                            .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                            .foregroundColor(Theme.inkPrimary)
                            .padding(Theme.Spacing.card)
                            .banknoteCard()

                        if vm.pollOptions.count > 2 {
                            Button {
                                HapticManager.selection()
                                vm.removePollOption(id: option.id)
                            } label: {
                                Image(systemName: "minus.circle.fill")
                                    .foregroundColor(Theme.bearRed)
                            }
                            .buttonStyle(EKPressStyle())
                        }
                    }
                }

                if vm.pollOptions.count < 6 {
                    Button {
                        HapticManager.selection()
                        vm.addPollOption()
                    } label: {
                        HStack(spacing: Theme.Spacing.xSmall) {
                            Image(systemName: "plus.circle.fill")
                            Text("Add Option")
                        }
                        .font(Theme.labelStyle)
                        .foregroundColor(Theme.securityGold)
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
        }
    }
}
