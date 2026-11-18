# Workspaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One global server and one dashboard show all registered factories (workspaces), poll the done checks of all of them, and let the user add (with optional `factory init`), rename, and delete workspaces.

**Architecture:** A new `workspaces.py` owns `$FACTORY_HOME/workspaces.yaml`. A new `runtime.py` holds one `Workspace` runtime per workspace (ctx, adapter, capabilities, error). `server.py` becomes global: its files live in `$FACTORY_HOME`, it keeps a lock-protected runtimes map, and one poll loop goes through all runtimes. `api.dispatch` routes `/api/w/<id>/...` to the existing route functions with the runtime in place of the server. `init` gets an optional library. The dashboard gets a sidebar.

**Tech Stack:** Python 3 (stdlib + pyyaml), git CLI, pytest, plain HTML/CSS/JS, `osascript` on macOS.

**Spec:** `specs/2026-11-18-workspaces-design.md`. Read it first. Every task implements the spec sections it names.

## Global Constraints

- All code changes stay in `software-factory/`. Work on branch `repo_panel`. `main` must not change.
- No code comments. No docstrings. Match the style of the surrounding code (short functions).
- Commit messages: short, plain. Never add a `Co-Authored-By` line.
- Run tests from `software-factory/` with `uv run --with pytest --with pyyaml pytest -q <paths>`. Full suite: `uv run --with pytest --with pyyaml pytest -q tests`. Save the baseline count before Task 1.
- Tests never write to the real `~/.config`. `FACTORY_HOME` points to a temporary folder in every test (Task 1 sets this up).
- `FACTORY_HOME` default: `~/.config/software-factory`.
- No browser `alert`, `confirm`, or `prompt` in pages.
- Server listens on `127.0.0.1` only. Token, Host, and Origin checks stay as they are.
- Exact texts (copy them as written):
  - No factory: `This repository has no factory. Run `factory init` in it first.` (error with `code: "no_factory"` and `main`)
  - Dashboard missing library: `The library folder does not exist. Create it, or leave the field blank.`
  - `require_repo`: `The factory is not initialized in this repository. Run `factory init`.`
  - Link warning: `The link <path> is missing. Run the install script.`
  - Confirm step title: `Set up the factory in <main>?`
  - Confirm step button: `Set up and add`. Field label: `Library folder`.
  - Delete modal: `Remove <name> from the dashboard? The repository and its tasks stay on disk. Done checks of this workspace stop. The workspace comes back when a task in this repository waits for a done check, when you resume a task in it, or when you run `factory dashboard` in it.`
  - Empty state: `No workspace. Click + to add a factory.`
  - Picker on another platform: `The folder picker works only on macOS.`
  - Start warning (`server.START_WARNING`): `Warning: the local server did not start, so done checks do not run. See <home>/server.log.`
- Do not add workspace registration to `factory launch`. Only `keep_polling` callers and `factory dashboard` register.

## Review Focus

1. A registered repository folder is deleted or its `factory.yaml` breaks. Expected: its row shows the error, the poll skips it, other workspaces keep working. Test in Task 3 (`test_broken_workspace_does_not_stop_others`).
2. Two repositories with the same folder name. Expected: ids `repo` and `repo-2`. Test in Task 1.
3. The user adds a worktree path of a registered repository. Expected: the main path is used and the duplicate error names the existing workspace. Test in Task 1.
4. A blank or whitespace library field in the dashboard. Expected: no library, and no folder is created in `$FACTORY_HOME`. Test in Task 4 (and CLI in Task 2).
5. A workspace is deleted in another browser tab while this tab shows it. Expected: the next refresh selects the first remaining workspace, without an error loop. Covered by the page logic in Task 5 (`/api/w/` 404 triggers a workspace reload) and the manual check in Task 7.

---

### Task 1: Workspace list module and test home

Spec: "Terms", "Workspace list", "Add rules" 1 and 4, "Constraints" (test home).

**Files:**
- Create: `lib/factory/workspaces.py`
- Modify: `tests/conftest.py` (fixtures `factory`, `inited`)
- Test: `tests/test_workspaces.py`

**Interfaces:**
- Produces (all in `factory.workspaces`):
  - `home() -> Path`: `Path(os.environ.get("FACTORY_HOME", "~/.config/software-factory")).expanduser()`, created on first write.
  - `list_path() -> Path`: `home() / "workspaces.yaml"`.
  - `mtime() -> float | None`: modification time of the list file, None if missing.
  - `slug(name: str) -> str`: spec rule 1 without the suffix.
  - `resolve_main(path: str) -> Path`: expands `~`, raises `FactoryError` if the path does not exist, returns `repo.main_repo(path)`.
  - `list_all() -> list[dict]`: entries `{id, name, path}` in file order.
  - `get(wid: str) -> dict | None`
  - `find_by_path(path) -> dict | None`: compares resolved paths.
  - `add(main: Path) -> dict`: raises `FactoryError` `"<path> is already the workspace <name>."` on a duplicate path. Does not check for a factory.
  - `register(main: Path) -> dict`: returns the existing entry or calls `add`.
  - `rename(wid: str, name: str) -> dict`: trims, refuses an empty name or more than 64 characters, refuses an unknown id.
  - `remove(wid: str) -> dict`: returns the removed entry, refuses an unknown id.
  - All writes go through `fsio.update_yaml(list_path(), fn)`.
- Produces (tests): autouse fixture `factory_home(tmp_path, monkeypatch) -> Path` that sets `FACTORY_HOME`. The `factory` fixture adds `"FACTORY_HOME": str(factory_home)` to its env. `Inited` gets `self.home`. The `inited` teardown does not change in this task: `server.json` moves to `$FACTORY_HOME` only in Task 3.

- [ ] **Step 1: Save the baseline.** Run the full suite. Write the pass count in the task report.
- [ ] **Step 2: Write the failing tests** in `tests/test_workspaces.py` with the `origin_repo` and `work` fixtures:
  - `test_home_uses_env`: `workspaces.home() == factory_home`.
  - `test_slug_rules`: `slug("SoftwareFactory") == "softwarefactory"`, `slug("My Repo_2") == "my-repo-2"`, `slug("--x--") == "x"`, `slug("ééé") == "workspace"`, `len(slug("a" * 50)) == 32`.
  - `test_add_and_list`: `add(origin_repo)` returns `{"id": "repo", "name": "repo", "path": str(origin_repo)}`, and `list_all()` returns it.
  - `test_same_folder_name_gets_suffix`: a second git repo in `work / "other" / "repo"` gets id `repo-2`.
  - `test_worktree_path_resolves_to_main`: create a worktree with `git worktree add`, `resolve_main(worktree) == origin_repo`, then `add(resolve_main(worktree))` after `add(origin_repo)` raises `FactoryError` with `"repo"` in the text.
  - `test_resolve_main_refuses_missing_and_non_git`: missing path and a plain folder both raise `FactoryError`.
  - `test_rename_rules`: rename to `"  New  "` gives `"New"`; empty and 65 characters raise; id stays `repo`.
  - `test_remove_and_register`: `remove("repo")` empties the list; `register(origin_repo)` adds it again; a second `register` returns the same entry and the list has one row.
- [ ] **Step 3: Run** `uv run --with pytest --with pyyaml pytest -q tests/test_workspaces.py`. Expected: FAIL (module missing).
- [ ] **Step 4: Implement** `lib/factory/workspaces.py` and the conftest changes.
- [ ] **Step 5: Run** the new tests, then the full suite. Expected: new tests PASS, the full suite count matches the baseline plus the new tests.
- [ ] **Step 6: Commit** `Add the workspace list`.

### Task 2: Init changes

Spec: "Init changes" 1 to 7, "Automatic registration" 1, "Poll loop" 1 (`poll_minutes` no longer written).

**Files:**
- Modify: `lib/factory/init.py`, `lib/factory/commands.py` (`init` parser and `init_cmd`), `lib/factory/version.py:27`
- Test: `tests/test_init_menu.py`, `tests/test_library.py` (or the file that tests `library.py`), `tests/test_migrate.py` (or the file that tests `migrate.plan`)

**Interfaces:**
- Consumes: `workspaces.register(main)` (Task 1).
- Produces:
  - `init.init(cwd, library=None, create_library=False) -> dict`. `library` is `None`, `""`, or blank: no library. The report has `"library": None` and `"library_git": False` in that case.
  - `init.InitChecksError(FactoryError)` with `self.details = {"checks": failed}` (failed check dicts). Message stays `Init stopped. Fix these first:` plus the lines.
  - `init.MissingLibraryError(FactoryError)` with `self.path`. Its message is the current CLI text with `--create-library`.
  - `init.link_warning() -> str | None`: the link warning text when `link_dir() / "factory"` does not exist, else None.
  - `factory.yaml` written by init: `library` is `""` when there is no library. No `poll_minutes` key.

- [ ] **Step 1: Write the failing tests:**
  - `test_init_without_library`: `factory("init")` succeeds; `factory.yaml` has `library: ""` and no `poll_minutes`; `factory("step", "list")` works.
  - `test_init_blank_library_is_none`: `factory("init", "--library", "  ")` succeeds and creates no folder in the cwd or in `factory_home`; the report (`--json`) has `"library": null`.
  - `test_init_registers_workspace`: after `factory("init", ...)`, `workspaces.list_all()` has one entry with `path == str(origin_repo)`. A second init keeps one entry.
  - `test_init_does_not_create_link`: remove the link that conftest made, run init, the link is still missing and stdout has `Run the install script.`.
  - `test_require_repo_text`: a command in a repo without init fails with `Run `factory init`.` in stderr.
  - `test_in_git_none`: `library.in_git(None) is False`.
  - `test_migrate_plan_without_library`: after init without library, `migrate.plan(ctx)["library"]["migrate"] is False` and `["path"] is None`.
- [ ] **Step 2: Run** these tests. Expected: FAIL.
- [ ] **Step 3: Implement.** In `init.init`, change a blank library to `None` before any `Path()` call. Skip the library block when it is `None`. Replace `report["link"] = ensure_link()` with the `link_warning()` result added to `report["warnings"]`. Keep `ensure_link` and the `factory link` command. Make `--library` optional in the parser. In `init_cmd`, call `workspaces.register(repo.load_ctx(".").main)` after `init.init` succeeds. Print `No library. Only built-in and local steps exist.` when the report library is None, and print the "not in git" warning only when a library exists.
- [ ] **Step 4: Run** the new tests and `tests/test_init_menu.py`. Expected: PASS.
- [ ] **Step 5: Commit** `Make the library optional in init`.

### Task 3: Global server, runtimes, and workspace routes

Spec: "Server > Life", "Runtimes", "Poll loop", "Routes" 2, "Automatic registration" 2, "Editor" (CLI part).

**Files:**
- Create: `lib/factory/runtime.py`
- Modify: `lib/factory/server.py`, `lib/factory/api.py` (`route`, `dispatch`, `ping`, `shutdown`, `job`, `info`), `lib/factory/cli.py:8` (`NO_VERSION_CHECK`), `lib/factory/commands.py` (`serve`, `dashboard`, `server stop`, `pipeline edit`, `step edit`, and the three `keep_polling` callers stay as they are)
- Modify tests: `tests/serverutil.py`, `tests/test_server.py`, `tests/test_background_poll.py`, and every test that reads `.factory/server.json`
- Test: `tests/test_global_server.py`

**Interfaces:**
- Consumes: `workspaces.list_all`, `workspaces.home`, `workspaces.mtime`, `workspaces.register` (Task 1).
- Produces:
  - `runtime.Workspace(server, entry: dict)`: attributes `id`, `name`, `path`, `ctx` (None on error), `adapter` (`{"ok", "message"}`), `capabilities`, `error` (str or None). Properties `jobs`, `next_poll`, and method `start_job(fn)` delegate to the server. The build runs `repo.load_ctx(path)`, `version.require_repo(ctx)`, and the adapter check of today's `Server.__init__`. Any exception becomes `error`.
  - `server.Server()`: no arguments. Methods: `reload()`, `reload_if_changed()`, `runtime(wid) -> Workspace | None`, `snapshot() -> list[Workspace]`. A `threading.Lock` guards `self.runtimes` (dict id → Workspace). `reload()` builds all runtimes again (a runtime holds no state). `Workspace.yaml_mtime` keeps the modification time of `<path>/.factory/factory.yaml` at build time (None if missing). `Workspace.stale() -> bool` is True when the current value differs. `Server.fresh(wid) -> Workspace | None` returns the runtime and builds it again first when it is stale. `reload_if_changed()` reloads when `workspaces.yaml` changed or when a runtime has an error.
  - `server.info_path() -> Path`, `read_info()`, `ensure_server()`, `running()`, `stop_server()`: no ctx. `keep_polling(ctx)`: `workspaces.register(ctx.main)`, then `ensure_server()`.
  - `server.stop_legacy(fdir: Path) -> bool`: if `fdir / "server.json"` names a live server that answers ping, POST `/api/shutdown` with its token; then remove the file. Called for each workspace at `Server.run()` start.
  - Error texts use the real log path: `The local server did not start. See <home>/server.log.` `START_WARNING` uses the same path.
  - `api.route(method, pattern, scope="workspace")`. Global scope: `ping`, `shutdown`, `job`. `dispatch(server, method, path, query, body)`: a path that matches `^/api/w/([a-z0-9-]{1,40})(/.*)$` resolves the runtime with `server.fresh(wid)` (unknown id → `NotFound`; runtime with `error` → `FactoryError(error)`), then matches `"/api" + rest` against workspace routes with the runtime as first argument. Other paths match global routes with the server.
  - `serverutil.info(fdir=None) -> dict`: reads `$FACTORY_HOME/server.json`. With `fdir`, adds `"ws"`: the id of the workspace whose path is `fdir.parent`. `serverutil.request` rewrites a path that starts with `/api/` to `/api/w/<ws>/...` when `info` has `"ws"` and the path does not start with `/api/ping`, `/api/shutdown`, `/api/jobs/`, `/api/workspaces`, or `/api/host`.

- [ ] **Step 1: Write the failing tests** in `tests/test_global_server.py`:
  - `test_dashboard_runs_outside_a_repo`: `factory("dashboard", cwd=work)` succeeds; `factory_home / "server.json"` exists; the URL in stdout has no `ws=`.
  - `test_dashboard_in_repo_selects_workspace`: `inited.factory("dashboard")` prints a URL with `ws=repo`.
  - `test_two_workspaces_one_server`: init a second repo (copy of the `origin_repo` setup in `work / "second" / "repo"`). One `server.json`. `/api/w/repo/tasks` and `/api/w/repo-2/tasks` both return 200. `/api/w/nope/tasks` returns 404.
  - `test_poll_covers_all_workspaces`: one waiting task with a `done_check` on a flag file in each workspace, `FACTORY_POLL_SECONDS=1`; both flags created; both tasks move on within 15 seconds.
  - `test_broken_workspace_does_not_stop_others`: register a second workspace, make sure that `/api/w/<second>/tasks` returns 200 (the runtime is built), then delete its folder. `/api/w/<second>/tasks` returns 400 with an error text. `/api/w/repo/tasks` returns 200. The poll still moves the first workspace's task.
  - `test_error_runtime_recovers` (in-process `Server()` with `FACTORY_HOME` set): break `factory.yaml` of a registered repo, `reload()`, the runtime has an error; fix the file, `reload()`, the error is gone. Then break it again: `server.fresh(id)` returns a runtime with an error, without `reload()`. Fix it again: one call of `server.reload_if_changed()` gives a runtime with no error, without a poll.
  - `test_legacy_server_file_is_removed`: write `<repo>/.factory/server.json` with a dead pid; start the server; the file is gone.
  - `test_stop_legacy_calls_shutdown` (in-process): monkeypatch `server.pid_alive` and `server.ping` to True and record the URL that `urllib.request.urlopen` gets; `stop_legacy(fdir)` posts to `/api/shutdown` and removes the file.
  - `test_server_stop_from_anywhere`: `factory("server", "stop", cwd=work)` stops the server.
  - `test_keep_polling_registers`: remove the workspace from the list, run `factory("tasks")` with a waiting check in the repo, and the workspace is in the list again.
  - `test_editor_url_has_ws`: `factory("pipeline", "edit")` prints a URL with `ws=repo`.
- [ ] **Step 2: Run** `tests/test_global_server.py`. Expected: FAIL.
- [ ] **Step 3: Implement** `runtime.py`, the server changes, the dispatch change, and the CLI changes. Add `"serve"`, `"dashboard"`, and `"server stop"` to `NO_VERSION_CHECK`. `dashboard_cmd` tries `repo.load_ctx()`: if it is initialized, it calls `workspaces.register(ctx.main)` and adds `ws=<id>` to the URL; any `FactoryError` from `load_ctx` means no `ws`. `server stop --unless-waiting` collects `engine.waiting_checks` over all listed workspaces and skips the ones that fail to load. The poll interval is `FACTORY_POLL_SECONDS` or 300. `watch_idle` uses waiting checks of all runtimes. Each poll calls `reload()` first, and it logs `poll failed for <id>: <error>` per failing workspace.
- [ ] **Step 4: Update the `inited` teardown** in `tests/conftest.py` to check `inited.home / "server.json"` in place of `.factory/server.json`. **Update the existing server tests** to the new helper (`info(inited.fdir)` keeps working through the `ws` rewrite). Replace reads of `inited.fdir / "server.json"` with `inited.home / "server.json"`. Change the `fail(ctx)` stub in `test_background_poll.py` to `fail()`. Remove the test that depends on `poll_minutes` if one exists, and write in the report which one.
- [ ] **Step 5: Run** the full suite. Expected: all PASS (baseline + new tests).
- [ ] **Step 6: Commit** `One global server for all workspaces`.

### Task 4: Workspace API routes

Spec: "Routes" 1 and 3, "Add rules" 2 and 3, "Needs-you count", "Runtimes" 2 (mtime reload), "Init changes" 6 and 7, "Dashboard > Add" 5 (failed checks).

**Files:**
- Modify: `lib/factory/api.py` (new global routes), `lib/factory/board.py` (count helper)
- Test: `tests/test_workspaces_api.py`

**Interfaces:**
- Consumes: Task 1 module, Task 2 `init.init`, `InitChecksError`, `MissingLibraryError`, Task 3 `Server.reload`, `Server.reload_if_changed`, `Server.snapshot`, `route(..., scope="global")`.
- Produces:
  - `board.needs_you(tasks: list[dict]) -> int`: count of tasks with `priority(task) < len(PRIORITY)`.
  - `board.open_tasks(tasks: list[dict]) -> int`: count of tasks whose status is not `finished`.
  - `GET /api/workspaces` → list of `{id, name, path, needs_you, open_tasks, error}`. It calls `reload_if_changed()` first, then `server.fresh(wid)` for each runtime, so a stale runtime is built again before the row is made. A workspace with an error has `needs_you: 0`, `open_tasks: 0`. `open_tasks` is not in the spec. The delete modal needs it.
  - `POST /api/workspaces/add` `{path, init?, library?}` → the new entry. Order: `resolve_main`, duplicate check with `find_by_path`, factory check, optional init, `workspaces.add`, `reload()`.
  - `POST /api/workspaces/<id>/rename` `{name}` → entry. `POST /api/workspaces/<id>/delete` → removed entry. Both call `reload()`. An unknown id gives 404.
  - `POST /api/workspaces/pick-folder` → `{path}` or `{path: null}`. It runs `["osascript", "-e", "POSIX path of (choose folder)"]` with `subprocess.run(capture_output=True, text=True)`. A non-zero return code gives `{path: null}`. The path loses its trailing newline and its trailing `/`.
  - `GET /api/host` → `{folder_picker: sys.platform == "darwin"}`.
  - Error bodies: no factory → 400 `{error, code: "no_factory", main}`. `InitChecksError` → 400 `{error, checks}`. `MissingLibraryError` → 400 with the dashboard text and `checks: []`. Any other init `FactoryError` → 400 `{error, checks: []}`.

- [ ] **Step 1: Write the failing tests** (served through the real server, using `request` without `ws`):
  - `test_list_has_counts`: one task `awaiting_approval`, one `blocked`, one `active` with `attention`, one `finished`; the row has `needs_you == 3`, `open_tasks == 3`.
  - `test_add_needs_factory`: a second repo without init; add returns 400 with `code == "no_factory"` and `main` equal to its path.
  - `test_add_with_init_without_library`: `{path, init: true, library: "  "}` returns 200; the repo has `.factory/factory.yaml` with `library: ""`; `factory_home` has no folder in it (only files, for example `server.json`, `workspaces.yaml`, and their `.lock` files).
  - `test_add_with_missing_library`: `library` points to a missing folder; 400 with `The library folder does not exist. Create it, or leave the field blank.` and `checks == []`.
  - `test_add_with_failed_check`: a repo without `origin` remote; 400 with `checks` that has one entry with `name == "git"`.
  - `test_add_duplicate`: adding the registered repo again gives 400 and names `repo`.
  - `test_rename_and_delete`: rename gives the new name in `/api/workspaces`; delete removes the row and `/api/w/repo/tasks` gives 404 afterwards; the repo `.factory/` still exists.
  - `test_list_marks_deleted_folder`: register a second workspace, make sure that `/api/w/<second>/tasks` returns 200, move its folder away, and one `GET /api/workspaces` gives that row an `error` (no poll, `FACTORY_POLL_SECONDS` not set). Move the folder back, and one more `GET /api/workspaces` gives `error: None`.
  - `test_list_sees_cli_init`: run `factory init` in a second repo through the CLI while the server runs; the next `GET /api/workspaces` has two rows.
  - `test_pick_folder` (in-process): monkeypatch `api.subprocess.run` to return code 0 with `"/Users/x/repo/\n"` → `{"path": "/Users/x/repo"}`; code 1 → `{"path": None}`; monkeypatch `api.sys.platform` to `"linux"` → `FactoryError` with the picker text.
- [ ] **Step 2: Run** `tests/test_workspaces_api.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the routes and the board helpers. Raise errors with `details` so that the existing `server.py` handler merges them into the body.
- [ ] **Step 4: Run** the new tests and `tests/test_dashboard_api.py`. Expected: PASS.
- [ ] **Step 5: Commit** `Workspace routes: list, add with init, rename, delete, folder picker`.

### Task 5: Dashboard sidebar and editor workspace

Spec: "Dashboard" (all subsections), "Editor".

**Files:**
- Modify: `lib/factory/web/dashboard.html`, `lib/factory/web/editor.html`
- Test: `tests/test_dashboard_page.py`, `tests/test_editor_page.py` (create if missing)

**Interfaces:**
- Consumes: Task 3 URL scheme `/api/w/<id>/...` and the `ws` URL parameter. Task 4 routes and error bodies.
- Produces (page code names used by the tests):
  - `GLOBAL_API = /^\/api\/(ping|shutdown|jobs\/|workspaces|host)/`. `api()` rewrites any other `/api/...` path to `/api/w/${encodeURIComponent(state.ws)}...`. The editor uses the same rule with `WS` from the URL.
  - `selectWorkspace(id)`: sets `state.ws`, writes `ws` with `history.replaceState`, saves `factory.workspace` in `localStorage` (inside try/catch), loads hidden columns from `factory.hiddenColumns.<id>`, closes the modal, clears `pausing`, `checking`, `deliveryErrors`, `removed`, sets `lastKey = null`, and refreshes.
  - `refresh()`: always loads `/api/workspaces`. If the selected id is missing from the list, it selects the stored id or the first one. With no workspace, the main area shows the empty text. With an `error`, the main area shows the error text. Otherwise it loads info, tasks, and backlog as today. A 404 on a `/api/w/` call reloads the list on the next refresh, without `showError` and without the `Offline` mark (that mark stays for network failures only).
  - `renderSidebar()`: `<aside id="sidebar">` with the title `Workspaces`, a `+` button (`openAddWorkspace`), and rows. Each row has the name, a `.badge` when `needs_you > 0`, `⚠` when `error`, and the `⋯` menu below. The badge reuses the `.count` pill class, with the accent color when `needs_you > 0`. It does not render again while a rename field or the menu is open.
  - The workspace `⋯` menu reuses the task menu pattern that main added: `<details class="more">` with a `<summary>` `⋯` and a `.menu` div with `Rename` and `Delete`. The existing `closeMenus`, `menuOpen`, and Escape handling close it. Do not write a second menu system. `renderSidebar` skips a render while `menuOpen()` is true.
  - `startRename(ws)`: the name becomes an input. Enter posts the rename. Escape cancels.
  - `openDeleteWorkspace(ws)`: modal with the exact delete text. When `open_tasks > 0`, it adds the line `<n> tasks are not finished.`. Buttons: `Cancel` and `Remove` (class `danger`).
  - `openAddWorkspace()`: modal with a path field, `Choose folder…` (only when `/api/host` gives `folder_picker: true`), and `Add`. On `code === "no_factory"`, it changes the modal to the confirm step: the title `Set up the factory in <main>?`, the list `<main>/.factory/` and `two lines in .git/info/exclude`, the line `Git does not track these files. Init keeps files that exist.`, the `Library folder` field, and `Set up and add`. Failed `checks` show as a list with `name: message`.
  - The API helper must pass the error body (`e.data`) to the add modal. The current `api()` already attaches `data` to the error.

- [ ] **Step 1: Write the failing page tests** (string checks, as in the current file): the dashboard page contains `id="sidebar"`, `Workspaces`, `GLOBAL_API`, `/api/w/`, `selectWorkspace`, `factory.hiddenColumns.`, `no_factory`, `Set up and add`, `Library folder`, `Choose folder…`, `/api/workspaces/pick-folder`, `Rename`, the exact delete text, `No workspace. Click + to add a factory.`, and has no `confirm(`. The editor page contains `GLOBAL_API` and `/api/w/`.
- [ ] **Step 2: Run** the page tests. Expected: FAIL.
- [ ] **Step 3: Implement** the page changes. Keep the CAPTN header (brand, tabs, `Offline`, theme toggle) at full width. Below it, a flex row with a fixed sidebar (about 220px) and `main`. Use the existing CSS variables (`--column`, `--line`, `--raised`, `--accent`, and so on), so both themes work. At widths under 600px (the breakpoint of the page), the sidebar goes above the board.
- [ ] **Step 4: Run** the page tests and the full suite. Expected: PASS.
- [ ] **Step 5: Commit** `Dashboard workspaces sidebar`.

### Task 6: Documentation

Spec: "Init changes" 3 and 8.

**Files:**
- Modify: `README.md` (lines near 53, 57, 99, 150, 161, and a new "Workspaces" part in the dashboard section), `skills/software-factory/SKILL.md:37`

- [ ] **Step 1: Update the README.** Explain these points:
  - `factory init [--library <path>] [--create-library]`.
  - The library is optional. Without a library, only built-in and local steps exist.
  - To add a library later, set `library:` in `.factory/factory.yaml`.
  - The install script makes the `~/.local/bin/factory` link. `factory link` fixes the link.
  - `factory dashboard` works from any folder.
  - Workspaces: the sidebar, the counter, Add with the init confirm step, Rename, Delete, and the folder picker on macOS only.
  - `FACTORY_HOME` and the files in it: `workspaces.yaml`, `server.json`, and `server.log`.
  - `server.json` and `server.log` are no longer in `.factory/`.
- [ ] **Step 2: Update the skill init flow** (`skills/software-factory/SKILL.md`, action "Init the factory"). Step 2: the library is optional, and the skill asks for a path only if the user wants a library. Step 3: without a library, offer the starter pack only with `--local`, because `--generic` fails with "No library is configured.".
- [ ] **Step 3: Run** `tests/test_docs.py`. Expected: PASS.
- [ ] **Step 4: Commit** `Document workspaces and the optional library`.

### Task 7: Final check

- [ ] **Step 1: Run** the full suite. Expected: all PASS. Write the count next to the baseline in the report.
- [ ] **Step 2: Manual check in the browser.** Use `FACTORY_HOME` set to a scratch folder and two test repositories. Make sure that:
  - The sidebar switches the columns and tasks.
  - The badge count changes.
  - Add with `Choose folder…` works.
  - Add on a repository without a factory shows the confirm step.
  - Rename with Enter and with Escape works.
  - Delete removes the row.
  - Delete in a second tab moves the first tab to the first remaining workspace (Review Focus 5).
  - Write the results in `verification/software-factory/workspaces-manual-check.md`.
- [ ] **Step 3: Commit** `Workspaces: verification`.
