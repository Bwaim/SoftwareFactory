# Software factory: names, focus, artifact viewer, poll and clean fixes

## Problem

Daily use of the factory shows six problems:

1. The task id, the Herdr workspace, tab and agent, the worktree folder and the Claude session are named from the description, for example `library-following-opening-the`. The Jira ticket key is easier to find, for example `ht-4549`. A ticket that is known only after the launch never renames anything.
2. "Focus" on a card focuses the agent inside Herdr, but the terminal app that shows Herdr stays behind the browser.
3. An artifact opened from a card closes only with its Close button. For a long file, the user must scroll to the bottom to reach it. Escape and a click outside do nothing.
4. A name longer than 32 characters makes Herdr fail. Real error, from a step that names its tab `<task id>-review-mr`:
   `herdr agent start failed: invalid_agent_name — agent name must start with a lowercase letter and contain only lowercase letters, digits, '-' or '_' (1-32 characters)`
   The tab name was `library-following-opening-the-review-mr`, 39 characters.
5. A card that waits on a `done_check` shows no time to the next check, and the user cannot run the check now.
6. "Clean" and `factory delete` report that commits will be lost, when the branch was merged with a squash merge. The commits are not lost: their content is in `origin/<base_ref>`, in one squashed commit.

## Solution

Fix the six problems in the existing factory. Each fix is a milestone.

## Variables

- `PROJECT_ROOT: /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory`
- `SPEC_DIR: <PROJECT_ROOT>/specs/`
    - Save your own spec here.
- `PLAN_DIR: <PROJECT_ROOT>/plans/`
    - Save your own plan here.
- `YOUR_WORKING_DIR: <PROJECT_ROOT>/software-factory/`
    - The existing factory. Save your work here.
- `VERIFICATION_DIR: <PROJECT_ROOT>/verification/software-factory/`
    - Save your verification artifacts here.
- `MAIN_PROMPT: <PROJECT_ROOT>/prompts/factory_skill_creation.md`
    - The full factory requirements. It already contains these fixes. Read it for context.

## Workflow

1. Read. Read `MAIN_PROMPT`, `YOUR_WORKING_DIR/README.md` and the factory code, so the fixes follow the existing design, modules and tests.
2. Brainstorm. Use the `/superpowers:brainstorming` skill to create a specification file from these requirements. Save the specification file in `SPEC_DIR/` before writing the plan.
3. Ask validation. Ask the user to validate the specification file.
4. Plan. After specification validation, use the `/superpowers:writing-plans` skill to create an implementation plan from the specification file. Save the plan file in `PLAN_DIR/` before writing implementation code. Split the plan into these milestones, in this order:
    1. Herdr name limit
    2. Clean after a squash merge
    3. Artifact viewer
    4. Poll countdown and "Check now"
    5. Focus brings the terminal app to the front
    6. Names from the ticket
5. Ask validation. Ask the user to validate the plan file.
6. Build. After plan validation, create the branch `factory-fixes` from `master`. Use the `/superpowers:subagent-driven-development` skill to implement the plan inside `YOUR_WORKING_DIR`, one milestone at a time. Run the full test suite of the factory after each milestone, fix the failures, and commit before starting the next milestone. Do not skip straight from this prompt to implementation.
7. Verify. Check every item in Definition Of Done, fix failures, and rerun the affected checks. Keep final verification artifacts inside `VERIFICATION_DIR` and report actual results and any remaining blockers.

## Definition Of Done

### Workflow Complete

- Your completed implementation plan exists under `PLAN_DIR/`.
    - It was written before implementation, and the build followed its build step.
- The work is on the branch `factory-fixes`. `master` is unchanged.
- Every existing test still passes. Each milestone adds its own tests.
- The README describes each change.

### Facts

These facts were checked on 2026-10-16. Check them again during the build.

- Herdr 0.9.3 has `herdr workspace rename`, `herdr tab rename` and `herdr agent rename`. Read their help for the syntax.
- The Herdr adapter names the agent with the name given to `start-session`, and uses the same text as the label of the workspace or the tab (`lib/factory/adapters/herdr.py`).
- The task id comes from `slugify(description)` in `lib/factory/launch.py`, cut at 29 characters, plus a `-2`, `-3` suffix when taken.
- The ticket of a task is the task state key `ticket` (`lib/factory/board.py`). The Nextory pipelines have a `ticket` input.
- Claude Code 2.1.301 has `--name <name>`, the display name of the session. Check whether a live session can be renamed, for example with a `/rename` command.
- The dashboard opens an artifact with `openModal(...)` and a Close button in a footer, after the whole text (`lib/factory/web/dashboard.html`).
- The server runs `engine.poll` in `poll_loop`, after a `sleep` of `poll_minutes` (`lib/factory/server.py`). The time of the next poll is not saved. `factory poll` checks every waiting task. It has no option for one task.
- `factory delete` lists commits as "not pushed" with `git log <upstream>..HEAD`. The upstream is `origin/<base_ref>` when `origin/<branch>` no longer exists (`lib/factory/delete.py`). After a squash merge, the branch commits are not ancestors of `origin/<base_ref>`, so they are listed as lost. The same check keeps the local branch.
- Git is 2.55. `git merge-tree --write-tree` is available (git 2.38 and later).
- Inside Herdr, `TERM_PROGRAM` is `herdr`. It does not name the terminal app that shows Herdr.

### 1. Herdr name limit

- Herdr accepts a name that matches `^[a-z][a-z0-9_-]{0,31}$`.
- `factory terminal start-session` accepts any name. The Herdr adapter turns it into a valid Herdr name:
    - Lowercase. Each run of other characters becomes `-`. A name that does not start with a letter gets the prefix `t-`.
    - When the result is longer than 32 characters: keep the start, and end with `-` plus 4 characters of a hash of the full name. The result is 32 characters at most. Two different long names give two different results.
    - A name that is already valid does not change.
- The handle saves the real Herdr name. Every later call uses the handle, never the requested name.
- `start-session` prints the handle, so a step can show the real tab name to the user.
- Tests:
    - `library-following-opening-the-review-mr` gives a valid name of at most 32 characters, and the session starts with the fake adapter and with a stubbed `herdr`.
    - Two names that differ only after character 32 give two different names.
    - `HT-4549 Fix` gives `ht-4549-fix`. `4549` gives `t-4549`.

### 2. Clean after a squash merge

- A commit of the task branch counts as merged when its content is already in `origin/<base_ref>`:
    - Run `git merge-tree --write-tree origin/<base_ref> refs/heads/<branch>` in the main repository. `factory clean` checks tasks from the main repository, and the worktree may already be gone. Use the worktree `HEAD` only for a task without a branch.
    - When it succeeds and the tree it prints equals the tree of `origin/<base_ref>`, the branch content is already in `origin/<base_ref>`. Merging the branch would change nothing.
    - The check errs on the safe side. When `main` changed the same lines after the squash merge, `merge-tree` gives another tree or a conflict. The task is then reported as not merged, and the delete asks for `--confirm-unpushed`. Nothing is lost by mistake.
- `factory delete --dry-run`:
    - When the branch content is already in `origin/<base_ref>`, it lists no commit as lost. It says: "The branch is merged into origin/<base_ref> (squash merge). Its commits are not lost."
    - It deletes the local branch in that case, like a normal merge.
    - When at least one change of the branch is not in `origin/<base_ref>`, the check is the same as today: it lists the commits and asks for `--confirm-unpushed`.
- `factory clean` shows the same reason for such a task: "merged (squash)".
- Run `git fetch origin <base_ref>` before the check, as `factory clean` does now.
- Tests, in a temp repo with a local bare `origin`:
    - A branch squash-merged into `main`, then the remote branch deleted: no lost commit, the local branch is deleted.
    - The same, plus one local commit made after the squash merge: that commit is listed as lost.
    - A branch merged with a merge commit: same result as today.
    - A branch never pushed and never merged: same result as today.
    - A squash-merged branch whose worktree is already removed: `factory clean` reports "merged (squash)".
    - A squash-merged branch, then a commit on `main` that changes the same lines: reported as not merged.

### 3. Artifact viewer

- The artifact viewer closes with:
    - The Escape key
    - A click outside the viewer
    - The Close button
- The title bar of the viewer, with its Close button, always stays visible. The text scrolls inside the viewer. The user never scrolls to the bottom to close it.
- Only the viewers that show a file close on Escape or on a click outside. A form, for example "Request changes", never closes on a click outside, so typed text is never lost. On Escape, a form with typed text asks before it closes.
- Tests: the dashboard page tests, or a browser check with the steps written in `VERIFICATION_DIR`, for a short and a long artifact.

### 4. Poll countdown and "Check now"

- The server saves the time of its next poll before each `sleep` of `poll_loop`. The tasks API returns it.
- `factory poll --task <id>` runs the `done_check` of one waiting task. Without `--task`, it checks every waiting task, as today.
- After each check, scheduled or manual, the factory saves the result in the task state: the time, whether the wait ended, and the last lines of the check output.
- A card of a task that is `waiting_external` on a step with a `done_check` shows:
    - "Next check in <m:ss>". The countdown updates every second in the page, from the time the API returns.
    - The last check: its time and its result, for example "still waiting: CodeRabbit review pending".
    - A "Check now" button. It calls the API route of `factory poll --task <id>` as a background job, like Pause does with `start_job` and `waitJob`, so the page never freezes. While the check runs, the button shows "Checking…" and is disabled. Then the card shows the result and refreshes. When the check ends the wait, the task moves on as after a scheduled poll.
- A `paused` task shows no countdown and no "Check now".
- Only one check of a task runs at a time, scheduled or manual. A second check of the same task waits for the first, or returns "A check is already running". After a wait has ended, a check of that task does nothing. So the wait ends once, and the session gets "The external event happened" once.
- The lock works across processes, because checks start from the dashboard server and from the CLI (`factory poll`, the menu action "Check waiting tasks"). Use for example one lock file per task in the task folder. A lock inside the server process only is not enough.
- Tests:
    - `factory poll --task` on a waiting task whose check passes, and on one whose check fails. The result is saved in the task state.
    - The API returns the next poll time.
    - Two checks of the same task at the same time, both passing: the wait ends once, and one message is delivered.
    - The same with one check from the CLI and one from the server: the wait ends once.
    - "Check now" on a check that takes 5 seconds: the API answers at once with a job, and the page stays usable.

### 5. Focus brings the terminal app to the front

- "Focus", on a card or in the menu, still runs `factory terminal focus`. After it, the factory brings the terminal app that shows Herdr to the front.
- The app name is the config key `terminal_app`, for example `Ghostty` or `iTerm`. It is asked on first use, like `ide_command`.
- On macOS, the factory runs `open -a <terminal_app>`. On another system, or when the command fails, the focus inside Herdr still works, and the dashboard shows that the app could not be brought to the front.
- When the user leaves `terminal_app` empty, the factory does not ask again and only focuses inside Herdr.
- Tests: with a stubbed `open`, the call is made with the configured app after the Herdr focus, and it is skipped when `terminal_app` is empty.

### 6. Names from the ticket

- At launch:
    - When the pipeline inputs have `ticket` with a value, the base of the task id is the first Jira key found in that value (`[A-Z][A-Z0-9]+-[0-9]+`), in lowercase, for example `ht-4549`. The value can be a key, a URL or a text like "HT-4549 Fix the list". When it has no key, the base is the slug of the description, as today.
    - The `-2`, `-3` suffix still applies when the id is taken.
    - So the worktree folder, the Herdr workspace, tab and agent, and the Claude session name are all named with the ticket.
    - `factory launch --dry-run` shows the id.
- After launch, when the task state key `ticket` gets a value for the first time, for example with `factory state set ticket HT-4549`:
    - The task id does not change. The task folder, the event log and the archive keep the id.
    - The task gets a display name: the first Jira key of the value, in lowercase, made unique among the live tasks. It follows the name rule of milestone 1.
    - The Herdr agent, the tab and the workspace that the task owns are renamed to the display name. The handle saves the new agent name.
    - The Claude session gets the display name: live, only when Claude Code supports it, the session is idle, and no question box is open. Otherwise at the next resume, with `--name`.
    - The worktree folder is not moved. A running session works in that folder, and some task keys, for example `repro_flow`, save absolute paths inside it. The dashboard and `factory tasks` show the display name, and the id when it differs.
    - A rename that fails does not fail `factory state set`. It logs `rename_failed` with the reason, and the card shows it.
- The display name is an optional field of the task state. A task without it uses its id. Existing tasks keep working without a migration. If you find that the data format version must change, ask the user first.
- Tests: a launch with `ticket=HT-4549` gives the id `ht-4549`, and a second one gives `ht-4549-2`. A launch with `ticket=https://x.atlassian.net/browse/HT-4549` also gives `ht-4549`. A ticket value without a key gives the description slug. A working session is not renamed live. A `factory state set ticket` after launch renames the Herdr names with a stubbed `herdr` and keeps the id and the worktree path.

## How You're Graded

- You'll be graded on a continuous basis based on every completed bullet in the Definition Of Done.
- Every step of Workflow must be fully accomplished: plan, build and verify.
- Instant failure if you write project deliverables outside `YOUR_WORKING_DIR`, with the exception of `SPEC_DIR`, `PLAN_DIR` and `VERIFICATION_DIR`.
- Instant failure if you change `master`, or push.
- Instant failure if you rename, close or start a real Herdr workspace, tab or agent of the user. Tests use the fake adapter or a stubbed `herdr`.
- Instant failure if you delete a real task, worktree or branch of the user.
- Instant failure if you read any part of any file inside `<PROJECT_ROOT>/specs/*` that isn't your own spec.
- Running tools outside these directories is allowed. Temporary files and tool-managed runtime data (caches, logs, browser profiles, updater logs) may use their normal locations and are not grading failures.
- If you find you've mistakenly caused a failure, stop immediately and report your failure.
