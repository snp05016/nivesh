import SwiftUI

struct AdvisorBioCard: View {
    let advisor: AdvisorBiography
    @State private var isExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(advisor.advisorName)
                        .font(.subheadline.weight(.bold))
                        .foregroundStyle(Theme.inkPrimary)
                    Text("\(advisor.experienceYears) Years of Market Research")
                        .font(.caption)
                        .foregroundStyle(Theme.inkTertiary)
                }
                Spacer()
                // SEBI badge
                Text("SEBI\nREG")
                    .font(.caption2.weight(.bold))
                    .multilineTextAlignment(.center)
                    .foregroundStyle(Theme.bullGreen)
                    .padding(Theme.Spacing.tight)
                    .background(Theme.bullGreen.opacity(0.08))
                    .cornerRadius(Theme.CornerRadius.small)
            }

            // Framework tags
            if let framework = advisor.analyticalFramework {
                ScrollView(.horizontal) {
                    HStack(spacing: Theme.Spacing.small) {
                        ForEach(framework.components(separatedBy: ","), id: \.self) { tag in
                            Text(tag.trimmingCharacters(in: .whitespaces))
                                .font(.caption2)
                                .foregroundStyle(Theme.securityGold)
                                .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.small)
                                .background(Theme.securityGold.opacity(0.08))
                                .cornerRadius(Theme.CornerRadius.small)
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                }
                .scrollIndicators(.hidden)
            }

            // Biography
            Text(advisor.fullBiographyText)
                .font(.caption)
                .foregroundStyle(Theme.inkSecondary)
                .lineLimit(isExpanded ? nil : 4)
                .lineSpacing(3)

            // Expand button
            Button(isExpanded ? "Show Less" : "Read More") {
                withAnimation { isExpanded.toggle() }
            }
            .font(.caption2.weight(.medium))
            .foregroundStyle(Theme.securityGold)
        }
        .padding(Theme.Spacing.standard)
        .background(Theme.canvasDeep)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.borderSage, lineWidth: 0.5))
        .cornerRadius(Theme.CornerRadius.small)
    }
}
