# Factory fixes: names, focus, artifact viewer, poll and clean

Date: 2026-10-16
Source: `prompts/factory_fixes.md`
Code: `software-factory/`
Baseline: 416 tests pass (`uv run --with pytest --with pyyaml pytest -q tests`).

## Goal

Fix six problems found in daily use, without changing the data format version.
Each fix is one milestone, built and committed in this order on the branch `factory-fixes`.

## Facts checked on 2026-10-16

- Herdr 0.9.3: `herdr workspace rename <WORKSPACE_ID> <LABEL>...`, `herdr tab rename <TAB_ID> <LABEL>...`, `herdr agent rename <TARGET> <NAME>`.
- Claude Code 2.1.301 has `--name <name>` and the slash command `/rename [name]` ("Rename the current conversation", runs at once). A live session can be renamed by typing `/rename <name>` into it.
- git 2.55: `git merge-tree --write-tree` is available.
- The task id is `slugify(description)` (29 characters max) plus `-2`, `-3` (`launch.py`).
- `poll_loop` sleeps, then calls `engine.poll` (`server.py`). The next poll time is not saved.
- `fsio.locked(path)` is an `fcntl.flock` lock on `<path>.lock`. It works across processes.

## Decisions

- D1. The name rule lives in one function, `adapters.base.herdr_name(name)`. The Herdr adapter and the fake adapter both use it, so tests with the fake adapter see the real name in the handle.
- D2. Squash detection is one new function in `delete.py`, `content_merged(ctx, rev, base_ref)`. Both `merge_state` (clean) and `plan_delete` (delete) call it.
- D3. Only the artifact viewer is "dismissable". `openModal` gets an option `{ dismissable: true }`. Forms keep today's behavior, plus an Escape guard.
- D4. The next poll time lives in memory on the `Server` object (`server.next_poll`). `/api/tasks` stays a list. Each row of a task that waits on a done check gets `next_check_at` (ISO time) and `last_check`.
- D5. The cross-process check lock is `fsio.locked(<task dir>/check)`, which gives the file `.factory/tasks/<id>/check.lock`. The lock is taken without blocking: a second check returns "A check is already running."
- D6. `terminal_app` is saved in `.factory/config.yaml`, in the section `terminal`: `factory config set terminal terminal_app Ghostty`. A missing key means "ask". An empty string means "never bring an app to the front".
- D7. The display name is a new optional field of the task file, `display_name`. A missing field means the id. No migration, no version change.
- D8. A failed terminal rename is saved as an optional task field `rename_error`. A failed Claude rename is saved as `claude_rename_error`. Both are logged as the event `rename_failed`. A successful Claude rename clears only `claude_rename_error`, never a Herdr rename error. The card shows both.
- D9. A pending Claude rename is saved as an optional task field `claude_rename_pending` (the name to apply). The server poll loop and each `/api/tasks` call apply it when the session is idle and no question box is open. A resume applies it with `--name` and clears it. `session.claude_args` always uses `display_name or id` for `--name`.

## Milestone 1: Herdr name limit

Behavior:

- `herdr_name(name)`:
  - Lowercase. Each run of characters outside `[a-z0-9_-]` becomes `-`. Leading and trailing `-` are removed.
  - When the result does not start with a letter, it gets the prefix `t-`. An empty result becomes `t`.
  - When the result is longer than 32 characters, it becomes `<start>-<hash4>`: the first 27 characters (trailing `-` removed), `-`, then the first 4 hex characters of the SHA-1 of the full requested name. 32 characters at most.
  - A name that already matches `^[a-z][a-z0-9_-]{0,31}$` is returned unchanged.
- `HerdrAdapter.start_session` computes the Herdr name first. The agent, the tab label and the workspace label use it. The handle `agent` field holds it.
- Every later call uses the handle. Nothing reads the requested name again.
- `factory terminal start-session` prints the handle. No change needed. The README says that `agent` in the handle is the real Herdr name.
- `FakeAdapter.start_session` records both the requested and the real name and returns the real name in the handle.

Tests (`tests/test_herdr_names.py`):

- `library-following-opening-the-review-mr` gives a valid name of 32 characters at most, and starts a session with the fake adapter and with the stubbed `herdr` (`tests/fake_herdr.py`). The stub log shows `agent start <valid name>`.
- Two 40-character names that differ only after character 32 give two different names.
- `HT-4549 Fix` gives `ht-4549-fix`. `4549` gives `t-4549`. `ht-4549` is unchanged.

## Milestone 2: Clean after a squash merge

Behavior:

- `content_merged(ctx, rev, base_ref)`, run in the main repository:
  - Run `git merge-tree --write-tree origin/<base_ref> <rev>`.
  - Return true only when the exit code is 0 and the first output line equals `git rev-parse origin/<base_ref>^{tree}`.
  - Any error or conflict returns false.
- `rev` is `refs/heads/<branch>` when the task has a branch. For a task without a branch, `rev` is the `HEAD` commit of the worktree, only when the worktree still exists.
- `merge_state` (clean): after the two current checks, when `content_merged` is true, the result is `(True, "merged (squash)")`.
- `plan_delete` (delete):
  - New plan field `squash_merged`.
  - When the commits of `git log <upstream>..HEAD` are not empty and `content_merged` is true, the plan sets `squash_merged: true`, `unpushed: []` and `delete_branch: true`.
  - `render_plan` then prints: "The branch is merged into origin/<base_ref> (squash merge). Its commits are not lost."
  - When `content_merged` is false, nothing changes: the commits are listed and `--confirm-unpushed` is needed.
- `factory clean` already runs `git fetch origin --prune`. `plan_delete` also runs `git fetch origin <base_ref>` before the check, so a direct `factory delete` is up to date too. A failed fetch is not an error: the check uses the last known `origin/<base_ref>`.

Tests (`tests/test_squash_merge.py`), in the temp repo with the local bare `origin` of `conftest.py`:

1. Branch squash-merged into `main`, remote branch deleted: dry run lists no commit, says the squash text, `delete_branch` is true. The real delete removes the local branch.
2. Same as 1, plus one local commit after the squash merge: that commit is listed, `needs_confirm` is true.
3. Branch merged with a merge commit: same result as today (merged, branch deleted).
4. Branch never pushed and never merged: same result as today (commits listed, branch kept).
5. Squash-merged branch, worktree removed by hand: `factory clean` reports `merged (squash)`.
6. Squash-merged branch, then a commit on `main` that changes the same lines: reported as not merged.

## Milestone 3: Artifact viewer

Behavior (`web/dashboard.html`):

- The modal box becomes a flex column with a maximum height of the window (`max-height: calc(100vh - 2rem)`).
- A title bar at the top holds the title and a Close button. It never scrolls away.
- The content area below scrolls (`overflow: auto`). The artifact `<pre>` sits in it.
- The artifact viewer opens with `{ dismissable: true }`:
  - Escape closes it.
  - A click on the dark backdrop, outside the box, closes it.
  - The Close button closes it.
- Other modals (forms):
  - A click outside never closes them.
  - Escape closes a form with no typed text.
  - Escape on a form with typed text shows an in-page question "Discard the typed text?" with "Discard" and "Keep editing". It does not use the browser `confirm()`.
  - "Typed text" means any `textarea` or text `input` in the modal whose value differs from its value when the modal opened.

Tests:

- `tests/test_dashboard_page.py`: the page HTML contains the dismissable option on the artifact viewer, the Escape handler, and the backdrop handler.
- Browser check, steps and results in `verification/software-factory/factory-fixes-artifact-viewer.md`: a server on a temp repo with the fake adapter, one task with a 3-line artifact and a 2000-line artifact. For each: the title bar stays visible, Escape closes, a click outside closes, Close closes. "Request changes" with typed text: a click outside does nothing, Escape asks.

## Milestone 4: Poll countdown and "Check now"

Behavior:

- Server:
  - `poll_loop` sets `server.next_poll = time.time() + interval` before each `sleep`.
  - `board.task_rows(ctx, next_poll=None)` adds to each row that waits on a done check: `next_check_at` (ISO, or null) and `last_check`.
  - `/api/tasks` passes `server.next_poll`.
  - New route `POST /api/tasks/<id>/check`: returns `{"job": <id>}` at once. The job runs `engine.check_task(ctx, tid)`.
- Engine:
  - `check_task(ctx, tid)` is the one-task check, used by the scheduled poll, `factory poll --task <id>` and the route.
    1. Take the lock `.factory/tasks/<id>/check.lock` without blocking. When it is taken, return `{"id": tid, "ended": false, "busy": true, "error": "A check is already running."}`.
    2. Inside the lock, reload the task. When it is no longer `waiting_external` on a step with a `done_check`, return "The task does not wait on a done check." and run nothing.
    3. Run the check. Save `last_check` in the task file: `{"at": <ISO>, "ended": <bool>, "output": <last 500 characters>}`.
    4. When it passed, call `end_wait` inside the lock. The wait ends once and one message is sent.
  - `poll(ctx)` calls `check_task` for each waiting task.
- CLI: `factory poll --task <id>` checks one task. Without `--task`, all waiting tasks. Note: `--task` is already a common option that selects a task. `poll` reads it as the task to check, and only the main repository is needed.
- Card, for `waiting_external` with a done check:
  - "Next check in m:ss", updated every second from `next_check_at`. At 0 it shows "Next check soon".
  - "Last check: <time>, <result>". The result is "still waiting: <last output line>" or "the wait ended".
  - "Check now": calls the route, then `waitJob`. While it runs, the button shows "Checking…" and is disabled. Then the card refreshes.
- A `paused` task shows no countdown and no button.

Tests (`tests/test_check_now.py`):

- `factory poll --task <id>` with a passing check: the wait ends, `last_check.ended` is true. With a failing check: still waiting, `last_check.output` holds the output.
- `/api/tasks` returns `next_check_at` when the server has a next poll time.
- Two threads run `check_task` on the same task at the same time, both checks passing: one `external_event` event, one `prompt_sent` event.
- One check from the CLI (subprocess) and one from a server job at the same time: one `external_event` event.
- "Check now" on a check that sleeps 5 seconds: the route answers in less than 1 second with a job. `/api/tasks` answers while the job runs. The job ends with the result.

## Milestone 5: Focus brings the terminal app to the front

Behavior:

- `session.focus(ctx, tid)` returns a result:
  - It runs the adapter focus first. A failure there raises, as today.
  - Then it reads `terminal_app` from `config.yaml` section `terminal`.
    - Missing: return `{"front": "ask"}`. Nothing else runs.
    - Empty: return `{"front": "off"}`.
    - Set, on macOS: run `open -a <terminal_app>`. Exit code 0 gives `{"front": "ok"}`. Otherwise `{"front": "failed", "message": ...}`.
    - Set, not on macOS: `{"front": "failed", "message": "Bringing the app to the front works only on macOS."}`.
- `factory terminal focus <id>` prints the result. For `ask`, it prints the command to save the app name.
- Dashboard "Focus":
  - `ask`: a small form "Which terminal app shows Herdr? (empty: never ask again)" with Save. Save calls `/api/config/set` (step `terminal`, key `terminal_app`), then focuses again.
  - `failed`: the card shows "Focused in Herdr. Could not bring <app> to the front: <message>".
- Menu "Focus a task" (`skills/software-factory/SKILL.md`): on `ask`, the orchestrator asks the user and saves the answer, then runs the focus again.
- The command to run is `open`, found on `PATH`, so tests stub it.

Tests (`tests/test_focus_front.py`), with the fake adapter and a stub `open` on `PATH` that logs its arguments:

- `terminal_app: Ghostty`: the fake adapter logs the focus, then the stub logs `-a Ghostty`.
- `terminal_app: ""`: the stub is not called, the result is `off`.
- Missing key: result `ask`, stub not called.
- Stub exits 1: result `failed`, the Herdr focus is still logged.
- The platform check is a function, so the test can force macOS.

## Milestone 6: Names from the ticket

Behavior at launch (`launch.py`):

- `ticket_base(value)`: the first match of `[A-Z][A-Z0-9]+-[0-9]+` in the value, in lowercase. None when there is no match.
- `plan_launch`: when no `--id`, and the inputs have a non-empty `ticket` with a key, the base is that key. Otherwise the description slug, as today. `unique_id` adds `-2`, `-3`.
- The worktree folder, the Herdr names and `--name` all come from the id. No other change.
- `factory launch --dry-run` already prints "Task id: ...".

Behavior after launch (new module `rename.py`):

- `engine.set_state` calls `rename.on_ticket_set(ctx, tid, old, new)` after saving, when the key is `ticket`, the old value has no Jira key (missing, empty, or a text like `none yet`), the new value has a Jira key, and the task has no `display_name`.
- Display name: the ticket key in lowercase, made unique among the live tasks (task folders not archived), against their ids and display names. Then `herdr_name` from milestone 1. When it equals the task id, nothing is renamed.
- Steps, each one independent. A failure is collected, never raised:
  1. Save `display_name` in the task file.
  2. When the task has a handle and the adapter supports `rename`: `adapter.rename(handle, name)`. Herdr: `agent rename <old agent> <name>`, `tab rename <tab> <name>` when the handle has a tab, `workspace rename <workspace> <name>` when the handle has a workspace. The handle saves the new agent name.
  3. Claude: save `claude_rename_pending: <name>`. The session that runs `factory state set` is working, so the rename is applied later (D9).
- `rename.apply_pending(ctx, task)`:
  - Runs only when `claude_rename_pending` is set and the task has a live handle.
  - Takes the lock `.factory/tasks/<id>/rename.lock` without blocking. When it is taken, it does nothing, so two callers never send `/rename` twice.
  - Inside the lock, reloads the task. When the field is still set, the session state is `idle` and no question box is open: types `/rename <name>` into the session, then clears the field and logs `claude_renamed`.
  - A failure leaves the field set, logs `rename_failed` and saves `rename_error`. It never fails the caller.
- Callers: the server poll loop, after each poll, for every task with the field. `/api/tasks`, for every task with the field, before it builds the rows.
- `session.resume` passes `--name <display name>` and clears `claude_rename_pending` in the same task update as the new handle.
  4. Log `task_renamed` with the new name and what was renamed. When a step failed, log `rename_failed` with the reason and save `rename_error`.
- `factory state set` never fails because of a rename. It prints a warning line when the rename failed.
- The worktree folder and the task id do not change.
- Display:
  - `board.task_row` adds `display_name` (the field, or the id) and `rename_error`.
  - `factory tasks` shows `<display name> (<id>)` when they differ.
  - The card title shows the display name, and the id below when it differs. The card shows `rename_error` in red.
- `adapters.base.OPTIONAL` gets `rename`. The fake adapter records `rename` calls.

Tests (`tests/test_ticket_names.py`):

- Launch with `ticket=HT-4549` gives the id `ht-4549`. A second launch gives `ht-4549-2`.
- Launch with `ticket=https://x.atlassian.net/browse/HT-4549` gives `ht-4549`.
- Launch with `ticket=none yet` gives the description slug.
- `factory state set ticket HT-4549` after launch, with the stubbed `herdr`: the stub log shows `agent rename`, `tab rename` and `workspace rename` with `ht-4549`. The handle agent is `ht-4549`. The id and the worktree path do not change. `claude_rename_pending` is `ht-4549`.
- Rename while the session is working: no `/rename` prompt, `claude_rename_pending` is `ht-4549`. Then the session is idle: `apply_pending` sends one `/rename ht-4549` and clears the field. A second call sends nothing.
- Rename while working, then resume: the resume passes `--name ht-4549` and clears the field.
- Launch with `ticket=none yet`, then `factory state set ticket HT-4549`: the task is renamed to `ht-4549`.
- A failing `herdr agent rename`: `factory state set` exits 0, the event `rename_failed` is logged, the row has `rename_error`.
- A second `factory state set ticket HT-1` does not rename again.

## Documentation

- README: one short entry per change, in the existing sections (Commands, Dashboard, Clean dialog, Troubleshooting, `.factory/config.yaml`, Events).
- `skills/software-factory/SKILL.md`: Focus asks `terminal_app` on `ask`. "Check waiting tasks" mentions `factory poll --task <id>`.
- Herdr allowlist in the README gains `herdr workspace rename`, `herdr tab rename`, `herdr agent rename`, and `open -a` for the focus. `.factory/claude-settings.json` allows only `factory` commands, so it does not change.

## Safety

- Tests use the fake adapter or the stubbed `herdr`. No real Herdr workspace, tab or agent is touched.
- Tests use temp repos only. No real task, worktree or branch is deleted.
- Nothing is pushed. `master` does not change. The spec and the plan are committed on `factory-fixes`.

## Out of scope

- Moving or renaming the worktree folder after launch.
- A data format version change.
- Renaming tasks for any key other than `ticket`.
