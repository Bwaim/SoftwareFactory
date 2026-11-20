import AppKit
import UserNotifications

let sentCode: Int32 = 0
let deniedCode: Int32 = 1
let failedCode: Int32 = 2
let askedCode: Int32 = 3
let usageCode: Int32 = 64

/// The first run asks for permission. The answer can come long after the factory gave up waiting, so the notification
/// is not held: exit with askedCode, and the factory shows this one with osascript.
let permissionWaitSeconds = 5.0
let overallTimeoutSeconds = 10.0

final class Notifier: NSObject, NSApplicationDelegate {
    let title: String
    let body: String
    let sound: String
    let center = UNUserNotificationCenter.current()

    init(title: String, body: String, sound: String) {
        self.title = title
        self.body = body
        self.sound = sound
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        center.getNotificationSettings { settings in
            switch settings.authorizationStatus {
            case .notDetermined:
                self.askPermission()
            case .denied:
                exit(deniedCode)
            default:
                self.post()
            }
        }
    }

    func askPermission() {
        center.requestAuthorization(options: [.alert, .sound]) { granted, _ in
            guard granted else { exit(deniedCode) }
            self.post()
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + permissionWaitSeconds) { exit(askedCode) }
    }

    func post() {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        if !sound.isEmpty {
            content.sound = UNNotificationSound(named: UNNotificationSoundName(sound))
        }
        let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
        center.add(request) { error in
            exit(error == nil ? sentCode : failedCode)
        }
    }
}

let arguments = CommandLine.arguments
guard arguments.count == 4 else {
    FileHandle.standardError.write("usage: captn-notify <title> <body> <sound>\n".data(using: .utf8)!)
    exit(usageCode)
}
let app = NSApplication.shared
let notifier = Notifier(title: arguments[1], body: arguments[2], sound: arguments[3])
app.delegate = notifier
app.setActivationPolicy(.accessory)
DispatchQueue.main.asyncAfter(deadline: .now() + overallTimeoutSeconds) { exit(failedCode) }
app.run()
