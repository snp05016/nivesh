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
                                .font(Theme.engravedSerif(size: 40, weight: .bold))
                                .foregroundColor(Theme.inkPrimary)
                        }
                        .padding(.top, 60)
                        .staggerAppear(delay: 0.1)

                        VStack(spacing: 4) {
                            Text("निवेश / NIVESH")
                                .font(Theme.engravedSerif(size: 34, weight: .bold))
                                .foregroundColor(Theme.inkPrimary)
                            Text(isRegistering ? "NEW REGISTRY ENROLLMENT" : "CENTRAL REGISTRY ACCESS")
                                .font(Theme.labelStyle)
                                .foregroundColor(Theme.inkSecondary)
                        }
                        .staggerAppear(delay: 0.2)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.bottom, 48)

                    // Entry Form
                    VStack(spacing: 24) {
                        VStack(spacing: 16) {
                            if isRegistering {
                                // Display Name
                                VStack(alignment: .leading, spacing: 8) {
                                    Text("पूरा नाम / FULL NAME")
                                        .font(.system(size: 8, weight: .black))
                                        .foregroundColor(Theme.inkSecondary)
                                    
                                    HStack(spacing: 12) {
                                        Image(systemName: "person.text.rectangle.fill")
                                            .font(.system(size: 14))
                                            .foregroundColor(Theme.inkSecondary.opacity(0.5))
                                        TextField("official name...", text: $displayName)
                                            .foregroundColor(Theme.inkPrimary)
                                            .focused($focusedField, equals: .displayName)
                                            .submitLabel(.next)
                                            .onSubmit { focusedField = .username }
                                    }
                                    .padding(16)
                                    .banknoteCard()
                                }
                                .staggerAppear(delay: 0.1)
                            }

                            // Username
                            VStack(alignment: .leading, spacing: 8) {
                                Text("प्रयोक्ता नाम / USERNAME")
                                    .font(.system(size: 8, weight: .black))
                                    .foregroundColor(Theme.inkSecondary)
                                
                                HStack(spacing: 12) {
                                    Image(systemName: "person.fill")
                                        .font(.system(size: 14))
                                        .foregroundColor(Theme.inkSecondary.opacity(0.5))
                                    TextField("identity entry...", text: $username)
                                        .autocorrectionDisabled()
                                        .autocapitalization(.none)
                                        .foregroundColor(Theme.inkPrimary)
                                        .focused($focusedField, equals: .username)
                                        .submitLabel(.next)
                                        .onSubmit { focusedField = .password }
                                }
                                .padding(16)
                                .banknoteCard()
                            }

                            // Password
                            VStack(alignment: .leading, spacing: 8) {
                                Text("कूटशब्द / SECURITY KEY")
                                    .font(.system(size: 8, weight: .black))
                                    .foregroundColor(Theme.inkSecondary)
                                
                                HStack(spacing: 12) {
                                    Image(systemName: "lock.shield.fill")
                                        .font(.system(size: 14))
                                        .foregroundColor(Theme.inkSecondary.opacity(0.5))
                                    SecureField("••••••••", text: $password)
                                        .foregroundColor(Theme.inkPrimary)
                                        .focused($focusedField, equals: .password)
                                        .submitLabel(.go)
                                        .onSubmit { attemptAction() }
                                }
                                .padding(16)
                                .banknoteCard()
                            }
                        }

                        // Error (Styled as a VOID stamp)
                        if let err = authManager.loginError {
                            HStack(spacing: 10) {
                                BanknoteSignalBadge(text: "DENIED", color: Theme.bearRed, rotation: -8)
                                    .scaleEffect(0.8)
                                Text(err.uppercased())
                                    .font(.system(size: 11, weight: .bold))
                                    .foregroundColor(Theme.bearRed)
                            }
                            .padding(12)
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
                            .padding(18)
                            .background(canProceed ? Theme.inkPrimary : Theme.inkPrimary.opacity(0.1))
                            .foregroundColor(canProceed ? Theme.canvas : Theme.inkPrimary.opacity(0.3))
                            .banknoteCard()
                        }
                        .disabled(!canProceed || authManager.isLoggingIn)

                        // Toggle Mode Button
                        Button(action: { 
                            withAnimation { isRegistering.toggle() }
                        }) {
                            Text(isRegistering ? "ALREADY ENROLLED? SIGN IN" : "NEW USER? ENROLL HERE")
                                .font(Theme.labelStyle)
                                .font(.system(size: 8))
                                .foregroundColor(Theme.securityGold)
                        }

                        if !isRegistering {
                            // Quick-fill (Official Tokens)
                            VStack(spacing: 12) {
                                Text("QUICK AUTHENTICATION")
                                    .font(Theme.labelStyle)
                                    .font(.system(size: 8))
                                    .foregroundColor(Theme.inkSecondary)
                                
                                HStack(spacing: 10) {
                                    ForEach(["saumya", "nirav", "ankur"], id: \.self) { name in
                                        Button {
                                            username = name
                                            password = "123"
                                            focusedField = nil
                                        } label: {
                                            Text(name.uppercased())
                                                .font(Theme.serialNumberFont(size: 11))
                                                .padding(.horizontal, 16)
                                                .padding(.vertical, 10)
                                                .background(username == name ? Theme.securityGold.opacity(0.1) : Color.clear)
                                                .foregroundColor(username == name ? Theme.securityGold : Theme.inkPrimary)
                                                .overlay(RoundedRectangle(cornerRadius: 2).stroke(username == name ? Theme.securityGold : Theme.inkPrimary.opacity(0.1), lineWidth: 1))
                                        }
                                    }
                                }
                            }
                            .padding(.top, 8)
                        }
                    }
                    .padding(32)
                    .banknoteCard()
                    .padding(.horizontal, 24)
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
