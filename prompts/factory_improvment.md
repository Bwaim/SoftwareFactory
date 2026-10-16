# Software factory: exclusive steps and "May wait for you"

## Problem

1. Some steps use a resource that only one task can use at a time, for example the Android emulator in the Nextory steps `nx-reproduce-bug` and `nx-verify-fix`. Today two tasks can run such steps at the same time, and they break each other's work. A lock written in the steps depends on the agent: the agent sometimes forgets to take it.
2. The factory knows that a task waits for the user only when the session runs `factory block`. A session that asks a question in plain text and ends its turn often skips it. Then the task stays `active`, the card stays green, and the user gets no notification. The task waits for nothing visible.

## Solution

Add two features to the existing factory:

- Exclusive steps: a step manifest can name a resource with `exclusive: <name>`. The factory lets only one task at a time run a step with that name. A second task waits, and the factory starts it when the resource is free.
- "May wait for you": the factory adds Claude Code hooks to the task sessions. When a session ends its turn while its task is `active`, the card shows "May wait for you" with the last message of the session, and the user gets one notification.

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
    - The full factory requirements. It already contains these two features. Read it for context.

## Workflow

1. Read. Read `MAIN_PROMPT`, `YOUR_WORKING_DIR/README.md` and the factory code, so the features follow the existing design, modules and tests.
2. Brainstorm. Use the `/superpowers:brainstorming` skill to create a specification file from these requirements. Save the specification file in `SPEC_DIR/` before writing the plan.
3. Ask validation. Ask the user to validate the specification file.
4. Plan. After specification validation, use the `/superpowers:writing-plans` skill to create an implementation plan from the specification file. Save the plan file in `PLAN_DIR/` before writing implementation code. Split the plan into these milestones, in this order:
    1. Exclusive steps
    2. "May wait for you"
5. Ask validation. Ask the user to validate the plan file.
6. Build. After plan validation, create the branch `factory-improvement` from `master`. Save `git rev-parse master` first, to check at the end that `master` did not change. Use the `/superpowers:subagent-driven-development` skill to implement the plan inside `YOUR_WORKING_DIR`, one milestone at a time. Run the full test suite of the factory after each milestone, fix the failures, and commit before starting the next milestone. Do not skip straight from this prompt to implementation.
7. Verify. Check every item in Definition Of Done, fix failures, and rerun the affected checks. Keep final verification artifacts inside `VERIFICATION_DIR` and report actual results and any remaining blockers.

## Definition Of Done

### Workflow Complete

- Your completed implementation plan exists under `PLAN_DIR/`.
    - It was written before implementation, and the build followed its build step.
- The work is on the branch `factory-improvement`. `master` is unchanged.
- Every existing test still passes. Each milestone adds its own tests.
- The README describes both features. The authoring skill (`factory-authoring`) describes `exclusive`.

### Facts

These facts were checked on 2026-10-16. Check them again during the build.

- A task session asks the user in plain text, never with the `AskUserQuestion` tool, then ends its turn (`MAIN_PROMPT`, Task execution).
- Every step prompt tells the session to run `factory block "<question>"` when it cannot continue without the user (`lib/factory/render.py`). Sessions often skip it.
- The Herdr states of a session seen on 2026-10-16 are `idle` and `working`. A session that waits on a plain text question is `idle`, like a session that has nothing to do.
- Init writes `.factory/claude-settings.json` only when it is missing (`lib/factory/init.py`, `write_new`). Today it holds only the permission rules for `factory`. Every task session starts with `--settings <main>/.factory/claude-settings.json` (`lib/factory/session.py`).
- The task state saves the Claude session id. A resume uses `--resume <session id>`, so the id stays the same for the whole task.
- The library lock `nx-emulator-lock.sh` exists (`NextoryCustomSkills/prompts/step_fixes.md`). Once `exclusive` is built, `nx-reproduce-bug` and `nx-verify-fix` can move to `exclusive: android-emulator`. That is a separate change in the library. Do not change the library.
- The library lock releases the emulator in the middle of `nx-reproduce-bug`, before a wait for the user that can take hours, and takes it again for new runs. It also has `release --force` for a holder that forgot to release.
- A `waiting_external` task on a step without a `done_check` shows the "Mark done" button (`factory external-done`).

### 1. Exclusive steps

- A step manifest can have `exclusive: <name>`, for example `exclusive: android-emulator`. The name matches `[a-z][a-z0-9_-]*`. Steps with the same name share one resource, at every level: local, generic and catalog.
- A task holds the resource while its current step has that `exclusive` name and has started. It releases it when the task leaves that step: `factory done`, `factory skip`, `factory goto`, a loop jump to a step without the name, the end of the pipeline, or `factory delete`.
    - A paused task keeps the resource, because the device keeps its state. Its card says so.
- A step can free the resource in the middle and take it again:
    - `factory exclusive release <name>` frees it early, for example before a long wait for the user. The step stays the current step. Logs `exclusive_release`.
    - `factory exclusive acquire <name>` takes it again. When another task holds it, the task waits exactly as with `factory next`, and the message tells the session to end its turn. Logs `exclusive_acquire`.
    - Leaving the step still releases the resource, when the task holds it.
- `factory next` on a step whose resource another task holds:
    - It does not start the step.
    - It sets the task to `waiting_external`, with the reason "Waiting for <name>, used by <task>".
    - It prints: "The step `<id>` needs `<name>`, now used by task `<task>`. The factory starts this task when it is free. End your turn."
    - It logs `exclusive_wait`.
- `factory exclusive release <name> --force` frees the resource whatever task holds it, for example when the holder is blocked for days or its session crashed in the step. The menu has an action for it, and the card of a waiting task has a "Release" button. Both ask for confirmation first. It logs `exclusive_forced` on the holder and on the task that asked, and then starts the next waiting task.
- `factory exclusive status` lists each resource, its holder, and the waiting tasks in order.
- When a task releases a resource, the factory gives it directly to the waiting task that has waited the longest, under the resource lock. That task becomes the holder at once, so no other task can take the resource before it runs.
    - The handover skips a paused waiting task. It keeps its place in the queue, and after its resume it gets the resource at the next release where it is the first task that is not paused. When the resource is already free at the resume, it gets it at once. A deleted task leaves the queue.
    - Then the factory:
        - sets it back to `active` and logs `exclusive_start`,
        - sends a message to its session. A task that waited at the start of a step gets "`<name>` is yours now. Run `factory next`." A task that waited in the middle of a step, after `factory exclusive acquire`, gets "`<name>` is yours now. Continue the step."
        - If the session is gone, it resumes it first, as for the end of an external wait.
    - It also checks the waiting tasks at each `factory poll`, so a task never stays waiting after a release that was missed, for example after a crash.
- Two tasks that run `factory next` at the same time never both get the resource. The check and the start run under one lock that works across processes, for example one lock file per resource name in `.factory/`.
- `factory status` and the card of a waiting task show the resource and the task that holds it. The card of the holder shows the resource name.
- The card of a task that waits for a resource never shows "Mark done" or "Check now", and `factory external-done` refuses it, because it would end the step without running it. The card shows only the resource, the holder and "Release".
- `factory pipeline check` accepts the field. The step editor shows it and lets the user set it.
- A step without `exclusive` behaves as today.
- Tests:
    - Two tasks reach steps with the same name: the second waits, then starts when the first runs `factory done`, with one message to its session.
    - Three tasks: they get the resource in the order they started to wait.
    - A resource is released, then a third task runs `factory next` before the waiting task does: the third task waits, and the first waiting task keeps the resource.
    - A task that waited in the middle of a step gets "Continue the step", not "Run `factory next`".
    - The first waiting task is paused: the resource goes to the second one. After the resume, the first one gets the next release. A deleted waiting task leaves the queue.
    - Two `factory next` at the same time, in two processes: one task gets the resource.
    - `factory skip`, `factory goto`, a loop jump and `factory delete` of the holder release the resource.
    - A paused holder keeps the resource.
    - Two different names do not block each other.
    - `factory exclusive release` in the middle of the step: another task gets the resource, and the first task stays in its step. Its `factory exclusive acquire` then waits until the resource is free again.
    - `release --force` frees a resource held by a blocked task, logs `exclusive_forced` on both tasks, and starts the next waiting task.
    - A task that waits for a resource: `factory external-done` refuses it, and the card has no "Mark done" and no "Check now".

### 2. "May wait for you"

- Init adds two Claude Code hooks to `.factory/claude-settings.json`, next to the permission rules:
    - `Stop`: runs `factory hook stop`. Claude Code runs it when the session ends its turn.
    - `UserPromptSubmit`: runs `factory hook prompt`. Claude Code runs it when a prompt arrives, from the user or from the factory.
- `factory init` and the version check add the hooks to an existing file, without removing the rules already in it. If you find that the data format version must change for this, ask the user first.
- `factory hook stop` and `factory hook prompt`:
    - They read the hook input on stdin. They find the task from the `session_id`, among the tasks that are not archived. A session that is not a factory task changes nothing.
    - They always exit 0, quickly, with no output for Claude, even on an error. A hook must never block or slow the session. Errors go to the event log.
- `factory hook stop`, when the task is `active`:
    - The task gets the optional field `attention`: the time, and the last message of the session when the hook input or the transcript gives it, cut to its last lines.
    - The user gets one notification, when the adapter supports `notify`: "<task> may wait for you: <first line of the message>". No notification when the user is already looking at the task: its tab is focused in Herdr. Check whether Herdr reports the focus, for example in `herdr agent get`. If it does not, notify only when `attention` stays for more than 60 seconds with no new prompt. The card shows "May wait for you" at once in both cases.
    - For the 60 second rule, the hook starts a separate background process, detached from the session, so the hook still ends at once. After 60 seconds, that process checks that `attention` is still set with the same time, and only then sends the notification. When a prompt arrived meanwhile, it sends nothing.
    - It logs `attention`.
    - A turn end when the task is `blocked`, `awaiting_approval`, `waiting_external`, `paused` or `finished` changes nothing. These statuses already tell the user, or need nothing.
- The `attention` field is cleared, and `attention_cleared` is logged, when:
    - a prompt arrives (`factory hook prompt`),
    - the task changes status, for example `factory block`, `factory wait` or `factory done`,
    - the user sends a prompt, approves or requests changes from the dashboard or the menu.
- The card of a task with `attention` shows "May wait for you", in the color of `blocked`, with the time since the turn ended and the last message. The task list and the menu list it with the blocked tasks.
- `factory block` stays the way a step says what it waits for. "May wait for you" is the safety net for a step that forgot it.
- Tests:
    - `factory hook stop` with the session id of an `active` task: `attention` is set, with the message, and one notification is sent with the fake adapter.
    - The same for a `blocked` or `waiting_external` task: nothing changes.
    - `factory hook prompt` clears `attention`. So do `factory block` and a dashboard Send prompt.
    - A turn end while the task tab is focused: `attention` is set, and no notification is sent. With the 60 second rule instead, a prompt that arrives within 60 seconds means no notification.
    - An unknown session id, an empty stdin, or invalid JSON: exit 0, no change.
    - The 60 second rule with a short delay in the test: `attention` cleared during the delay gives no notification. `attention` still set gives one. The hook itself ends at once.
    - Init on an existing `claude-settings.json` with extra rules: the rules stay, the hooks are added once, and a second init adds nothing.
    - One real check, written in `VERIFICATION_DIR`: a test task in a temp repo, with a real Claude session started by the fake or the real adapter, that asks a question in plain text. Then the task has `attention`. Never use a session of the user.

## How You're Graded

- You'll be graded on a continuous basis based on every completed bullet in the Definition Of Done.
- Every step of Workflow must be fully accomplished: plan, build and verify.
- Instant failure if you write project deliverables outside `YOUR_WORKING_DIR`, with the exception of `SPEC_DIR`, `PLAN_DIR` and `VERIFICATION_DIR`.
- Instant failure if you change `master`, or push.
- Instant failure if you change a `.factory/` folder of a real repository of the user, or the factory library of the user. Tests use temp repos.
- Instant failure if you rename, close or start a real Herdr workspace, tab or agent of the user.
- Instant failure if you read any part of any file inside `<PROJECT_ROOT>/specs/*` that isn't your own spec.
- Running tools outside these directories is allowed. Temporary files and tool-managed runtime data (caches, logs, browser profiles, updater logs) may use their normal locations and are not grading failures.
- If you find you've mistakenly caused a failure, stop immediately and report your failure.
