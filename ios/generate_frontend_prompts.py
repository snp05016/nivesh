import os

prompts = [
    ("Prompt 01: Build PKScreenerView", "Missing Frontend", "Create `PKScreenerView.swift` to display pure technical breakout signals directly from the backend `pkscreener_runner.py` output, bridging a feature gap."),
    ("Prompt 02: Build MacroDashboardView", "Missing Frontend", "Develop `MacroDashboardView.swift` to visualize data from `macro_modifiers.py` (e.g., Minskyan Risk, FII/DII Net Flows, USDINR)."),
    ("Prompt 03: Build DataFreshnessHUD", "Missing Frontend", "Implement `DataFreshnessHUD.swift` to show users exactly when `harvester.py` last fetched news, filings, and advisor videos."),
    ("Prompt 04: Implement PDFUploadView for RAG", "Missing Frontend", "Add `PDFUploadView.swift` in the Copilot section to allow users to upload filings and interact with backend `rag_ingestion.py`."),
    ("Prompt 05: Create AnalysisTimelineView", "Missing Frontend", "Build `AnalysisTimelineView.swift` to visualize `checkpoints.py` history, showing how AI signals and confidence shifted over months."),
    ("Prompt 06: Build PiotroskiBreakdownSheet", "Missing Frontend", "Create `PiotroskiBreakdownSheet.swift` to visually map the 9-point criteria computed by the backend `piotroski.py`."),
    ("Prompt 07: Build OptionsMicrostructureScreen", "Missing Frontend", "Implement `OptionsMicrostructureScreen.swift` to visualize Put/Call Ratio (PCR) and Gamma Exposure (GEX) from `microstructure_engine.py`."),
    ("Prompt 08: Create AdvisorVideoPlayer", "Missing Frontend", "Build a native `AdvisorVideoPlayer.swift` component to embed or link to YouTube URLs harvested by `expert_youtube_harvester.py`."),
    ("Prompt 09: Implement ScreenerFilterSheet", "Missing Frontend", "Develop `ScreenerFilterSheet.swift` to allow users to build NLP queries that natively hit the backend `nl_screener.py` logic."),
    ("Prompt 10: Build StrategyExecutionView", "Missing Frontend", "Create `StrategyExecutionView.swift` to visually track mocked paper-trading portfolios running on `strategy_engine.py`."),
    ("Prompt 11: Implement FeedbackInjectorUI", "Missing Frontend", "Add a thumbs-up/down and comment UI on AI analysis paragraphs to feed the backend `feedback_injector.py`."),
    ("Prompt 12: Build SectorRotationHeatmap", "Missing Frontend", "Develop a heatmap in `SectorRotationScreen.swift` to visualize `sector_rotation.py` RRG Quadrants (Leading, Weakening, Lagging, Improving)."),

    ("Prompt 13: Remove Hardcoded 192.168.1.122 URL", "Hardcoding", "Remove the hardcoded default URL `http://192.168.1.122:8000` from `NetworkManager.swift` and use Plist/XCConfig environment variables."),
    ("Prompt 14: Fix Hardcoded Network Timeouts", "Hardcoding", "Extract hardcoded timeout intervals (`timeoutIntervalForRequest = 30`) in `NetworkManager.swift` into a dynamic global configuration struct."),
    ("Prompt 15: Enforce Theme.Spacing strictly", "Hardcoding", "Audit all `.padding()` calls in SwiftUI Views to remove hardcoded integers and strictly enforce `Theme.Spacing.*` multiples of 8pt."),
    ("Prompt 16: Remove hardcoded system fonts", "Hardcoding", "Find and replace all `.font(.system(size:))` calls with `Theme.engravedSerif` or `Theme.serialNumberFont` to maintain Banknote aesthetic."),
    ("Prompt 17: Replace hardcoded hex colors", "Hardcoding", "Remove any raw `Color(hex:)` usage, particularly in charts, and replace with semantic tokens like `Theme.bullGreen` and `Theme.bearRed`."),
    ("Prompt 18: Remove 200-char Error limits", "Hardcoding", "Remove hardcoded `.prefix(200)` limits in `NetworkManager` error diagnostics to allow users to see full, scrollable stack traces."),
    ("Prompt 19: Dynamic Signal Mapping", "Hardcoding", "Move the hardcoded `_SIGNAL_MAP` equivalent logic out of `BanknoteDesignSystem.swift` into a remote configuration payload."),
    ("Prompt 20: Extract TimeZone Identifier", "Hardcoding", "Remove hardcoded `TimeZone(identifier: \"Asia/Kolkata\")` across views and centralize it in a shared `Formatters.swift` constant."),
    ("Prompt 21: Standardize Corner Radii", "Hardcoding", "Replace arbitrary `.cornerRadius(8)` modifiers with standard `Theme.CornerRadius.medium` throughout the app."),
    ("Prompt 22: Extract Animation Durations", "Hardcoding", "Move hardcoded animation durations (e.g. `duration: 1.2`) into a central `Theme.Animation` namespace for consistency."),
    ("Prompt 23: Dynamic Chart Domain Bounds", "Hardcoding", "Eliminate hardcoded chart axes limits (e.g., `yAxis(min: 0, max: 100)`) and calculate `ChartDomain` dynamically based on data ranges."),
    ("Prompt 24: Move Placeholders to Localizable.strings", "Hardcoding", "Extract all hardcoded English placeholder text in Search and Copilot screens into a `Localizable.strings` file for future l10n."),
    ("Prompt 25: Backend-driven regex for Tickers", "Hardcoding", "Refactor `classifyNumericInput` in `NetworkManager` to use a backend-supplied regex instead of hardcoded `.count >= 5` logic."),
    ("Prompt 26: Extract Batch Analysis Limit", "Hardcoding", "Extract the hardcoded `20` limit for batch requests in the UI into a shared constant synced with backend capabilities."),
    ("Prompt 27: Implement Endpoint Enum Router", "Hardcoding", "Remove raw URL string interpolations in `NetworkManager.swift` and implement a strict, type-safe `Endpoint` enum router."),

    ("Prompt 28: Enforce EKPressStyle globally", "UX/Aesthetic", "Audit all SwiftUI `Button` instances to ensure 100% compliance with `.buttonStyle(EKPressStyle())` or `.ekPress()` modifier."),
    ("Prompt 29: Enforce Haptic Feedback", "UX/Aesthetic", "Add `HapticManager.selection()` triggers to all segment pickers, checkboxes, and list tap gestures across the app."),
    ("Prompt 30: Replace standard Divider", "UX/Aesthetic", "Replace all generic SwiftUI `Divider()` components with the bespoke `GuillocheDivider()` component."),
    ("Prompt 31: Themed Scroll Indicators", "UX/Aesthetic", "Modify all standard `ScrollView` instances to use custom scroll indicators tailored to the Banknote Aesthetic."),
    ("Prompt 32: Enforce banknoteCard modifier", "UX/Aesthetic", "Replace custom `RoundedRectangle` card backgrounds with the unified `.banknoteCard()` view modifier for consistent shadows and borders."),
    ("Prompt 33: Apply stampAppear modifier", "UX/Aesthetic", "Ensure every `BanknoteSignalBadge` (e.g., BULLISH/BEARISH) uses the `.stampAppear()` modifier to animate onto the screen like a physical stamp."),
    ("Prompt 34: Add RupeeWatermark globally", "UX/Aesthetic", "Inject the `RupeeWatermark` into the background `ZStack` of all deep-dive detail screens to enhance the currency theme."),
    ("Prompt 35: Enhance GovernorSealAvatar", "UX/Aesthetic", "Upgrade `GovernorSealAvatar` to support dynamic user profile images masked exactly by the seal's concentric outline."),
    ("Prompt 36: Enforce IndianFormatter.formatLakhsCrores", "UX/Aesthetic", "Audit all money displays to ensure strict usage of `IndianFormatter.formatLakhsCrores()`. Forbid generic western numbering (millions/billions)."),
    ("Prompt 37: Fix Unidirectional Data Flow", "UX/Aesthetic", "Refactor screens passing `@ObservedObject` ViewModels 4 levels deep; replace with `@EnvironmentObject` or lightweight `@Binding`s."),
    ("Prompt 38: Enforce Infinity max-width", "UX/Aesthetic", "Find hardcoded `.frame(width: 350)` elements and replace with `.frame(maxWidth: .infinity).padding(.horizontal, Theme.screenPadding)`."),
    ("Prompt 39: Forbid GeometryReader in HStacks", "UX/Aesthetic", "Remove `GeometryReader` instances inside `HStack` or horizontal `ScrollView`s and replace with proportional screen width math."),
    ("Prompt 40: Implement numericText Transitions", "UX/Aesthetic", "Upgrade `PortfolioValueDisplay` and similar numeric views to use `.contentTransition(.numericText())` for smooth ticker animations."),
    ("Prompt 41: Replace blocking spinners with Skeletons", "UX/Aesthetic", "Implement shimmer skeleton loaders for all network requests instead of using blocking `ProgressView()` spinners."),
    ("Prompt 42: Respect ReduceMotion Accessibility", "UX/Aesthetic", "Add an `@Environment(\\.accessibilityReduceMotion)` check to disable `StampAppear` and spring animations for accessible users."),

    ("Prompt 43: Complete async/await migration", "Architecture", "Refactor any remaining legacy closures or Combine publishers in `NetworkManager.swift` to modern Swift concurrency (`async/await`)."),
    ("Prompt 44: Implement NSCache ImageCache", "Architecture", "Create a robust `ImageCache` service using `NSCache` for advisor avatars and news thumbnails to prevent redundant network downloads."),
    ("Prompt 45: Break down StockDatabase", "Architecture", "Refactor the massive `StockDatabase.swift` file (400kb) into separate, domain-specific CoreData or SwiftData files."),
    ("Prompt 46: Lazy-load AnalysisScreen components", "Architecture", "Optimize `AnalysisScreen.swift` (120kb) by extracting heavy views into separate files and using `LazyVStack` to reduce memory footprint."),
    ("Prompt 47: Remove redundant onAppear fetches", "Architecture", "Remove `NetworkManager` API calls from the `.onAppear` of deeply nested subviews to prevent rapid-fire redundant requests during scrolling."),
    ("Prompt 48: Implement Search Debounce", "Architecture", "Implement Combine-based text debouncing in `SearchScreen.swift`'s view model to prevent spamming the backend `/search` endpoint."),
    ("Prompt 49: Cache JSONDecoder instance", "Architecture", "Refactor `NetworkManager.swift` to instantiate and reuse a single `JSONDecoder` instance instead of creating a new one per network request."),
    ("Prompt 50: Implement Offline Mode", "Architecture", "Add logic in `NetworkManager` to detect `NSURLErrorNotConnectedToInternet` and seamlessly fallback to cached CoreData/SwiftData models."),
    ("Prompt 51: Fix PortfolioScreen full-state reloads", "Architecture", "Replace heavy full-screen `@State` updates in `PortfolioScreen.swift` with granular `Equatable` view wrappers to stop frame drops."),
    ("Prompt 52: Fix HomeFeedViewModel memory leaks", "Architecture", "Audit closures in `HomeFeedViewModel.swift` and `NetworkManager.swift` to ensure `[weak self]` is used, preventing retain cycles."),
    ("Prompt 53: Move Chart calculations to background Task", "Architecture", "Shift computationally expensive chart data normalization away from the MainActor/main thread and into detached background `Task`s."),
    ("Prompt 54: Audit EnvironmentObject over-invalidation", "Architecture", "Reduce the scope of `@EnvironmentObject` usage. Split mega-objects into smaller stores so changing one property doesn't redraw the whole app."),
    ("Prompt 55: Split Models.swift monolith", "Architecture", "Break the massive `Models.swift` (70kb) into a clean folder structure (`Models/Responses`, `Models/Requests`, `Models/Entities`)."),
    ("Prompt 56: Network Retry with Exponential Backoff", "Architecture", "Implement a generic network retry loop with jittered exponential backoff inside `NetworkManager.dataWithRetry()` to handle flaky 5G connections.")
]

import os

target_dir = "/Users/saumya/Desktop/nivesh/prompts/automated frontend improvements"
os.makedirs(target_dir, exist_ok=True)

rankings = []

for i, (title, category, desc) in enumerate(prompts):
    rank = i + 1
    
    clean_title = title.split(': ')[1] if ': ' in title else title
    file_name = f"rank_{rank:02d}_{clean_title.lower().replace(' ', '_').replace('/', '_').replace('-', '_')}.md"
    file_path = os.path.join(target_dir, file_name)
    
    content = f"# {title}\n\n"
    content += f"**Category:** {category}\n\n"
    content += f"**Goal:** Analyze the iOS frontend architecture to address this specific issue.\n\n"
    content += f"**Problem Statement / Description:**\n{desc}\n\n"
    content += f"**Why it will improve the system:**\n"
    if category == "Missing Frontend":
        content += "It exposes powerful backend data engines to the user, closing the feature parity gap and maximizing the value of existing backend code.\n\n"
    elif category == "Hardcoding":
        content += "It makes the frontend application dynamic, config-driven, and robust against backend URL or data structure changes without requiring App Store updates.\n\n"
    elif category == "UX/Aesthetic":
        content += "It strictly enforces the 'Banknote Aesthetic' and Nivesh design language, ensuring the app feels premium, native, and highly polished.\n\n"
    else:
        content += "It drastically improves scroll performance, reduces memory leaks, and ensures battery-efficient network usage.\n\n"
    content += f"**What you have to do:**\n"
    content += "1. Read the relevant iOS Swift files (Views, ViewModels, NetworkManager).\n"
    content += "2. Design the SwiftUI view or structural fix.\n"
    content += "3. Implement the changes following unidirectional data flow.\n"
    content += "4. Build and verify in Xcode / Previews.\n"
    
    with open(file_path, "w") as f:
        f.write(content)
        
    rankings.append((rank, title, file_name))

rank_file_path = os.path.join(target_dir, "rank.md")
with open(rank_file_path, "w") as f:
    f.write("# Automated Frontend Improvements - Ranking (1-56)\n\n")
    for rank, title, file_name in rankings:
        f.write(f"{rank}. [{title}](./{file_name})\n")

print(f"Generated 56 frontend prompts and rank.md in {target_dir}")
