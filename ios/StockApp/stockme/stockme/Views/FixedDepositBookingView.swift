import SwiftUI

// MARK: - Fixed Deposit Booking
//
// MOCK DATA - simulated for demo purposes, not a real integration. Submits
// to a mock backend endpoint (see NetworkManager+FixedDeposits.swift) that
// records the booking and returns a (possibly failed-closed) status. Neither
// UPI nor Net Banking collects any real payment — both rails are explicitly
// demo-labeled. If the booking fails closed on a KYC/device-binding gate,
// the decision_reason is surfaced clearly and the user is guided toward
// Account Settings to complete device binding/consent — this view never
// calls /api/kyc/... directly, that flow lives in Account Settings.

struct FixedDepositBookingView: View {
    @StateObject private var vm: FixedDepositBookingViewModel

    init(scheme: FDSchemeDTO) {
        _vm = StateObject(wrappedValue: FixedDepositBookingViewModel(scheme: scheme))
    }

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.sectionSpacing) {
                FDBookingHeader(scheme: vm.scheme)

                GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                if let booking = vm.bookingResult {
                    FDBookingResultCard(booking: booking, requiresFollowUp: vm.requiresAccountSettingsFollowUp)
                        .padding(.horizontal, Theme.screenPadding)
                } else {
                    FDBookingInputs(vm: vm)
                        .padding(.horizontal, Theme.screenPadding)

                    FDCalculatorResultCard(result: vm.calculator.result, isCalculating: vm.calculator.isCalculating)
                        .padding(.horizontal, Theme.screenPadding)

                    FDPaymentMethodPicker(selected: $vm.paymentMethod)
                        .padding(.horizontal, Theme.screenPadding)

                    FDBookingSubmitButton(vm: vm)
                        .padding(.horizontal, Theme.screenPadding)
                }
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Book Fixed Deposit")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            vm.syncCalculatorInputs()
            await vm.calculator.recalculate()
        }
        .onChange(of: vm.principal) { _, _ in
            vm.syncCalculatorInputs()
            Task { await vm.calculator.recalculate() }
        }
        .onChange(of: vm.tenureMonths) { _, _ in
            vm.syncCalculatorInputs()
            Task { await vm.calculator.recalculate() }
        }
    }
}

// MARK: - Header

struct FDBookingHeader: View {
    let scheme: FDSchemeDTO

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text(scheme.issuerName)
                .font(Theme.engravedSerif(size: 24, weight: .bold, relativeTo: .title2))
                .foregroundColor(Theme.inkPrimary)
            Text("Fixed Deposit · \(scheme.interestRateDisplay) interest")
                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                .foregroundColor(Theme.inkSecondary)
            Text("DEMO BOOKING · NO REAL PAYMENT COLLECTED")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .padding(.horizontal, Theme.Spacing.medium)
                .padding(.vertical, Theme.Spacing.small)
                .foregroundColor(Theme.holdAmber)
                .background(Theme.holdAmber.opacity(0.12))
                .cornerRadius(Theme.CornerRadius.badge)
        }
        .padding(.horizontal, Theme.screenPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Inputs

struct FDBookingInputs: View {
    @ObservedObject var vm: FixedDepositBookingViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            FDAmountInput(vm: vm)
            GuillocheDivider()
            FDTenureInput(vm: vm)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct FDAmountInput: View {
    @ObservedObject var vm: FixedDepositBookingViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("PRINCIPAL AMOUNT")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)
            Text(IndianFormatter.formatLakhsCrores(vm.principal))
                .font(Theme.dataLarge())
                .foregroundColor(Theme.inkPrimary)
            Slider(value: $vm.principal, in: vm.scheme.minAmount...vm.scheme.maxAmount, step: 1000)
                .tint(Theme.securityGold)
            Text("Range: \(vm.scheme.amountRangeDisplay)")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)
        }
    }
}

private struct FDTenureInput: View {
    @ObservedObject var vm: FixedDepositBookingViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("TENURE")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)
            Text("\(vm.tenureMonths) months")
                .font(Theme.dataLarge(size: 22))
                .foregroundColor(Theme.inkPrimary)
            Slider(
                value: Binding(
                    get: { Double(vm.tenureMonths) },
                    set: { vm.tenureMonths = Int($0) }
                ),
                in: Double(vm.scheme.minTenureMonths)...Double(vm.scheme.maxTenureMonths),
                step: 1
            )
            .tint(Theme.securityGold)
            Text("Range: \(vm.scheme.tenureRangeDisplay)")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)
        }
    }
}

// MARK: - Payment Method Picker

struct FDPaymentMethodPicker: View {
    @Binding var selected: FDPaymentMethod

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("PAYMENT METHOD")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)

            Text("Demo rails only — no real payment is initiated or collected.")
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                .foregroundColor(Theme.inkTertiary)

            HStack(spacing: Theme.Spacing.standard) {
                ForEach(FDPaymentMethod.allCases) { method in
                    FDPaymentMethodOption(method: method, isSelected: selected == method) {
                        selected = method
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct FDPaymentMethodOption: View {
    let method: FDPaymentMethod
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button {
            HapticManager.selection()
            action()
        } label: {
            VStack(spacing: Theme.Spacing.small) {
                Image(systemName: method.icon)
                    .font(Theme.serialNumberFont(size: 20, relativeTo: .headline))
                Text(method.displayName)
                    .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                    .tracking(1.0)
                    .multilineTextAlignment(.center)
            }
            .foregroundColor(isSelected ? Theme.canvas : Theme.inkSecondary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, Theme.Spacing.standard)
            .background(isSelected ? Theme.inkPrimary : Color.clear)
            .cornerRadius(Theme.CornerRadius.medium)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .stroke(Theme.borderFine, lineWidth: isSelected ? 0 : 1)
            )
        }
        .buttonStyle(EKPressStyle())
    }
}

// MARK: - Submit Button

struct FDBookingSubmitButton: View {
    @ObservedObject var vm: FixedDepositBookingViewModel

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            if let error = vm.submissionError {
                Text(error)
                    .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                    .foregroundColor(Theme.bearRed)
            }

            Button {
                HapticManager.selection()
                Task { await vm.submit() }
            } label: {
                HStack {
                    Spacer()
                    if vm.isSubmitting {
                        ProgressView().tint(Theme.canvas)
                    } else {
                        Text("Book Fixed Deposit (Demo)")
                            .font(Theme.labelStyle)
                    }
                    Spacer()
                }
                .padding(Theme.Spacing.card)
                .background(vm.canSubmit ? Theme.securityGold : Theme.canvasShadow)
                .foregroundColor(vm.canSubmit ? Theme.canvas : Theme.inkTertiary)
                .cornerRadius(Theme.CornerRadius.medium)
            }
            .buttonStyle(EKPressStyle())
            .disabled(!vm.canSubmit)
        }
    }
}

// MARK: - Booking Result

struct FDBookingResultCard: View {
    let booking: FDBookingResponse
    let requiresFollowUp: Bool

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            Image(systemName: statusIcon)
                .font(Theme.officialStampFont(size: 40))
                .foregroundColor(statusColor)

            Text(statusTitle)
                .font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)

            Text("Booking #\(booking.id) · \(booking.parsedStatus.displayName)")
                .font(Theme.serialNumberFont(size: 13, relativeTo: .subheadline))
                .foregroundColor(Theme.inkSecondary)

            if let reason = booking.decisionReason, !reason.isEmpty {
                Text(reason)
                    .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                    .foregroundColor(booking.parsedStatus == .failed ? Theme.bearRed : Theme.inkTertiary)
                    .multilineTextAlignment(.center)
            }

            if booking.parsedStatus != .failed {
                GuillocheDivider()
                HStack(spacing: Theme.Spacing.card) {
                    FDBookingSummaryTile(label: "Principal", value: booking.principalDisplay)
                    FDBookingSummaryTile(label: "Maturity Value", value: booking.maturityDisplay, valueColor: Theme.securityGold)
                }
            }

            if requiresFollowUp {
                FDAccountSettingsFollowUp()
            }

            Text("This is a mock confirmation — no real NBFC was contacted and no funds were transferred.")
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                .foregroundColor(Theme.inkTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private var statusIcon: String {
        switch booking.parsedStatus {
        case .confirmed: return "checkmark.seal.fill"
        case .pending: return "clock.fill"
        case .failed: return "xmark.seal.fill"
        }
    }

    private var statusColor: Color {
        switch booking.parsedStatus {
        case .confirmed: return Theme.bullGreen
        case .pending: return Theme.holdAmber
        case .failed: return Theme.bearRed
        }
    }

    private var statusTitle: String {
        switch booking.parsedStatus {
        case .confirmed: return "Booking Confirmed"
        case .pending: return "Booking Pending"
        case .failed: return "Booking Failed"
        }
    }
}

private struct FDBookingSummaryTile: View {
    let label: String
    let value: String
    var valueColor: Color = Theme.inkPrimary

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundColor(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                .foregroundColor(valueColor)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Guides the user toward Account Settings when a booking fails closed on a
/// KYC consent / SIM device-binding gate. Does NOT call /api/kyc/consents or
/// /api/kyc/device-binding itself — that flow already lives in Account
/// Settings; this is a pointer, not a shortcut around it.
private struct FDAccountSettingsFollowUp: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            HStack(spacing: Theme.Spacing.small) {
                Image(systemName: "exclamationmark.shield.fill")
                    .foregroundColor(Theme.holdAmber)
                Text("Action Needed")
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.2)
                    .foregroundColor(Theme.holdAmber)
            }
            Text("This booking failed closed because device binding or KYC consent is incomplete. Open Account Settings to complete device binding and KYC consent, then try booking again.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.standard)
        .background(Theme.holdAmber.opacity(0.08))
        .cornerRadius(Theme.CornerRadius.medium)
    }
}
