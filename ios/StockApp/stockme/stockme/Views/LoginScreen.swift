import SwiftUI
import UIKit

struct LoginScreen: View {
    @EnvironmentObject var authManager: AuthManager

    @State private var isRegistering = false
    @State private var username = ""
    @State private var password = ""
    @State private var displayName = ""
    @State private var showPassword = false
    @State private var acceptedPolicy = false
    @State private var ageConfirmed = false
    @FocusState private var focusedField: Field?

    enum Field { case username, password, displayName }

    var body: some View {
        ZStack {
            // The Banknote Canvas
            PaperTexture()
            
            // Background Medallions
            BanknoteWatermark(text: "NIVESH", size: 120, opacity: 0.02, alignment: .topLeading)
            BanknoteWatermark(text: "निवेश", size: 100, opacity: 0.015, alignment: .bottomTrailing)

            ScrollView {
                VStack(spacing: Theme.Spacing.none) {
                    // Header (Denomination Style)
                    VStack(spacing: Theme.Spacing.card) {
                        ZStack {
                            Circle()
                                .stroke(Theme.inkSecondary.opacity(0.3), lineWidth: 1)
                                .frame(width: 80, height: 80)
                            Text("₹")
                                .font(Theme.engravedSerif(size: 40, weight: .bold, relativeTo: .largeTitle))
                                .foregroundStyle(Theme.inkPrimary)
                        }
                        .padding(.top, Theme.Spacing.xLarge * 2)
                        .staggerAppear(delay: 0.1)

                        VStack(spacing: Theme.Spacing.small) {
                            Text("निवेश / NIVESH")
                                .font(Theme.engravedSerif(size: 34, weight: .bold, relativeTo: .largeTitle))
                                .foregroundStyle(Theme.inkPrimary)
                            Text(isRegistering ? "CREATE ACCOUNT" : "SIGN IN")
                                .font(Theme.labelStyle)
                                .foregroundStyle(Theme.inkSecondary)
                        }
                        .staggerAppear(delay: 0.2)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.bottom, Theme.Spacing.xLarge)

                    // Entry Form
                    VStack(spacing: Theme.Spacing.large) {
                        VStack(spacing: Theme.Spacing.card) {
                            if isRegistering {
                                // Display Name
                                VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                                    Text("पूरा नाम / FULL NAME")
                                        .font(.caption2.weight(.black))
                                        .foregroundStyle(Theme.inkSecondary)
                                    
                                    HStack(spacing: Theme.Spacing.standard) {
                                        Image(systemName: "person.text.rectangle.fill")
                                            .font(.callout)
                                            .foregroundStyle(Theme.inkSecondary.opacity(0.5))
                                        TextField("display name...", text: $displayName)
                                            .textContentType(.name)
                                            .accessibilityLabel("Full name")
                                            .foregroundStyle(Theme.inkPrimary)
                                            .focused($focusedField, equals: .displayName)
                                            .submitLabel(.next)
                                            .onSubmit { focusedField = .username }
                                    }
                                    .padding(Theme.Spacing.card)
                                    .banknoteCard()
                                }
                                .staggerAppear(delay: 0.1)
                            }

                            // Username
                            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                                Text("प्रयोक्ता नाम / USERNAME")
                                    .font(.caption2.weight(.black))
                                    .foregroundStyle(Theme.inkSecondary)
                                
                                HStack(spacing: Theme.Spacing.standard) {
                                    Image(systemName: "person.fill")
                                        .font(.callout)
                                        .foregroundStyle(Theme.inkSecondary.opacity(0.5))
                                    TextField("username...", text: $username)
                                        .textContentType(.username)
                                        .accessibilityLabel("Username")
                                        .autocorrectionDisabled()
                                        .autocapitalization(.none)
                                        .foregroundStyle(Theme.inkPrimary)
                                        .focused($focusedField, equals: .username)
                                        .submitLabel(.next)
                                        .onSubmit { focusedField = .password }
                                }
                                .padding(Theme.Spacing.card)
                                .banknoteCard()
                            }

                            // Password
                            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                                Text("कूटशब्द / SECURITY KEY")
                                    .font(.caption2.weight(.black))
                                    .foregroundStyle(Theme.inkSecondary)
                                
                                HStack(spacing: Theme.Spacing.standard) {
                                    Image(systemName: "lock.shield.fill")
                                        .font(.callout)
                                        .foregroundStyle(Theme.inkSecondary.opacity(0.5))
                                    Group {
                                        if showPassword {
                                            TextField("••••••••", text: $password)
                                                .autocorrectionDisabled()
                                                .autocapitalization(.none)
                                        } else {
                                            SecureField("••••••••", text: $password)
                                        }
                                    }
                                    .textContentType(isRegistering ? .newPassword : .password)
                                    .accessibilityLabel("Password")
                                    .foregroundStyle(Theme.inkPrimary)
                                    .focused($focusedField, equals: .password)
                                    .submitLabel(.go)
                                    .onSubmit { attemptAction() }
                                    Button { showPassword.toggle() } label: {
                                        Image(systemName: showPassword ? "eye.slash" : "eye")
                                            .font(.callout)
                                            .foregroundStyle(Theme.inkSecondary)
                                    }
                                    .buttonStyle(.plain)
                                    .accessibilityLabel(showPassword ? "Hide password" : "Show password")
                                }
                                .padding(Theme.Spacing.card)
                                .banknoteCard()

                                if isRegistering {
                                    Text("At least 8 characters")
                                        .font(.caption)
                                        .foregroundStyle((1...7).contains(password.count) ? Theme.bearRed : Theme.inkSecondary)
                                }
                            }

                            if isRegistering {
                                PolicyConsentRow(accepted: $acceptedPolicy, ageConfirmed: $ageConfirmed)
                            }
                        }

                        // Error (Styled as a VOID stamp)
                        if let err = authManager.loginError {
                            HStack(spacing: Theme.Spacing.medium) {
                                BanknoteSignalBadge(text: "DENIED", color: Theme.bearRed, rotation: -8)
                                    .scaleEffect(0.8)
                                Text(err)
                                    .font(.caption.weight(.bold))
                                    .foregroundStyle(Theme.bearRed)
                            }
                            .padding(Theme.Spacing.standard)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Theme.signalRuby.opacity(0.05))
                        }

                        // Primary Action Button
                        Button(action: { HapticManager.selection(); attemptAction() }) { HStack {
                                if authManager.isLoggingIn {
                                    ProgressView().tint(Theme.inkPrimary)
                                } else {
                                    Text(isRegistering ? "CREATE ACCOUNT" : "SIGN IN")
                                        .font(Theme.labelStyle)
                                        .tracking(1)
                                }
                            }
                            .frame(maxWidth: .infinity)
                            .padding(Theme.Spacing.card)
                            .background(canProceed ? Theme.inkPrimary : Theme.inkPrimary.opacity(0.1))
                            .foregroundStyle(canProceed ? Theme.canvas : Theme.inkPrimary.opacity(0.3))
                            .banknoteCard()
                        }
                        .disabled(!canProceed || authManager.isLoggingIn)

                        // Toggle Mode Button
                        Button(action: { HapticManager.selection();  HapticManager.selection()
                            withAnimation { isRegistering.toggle() }
                        }) {
                            Text(isRegistering ? "HAVE AN ACCOUNT? SIGN IN" : "NEW USER? CREATE ACCOUNT")
                                .font(Theme.labelStyle)
                                .foregroundStyle(Theme.securityGold)
                        }
                    }
                    .padding(Theme.Spacing.xLarge)
                    .banknoteCard()
                    .padding(.horizontal, Theme.Spacing.large)
                    .staggerAppear(delay: 0.4)
                }
            }
            .hideKeyboardOnTap()
        }
        .onChange(of: authManager.loginError) { _, err in
            if let err { UIAccessibility.post(notification: .announcement, argument: err) }
        }
    }

    private var canProceed: Bool {
        if isRegistering {
            // Mirrors the server's password policy (auth_service.register_user).
            return !username.isEmpty && password.count >= 8 && !displayName.isEmpty && acceptedPolicy && ageConfirmed
        }
        return !username.trimmingCharacters(in: .whitespaces).isEmpty && !password.isEmpty
    }

    private func attemptAction() {
        guard canProceed else { return }
        focusedField = nil
        Task {
            if isRegistering {
                await authManager.register(username: username, password: password, displayName: displayName, ageConfirmed: ageConfirmed)
            } else {
                await authManager.login(username: username, password: password)
            }
        }
    }
}

/// FINSEC-09 / REG-12: privacy notice and 18+ attestation shown at
/// registration. Registration stays disabled until both boxes are ticked;
/// AuthManager.register sends PolicyVersion.current and the age attestation so
/// the server records what was accepted.
private struct PolicyConsentRow: View {
    @Binding var accepted: Bool
    @Binding var ageConfirmed: Bool
    @State private var shownPolicy: DisclosureKey?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            ConsentCheckbox(isOn: $ageConfirmed, label: "I am 18 or older")
            ConsentCheckbox(isOn: $accepted, label: "I agree to the Privacy Policy and Terms of Use")

            HStack(spacing: Theme.Spacing.large) {
                ForEach([DisclosureKey.privacyPolicy, .termsOfUse]) { key in
                    Button(key.displayTitle) { shownPolicy = key }
                        .font(Theme.labelStyle)
                        .foregroundStyle(Theme.securityGold)
                        .buttonStyle(.plain)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .sheet(item: $shownPolicy) { key in
            NavigationStack { DisclosureDetailView(key: key) }
                .presentationDragIndicator(.visible)
        }
    }
}

private struct ConsentCheckbox: View {
    @Binding var isOn: Bool
    let label: String

    var body: some View {
        Button {
            HapticManager.selection()
            isOn.toggle()
        } label: {
            HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                Image(systemName: isOn ? "checkmark.square.fill" : "square")
                    .font(.callout)
                    .foregroundStyle(isOn ? Theme.inkPrimary : Theme.inkSecondary)
                Text(label)
                    .font(.caption)
                    .foregroundStyle(Theme.inkPrimary)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(label)
        .accessibilityValue(isOn ? "Checked" : "Not checked")
        .accessibilityAddTraits(.isButton)
    }
}
