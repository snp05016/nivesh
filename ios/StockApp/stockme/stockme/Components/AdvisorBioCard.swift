import SwiftUI

struct AdvisorBioCard: View {
    let advisor: AdvisorBiography
    @State private var isExpanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(advisor.advisorName)
                        .font(.system(size: 15, weight: .bold))
                        .foregroundColor(Theme.inkPrimary)
                    Text("\(advisor.experienceYears) Years of Market Research")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.inkTertiary)
                }
                Spacer()
                // SEBI badge
                Text("SEBI\nREG")
                    .font(.system(size: 7, weight: .bold))
                    .multilineTextAlignment(.center)
                    .foregroundColor(Theme.bullGreen)
                    .padding(6)
                    .background(Theme.bullGreen.opacity(0.08))
                    .cornerRadius(4)
            }

            // Framework tags
            if let framework = advisor.analyticalFramework {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 4) {
                        ForEach(framework.components(separatedBy: ","), id: \.self) { tag in
                            Text(tag.trimmingCharacters(in: .whitespaces))
                                .font(.system(size: 8))
                                .foregroundColor(Theme.securityGold)
                                .padding(.horizontal, 6).padding(.vertical, 3)
                                .background(Theme.securityGold.opacity(0.08))
                                .cornerRadius(3)
                        }
                    }
                }
            }

            // Biography
            Text(advisor.fullBiographyText)
                .font(.system(size: 11))
                .foregroundColor(Theme.inkSecondary)
                .lineLimit(isExpanded ? nil : 4)
                .lineSpacing(3)

            // Expand button
            Button(isExpanded ? "Show Less" : "Read More") {
                withAnimation { isExpanded.toggle() }
            }
            .font(.system(size: 10, weight: .medium))
            .foregroundColor(Theme.securityGold)
        }
        .padding(14)
        .background(Theme.canvasDeep)
        .overlay(RoundedRectangle(cornerRadius: 4).stroke(Theme.borderSage, lineWidth: 0.5))
        .cornerRadius(4)
    }
}
