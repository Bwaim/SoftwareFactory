# Update From the Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The dashboard shows a banner when a newer GitHub release exists, and one click installs it, restarts the server on the new code and reloads the page.

**Architecture:** A new module `lib/factory/update.py` holds the version check, the dismissed version, and an `Updater` that runs the release `install.sh` and starts the new server. `server.py` gets a stop flag that pauses polling, waits for running checks and refuses POST calls during an update. `api.py` gets four global routes. `dashboard.html` shows the banner and moves to the new URL. The Dock app accepts a `navigate:<url>` message. `release.yml` attaches `install.sh` to each release.

**Tech Stack:** Python 3 (stdlib + pyyaml), pytest, plain HTML/JS, Swift (AppKit, WebKit), POSIX sh, GitHub Actions.

**Spec:** `specs/2026-11-20-auto-update-design.md`. Read it first. Each task names the spec sections it implements.

## Global Constraints

- Work on branch `auto_update`. Code changes stay in `software-factory/`, `.github/workflows/release.yml` and this plan.
- No code comments. No docstrings in new code. Short functions, like the surrounding code. Swift: no `//` comments.
- Commit messages: short, plain. Never add a `Co-Authored-By` line.
- Run tests from `software-factory/` with `uv run --with pytest --with pyyaml pytest -q <paths>`.
- Tasks 1 to 6: run only the test files or test functions that the task adds or changes. Do not run the full suite. Task 7 runs the full suite once.
- Names (copy them as written):
  - Module `factory.update`. Dismissed file: `workspaces.home() / "update-dismissed"`.
  - GitHub API URL: `https://api.github.com/repos/Bwaim/SoftwareFactory/releases/latest`.
  - Release download base: `https://github.com/Bwaim/SoftwareFactory/releases/download`. Install script URL: `<base>/v<latest>/install.sh`.
  - Script install marker: `<root>/.installed-by-script`. Version file: `<root>/VERSION`.
  - Environment variables: `FACTORY_UPDATE_URL`, `FACTORY_NO_UPDATE_CHECK`, `FACTORY_UPDATE_INSTALL_URL`, `FACTORY_UPDATE_ROOT` (tests only: replaces `repo.PLUGIN_ROOT` as the install root), and for `install.sh`: `FACTORY_INSTALL_TTY`, `FACTORY_INSTALL_DOWNLOAD_BASE`, `FACTORY_INSTALL_DIR`, `FACTORY_INSTALL_TERMINAL`.
  - Routes (global scope): `GET /api/update`, `POST /api/update/dismiss`, `POST /api/update/run`, `POST /api/update/close`.
  - Dock app message: `navigate:<url>`.
  - Check interval: 24 hours. Page check interval: 1 hour. Hold time: 60 seconds after the job ends. Success notice: 10 seconds.
- Exact texts:
  - Banner: `New version {latest} is available (you have {installed}).` Buttons `Update`, `Later`.
  - Confirm (in page, not a browser dialog): `{n} tasks are running. They continue, and their next steps use the new version. Update now?` For n = 1: `1 task is running. It continues, and its next steps use the new version. Update now?` Buttons `Update`, `Cancel`.
  - During the job: `Updating…`, buttons disabled.
  - Job failure: `The update failed.` plus the `install.sh` output in a `<pre>`, button `Close`.
  - New server failure: `The update is installed, but the new server did not start. See {server.log path}.`
  - Success notice on the new page: `CAPTN is updated to {version}.`
  - Refusal during an update: `An update is running.` (HTTP 409).
  - No checked version: `No update is available.`

## Review Focus

1. The GitHub API answers with a tag that is not `v<int>.<int>.<int>` (for example `v0.3.0-rc1`), or with no `tag_name`, or with HTML. Expected: no banner, one log line, no exception. Pinned by `test_bad_tags_give_no_update` and `test_fetch_bad_body_gives_none` in Task 1.
2. The test suite and CI must never call GitHub. Expected: the autouse fixture sets `FACTORY_NO_UPDATE_CHECK=1`, so every test server skips the check. Pinned by `test_no_update_check_env_skips_the_check` in Task 1.
3. The user double-clicks "Update", or clicks in two tabs. Expected: one job, both calls get the same job id. Pinned by `test_second_run_returns_the_same_job` in Task 3.
4. `install.sh` exits non-zero after the folder swap (for example the link step). Expected: the job goes on, starts the new server and keeps the output. Pinned by `test_failure_after_swap_goes_on` in Task 3.
5. A "Check now" click while an update runs. Expected: HTTP 409 `An update is running.`, and no check runs. Pinned by `test_post_refused_while_updating` in Task 2.

---

### Task 1: Version check (spec "Version check", "API" dismiss part)

**Files:**
- Create: `software-factory/lib/factory/update.py`
- Modify: `software-factory/tests/conftest.py` (autouse `factory_home` fixture)
- Test: `software-factory/tests/test_update.py` (new)

**Interfaces:**
- Produces, in `factory.update`:
  - `API_URL`, `RELEASES`, `CHECK_SECONDS = 24 * 3600`, `HOLD_SECONDS = 60`.
  - `root() -> Path`: `FACTORY_UPDATE_ROOT` or `repo.PLUGIN_ROOT`.
  - `script_install() -> bool`: `root() / ".installed-by-script"` exists.
  - `parse(text) -> tuple[int, int, int] | None`: accepts `v1.2.3` and `1.2.3` only.
  - `newer(latest: str, installed: str) -> bool`: false when either does not parse.
  - `fetch_latest(url=None, timeout=10) -> str | None`: GET the API URL (`FACTORY_UPDATE_URL` overrides), read `tag_name`, return the version without `v`, or `None` on any error or bad tag. On error, write one line with `server.log`-style `print(..., file=sys.stderr)`.
  - `dismissed() -> str | None`, `dismiss(version: str) -> None`.
  - `class Checker`: `latest: str | None`, `checked_at: float | None`, `check_once() -> None` (sets `latest` only when `newer(found, cli.VERSION)`), `start() -> None` (daemon thread: `check_once()`, then every `CHECK_SECONDS`). `start()` does nothing when `FACTORY_NO_UPDATE_CHECK` is set or `script_install()` is false.

- [ ] **Step 1: Write the failing tests**

```python
def test_newer_compares_numbers():
    assert update.newer("0.10.0", "0.9.0")
    assert update.newer("v0.3.0", "0.2.0")
    assert not update.newer("0.2.0", "0.2.0")
    assert not update.newer("0.1.9", "0.2.0")

@pytest.mark.parametrize("tag", ["v0.3.0-rc1", "latest", "", None, "v1.2"])
def test_bad_tags_give_no_update(tag):
    assert not update.newer(tag, "0.2.0")

def test_fetch_reads_tag_name(fake_api):          # fake_api: local http.server that returns a set body
    fake_api.body = {"tag_name": "v0.3.0"}
    assert update.fetch_latest(fake_api.url) == "0.3.0"

def test_fetch_bad_body_gives_none(fake_api, capsys):
    fake_api.raw = b"<html>rate limited</html>"
    assert update.fetch_latest(fake_api.url) is None
    assert capsys.readouterr().err.count("\n") == 1

def test_fetch_offline_gives_none():
    assert update.fetch_latest("http://127.0.0.1:9/") is None

def test_dismiss_round_trip(factory_home):
    assert update.dismissed() is None
    update.dismiss("0.3.0")
    assert update.dismissed() == "0.3.0"
    assert (factory_home / "update-dismissed").read_text().strip() == "0.3.0"

def test_checker_keeps_only_newer(fake_api, monkeypatch):   # monkeypatch cli.VERSION = "0.2.0", FACTORY_UPDATE_URL = fake_api.url
    fake_api.body = {"tag_name": "v0.2.0"}
    c = update.Checker(); c.check_once()
    assert c.latest is None and c.checked_at is not None
    fake_api.body = {"tag_name": "v0.3.0"}
    c.check_once()
    assert c.latest == "0.3.0"

def test_no_update_check_env_skips_the_check(monkeypatch, tmp_path):
    assert os.environ["FACTORY_NO_UPDATE_CHECK"] == "1"
    monkeypatch.setenv("FACTORY_UPDATE_ROOT", str(tmp_path)); (tmp_path / ".installed-by-script").touch()
    c = update.Checker(); c.start()
    assert c.checked_at is None

def test_no_check_without_script_install(monkeypatch, tmp_path):
    monkeypatch.delenv("FACTORY_NO_UPDATE_CHECK")
    monkeypatch.setenv("FACTORY_UPDATE_ROOT", str(tmp_path))
    c = update.Checker(); c.start()
    assert c.checked_at is None
```

- [ ] **Step 2: Run the tests and make sure they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_update.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'factory.update'`.

- [ ] **Step 3: Implement `update.py` with the interfaces above, and add `monkeypatch.setenv("FACTORY_NO_UPDATE_CHECK", "1")` to the autouse `factory_home` fixture in `conftest.py`**

`fetch_latest` uses `urllib.request` with an `Accept: application/vnd.github+json` header and a generic `User-Agent: captn-factory`. `dismiss` uses `fsio` to write the file.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_update.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/factory/update.py tests/test_update.py tests/conftest.py
git commit -m "Update: version check"
```

---

### Task 2: Server stop flag and new server start (spec "Update job" steps 1 and 5)

**Files:**
- Modify: `software-factory/lib/factory/server.py` (`Server`, `make_handler`, `ensure_server`)
- Modify: `software-factory/lib/factory/api.py` (wrap the three check routes)
- Test: `software-factory/tests/test_update_server.py` (new)

**Interfaces:**
- Produces, on `Server`:
  - `updating: bool` (default `False`).
  - `activity()`: a context manager that counts running work. `poll_all` and the routes `/api/tasks/<id>/check`, `/api/pipelines/check`, `/api/steps/check` run inside it. It checks `updating` under the same `Condition` lock as the count. If `updating` is true, it raises `UpdateRunning` and counts nothing.
  - `class UpdateRunning(FactoryError)` with the message `An update is running.` In `handle_request`, put `except UpdateRunning` before `except FactoryError`, and answer HTTP 409 `{"error": str(e)}`. Without this order, `FactoryError` catches it first and answers 400. `poll_loop` catches it and skips the poll.
  - `pause_for_update(timeout=None) -> None`: sets `updating = True`, then waits until the activity count is 0.
  - `resume_after_update() -> None`: sets `updating = False` and calls `self.wake.set()`.
  - `reschedule()` does nothing while `updating`. `poll_loop` skips `poll_all` while `updating`.
- Produces, in `server.py`:
  - `UPDATE_ALLOWED = ("/api/update/run", "/api/update/close")`.
  - The handler answers HTTP 409 `{"error": "An update is running."}` to every POST whose path is not in `UPDATE_ALLOWED`, while `server.updating`. GET calls stay open.
  - `spawn_server(argv: list[str]) -> dict`: the start-and-wait part of `ensure_server()` (log file, env without `FACTORY_DOCK_APP`, wait for a new pid in `server.json` that answers the ping, `START_TIMEOUT`). `ensure_server()` calls it with `[sys.executable, <PLUGIN_ROOT>/bin/factory, "serve"]`. Raises `FactoryError` on timeout, as today.

- [ ] **Step 1: Write the failing tests**

Start a `Server()` in the test process (`threading.Thread(target=srv.httpd.serve_forever, daemon=True)`), and use `serverutil.request` with `{"port": srv.port, "token": srv.token}`.

```python
def test_post_refused_while_updating(live):
    live.server.updating = True
    status, body = request(live.info, "POST", "/api/server-settings/save", {})
    assert (status, body["error"]) == (409, "An update is running.")
    assert request(live.info, "GET", "/api/ping")[0] == 200

def test_update_routes_allowed_while_updating(live):
    live.server.updating = True
    for path in ("/api/update/run", "/api/update/close"):
        assert request(live.info, "POST", path, {})[0] != 409

def test_pause_waits_for_running_activity(live):
    srv = live.server
    entered, release = threading.Event(), threading.Event()
    def busy():
        with srv.activity():
            entered.set(); release.wait(5)
    threading.Thread(target=busy).start(); entered.wait(5)
    t = threading.Thread(target=srv.pause_for_update); t.start()
    time.sleep(0.3); assert t.is_alive() and srv.updating
    release.set(); t.join(5); assert not t.is_alive()

def test_activity_refused_while_updating(live):
    live.server.updating = True
    with pytest.raises(server.UpdateRunning, match="An update is running."):
        with live.server.activity():
            pass

def test_route_in_activity_answers_409(live, monkeypatch):
    def busy_route(srv, query, body):
        with srv.activity():
            return {"ok": True}
    monkeypatch.setitem(api.ROUTES, "global", [("POST", re.compile("^/api/update/run$"), busy_route)])
    live.server.updating = True
    status, body = request(live.info, "POST", "/api/update/run", {})
    assert (status, body["error"]) == (409, "An update is running.")

def test_reschedule_does_nothing_while_updating(live):
    live.server.updating = True
    live.server.reschedule()
    assert not live.server.wake.is_set()

def test_resume_wakes_the_poll(live):
    live.server.updating = True
    live.server.resume_after_update()
    assert not live.server.updating and live.server.wake.is_set()

def test_spawn_server_starts_a_new_server(factory_home):
    info = server.spawn_server([sys.executable, str(BIN), "serve"])
    try:
        assert ping(info) and info["pid"] != os.getpid()
    finally:
        server.stop_server()
```

- [ ] **Step 2: Run the tests and make sure they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_update_server.py`
Expected: FAIL, `AttributeError` on `updating`, `activity` or `spawn_server`.

- [ ] **Step 3: Implement the interfaces above**

Use a `threading.Condition` for the activity count. Check the refusal in `handle_request` after the token check and before `api.dispatch`.

- [ ] **Step 4: Run the new tests and the existing server tests that touch `ensure_server`**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_update_server.py tests/test_global_server.py tests/test_server.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/factory/server.py lib/factory/api.py tests/test_update_server.py
git commit -m "Server: pause for an update"
```

---

### Task 3: Update job (spec "Update job")

**Files:**
- Modify: `software-factory/lib/factory/update.py`
- Test: `software-factory/tests/test_update_job.py` (new)

**Interfaces:**
- Consumes: Task 1 (`root`, `RELEASES`, `HOLD_SECONDS`), Task 2 (`Server.pause_for_update`, `resume_after_update`, `stop`, `jobs`, `spawn_server`).
- Produces, in `factory.update`:
  - `install_url(version: str) -> str`: `FACTORY_UPDATE_INSTALL_URL` or `f"{RELEASES}/v{version}/install.sh"`.
  - `install_env(version: str) -> dict`: `os.environ` plus `FACTORY_INSTALL_TTY` (a path that does not exist, in a new temp folder), `FACTORY_INSTALL_DOWNLOAD_BASE = f"{RELEASES}/v{version}"`, `FACTORY_INSTALL_DIR = str(root())`, and `FACTORY_INSTALL_TERMINAL` = the stripped text of `workspaces.home() / "terminal"` when that file exists.
  - `run_install(version: str) -> tuple[int, str]`: download the script to a temp folder, run `sh <script>` with `stdin=DEVNULL`, `install_env(version)`, stdout and stderr merged. Returns `(status, output)`. A download error returns `(1, <message>)`.
  - `installed_version() -> str | None`: stripped text of `root() / "VERSION"`.
  - `class Updater(server, checker, start=spawn_new)`:
    - `run(ws: str | None) -> str`: returns the job id. Refuses with `FactoryError("No update is available.")` when `checker.latest` is `None`. Returns the running job id when one runs.
    - `holds() -> bool`: true while the job runs, and in the hold states below.
    - `job_read(job_id) -> None`: called by the jobs route when it returns a finished result. It only ends the hold. It never calls `server.stop()`, because the reply is not written yet. `watch_idle` then stops the old server at its next tick, because `replaced()` is true and `holds()` is false.
    - `close() -> None`: called by `/api/update/close`. It also only ends the hold.
    - The hold timer also only ends the hold.
  - `spawn_new() -> dict`: `server.spawn_server([str(root() / "bin" / "factory"), "serve"])`.
- Job steps, in a thread, writing `server.jobs[job_id]`:
  1. `server.pause_for_update()`.
  2. `status, output = run_install(latest)`.
  3. If `status != 0` and `installed_version() != latest`: job `{"status": "error", "error": "The update failed.", "output": output}`, then `server.resume_after_update()`. No hold.
  4. Else, if `status != 0`, write `output` to `workspaces.home() / "update.log"` and set `warn = True`. Then `info = start()`. On `FactoryError`: job `{"status": "error", "error": "The update is installed, but the new server did not start. See {server.log_path()}.", "output": output}`. Hold state `"failed"`: the hold ends on `close()` or `HOLD_SECONDS` after the job ends. `job_read` does not end this hold.
  5. On success: job `{"status": "done", "result": {"url": <url>, "version": latest, "output": output}}`. `<url>` is `server.page_url(info, "dashboard", **params)` with `params` = `ws` (when given), `updated=latest`, and `warn="1"` when `warn`. Hold state `"done"`: the hold ends on `job_read(job_id)` or `HOLD_SECONDS` after the job ends.
  - "The hold ends" means `holds()` becomes false. The old server stops later in `watch_idle`.

- [ ] **Step 1: Write the failing tests**

Use a fake server object (`jobs = {}`, `pause_for_update`, `resume_after_update`, `stop` that records calls), a fake checker with `latest = "0.3.0"`, a fake `start`, and a local HTTP server that serves a fake `install.sh` through `FACTORY_UPDATE_INSTALL_URL`. Patch `update.HOLD_SECONDS` to a small value where needed.

```python
def test_install_env(monkeypatch, tmp_path, factory_home):
    monkeypatch.setenv("FACTORY_UPDATE_ROOT", str(tmp_path / "sf"))
    factory_home.mkdir(parents=True, exist_ok=True); (factory_home / "terminal").write_text("herdr\n")
    env = update.install_env("0.3.0")
    assert env["FACTORY_INSTALL_DOWNLOAD_BASE"] == "https://github.com/Bwaim/SoftwareFactory/releases/download/v0.3.0"
    assert env["FACTORY_INSTALL_DIR"] == str(tmp_path / "sf")
    assert env["FACTORY_INSTALL_TERMINAL"] == "herdr"
    assert not Path(env["FACTORY_INSTALL_TTY"]).exists()

def test_install_env_without_saved_terminal(factory_home, monkeypatch):
    monkeypatch.delenv("FACTORY_INSTALL_TERMINAL", raising=False)
    assert "FACTORY_INSTALL_TERMINAL" not in update.install_env("0.3.0")

def test_install_url_uses_the_checked_version():
    assert update.install_url("0.3.0") == "https://github.com/Bwaim/SoftwareFactory/releases/download/v0.3.0/install.sh"

def test_run_refused_without_checked_version(fakes):
    fakes.checker.latest = None
    with pytest.raises(FactoryError, match="No update is available."):
        fakes.updater.run(None)

def test_second_run_returns_the_same_job(fakes):          # install script blocks on a flag file
    first = fakes.updater.run(None)
    assert fakes.updater.run(None) == first

def test_success_returns_new_url_and_holds_until_read(fakes):   # install script writes VERSION 0.3.0, exit 0
    job = fakes.finish(fakes.updater.run("repo"))
    url = job["result"]["url"]
    assert "ws=repo" in url and "updated=0.3.0" in url and job["result"]["version"] == "0.3.0"
    assert "warn=" not in url
    assert fakes.updater.holds()
    fakes.updater.job_read(fakes.job_id)
    assert not fakes.updater.holds() and not fakes.server.stopped

def test_success_hold_ends_without_read(fakes):          # HOLD_SECONDS patched to 0.2
    fakes.finish(fakes.updater.run(None))
    time.sleep(0.5)
    assert not fakes.updater.holds() and not fakes.server.stopped

def test_failure_before_swap_resumes(fakes):              # install script prints "boom", exit 1, VERSION unchanged
    job = fakes.finish(fakes.updater.run(None))
    assert job["status"] == "error" and job["error"] == "The update failed." and "boom" in job["output"]
    assert fakes.server.resumed and not fakes.updater.holds() and not fakes.server.stopped

def test_failure_after_swap_goes_on(fakes, factory_home): # install script writes VERSION 0.3.0, prints "link failed", exit 1
    job = fakes.finish(fakes.updater.run(None))
    assert job["status"] == "done" and "link failed" in job["result"]["output"]
    assert "warn=1" in job["result"]["url"]
    assert "link failed" in (factory_home / "update.log").read_text()

def test_new_server_failure_holds_until_close(fakes):     # start raises FactoryError
    job = fakes.finish(fakes.updater.run(None))
    assert job["error"].startswith("The update is installed, but the new server did not start. See ")
    fakes.updater.job_read(fakes.job_id)
    assert fakes.updater.holds()
    fakes.updater.close()
    assert not fakes.updater.holds() and not fakes.server.stopped

def test_pause_runs_before_install(fakes):
    fakes.finish(fakes.updater.run(None))
    assert fakes.server.calls[:2] == ["pause", "install"]
```

- [ ] **Step 2: Run the tests and make sure they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_update_job.py`
Expected: FAIL, `AttributeError: module 'factory.update' has no attribute 'install_env'`.

- [ ] **Step 3: Implement the interfaces and job steps above in `update.py`**

Keep the hold timer in a `threading.Timer` started when the job ends.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_update_job.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/factory/update.py tests/test_update_job.py
git commit -m "Update: job that runs the release install script"
```

---

### Task 4: API routes and server wiring (spec "API", "Update job" step 7)

**Files:**
- Modify: `software-factory/lib/factory/api.py`, `software-factory/lib/factory/server.py`
- Modify: `software-factory/tests/serverutil.py` (`GLOBAL` gets `"/api/update"`)
- Test: `software-factory/tests/test_update_api.py` (new)

**Interfaces:**
- Consumes: Task 1 `Checker`, `dismissed`, `dismiss`. Task 3 `Updater`.
- Produces:
  - `Server.checker = update.Checker()` and `Server.updater = update.Updater(self, self.checker)`. `Server.run()` calls `self.checker.start()`.
  - `watch_idle`: `done = (self.replaced() and not self.updater.holds()) or (...)`.
  - `GET /api/update` returns `{"installed": cli.VERSION, "latest": checker.latest, "dismissed": checker.latest is not None and update.dismissed() == checker.latest, "running_tasks": n, "log": str(workspaces.home() / "update.log")}`. `n` is the number of tasks with status `active`, `awaiting_approval` or `waiting_external`, over the workspaces without error (`state.list_tasks(ws.ctx)`). Put the statuses in `update.RUNNING_STATUSES`. Paused, blocked, finished and other tasks do not count, because no agent runs for them.
  - `POST /api/update/dismiss` calls `update.dismiss(checker.latest)` when it is not `None`. Returns `{"ok": True}`.
  - `POST /api/update/run` with body `{"ws": <id or null>}`. The `ws` value must match `[a-z0-9-]{1,40}` or be absent. Returns `{"job": <id>}`.
  - `POST /api/update/close` calls `updater.close()`. Returns `{"ok": True}`.
  - The `/api/jobs/<id>` route calls `server.updater.job_read(job_id)` when the job is not running.

- [ ] **Step 1: Write the failing tests**

Run a real server subprocess (`factory dashboard` as in `test_global_server.py`) with `FACTORY_UPDATE_URL` pointing at a local fake API, `FACTORY_NO_UPDATE_CHECK` removed, and `FACTORY_UPDATE_ROOT` pointing at a temp folder with `.installed-by-script`.

```python
def test_update_info_shows_newer_release(update_server):        # fake API tag v99.0.0
    status, body = request(update_server.info, "GET", "/api/update")
    assert status == 200
    assert body["installed"] == cli.VERSION and body["latest"] == "99.0.0"
    assert body["dismissed"] is False and body["running_tasks"] == 0

def test_update_info_counts_running_tasks(update_server_with_tasks):
    # one task in each status: active, awaiting_approval, waiting_external, paused, blocked, finished
    assert request(update_server_with_tasks.info, "GET", "/api/update")[1]["running_tasks"] == 3

def test_dismiss_hides_this_version(update_server, factory_home):
    request(update_server.info, "POST", "/api/update/dismiss", {})
    assert request(update_server.info, "GET", "/api/update")[1]["dismissed"] is True
    assert (factory_home / "update-dismissed").read_text().strip() == "99.0.0"

def test_run_refuses_a_bad_ws(update_server):
    status, body = request(update_server.info, "POST", "/api/update/run", {"ws": "../x"})
    assert status == 400

def test_no_latest_when_check_is_off(factory, factory_home, tmp_path):
    ...  # default env (FACTORY_NO_UPDATE_CHECK=1): GET /api/update gives latest None
```

- [ ] **Step 2: Run the tests and make sure they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_update_api.py`
Expected: FAIL with 404 on `/api/update`.

- [ ] **Step 3: Implement the interfaces above**

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_update_api.py tests/test_update_server.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/factory/api.py lib/factory/server.py tests/serverutil.py tests/test_update_api.py
git commit -m "API: update routes"
```

---

### Task 5: Dashboard banner and Dock app navigate (spec "Banner", "Reload")

**Files:**
- Modify: `software-factory/lib/factory/web/dashboard.html`, `software-factory/lib/factory/dockapp/main.swift`
- Test: `software-factory/tests/test_dashboard_page.py`, `software-factory/tests/test_dockapp.py`

**Interfaces:**
- Consumes: Task 4 routes and the job result `{"url", "version", "output"}`.
- Produces in `dashboard.html`:
  - `<div id="update-banner" hidden></div>` after `<div id="banner" hidden></div>`.
  - `GLOBAL_API` regex includes `update`.
  - `checkUpdate()` runs at load and every `UPDATE_CHECK_MS = 3600000`.
  - `moveToServer(url)`: `if (window.webkit?.messageHandlers?.captn) tellApp("navigate:" + url); else location.assign(url);`.
  - On load, if the URL has `updated=<version>`, show `CAPTN is updated to {version}.` for `UPDATED_NOTICE_MS = 10000`. If the URL also has `warn=1`, add `install.sh reported an error. See {path}.` The path comes from `GET /api/update` as `"log"` (the full path of `workspaces.home() / "update.log"`). Task 4 adds this field.
  - After the notice shows, remove `updated` and `warn` from the URL with `history.replaceState`, so a reload does not show it again.
  - On job failure, `Close` calls `POST /api/update/close`, then hides the banner.
- Produces in `main.swift`, in `pageSaid`: a message that starts with `navigate:` is parsed as a URL. If `ServerAddress.isFactoryPage(url)` is false, it is ignored. Otherwise `loadDashboard(url)`, then each page that is not the dashboard runs `page.reload(base: url)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_update_banner_texts():
    assert '<div id="update-banner" hidden></div>' in PAGE
    assert "New version ${" in PAGE and "is available (you have ${" in PAGE
    assert "tasks are running. They continue, and their next steps use the new version. Update now?" in PAGE
    assert "1 task is running. It continues, and its next steps use the new version. Update now?" in PAGE
    assert "Updating…" in PAGE and "The update failed." in PAGE and "CAPTN is updated to ${" in PAGE
    assert "install.sh reported an error. See ${" in PAGE

def test_updated_notice_leaves_the_url():
    assert "history.replaceState" in PAGE
    block = PAGE.split("history.replaceState")[0].rsplit("\nfunction ", 1)[1]
    assert '"updated"' in block and '"warn"' in block

def test_update_banner_calls():
    assert "/api/update/run" in PAGE and "/api/update/dismiss" in PAGE and "/api/update/close" in PAGE
    assert "UPDATE_CHECK_MS = 3600000" in PAGE and "UPDATED_NOTICE_MS = 10000" in PAGE
    assert 'tellApp("navigate:" + url)' in PAGE and "location.assign(url)" in PAGE
    assert "|update" in PAGE.split("const GLOBAL_API")[1].split("\n")[0]

def test_update_confirm_is_not_a_browser_dialog():
    block = PAGE.split("function checkUpdate")[1].split("\nfunction ")[0]
    assert "confirm(" not in block and "alert(" not in block
```

In `test_dockapp.py`:

```python
def test_swift_navigate_checks_factory_page():
    src = dockapp.SOURCE.read_text()
    assert 'hasPrefix("navigate:")' in src
    block = src.split('hasPrefix("navigate:")')[1].split("\n    }\n")[0]
    assert "ServerAddress.isFactoryPage(" in block and "loadDashboard(" in block and "reload(base:" in block
```

- [ ] **Step 2: Run the tests and make sure they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_dashboard_page.py -k update tests/test_dockapp.py -k "navigate or compiles"`
Expected: the new tests FAIL. `test_swift_source_compiles` passes.

- [ ] **Step 3: Implement the banner and the Swift message handling**

Match the style of the existing `#banner`. Use the existing `waitJob` pattern, but read `job.output` on error and do not call `showError`.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: same command as Step 2.
Expected: PASS, including `test_swift_source_compiles` when `swiftc` exists.

- [ ] **Step 5: Commit**

```bash
git add lib/factory/web/dashboard.html lib/factory/dockapp/main.swift tests/test_dashboard_page.py tests/test_dockapp.py
git commit -m "Dashboard: update banner; Dock app: navigate message"
```

---

### Task 6: Release asset and README (spec "Release", "README")

**Files:**
- Modify: `.github/workflows/release.yml`, `software-factory/README.md`
- Test: `software-factory/tests/test_release_build.py`

**Interfaces:**
- Produces: the `gh release create` line attaches `install.sh` after the two existing files.

- [ ] **Step 1: Write the failing test**

```python
def test_release_workflow_attaches_install_script():
    text = (PROJECT_ROOT / ".github" / "workflows" / "release.yml").read_text()
    line = next(l for l in text.splitlines() if "gh release create" in l)
    assert "dist/software-factory.tar.gz.sha256 install.sh" in line
```

- [ ] **Step 2: Run the test and make sure it fails**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_release_build.py::test_release_workflow_attaches_install_script`
Expected: FAIL.

- [ ] **Step 3: Change `release.yml`, then the README install section**

README, after "To update the factory, run the same command again.", add in the STE style of the file:
- From the version that contains this feature, the dashboard shows a banner when a new version exists. "Update" installs it and restarts the server.
- Users of 0.2.0 or older run the install command one more time to get this feature. Their dashboard shows no banner.
- `FACTORY_NO_UPDATE_CHECK=1` turns the check off.

- [ ] **Step 4: Run the test and make sure it passes**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_release_build.py tests/test_docs.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ../.github/workflows/release.yml README.md tests/test_release_build.py
git commit -m "Release: attach install.sh; README: update from the dashboard"
```

---

### Task 7: Full suite and manual test list

**Files:**
- Create: `verification/2026-11-20-auto-update.md`

- [ ] **Step 1: Run the full suite once**

Run: `uv run --with pytest --with pyyaml pytest -q`
Expected: PASS. Fix failures, then run only the failing tests again.

- [ ] **Step 2: Write the manual test list**

One line per case, to run on a Mac with a script install: banner shows with a newer release; "Later" hides it until a newer version; "Update" in a browser tab moves to the new URL and shows `CAPTN is updated to {version}.`; "Update" in the Dock app moves the dashboard and the open editor windows; update with a running task shows the confirm text; a failed download shows `The update failed.` and the done checks run again; a second tab shows "Offline" after the update; the saved terminal choice (`~/.config/software-factory/terminal`) is the same after the update; in the Dock app, a new server that does not start shows its error until "Close", then "Start" starts the new server; "Update" in a second tab during an update shows the same job.

- [ ] **Step 3: Commit**

```bash
git add ../verification/2026-11-20-auto-update.md
git commit -m "Verification: update from the dashboard, manual tests"
```
