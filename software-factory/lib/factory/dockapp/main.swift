import AppKit
import Foundation
import WebKit

let appName = "CAPTN Dashboard"
let localHost = "127.0.0.1"
let messageHandlerName = "captn"
let skipQuitWarningKey = "skipQuitWarning"
let pingSeconds = 60.0
let quitCommandSeconds = 10.0
let dashboardCommandSeconds = 300.0
let loginShellSeconds = 10.0
let brandPurple = NSColor(srgbRed: 0x67 / 255.0, green: 0x38 / 255.0, blue: 0x88 / 255.0, alpha: 1)

struct CommandResult {
    let status: Int32
    let output: String
    let error: String

    var succeeded: Bool { status == 0 }
    var combinedOutput: String {
        [error, output].map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }.joined(separator: "\n")
    }
}

final class PipeReader {
    let pipe = Pipe()
    private var data = Data()
    private let done = DispatchGroup()

    func start() {
        done.enter()
        DispatchQueue.global().async {
            self.data = self.pipe.fileHandleForReading.readDataToEndOfFile()
            self.done.leave()
        }
    }

    func text() -> String {
        guard done.wait(timeout: .now() + 2) == .success else { return "" }
        return String(decoding: data, as: UTF8.self)
    }
}

enum Command {
    static func run(_ executable: String, _ arguments: [String], environment: [String: String], timeout: TimeInterval) -> CommandResult? {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        process.currentDirectoryURL = URL(fileURLWithPath: NSHomeDirectory())
        process.environment = environment
        process.standardInput = FileHandle.nullDevice
        let output = PipeReader()
        let errors = PipeReader()
        process.standardOutput = output.pipe
        process.standardError = errors.pipe
        let finished = DispatchSemaphore(value: 0)
        process.terminationHandler = { _ in finished.signal() }
        do {
            try process.run()
        } catch {
            return CommandResult(status: -1, output: "", error: "\(executable): \(error.localizedDescription)")
        }
        output.start()
        errors.start()
        guard finished.wait(timeout: .now() + timeout) == .success else {
            process.terminate()
            return nil
        }
        return CommandResult(status: process.terminationStatus, output: output.text(), error: errors.text())
    }
}

enum LoginEnvironment {
    static let values: [String: String] = withUTF8(withTools(load()))
    static let dropped: Set<String> = ["_", "SHLVL", "PWD", "OLDPWD"]

    static func load() -> [String: String] {
        let current = ProcessInfo.processInfo.environment
        let shell = current["SHELL"].flatMap { $0.isEmpty ? nil : $0 } ?? "/bin/zsh"
        let result = Command.run(shell, ["-l", "-c", "env -0"], environment: current, timeout: loginShellSeconds)
        guard let output = result?.output else { return current }
        let parsed = parse(output)
        return parsed["PATH"] == nil ? current : parsed
    }

    static func parse(_ text: String) -> [String: String] {
        var values: [String: String] = [:]
        for line in text.split(separator: "\0") {
            guard let equals = line.firstIndex(of: "=") else { continue }
            let key = String(line[..<equals])
            guard isName(key), !dropped.contains(key) else { continue }
            values[key] = String(line[line.index(after: equals)...])
        }
        return values
    }

    static func isName(_ key: String) -> Bool {
        guard let first = key.unicodeScalars.first, !CharacterSet.decimalDigits.contains(first) else { return false }
        return key.unicodeScalars.allSatisfy { $0 == "_" || ($0.isASCII && CharacterSet.alphanumerics.contains($0)) }
    }

    static func withTools(_ environment: [String: String]) -> [String: String] {
        var path = (environment["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin").split(separator: ":").map(String.init)
        for dir in ["/opt/homebrew/bin", "/usr/local/bin", NSHomeDirectory() + "/.local/bin"] where !path.contains(dir) {
            path.append(dir)
        }
        var values = environment
        values["PATH"] = path.joined(separator: ":")
        return values
    }

    static func withUTF8(_ environment: [String: String]) -> [String: String] {
        let locale = ["LC_ALL", "LC_CTYPE", "LANG"].contains { !(environment[$0] ?? "").isEmpty }
        guard !locale else { return environment }
        var values = environment
        values["LANG"] = "en_US.UTF-8"
        return values
    }
}

enum Factory {
    static var uv: String { infoString("CAPTNUv") }
    static var script: String { infoString("CAPTNFactory") }

    static func infoString(_ key: String) -> String {
        Bundle.main.object(forInfoDictionaryKey: key) as? String ?? ""
    }

    static func run(_ arguments: [String], timeout: TimeInterval) -> CommandResult? {
        var environment = LoginEnvironment.values
        environment["FACTORY_DOCK_APP"] = "1"
        return Command.run(uv, ["run", "--script", script] + arguments, environment: environment, timeout: timeout)
    }

    static func runInBackground(_ arguments: [String], timeout: TimeInterval, then finish: @escaping (CommandResult?) -> Void) {
        DispatchQueue.global(qos: .userInitiated).async {
            let result = run(arguments, timeout: timeout)
            DispatchQueue.main.async { finish(result) }
        }
    }

    static func dashboardURL(in result: CommandResult) -> URL? {
        let prefix = "Dashboard: "
        let line = result.output.split(whereSeparator: \.isNewline).last { $0.hasPrefix(prefix) }
        return line.flatMap { URL(string: $0.dropFirst(prefix.count).trimmingCharacters(in: .whitespaces)) }
    }

    static func waitingTasks(in result: CommandResult?) -> [String]? {
        guard let result, result.succeeded, let data = result.output.data(using: .utf8) else { return nil }
        guard let list = (try? JSONSerialization.jsonObject(with: data)) as? [Any] else { return nil }
        return list.map { "\($0)" }
    }
}

enum ServerAddress {
    static func token(of url: URL) -> String? {
        URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems?.first { $0.name == "token" }?.value
    }

    static func rebase(_ url: URL, onto base: URL) -> URL {
        guard var parts = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let baseParts = URLComponents(url: base, resolvingAgainstBaseURL: false) else { return url }
        parts.host = baseParts.host
        parts.port = baseParts.port
        let token = URLQueryItem(name: "token", value: token(of: base))
        var items = parts.queryItems ?? []
        if let index = items.firstIndex(where: { $0.name == "token" }) {
            items[index] = token
        } else {
            items.append(token)
        }
        parts.queryItems = items
        return parts.url ?? url
    }

    static func isFactoryPage(_ url: URL) -> Bool {
        ["http", "https"].contains(url.scheme) && url.host == localHost
    }

    static func staysInApp(_ url: URL) -> Bool {
        isFactoryPage(url) || ["about", "data", "blob"].contains(url.scheme)
    }

    static func ping(_ base: URL, then finish: @escaping (Bool) -> Void) {
        guard var parts = URLComponents(url: base, resolvingAgainstBaseURL: false) else { return finish(false) }
        parts.path = "/api/ping"
        parts.query = nil
        guard let url = parts.url else { return finish(false) }
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 5)
        request.setValue(token(of: base), forHTTPHeaderField: "X-Factory-Token")
        URLSession.shared.dataTask(with: request) { _, response, _ in
            let up = (response as? HTTPURLResponse)?.statusCode == 200
            DispatchQueue.main.async { finish(up) }
        }.resume()
    }
}

final class StatusScreen: NSView {
    private let title = NSTextField(labelWithString: "")
    private let detailsScroll = NSTextView.scrollableTextView()
    private var details: NSTextView { detailsScroll.documentView as! NSTextView }
    private let button = NSButton(title: "", target: nil, action: nil)
    private var onClick: (() -> Void)?

    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor
        title.font = .systemFont(ofSize: 22, weight: .semibold)
        title.alignment = .center
        setUpDetails()
        button.bezelColor = brandPurple
        button.target = self
        button.action = #selector(clicked)
        let stack = NSStackView(views: [title, detailsScroll, button])
        stack.orientation = .vertical
        stack.spacing = 16
        stack.translatesAutoresizingMaskIntoConstraints = false
        addSubview(stack)
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: centerYAnchor),
            stack.widthAnchor.constraint(lessThanOrEqualTo: widthAnchor, constant: -48),
            preferredWidth(of: detailsScroll),
            detailsScroll.heightAnchor.constraint(equalToConstant: 240),
        ])
    }

    required init?(coder: NSCoder) { nil }

    private func preferredWidth(of view: NSView) -> NSLayoutConstraint {
        let width = view.widthAnchor.constraint(equalToConstant: 560)
        width.priority = .defaultHigh
        return width
    }

    override func viewDidChangeEffectiveAppearance() {
        super.viewDidChangeEffectiveAppearance()
        effectiveAppearance.performAsCurrentDrawingAppearance {
            layer?.backgroundColor = NSColor.windowBackgroundColor.cgColor
        }
    }

    private func setUpDetails() {
        details.isEditable = false
        details.font = .monospacedSystemFont(ofSize: 11, weight: .regular)
        detailsScroll.borderType = .bezelBorder
    }

    func show(title text: String, details detailText: String = "", button buttonTitle: String? = nil, onClick action: (() -> Void)? = nil) {
        title.stringValue = text
        title.isHidden = text.isEmpty
        details.string = detailText
        detailsScroll.isHidden = detailText.isEmpty
        button.title = buttonTitle ?? ""
        button.isHidden = buttonTitle == nil
        onClick = action
        isHidden = false
    }

    func hide() {
        isHidden = true
        onClick = nil
    }

    @objc private func clicked() {
        onClick?()
    }
}

final class MessageRelay: NSObject, WKScriptMessageHandler {
    weak var app: AppDelegate?

    init(app: AppDelegate) {
        self.app = app
    }

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        app?.pageSaid(message.body as? String ?? "")
    }
}

final class PageWindow: NSObject, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate {
    unowned let app: AppDelegate
    let window: NSWindow
    let webView: WKWebView
    let screen = StatusScreen()
    private var titleObservation: NSKeyValueObservation?

    init(app: AppDelegate, configuration: WKWebViewConfiguration) {
        self.app = app
        webView = WKWebView(frame: .zero, configuration: configuration)
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1280, height: 860),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        super.init()
        window.title = appName
        window.tabbingMode = .preferred
        window.tabbingIdentifier = appName
        window.isReleasedWhenClosed = false
        window.delegate = self
        window.setFrameAutosaveName(appName)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        setUpContent()
        titleObservation = webView.observe(\.title) { [weak self] web, _ in
            let title = web.title ?? ""
            self?.window.title = title.isEmpty ? appName : title
        }
    }

    private func setUpContent() {
        let content = NSView()
        for view in [webView, screen] as [NSView] {
            view.translatesAutoresizingMaskIntoConstraints = false
            content.addSubview(view)
            NSLayoutConstraint.activate([
                view.leadingAnchor.constraint(equalTo: content.leadingAnchor),
                view.trailingAnchor.constraint(equalTo: content.trailingAnchor),
                view.topAnchor.constraint(equalTo: content.topAnchor),
                view.bottomAnchor.constraint(equalTo: content.bottomAnchor),
            ])
        }
        screen.isHidden = true
        window.contentView = content
    }

    func load(_ url: URL) {
        webView.load(URLRequest(url: url))
    }

    func reload(base: URL?) {
        guard let base else {
            webView.reload()
            return
        }
        load(ServerAddress.rebase(webView.url ?? base, onto: base))
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        app.windowShouldClose(self)
    }

    func windowWillClose(_ notification: Notification) {
        titleObservation = nil
        app.windowWillClose(self)
    }

    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url, !ServerAddress.staysInApp(url) else { return decisionHandler(.allow) }
        NSWorkspace.shared.open(url)
        decisionHandler(.cancel)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        if (error as NSError).code != NSURLErrorCancelled {
            app.serverMayBeDown()
        }
    }

    func webView(
        _ webView: WKWebView,
        createWebViewWith configuration: WKWebViewConfiguration,
        for action: WKNavigationAction,
        windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        if let url = action.request.url, !ServerAddress.staysInApp(url) {
            NSWorkspace.shared.open(url)
            return nil
        }
        return app.openTab(next: self, configuration: configuration).webView
    }
}

enum QuitChoice {
    case cancel
    case quit(stopServer: Bool)
}

enum QuitAlert {
    static func ask(waitingTasks: [String]?) -> QuitChoice {
        guard let tasks = waitingTasks else {
            return askStopOrKeep("Cannot list the waiting tasks.")
        }
        if !tasks.isEmpty {
            let ids = tasks.joined(separator: ", ")
            return askStopOrKeep("Tasks wait on a done check: \(ids). Quitting stops their done checks.")
        }
        if UserDefaults.standard.bool(forKey: skipQuitWarningKey) {
            return .quit(stopServer: true)
        }
        return askQuit()
    }

    static func askStopOrKeep(_ message: String) -> QuitChoice {
        let alert = makeAlert(message, buttons: ["Stop", "Keep server running", "Cancel"])
        switch alert.runModal() {
        case .alertFirstButtonReturn: return .quit(stopServer: true)
        case .alertSecondButtonReturn: return .quit(stopServer: false)
        default: return .cancel
        }
    }

    static func askQuit() -> QuitChoice {
        let alert = makeAlert("Quitting CAPTN Dashboard stops the factory server.", buttons: ["Quit", "Cancel"])
        alert.showsSuppressionButton = true
        alert.suppressionButton?.title = "Don't show again"
        guard alert.runModal() == .alertFirstButtonReturn else { return .cancel }
        if alert.suppressionButton?.state == .on {
            UserDefaults.standard.set(true, forKey: skipQuitWarningKey)
        }
        return .quit(stopServer: true)
    }

    static func makeAlert(_ message: String, buttons: [String]) -> NSAlert {
        let alert = NSAlert()
        alert.messageText = message
        alert.alertStyle = .warning
        for title in buttons {
            alert.addButton(withTitle: title)
        }
        alert.buttons.last?.keyEquivalent = "\u{1b}"
        return alert
    }
}

enum QuitReason {
    static let systemReasons: Set<OSType> = [
        OSType(kAELogOut), OSType(kAEReallyLogOut), OSType(kAEShowRestartDialog),
        OSType(kAERestart), OSType(kAEShowShutdownDialog), OSType(kAEShutDown),
    ]

    static func isSystemShutdown() -> Bool {
        let event = NSAppleEventManager.shared().currentAppleEvent
        guard let reason = event?.attributeDescriptor(forKeyword: AEKeyword(kAEQuitReason))?.typeCodeValue else { return false }
        return systemReasons.contains(reason)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    let processPool = WKProcessPool()
    lazy var relay = MessageRelay(app: self)
    var pages: [PageWindow] = []
    var dashboard: PageWindow?
    var base: URL?
    var receivedURL = false
    var loadCount = 0
    var starting = false
    var checkingServer = false
    var serverStopped = false
    var pingTimer: Timer?
    var quitConfirmed = false
    var stopServerOnQuit = false
    var quitCheckRunning = false
    var keepAwake: NSObjectProtocol?

    func applicationWillFinishLaunching(_ notification: Notification) {
        NSApp.mainMenu = MainMenu.build(target: self)
        NSAppleEventManager.shared().setEventHandler(
            self,
            andSelector: #selector(handleURLEvent(_:reply:)),
            forEventClass: AEEventClass(kInternetEventClass),
            andEventID: AEEventID(kAEGetURL)
        )
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        keepAwake = ProcessInfo.processInfo.beginActivity(
            options: .userInitiatedAllowingIdleSystemSleep,
            reason: "Keep the factory server alive"
        )
        DispatchQueue.global(qos: .userInitiated).async {
            _ = LoginEnvironment.values
        }
        pingTimer = Timer.scheduledTimer(withTimeInterval: pingSeconds, repeats: true) { [weak self] _ in
            self?.checkServer(confirmations: 2)
        }
        if !receivedURL {
            startFactory()
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        guard dashboard == nil else { return true }
        if starting {
            showStarting()
        } else if serverStopped {
            showServerStopped()
        } else if let base {
            showDashboard().load(base)
        } else {
            startFactory()
        }
        return false
    }

    @objc func handleURLEvent(_ event: NSAppleEventDescriptor, reply: NSAppleEventDescriptor) {
        guard let text = event.paramDescriptor(forKeyword: AEKeyword(keyDirectObject))?.stringValue,
              let url = URL(string: text) else { return }
        guard ServerAddress.isFactoryPage(url) else {
            NSWorkspace.shared.open(url)
            return
        }
        receivedURL = true
        loadDashboard(url)
        NSApp.activate(ignoringOtherApps: true)
    }

    func loadDashboard(_ url: URL) {
        loadCount += 1
        base = url
        serverStopped = false
        let page = showDashboard()
        page.screen.hide()
        page.load(url)
    }

    func startFactory() {
        guard !starting else { return }
        starting = true
        let request = loadCount
        showStarting()
        Factory.runInBackground(["dashboard"], timeout: dashboardCommandSeconds) { [weak self] result in
            self?.factoryStarted(result, request: request)
        }
    }

    func showStarting() {
        showDashboard().screen.show(title: "Starting the factory…")
    }

    func factoryStarted(_ result: CommandResult?, request: Int) {
        starting = false
        guard request == loadCount else { return }
        if let result, result.succeeded, let url = Factory.dashboardURL(in: result) {
            return loadDashboard(url)
        }
        let details = result.map { $0.combinedOutput.isEmpty ? "factory dashboard exited with status \($0.status)." : $0.combinedOutput }
        showDashboard().screen.show(
            title: "",
            details: details ?? "factory dashboard did not finish in time.",
            button: "Try again"
        ) { [weak self] in self?.startFactory() }
    }

    @discardableResult
    func showDashboard() -> PageWindow {
        if let dashboard {
            dashboard.window.makeKeyAndOrderFront(nil)
            return dashboard
        }
        let page = makePage(configuration: newConfiguration())
        dashboard = page
        if let other = pages.first(where: { $0 !== page })?.window {
            other.addTabbedWindow(page.window, ordered: .below)
        } else {
            page.window.center()
        }
        page.window.makeKeyAndOrderFront(nil)
        return page
    }

    func openTab(next opener: PageWindow, configuration: WKWebViewConfiguration) -> PageWindow {
        let page = makePage(configuration: configuration)
        opener.window.addTabbedWindow(page.window, ordered: .above)
        page.window.makeKeyAndOrderFront(nil)
        return page
    }

    func makePage(configuration: WKWebViewConfiguration) -> PageWindow {
        let page = PageWindow(app: self, configuration: configuration)
        pages.append(page)
        return page
    }

    func newConfiguration() -> WKWebViewConfiguration {
        let configuration = WKWebViewConfiguration()
        configuration.processPool = processPool
        configuration.userContentController.add(relay, name: messageHandlerName)
        configuration.preferences.isElementFullscreenEnabled = true
        return configuration
    }

    func windowWillClose(_ page: PageWindow) {
        pages.removeAll { $0 === page }
        if dashboard === page {
            dashboard = nil
        }
    }

    @objc func reloadPage(_ sender: Any?) {
        let key = NSApp.keyWindow
        pages.first { $0.window === key }?.reload(base: base)
    }

    func pageSaid(_ message: String) {
        if message == "unreachable" {
            serverMayBeDown()
        }
    }

    func serverMayBeDown() {
        checkServer(confirmations: 1)
    }

    func checkServer(confirmations: Int) {
        guard let base, !checkingServer, !serverStopped, !starting else { return }
        checkingServer = true
        ping(base, tries: confirmations) { [weak self] up in
            self?.serverChecked(up: up, base: base)
        }
    }

    func ping(_ base: URL, tries: Int, then finish: @escaping (Bool) -> Void) {
        ServerAddress.ping(base) { [weak self] up in
            if up || tries <= 1 {
                finish(up)
            } else {
                self?.ping(base, tries: tries - 1, then: finish)
            }
        }
    }

    func serverChecked(up: Bool, base checked: URL) {
        checkingServer = false
        guard !up, checked == base, !starting else { return }
        serverStopped = true
        showServerStopped()
    }

    func showServerStopped() {
        showDashboard().screen.show(title: "Server stopped", button: "Start") { [weak self] in
            self?.startFactory()
        }
    }

    func windowShouldClose(_ page: PageWindow) -> Bool {
        guard pages.count == 1, !quitConfirmed else { return true }
        if !quitCheckRunning {
            checkBeforeQuit { [weak self] choice in self?.windowQuitChecked(choice) }
        }
        return false
    }

    func windowQuitChecked(_ choice: QuitChoice) {
        guard case .quit(let stopServer) = choice else { return }
        quitConfirmed = true
        stopServerOnQuit = stopServer
        NSApp.terminate(nil)
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if quitConfirmed {
            return finishQuit()
        }
        if QuitReason.isSystemShutdown() {
            quitConfirmed = true
            stopServerOnQuit = true
            return finishQuit()
        }
        guard !quitCheckRunning else { return .terminateCancel }
        checkBeforeQuit { [weak self] choice in self?.terminateQuitChecked(choice) }
        return .terminateLater
    }

    func terminateQuitChecked(_ choice: QuitChoice) {
        guard case .quit(let stopServer) = choice else {
            return NSApp.reply(toApplicationShouldTerminate: false)
        }
        quitConfirmed = true
        stopServerOnQuit = stopServer
        if finishQuit() == .terminateNow {
            NSApp.reply(toApplicationShouldTerminate: true)
        }
    }

    func finishQuit() -> NSApplication.TerminateReply {
        guard stopServerOnQuit else { return .terminateNow }
        stopServerOnQuit = false
        Factory.runInBackground(["server", "stop"], timeout: quitCommandSeconds) { _ in
            NSApp.reply(toApplicationShouldTerminate: true)
        }
        return .terminateLater
    }

    func checkBeforeQuit(then decide: @escaping (QuitChoice) -> Void) {
        quitCheckRunning = true
        guard let base else {
            DispatchQueue.main.async { [weak self] in
                self?.quitCheckRunning = false
                decide(.quit(stopServer: false))
            }
            return
        }
        ServerAddress.ping(base) { [weak self] up in
            guard up else {
                self?.quitCheckRunning = false
                return decide(.quit(stopServer: false))
            }
            Factory.runInBackground(["server", "waiting", "--json"], timeout: quitCommandSeconds) { result in
                let choice = QuitAlert.ask(waitingTasks: Factory.waitingTasks(in: result))
                self?.quitCheckRunning = false
                decide(choice)
            }
        }
    }
}

enum MainMenu {
    static func build(target: AppDelegate) -> NSMenu {
        let menu = NSMenu()
        menu.addItem(submenu(appName, items: [
            item("Hide \(appName)", #selector(NSApplication.hide(_:)), "h"),
            item("Hide Others", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]),
            item("Show All", #selector(NSApplication.unhideAllApplications(_:)), ""),
            .separator(),
            item("Quit \(appName)", #selector(NSApplication.terminate(_:)), "q"),
        ]))
        menu.addItem(submenu("Edit", items: [
            item("Undo", Selector(("undo:")), "z"),
            item("Redo", Selector(("redo:")), "z", [.command, .shift]),
            .separator(),
            item("Cut", #selector(NSText.cut(_:)), "x"),
            item("Copy", #selector(NSText.copy(_:)), "c"),
            item("Paste", #selector(NSText.paste(_:)), "v"),
            item("Select All", #selector(NSText.selectAll(_:)), "a"),
        ]))
        let reload = item("Reload", #selector(AppDelegate.reloadPage(_:)), "r")
        reload.target = target
        menu.addItem(submenu("View", items: [
            reload,
            .separator(),
            item("Show Tab Bar", #selector(NSWindow.toggleTabBar(_:)), ""),
            item("Show All Tabs", #selector(NSWindow.toggleTabOverview(_:)), "\\", [.command, .shift]),
        ]))
        let window = submenu("Window", items: [
            item("Close", #selector(NSWindow.performClose(_:)), "w"),
            item("Minimize", #selector(NSWindow.performMiniaturize(_:)), "m"),
            .separator(),
            item("Show Previous Tab", #selector(NSWindow.selectPreviousTab(_:)), "\t", [.control, .shift]),
            item("Show Next Tab", #selector(NSWindow.selectNextTab(_:)), "\t", [.control]),
            item("Merge All Windows", #selector(NSWindow.mergeAllWindows(_:)), ""),
        ])
        menu.addItem(window)
        NSApp.windowsMenu = window.submenu
        return menu
    }

    static func submenu(_ title: String, items: [NSMenuItem]) -> NSMenuItem {
        let holder = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        let submenu = NSMenu(title: title)
        items.forEach(submenu.addItem)
        holder.submenu = submenu
        return holder
    }

    static func item(_ title: String, _ action: Selector, _ key: String, _ modifiers: NSEvent.ModifierFlags = .command) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: key)
        item.keyEquivalentModifierMask = modifiers
        return item
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
