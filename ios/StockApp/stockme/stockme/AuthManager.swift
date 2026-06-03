import Foundation
import Combine

@MainActor
class AuthManager: ObservableObject {
    @Published var currentUser: LoggedInUser? = nil
    @Published var isLoggingIn = false
    @Published var loginError: String? = nil

    private let key = "nivesh_user_v1"

    init() {
        if let data = UserDefaults.standard.data(forKey: key),
           let user = try? JSONDecoder().decode(LoggedInUser.self, from: data) {
            currentUser = user
            NetworkManager.shared.authToken = user.token
        }
    }

    var isLoggedIn: Bool { currentUser != nil }

    func login(username: String, password: String) async {
        isLoggingIn = true
        loginError = nil
        do {
            let user = try await NetworkManager.shared.login(username: username, password: password)
            currentUser = user
            NetworkManager.shared.authToken = user.token
            if let data = try? JSONEncoder().encode(user) {
                UserDefaults.standard.set(data, forKey: key)
            }
        } catch let e as NetworkError {
            loginError = e.errorDescription ?? "Login failed"
        } catch {
            loginError = "Wrong username or password"
        }
        isLoggingIn = false
    }
    
    func register(username: String, password: String, displayName: String) async {
        isLoggingIn = true
        loginError = nil
        do {
            let user = try await NetworkManager.shared.register(username: username, password: password, displayName: displayName)
            currentUser = user
            NetworkManager.shared.authToken = user.token
            if let data = try? JSONEncoder().encode(user) {
                UserDefaults.standard.set(data, forKey: key)
            }
        } catch let e as NetworkError {
            loginError = e.errorDescription ?? "Registration failed"
        } catch {
            loginError = "Failed to create account"
        }
        isLoggingIn = false
    }

    func logout() {
        currentUser = nil
        NetworkManager.shared.authToken = nil
        UserDefaults.standard.removeObject(forKey: key)
    }
}
