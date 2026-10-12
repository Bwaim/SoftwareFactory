# Software Factory: Design

Date: 2026-10-12

## 1. Scope and sources

- Product requirements: `prompts/factory_skill_creation.md` (the prompt). It defines every feature, command, field, event type, status and Definition Of Done bullet.
- This spec records the design decisions taken in brainstorming. It does not copy the prompt. When the two differ, this spec wins.
- Build target: `software-factory/` (the plugin and `FACTORY_SOURCE`). Verification: `verification/software-factory/`. Marketplace: `.claude-plugin/marketplace.json`.

## 2. Goal and success

- One orchestrator skill starts each task in its own worktree, Herdr tab and named Claude session, and runs it through a pipeline of reusable steps.
- A local dashboard shows the tasks as a board and the backlog, and acts on them.
- Success: every Definition Of Done bullet of the prompt passes, proved by `verification/software-factory/report.md`.

## 3. Decisions

- D1. Program layout. One entry script `bin/factory`, run with `uv run --script`, with inline dependencies (`pyyaml` only). The code is split into modules in `lib/factory/`. "Single-file" in the prompt means inline dependencies, so only `uv` is needed.
- D2. The local server is the `factory serve` subcommand. There is no second script.
- D3. Adapters are Python modules in `lib/factory/adapters/`, selected by `terminal` in `.factory/factory.yaml`.
- D4. The expanded step list is a snapshot in `task.json`, taken at launch.
- D5. Locks are taken on a separate `<file>.lock` file.
- D6. Repository data and library are migrated independently, each from its own stored version.
- D7. The folder trust dialog of Claude in new worktrees is checked early in milestone 1. The fix is chosen with the user after the finding is reported.

## 4. Layout

```
software-factory/
  .claude-plugin/plugin.json
  skills/software-factory/SKILL.md
  bin/factory
  lib/factory/
    cli.py           # argparse, one function per command, no logic
    repo.py          # main repository, current task, --task
    fsio.py          # atomic write, locks
    version.py       # data version checks
    registry.py      # steps and pipelines from 3 levels, composite expansion, loop check
    pipeline_check.py
    config.py
    state.py         # task.json model, statuses, columns
    events.py        # events.jsonl
    engine.py        # step flow: next, done, skip, goto, block, unblock, approve, request-changes, wait, poll checks
    session.py       # pause, resume, focus, send prompt, wait-idle, notify, deliver
    launch.py        # create-task, create-worktree, dry run, rollback
    delete.py        # delete-task, clean
    backlog.py
    catalog.py
    library.py       # library commit
    init.py          # prerequisites, files, exclude entries, link, settings, library creation, starter pack
    migrate.py       # backups, clean-git check, migration scripts
    server.py        # factory serve
    adapters/base.py, herdr.py, fake.py
    web/editor.html, web/dashboard.html
  builtin/pipelines/, builtin/steps/
  catalog/pipelines/, catalog/steps/
  migrations/
  tests/
  README.md
```

- `bin/factory` resolves its own symlink and adds `lib/` to `sys.path`. So the `~/.local/bin/factory` link works.
- Each CLI command and each server route calls the same module function. `cli.py` and `server.py` hold no task logic.
- Built-in steps and pipelines are read from `builtin/` next to the CLI.
- `.factory/` gets one more file: `server.log`, the output of the detached server.

## 5. Plugin and command access

- `.claude-plugin/marketplace.json` defines the marketplace `software-factory`, with one plugin whose source is `./software-factory`.
- The plugin cache path changes when the plugin updates. Init creates `~/.local/bin/factory` as a symlink to `bin/factory` of the running plugin. The orchestrator checks this link at every start and fixes it when it points to another path.
- Init writes `.factory/claude-settings.json` with allow rules `Bash(factory:*)` and `Bash(factory *)`. Every task session starts with `--settings <main repository>/.factory/claude-settings.json`.

## 6. Task data

`task.json` fields:

- Fixed fields, written only by the CLI: `id`, `description`, `pipeline`, `steps` (the snapshot), `position`, `status`, `status_reason`, `saved_status`, `column`, `worktree`, `session_id`, `terminal_handle`, `goto_counts`, `approval`, `created_at`, `updated_at`.
- `state`: the key/value store used by `reads`, `writes` and `factory state get|set`. It holds the inputs, `summary`, `branch`, `ticket`, `mr_url` and every key a step writes.

Snapshot (D4):

- At launch, the pipeline is expanded into a flat list of leaf steps. Composite steps are opened up at this point. `create-worktree` is added first when the pipeline does not list it (not for `new-step-assistant`).
- Each entry stores the leaf step id, its path (ids from the pipeline entry down to the leaf) and the pipeline entry overrides: `with`, `column`, `model`, `effort`.
- `position` is the index in this snapshot. It is shown as a name path, for example `rebase-and-commit > commit`.
- At each `next`, only the step file content is loaded again. A changed step file applies from the next step. A changed pipeline file, or a changed child list of a composite step, applies only to new tasks.

## 7. Step flow (`engine.py`)

`factory next` prints:

- The step path, type and where it runs.
- The resolved config values (`with`, then `config.yaml`, then default). For each missing value, the instruction to ask the user and run `factory config set <step> <key> <value>`. It logs `config_asked`.
- The values of the `reads` keys, and the step body.
- For a `script` step: the command to run.
- For a `subagent` step: the full Agent tool call, with model, effort and a self-contained prompt. Pipeline entry values win over manifest values.
- For a task without a worktree: every `factory` command with `--task <id>`.
- On the first `next` of a position: log `step_started`, move the column, and run the start action of the step (`user-validation` clears `approval` and sets `awaiting_approval`).

`factory done`:

- Runs `done_check` when set, with a timeout. It logs `done_check_failed` with the output when the check fails.
- On success, it logs `step_done` and advances `position`. After the last step, it sets `finished`, logs `task_finished` and calls `notify`.

Other commands:

- `factory skip`: refused for `required` steps.
- `factory goto <step-path> --reason <text>`: only to an earlier position. The 3rd jump back to the same position blocks the task with "loop on <step>".
- `factory approval check`: exits 0 only when the current position is approved. It is the `done_check` of `user-validation`.
- `factory poll`: runs the `done_check` of every `waiting_external` task, with a 60 second timeout. Paused tasks are skipped. When a check passes, the step is done and the message goes through `session.deliver`.

## 8. Concurrency (D5)

- The session, the server poll and the dashboard can write the same files.
- Every change to `task.json`, `config.yaml` and `backlog.md` takes an `fcntl` lock on `<file>.lock`. The lock is held for the whole read, change and rename.
- Every write is atomic: write a temporary file in the same folder, then rename it.

## 9. Launch and delete

Launch order:

1. Validate the values.
2. `git fetch`.
3. Create the worktree.
4. Create the task folder and `task.json`.
5. `start-session`.
6. Save the terminal handle.
7. Remove the backlog entry.

- On failure, the done steps are undone in reverse order.
- The rollback deletes the branch only if this launch created it. It never deletes an existing branch.
- `--dry-run` runs the checks of steps 1 to 3 without side effects, other than `git fetch`, which only updates remote refs.
- Delete and clean follow the prompt.

## 10. Sessions and the Herdr adapter

Adapter interface:

- Required: `check`, `start_session`, `close`.
- Optional: `send_prompt`, `focus`, `state`, `wait_idle`, `notify`.
- `capabilities()` lists the optional actions. The menu and the dashboard hide the others.

Herdr adapter:

- Every call uses JSON output. Ids come from the response and are never guessed.
- The exact syntax of each command is checked against `herdr` 0.9.3 before the adapter is written.
- The build checks whether closing a tab or workspace stops the Claude process. If it does not, `close` stops the agent first.
- The handle is `{"agent": <name>, "workspace": <id>}` or `{"agent": <name>, "tab": <id>}`.

Fake adapter:

- It records each call in a JSON file and returns configurable results.
- It is used only by tests, and Init never offers it.

`session.py`:

- `resume` rebuilds the Claude arguments of the launch, adds `--resume <session_id>`, and restores `saved_status`.
- `deliver(task, text)` sends text to a task session. If the session is gone, it resumes the session and puts the text inside the resume prompt, so it sends one prompt only.
- Poll, approve, request-changes and external-done all use `deliver`.

Folder trust (D7):

- In milestone 1, check whether Claude shows the folder trust dialog when it starts in a new worktree.
- If it does, `start-session` must detect the dialog and report it clearly.
- Report the finding to the user before choosing the fix: either `worktree_root` under a trusted folder, if trust is inherited, or ask the user to accept the dialog once.

## 11. Server (`factory serve`)

- `ThreadingHTTPServer` on `127.0.0.1`, on a free port.
- It writes `server.json` with the port, the token and the pid.
- `factory dashboard` and `factory pipeline edit` reuse the server when the pid is alive and `/api/ping` answers with the token.
- Otherwise they start the server fully detached, with `start_new_session=True` and output to `.factory/server.log`.
- Pages are always opened at `http://127.0.0.1:<port>/...?token=<token>`, never `localhost`.

Security:

- Every `/api/*` request needs the `X-Factory-Token` header.
- A request is rejected when its `Host` is not `127.0.0.1:<port>`.
- A request is rejected when it has an `Origin` header that is not `http://127.0.0.1:<port>`.

Behavior:

- At start, the server runs the adapter check. If it fails, the dashboard shows a banner with the reason and disables the buttons that need the adapter.
- A background thread runs `poll` every `poll_minutes`.
- The server exits after 30 minutes without requests, or on `POST /api/shutdown` (used by Exit).
- Long actions (pause with `wait-idle`) run in a thread and return a job id. The page polls `/api/jobs/<id>`.

## 12. Pages

- Plain HTML, CSS and JavaScript, with no external library. Served from `lib/factory/web/`.
- The editor runs `/api/pipelines/check` after each change, with a short delay.
- The dashboard refreshes every 5 seconds. This refresh also keeps the server alive.
- Hidden columns are saved in `localStorage`.
- Features follow the Pipeline editor and Dashboard sections of the prompt.

## 13. Orchestrator (`SKILL.md`)

At start, in order:

1. `factory terminal check`. If it fails, say why and stop.
2. Check and fix the `~/.local/bin/factory` link.
3. `factory version check`. Same: continue. Older: run `migrate`. Newer: stop and ask the user to update the factory.
4. If paused tasks exist, offer to resume all, some or none.

Menu:

- A numbered text list built from `factory menu --json`, with one heading per group.
- The CLI decides which actions show: only Init before init, and no actions the adapter does not support.
- Each action maps to `factory` commands.
- The conversation is needed only for `backlog-add`, `backlog-remove`, the backlog import, catalog choices, and confirmations of dry runs.

## 14. Init (`init.py`)

`factory init --library <path> [--create-library]`:

1. Checks the prerequisites.
2. Writes `factory.yaml` (version, library, `terminal: herdr`, default columns, `poll_minutes: 5`), `config.yaml` and `backlog.md`.
3. Writes `claude-settings.json`.
4. Creates the folders.
5. Adds `.factory/` and `.factory.backup-*/` to `.git/info/exclude`.
6. Creates the link.

- It never overwrites an existing file.
- The starter pack (`factory catalog install quick-task ...`) and the backlog import are separate commands. The skill asks for them.

## 15. Versioning and migration (D6)

- Data format version 1. `.factory/factory.yaml` and `<library>/factory.yaml` each store their own version.
- Every command checks the repository version. Commands that load the library also check the library version. A different version is refused.
- `migrations/<n>-to-<n+1>.py` scripts expose `migrate_repo(factory_dir)` and `migrate_library(library_dir)`.
- `migrate` brings each target from its own version to the current version. A library already at the current version, for example one shared with another migrated repository, is not migrated again.
- Backups and the clean-git check follow the prompt. The library is backed up or checked only when it is migrated.
- The build ships version 1 and no migration scripts. Tests use a fake `1-to-2` script, from a folder set with `FACTORY_MIGRATIONS_DIR`. This variable is used only by tests.

## 16. Testing and verification

- `pytest`, run with `uv run --with pytest`. Product scripts keep `pyyaml` as their only dependency.
- Every test builds its repositories inside `verification/software-factory/`: a test repository with a bare `origin`, and a test library in its own repository. `worktree_root` points there.
- Every CLI bullet of the prompt's Verification section has at least one test, using the fake adapter.
- Server tests start a real `factory serve` and call it with `urllib`. One test checks that the server still runs after the command that started it has ended.
- The lock test runs two real processes that write 200 times each, then checks that no write is lost.
- End-to-end test, `tests/e2e_herdr.py`, in the real Herdr session with real Claude. It covers every e2e bullet of the prompt:
  - Launch: fetch, worktree from `origin/main`, Herdr, Claude named with the task id, first prompt received.
  - Two `script` steps run to the end with `next` and `done`.
  - No permission prompt during the session.
  - Pause closes the terminal. Resume reopens the same session, which continues.
  - Delete is refused without `--confirm-unpushed` when there are uncommitted changes, then closes the terminal, removes the worktree and archives the task folder.
- The e2e script records the ids of every Herdr workspace, tab and pane it creates, and closes only those.
- At the end, the tests remove the test repositories.
- A report generator writes `verification/software-factory/report.md`, with one section per milestone, from the pytest and e2e results.

## 17. Milestones

The order follows the prompt: Core, Task life, Authoring, Lifecycle and docs, Dashboard.

- Each milestone ends with its tests passing and a commit.
- Milestone 1 includes the folder trust check (D7) and the Herdr syntax check.
