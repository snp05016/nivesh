import SwiftUI

// MARK: - Loan Application (Multi-Step)
//
// MOCK DATA - simulated for demo purposes, not a real integration. Submits
// to a mock backend endpoint (see NetworkManager+Finance.swift) that just
// records the application and returns a fabricated "submitted" status. The
// KYC consent step is a demo checkbox only — no real e-KYC document upload,
// no PAN/Aadhaar or other government ID is ever collected.

struct LoanApplicationView: View {
    @StateObject private var vm: LoanApplicationViewModel
    @Environment(\.dismiss) private var dismiss

    init(offer: LoanOfferDTO) {
        _vm = StateObject(wrappedValue: LoanApplicationViewModel(offer: offer))
    }

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.sectionSpacing) {
                LoanApplicationHeader(offer: vm.offer)

                GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                LoanApplicationStepIndicator(currentStep: vm.currentStep, totalSteps: vm.totalSteps)
                    .padding(.horizontal, Theme.screenPadding)

                if let submitted = vm.submittedApplication {
                    LoanApplicationSubmittedCard(application: submitted)
                        .padding(.horizontal, Theme.screenPadding)

                    if submitted.parsedStatus == .approved || submitted.parsedStatus == .disbursed {
                        LoanDisbursementCard(vm: vm)
                            .padding(.horizontal, Theme.screenPadding)
                            .task { await vm.refreshDisbursementStatus() }
                    }
                } else {
                    LoanApplicationStepContent(vm: vm)
                        .padding(.horizontal, Theme.screenPadding)

                    LoanApplicationNavigationButtons(vm: vm)
                        .padding(.horizontal, Theme.screenPadding)
                }
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Apply for Loan")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Header

struct LoanApplicationHeader: View {
    let offer: LoanOfferDTO

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text(offer.nbfcName)
                .font(Theme.engravedSerif(size: 24, weight: .bold, relativeTo: .title2))
                .foregroundColor(Theme.inkPrimary)
            Text("\(offer.parsedLoanType.displayName) · \(offer.interestRateDisplay) interest")
                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                .foregroundColor(Theme.inkSecondary)
            Text("DEMO APPLICATION · NO REAL UNDERWRITING")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .padding(.horizontal, Theme.Spacing.medium)
                .padding(.vertical, Theme.Spacing.small)
                .foregroundColor(Theme.holdAmber)
                .background(Theme.holdAmber.opacity(0.12))
                .cornerRadius(Theme.CornerRadius.badge)

            NavigationLink(destination: KeyFactStatementView(source: .loanOffer(id: offer.id))) {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "doc.text.magnifyingglass").foregroundColor(Theme.securityGold)
                    Text("View Key Fact Statement")
                        .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                        .foregroundColor(Theme.inkPrimary)
                    Spacer()
                    Image(systemName: "chevron.right").font(.caption2.weight(.semibold)).foregroundColor(Theme.inkTertiary)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(EKPressStyle())
        }
        .padding(.horizontal, Theme.screenPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Step Indicator

struct LoanApplicationStepIndicator: View {
    let currentStep: Int
    let totalSteps: Int

    private let labels = ["Amount", "Tenure", "Purpose", "KYC Consent"]

    var body: some View {
        HStack(spacing: Theme.Spacing.small) {
            ForEach(0..<totalSteps, id: \.self) { step in
                VStack(spacing: Theme.Spacing.small) {
                    Circle()
                        .fill(step <= currentStep ? Theme.securityGold : Theme.canvasShadow)
                        .frame(width: 8, height: 8)
                    Text(labels[step])
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .foregroundColor(step == currentStep ? Theme.inkPrimary : Theme.inkTertiary)
                }
                if step < totalSteps - 1 {
                    Rectangle()
                        .fill(step < currentStep ? Theme.securityGold : Theme.canvasShadow)
                        .frame(height: 1)
                        .offset(y: -8)
                }
            }
        }
    }
}

// MARK: - Step Content

struct LoanApplicationStepContent: View {
    @ObservedObject var vm: LoanApplicationViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            switch vm.currentStep {
            case 0: LoanAmountStep(vm: vm)
            case 1: LoanTenureStep(vm: vm)
            case 2: LoanPurposeStep(vm: vm)
            case 3: LoanKYCConsentStep(vm: vm)
            default: EmptyView()
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct LoanAmountStep: View {
    @ObservedObject var vm: LoanApplicationViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("LOAN AMOUNT")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)
            Text(IndianFormatter.formatLakhsCrores(vm.amount))
                .font(Theme.dataLarge())
                .foregroundColor(Theme.inkPrimary)
            Slider(value: $vm.amount, in: vm.offer.minAmount...vm.offer.maxAmount, step: 1000)
                .tint(Theme.securityGold)
                .accessibilityLabel("Loan amount")
                .accessibilityValue(IndianFormatter.formatLakhsCrores(vm.amount))
            Text("Range: \(vm.offer.amountRangeDisplay)")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)
        }
    }
}

private struct LoanTenureStep: View {
    @ObservedObject var vm: LoanApplicationViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("TENURE")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)
            Text("\(vm.tenureMonths) months (\(vm.tenureMonths / 12) yrs \(vm.tenureMonths % 12) mo)")
                .font(Theme.dataLarge(size: 22))
                .foregroundColor(Theme.inkPrimary)
            Slider(
                value: Binding(
                    get: { Double(vm.tenureMonths) },
                    set: { vm.tenureMonths = Int($0) }
                ),
                in: Double(vm.offer.minTenureMonths)...Double(vm.offer.maxTenureMonths),
                step: 1
            )
            .tint(Theme.securityGold)
            .accessibilityLabel("Tenure")
            .accessibilityValue("\(vm.tenureMonths) months")
            Text("Range: \(vm.offer.tenureRangeDisplay)")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)
        }
    }
}

private struct LoanPurposeStep: View {
    @ObservedObject var vm: LoanApplicationViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("PURPOSE OF LOAN")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)
            TextField("e.g. Home renovation, vehicle purchase...", text: $vm.purpose, axis: .vertical)
                .font(Theme.serialNumberFont(size: 14))
                .foregroundColor(Theme.inkPrimary)
                .lineLimit(3...6)
                .padding(Theme.Spacing.standard)
                .background(Theme.canvasShadow)
                .cornerRadius(Theme.CornerRadius.medium)
        }
    }
}

private struct LoanKYCConsentStep: View {
    @ObservedObject var vm: LoanApplicationViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("KYC CONSENT")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)

            Text("This is a demo consent checkbox only. No real e-KYC, document upload, or government ID (PAN/Aadhaar) is collected or verified — nothing here contacts a real NBFC or credit bureau.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)

            Button {
                HapticManager.selection()
                vm.kycConsent.toggle()
            } label: {
                HStack(spacing: Theme.Spacing.standard) {
                    Image(systemName: vm.kycConsent ? "checkmark.square.fill" : "square")
                        .foregroundColor(vm.kycConsent ? Theme.securityGold : Theme.inkTertiary)
                    Text("I consent to (mock) KYC verification for this demo application.")
                        .font(Theme.engravedSerif(size: 13, relativeTo: .subheadline))
                        .foregroundColor(Theme.inkPrimary)
                        .multilineTextAlignment(.leading)
                }
            }
            .buttonStyle(EKPressStyle())

            DisclosureLinkRow(key: .digitalLendingCompliance)
            DisclosureLinkRow(key: .lendingServiceProvider)

            LoanApplicationSummaryCard(vm: vm)
        }
    }
}

private struct LoanApplicationSummaryCard: View {
    @ObservedObject var vm: LoanApplicationViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            GuillocheDivider()
            SummaryRow(label: "Amount", value: IndianFormatter.formatLakhsCrores(vm.amount))
            SummaryRow(label: "Tenure", value: "\(vm.tenureMonths) months")
            SummaryRow(label: "Purpose", value: vm.purpose.isEmpty ? "—" : vm.purpose)
        }
    }
}

private struct SummaryRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .tracking(1.0)
                .foregroundColor(Theme.inkTertiary)
            Spacer()
            Text(value)
                .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                .foregroundColor(Theme.inkPrimary)
                .multilineTextAlignment(.trailing)
        }
    }
}

// MARK: - Navigation Buttons

struct LoanApplicationNavigationButtons: View {
    @ObservedObject var vm: LoanApplicationViewModel

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            if let error = vm.submissionError {
                Text(error)
                    .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                    .foregroundColor(Theme.bearRed)
            }

            HStack(spacing: Theme.Spacing.standard) {
                if vm.currentStep > 0 {
                    Button {
                        HapticManager.selection()
                        vm.goBack()
                    } label: {
                        Text("Back")
                            .font(Theme.labelStyle)
                            .frame(maxWidth: .infinity)
                            .padding(Theme.Spacing.card)
                            .banknoteCard()
                            .foregroundColor(Theme.inkSecondary)
                    }
                    .buttonStyle(EKPressStyle())
                }

                Button {
                    HapticManager.selection()
                    if vm.currentStep == vm.totalSteps - 1 {
                        Task { await vm.submit() }
                    } else {
                        vm.advance()
                    }
                } label: {
                    HStack {
                        Spacer()
                        if vm.isSubmitting {
                            ProgressView().tint(Theme.canvas)
                        } else {
                            Text(vm.currentStep == vm.totalSteps - 1 ? "Submit Application" : "Next")
                                .font(Theme.labelStyle)
                        }
                        Spacer()
                    }
                    .padding(Theme.Spacing.card)
                    .background(vm.canAdvance ? Theme.securityGold : Theme.canvasShadow)
                    .foregroundColor(vm.canAdvance ? Theme.canvas : Theme.inkTertiary)
                    .cornerRadius(Theme.CornerRadius.medium)
                }
                .buttonStyle(EKPressStyle())
                .disabled(!vm.canAdvance || vm.isSubmitting)
            }
        }
    }
}

// MARK: - Submitted Confirmation

struct LoanApplicationSubmittedCard: View {
    let application: LoanApplicationResponse

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            Image(systemName: "checkmark.seal.fill")
                .font(Theme.officialStampFont(size: 40))
                .foregroundColor(Theme.bullGreen)

            Text("Application Submitted")
                .font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)

            Text("Application #\(application.id) · \(application.parsedStatus.displayName)")
                .font(Theme.serialNumberFont(size: 13, relativeTo: .subheadline))
                .foregroundColor(Theme.inkSecondary)

            Text("This is a mock confirmation — no real lender was contacted and no funds will be disbursed.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Disbursement (Mock)

/// Shown once a (mock) loan application reaches "approved" — lets the user
/// trigger a fake disbursement and shows its status. MOCK DATA - simulated
/// for demo purposes, not a real integration; no real funds are ever moved
/// and no real NBFC is contacted.
struct LoanDisbursementCard: View {
    @ObservedObject var vm: LoanApplicationViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("DISBURSEMENT (DEMO)")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)

            Text("Simulated disbursement only — no real funds are moved and no real NBFC is contacted.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)

            if let disbursement = vm.disbursement {
                DisbursementStatusRow(disbursement: disbursement)
            }
            if let error = vm.disbursementError {
                Text(error)
                    .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                    .foregroundColor(Theme.bearRed)
            }

            // A legacy "failed" row must not dead-end the flow: allow a retry.
            if vm.disbursement == nil || vm.disbursement?.status == "failed" {
                Button {
                    HapticManager.selection()
                    Task { await vm.requestDisbursement() }
                } label: {
                    HStack {
                        Spacer()
                        if vm.isRequestingDisbursement {
                            ProgressView().tint(Theme.canvas)
                        } else {
                            Text("Request Disbursement (Demo)")
                                .font(Theme.labelStyle)
                        }
                        Spacer()
                    }
                    .padding(Theme.Spacing.card)
                    .background(Theme.securityGold)
                    .foregroundColor(Theme.canvas)
                    .cornerRadius(Theme.CornerRadius.medium)
                }
                .buttonStyle(EKPressStyle())
                .disabled(vm.isRequestingDisbursement)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct DisbursementStatusRow: View {
    let disbursement: DisbursementDTO

    private var statusColor: Color {
        switch disbursement.parsedStatus {
        case .completed: return Theme.bullGreen
        case .failed: return Theme.bearRed
        case .pending: return Theme.holdAmber
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            GuillocheDivider()
            SummaryRow(label: "Status", value: disbursement.parsedStatus.displayName)
            if let amount = disbursement.disbursedAmountDisplay {
                SummaryRow(label: "Amount", value: amount)
            }
            if let nbfc = disbursement.nbfcName {
                SummaryRow(label: "NBFC (Demo)", value: nbfc)
            }
            if disbursement.parsedStatus == .failed, let reason = disbursement.failureReason {
                Text(reason)
                    .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                    .foregroundColor(Theme.bearRed)
            }
            Text("MOCK STATUS")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundColor(statusColor)
        }
    }
}
