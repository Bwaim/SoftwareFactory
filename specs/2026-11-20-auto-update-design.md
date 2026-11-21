# Update from the dashboard

Source: user request in the session of 2026-11-20.

## Intent

Today the user updates the factory with one command: the install script, run again. Users do not run this command often, so they stay on old versions. The dashboard will tell the user that a new version exists, and update the factory with one click.

## Terms

- Installed version: the value of `VERSION` in `lib/factory/cli.py`. Today it is `0.2.0`.
- Latest version: the tag of the latest GitHub release, without the `v`. Example: tag `v0.3.0` gives `0.3.0`.
- Update banner: the new line at the top of the dashboard that shows the latest version.

## Facts about the current code

- `install.sh` downloads `releases/latest/download/software-factory.tar.gz` and its `.sha256`. It makes sure that the digest matches. It moves the old `~/.local/share/software-factory` to a backup and moves the new folder in. It restores the backup only when that last move fails, and then deletes the backup. Then it runs `factory app install` on macOS. That step builds the Dock app with `swiftc -O` and can take up to about one minute.
- `FACTORY_INSTALL_DOWNLOAD_BASE` replaces the base URL from which `install.sh` downloads the archive and its `.sha256`.
- At start, `install.sh` deletes all `<dir>.stage.*` and `<dir>.backup.*` folders. Two runs at the same time can delete the folders of each other.
- `install.sh` asks questions only when it can open `/dev/tty`, or the file in `FACTORY_INSTALL_TTY`. Without a terminal, it installs no tools and asks nothing (`interactive=0`).
- `install.sh` stops if `curl`, `tar`, `uv` or `claude` is not on `PATH`.
- `.github/workflows/release.yml` runs on a `v*` tag. It runs `scripts/build-release.sh` and attaches `software-factory.tar.gz` and its `.sha256` to the release. `install.sh` is not attached.
- One server serves all repositories. Each start uses a random port and a new token. `ensure_server()` starts `bin/factory serve` from `repo.PLUGIN_ROOT` and waits for a new `server.json`.
- A server stops by itself when `server.json` names another pid (`Server.replaced()`, checked every 30 seconds or less by `watch_idle`).
- A server stop closes the dashboard terminals (`REGISTRY.close_all()`). Agents in Warp or Herdr keep running.
- When the server loads a repository with older data, it migrates the data (`runtime.migrate_if_older`). If the migration fails, the repository shows the error. The server tries again at each reload.
- The Dock app gets the dashboard URL from the output of `factory dashboard`. It pings the server. When the ping fails, it shows "Server stopped" with a "Start" button. The page talks to the app with `tellApp(msg)` (`window.webkit.messageHandlers.captn`).
- Long server actions use `server.start_job(fn)` and `GET /api/jobs/<id>`.

## Goals

1. When the dashboard opens, the user sees the update banner if a newer release exists.
2. One click on "Update" installs the latest release, restarts the server on the new code, and reloads the dashboard. This works in a browser tab and in the Dock app.
3. Repositories with older data migrate by themselves after the restart. This exists today and needs no new code.
4. A failed download or a bad digest leaves the old install in place. Each failed update shows the error output.

## Non-goals

- No automatic update without a click.
- No "Migrate" button. The server already migrates older data at load.
- No update of the tools that `install.sh` can install (Homebrew, Herdr, and the others).
- No release notes in the banner.
- No downgrade, and no choice of a version other than the latest.

## Anti-goals

- The update must never leave the user without a working factory. A failed download or a bad digest keeps the old install. A new server that does not start gets a clear message and a way to start again (Update job, step 8).
- The version check must never block or slow the dashboard. A failed check shows nothing.
- The update must not change the terminal choice of the user or ask questions.

## Approaches

- O1, chosen: the server downloads `install.sh` from the latest release and runs it with no questions. There is one update path, and the download, the digest check and the restore already exist and have tests.
- O2: a new `factory update` command in Python that copies the logic of `install.sh`. It is easier to test, but two update paths can drift apart.
- O3: the banner only shows the command to copy. It is small, but the user still runs a command. This is the problem to fix.

The user chose O1.

## Design

### Version check

- The server gets `https://api.github.com/repos/Bwaim/SoftwareFactory/releases/latest` and reads `tag_name`.
- The server makes the check in a background thread when it starts, and again every 24 hours.
- The server keeps the result in memory: the latest version, and the time of the check.
- A version is newer when its numbers, compared one by one, are greater. A tag that is not `v<int>.<int>.<int>` counts as no update.
- If the request fails, the server writes one line to `server.log` and keeps no update.
- `FACTORY_UPDATE_URL` replaces the GitHub API URL. Tests use it.
- `FACTORY_NO_UPDATE_CHECK=1` turns the check off. Tests and CI use it.
- Builder check call: if `repo.PLUGIN_ROOT` has no `.installed-by-script` file, the server makes no check. Examples: a git checkout or a plugin copy. `install.sh` cannot update these installs, and the banner then stays after each update.

### API

- `GET /api/update` (global scope) returns `{"installed": "0.2.0", "latest": "0.3.0" or null, "dismissed": bool, "running_tasks": int}`.
- Builder check call: `running_tasks` counts the tasks of all repositories that have a live agent session. A task that waits for the user or for a done check also counts, because the update affects its next step.
- `POST /api/update/dismiss` (global scope) saves the latest version in `workspaces.home() / "update-dismissed"` (by default `~/.config/software-factory/update-dismissed`). A newer version shows the banner again.
- `POST /api/update/run` (global scope) starts a job with `server.start_job`. It returns the job id. Only one update job runs at a time. If an update job is already running, the call returns the id of that job and starts nothing.
- `POST /api/update/close` (global scope) tells the old server that the user closed the error of Update job, step 8. The old server then stops. In other states, it does nothing.

### Banner

```
New version 0.3.0 is available (you have 0.2.0).   [Update]  [Later]
```

- The dashboard calls `GET /api/update` when it loads, and again every hour.
- It shows the banner when `latest` is not null and `dismissed` is false.
- "Later" calls `/api/update/dismiss` and hides the banner.
- If `running_tasks` is more than 0, "Update" first asks in the page (not a browser dialog): "2 tasks are running. They continue, and their next steps use the new version. Update now?"
- During the update, the banner shows "Updating…" and the buttons are disabled.
- If the job fails, the banner shows "The update failed." and the output of `install.sh`, with a "Close" button. Builder check call: the text does not say that the old version is still installed. `install.sh` can fail after the folder swap, for example at the link step, and then the new code is in place.
- After a success, the new page shows the installed version for 10 seconds: "CAPTN is updated to 0.3.0."

### Update job

1. Stop the `poll_loop` of the old server. The old server runs no done checks from this point.
   - Then wait until the running `poll_all` and the running check calls end. A done check runs a shell command with a timeout (`engine.run_check`) and can take minutes. If it runs during the folder swap, old code saves its result while the new files are on disk. During the wait, the banner shows "Updating…".
   - While an update job runs, the old server refuses every POST call except `/api/update/run` and `/api/update/close`, with "An update is running." Examples of refused calls: `/api/tasks/<id>/check`, `/api/pipelines/check`, `/api/steps/check` and `/api/server-settings/save`. `GET /api/jobs/<id>` stays open.
   - The same stop flag makes `reschedule()` do nothing, so nothing wakes `poll_loop`.
2. Download `releases/download/v<latest>/install.sh` to a temporary folder.
   - `<latest>` is the latest version that the server checked. The server never takes this value from the page, because the value goes into a download URL.
   - If the server has no checked latest version, `/api/update/run` refuses with "No update is available."
3. Run it with `sh`, `stdin` from `/dev/null`, `FACTORY_INSTALL_TTY` set to a path that does not exist, and the server environment. Capture stdout and stderr.
   - Set `FACTORY_INSTALL_DOWNLOAD_BASE` to `https://github.com/Bwaim/SoftwareFactory/releases/download/v<latest>`. The script and the archive then come from the same release, and the installed version is the version of the banner.
   - Set `FACTORY_INSTALL_DIR` to `repo.PLUGIN_ROOT`, so that the script updates the copy that the server runs.
   - Builder check call: if `workspaces.home() / "terminal"` exists, set `FACTORY_INSTALL_TERMINAL` to its value. Without it, `finish_terminal` can switch a Herdr user to Warp when `herdr` is not on the server `PATH`. If the file does not exist, set nothing, the same as a manual run.
4. If the exit status is not 0, read `repo.PLUGIN_ROOT / "VERSION"`.
   - If it contains `<latest>`, the folder swap was done before the failure. Go on to step 5. The job result also holds the `install.sh` output, and the new page shows it.
   - Otherwise, the job fails with the output. The old code is still in place. The old server clears the stop flag and starts its `poll_loop` again.
5. Start the new server with `bin/factory serve` through its shebang, not `sys.executable`. A release can change the inline dependencies of `bin/factory`, and the old Python environment cannot import them. Otherwise, use the same code as `ensure_server()`, but do not reuse the running server.
6. The job result is the new dashboard URL, with the same workspace parameters as the current page.
7. The old server stops after the page reads the job result. Builder check call: while an update job exists, `watch_idle` ignores `replaced()` until `GET /api/jobs/<id>` returned the done result, or until 60 seconds after the job ends. Without this, the old server can stop before the page learns the new URL.
8. Builder check call: if the new server does not start, the job fails with "The update is installed, but the new server did not start. See <server.log path>." `install.sh` already deleted the backup, so no restore is possible.
   - The old server stops when the user clicks "Close" on the error (`POST /api/update/close`), or 60 seconds after the job ends at most. It does not stop when the page reads the error, because the Dock app then covers the error with its "Server stopped" screen. It must stop, because `ensure_server()` reuses a server that answers the ping. A running old server has old code and no `poll_loop`, and the Dock app shows "Start" only when the ping fails.
   - Until the user starts the factory again, no done checks run.
   - The user starts the factory again with `factory dashboard` or the "Start" button of the Dock app. This starts a server from the new code.

`FACTORY_UPDATE_INSTALL_URL` replaces the `install.sh` URL. Tests use it.

Accepted risk: the time between the folder swap and the stop of the old server is long. It includes the Dock app build (up to about one minute), the start of the new server, and up to 30 more seconds of `watch_idle`. In this time, old code runs with the new `catalog`, `builtin` and `web` files on disk. The old server can also import a new module, because some imports run inside functions. Step 1 stops the `poll_loop`, so the old server does not run done checks, and two servers never poll the same repositories. In this time the old server only answers API calls of open pages.

Accepted limit: other open dashboards lose their server. Examples: a second browser tab, or the Dock app when the click came from a browser. The Dock app shows "Server stopped", and its "Start" button finds the new server through `ensure_server`. A browser tab only shows "offline". The user opens the dashboard again with `factory dashboard`.

### Reload

- In a browser tab, the page goes to the new URL.
- In the Dock app, the page sends `tellApp("navigate:<url>")`. The app accepts the message only when `ServerAddress.isFactoryPage(url)` is true. Without this check, a page can make the app load any URL. The app sets `base` to the new URL and loads it. Without this message, the app pings the old URL, sees no server, and shows "Server stopped".
- Builder check call: the app also moves each open editor window to the new server with `ServerAddress.rebase`. Without this, editor windows show "Server stopped".
- `install.sh` rebuilds the Dock app. The running app keeps the old binary until the user quits it. This is acceptable.

### Release

- `release.yml` also attaches `install.sh` to each release, so that the update script and the code have the same version.
- The README `install.sh` command does not change.

### README

- The install section says that the dashboard shows new versions and updates with one click, from the version that contains this feature.
- It says that users of 0.2.0 or older run the install command one more time to get this feature. Their dashboard shows no banner.
- It names `FACTORY_NO_UPDATE_CHECK`.

## Left to the builder

- The file layout of the new Python code (for example a new `update.py`).
- The style of the banner, in line with the current dashboard.
- The exact text of log lines.
- The test structure, with a fake release server and a fake `install.sh`.
