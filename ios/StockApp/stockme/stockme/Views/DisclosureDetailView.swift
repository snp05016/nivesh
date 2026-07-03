import SwiftUI

// MARK: - DisclosureDetailView
//
// Generic screen that fetches and renders a DisclosureDTO by key from the
// REAL GET /api/v1/compliance/disclosures/{key} endpoint
// (backend/routers/compliance.py + backend/services/disclosure_service.py).
// DEMO-GRADE / ILLUSTRATIVE CONTENT ONLY — every disclosure body rendered
// here is clearly-labelled placeholder/demo copy for a portfolio project,
// NOT real legal advice, NOT a real regulatory filing, and does NOT
// reference any real SEBI/RBI registration or license number.

struct DisclosureDetailView: View {
    let key: DisclosureKey

    @State private var disclosure: DisclosureDTO?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            if isLoading && disclosure == nil {
                ProgressView().tint(Theme.securityGold)
            } else if let disclosure {
                content(disclosure)
            } else if let errorMessage {
                errorState(errorMessage)
            }
        }
        .navigationTitle(disclosure?.title ?? key.displayTitle)
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private func content(_ disclosure: DisclosureDTO) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.large) {
                Text(disclosure.title)
                    .font(Theme.engravedSerif(size: 22, weight: .bold))
                    .foregroundStyle(Theme.inkPrimary)

                demoBadge

                Text(disclosure.body)
                    .font(Theme.engravedSerif(size: 13, relativeTo: .subheadline))
                    .foregroundStyle(Theme.inkSecondary)

                if let sections = disclosure.sections, !sections.isEmpty {
                    GuillocheDivider()
                    VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                        ForEach(sections) { section in
                            SectionBlock(section: section)
                        }
                    }
                }
            }
            .padding(.horizontal, Theme.Spacing.screen)
            .padding(.vertical, Theme.Spacing.large)
        }
        .banknoteCard()
        .padding(.horizontal, Theme.Spacing.screen)
        .padding(.vertical, Theme.Spacing.large)
    }

    private var demoBadge: some View {
        Text("ILLUSTRATIVE DEMO CONTENT · NOT REAL LEGAL ADVICE")
            .font(Theme.officialStampFont(size: 9))
            .tracking(1.2)
            .padding(.horizontal, Theme.Spacing.medium)
            .padding(.vertical, Theme.Spacing.small)
            .foregroundStyle(Theme.holdAmber)
            .background(Theme.holdAmber.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.badge))
    }

    private func errorState(_ message: String) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Theme.bearRed)
            Text(message)
                .font(Theme.engravedSerif(size: 13, relativeTo: .subheadline))
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
        }
        .padding(Theme.Spacing.screen)
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        do {
            disclosure = try await NetworkManager.shared.fetchDisclosure(key: key.rawValue)
        } catch {
            errorMessage = "Couldn't load this disclosure. Pull down or try again later."
        }
        isLoading = false
    }
}

private struct SectionBlock: View {
    let section: DisclosureSection

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            if let heading = section.heading {
                Text(heading.uppercased())
                    .font(Theme.officialStampFont(size: 10))
                    .tracking(1.2)
                    .foregroundStyle(Theme.securityGold)
            }
            Text(section.text)
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Link row for embedding a "View <Disclosure>" entry inline in another
/// screen (Account Settings, Loan Application, FD Booking).
struct DisclosureLinkRow: View {
    let key: DisclosureKey
    var title: String? = nil
    var icon: String = "doc.text.magnifyingglass"

    var body: some View {
        NavigationLink(destination: DisclosureDetailView(key: key)) {
            HStack(spacing: Theme.Spacing.standard) {
                Image(systemName: icon)
                    .foregroundStyle(Theme.securityGold.opacity(0.7))
                Text(title ?? key.displayTitle)
                    .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.inkPrimary)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(Theme.inkTertiary)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(EKPressStyle())
    }
}

#Preview {
    NavigationStack { DisclosureDetailView(key: .privacyPolicy) }
}

// MARK: - KeyFactStatementView
//
// Small KFS-specific screen for the Loan Application / FD Booking flows.
// Fetches the computed Key Fact Statement (loan_amount/principal, interest
// rate, all_fees, apr, tenure) from the REAL
// GET /api/v1/compliance/key-fact-statement endpoint (backend/routers/
// compliance.py + backend/services/disclosure_service.py). DEMO-GRADE — see
// the 'apr_disclosure' DisclosureDetailView for the illustrative APR formula.

struct KeyFactStatementView: View {
    enum Source {
        case loanOffer(id: Int)
        case fdScheme(id: Int)
    }

    let source: Source

    @State private var kfs: KeyFactStatementDTO?
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            if isLoading && kfs == nil {
                ProgressView().tint(Theme.securityGold)
            } else if let kfs {
                content(kfs)
            } else if let errorMessage {
                VStack(spacing: Theme.Spacing.standard) {
                    Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Theme.bearRed)
                    Text(errorMessage)
                        .font(Theme.engravedSerif(size: 13, relativeTo: .subheadline))
                        .foregroundStyle(Theme.inkSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(Theme.Spacing.screen)
            }
        }
        .navigationTitle("Key Fact Statement")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private func content(_ kfs: KeyFactStatementDTO) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.large) {
                Text(kfs.issuerDisplayName)
                    .font(Theme.engravedSerif(size: 20, weight: .bold))
                    .foregroundStyle(Theme.inkPrimary)

                Text("ILLUSTRATIVE KEY FACT STATEMENT · DEMO")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.2)
                    .padding(.horizontal, Theme.Spacing.medium)
                    .padding(.vertical, Theme.Spacing.small)
                    .foregroundStyle(Theme.holdAmber)
                    .background(Theme.holdAmber.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.badge))

                VStack(spacing: Theme.Spacing.none) {
                    KFSRow(label: kfs.isFixedDeposit ? "Principal Amount" : "Loan Amount", value: kfs.amountDisplay)
                    GuillocheDivider()
                    KFSRow(label: "Interest Rate", value: kfs.interestRateDisplay)
                    GuillocheDivider()
                    KFSRow(label: "All Fees", value: kfs.feesDisplay)
                    GuillocheDivider()
                    KFSRow(label: "APR", value: kfs.aprDisplay, valueColor: Theme.securityGold)
                    GuillocheDivider()
                    KFSRow(label: "Tenure", value: kfs.tenureDisplay)
                }
                .banknoteCard()

                if let disclaimer = kfs.disclaimer {
                    Text(disclaimer)
                        .font(Theme.serialNumberFont(size: 10))
                        .foregroundStyle(Theme.inkTertiary)
                }

                DisclosureLinkRow(key: .aprDisclosure, title: "How APR Is Calculated")
                DisclosureLinkRow(key: kfs.isFixedDeposit ? .lendingServiceProvider : .digitalLendingCompliance)
            }
            .padding(.horizontal, Theme.Spacing.screen)
            .padding(.vertical, Theme.Spacing.large)
        }
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        do {
            switch source {
            case .loanOffer(let id):
                kfs = try await NetworkManager.shared.fetchKeyFactStatement(loanOfferId: id)
            case .fdScheme(let id):
                kfs = try await NetworkManager.shared.fetchKeyFactStatement(schemeId: id)
            }
        } catch {
            errorMessage = "Couldn't load the Key Fact Statement. Please try again."
        }
        isLoading = false
    }
}

private struct KFSRow: View {
    let label: String
    let value: String
    var valueColor: Color = Theme.inkPrimary

    var body: some View {
        HStack {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 10))
                .tracking(1.0)
                .foregroundStyle(Theme.inkTertiary)
            Spacer()
            Text(value)
                .font(Theme.serialNumberFont(size: 13))
                .foregroundStyle(valueColor)
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
    }
}
