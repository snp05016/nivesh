import AVFoundation
import Foundation

final class AppSoundManager {
    static let shared = AppSoundManager()
    private var player: AVAudioPlayer?

    func playRustling() {
        guard let url = Bundle.main.url(forResource: "rupee_rustle", withExtension: "mp3") else {
            // Add rupee_rustle.mp3 to the Xcode target (free from freesound.org, search "paper rustle")
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
            // Silent fallback — no crash if file missing or session fails
        }
    }
}
