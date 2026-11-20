# Dock app for the dashboard

Source: user request in the session of 2026-11-20.

## Intent

Today the user opens the dashboard with `factory dashboard` or with the menu action "Open dashboard". The command runs `open <url>`, so each call opens a new browser tab. The user wants a macOS app in the Dock, like Chrome. A click on the icon starts the factory and shows the dashboard. A second click brings the open dashboard to the front.

## Terms

- Dock app: the new macOS app "CAPTN Dashboard". It shows the dashboard in its own window.
- Notifier app: the existing app that sends notifications. Its new name is "CAPTN Dashboard Notifier".
- Done check: the background poll of the server that moves a waiting task forward.
- Waiting task: a task that waits on a done check. `server.waiting_checks()` lists these tasks.

## Facts about the current code

- Each server start uses a random port and a new token (`server.py`). The dashboard URL holds both.
- The server stops by itself after `IDLE_SECONDS` (1800 seconds) with no API call, but only when no task waits on a done check (`watch_idle`, `not self.waiting()`). The dashboard polls every 5 seconds, so the server stays up while a dashboard is open. A call to `/api/ping` with the token also resets the idle time.
- A server stop ends the done checks and closes the terminals of the dashboard (`REGISTRY.close_all()`). Agents in Warp or herdr keep running.
- `factory dashboard` calls `ensure_server()`, then `open_page(url)`, then prints `Dashboard: <url>`. `FACTORY_NO_OPEN` makes `open_page` do nothing. `open_page` also serves `factory pipeline edit` and `factory step edit`.
- `factory server stop --unless-waiting` exists. It prints a sentence and has no JSON output.
- The menu action "Open dashboard" runs `factory dashboard`.
- The notifier app is built with `swiftc` into `~/Applications/CAPTN Factory.app`. A stamp in `Info.plist` (a hash of the sources) triggers a rebuild when a source changes (`notifier/__init__.py`).
- The "Create a pipeline" button in the launch popup calls `window.open("/editor?...", "_blank")`.

## Goals

1. The user pins "CAPTN Dashboard" in the Dock. A click starts the server when needed and shows the dashboard in the app window.
2. When the app runs, a click on the Dock icon brings its window to the front. It never opens a second dashboard.
3. When the server cannot be reached, the app shows "Server stopped" and a "Start" button. "Start" starts a server and loads the dashboard from it.
4. When the app quits, it stops the server, after a warning (see "Quit").
5. "Create a pipeline" opens the editor as a native tab of the app window.
6. The Dock app and the notifier app use a new icon: the Captain Bot on a purple rounded square.
7. The notifier app has the new name "CAPTN Dashboard Notifier".
8. When the Dock app is installed, `factory dashboard` and the menu action "Open dashboard" show the dashboard in the Dock app, not in a browser tab.

## Non-goals

- CLI pages other than the dashboard in the app. `factory pipeline edit` and `factory step edit` keep opening in the browser.
- An automatic server restart by the app. The app starts a server only at launch and on "Start".
- A fixed port or a fixed token for the server.
- Support outside macOS. On other platforms, nothing changes.
- One app for both the dashboard and the notifications.
- A signed or notarized app. The app is signed ad hoc, as the notifier app is.

## Anti-goals

- A click on the Dock icon opens a browser tab.
- A server stop without a warning when tasks wait on a done check.
- A click on "Create a pipeline" that does nothing in the app.
- A change in the notification behavior, other than the app name and the icon.

## Approaches

1. Small app that runs `factory dashboard` and quits. It handles a restart, because each click starts a server when needed. It does not focus the open tab, and old tabs stay dead.
2. Approach 1, plus AppleScript that finds the dashboard tab in Chrome or Safari and brings it to the front. It needs a script per browser and the "Automation" permission. After a restart, the old tab has the old port, so the search fails.
3. Native app with its own window and a WKWebView (the macOS web view). macOS brings a running app to the front on a Dock click. The app reloads the dashboard from the new server after a restart. Chosen by the user, because it is the only approach that solves the focus and the restart without browser scripts.

## Design

### The app

- Name "CAPTN Dashboard". Bundle id `com.captn.factory.dashboard`. Path `~/Applications/CAPTN Dashboard.app`.
- One Swift source file, compiled with `swiftc`, signed ad hoc with `codesign`. The build uses the method of the notifier app: a stamp in `Info.plist`, a build in a temporary folder, a move into place, and `lsregister`.
- `bin/factory` runs through `uv` (`#!/usr/bin/env -S uv run --script`). The build writes the absolute path of `uv` and of `bin/factory` into `Info.plist`. The app runs `<uv> run --script <bin/factory> <args>`. The app does not use `PATH`, because a Dock app gets a minimal `PATH`. The app does not use `sys.executable`, because `uv cache clean` can delete that interpreter. These paths are part of the stamp, so a new install path triggers a rebuild.
- The window holds a WKWebView. The window title is the page title.
- Closing the last window quits the app. The quit warning (see "Quit") shows in `windowShouldClose` of the last window, before the window closes. "Cancel" keeps the window open.
- If the app runs without a window for another reason, a click on the Dock icon opens the dashboard window again (`applicationShouldHandleReopen`).
- While the app runs, it calls `/api/ping` with the token every 60 seconds, from Swift. This keeps the server up when macOS slows the JS timers of a hidden window (App Nap). It also finds a stopped server when the page does not poll.

### Getting the URL

- The app runs `factory dashboard` with `FACTORY_DOCK_APP=1`, and reads the URL from the output. This call starts a server when none runs. `FACTORY_DOCK_APP` stops the command from opening a page and from rebuilding the app.
- The app does this at launch and on a click on "Start". Cmd+R only reloads the current page.
- When macOS launches the app with a URL (see "Dashboard from the CLI and the menu"), the app loads that URL and does not run `factory dashboard`.
- The app runs the command in a background thread, so the window does not freeze. While it runs, the window shows "Starting the factory…".
- If the command fails, the window shows its error output and a "Try again" button.
- `factory dashboard` registers the current folder as a workspace when it is a factory. The app runs the command in the home folder, so it registers nothing.

### Server stopped

- When the dashboard cannot reach the server, the app window shows "Server stopped" and a "Start" button. This is the same for a manual stop, a crash and an update.
- "Cannot reach" means a failed navigation, failed API calls from the page, or a failed `/api/ping` from Swift. The page tells the app through a WKWebView message handler. The dashboard already shows an "offline" mark in this case.
- Before the app shows "Server stopped", it confirms with its own `/api/ping`. One slow or failed poll of the page does not show the screen.
- The app never starts a server without a click on "Start".
- While the app is open, the Swift ping and the dashboard poll keep the server up, so it does not stop after `IDLE_SECONDS`. The user stops it by quitting the app or with `factory server stop`.
- An editor tab that cannot reach the server shows "Server stopped. Reload the editor after Start. Unsaved changes are lost." The app does not reload it by itself.
- When the user reloads an editor tab (Cmd+R), the app replaces the port and the `token` parameter of its URL with those of the last dashboard URL it loaded, then loads it. That URL comes from "Start", from the launch, or from an open URL event. Cmd+R never runs `factory dashboard`, because that command can start a server.

### Dashboard from the CLI and the menu

- This change is in `dashboard_cmd` only. `open_page` does not change, so `factory pipeline edit` and `factory step edit` keep opening in the browser (D2).
- On macOS, when the Dock app is installed and neither `FACTORY_DOCK_APP` nor `FACTORY_NO_OPEN` is set, `factory dashboard` and the menu action "Open dashboard" do not open a browser tab. They start the server when needed, then open the dashboard URL in the Dock app (`open -b com.captn.factory.dashboard <url>`).
- The app receives the URL (open URL event). If the app runs, it loads this URL in its dashboard window and comes to the front. If it does not run, macOS launches it with this URL. The URL keeps the `ws` parameter, so the dashboard shows the workspace of the current repository.
- When the Dock app is not installed, or outside macOS, the behavior does not change.
- The command still prints `Dashboard: <url>`.

### Quit

When the app quits, it stops the server with `factory server stop`. It shows a warning before this.

- No waiting task: an `NSAlert` with the text "Quitting CAPTN Dashboard stops the factory server." and the buttons "Quit" and "Cancel". The alert has a checkbox "Don't show again". When the user checks it and quits, the app saves this choice in its preferences. The alert then does not show again for this case.
- One or more waiting tasks: the alert always shows, also when "Don't show again" is saved. It lists the waiting tasks, and says that their done checks stop. The buttons are "Stop", "Keep server running" and "Cancel". "Keep server running" quits the app and leaves the server up.
- The app gets the waiting tasks from a new command `factory server waiting --json`. It prints the ids of the waiting tasks as a JSON list, from `server.waiting_checks()`.
- During a macOS logout or shutdown, the app does not show the alert. It stops the server.
- The warning has two entry points: `windowShouldClose` of the last window, and Cmd+Q (`applicationShouldTerminate`). It shows once per quit. When the user confirms in `windowShouldClose`, the app sets a flag, and `applicationShouldTerminate` skips the alert.

### Editor in a tab

- The app handles `window.open` (the `WKUIDelegate` method `createWebViewWith`). It opens a new app window with the requested URL.
- App windows use `tabbingMode = .preferred`, so a new window opens as a tab of the current window.
- Links to other hosts (for example ticket links) open in the default browser.

### Icon

- A new `AppIcon.icns`, made from the Captain Bot SVG of the dashboard.
- The background is a rounded square in the brand purple `#673888`, in the macOS icon grid.
- The bot face is purple too, so the face gets a white rim to stay visible.
- The repo keeps the SVG source of the icon and the script that makes the `.icns`. The build of the apps uses the `.icns` file from the repo and does not run the script.
- The Dock app and the notifier app use this icon.

### Notifier rename

- The new app name is "CAPTN Dashboard Notifier", in `APP_NAME`, `CFBundleName` and `CFBundleDisplayName`.
- The bundle id stays `com.captn.factory.notifications`. macOS links the notification permission to the bundle id, so the user probably does not allow notifications again.
- The notification title (`TITLE`) stays "CAPTN Factory".
- When the build makes the new app, it deletes `~/Applications/CAPTN Factory.app` if it exists.

### Install and update

- `install.sh` builds the Dock app on macOS when `swiftc` and `codesign` exist. It prints the app path and tells the user to drag the app to the Dock.
- `factory dashboard` rebuilds the Dock app when its stamp changes, as `notifier.ensure_app()` does. A failed build does not fail the command.
- When `FACTORY_DOCK_APP` is set, `factory dashboard` does not rebuild the Dock app, because the app is the caller. A new build applies at the next launch of the app.
- When `FACTORY_NO_OPEN` is set, `factory dashboard` does not rebuild the Dock app either, so tests never start a `swiftc` build.
- `FACTORY_DASHBOARD_APP` overrides the app path, as `FACTORY_NOTIFIER_APP` does for the notifier. Build tests use it.
- A new command `factory app install` builds the Dock app and prints its path. `install.sh` calls this command.
- The README describes the Dock app, the quit warning and the new notifier name.

## Decisions by the user

- D1. Alert with "Stop", "Keep server running" and "Cancel" when tasks wait on a done check.
- D2. CLI pages stay in the browser.
- O1. The editor opens as a native tab of the app window.
- O3. Native app with WKWebView.
- The names "CAPTN Dashboard" and "CAPTN Dashboard Notifier".
- The icon gets a rounded-square background.
- Q1. `factory dashboard` and "Open dashboard" use the Dock app when it is installed.
- Q4. When the server cannot be reached, the app shows "Server stopped" and a "Start" button, for every cause.

## Calls by the designer

- Closing the last window quits the app, and the quit stops the server.
- The background color is `#673888` with a white rim on the face.
- The app runs `factory` through absolute paths of `uv` and `bin/factory` in `Info.plist` (Q2).
- An editor tab shows a reload message after a server stop and does not reload by itself (Q3).
- The app does not rebuild itself. The rebuild happens in `install.sh`, `factory app install` and `factory dashboard` from a terminal (Q5).
- The new commands `factory app install` and `factory server waiting --json`.
- A Swift ping every 60 seconds, and a confirm ping before "Server stopped".
- `FACTORY_NO_OPEN` stays for tests, so a test run on a Mac with the app installed does not open or rebuild the app.
- The quit warning shows before the last window closes.
- The environment variable `FACTORY_DOCK_APP`.

## Left to the builder

- The exact layout of the Swift code.
- How the page tells the app that the server cannot be reached.
- Tests: the Python parts (build, stamp, `Info.plist`, rename, old app removal, waiting-task output) get unit tests. The Swift app gets a manual test list. The list includes a hidden window for more than 30 minutes: the server must stay up. It also includes: close the last window, click "Quit", and make sure that only one alert shows.
