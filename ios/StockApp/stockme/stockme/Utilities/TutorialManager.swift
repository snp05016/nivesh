import SwiftUI
import Combine

class TutorialManager: ObservableObject {
    static let udKey = "nivesh_tutorial_completed_v1"

    @Published var isShowingTutorial: Bool
    @Published var currentStep: Int = 1
    let totalSteps = 10

    init() {
        let completed = UserDefaults.standard.bool(forKey: Self.udKey)
        isShowingTutorial = !completed
    }

    func next() {
        withAnimation(.spring(response: 0.5, dampingFraction: 0.8)) {
            if currentStep < totalSteps {
                currentStep += 1
            } else {
                complete()
            }
        }
    }

    func previous() {
        withAnimation(.spring(response: 0.5, dampingFraction: 0.8)) {
            if currentStep > 1 { currentStep -= 1 }
        }
    }

    func skip() {
        UserDefaults.standard.set(true, forKey: Self.udKey)
        withAnimation { isShowingTutorial = false }
    }

    func complete() {
        UserDefaults.standard.set(true, forKey: Self.udKey)
        withAnimation { isShowingTutorial = false }
    }

    func resetForTesting() {
        UserDefaults.standard.removeObject(forKey: Self.udKey)
        currentStep = 1
    }
}
