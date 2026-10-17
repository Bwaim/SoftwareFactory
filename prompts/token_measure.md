# Software factory: measure tokens and quality per step and per task

## Problem

1. The user wants to lower the token cost of the pipelines, one change at a time, and document the impact of each change. Today the factory measures nothing. A one-off script read the Claude transcripts of 9 Nextory tasks on 2026-10-18 and found:
    - Cache reads are 98–99% of all input tokens. Output tokens are small.
    - A task runs in one Claude session. Its context only grows: about 80k tokens at the first step, 300–600k at the end. Every late step re-reads the whole history.
    - In bug tasks, `nx-reproduce-bug` alone makes 19–36% of the reads, and makes the context grow by about 230k tokens.
2. The next changes (a fresh session per phase, shorter command output, a model per step) need a "before" and an "after" to compare. A token saving must not hide a quality loss, so quality needs numbers too.
3. Tasks differ a lot, so the comparison must group tasks by the version of the library and the factory that ran them, and compare steps, not only task totals.

## Solution

- The factory computes the token usage of each step run of a task from the Claude transcripts, and stores it in the task folder.
- The factory computes quality and time numbers of each task from its events, and stores them with the usage.
- Each task is tagged at launch with the library commit and the factory version.
- A command shows the usage of one task, and compares groups of tasks.
- The same computation works on the tasks that already exist, so the baseline is available at once.
- This change measures only. It changes no pipeline, no step and no session behavior.

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
    - The full factory requirements. Read it for context. Add this feature to it, in its style.
- `NEXTORY_REPO: /Users/fabienboismoreau/Documents/Projects/Nextory/Nextory_ai/nextory`
    - A real repository where the factory runs, with real tasks in `.factory/tasks/`. Read only.
- `TRANSCRIPTS: ~/.claude/projects/`
    - The Claude Code transcripts. Read only.
- `FIRST_SCRIPT: <PROJECT_ROOT>/prompts/token_optimization_per_step.py`
    - The one-off script of 2026-10-18, with the dedup fix. Read it as an example of the method. Do not copy it as is: it is not tested and it has known gaps (see Facts).
- `NOTES: <PROJECT_ROOT>/prompts/token_optimization.md`
    - The analysis behind this change, and the next optimization steps. Read it for context. Do not build its levers here.

## Workflow

1. Read. Read `MAIN_PROMPT`, `YOUR_WORKING_DIR/README.md`, the factory code (`state.py`, `events.py`, `engine.py`, `session.py`, `launch.py`, `version.py`, `server.py`, the dashboard) and `FIRST_SCRIPT`.
2. Brainstorm. Use the `/superpowers:brainstorming` skill to create a specification file from these requirements. Save the specification file in `SPEC_DIR/` before writing the plan.
3. Ask validation. Ask the user to validate the specification file.
4. Plan. After specification validation, use the `/superpowers:writing-plans` skill to create an implementation plan from the specification file. Save the plan file in `PLAN_DIR/` before writing implementation code. Split the plan into these milestones, in this order:
    1. Usage per step run, from the transcripts
    2. Quality and time numbers, from the events
    3. Tags at launch
    4. Storage in the task folder, and the commands
    5. Dashboard
5. Ask validation. Ask the user to validate the plan file.
6. Build. After plan validation, create the branch `token-measure` from `master`. Use the `/superpowers:subagent-driven-development` skill to implement the plan inside `YOUR_WORKING_DIR`, one milestone at a time. Run the full test suite of the factory after each milestone, fix the failures, and commit before starting the next milestone. Do not skip straight from this prompt to implementation.
7. Verify. Check every item in Definition Of Done, fix failures, and rerun the affected checks. Keep final verification artifacts inside `VERIFICATION_DIR` and report actual results and any remaining blockers.

## Definition Of Done

### Workflow Complete

- Your completed implementation plan exists under `PLAN_DIR/`.
    - It was written before implementation, and the build followed its build step.
- The work is on the branch `token-measure`. `master` is unchanged.
- Every existing test still passes. Each milestone adds its own tests.
- The README and `MAIN_PROMPT` describe the feature.
- The baseline report of the existing tasks of `NEXTORY_REPO` is saved in `VERIFICATION_DIR`, made with the new command, read-only.

### Facts

These facts were checked on 2026-10-18. Check them again during the build.

- `task.json` has `session_id`. The main transcript of a task is `TRANSCRIPTS/<project folder>/<session_id>.jsonl`. Its subagents are `TRANSCRIPTS/<project folder>/<session_id>/subagents/agent-*.jsonl`. The project folder name comes from the worktree path, with `/`, `_` and `.` turned into `-`. Find the file by the session id, not by building the folder name, and check how Claude Code builds it.
- A transcript line of type `assistant` has `message.usage` with `input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens` and `output_tokens`, and `message.model`. Each line has a `timestamp`.
- One API call can be split into several `assistant` lines with the same `message.id` and the same usage. Count each `message.id` once. On ht-4564, 166 lines are 104 calls: without the dedup, the reads are 24.4M instead of 15.4M. The first version of `FIRST_SCRIPT` had this bug. It is fixed in the saved copy.
- The context size of a call is `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`.
- `events.jsonl` of a task has `step_started` (with `step`, `run_in`, `model`, `effort`), `step_done`, `step_goto`, `loop_back`, `loop_limit`, `task_blocked`, `task_unblocked`, `approved`, `changes_requested`, `done_check_failed`, `waiting_started`, `external_event`, `column_changed`, `attention`, `attention_cleared`, `task_paused`, `task_resumed` and `task_finished`, each with `ts`. Check the full list in the code.
- A subagent transcript belongs to the step that was running when the subagent started.
- `FIRST_SCRIPT` gives each call to the last `step_started` before it. It ignores the time when no step runs, and the case where a task has several sessions.
- A later change will start a fresh Claude session per phase. So a task can have several session ids, and the measurement must support a list of sessions per task.
- Claude Code can remove old transcripts (`cleanupPeriodDays`). A usage that is stored in the task folder must stay when the transcript is gone.
- `factory version check` knows the factory version. The library is a git repository (`factory library commit`).

### 1. Usage per step run

- One record per step run. A step that runs again, in a loop or after a `goto`, gives a new record with its round number.
- Each record has: the task id, the step id, its path, the round, `run_in`, the model and the effort (from the event, and the models seen in the transcript), the start and end times, and:
    - main session: number of calls, cache reads, cache writes (`cache_creation_input_tokens` plus `input_tokens`), output tokens, context size at the first and at the last call
    - subagents: number of subagents, calls, cache reads, cache writes, output tokens
    - tool results: total characters of the tool results in the main session during the step
- Calls when no step runs (before the first step, between steps, after the end) go to a separate bucket, not to a step.
- The record also has a cost index in "input-token equivalents": `cache reads × 0.1 + cache writes × 1.25 + input + output × 5`. It is only a weight, to rank the steps. Write the weights in one place and in the README. Do not show money.
- Tests with small fake transcripts and events: the dedup by `message.id`, a call before the first step, a subagent that starts in one step and ends in the next, a step run twice in a loop, 2 sessions in one task, a missing transcript.

### 2. Quality and time numbers

From the events, per task:
- the number of loop jumps per loop, the loop limits reached, the `goto`s
- the number of `changes_requested` and `approved` per approval step
- the number of `done_check_failed`
- the time of each step run, the time per column, and the total time
- the time blocked or waiting for the user (`task_blocked` to `task_unblocked`, `attention` to `attention_cleared`), and the time waiting for an external event
- From the task keys, when they exist: the number of findings in `spec_findings`, `plan_findings`, `execution_findings`, `code_rabbit_findings` and `fix_findings` at each round. Explain in the spec how you count findings in a text key. When it cannot be counted, store "set" or "not set".

These numbers are read from data the factory already has. Do not add questions to the user.

### 3. Tags at launch

- At launch, save in the task: the factory version, the library commit (`git rev-parse HEAD` of the library, with a `dirty` flag when it has changes), and the pipeline id.
- An existing task has no tags. It gets "unknown", and the report can still group it, for example by its launch date.
- A tag can also be set by hand, for example `factory tag <task> baseline`, so the user can name a group of tasks. Choose the command name in the spec.

### 4. Storage and commands

- The usage records, the quality numbers and the tags are saved in the task folder, in a file such as `usage.json`. The task folder is kept when a task is archived.
- When to compute:
    - At each step end (`factory done`, `factory skip`, `goto`, loop jump), for the step that ended. It must never fail or slow down the step change: a computation error is logged as an event and the step change goes on. Measure the time it adds on the biggest real transcript, and report it.
    - On demand, for one task or all tasks, also for finished and archived tasks.
    - When a transcript is gone, keep the stored records.
- A command shows one task: a table per step run, sorted by the cost index, with the totals.
- A command compares groups of tasks: grouped by tag, by library commit, by pipeline, or by launch date range. Per group and per step id: the number of runs, the median and the sum of calls, reads, cost index, context size at the start, and the quality numbers. Also the per-task totals.
- An export to CSV or JSON, so the user can document each change.
- Choose the command names in the spec, in the style of the other `factory` commands. Every command has `--json`.

### 5. Dashboard

- The card of a task shows its cost index so far, and the context size of the last call.
- The task view shows the table per step run.
- Keep it small. A full comparison view is not needed: the command does it.

### Baseline

- Run the on-demand computation, read-only, on the tasks of `NEXTORY_REPO`, including the finished and archived ones. Save the report in `VERIFICATION_DIR`.
- This writes `usage.json` in the task folders of `NEXTORY_REPO`. Ask the user before you do it. Until the user agrees, compute into `VERIFICATION_DIR` only.
- Compare the numbers with `FIRST_SCRIPT` and with the table in `NOTES`, and explain any difference.

## How You're Graded

- You'll be graded on a continuous basis based on every completed bullet in the Definition Of Done.
- Every step of Workflow must be fully accomplished: plan, build and verify.
- Instant failure if you write project deliverables outside `YOUR_WORKING_DIR`, with the exception of `SPEC_DIR`, `PLAN_DIR` and `VERIFICATION_DIR`.
- Instant failure if you change `master`, or push.
- Instant failure if you change or delete a transcript in `TRANSCRIPTS`.
- Instant failure if you change a tracked file of `NEXTORY_REPO`, or change, advance or delete a task of the user. Writing `usage.json` in a real task folder is allowed only after the user agrees.
- Instant failure if you run `claude`, `factory` or a hook command in a worktree of a real task.
- Instant failure if you rename, close or start a real Herdr workspace, tab or agent of the user. Tests use the fake adapter.
- Instant failure if you read any part of any file inside `<PROJECT_ROOT>/specs/*` that isn't your own spec.
- Running tools outside these directories is allowed. Temporary files and tool-managed runtime data (caches, logs, browser profiles, updater logs) may use their normal locations and are not grading failures.
- If you find you've mistakenly caused a failure, stop immediately and report your failure.
