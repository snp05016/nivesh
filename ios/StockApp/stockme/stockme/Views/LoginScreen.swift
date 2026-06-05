import SwiftUI

struct LoginScreen: View {
    @EnvironmentObject var authManager: AuthManager

    @State private var isRegistering = false
    @State private var username = ""
    @State private var password = ""
    @State private var displayName = ""
    @FocusState private var focusedField: Field?

    enum Field { case username, password, displayName }

    var body: some View {
        ZStack {
            // The Banknote Canvas
            PaperTexture()
            
            // Background Medallions
            BanknoteWatermark(text: "RESERVE BANK", size: 120, opacity: 0.02, alignment: .topLeading)
            BanknoteWatermark(text: "OFFICIAL", size: 100, opacity: 0.015, alignment: .bottomTrailing)

            ScrollView {
                VStack(spacing: 0) {
                    // Header (Official Denomination Style)
                    VStack(spacing: 16) {
                        ZStack {
                            Circle()
                                .stroke(Theme.inkSecondary.opacity(0.3), lineWidth: 1)
                                .frame(width: 80, height: 80)
                            Text("₹")
                                .font(Theme.engravedSerif(size: 40, weight: .bold, relativeTo: .largeTitle))
                                .foregroundStyle(Theme.inkPrimary)
                        }
                        .padding(.top, 60)
                        .staggerAppear(delay: 0.1)

                        VStack(spacing: 4) {
                            Text("निवेश / NIVESH")
                                .font(Theme.engravedSerif(size: 34, weight: .bold, relativeTo: .largeTitle))
                                .foregroundStyle(Theme.inkPrimary)
                            Text(isRegistering ? "NEW REGISTRY ENROLLMENT" : "CENTRAL REGISTRY ACCESS")
                                .font(Theme.labelStyle)
                                .foregroundStyle(Theme.inkSecondary)
                        }
                        .staggerAppear(delay: 0.2)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.bottom, Theme.Spacing.xLarge)

                    // Entry Form
                    VStack(spacing: Theme.Spacing.large) {
                        VStack(spacing: 16) {
                            if isRegistering {
                                // Display Name
                                VStack(alignment: .leading, spacing: 8) {
                                    Text("पूरा नाम / FULL NAME")
                                        .font(.caption2.weight(.black))
                                        .foregroundStyle(Theme.inkSecondary)
                                    
                                    HStack(spacing: 12) {
                                        Image(systemName: "person.text.rectangle.fill")
                                            .font(.callout)
                                            .foregroundStyle(Theme.inkSecondary.opacity(0.5))
                                        TextField("official name...", text: $displayName)
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
                            VStack(alignment: .leading, spacing: 8) {
                                Text("प्रयोक्ता नाम / USERNAME")
                                    .font(.caption2.weight(.black))
                                    .foregroundStyle(Theme.inkSecondary)
                                
                                HStack(spacing: 12) {
                                    Image(systemName: "person.fill")
                                        .font(.callout)
                                        .foregroundStyle(Theme.inkSecondary.opacity(0.5))
                                    TextField("identity entry...", text: $username)
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
                            VStack(alignment: .leading, spacing: 8) {
                                Text("कूटशब्द / SECURITY KEY")
                                    .font(.caption2.weight(.black))
                                    .foregroundStyle(Theme.inkSecondary)
                                
                                HStack(spacing: 12) {
                                    Image(systemName: "lock.shield.fill")
                                        .font(.callout)
                                        .foregroundStyle(Theme.inkSecondary.opacity(0.5))
                                    SecureField("••••••••", text: $password)
                                        .foregroundStyle(Theme.inkPrimary)
                                        .focused($focusedField, equals: .password)
                                        .submitLabel(.go)
                                        .onSubmit { attemptAction() }
                                }
                                .padding(Theme.Spacing.card)
                                .banknoteCard()
                            }
                        }

                        // Error (Styled as a VOID stamp)
                        if let err = authManager.loginError {
                            HStack(spacing: 10) {
                                BanknoteSignalBadge(text: "DENIED", color: Theme.bearRed, rotation: -8)
                                    .scaleEffect(0.8)
                                Text(err.uppercased())
                                    .font(.caption.weight(.bold))
                                    .foregroundStyle(Theme.bearRed)
                            }
                            .padding(Theme.Spacing.standard)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Theme.signalRuby.opacity(0.05))
                        }

                        // Primary Action Button
                        Button(action: attemptAction) {
                            HStack {
                                if authManager.isLoggingIn {
                                    ProgressView().tint(Theme.inkPrimary)
                                } else {
                                    Text(isRegistering ? "ENROLL IN REGISTRY" : "AUTHENTICATE & ENTER")
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
                        Button(action: { 
                            withAnimation { isRegistering.toggle() }
                        }) {
                            Text(isRegistering ? "ALREADY ENROLLED? SIGN IN" : "NEW USER? ENROLL HERE")
                                .font(Theme.labelStyle)
                                .foregroundStyle(Theme.securityGold)
                        }

                        if !isRegistering {
                            // Quick-fill (Official Tokens)
                            VStack(spacing: 12) {
                                Text("QUICK AUTHENTICATION")
                                    .font(Theme.labelStyle)
                                    .foregroundStyle(Theme.inkSecondary)
                                
                                HStack(spacing: 10) {
                                    ForEach(["saumya", "nirav", "ankur"], id: \.self) { name in
                                        Button {
                                            username = name
                                            password = "123"
                                            focusedField = nil
                                        } label: {
                                            Text(name.uppercased())
                                                .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                                                .padding(.horizontal, Theme.Spacing.card)
                                                .padding(.vertical, Theme.Spacing.standard)
                                                .background(username == name ? Theme.securityGold.opacity(0.1) : Color.clear)
                                                .foregroundStyle(username == name ? Theme.securityGold : Theme.inkPrimary)
                                                .overlay(RoundedRectangle(cornerRadius: 2).stroke(username == name ? Theme.securityGold : Theme.inkPrimary.opacity(0.1), lineWidth: 1))
                                        }
                                    }
                                }
                            }
                            .padding(.top, 8)
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
    }

    private var canProceed: Bool {
        if isRegistering {
            return !username.isEmpty && !password.isEmpty && !displayName.isEmpty
        }
        return !username.trimmingCharacters(in: .whitespaces).isEmpty && !password.isEmpty
    }

    private func attemptAction() {
        guard canProceed else { return }
        focusedField = nil
        Task {
            if isRegistering {
                await authManager.register(username: username, password: password, displayName: displayName)
            } else {
                await authManager.login(username: username, password: password)
            }
        }
    }
}
