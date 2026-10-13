# Software factory: pipeline loops

## Problem

Some work needs rounds:
- A step writes a spec. A review step finds problems. The spec step fixes them, and the review runs again. After 2 rounds with problems left, the user decides.
- A step splits the work into tickets. One round of steps handles one ticket. The number of tickets is known only at run time.

Today the only way back is `factory goto`. The session may run it only after user approval, and the limit is fixed at 3 jumps. A pipeline cannot say "go back to this step while this key has a value, at most N times".

## Solution

- A pipeline entry gets an optional `loop` field: go back to an earlier entry while a task key is set, at most `max` times.
- The factory makes the jump itself, in `factory done`. The session never runs `goto` for a loop.
- After `max` rounds with the key still set, the task moves on and is blocked for the user.
- No new step type. No data version change.

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
    - The full factory requirements. Read it for context. It already contains these changes.

## Workflow

1. Read. Read `MAIN_PROMPT`, `YOUR_WORKING_DIR/README.md`, both skills under `YOUR_WORKING_DIR/skills/` and the factory code, so the changes follow the existing design, modules and tests.
2. Brainstorm. Use the `/superpowers:brainstorming` skill to create a specification file from these requirements. Save the specification file in `SPEC_DIR/` before writing the plan.
3. Ask validation. Ask the user to validate the specification file.
4. Plan. After specification validation, use the `/superpowers:writing-plans` skill to create an implementation plan from the specification file. Save the plan file in `PLAN_DIR/` before writing implementation code. Split the plan into these milestones, in this order:
    1. Loop runtime: the `loop` field, the pipeline checks, the task snapshot, `factory done`, the footer line, the events and `factory status`.
    2. Loop authoring: the pipeline editor, the dashboard card, the authoring skill and the README.
5. Ask validation. Ask the user to validate the plan file.
6. Build. After plan validation, create the branch `pipeline-loop` from `master`. Use the `/superpowers:subagent-driven-development` skill to implement the plan inside `YOUR_WORKING_DIR`, one milestone at a time. Run the full test suite of the factory after each milestone, fix the failures, and commit before starting the next milestone. Do not skip straight from this prompt to implementation.
7. Verify. Check every item in Definition Of Done, fix failures, and rerun the affected checks. Keep final verification artifacts inside `VERIFICATION_DIR` and report actual results and any remaining blockers.

## Definition Of Done

### Workflow Complete

- Your completed implementation plan exists under `PLAN_DIR/`
    - It was written before implementation, and the build followed its build step.
- The work is on the branch `pipeline-loop`. `master` is unchanged.
- Every existing test still passes, or is updated because its behavior changed on purpose. The report lists each updated test and why.

### Loop field

- A `steps` entry of a pipeline can have a `loop` map:
  - `back_to`: the id of an entry of the same pipeline, at or before this entry. When the id appears more than once, the nearest one at or before this entry is used. `back_to` can be the entry itself, to repeat one round.
  - `while`: a task key name.
  - `max`: an integer from 1 to 20. The most jumps back for this loop.
- The entry can be a normal step or a group step.
- Example, a review loop:

```yaml
steps:
  - write-spec
  - id: review-spec
    loop:
      back_to: write-spec
      while: findings
      max: 2
  - next-step
```

- Example, one round per ticket, for any number of tickets:

```yaml
steps:
  - split-tickets
  - id: ticket-round
    loop:
      back_to: ticket-round
      while: remaining
      max: 20
```

### Runtime

- The task snapshot keeps each loop: the position of the last step of the entry, the position of the first step of the `back_to` entry, `while` and `max`. A step file or pipeline file changed later does not change a running loop.
- When `factory done` succeeds on the last step of a loop entry, the factory reads the `while` key:
  - The key is "set" when it has a value that is not empty and is not `none`, ignoring case and spaces around it.
  - Set, and fewer than `max` jumps were made for this loop: the task goes back to the first step of `back_to`. `factory done` prints "Loop <n> of <max>: back to `<step>`. Run `factory next`." where `<n>` is the number of this jump, from 1 to `max`.
  - Set, and `max` jumps were made: the task moves to the next step and is blocked, with the reason "Loop limit reached on `<entry>`: `<key>` is still set". The `factory done` output tells the session to ask the user. The user can unblock to continue, or approve one more round, which the session then makes with `factory goto`.
  - Not set: the task moves to the next step, as today.
- A loop on the last entry of the pipeline that ends finishes the task, as today. At the limit on the last entry, the task also finishes, logs `loop_limit` and sends a notification that says the loop limit was reached.
- A skipped step never triggers its loop.
- The jump back resets the same task fields as `factory goto`: `started`, `command_result` and `approval`. Task keys keep their values.
- The jump runs in the same task session. Every `session` step that runs again keeps the conversation of the earlier rounds. A `subagent` step starts a new agent each time.
- Loop jumps are counted per loop, apart from `goto_counts`. The 3-jump limit of `factory goto` does not count loop jumps. A loop's count resets to 0 when the task jumps to a step before its range, by an outer loop or by `factory goto`. So an inner loop gets its full `max` in each round of an outer loop.
- Events: `loop_back`, with the entry, the target step, the round and `max`, and `loop_limit`, with the entry and the key.
- `factory status` shows "loop <n> of <max>", with `<n>` the jumps made, while the current step is inside a loop range that has made at least one jump. Inside nested loops, it shows the innermost one.

### Footer

- When a step inside a loop range outputs the `while` key, `factory next` adds one line to its footer: "This step controls a loop. Set `<key>` to `none` when nothing is left." Task keys keep their values, so a clean round must reset the key.

### Pipeline check

- Errors:
  - `loop` is not a map, or has a field other than `back_to`, `while` and `max`.
  - `back_to` is not the id of this entry or of an earlier entry.
  - `max` is not an integer from 1 to 20.
  - `while` is not a valid key name.
  - Two loops overlap without one being inside the other.
- Warnings:
  - No step inside the loop range outputs the `while` key.
  - The `while` key is an optional output of every step that outputs it inside the loop range.
  - The loop entry is the last entry of the pipeline: at the limit, the task finishes without asking the user. Add a step after it, for example `user-validation`.

### Pipeline editor and dashboard

- The pipeline editor keeps `loop` when it loads and saves a pipeline.
- The entry form edits `back_to` (a list of this entry and the earlier entries), `while` (a list of the keys available at the end of the entry, with free text allowed) and `max`.
- A pipeline row with a loop shows a mark with its target and `max`, for example "↺ write-spec ×2".
- The live checks show the new errors and warnings.
- A dashboard card shows "loop <n> of <max>" like `factory status`.

### Authoring skill and documentation

- The `factory-authoring` skill documents `loop`: the fields, the rules of the runtime, the footer line, and the two examples above with their steps. The review example uses a review step with `run_in: subagent` in its step file.
- The skill tells the agent that each step that outputs the `while` key must set it to `none` when nothing is left.
- The README describes `loop` in the pipeline fields, with the review example, and the new events.
- The README and the skill use simple English and short sentences.

### Verification

- The build is verified with an automated test run. Its report goes to `VERIFICATION_DIR/pipeline-loop-report.md`.
- The report has one section per milestone, with the tests run and their results, and the result of the full test suite.
- Test setup: the same as the existing factory tests. A test repository, a test library in its own test git repository, the fake adapter, never a real library or a real `.factory/`.
- CLI tests, without Herdr or Claude:
  - Review loop, key set twice then `none`: two jumps back, then the next step. The `factory done` outputs and the `loop_back` events show loops 1 and 2 of 2.
  - Review loop, key still set after `max` jumps: the task moves to the next step and is blocked with the limit reason. A `loop_limit` event is logged.
  - Loop on a group entry back to itself: one round per value, until the key is `none`.
  - Nested loops: an inner loop that reached its limit gets its full `max` again after the outer loop jumps back.
  - At the limit on the last entry, the task finishes and a `loop_limit` event is logged.
  - `none`, ` None `, an empty value and a key that was never set all count as not set.
  - A skipped loop step does not jump.
  - Loop jumps do not change `goto_counts`, and three loop rounds do not block the task as a `goto` loop.
  - The jump resets `command_result` and `approval`, and keeps task keys.
  - Each pipeline check error and warning of this prompt appears on a test pipeline.
  - The footer line appears on the step that outputs the `while` key inside the loop range, and on no other step.
  - `factory status` shows "loop <n> of <max>".
  - The pipeline editor API saves and loads a pipeline with `loop` unchanged.
  - The examples of the authoring skill load, and `factory pipeline check` on them gives no error and no warning.
  - Every `factory` command written in the README and the skills exists in the CLI.
- Manual check list in `VERIFICATION_DIR/pipeline-loop-manual-check.md`, for the user to run:
  - Run a review loop pipeline with a real session: the spec step runs again in the same session with the findings, and the task is blocked after the last round when findings remain.
  - Run a ticket loop pipeline with three tickets.
  - Add a loop to a pipeline in the pipeline editor, check the mark and the live checks, and save.
  - Follow "loop <n> of <max>" on a dashboard card.

## How You're Graded

- You'll be graded on a continuous basis based on every completed bullet in the Definition Of Done.
- Every step of Workflow must be fully accomplished: plan, build and verify.
- Instant failure if you write project deliverables outside `YOUR_WORKING_DIR` with the exception of `SPEC_DIR`, `PLAN_DIR` and `VERIFICATION_DIR`.
- Instant failure if you read any part of any file inside `<PROJECT_ROOT>/specs/*` that isn't your own spec.
- Instant failure if you change a real library or a real `.factory/` folder. Tests use test repositories only.
- Instant failure if you close a Herdr workspace, tab, pane or session you did not create.
- Running tools outside these directories is allowed. Temporary files and tool-managed runtime data (caches, logs, browser profiles, updater logs) may use their normal locations and are not grading failures.
- If you find you've mistakenly caused a failure, stop immediately and report your failure.
