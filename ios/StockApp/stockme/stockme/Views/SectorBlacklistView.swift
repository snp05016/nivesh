import SwiftUI

struct SectorBlacklistView: View {
    @AppStorage("nivesh_sectorBlacklist") private var blacklistData: Data = Data()
    @State private var excludedSectors: Set<String> = []

    private let allSectors = [
        "Banking", "IT", "Pharma", "Auto", "FMCG",
        "Metals", "Energy", "Realty", "Media", "PSU",
    ]

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .twoHundred)

            List {
                Section {
                    ForEach(allSectors, id: \.self) { sector in
                        HStack {
                            Text(sector)
                                .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                                .foregroundStyle(Theme.inkPrimary)
                            Spacer()
                            if excludedSectors.contains(sector) {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundStyle(Theme.bearRed)
                            } else {
                                Image(systemName: "circle")
                                    .foregroundStyle(Theme.inkTertiary)
                            }
                        }
                        .contentShape(Rectangle())
                        .onTapGesture {
                            HapticManager.selection()
                            if excludedSectors.contains(sector) {
                                excludedSectors.remove(sector)
                            } else {
                                excludedSectors.insert(sector)
                            }
                            save()
                        }
                    }
                } header: {
                    Text("EXCLUDED SECTORS").font(Theme.officialStampFont(size: 9)).tracking(1.5)
                } footer: {
                    Text("Stocks in excluded sectors will not appear in screener results or alerts.")
                        .font(Theme.engravedSerif(size: 11))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Sector Blacklist")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .onAppear { load() }
    }

    private func load() {
        if let decoded = try? JSONDecoder().decode(Set<String>.self, from: blacklistData) {
            excludedSectors = decoded
        }
    }

    private func save() {
        if let encoded = try? JSONEncoder().encode(excludedSectors) {
            blacklistData = encoded
        }
    }
}
