# Authoring skill: design

Source: `prompts/factory_authoring_skill.md`. Context: `prompts/factory_skill_creation.md` (section "Authoring skill").

## 1. Goal

- A user gives an AI agent a request or a prompt file that describes a pipeline. The agent writes valid step and pipeline files.
- The agent does not need the orchestrator, the local server, the browser or the README.
- The agent checks its files with `factory pipeline check` and `factory pipeline keys`, and fixes them until the check has no error.

Not in scope:
- No new CLI command.
- No change to the step format, the pipeline format or the factory code under `lib/`.
- No change to the `software-factory` skill menu.
- No new tutorial step in the README.

## 2. Deliverables

All paths are under `software-factory/`.

| File | Change |
| --- | --- |
| `skills/factory-authoring/SKILL.md` | New. The skill: frontmatter, workflow, rules, format reference, examples. |
| `README.md` | New section "Authoring skill" in Reference, and one line in "Install and prerequisites" on how to call it. |
| `tests/test_authoring_skill.py` | New. The CLI tests of section 7. |
| `tests/report_authoring_skill.py` | New. Writes the verification report. |

Verification files, under `verification/software-factory/`:
- `authoring-skill-report.md`
- `authoring-skill-junit.xml`
- `authoring-skill-manual-check.md`

## 3. Loading and calling

- The plugin finds every `skills/<name>/SKILL.md` by itself. `plugin.json` does not change.
- Frontmatter:
  - `name: factory-authoring`
  - `description`: create or change Software Factory pipelines and steps (`.factory/steps`, `.factory/pipelines`, library steps). Use when the user asks to create, change or fix a factory pipeline or step, or gives a file that describes one, for example "Implement `prompts/crash-pipeline.md`". The key use case comes first. The text stays well under the 1,536 characters that Claude Code shows.
  - `argument-hint: <prompt file or request>`
- Calling it:
  - Claude loads it from the description.
  - The user calls it with `/factory-authoring <file or request>`. The full name `/software-factory:factory-authoring` works too. The README names both. Claude Code documents the short name as working "unless another command already uses that name".
  - The text after the command reaches the skill as `$ARGUMENTS`.
- No orchestrator: the skill never runs `factory menu`, `factory terminal check`, `factory dashboard`, `factory pipeline edit` or `factory step edit`. The only exception is the final report: it tells the user that they can open `factory pipeline edit <id>` to review.

### 3.1 The `factory` command

- The orchestrator creates the link `~/.local/bin/factory` on its first run. A user who never ran it may not have the link.
- The skill: "Run `command -v factory`. If it prints nothing, use `<this skill's base directory>/../../bin/factory` everywhere this skill says `factory`."
- The skill never creates the link. That is a change outside the repository.

## 4. Skill content

One file. The DoD asks for everything in the skill. A second reference file in the skill folder would make the agent read two files, so the reference stays in `SKILL.md`. Expected size: about 350 lines.

### 4.1 Workflow (the 9 steps of the prompt)

1. **Find the repository.**
   - The main repository is the parent of `git rev-parse --path-format=absolute --git-common-dir`. This also works inside a worktree.
   - If `.factory/factory.yaml` does not exist there, stop. Tell the user to add the factory to the repository first, with the menu action "Init the factory" of `/software-factory:software-factory`.
   - Run `factory version check --json`. If `state` is not `same`, stop. Tell the user to start the orchestrator, which runs the migration (`older`), or to update the plugin (`newer`). Reason: with the wrong data version, step files of the other format do not load.
2. **Read the request.**
   - Ask the user only what the file or the request does not say.
   - When the level is not given, use local.
3. **List what exists.**
   - Run `factory step list --all --json` and `factory pipeline list --json`.
   - Reuse a step that does the job.
   - Never create a step with the id of an existing step at the same level. The list shows only the step that wins. So before writing a file, also check that the target file does not exist.
   - A step with the same id at a higher level is an override, for example a local `commit` over the generic `commit`. Do it only when the user asks, and say so.
4. **Plan the key flow.**
   - For each step, list the keys it uses and where each one comes from: an input, an output of an earlier step, or a factory key.
   - `summary` is "maybe set". A step that needs it must work when it is `(not set)`.
5. **Write the files.** The step files first, then the pipeline files. Use the format reference.
6. **Check.**
   - Run `factory pipeline check <id>` for each new or changed pipeline. After a step change, run it for every pipeline listed by `factory pipeline list --json`. No command lists the pipelines that use a step, and checking all of them also covers group steps.
   - An error stops the check. A step file that does not load gives `<path>: <problem>`. Fix the file and run the check again, until no error is left.
   - Read each warning. Fix it, or tell the user why it stays.
   - Run `factory pipeline keys <id> --at <position>` for each position. Check that each key a step uses is in the list before that step.
7. **Generic changes:** tell the user that other repositories that use the library are not checked.
8. **Library commit:** for new or changed generic files, show the files and the message, then run `factory library commit "<message>" <paths...>` only after the user approves. The message is `Factory library: <action> <kind> <id>`, with the factory's actions `add`, `update` or `delete`. Examples: `Factory library: add step <id>`, `Factory library: update pipeline <id>`. Never `change`. Never push. Local files are never committed, because `.factory/` is excluded from git.
9. **Report:** the files created or changed, their level, and the check results. Tell the user they can review a pipeline with `factory pipeline edit <id>`.

### 4.2 Rules

- Never edit a built-in step or pipeline file, under the plugin's `builtin/` folder. To change a built-in step, write a local step with the same id.
- Never edit files under `.factory/tasks/`.
- Never change a step that an unfinished task uses without telling the user first:
  - `factory tasks --json` lists the tasks. Unfinished means `status` is not `finished`.
  - For each unfinished task, read `.factory/tasks/<id>/task.json`, read only. Its `steps` list holds the saved step entries.
  - The task uses a step when the step id is in the `path` of any entry, not only in `id`. This covers group steps: a group's id is in the `path` of each of its children.
  - A task uses the changed step from its next step on.
- A generic pipeline uses only generic or built-in steps. So each new step of a generic pipeline is generic too. If not, `factory pipeline check` warns "This generic pipeline uses the local step `<id>`".
- A step that calls a skill is an `ai` step. Its prompt calls the skill, and `requires` lists it, for example `requires: [/superpowers:writing-plans]`.
- Ids and key names follow the rules of section 4.3. The file name is `<id>.md` or `<id>.yaml`.

### 4.3 Format reference

The source of truth is the factory code. Each item comes from it.

**Where files go**
- Local: `<main repo>/.factory/steps/<id>.md` and `<main repo>/.factory/pipelines/<id>.yaml`.
- Generic: `<library>/steps/<id>.md` and `<library>/pipelines/<id>.yaml`. `<library>` is the `library` key of `.factory/factory.yaml`.
- Built-in steps ship with the plugin. Never change them.
- Local wins over generic. Generic wins over built-in.
- A script for a `command` step goes next to the step file, in the same `steps/` folder.

**Ids** (`step_format.STEP_ID_RE`)
- Step ids and pipeline ids: lowercase letters, digits, `-` and `_`. They start with a letter. At most 64 characters.
- Good: `fix-crash`, `run_tests2`. Bad: `Fix-Crash`, `2fix`, `fix crash`.

**Key names** (`keys.KEY_RE`)
- Inputs, outputs and config keys: lowercase letters, digits and `_`. They start with a letter. No `-`.
- Good: `crash_log`, `plan2`. Bad: `crash-log`, `CrashLog`.

**Key types**
- `text` (one line), `long-text` (several lines), `file` (an absolute path).
- A missing type means `text`.
- Factory keys: `task_id` (always set), `description` (always set), `summary` (maybe set: only for a task started from a backlog entry).

**Step file**
- YAML frontmatter between two `---` lines, then the body.
- Every manifest field (`step_format.FIELD_ORDER`), with its allowed values:

| Field | Values | Applies to |
| --- | --- | --- |
| `id` | step id | all |
| `description` | one line | all. Empty: warning. |
| `category` | free text | all |
| `type` | `ai`, `command`, `group` | all |
| `outputs` | map of key name to `type`, `description`, `optional` | `ai`, `command` |
| `done_when` | text shown to the agent | `ai`, `command` |
| `done_check` | shell command. Exit 0 means done. Uses `"$FACTORY_KEY_<KEY>"`. No `{{...}}`. | `ai`, `command` |
| `config` | map of key name to `description` and optional `default` | `ai`, `command` |
| `required` | `true` or `false`. `true`: `factory skip` is refused. | `ai`, `command` |
| `run_in` | `session` (default) or `subagent` | `ai` |
| `model` | model name, for example `opus` | `ai` with `run_in: subagent` |
| `effort` | for example `low`, `high` | `ai` with `run_in: subagent` |
| `requires` | list of skills (`/plugin:skill`) or programs on PATH | `ai`, `command` |
| `column` | a board column of `columns` in `.factory/factory.yaml` | `ai`, `command` |
| `wait_external` | `true`: the step ends with `factory wait` | `ai`, `command` |
| `steps` | list of child step ids | `group` only |

- Empty fields can be left out.
- A `group` step uses only `id`, `description`, `category`, `type` and `steps`. The factory reads the other fields from its child steps.

**`ai` step**
- The body is the exact prompt.
- `{{<key>}}` becomes the task key value. `{{config.<key>}}` becomes the config value. A key that is not set becomes `(not set)`.
- `{{config.<key>}}` needs the key in `config`. If not, the step does not load.
- Single braces `{like this}` stay text.
- Do not write an outputs list or "run factory done" in the prompt. The factory adds a footer with the outputs, `factory state set` for each one, `done_when` and the end line.

**`command` step**
- The body is a shell command. `factory run-command` runs it with `bash` in the task worktree.
- It gets each task key as `"$FACTORY_KEY_<KEY>"`, each config value as `"$FACTORY_CONFIG_<KEY>"` and the step folder as `"$FACTORY_STEP_DIR"`. `<KEY>` is the key name in upper case. Always use double quotes.
- No `{{...}}` in a command. The step does not load.
- A long command goes in a script next to the step: `bash "$FACTORY_STEP_DIR/<id>.sh"`.
- The command sets its own outputs with `factory state set <key> <value>`. A `file` output gets its path from `factory artifact path <name>`. The session never sets them.
- Exit code 0 means success.

**`group` step**
- `steps` lists child step ids. A child can be a group.
- No body. No `outputs`: they come from the children.
- No loop: a group cannot contain itself at any depth.

**Outputs and `factory done`**
- Each output: `type`, `description`, and `optional: true` when the step may leave it unset.
- `factory done` checks, in this order:
  1. Every output that is not optional is set.
  2. Every `file` output points to a path that exists.
  3. For a `command` step, the last `factory run-command` exited with 0.
  4. The `done_check`, when there is one.

**Config and `with`**
- `config` declares the values a step needs, each with a `description` and an optional `default`.
- A value comes from, in order: the `with` of the pipeline entry, the value saved in `.factory/config.yaml`, then the `default`.
- When no value exists: the launch dry run asks only for the config of `create-worktree`. For any other step, `factory next` asks the user for the missing value when the step starts.
- `with` on a group entry applies to each child step that declares that config key.

**Pipeline file**
- Fields:
  - `id`: the pipeline id, the same as the file name.
  - `description`.
  - `inputs`: a map of key name to `type` and `description`. The launch asks for them. A relative `file` path is resolved from the main repository.
  - `steps`: a list. Each entry is a step id, or a map with `id`, `with`, `model`, `effort`, `column`.
  - `claude`: `model` and `effort` of the task session.
  - `start_column`: the board column of a new task.
- `create-worktree`: the factory adds it as the first step. List it only to set its `with` values, and then only as the first step.

**Examples**
- Each example is a `####` heading with its file path, then one fenced block with the whole file. The test of section 7 reads them in this form.
- The examples are one flow, a crash fix:
  - `.factory/steps/collect-crash.md`: a `command` step. Config `lines`, default `200`. Output `crash_report` (`file`). It runs `bash "$FACTORY_STEP_DIR/collect-crash.sh"`.
  - `.factory/steps/collect-crash.sh`: it reads `"$FACTORY_KEY_CRASH_LOG"` and `"$FACTORY_CONFIG_LINES"`, writes the last lines to `"$(factory artifact path crash-report.md)"`, then runs `factory state set crash_report "<path>"`.
  - `.factory/steps/fix-crash.md`: an `ai` step. It uses `{{crash_report}}`, `{{description}}` and `{{config.test_hint}}`. Output `fix_summary` (`long-text`). It has `done_when`.
  - `.factory/steps/crash-triage.md`: a `group` step with `steps: [collect-crash, fix-crash]`.
  - `.factory/pipelines/crash-fix.yaml`: an input `crash_log` (`file`), the entry `crash-triage` with `with: {lines: 100}`, then the built-in `user-validation`.
- This covers an input, an output used by a later step (`crash_report`) and a config value (`lines`, `test_hint`).

## 5. README

- "Install and prerequisites": one line. To write pipelines and steps with an agent, call `/factory-authoring` in any Claude session.
- New Reference section "Authoring skill":
  - What it does: it writes step and pipeline files from a request or a prompt file, then checks them with `factory pipeline check`.
  - How to call it: Claude loads it from your request, or you call `/factory-authoring <file or request>`. The full name is `/software-factory:factory-authoring`.
  - Example: a short prompt file `prompts/crash-pipeline.md`, and the request "Implement `prompts/crash-pipeline.md`".
  - It writes local files unless you ask for generic. It offers the library commit for generic files. It needs `.factory/` in the repository.
- Simple English, short sentences.

## 6. Error handling in the skill

| Case | Behavior |
| --- | --- |
| No `.factory/factory.yaml` | Stop. Tell the user to init the factory. |
| Data version not `same` | Stop. Tell the user to migrate or to update the plugin. |
| `factory` not on PATH | Use the absolute path of section 3.1. |
| A step file does not load | `factory pipeline check` names the file. Fix it and check again. |
| A level is not given | Local. |
| Generic asked, no library | `library` is missing in `.factory/factory.yaml`. Stop and tell the user. |
| The library is not in git | Skip the library commit and say so. |
| A changed step is used by an unfinished task | Tell the user before the change. |

## 7. Tests

Setup: the existing fixtures of `tests/conftest.py`. A test repository with `factory init`, a test library in its own test git repository. Never a real library or a real `.factory/`.

New file `tests/test_authoring_skill.py`:
- **T1** The file exists. The frontmatter is YAML with `name: factory-authoring`, a `description` that names pipelines and steps, and an `argument-hint`.
- **T2** Every `factory` command in a code span or a fenced block of the skill exists in the CLI. It reuses `check` and `command_names` of `tests/test_docs.py`.
- **T3** The examples:
  - The test reads each `####` path heading and the fenced block after it, and writes the file into a test repository. Paths start with `.factory/`.
  - `Registry.load` loads the steps.
  - `factory pipeline check crash-fix --json` prints `[]`: no error and no warning.
  - `factory pipeline keys crash-fix` lists `crash_report` from the step `collect-crash`.
  - At least one example of each type: `ai`, `command`, `group`.
- **T4** Every field in `step_format.FIELD_ORDER` appears in backticks in the skill. Every pipeline field (`id`, `description`, `inputs`, `steps`, `claude`, `start_column`), every pipeline entry field (`id`, `with`, `model`, `effort`, `column`), the output fields (`type`, `description`, `optional`) and the config fields (`description`, `default`) appear in the skill. The pipeline lists come from `registry.Pipeline` and `registry.Registry.expand`, because the code has no constant for them.
- **T5** Every built-in step id named in the skill exists in `builtin/steps/`. Names are found by the pattern "built-in step `<id>`" and by the example pipeline entries that are not example steps.
- **T6** The README has the "Authoring skill" section with `/factory-authoring` and an example prompt file.
- The `software-factory` skill is not changed. The report shows this with `git diff master -- skills/software-factory/SKILL.md`, which must be empty. A test adds nothing here.

Existing tests: no behavior changes, so none should change. `test_docs::test_skill_and_builtin_commands_exist` stays as is. T2 covers the new skill.

Report: `tests/report_authoring_skill.py`, on the model of `report_step_editor.py`. It reads `authoring-skill-junit.xml`, lists the tests of `test_authoring_skill`, the full suite result and the updated tests (expected: none), and ends with the DoD mapping.

## 8. Manual check list

`verification/software-factory/authoring-skill-manual-check.md`, for the user, in a test repository with a test library:
1. In a normal Claude session, not the orchestrator, ask "Implement `<prompt file>`". The file describes a pipeline with one `ai` step, one `command` step with a `file` output, and a pipeline input. Expected: the skill loads, the files are written, `factory pipeline check` passes.
2. Launch that pipeline and run it to the end.
3. Ask for a generic step. Expected: the library commit is offered, with a `Factory library: ...` message.
4. Ask to change a step that a pipeline uses. Expected: the agent runs `factory pipeline check` on every pipeline of `factory pipeline list --json`.
5. Call `/factory-authoring <request>` directly. Expected: the skill runs with the request.

## 9. Risks

- **R1** The short command `/factory-authoring` works only when no other command has that name. The README also gives the full name.
- **R2** The skill is long. The agent might skip parts of it. The workflow comes first in the file and the reference comes after it.
- **R3** The format reference can drift from the code. T3 and T4 catch the main drifts: examples that stop loading, and fields that are not described.
- **R4** T5 finds built-in ids only by pattern. A built-in id written in another form is not checked.
