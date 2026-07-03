import SwiftUI

// MARK: - AccountSecurityStatusView
//
// "SIM-binding controls" + KYC-details account-settings screen. Talks to the
// REAL, already-merged /api/kyc/... surface (backend/routers/kyc.py +
// backend/services/kyc_consent_service.py). MOCK DATA - simulated for demo
// purposes, not a real integration: there is no real telecom
// SIM-swap-detection API and no real credit-bureau / government ID
// verification anywhere behind these endpoints — this screen only shows
// what this app itself recorded. Reachable from Settings → Account Security.

struct AccountSecurityStatusView: View {
    @State private var consents: [ConsentDTO] = []
    @State private var deviceBindings: [DeviceBindingDTO] = []
    @State private var verifyResult: DeviceBindingVerifyDTO?
    @State private var fraudSignals: FraudSignalsDTO?

    @State private var isLoading = false
    @State private var errorMessage: String?

    @State private var busyConsentType: String?
    @State private var isBindingDevice = false
    @State private var actionMessage: String?

    /// Same source LoanViewModel.submit() uses for the mock device-binding
    /// KYC gate — see ViewModels/LoanViewModel.swift.
    private var currentDeviceId: String? {
        UIDevice.current.identifierForVendor?.uuidString
    }

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            if isLoading && consents.isEmpty && deviceBindings.isEmpty {
                ProgressView().tint(Theme.securityGold)
            } else {
                ScrollView {
                    VStack(spacing: Theme.Spacing.large) {
                        disclaimerBanner
                        consentSection
                        deviceBindingSection
                        fraudSignalsSection
                        if let error = errorMessage {
                            Text(error)
                                .font(Theme.serialNumberFont(size: 11))
                                .foregroundStyle(Theme.bearRed)
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.screen)
                    .padding(.vertical, Theme.Spacing.large)
                }
                .refreshable { await loadAll() }
            }
        }
        .navigationTitle("KYC & Device Security")
        .navigationBarTitleDisplayMode(.large)
        .task { await loadAll() }
    }

    // MARK: - Disclaimer

    private var disclaimerBanner: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: "exclamationmark.shield")
                .foregroundStyle(Theme.holdAmber)
            Text("MOCK DATA — simulated for demo purposes. No real telecom SIM-swap-detection API and no real government ID verification back these checks.")
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                .foregroundStyle(Theme.inkTertiary)
        }
        .padding(Theme.Spacing.card)
        .background(Theme.holdAmber.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
    }

    // MARK: - KYC Consents

    private var consentSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            sectionHeader("KYC CONSENTS", hindi: "केवाईसी सहमति")
            VStack(spacing: Theme.Spacing.none) {
                ForEach(Array(KYCConsentType.allCases.enumerated()), id: \.element.id) { index, type in
                    if index > 0 { GuillocheDivider() }
                    ConsentRow(
                        type: type,
                        consent: activeConsent(for: type),
                        isBusy: busyConsentType == type.rawValue,
                        onToggle: { grant in Task { await toggleConsent(type: type, granted: grant) } }
                    )
                }
            }
            .banknoteCard()

            if let actionMessage {
                Text(actionMessage)
                    .font(Theme.serialNumberFont(size: 11))
                    .foregroundStyle(Theme.bullGreen)
            }
        }
    }

    private func activeConsent(for type: KYCConsentType) -> ConsentDTO? {
        consents.first { $0.consentType == type.rawValue && $0.granted && $0.revokedAt == nil }
    }

    // MARK: - Device Binding

    private var deviceBindingSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            sectionHeader("DEVICE BINDING (SIM-BINDING)", hindi: "डिवाइस बंधन")
            VStack(spacing: Theme.Spacing.none) {
                if deviceBindings.isEmpty {
                    NoDeviceBoundRow()
                } else {
                    ForEach(Array(deviceBindings.enumerated()), id: \.element.id) { index, binding in
                        if index > 0 { GuillocheDivider() }
                        DeviceBindingRow(binding: binding, isCurrentDevice: binding.deviceId == currentDeviceId)
                    }
                }
                if let verifyResult {
                    GuillocheDivider()
                    VerifyResultRow(result: verifyResult)
                }
            }
            .banknoteCard()

            bindDeviceButton
        }
    }

    private var bindDeviceButton: some View {
        Button {
            HapticManager.selection()
            Task { await bindThisDevice() }
        } label: {
            HStack {
                Spacer()
                if isBindingDevice {
                    ProgressView().tint(Theme.canvas)
                } else {
                    Text(alreadyBoundAsPrimary ? "RE-BIND THIS DEVICE" : "BIND THIS DEVICE")
                        .font(Theme.officialStampFont(size: 11))
                        .tracking(1.2)
                }
                Spacer()
            }
            .foregroundStyle(Theme.canvas)
            .padding(.vertical, Theme.Spacing.standard)
            .background(Theme.securityGoldGradient)
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        }
        .buttonStyle(EKPressStyle())
        .disabled(isBindingDevice || currentDeviceId == nil)
    }

    private var alreadyBoundAsPrimary: Bool {
        deviceBindings.contains { $0.deviceId == currentDeviceId && $0.isPrimary }
    }

    // MARK: - Fraud Signals

    private var fraudSignalsSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            sectionHeader("ACCOUNT SECURITY SIGNALS", hindi: "सुरक्षा संकेत")
            VStack(spacing: Theme.Spacing.none) {
                if let fraudSignals {
                    if fraudSignals.isFlagged {
                        FraudFlaggedRow(signals: fraudSignals)
                    } else {
                        FraudQuietRow(signals: fraudSignals)
                    }
                } else {
                    FraudSignalsUnavailableRow()
                }
            }
            .banknoteCard()

            Text("MOCK CHECK — a simple counter over this app's own device-binding attempts, not a real fraud-detection engine.")
                .font(Theme.engravedSerif(size: 10, relativeTo: .caption2))
                .foregroundStyle(Theme.inkTertiary)
        }
    }

    private func sectionHeader(_ title: String, hindi: String) -> some View {
        HStack(alignment: .bottom, spacing: Theme.Spacing.tight) {
            Text(hindi).font(Theme.hindiFont(size: 9)).foregroundStyle(Theme.inkSecondary)
            Text(title).font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
        }
        .padding(.horizontal, Theme.Spacing.small)
    }

    // MARK: - Actions

    private func loadAll() async {
        isLoading = true
        errorMessage = nil
        do {
            async let consentsTask = NetworkManager.shared.fetchActiveConsents()
            consents = try await consentsTask
        } catch {
            errorMessage = "Couldn't load KYC consent status. Pull to retry."
        }

        // Device bindings have no dedicated "list" endpoint on the backend
        // (/api/kyc/device-binding/verify only confirms one device_id) — we
        // derive the shown binding from the verify response for the current
        // device, since that's the only device-binding read surface exposed.
        if let currentDeviceId {
            do {
                verifyResult = try await NetworkManager.shared.verifyDeviceBinding(deviceId: currentDeviceId)
                if verifyResult?.verified == true {
                    deviceBindings = [DeviceBindingDTO(id: 0, userId: 0, deviceId: currentDeviceId, boundAt: nil, isPrimary: true)]
                } else {
                    deviceBindings = []
                }
            } catch {
                // Non-fatal — leave deviceBindings empty and show the
                // "no device bound" state; errorMessage stays focused on
                // the consents fetch above.
            }
        }

        do {
            fraudSignals = try await NetworkManager.shared.fetchFraudSignals()
        } catch {
            // Non-fatal — the section just shows an "unavailable" state;
            // errorMessage stays focused on the consents fetch above.
            fraudSignals = nil
        }
        isLoading = false
    }

    private func toggleConsent(type: KYCConsentType, granted: Bool) async {
        busyConsentType = type.rawValue
        actionMessage = nil
        do {
            _ = try await NetworkManager.shared.grantConsent(type: type.rawValue, granted: granted)
            actionMessage = granted ? "\(type.displayName) consent granted." : "\(type.displayName) consent withdrawn."
            consents = try await NetworkManager.shared.fetchActiveConsents()
        } catch {
            errorMessage = "Couldn't update \(type.displayName) consent. Please try again."
        }
        busyConsentType = nil
    }

    private func bindThisDevice() async {
        guard let currentDeviceId else { return }
        isBindingDevice = true
        errorMessage = nil
        do {
            let binding = try await NetworkManager.shared.bindDevice(deviceId: currentDeviceId, isPrimary: true)
            deviceBindings = [binding]
            verifyResult = try await NetworkManager.shared.verifyDeviceBinding(deviceId: currentDeviceId)
            actionMessage = "This device is now bound."
            HapticManager.success()
        } catch {
            errorMessage = "Couldn't bind this device. Please try again."
        }
        isBindingDevice = false
    }
}

// MARK: - Rows

private struct ConsentRow: View {
    let type: KYCConsentType
    let consent: ConsentDTO?
    let isBusy: Bool
    let onToggle: (Bool) -> Void

    private var isGranted: Bool { consent != nil }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            ZStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill((isGranted ? Theme.bullGreen : Theme.inkSecondary).opacity(0.08))
                    .frame(width: 32, height: 32)
                Image(systemName: isGranted ? "checkmark.shield.fill" : "shield")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle((isGranted ? Theme.bullGreen : Theme.inkSecondary).opacity(0.7))
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(type.displayName.uppercased())
                    .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                Text(type.explanation)
                    .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkTertiary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer()
            if isBusy {
                ProgressView().tint(Theme.securityGold)
            } else {
                Toggle("", isOn: Binding(get: { isGranted }, set: { onToggle($0) }))
                    .labelsHidden()
                    .tint(Theme.securityGold)
            }
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
    }
}

private struct DeviceBindingRow: View {
    let binding: DeviceBindingDTO
    let isCurrentDevice: Bool

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            ZStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.bullGreen.opacity(0.08)).frame(width: 32, height: 32)
                Image(systemName: "iphone.gen3")
                    .font(.subheadline.weight(.medium)).foregroundStyle(Theme.bullGreen.opacity(0.7))
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(binding.maskedDeviceId)
                    .font(Theme.serialNumberFont(size: 13)).foregroundStyle(Theme.inkPrimary)
                Text(binding.isPrimary ? "Primary device" : "Secondary device")
                    .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkTertiary)
            }
            Spacer()
            if isCurrentDevice {
                Text("THIS DEVICE")
                    .font(Theme.officialStampFont(size: 7))
                    .foregroundStyle(Theme.bullGreen)
            }
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
    }
}

private struct NoDeviceBoundRow: View {
    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            ZStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.bearRed.opacity(0.08)).frame(width: 32, height: 32)
                Image(systemName: "iphone.slash")
                    .font(.subheadline.weight(.medium)).foregroundStyle(Theme.bearRed.opacity(0.7))
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("NO DEVICE BOUND")
                    .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                Text("Loan/FD applications will fail closed until this device is bound.")
                    .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkTertiary)
            }
            Spacer()
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
    }
}

private struct VerifyResultRow: View {
    let result: DeviceBindingVerifyDTO

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: result.verified ? "checkmark.seal.fill" : "xmark.seal.fill")
                .foregroundStyle(result.verified ? Theme.bullGreen : Theme.bearRed)
            Text(result.reason)
                .font(Theme.serialNumberFont(size: 10))
                .foregroundStyle(Theme.inkTertiary)
            Spacer()
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
    }
}

private struct FraudFlaggedRow: View {
    let signals: FraudSignalsDTO

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            ZStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.bearRed.opacity(0.08)).frame(width: 32, height: 32)
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.subheadline.weight(.medium)).foregroundStyle(Theme.bearRed.opacity(0.8))
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("ACCOUNT FLAGGED (MOCK)")
                    .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.bearRed)
                Text("\(signals.crossUserRejectionsTotal) cross-user rejection(s) · \(signals.rateLimitHits24h) rate-limit hit(s) in 24h — simulated check only, no real fraud engine.")
                    .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkTertiary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer()
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
    }
}

private struct FraudQuietRow: View {
    let signals: FraudSignalsDTO

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            ZStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.bullGreen.opacity(0.08)).frame(width: 32, height: 32)
                Image(systemName: "checkmark.shield")
                    .font(.subheadline.weight(.medium)).foregroundStyle(Theme.bullGreen.opacity(0.7))
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("No fraud signals detected (mock check)")
                    .font(Theme.serialNumberFont(size: 12)).foregroundStyle(Theme.inkPrimary)
                Text("\(signals.totalBindAttempts24h) device-bind attempt(s) in the last 24h.")
                    .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkTertiary)
            }
            Spacer()
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
    }
}

private struct FraudSignalsUnavailableRow: View {
    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: "questionmark.circle")
                .foregroundStyle(Theme.inkTertiary)
            Text("Fraud signal status unavailable right now.")
                .font(Theme.serialNumberFont(size: 11)).foregroundStyle(Theme.inkTertiary)
            Spacer()
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
    }
}

#Preview {
    NavigationStack { AccountSecurityStatusView() }
}
