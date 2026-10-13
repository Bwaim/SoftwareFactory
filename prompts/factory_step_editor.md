# Software factory: step editor and typed task keys

## Problem

Creating a step is slow and unclear:
- The step assistant asks many questions in a Claude session. Writing the step file by hand is often faster.
- `reads` and `writes` are free lists of names. Nothing says where a key comes from, when it is set, or what kind of value it holds. Example: `brainstorm` reads `summary`, but nothing says that only a launch from a backlog entry sets it.
- The pipeline editor does not show which task keys a step can use at its position in the pipeline.
- A pipeline input has no type. The launch cannot tell a short value from a long text or a file path.
- The step types `prompt` and `skill` are the same thing: a text sent to the agent. The agent never gets the exact text the user wrote, because `factory next` adds the key values around it.
- A missing step is found while building a pipeline, but it cannot be created from the pipeline editor.

## Solution

- Task keys have a type: `text`, `long-text` or `file`.
- A step has one of three types:
  - `ai`: the exact prompt sent to the agent, with placeholders for task keys and config values.
  - `command`: a shell command.
  - `group`: the old composite step, a list of child steps.
- A step declares its outputs with their type. The keys it uses are computed from its prompt or command, never written by hand.
- The pipeline editor shows the task keys available at each position, and has a step form to create and edit steps. It replaces the step assistant.
- Every task runs in a worktree. With the step assistant gone, no pipeline runs in the main repository.
- The data format goes to version 2, with a migration.

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

1. Read. Read `MAIN_PROMPT`, `YOUR_WORKING_DIR/README.md` and the factory code, so the changes follow the existing design, modules and tests.
2. Brainstorm. Use the `/superpowers:brainstorming` skill to create a specification file from these requirements. Save the specification file in `SPEC_DIR/` before writing the plan.
3. Ask validation. Ask the user to validate the specification file.
4. Plan. After specification validation, use the `/superpowers:writing-plans` skill to create an implementation plan from the specification file. Save the plan file in `PLAN_DIR/` before writing implementation code. Split the plan into these milestones, in this order:
    1. Step format and runtime: typed keys, the `ai`, `command` and `group` types, placeholders, outputs, `factory next`, `factory done`, `factory state set`, `factory run-command`, the removal of the step assistant and of tasks without a worktree, the built-in and catalog steps in the new format, and the migration from version 1 to version 2.
    2. Available keys: `factory pipeline keys`, the new pipeline checks, typed pipeline inputs in the launch, the menu and the dashboard Launch form.
    3. Step editor: the step form in the pipeline editor, its server API, the menu action "Create a new step", and the README.
5. Ask validation. Ask the user to validate the plan file.
6. Build. After plan validation, create the branch `step-editor` from `master`. Use the `/superpowers:subagent-driven-development` skill to implement the plan inside `YOUR_WORKING_DIR`, one milestone at a time. Run the full test suite of the factory after each milestone, fix the failures, and commit before starting the next milestone. Do not skip straight from this prompt to implementation.
7. Verify. Check every item in Definition Of Done, fix failures, and rerun the affected checks. Keep final verification artifacts inside `VERIFICATION_DIR` and report actual results and any remaining blockers.

## Definition Of Done

### Workflow Complete

- Your completed implementation plan exists under `PLAN_DIR/`
    - It was written before implementation, and the build followed its build step.
- The work is on the branch `step-editor`. `master` is unchanged.
- Every existing test still passes, or is updated because its behavior changed on purpose. The report lists each updated test and why.

### Task keys

- A task key name uses lowercase letters, digits and `_`, and starts with a letter. Example: `crash_url`.
- A key has a type:
  - `text`: one line, a short value. Example: a branch name, a URL.
  - `long-text`: several lines. Example: a summary, notes.
  - `file`: the absolute path of a file or a folder.
- The type is optional everywhere. A missing type means `text`.
- A key comes from one of three sources:
  - A pipeline input
  - An output of an earlier step
  - The factory itself. The factory keys are:
    - `task_id` (`text`): the task id
    - `description` (`text`): the task description
    - `summary` (`long-text`): set only when the task is launched from a backlog entry
- A key is "maybe set" at a position when it is `summary`, or when it comes from an output marked `optional: true`. Otherwise it is "always set".

### Pipeline inputs

- Each input has a `type` and a `description`.
- Launch:
  - `text`: one line in the menu and a text field in the dashboard Launch form.
  - `long-text`: the menu tells the user they can write several lines. The dashboard Launch form shows a text area.
  - `file`: the launch dry run reports an error when the path does not exist. A relative path is resolved from the main repository and saved as an absolute path.

### Step format

- `type` is one of `ai`, `command` or `group`.
- `outputs`: the keys the step sets, replacing `writes`. Each output has `type`, `description` and an optional `optional: true`.
- The `reads` field is removed. The keys a step uses are computed:
  - `ai`: from the placeholders in its prompt
  - `command`: from the `$FACTORY_KEY_<KEY>` variables in its command
  - `group`: from its child steps, and its outputs too
- `ai` step:
  - The body is the prompt. It is the exact text sent to the agent, with placeholders replaced.
  - `{{<key>}}` is replaced with the value of a task key. `{{config.<key>}}` is replaced with a config value.
  - A key that is not set is replaced with `(not set)`.
  - A placeholder `{{config.<key>}}` for a key the manifest does not declare in `config` is an error when the step loads.
  - A `{{...}}` placeholder in a `command` step is an error when the step loads. A command uses the environment variables below, so a value is never pasted into shell code.
  - `run_in`, `model` and `effort` apply only to `ai` steps.
  - A step that calls a skill is an `ai` step whose prompt calls the skill. `requires` still lists the skill.
- `command` step:
  - The body is a shell command, one or more lines. It runs with `bash` in the task worktree.
  - The task keys are environment variables `FACTORY_KEY_<KEY>`, for example `FACTORY_KEY_CRASH_URL`. The config values stay `FACTORY_CONFIG_<KEY>`.
  - `FACTORY_STEP_DIR` is the folder of the step file. A command calls a script next to the step with `bash "$FACTORY_STEP_DIR/<file>"`.
  - The command sets its outputs with `factory state set`.
- `group` step: the manifest has a `steps` list of child step ids, and no body. The rules of composite steps stay: a group cannot include itself, directly or through another group, and the current step shows its full path, for example `rebase-and-commit > commit`.
- `done_when` and the optional `done_check` stay.

### Step runtime

- `factory next` for an `ai` step prints the prompt with its placeholders replaced, then one fixed footer from the factory:
  - Each output to set, with its type and description, and the exact `factory state set <key> <value>` command
  - For a `file` output, `factory artifact path <name>`, which gives a path in the artifacts folder
  - The `done_when` text
  - "When the step is done, run `factory done`."
- For a subagent step, the Agent prompt is this same text.
- `factory next` for a `command` step tells the session to run `factory run-command`. It runs the command and prints its output and its exit code.
- `factory state set <key> <value>`:
  - For a `file` output of the current step, it refuses a path that does not exist, and saves the absolute path.
  - It still accepts a key that is not a declared output.
- `factory done` checks, in this order, and stays on the step with the reason when one fails:
  1. Every output not marked `optional` is set.
  2. Every `file` output that is set points to an existing path.
  3. For a `command` step: its last `factory run-command` exited with code 0.
  4. The `done_check`, when present.
- The checks 1 and 2 replace `done_check` lines like `test -f "$(factory state get plan)"`. The catalog steps drop them.

### No more step assistant

- The built-in pipeline `new-step-assistant` and the built-in step `new-step` are removed.
- No pipeline runs in the main repository anymore. Remove what only served it: the Herdr `tab create` path for a task in the main repository, the main repository case in launch and resume, and the `--task <id>` that `factory next` and the first prompt add for a task without a worktree. Every task runs in its own worktree.
- The `--task <id>` option stays on the commands, so the orchestrator and the tests can still name a task.

### Built-in and catalog steps

- Every built-in and catalog step file is rewritten in the new format by the build:
  - `prompt` and `skill` become `ai`. `script` becomes `command`. A placeholder replaces each key name the prompt refers to, for example `{{spec}}`.
  - Outputs get their real type: `spec`, `plan` and `review` are `file`. `mr_url` is `text`. `branch` is `text` and `optional: true` in `commit`.
  - `push` and `run-tests` become `command` steps that call their script with `$FACTORY_STEP_DIR`.
- No catalog file refers to a project-specific skill or tool.

### Migration from version 1 to version 2

- The data format version goes from 1 to 2. The migration script is `migrations/1-to-2`.
- It runs on the local steps and pipelines, the generic library, and the saved step lists of unfinished tasks:
  - `prompt` and `skill` become `ai`. `composite` becomes `group`.
  - `script` becomes `command`. The body `<file>` becomes `bash "$FACTORY_STEP_DIR/<file>"`.
  - `writes: [a, b]` becomes `outputs` with `type: text` and `optional: true` for each key, so no new done check blocks an old step.
  - For an `ai` step with `reads`, it adds this block at the end of the prompt, one line per key: `- <key>: {{<key>}}`, under the line `Task keys:`. The agent then gets the same values as before.
  - It removes `reads`.
- Before it changes anything, it refuses and lists the problems when:
  - A key name does not follow the key name rule.
  - An unfinished task uses `new-step-assistant`. The message says to delete the task first.
- The existing `migrate` step runs it, with the backup and the library git check.
- The library commit message is `Factory library: migrate to version 2`.

### Available keys

- `factory pipeline keys <id> [--at <position>] [--json]` lists the keys available before the step at this position. Without `--at`, it lists the keys available after the last step.
- Each key shows its name, its type, its source (`input`, `step <id>`, or `factory`), and "always set" or "maybe set".
- A key written by two sources keeps the latest one.
- The server API has a route that returns the same list. Both call the same function.
- New pipeline checks:
  - Warning: a step uses a key that no earlier source sets. It replaces the warning about `reads`.
  - Warning: a key is set with two different types in the pipeline.

### Step editor

- The pipeline editor has a step form. It replaces the step assistant.
- It opens from:
  - A "New step" button above the available steps
  - An "Edit" button in the detail panel of a local or generic step
  - A "Copy to local" button in the detail panel of a generic or built-in step. It opens the form with a copy that saves as a local step with the same id, which overrides it.
  - A "Duplicate" button in the detail panel of any step. It opens the form with a copy under a new id.
- `factory step edit [<id>]` opens the editor on the form: empty without an id, the step with an id. The menu action "Create a new step" runs `factory step edit`.
- The form fields:
  - `id`: refused when another step has it, hidden steps included. It cannot change when editing.
  - `description`, `done_when`, `done_check`
  - `category`: a list of the existing categories, plus a field for a new one
  - `type`: `ai`, `command` or `group`
  - Level: local or generic, chosen when the step is new
  - `run_in`, `model` and `effort`: lists, shown only for `ai`
  - `column`: a list of the board columns, or none
  - `required` and `wait_external`: checkboxes
  - `requires`: a list of text entries
  - `config`: a table with key, description and default
  - `outputs`: a table with key, type (a list of `text`, `long-text`, `file`), description and optional
  - The body: a text area for the prompt or the command. A `group` step shows a list of child steps instead, chosen from the steps that are not hidden, and ordered by drag and drop.
- Next to the body, the form shows the keys the step can use:
  - When the step is selected in the current pipeline: the keys available at its position, from `factory pipeline keys --at`.
  - Otherwise: the factory keys.
  - Its own config keys, as `{{config.<key>}}`.
  - Clicking a key inserts `{{<key>}}` in an `ai` prompt, or `$FACTORY_KEY_<KEY>` in a command.
- For an `ai` step, a "Preview" shows the exact text `factory next` would print, with each placeholder shown as `<key>` and the footer included.
- Saving an existing step first shows:
  - The pipelines that use the step
  - The unfinished tasks that use it. The change applies to them from their next step.
  - For a generic step: "Other repositories that use this library are not checked."
- The server checks the step with the same function the factory uses to load steps. Errors block the save. Warnings do not.
- After the save, the step list reloads. For a generic step, the editor offers the library commit `Factory library: add step <id>` or `Factory library: update step <id>`. A `command` step that comes with a script file is written by hand, so the form never writes a script file.
- Built-in steps cannot be edited. They can only be copied.
- The detail panel shows the computed keys the step uses, its outputs with their types, and for a `group` step its child steps.

### Orchestrator

- "Create a new step" runs `factory step edit`, which opens the step form in the pipeline editor.

### Documentation

- The README describes the key types, the factory keys, the three step types, placeholders, outputs, the `FACTORY_KEY_` and `FACTORY_STEP_DIR` variables, the step form, `factory pipeline keys`, `factory step edit` and `factory run-command`.
- The README tutorial step "Create a step" uses the step form in the pipeline editor. The other tutorial steps stay unchanged.
- The README uses simple English and short sentences.

### Verification

- The build is verified with an automated test run. Its report goes to `VERIFICATION_DIR/step-editor-report.md`.
- The report has one section per milestone, with the tests run and their results, and the result of the full test suite.
- Test setup: the same as the existing factory tests. A test repository, a test library in its own test git repository, never a real library or a real `.factory/`.
- CLI tests, without Herdr or Claude:
  - `factory next` on an `ai` step prints the prompt with each placeholder replaced, `(not set)` for a missing key, and the footer with every output.
  - A `{{config.<key>}}` placeholder for an undeclared config key is refused when the step loads.
  - A `command` step gets its keys as `FACTORY_KEY_<KEY>`, its config as `FACTORY_CONFIG_<KEY>`, and `FACTORY_STEP_DIR`. `factory done` refuses it until `factory run-command` exits with code 0.
  - `factory done` refuses a missing output that is not optional, and a `file` output whose path does not exist.
  - `factory state set` refuses a missing path for a `file` output and saves an absolute path.
  - A `group` step: the full path is shown, its keys and outputs are computed, and a loop is refused.
  - `factory pipeline keys` lists inputs, outputs of earlier steps and factory keys with their type and source, and marks `summary` and optional outputs as "maybe set".
  - Each new pipeline check warning appears on a test pipeline.
  - A `file` input that does not exist is a launch dry run error. A relative path is saved as an absolute path.
  - The migration from version 1 to version 2 converts test data of every step type, `writes` and `reads`, and a script step. The migrated pipeline runs to the end with the fake adapter. It refuses a bad key name and an unfinished `new-step-assistant` task before changing anything.
  - The built-in pipeline `new-step-assistant` and the step `new-step` no longer exist. `factory next` never adds `--task` to the commands it prints.
  - A `{{...}}` placeholder in a `command` step is refused when the step loads.
  - The step API, tested without a browser: save a new local step, save a generic step and get the library commit offer, refuse a duplicate id, refuse an edit of a built-in step, copy to local, return the save impact (pipelines and unfinished tasks), and return the preview text. Requests without the token are rejected.
  - Every `factory` command written in the README exists in the CLI.
  - No catalog file refers to a project-specific skill or tool.
- Manual browser check list in `VERIFICATION_DIR/step-editor-manual-check.md`, for the user to run:
  - Create a new `ai` step from the form, insert keys by clicking, check the preview, save it local, and add it to a pipeline.
  - Edit a generic step, see the save impact, save, and commit to the library.
  - Copy a built-in step to local, and duplicate a step.
  - Create a `group` step by choosing and ordering child steps.
  - Select a step in a pipeline and check the available keys at its position.
  - Launch a pipeline from the dashboard with a `long-text` input in a text area, and with a `file` input that does not exist.
  - The orchestrator "Create a new step" action opens the form.
  - Migrate a copy of a real version 1 `.factory/` folder and library, made by the user, and run a migrated pipeline.

## How You're Graded

- You'll be graded on a continuous basis based on every completed bullet in the Definition Of Done.
- Every step of Workflow must be fully accomplished: plan, build and verify.
- Instant failure if you write project deliverables outside `YOUR_WORKING_DIR` with the exception of `SPEC_DIR`, `PLAN_DIR` and `VERIFICATION_DIR`.
- Instant failure if you read any part of any file inside `<PROJECT_ROOT>/specs/*` that isn't your own spec.
- Instant failure if you change a real library or a real `.factory/` folder. Tests use test repositories only.
- Instant failure if you close a Herdr workspace, tab, pane or session you did not create.
- Running tools outside these directories is allowed. Temporary files and tool-managed runtime data (caches, logs, browser profiles, updater logs) may use their normal locations and are not grading failures.
- If you find you've mistakenly caused a failure, stop immediately and report your failure.
