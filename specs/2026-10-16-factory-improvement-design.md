# Factory improvement: exclusive steps and "May wait for you"

Date: 2026-10-16
Source: `prompts/factory_improvment.md`. Full factory requirements: `prompts/factory_skill_creation.md`.
Code: `software-factory/`. Baseline: 478 tests pass (`uv run --with pytest --with pyyaml pytest -q tests`).

## 1. Intent

- Two tasks must never use one device at the same time. Today a lock written inside the step depends on the agent, and the agent forgets it. The factory must enforce it.
- A task session that asks a question in plain text and forgets `factory block` stays `active` and green. The user gets no signal. The factory must detect the turn end and tell the user.

## 2. Goals, non-goals, anti-goals

Goals:

- G1. A step manifest field `exclusive: <name>`. The factory lets one task at a time run a step with this name.
- G2. Two Claude Code hooks on task sessions. A turn end while the task is `active` sets "May wait for you" on the card and sends one notification.

Non-goals:

- No change to the library of the user (`NextoryCustomSkills`). Moving `nx-reproduce-bug` and `nx-verify-fix` to `exclusive: android-emulator` is a later, separate change.
- No new terminal adapter. No change of the data format version (see 5.4).
- `factory block` stays the main way a step says it waits. "May wait for you" is only a safety net.

Anti-goals (failure even if it works):

- A1. Two tasks hold the same resource at the same time, even for a moment, even with two processes.
- A2. A hook blocks, slows or prints text into a Claude session. A hook error breaks a session.
- A3. A task waits for a resource forever after a release that was missed.
- A4. "Mark done" or "Check now" ends a resource wait without running the step.
- A5. Tests touch a real `.factory/`, the user's library, or a real Herdr workspace, tab or agent.

## 3. Exclusive steps

### 3.1 Manifest field

- `exclusive: <name>`. The name matches `[a-z][a-z0-9_-]*`. Steps with the same name share one resource, at every level (local, generic, built-in, catalog).
- `step_format.validate` checks it, so `factory pipeline check`, the registry load and the step editor all report a bad name as an error.
- `exclusive` on a `group` step is an error: "`exclusive` applies only to `ai` and `command` steps. Set it on the child steps." (my call: a group has no single "current step".)
- `exclusive` joins `FIELD_ORDER` after `wait_external`.
- The step editor form has an `exclusive` text field. The detail panel shows it with the other manifest fields. The README "Step manifest fields" lists it.
- The `ai` and `command` footer of `factory next` gets one line for an exclusive step: "This step uses `<name>`. Only one task at a time runs it. Before a long wait for the user, free it with `factory exclusive release <name>`. Take it again with `factory exclusive acquire <name>`."
- A step without `exclusive` behaves as today.

### 3.2 Resource state

- New module `lib/factory/exclusive.py`.
- One file per resource name: `.factory/exclusive/<name>.json`, changed only under its lock file `.factory/exclusive/<name>.json.lock` (`fsio.update_json`, `flock`). This lock works across processes. Every check and change of a resource runs under it.
- Content:
  - `holder`: task id or null
  - `since`: the time the holder got it
  - `queue`: ordered list of `{task, since, mode}`. `mode` is `next` (waited at the start of the step) or `acquire` (waited in the middle of the step).
- The task state gets the optional field `exclusive_wait`: `{name, mode}` while the task is in a queue. It also gets the optional field `exclusive_released`: the name, after the task released it in the middle of the step. Both are cleared when the task leaves the step.
- Scope: one repository. The requirements put the lock in `.factory/`. Two repositories that share one emulator do not see each other's resources. This is a known limit, not handled in this build.
- Lock order: resource lock, then task lock. Code never takes a resource lock inside a task update, so there is no deadlock.

### 3.3 Hold and release

- A task holds the resource while its current step has that `exclusive` name and has started.
- `factory next` on a step with `exclusive` (under the resource lock):
  - The task is the holder: start the step as today.
  - No holder, and no waiting task that is not paused: the task becomes the holder, then the step starts.
  - Otherwise: the step does not start. The task joins the queue once (a second `next` does not add it again). Status `waiting_external`, reason "Waiting for <name>, used by <holder>". It prints "The step `<id>` needs `<name>`, now used by task `<holder>`. The factory starts this task when it is free. End your turn." It logs `exclusive_wait` (`name`, `holder`).
  - When the holder is null because only paused tasks wait, the new task takes it. The reason then names "a paused task" only if needed (my call: the paused tasks do not block).
- `factory next` on a started step that the task released with `factory exclusive release`: prints the step text with one more line, "You released `<name>`. Run `factory exclusive acquire <name>` before you use it again." It does not take the resource.
- `factory next` on a started step whose resource the task lost by `release --force`: same as above. The forced release sets `exclusive_released` on the holder (my call: the holder's session must ask again, never use the device silently).
- Leaving the step releases the resource and removes the task from the queue of that step: `factory done`, `factory skip`, `factory goto`, a loop jump, the end of the pipeline, `factory delete`.
  - Rule used for all of them: after the move, if the new current step has the same `exclusive` name, the task keeps the resource. Otherwise it releases it. (my call, from "a loop jump to a step without the name": two steps in a row on the same device keep it, so no other task can change the device between them.)
  - One function, `exclusive.sync(ctx, tid)`, runs after each of these moves. It compares the resources the task holds or waits for with the `exclusive` name of its current step.
- A paused task keeps the resource. Its card says "Keeps `<name>` while paused".
- `factory exclusive release <name>`: the task must be the holder. It frees the resource, sets `exclusive_released`, keeps the step as the current step, logs `exclusive_release`, then runs the handover.
- `factory exclusive acquire <name>`: the current step must have that name and must have started.
  - The task holds it already: prints "You hold `<name>`."
  - Free: the task becomes the holder, `exclusive_released` is cleared, logs `exclusive_acquire`, prints "`<name>` is yours. Continue the step."
  - Held by another task: joins the queue with mode `acquire`, status `waiting_external` with the same reason as `next`, logs `exclusive_wait`, prints "`<name>` is used by task `<holder>`. The factory sends you a message when it is free. End your turn."
- `factory exclusive release <name> --force`: frees the resource whatever task holds it.
  - Logs `exclusive_forced` (`name`, `holder`, `by`) on the holder, and on the task that asked when there is one: `--task <id>`, or the waiting task of the dashboard card.
  - Sets `exclusive_released` on the holder, then runs the handover.
  - The menu action "Release a shared resource" and the "Release" button on a waiting card call it. Both ask for confirmation first, and show the holder and its status.
- `factory exclusive status [--json]`: one line per resource name used by a step or present in `.factory/exclusive/`: the holder (or free), and the waiting tasks in order, with their status.

### 3.4 Handover

- `exclusive.handover(ctx, name)` runs after every release, under the resource lock:
  - It removes from the queue the tasks that no longer exist, are archived, finished, or are no longer on a step with this name.
  - It picks the first queued task that is not paused. It becomes the holder at once and leaves the queue. Paused tasks keep their place.
  - Inside the same lock it sets that task to `active`, clears `exclusive_wait` (and `exclusive_released` for mode `acquire`), and for mode `next` keeps the step not started, so `factory next` starts it.
- After the lock, it logs `exclusive_start` on that task and sends the message with `session.deliver`:
  - mode `next`: "`<name>` is yours now. Run `factory next`."
  - mode `acquire`: "`<name>` is yours now. Continue the step."
  - `session.deliver` resumes the session first when it is gone, as for the end of an external wait. A delivery error is logged (`prompt_failed`) and does not undo the handover.
- Resume of a paused waiting task runs the handover of its resource, so it gets the resource at once when it is free. A paused holder resumes as holder.
- `factory delete` removes the task from every queue and releases what it holds, then runs the handover.
- `factory poll` runs `exclusive.recheck(ctx)` for every resource, also when no task waits on a done check. It releases a holder that no longer exists, is archived or finished, or is no longer on a step with this name and is not paused. Then it runs the handover. This covers a crash between a release and its handover. The server poll loop runs it too.

### 3.5 Waiting tasks and the existing external wait

- A task with `exclusive_wait` is `waiting_external`, but it is not an external wait:
  - `engine.waiting_step` and `engine.is_waiting_check` ignore it, so `factory poll` never runs the step `done_check`, and the server does not stay alive for it.
  - `factory external-done` refuses it: "Task <id> waits for `<name>`, not for an external event. Release it with `factory exclusive release <name> --force` if the holder is stuck."
  - `factory wait` is not involved.
- `factory skip` and `factory goto` still work on a waiting task, after user approval. They remove it from the queue.

### 3.6 Display

- `factory status` adds one line: "Exclusive: `<name>`, held by this task", "Exclusive: `<name>`, released", or "Exclusive: waiting for `<name>`, used by `<holder>`".
- The task row of `factory tasks --json` and `/api/tasks` gets `exclusive`: `{name, holder, holds, waiting, released}`, or null.
- Card of a waiting task: the resource and the holder, and a "Release" button (with confirmation). No "Mark done", no "Check now".
- Card of the holder: "Uses `<name>`", or "Keeps `<name>` while paused".
- New API route `POST /api/exclusive/<name>/release` with `{task}`. It calls the same function as the CLI.

### 3.7 Events

`exclusive_wait`, `exclusive_start`, `exclusive_release`, `exclusive_acquire`, `exclusive_forced`. Each has `name`. The README Events section lists them.

## 4. "May wait for you"

### 4.1 Hooks in `.factory/claude-settings.json`

- The file gets, next to `permissions`:
  ```json
  "hooks": {
    "Stop": [{"hooks": [{"type": "command", "command": "'<link dir>/factory' hook stop", "timeout": 10}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "'<link dir>/factory' hook prompt", "timeout": 10}]}]
  }
  ```
  The command uses the absolute path of the `factory` link from `init.ensure_link`, so it works when the hook shell has no `~/.local/bin` in PATH (my call).
- `init.ensure_settings(ctx)` adds what is missing, without removing other rules or other hooks:
  - Missing file: write the permission rules and both hooks.
  - Existing file: add the two permission rules if missing, and each hook if no handler of that event has a command ending with `factory hook stop` / `factory hook prompt`. A second run adds nothing.
- `factory init` calls it (replaces `write_new` for this file). `factory version check` calls it when the repository is initialized and its version is the same, and reports `settings_updated`.
- The data format version stays 2: the new fields are optional, and old data stays valid. No migration. (The prompt says to ask the user first if a version change is needed. It is not.)

### 4.2 `factory hook stop` and `factory hook prompt`

- New module `lib/factory/attention.py`. `hook` is in `NO_VERSION_CHECK`; the command does its own checks.
- They read the hook input JSON on stdin. They find the task whose `session_id` equals the input `session_id`, among the tasks in `.factory/tasks/*/task.json` (archived tasks are in `tasks/archive/`, so they are not seen).
- No task, empty stdin, invalid JSON, no `.factory/`, or another data version: exit 0, no change.
- Always exit 0 and print nothing on stdout or stderr. `UserPromptSubmit` stdout would go into the Claude context, so this matters.
- Errors: logged as `hook_failed` (`hook`, `error`) on the task when the task is known. Otherwise nothing is written (my call: there is no task log to write to).

### 4.3 `factory hook stop`

- Only when the task status is `active`. `blocked`, `awaiting_approval`, `waiting_external`, `paused`, `finished`: no change.
- No change when the hook input lists background work (`background_tasks` not empty): the session ended its turn but still works, and starts a new turn by itself (my call).
- Sets the optional task field `attention`: `{at, message}`.
  - `message`: `last_assistant_message` of the hook input. When it is missing, the text of the last assistant entry of `transcript_path`, best effort. It keeps the last 12 lines and at most 2000 characters. Null when nothing is found.
- Logs `attention` (`message`: its first line).
- Notification, when the adapter supports `notify`: "<display name> may wait for you: <first line of the message>". Without a message: "<display name> may wait for you."
  - The adapter gets an optional capability `focused`. The Herdr adapter reads `focused` from `herdr agent get` (checked on 2026-10-16 with Herdr 0.9.3: among 6 agents in several tabs and workspaces, only the pane the user looked at had `"focused": true`, so focus is global, not per tab).
  - A focused pane does not mean the user is looking: focus stays on the last pane, and the user may be in another app (user decision N1).
  - Task agent not focused: notify at once.
  - Task agent focused, no `focused` capability, or the focus check fails: the 60 second rule. The hook starts a detached process `factory hook notify-later <id> <at>` (`start_new_session`, no stdin, stdout or stderr), then ends at once. That process sleeps 60 seconds (`FACTORY_ATTENTION_DELAY` overrides it in tests), loads the task, and notifies only when `attention.at` is still the same.
  - The card shows "May wait for you" at once in both cases.

### 4.4 Clearing `attention`

- `factory hook prompt` clears it.
- Any status change clears it: `state.update` compares the status before and after the change, removes `attention` when the status changed, and logs `attention_cleared` (`reason: status`). This covers `factory block`, `factory wait`, `factory done` to finish, approve, request changes, pause, resume, and the exclusive wait.
- A successful `session.deliver` or `session.send_prompt` clears it (`reason: prompt`), so the dashboard and the menu Send prompt clear it even when the hook does not run.
- `attention_cleared` is logged once, only when `attention` was set.

### 4.5 Display

- The task row gets `attention`: `{at, message}` or null.
- The card of a task with `attention`: "May wait for you", in the blocked color (the card uses the blocked background), the time since the turn ended, and the message as plain text.
- `factory tasks` sorts tasks with `attention` together with `blocked` (first), then `awaiting_approval`. The text line shows "may wait for you" and the first line of the message.
- The orchestrator skill: "Show tasks" and the lists of tasks that need the user include the tasks with `attention`.

## 5. Other changes

### 5.1 CLI

- `factory exclusive status`, `factory exclusive release <name> [--force]`, `factory exclusive acquire <name>`.
- `factory hook stop`, `factory hook prompt`, `factory hook notify-later <id> <at>`.

### 5.2 Menu and orchestrator skill

- New menu action in the Tasks group: "Release a shared resource" (`exclusive-release`). The skill runs `factory exclusive status --json`, lists held resources with their holder and waiting tasks, asks which one, shows the holder and its status, asks for confirmation, then runs `factory exclusive release <name> --force`.

### 5.3 Docs

- README: the `exclusive` field, the exclusive commands, the "Release" button and card lines, the menu action, the hooks and "May wait for you", the new events, the `hook` commands.
- `factory-authoring` skill: the `exclusive` field in the manifest reference, with an example and the release and acquire commands.

### 5.4 Data format

- No version change. New optional fields: step `exclusive`, task `attention`, `exclusive_wait`, `exclusive_released`, files `.factory/exclusive/*.json`, and the hooks in `claude-settings.json` (added by init and the version check).

## 6. Tests

All tests use temp repos under `verification/software-factory/work/` and the fake adapter.

Exclusive steps (milestone 1):

1. Two tasks reach steps with the same name: the second waits, then starts when the first runs `factory done`, with one message to its session.
2. Three tasks get the resource in the order they started to wait.
3. After a release, a third task runs `factory next` before the waiting task: the third waits, the first waiting task keeps the resource.
4. A task that waited after `factory exclusive acquire` gets "Continue the step", not "Run `factory next`".
5. The first waiting task is paused: the resource goes to the second. After the resume, the first gets the next release. When the resource is free at the resume, it gets it at once. A deleted waiting task leaves the queue.
6. Two `factory next` at the same time, in two processes: exactly one task holds the resource.
7. `factory skip`, `factory goto`, a loop jump and `factory delete` of the holder release the resource.
8. A paused holder keeps the resource.
9. Two different names do not block each other.
10. `factory exclusive release` in the middle of the step: another task gets the resource, the first stays in its step. Its `factory exclusive acquire` then waits until the resource is free again.
11. `release --force` frees a resource held by a blocked task, logs `exclusive_forced` on both tasks, and starts the next waiting task.
12. A waiting task: `factory external-done` refuses it, its row has no done check (no "Mark done", no "Check now" in the page logic), and `factory poll` does not run its `done_check`.
13. `factory poll` hands a free resource to a waiting task after a missed handover.
14. `exclusive` name check: bad name and group step are errors; `factory pipeline check` passes with a good name; the step API saves and returns the field.
15. A step without `exclusive` behaves as before (the existing suite).

"May wait for you" (milestone 2):

1. `factory hook stop` with the session id of an `active` task: `attention` is set with the message, and one notification is sent (fake adapter, not focused).
2. The same for a `blocked` or `waiting_external` task: no change.
3. `factory hook prompt` clears `attention`. So do `factory block` and the dashboard Send prompt. Each logs `attention_cleared`.
4. Turn end while the task tab is focused (fake adapter `focused`): `attention` set, no notification at once, one notification after the delay when `attention` is still set, none when a prompt arrives during the delay.
5. Unknown session id, empty stdin, invalid JSON: exit 0, no output, no change.
6. 60 second rule, short delay: `attention` cleared during the delay gives no notification; still set gives one. The hook itself returns in less than the delay.
7. Init on an existing `claude-settings.json` with extra rules: the rules stay, the hooks are added once, a second init and a version check add nothing.
8. The task list puts a task with `attention` with the blocked tasks; the row has `attention`.
9. Real check, script in `verification/software-factory/`: a temp repo with the factory and the fake adapter, a launched test task, then a real headless Claude run (`claude -p` with the task `--session-id` and `--settings`) in the task worktree, asked to ask a question in plain text. Then the task has `attention`. It never uses a session or a Herdr workspace of the user.

## 7. Left to the builder

- Function names and the split between `exclusive.py`, `attention.py` and `engine.py`.
- The exact card layout and wording of short labels in the dashboard, within the texts above.
- The transcript parsing fallback, as long as it never fails the hook.
