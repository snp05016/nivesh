// SOUND POLICY (AGENTS.md §2.9 VIII + Fix 1.5):
// Rupee rustle sound LIMITED to: Trade Journal entry logged, AI Analysis complete.
// Do NOT trigger on: price updates, index refreshes, navigation, or scrolling.
// Fix 1.5: Opt-in via Settings toggle. Default: SILENT (haptic-only via EKPressHapticStyle).

import AVFoundation
import Foundation

final class AppSoundManager {
    static let shared = AppSoundManager()
    private var player: AVAudioPlayer?

    /// Fix 1.5: Opt-in transaction sound. Default false (silent haptic-only).
    static var isSoundEnabled: Bool {
        get { UserDefaults.standard.bool(forKey: "nivesh_sound_enabled_v1") }
        set { UserDefaults.standard.set(newValue, forKey: "nivesh_sound_enabled_v1") }
    }

    func playRustling() {
        guard AppSoundManager.isSoundEnabled else { return }
        guard let url = Bundle.main.url(forResource: "rupee_rustle", withExtension: "mp3") else {
            return
        }
        do {
            #if canImport(UIKit)
            try AVAudioSession.sharedInstance().setCategory(.ambient, mode: .default)
            try AVAudioSession.sharedInstance().setActive(true)
            #endif
            player = try AVAudioPlayer(contentsOf: url)
            player?.volume = 0.35
            player?.play()
        } catch {
            // Silent fallback
        }
    }
}
