# Step editor and typed task keys: design

Requirements and Definition Of Done: `prompts/factory_step_editor.md`. Full factory requirements: `prompts/factory_skill_creation.md`.
Code: `software-factory/`. Verification: `verification/software-factory/`.

## 1. Goal

- Typed task keys (`text`, `long-text`, `file`), with three sources: pipeline inputs, step outputs, factory keys.
- Three step types: `ai`, `command`, `group`. Placeholders in `ai` prompts. `FACTORY_KEY_<KEY>` variables in commands.
- The keys a step uses are computed. Outputs are declared with their type.
- `factory next` prints the exact prompt, plus one fixed footer.
- `factory pipeline keys` and the new pipeline checks.
- A step form in the pipeline editor. It replaces the step assistant.
- Every task runs in a worktree.
- Data format version 2, with the migration `migrations/1-to-2.py`.

## 2. Decisions

- D1. The migration file is `migrations/1-to-2.py`. The current loader expects the `.py` suffix.
- D2. A step file with a load error makes `Registry.load` fail. The error names the file and the reason. This is how parse errors and group loops already work.
- D3. `done_check` also gets the `FACTORY_KEY_<KEY>` variables and `FACTORY_STEP_DIR`. A `{{...}}` in a `done_check` is a load error. The `$FACTORY_KEY_` variables of the `done_check` count as keys the step uses.
- D4. The footer starts with the step path line, for example `Step 3 of 7: rebase-and-commit > commit`. It keeps the "If needed" lines (block, skip, goto) in session steps. A `wait_external` step ends with "run `factory wait`".
- D5. `task_id` and `description` come from the task fields at render time. They are not copied into the state. `summary` stays in the state.
- D6. `create-worktree` has no outputs. `branch` comes from a pipeline input or from the `commit` output.
- D7. A group step that declares `outputs` is a load error. Group outputs are computed. The form hides the outputs table for a group.
- D8. `--at <position>` is the 1-based position in the `steps` list of the pipeline file. The implicit `create-worktree` is not counted. `--at 1` means "before the first listed step".
- D9. The adapter `in_worktree` parameter and the `--worktree` flag of `factory terminal start-session` are removed. They only served tasks in the main repository.
- D10. Unfinished tasks in the migration: a task of `new-step-assistant` refuses the migration. A saved state key with a bad name is a warning. It is listed in the migration summary, and the migration continues. The key name rule blocks the migration only for keys in step and pipeline files.
- D11. Subagent step: the Agent prompt is the same prompt and footer as for a session step. Only the last line differs: "End with a short report. If you need an answer from the user, say so in the report and stop." Only the session runs `factory done`.

## 3. Task keys

New module `lib/factory/keys.py`. It holds every key rule. The engine, the checks, the editor and the CLI use it.

- `KEY_RE = [a-z][a-z0-9_]*`. `KEY_TYPES = ("text", "long-text", "file")`. A missing type means `text`.
- `FACTORY_KEYS`:
  - `task_id`: `text`, always set
  - `description`: `text`, always set
  - `summary`: `long-text`, maybe set
- `env_name(key)` returns `FACTORY_KEY_` plus the key in upper case. The key rule makes this one-to-one.
- `PLACEHOLDER_RE = \{\{([^{}]*)\}\}`. `placeholders(text)` returns:
  - the task keys used
  - the config keys used
  - the invalid placeholders. An invalid placeholder is a placeholder whose inner text is neither a key name nor `config.<name>`.
- `env_refs(text)` returns the keys named by `$FACTORY_KEY_<NAME>` or `${FACTORY_KEY_<NAME>...}`, converted back to lower case.
- `step_uses(reg, sid)`:
  - `ai`: the placeholder keys of the body, then the `done_check` env refs.
  - `command`: the env refs of the body, then those of the `done_check`.
  - `group`: walk the leaves in order. A leaf key counts when no earlier leaf of the group outputs it.
  - The result is ordered and has no duplicates.
- `step_outputs(reg, sid)`: a dict `key -> {type, description, optional}`.
  - `ai` and `command`: the manifest `outputs`.
  - `group`: the outputs of the leaves in order. The latest leaf wins.
- `available(reg, data, at=None)`:
  - It runs over the factory keys, then the pipeline inputs, then the leaf outputs of each entry before `at`.
  - It returns rows `{name, type, source, set}`. `source` is `factory`, `input` or `step <leaf id>`. `set` is `always` or `maybe`.
  - The latest source wins. `maybe` means the winning source is `summary` or an output with `optional: true`.
  - The implicit `create-worktree` has no outputs, so it adds nothing.
  - `at` is out of range: `FactoryError` "The position must be between 1 and <n + 1>."
- `factory pipeline keys` and the API route call `available`.

## 4. Step format version 2

New module `lib/factory/step_format.py`.

### 4.1 Manifest

- Fields:
  - `id`, `description`, `category`
  - `type`: `ai`, `command` or `group`
  - `outputs`: `{key: {type, description, optional}}`
  - `done_when`, `done_check`, `config`, `required`
  - `run_in`, `model`, `effort`
  - `requires`, `column`, `wait_external`
  - `steps`: only for a group
- `reads` and `writes` no longer exist. The type `prompt`, `skill`, `script` or `composite` is a load error that says to run the migration.

### 4.2 `validate(manifest, body, path=None)`

It returns `(errors, warnings)` as lists of text. `Registry.load` calls it for each step file and raises a `FactoryError` with the first errors. The editor save calls the same function.

Errors:

- The id is invalid.
- The type is missing or not one of the three.
- An output name breaks the key rule. An output type is unknown. An output is not a mapping.
- A config key name breaks the key rule.
- `ai`:
  - an invalid placeholder
  - `{{config.<key>}}` for a key that `config` does not declare
  - an empty body
- `command`:
  - any `{{...}}` in the body
  - an empty body
- `group`:
  - no `steps`
  - a non-empty body
  - `outputs` set (D7)
- Any type: a `{{...}}` in `done_check` (D3).
- `run_in` is not `session` or `subagent`.

Warnings:

- `run_in`, `model` or `effort` on a step that is not `ai`
- An empty `description`
- An output without a `description`
- `model` or `effort` on an `ai` step that runs in the session

The registry loop check stays. It now walks `group` steps.

### 4.3 `dump(manifest, body)`

- It writes the YAML frontmatter in this key order: `id`, `description`, `category`, `type`, `outputs`, `done_when`, `done_check`, `config`, `required`, `run_in`, `model`, `effort`, `requires`, `column`, `wait_external`, `steps`.
- It drops empty values, except `required`.
- Then it writes the body. A group has no body.

### 4.4 Registry changes

- `Step.type` has no default. A missing type is caught by `validate`.
- `io()` is replaced by `keys.step_uses` and `keys.step_outputs`.
- `NO_WORKTREE_PIPELINES` is removed. `expand()` always adds `create-worktree`.
- `composite` becomes `group` in `leaves` and in `step_delete.find_users`. The user kind becomes `group`, and the text says "group step".
- `step_delete.script_of` reads `$FACTORY_STEP_DIR/<file>` from the command body, and from `"$FACTORY_STEP_DIR/<file>"`. A file is listed only when it exists in the same `steps/` folder.

## 5. Step runtime

All runtime code lives in `engine.py`. Text rendering is in the new module `lib/factory/render.py`, so the editor preview uses the same code.

### 5.1 Values and environment

- `key_values(task)`: the task state, plus `task_id` and `description` from the task fields.
- `render.fill(text, values, config_values)`:
  - It replaces each `{{key}}` with its value, or `(not set)`.
  - It replaces each `{{config.key}}` with the resolved config value.
- `step_env(ctx, task, step, config_values)`:
  - `FACTORY_TASK`
  - `FACTORY_KEY_<KEY>` for each key value with a valid name
  - `FACTORY_CONFIG_<KEY>`
  - `FACTORY_STEP_DIR`: the folder of the step file
  - A key that is not set has no variable.
  - The `command` step, `done_check` and `factory poll` all use this environment.

### 5.2 `factory next` for an `ai` step in the session

```
<prompt with placeholders replaced>

---
Step 3 of 7: rebase-and-commit > commit
Outputs to set:
- `branch` (text, optional): <description>. Set it with `factory state set branch <value>`.
- `spec` (file): <description>. Set it with `factory state set spec <path>`. Get a path in the artifacts folder with `factory artifact path <name>`.
Done when: <done_when>
If needed:
- If you cannot continue without the user, run `factory block "<question>"`, ask the user, then run `factory unblock` when the user answers.
- Only after the user approves: skip this step with `factory skip`, or go back with `factory goto <step path> --reason "<why>"`.
When the step is done, run `factory done`.
```

- The "Outputs to set" block is shown only when the step has outputs. The "Done when" line is shown only when `done_when` is set.
- `wait_external`: the last line is "When the actions of this step are done, run `factory wait`. The factory tells you when the external event happens."
- Missing config values: the existing "ask the user" text is unchanged.
- No text ever adds `--task`.

### 5.3 Subagent `ai` step

```
Step 4 of 7: review
Run this step in a subagent. Call the Agent tool with:
- model: <model or inherit>
- effort: <effort or inherit>
- prompt:
<<<
<prompt with placeholders replaced>

---
Step 4 of 7: review
Outputs to set: ...
Done when: ...
End with a short report. If you need an answer from the user, say so in the report and stop.
>>>
When the subagent ends, read its report. If it needs the user, ask the user, then run `factory next` again. Otherwise run `factory done`.
```

### 5.4 `command` step

- `factory next` prints:
  - the step line
  - "Run `factory run-command`. It runs the step command and prints its output and its exit code."
  - the outputs, as "The command sets these outputs:"
  - the done-when line
  - "If the exit code is not 0, fix the cause or ask the user, then run `factory run-command` again."
  - the "If needed" lines
  - the done line
- `factory run-command`:
  - It refuses a step that is not `command`.
  - It runs `bash -c <body>` in the task worktree, with `step_env`.
  - It streams the output, then prints `Exit code: <n>`.
  - It saves `task["command_result"] = {"position": <pos>, "exit_code": <n>}`.
  - Its own exit code is the command exit code.
- `factory run-script` is removed.
- `advance` and `goto` clear `command_result`. `request-changes` does not, because it only applies to `user-validation`.

### 5.5 `factory done`

It checks these in order. It stops at the first failure, logs `done_check_failed` with the reason, and stays on the step.

1. Every output not marked `optional` is set and not empty.
   - "The output `<key>` is not set. Set it with `factory state set <key> <value>`."
2. Every `file` output that is set points to an existing path.
   - "The output `<key>` points to a path that does not exist: <path>."
3. `command` step: `command_result` is for this position and has exit code 0.
   - "Run `factory run-command` first." or "The last `factory run-command` exited with code <n>. Fix it and run it again."
4. The `done_check`, when present. Its current text is unchanged.

`factory poll` and `external-done` keep their current behavior. They do not run checks 1 to 3.

### 5.6 `factory state set <key> <value>`

- New function `engine.set_state(ctx, tid, key, value)`.
- When the task has a current step and `key` is a `file` output of that step:
  - The value is resolved against the caller's folder (`ctx.cwd`).
  - A path that does not exist is refused: "The path does not exist: <abs>. The output `<key>` is a file."
  - The absolute path is saved.
- In every other case, the value is saved as given. This includes keys that are not declared outputs.

## 6. No more step assistant, no task without a worktree

Removed:

- `builtin/pipelines/new-step-assistant.yaml`
- `builtin/steps/new-step.md`
- `registry.NO_WORKTREE_PIPELINES`
- the main repository branch of `launch.plan_launch`
- `session.factory_cmd` and its `--task` suffix
- `engine.with_task_flag`, `engine.cmd` suffix and `repo.task_flag`
- the library `--add-dir`
- `HerdrAdapter.open_main_repo`
- the `in_worktree` parameter of every adapter (D9)

Kept:

- `create_tab` for a worktree that Herdr reports as `already_open`
- the `--task` option of every command

`session.start` always uses `task["worktree"]`. A task without a worktree raises a `FactoryError`.

The text of `test_step_assistant.py` changes. It now checks that the pipeline and the step do not exist, and that `factory next` output never contains `--task`.

## 7. Built-in and catalog steps

Every file is rewritten by hand in the new format.

- Built-in steps:
  - `create-task`, `delete-task`, `backlog-add`, `backlog-remove` and `migrate`: `ai` with the same text.
  - `create-worktree`: `ai`, no outputs.
  - `user-validation`: `ai`. It uses `{{config.target}}` and `{{config.artifact_key}}`.
  - `create-task` mentions the input types: a `long-text` input can have several lines. A `file` input is a path.
- Catalog steps:
  - `implement`: `ai` with `{{description}}` and `{{summary}}`.
  - `brainstorm`: `ai` with `{{description}}` and `{{summary}}`. Output `spec` (`file`).
  - `write-plan`: `ai` with `{{spec}}` and `{{config.plan_style}}`. Output `plan` (`file`).
  - `execute-plan`: `ai` with `{{plan}}`.
  - `commit`: `ai` with `{{task_id}}`. Output `branch` (`text`, `optional: true`).
  - `rebase` and `review`: `ai` with `{{config.base_ref}}`. `review` has output `review` (`file`).
  - `create-pr`: `ai` with `{{branch}}`, `{{description}}`, `{{summary}}`, `{{config.forge}}` and `{{config.target_branch}}`. Output `mr_url` (`text`).
  - `address-review-comments`: `ai` with `{{mr_url}}` and `{{config.forge}}`.
  - `wait-review`: `ai` with `{{mr_url}}`. Its `done_check` uses `$FACTORY_KEY_MR_URL`.
  - `wait-qa`: `ai`.
  - `push`: `command` with body `bash "$FACTORY_STEP_DIR/push.sh"`.
  - `run-tests`: `command` with body `bash "$FACTORY_STEP_DIR/run-tests.sh"`.
- The `done_check` lines `test -f "$(factory state get ...)"` and `test -n "$(factory state get mr_url)"` are removed. The checks of section 5.5 replace them.
- The existing test "no catalog file refers to a project-specific skill or tool" stays.

## 8. Migration from version 1 to version 2

- `version.DATA_VERSION` defaults to 2.
- `migrations/1-to-2.py` is self-contained: it does not import the factory code, so later code changes cannot break it. It exposes:
  - `check_repo(factory_dir) -> (errors, warnings)` and `check_library(library_dir) -> (errors, warnings)`
  - `migrate_repo(factory_dir)` and `migrate_library(library_dir)`

### 8.1 Step conversion

- A missing type, `prompt` and `skill` become `ai`. `composite` becomes `group`.
- `script` becomes `command`. The body is `bash "$FACTORY_STEP_DIR/<first line>"`.
- `writes: [a, b]` becomes `outputs: {a: {type: text, description: "", optional: true}, ...}`.
- An `ai` step with a non-empty `reads` gets this text at the end of the body, one line per key:

  ```

  Task keys:
  - <key>: {{<key>}}
  ```

- An `ai` step that declares `config` keys gets this text at the end of the body, after the `Task keys:` block when there is one. Version 1 `factory next` printed every config value, so migrated steps keep them:

  ```

  Config:
  - <key>: {{config.<key>}}
  ```

- A config key name that breaks the key rule refuses the migration, because its placeholder would be invalid.
- `reads` and `writes` are removed. Other fields and the file name stay.

### 8.2 Checks before any change

These checks run on the converted text, in memory.

- Errors:
  - a key name in `reads`, `writes` or pipeline `inputs` that breaks the key rule
  - an `ai` body with a placeholder that would be invalid, or an undeclared `{{config.x}}`
  - a `command` body or a `done_check` with `{{`
  - every other case that `step_format.validate` refuses on the converted step: a bad step id, an empty prompt, a script step with no file name, a composite step without `steps`, a bad `run_in`. The migration script keeps its own copy of these rules. A test runs `step_format.validate` on every converted test step.
  - an unfinished task (not `finished`, not in `archive/`) whose pipeline is `new-step-assistant`. Message: "Task <id> uses the removed pipeline `new-step-assistant`. Delete it with the previous factory version, or move `.factory/tasks/<id>` to `.factory/tasks/archive/<id>`, then migrate again."
- Warnings: a state key with a bad name in an unfinished task (D10).

### 8.3 What it changes

- In the repository: `.factory/steps/*.md`. `.factory/pipelines/*.yaml` stay unchanged, because an input without a type means `text`.
- In the library: `<library>/steps/*.md`.
- Unfinished tasks: only checked. Their saved step lists hold ids and paths, so the version 2 step files apply from their next step.

### 8.4 `migrate.py` changes

- `migrate()` first calls `check_repo` and `check_library` of every script it will run, when the script has them.
- If there is any error, it raises a `FactoryError` with every error. Nothing is changed and no backup is made.
- The warnings go into the result as `warnings` and are printed in the summary.
- The library git check, the backups, the version bump, the `migrated` events and the commit message `Factory library: migrate to version 2` stay.
- The `migrate` built-in step shows the warnings.

## 9. Pipelines, checks and launch

### 9.1 Inputs

- `inputs: {name: {type, description}}`. A missing type means `text`.

### 9.2 `pipeline_check.check` changes

- `ALWAYS_AVAILABLE` is removed. `keys.available` replaces it.
- Error: an input name breaks the key rule. Error: an input type is unknown.
- Warning (replaces the `reads` warning): "Step `<leaf>` uses `<key>`, which no input, earlier step or factory key sets." It is checked per leaf, against the keys available before that leaf. A key that is one of the leaf's own outputs gives no warning, for example a `done_check` that reads the output the step sets.
- Warning: "The key `<key>` is set with two types: <type> (<source>) and <type> (<source>)." It is shown once per key.
- The other checks stay.

### 9.3 Launch

- `plan_launch` builds `report["inputs"]`, the values to save:
  - A `file` input with a value is resolved against `ctx.main` when it is relative.
  - If the path does not exist, the report gets the error "The input `<name>` is a path that does not exist: <abs>."
  - The absolute path is saved.
- `launch` saves `report["inputs"]` in the state.
- `pipeline_store.list_pipelines` rows get `inputs: {name: {type, description}}`, so the orchestrator knows the types.
- Dashboard Launch form:
  - `long-text`: a `textarea`
  - `text`: a text field
  - `file`: a text field with the hint "Path, absolute or relative to the main repository"
  - Dry run errors are already shown in red.
- The orchestrator `create-task` step:
  - For a `long-text` input, it tells the user that several lines are allowed.
  - For a `file` input, it asks for a path.

### 9.4 Commands

`factory pipeline keys <id> [--at <position>] [--json]`:

- Text output: one line per key, `<name> (<type>) from <source>, <always set|maybe set>`.
- JSON output: the rows.

## 10. Step editor

### 10.1 Server module `lib/factory/step_store.py`

| Function | Route | Result |
|---|---|---|
| `form_data(ctx)` | `GET /api/step-form` | categories, board columns, `library` (bool), factory keys, key types, the step ids of every level (hidden ones too) |
| `check(ctx, manifest, body)` | `POST /api/steps/check` | `{errors, warnings, uses, outputs}` from `step_format.validate` and `keys` |
| `preview(ctx, manifest, body)` | `POST /api/steps/preview` | `{text}`: the `factory next` text, each placeholder shown as `<key>` or `<config.key>`, step line `Step: <id>` |
| `impact(ctx, sid)` | `POST /api/steps/impact` | `{pipelines, groups, tasks, warnings}`. It reuses `step_delete.find_users`. The warning for a generic step is "Other repositories that use this library are not checked." |
| `save(ctx, manifest, body, level, mode)` | `POST /api/steps/save` | `{path, level, warnings, library_commit}` |
| `keys.available` | `POST /api/pipelines/keys` with `{data, at}` | key rows |

`save` modes:

- `new`:
  - The id must be valid and unused at every level, hidden steps included. Otherwise it returns 409 "A step named `<id>` already exists."
  - `level` is `local` or `generic`. Writes `<root>/steps/<id>.md`.
- `edit`:
  - The step in use with this id must be at `level`, and not built-in. Otherwise: "Built-in steps cannot be edited. Copy the step to local instead."
  - The id cannot change. It writes the existing file path.
- `copy-local`:
  - The id must exist at the generic or built-in level, and no local step may have it. It writes `.factory/steps/<id>.md`.
- Errors from `validate` block the save with 400. Warnings are returned.
- Generic save in a git library: `library_commit = {message: "Factory library: add|update step <id>", paths: [<file>]}`.
- The form never writes a script file.

Routes `POST /api/steps/...` sit before the existing `/api/steps/<id>` routes. The token, `Host` and `Origin` checks apply as for all routes.

`step_detail` returns `uses`, `outputs` and `children` in place of `reads` and `writes`.

### 10.2 CLI

- `factory step edit [<id>]`:
  - It checks that the id exists.
  - It starts the server and opens `/editor?step=<id>`, or `/editor?new_step=1`.
  - It prints the URL.
- The menu action "Create a new step" (`new-step`): the orchestrator runs `factory step edit` and tells the user the form is open in the browser.

### 10.3 Page `editor.html`

The page uses plain JS and no library, the same as the current page.

- A "New step" button above the available steps.
- Detail panel:
  - the computed `uses`
  - `outputs` with their types
  - for a group, the child steps, each one clickable
  - buttons:
    - "Edit" for local or generic
    - "Copy to local" for generic or built-in
    - "Duplicate" for any step
    - "Delete" as today
- Selecting a pipeline step shows "Keys available here" from `/api/pipelines/keys` at its position.
- Pipeline inputs get a type list.
- The step form is a full-height overlay.
  - Left side: the fields of the requirements.
    - `category`: a list plus "New category" with a text field.
    - Level radio buttons, only for a new step.
    - `run_in`, `model` and `effort`: shown only for `ai`. `model` is `""`, `opus`, `sonnet` or `haiku`. `effort` is `""`, `low`, `medium`, `high` or `max`.
    - `column`: the board columns plus none.
    - `requires`: a list of rows.
    - `config` and `outputs`: tables of rows.
    - Body: a textarea. For a group, a child list: add from a list of steps that are not hidden, drag to reorder, remove.
  - Right side:
    - the key list: keys at the pipeline position when the form was opened from a pipeline step, otherwise the factory keys, plus `{{config.<key>}}` for each config row
    - Clicking a key inserts `{{key}}` (ai) or `$FACTORY_KEY_<KEY>` (command) at the cursor.
    - "Preview", for `ai` only
    - the live check result
  - Save:
    - When editing, it first shows the impact and asks to confirm.
    - Then it calls `save`, shows the warnings, and reloads the steps.
    - For a generic step, it shows the library commit offer with "Commit" and "Not now", like delete does today.
- `?step=<id>` opens the form on that step in `edit` mode, or in `copy-local` mode when the step is built-in. `?new_step=1` opens an empty form.

## 11. Orchestrator and README

- `SKILL.md`:
  - "Create a new step" runs `factory step edit`.
  - "Launch" explains the input types.
  - "Migrate" shows the warnings.
- `README.md`:
  - Concepts: key types, factory keys, the three step types, placeholders, outputs, `FACTORY_KEY_` and `FACTORY_STEP_DIR`.
  - Tutorial step 4 "Create a step" uses the step form.
  - Reference: `factory pipeline keys`, `factory step edit`, `factory run-command`. `factory run-script` is removed.
  - The pipeline editor section describes the step form and the keys panel.
  - The step manifest fields are updated.
  - Simple English and short sentences.

## 12. Testing

- The test setup stays: `inited` fixture, test repository, test library in its own git repository, fake adapter.
- The `write_step` helper default type becomes `ai`.
- The existing tests that use `prompt`, `script`, `reads`, `writes` or the main-repository task are updated. The report lists each one and why.
- New test modules:
  - `test_keys.py`: key rule, placeholders, env refs, uses and outputs of each type, `available` with maybe set and latest wins
  - `test_step_format.py`: every load error and warning, `dump` round trip, a group loop is refused
  - `test_runtime_v2.py`:
    - `next` output for an `ai` step: replaced placeholders, `(not set)`, the footer with every output
    - the subagent text
    - `command` env and `run-command`
    - the four checks of `done`
    - `state set` for a `file` output
    - group full path
    - no `--task` in any printed text
  - `test_pipeline_keys.py`: CLI text and JSON, `--at`, the two new warnings
  - `test_typed_inputs.py`: a `file` input that does not exist is a dry run error, a relative path is saved as absolute, and the inputs show in the pipeline list
  - `test_migrate_v2.py`:
    - converts every old type, `reads`, `writes` and a script step
    - an `ai` step with config keys gets the `Config:` block after the `Task keys:` block, and `factory next` prints the config values
    - the migrated pipeline runs to the end with the fake adapter
    - a bad key name refuses with nothing changed
    - a `new-step-assistant` task refuses with nothing changed
    - a bad state key is a warning
  - `test_step_editor_api.py`:
    - save a new local step
    - save a generic step and get the commit offer
    - a duplicate id gets 409
    - a built-in edit is refused
    - copy to local
    - impact
    - preview
    - check
    - keys route
    - no token gets 401
    - `factory step edit` prints the URL
  - `test_catalog.py` and `test_builtin.py`: every built-in and catalog step loads with the version 2 rules, and the assistant is gone.
- Report: `tests/report_step_editor.py` reads `verification/software-factory/step-editor-junit.xml` and writes `step-editor-report.md`. It has one section per milestone, the full suite, and the list of updated tests.
- Manual check list: `verification/software-factory/step-editor-manual-check.md`, with the items of the requirements.
- `tests/e2e_herdr.py` is moved to `command` steps. It needs Herdr, so it is not run in this build.

## 13. Milestones

1. Step format and runtime: sections 3 (`step_uses`, `step_outputs`), 4, 5, 6, 7 and 8.
2. Available keys: `keys.available`, section 9, the menu and SKILL launch text, the dashboard Launch form.
3. Step editor: section 10, the menu action, section 11.

## 14. Out of scope

- No value check for `text` and `long-text` inputs.
- No change to `factory poll` beyond the new environment.
- No new event types.
- The form never writes script files.
