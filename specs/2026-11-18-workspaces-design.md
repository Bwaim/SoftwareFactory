# Workspaces in the dashboard

Source: user request in the session of 2026-11-18.

## Intent

The user runs tasks in several repositories at the same time and loses track of them. The dashboard must show all registered factories in one place. Every factory must keep its done checks running in the background, also when the dashboard shows another factory.

## Terms

- Workspace: one registered factory. A workspace points to the main folder of one git repository that has `.factory/factory.yaml`.
- Workspace list: the file that keeps all workspaces. Its path is `$FACTORY_HOME/workspaces.yaml`.
- `FACTORY_HOME`: the global folder of the factory. The default is `~/.config/software-factory`. The `FACTORY_HOME` environment variable overrides it. Tests use the override.
- Runtime: the server objects for one workspace (repo context, terminal adapter, adapter status, capabilities).
- Needs-you count: the number of tasks in a workspace that wait for the user. A task counts if it has `attention` or its status is `blocked` or `awaiting_approval`. This is the rule of `board.priority()`: a task counts when its priority is below `len(board.PRIORITY)`.

## Goals

1. `factory dashboard` works from any folder, also outside a git repository.
2. The dashboard shows a "Workspaces" sidebar. Each row shows the workspace name and its needs-you count.
3. A click on a workspace shows its columns, tasks, and backlog.
4. Each workspace row has a "⋯" button. The button opens a menu with "Rename" and "Delete".
5. A "+" button next to the "Workspaces" title adds a workspace. The user types a path or selects a folder with the macOS folder picker.
6. One server polls the done checks of all workspaces.

## Non-goals

- Change the order of workspaces with drag and drop. The sidebar shows workspaces in the order of addition.
- Show tasks of several workspaces in one board.
- A folder picker on Linux or Windows.

## Anti-goals

- Delete removes files. Delete only removes the workspace from the workspace list. It never changes the repository or its `.factory/` folder.
- Two servers poll the same repository at the same time. This can run a done check two times.
- A broken workspace (missing folder, invalid `factory.yaml`) stops the server or hides the other workspaces.

## Approaches

- O1, one global server (selected). One server process runs for all workspaces. It keeps one runtime per workspace. One poll loop goes through all workspaces. API routes get a workspace prefix.
- O2, one hub server and one server per repo. The hub shows the dashboard and forwards each API call to a repo server. `api.py` does not change. It gives N+1 processes, two layers of tokens, and repo servers that stop after 30 idle minutes.
- A third option was dropped: the browser calls each repo server directly. `refusal()` in `server.py` refuses other origins, so this needs security changes.

The user selected O1. One process with one poll loop matches the goal "all workspaces keep running their done checks". O2 adds a process layer only to keep the route code unchanged, and that code is small.

## Workspace list

The file `$FACTORY_HOME/workspaces.yaml` has this shape:

```yaml
workspaces:
  - id: softwarefactory
    name: SoftwareFactory
    path: /Users/me/Projects/SoftwareFactory
```

1. `id` is a slug of the folder name. Make it lowercase. Replace each run of characters outside `[a-z0-9]` with one `-`. Remove `-` at the start and the end. Cut it to 32 characters. If the result is empty, use `workspace`. If the slug exists, add `-2`, `-3`, and so on. The id never changes after creation.
2. `name` is the display name. The default is the folder name. Rename changes only `name`. A name has 1 to 64 characters after trim. Two workspaces can have the same name.
3. `path` is the absolute main repository path (`repo.main_repo`). If the user adds a worktree path, the list keeps the main repository path.
4. Two workspaces cannot have the same `path`. If the user adds a path that is in the list, return an error that names the existing workspace.
5. All writes use `fsio.update_yaml`, so the file lock protects them.
6. A new module `workspaces.py` owns this file: `list`, `get`, `add`, `rename`, `remove`, `find_by_path`.

### Add rules

1. The path must exist and be in a git repository.
2. If the main repository has no `.factory/factory.yaml` and the request has no `init: true`, return an error with the code `no_factory` and the main repository path. The dashboard then shows the init confirm step (see "Dashboard > Add").
3. If the request has `init: true`, the server calls `init.init(main, library)` in its own process, then adds the workspace. `library` is optional. An empty value means no library (see "Init changes").
4. The path accepts `~`.

### Automatic registration

1. The `init` CLI command in `commands.py` adds the repository to the workspace list after `init.init()` succeeds. `init.init()` itself does not register. The dashboard add route calls `init.init()` and then adds the workspace once, so no duplicate path error occurs.
2. `server.keep_polling(ctx)` and `factory dashboard` inside an initialized repository add the repository if it is not in the list. `keep_polling(ctx)` uses `ctx` only for this registration. `factory dashboard` outside a repository registers nothing. This makes sure that the done checks of a launched task run. It also moves existing users to workspaces without a manual step.

## Server

### Life

1. `server.json` and `server.log` move to `$FACTORY_HOME`. The server process starts with `cwd=$FACTORY_HOME`.
2. `factory serve` and `factory dashboard` do not need a repository. Add them to the commands that skip `repo.load_ctx` and `version.require_repo` in `cli.main`.
3. `ensure_server()`, `running()`, and `stop_server()` take no repo context. `keep_polling(ctx)` keeps its `ctx` argument for the automatic registration only. It does not pass `ctx` to the server.
4. The server stops after `IDLE_SECONDS` without requests only when no workspace has a waiting check. This is the rule of `specs/2026-10-14-background-poll-design.md`, applied to all workspaces.
5. `factory server stop` stops the global server. It works from any folder. With `--unless-waiting`, the server keeps running if any workspace has a waiting check.
6. On start, the server looks for an old `<repo>/.factory/server.json` in each workspace. If that old server runs, the new server stops it and removes the file. This prevents two polls of one repository.

### Runtimes

1. A `Workspace` runtime object has `ctx`, `adapter`, `capabilities`, and a reference to the shared `jobs` and `start_job` of the server. It also exposes `next_poll` of the server.
2. The server builds runtimes from the workspace list. It reads the list again in three cases: after an add, rename, or remove through the API, at each poll, and on `GET /api/workspaces` when the modification time of `workspaces.yaml` changed. The last case shows a repository from `factory init` in a terminal within 5 seconds.
3. A runtime that fails to build (missing folder, invalid `factory.yaml`, wrong version) keeps an `error` text. Its routes return that error. The poll loop skips it.
4. The current route functions in `api.py` receive the runtime in place of the server. They use `server.ctx`, `server.adapter`, `server.capabilities`, `server.jobs`, `server.start_job`, and `server.next_poll`. The runtime gives the same names, so the route bodies stay the same.
5. A lock protects the runtimes map. Readers (routes, poll loop) take a copy of the map under the lock and then work on the copy. Writers (add, remove, reload) replace the map under the lock. A runtime removed during a poll finishes its current poll step.

### Poll loop

1. One loop runs every `poll_interval`. The interval is the global default (5 minutes) or `FACTORY_POLL_SECONDS`. The per-repo `poll_minutes` in `factory.yaml` is no longer used. `factory init` stops writing it. An existing `poll_minutes` key stays in the file and the server ignores it.
2. For each runtime without error, run `engine.poll(ctx)` and `rename.apply_all_pending(ctx)`. An exception in one workspace is logged to `server.log` with the workspace id. The loop continues with the next workspace.

### Routes

1. Global routes:
   - `GET /api/ping`
   - `POST /api/shutdown`
   - `GET /api/jobs/<id>`
   - `GET /api/workspaces`: the list with `id`, `name`, `path`, `needs_you`, and `error`.
   - `POST /api/workspaces/add` with `{path, init, library}`. `init` (default false) and `library` (default empty) are optional. It returns the new workspace. Without a factory and without `init: true`, it returns HTTP 400 with `{error, code: "no_factory", main}`. If init fails, it returns HTTP 400 with `{error, checks}`, where `checks` is the list of failed checks. If init fails for another reason (for example a missing library folder), `checks` is an empty list and the dashboard shows only `error`.
   - `POST /api/workspaces/<id>/rename` with `{name}`.
   - `POST /api/workspaces/<id>/delete`.
   - `POST /api/workspaces/pick-folder`: runs `osascript -e 'POSIX path of (choose folder)'` and returns `{path}`. If the user cancels, it returns `{path: null}`. On other platforms it returns an error.
   - `GET /api/host`: returns `{folder_picker: true|false}`. The value is true on macOS.
2. Workspace routes: all other current routes move under `/api/w/<id>/`. Example: `/api/tasks` becomes `/api/w/<id>/tasks`. An unknown id returns 404.
3. The pick-folder call blocks until the user closes the dialog. The server is a `ThreadingHTTPServer`, so other requests continue.

### Needs-you count

`GET /api/workspaces` computes the count with `state.list_tasks(ctx)` for each workspace. It does not build full board rows, because the dashboard calls it every 5 seconds.

## Dashboard

### Layout

```
┌ Workspaces    + ┐┌ Tasks  Backlog ───────────────────────────┐
│ SoftwareFac  2 ⋯││ Discovery │ Spec │ Plan │ Impl │ Review   │
│ backend        ⋯││  [task]   │      │[task]│      │          │
│ ⚠ old-repo     ⋯││           │      │      │      │          │
└─────────────────┘└───────────────────────────────────────────┘
```

1. A left sidebar shows the "Workspaces" title, the "+" button, and one row per workspace.
2. The selected row has a highlight.
3. A needs-you count above 0 shows as a badge. A count of 0 shows nothing.
4. A workspace with `error` shows a warning mark. A click on it shows the error text in the main area.
5. The page refreshes the workspace list with the task list, every `REFRESH_MS` (5 seconds).

### Selection

1. The URL keeps the selected id: `/dashboard?token=...&ws=<id>`.
2. `factory dashboard` inside a registered repository opens with that workspace selected. From another folder, it opens with no `ws`.
3. With no valid `ws`, the page selects the last selected workspace from `localStorage`, else the first workspace.
4. The hidden columns key in `localStorage` gets the workspace id, so each workspace keeps its own hidden columns.
5. A switch clears the open modal and the per-task state (`pausing`, `checking`, `deliveryErrors`, `removed`).

### Add

1. The "+" button opens a modal with a path field, a "Choose folder…" button, and "Add".
2. "Choose folder…" shows only when `/api/host` returns `folder_picker: true`. It calls `pick-folder` and puts the result in the path field.
3. "Add" calls `workspaces/add`. On success, the modal closes and the new workspace is selected. On error, the modal shows the error text.
4. If the error code is `no_factory`, the modal changes to a confirm step:
   - The title is "Set up the factory in <main>?".
   - It lists what init writes: the `<main>/.factory/` folder and two lines in `.git/info/exclude`. Git does not track any of them. Init keeps files that exist.
   - It has an optional "Library folder" field. The field is blank by default.
   - It has a "Set up and add" button. The button sends `{path, init: true, library}` to `workspaces/add`.
   - The dashboard does not offer `--create-library`. The library folder must exist.
5. Init runs the terminal (Herdr), git `origin`, and `uv` checks in the environment of the server process. If the server did not start in a Herdr pane, `HERDR_ENV` is not set and the terminal check fails. Task launch from the dashboard has the same limit, so this is accepted. If init fails, the confirm step shows the list of failed checks.

### Menu

1. The "⋯" button opens a small menu with "Rename" and "Delete". A click outside the menu or Escape closes it.
2. "Rename" replaces the name with a text field. Enter saves. Escape cancels.
3. "Delete" opens a confirmation modal. It does not use the browser `confirm()`. The modal text is: "Remove <name> from the dashboard? The repository and its tasks stay on disk. Done checks of this workspace stop. The workspace comes back when you launch or resume a task in this repository, or run `factory dashboard` in it." If the workspace has tasks that are not finished, the modal also shows their number.
4. Delete does not stick. The user selected this. The list keeps no record of deleted workspaces, so automatic registration adds the repository again. The user prefers that a running task always has its done checks.
5. After delete, the page selects the first remaining workspace. With no workspace, the main area shows: "No workspace. Click + to add a factory."

### Editor

The editor page (`/editor`) also takes `ws=<id>` and uses `/api/w/<id>/` routes. `factory pipeline edit` and `factory step edit` stay repo commands. They add `ws=<id>` of their repository to the URL.

## Init changes

These CLI changes are part of the same work.

1. The library becomes optional. `factory init` no longer requires `--library`. Without it, init skips the library checks and writes `library: ""` to `factory.yaml`.
2. The rest of the code accepts no library, because `ctx.library()` returns None for an empty value. The effects:
   - There is no generic level. Only the built-in and local levels exist.
   - The editor already hides "Save generic".
   - `catalog install --generic` and generic saves fail with "No library is configured.".
   - Library commits are disabled.
   - `factory migrate` skips the library.
3. A second `factory init` does not set a library, because `write_new` keeps `factory.yaml`. To add a library later, the user edits `factory.yaml`. A command for this is out of scope.
4. The error text in `version.require_repo` changes from "Run `factory init --library <path>`." to "Run `factory init`.".
5. `init` no longer calls `ensure_link()`. The install script owns the `~/.local/bin/factory` link. From the server, `ensure_link()` can create a link to the code that the server runs, for example a development checkout. In its place, init makes sure that the link exists. If the link is missing, init adds this warning to the report: "Run the install script." The `factory link` command stays.
6. `init.init()` changes an empty or blank `library` value to `None` before any `Path()` call. `Path("")` resolves to the current folder, and the server runs with `cwd=$FACTORY_HOME`, so a blank value would create a library there. Add a test for a blank library from the dashboard and from the CLI.
7. If the library folder does not exist, the CLI keeps its text "Run again with --create-library to create it.". The dashboard add route returns its own text: "The library folder does not exist. Create it, or leave the field blank.".
8. Update the README: the init options, the optional library, how to add a library later, and the link.

## Constraints

- Python standard library and `pyyaml` only, as today.
- The server listens only on `127.0.0.1`. The token, Host, and Origin checks stay.
- No browser `alert`, `confirm`, or `prompt`.
- Tests use `FACTORY_HOME` in a temporary folder. They never write to the real `~/.config`. Add `FACTORY_HOME` to the CLI env dict in `tests/conftest.py` (next to `FACTORY_LINK_DIR` and `FACTORY_TERMINAL`). In-process tests that call `workspaces.py` or the server set the same override.

## Left to the builder

- The module and class split in `server.py` (for example a new `runtime.py`).
- The exact CSS of the sidebar, badge, and menu. Use the existing CSS variables of `dashboard.html`.
- How the dashboard code passes the workspace id to `api()` (for example a `wsApi()` helper).
- The update of existing tests that call the old routes and the old `server.json` path.
- Add tests for `library.in_git(None)` and `migrate.plan` with no library. No code change is needed: `repo_root(None)` returns None, so `in_git(None)` returns False, and `library_version(None)` returns None, so `migrate.plan` marks no library migration.
