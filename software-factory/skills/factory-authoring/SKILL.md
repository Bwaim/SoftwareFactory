---
name: factory-authoring
description: Create or change Software Factory pipelines and steps by writing their files directly (.factory/steps, .factory/pipelines, library steps and pipelines), then check them with `factory pipeline check`. Use when the user asks to create, change or fix a factory pipeline or step, or gives a file that describes one, for example "Implement prompts/crash-pipeline.md". Works without the factory orchestrator, the local server or the browser.
argument-hint: <prompt file or request>
---

# Factory authoring

You write Software Factory step files and pipeline files, then you check them with the factory, the same way code is checked with tests.

Request: $ARGUMENTS

`factory` below is the factory CLI. Run `command -v factory`. If it prints nothing, use `<this skill's base directory>/../../bin/factory` everywhere this skill says `factory`. Never create a link for it.

## Workflow

1. **Find the repository.**
   - The main repository is the parent folder of `git rev-parse --path-format=absolute --git-common-dir`. This also works inside a worktree.
   - If `<main repo>/.factory/factory.yaml` does not exist, stop. Tell the user to add the factory to the repository first: run `/software-factory:software-factory` and choose "Init the factory".
   - Run `factory version check --json`. If `state` is `older`, stop and tell the user to start the orchestrator, which runs the migration. If `state` is `newer`, stop and tell the user to update the factory plugin.
2. **Read the request.**
   - Read the request or the prompt file.
   - Ask the user only what the file or the request does not say.
   - When the level is not given, use local.
   - For a generic file, read the `library` key of `.factory/factory.yaml`. If it is missing, stop and tell the user that no library is set.
3. **List what exists.**
   - Run `factory step list --all --json` and `factory pipeline list --json`.
   - Reuse an existing step when it does the job.
   - Never create a step with the id of an existing step at the same level. The list shows only the step that wins, so also check that the target file does not exist before you write it.
   - A local step with the id of a generic or built-in step overrides it. Do this only when the user asks for it, and say so.
4. **Plan the key flow.**
   - For each step, list the keys it uses.
   - Each key must come from a pipeline input, an output of an earlier step, or a factory key.
   - `summary` is maybe set. A step that uses it must still work when it is not set.
   - In an `ai` step, a key that is not set becomes `(not set)`. In a `command` step, the variable is not set.
5. **Write the files.** Write the step files first, then the pipeline files. Follow the format reference below.
6. **Check.**
   - Run `factory pipeline check <id>` for each new or changed pipeline.
   - After a step change, run it for every pipeline listed by `factory pipeline list --json`. No command lists the pipelines that use a step, and checking all of them also covers group steps.
   - A step file that does not load stops the check with `<path>: <problem>`. Other errors are listed together. Fix the errors and run the check again, until there is no error.
   - Fix a load error right away. While a step file does not load, no factory command works, and running tasks cannot go on.
   - Read each warning. Fix it, or tell the user why it stays.
   - Run `factory pipeline keys <id> --at <position>` for the position of each step. Check that each key the step uses is in the list.
     - The position is the 1-based number of the entry in the `steps` list of the pipeline. A listed `create-worktree` counts.
     - For a step inside a group, also count the outputs of the earlier child steps of that group.
     - `factory pipeline check` already warns about a key that is really missing, also inside groups.
   - The check sees the keys of a command line, not the keys used inside a script file. Check the keys of a script by hand.
7. **Generic changes.** Tell the user that other repositories that use the library are not checked.
8. **Library commit.** For new or changed generic files:
   - Show the files and the message `Factory library: <action> <kind> <id>`. The action is `add`, `update` or `delete`. The kind is `step` or `pipeline`. Examples: `Factory library: add step fix-crash`, `Factory library: update pipeline crash-fix`.
   - Run `factory library commit "<message>" <paths...>` only after the user approves.
   - If the library is not in a git repository, skip the commit and say so.
   - Never push.
   - Local files are never committed. `.factory/` is excluded from git.
9. **Report.** List the files you created or changed, their level, and the check results. Tell the user they can review a pipeline with `factory pipeline edit <id>`.

## Rules

- Never edit a built-in step or pipeline. Built-in files are in the `builtin/` folder of the plugin. To change a built-in step, write a local step with the same id.
- Never edit files under `.factory/tasks/`.
- Never change a step that an unfinished task uses without telling the user first.
  - `factory tasks --json` lists the tasks. A task is unfinished when its `status` is not `finished`.
  - For each unfinished task, read `.factory/tasks/<id>/task.json`. Only read it. Its `steps` list holds the saved step entries.
  - The task uses a step when the step id is in the `path` of any entry, not only in its `id`. A group id is in the `path` of each of its child steps.
  - The task uses the changed step from its next step on.
- A generic pipeline uses only generic or built-in steps. So each new step of a generic pipeline is generic too. If not, `factory pipeline check` warns "This generic pipeline uses the local step".
- A step that calls a skill is an `ai` step. Its prompt calls the skill, and `requires` lists it. Example: `requires: [/superpowers:writing-plans]`.
- The file name is the id: `<id>.md` for a step, `<id>.yaml` for a pipeline.
- Never use `ticket` as an output key. It is the Jira ticket key: the dashboard shows it as the card title and builds its link from `ticket_url`.

## Format reference

### Where files go

- Local: `<main repo>/.factory/steps/<id>.md` and `<main repo>/.factory/pipelines/<id>.yaml`.
- Generic: `<library>/steps/<id>.md` and `<library>/pipelines/<id>.yaml`. `<library>` is the `library` key of `.factory/factory.yaml`.
- Built-in steps ship with the plugin. Never change them.
- Local wins over generic. Generic wins over built-in.
- A script of a `command` step goes next to the step file, in the same `steps/` folder.

### Ids and key names

- A step id or a pipeline id uses lowercase letters, digits, `-` and `_`. It starts with a letter. It has at most 64 characters.
  - Good: `fix-crash`, `run_tests2`. Bad: `Fix-Crash`, `2fix`, `fix crash`.
- A key name (input, output or config key) uses lowercase letters, digits and `_`. It starts with a letter. No `-`.
  - Good: `crash_log`, `plan2`. Bad: `crash-log`, `CrashLog`.

### Key types

- `text`: one line.
- `long-text`: several lines.
- `file`: an absolute path.
- A missing type means `text`.
- Factory keys:
  - `task_id`: always set.
  - `description`: always set. The task description.
  - `summary`: maybe set. It is set only when the task starts from a backlog entry.

### Step file

A step file is YAML frontmatter between two `---` lines, then the body.

| Field | Values | Applies to |
| --- | --- | --- |
| `id` | the step id | all |
| `description` | one line. Empty gives a warning. | all |
| `category` | free text, for example `build` | all |
| `type` | `ai`, `command` or `group` | all |
| `outputs` | map of key name to `type`, `description` and `optional` | `ai`, `command` |
| `done_when` | text shown to the agent | `ai`, `command` |
| `done_check` | shell command. Exit code 0 means done. Use `"$FACTORY_KEY_<KEY>"`, never `{{...}}`. | `ai`, `command` |
| `config` | map of key name to `description` and an optional `default` | `ai`, `command` |
| `required` | `true` or `false`. With `true`, `factory skip` is refused. | `ai`, `command` |
| `run_in` | `session` (the default) or `subagent` | `ai` |
| `model` | a model name, for example `opus` | `ai` with `run_in: subagent` |
| `effort` | for example `low` or `high` | `ai` with `run_in: subagent` |
| `requires` | list of skills (`/plugin:skill`) or programs on PATH | `ai`, `command` |
| `column` | a board column from `columns` in `.factory/factory.yaml` | `ai`, `command` |
| `wait_external` | `true`: the step ends with `factory wait` | `ai`, `command` |
| `exclusive` | Name of a resource that only one task at a time can use, like `android-emulator`. Steps with the same name share it. Lowercase letters, digits, `-`, `_` | `ai`, `command` |
| `steps` | list of child step ids | `group` |

- Leave out empty fields.
- A `group` step uses only `id`, `description`, `category`, `type` and `steps`. The factory reads the other fields from its child steps.
- `model` or `effort` on a step that runs in the session gives a warning.

### `ai` step

- The body is the exact prompt.
- `{{<key>}}` becomes the value of the task key. `{{config.<key>}}` becomes the config value.
- A key that is not set becomes `(not set)`.
- `{{ key }}` with spaces is not a placeholder. The step does not load.
- `{{config.<key>}}` needs the key in `config`. If not, the step does not load.
- Single braces, like `{name}`, stay text.
- Do not list the outputs or write "run factory done" in the prompt. The factory adds a footer with each output, the `factory state set` command for it, the `done_when` text and the end line.

### `command` step

- The body is a shell command. `factory run-command` runs it with `bash` in the task worktree.
- The command gets:
  - each task key as `"$FACTORY_KEY_<KEY>"`,
  - each config value as `"$FACTORY_CONFIG_<KEY>"`,
  - the folder of the step file as `"$FACTORY_STEP_DIR"`.
- `<KEY>` is the key name in upper case. Always put these variables in double quotes.
- A key that is not set is not in the environment. Use `"${FACTORY_KEY_<KEY>:-}"` for `summary` and for optional outputs.
- No `{{...}}` in a command. The step does not load.
- Put a long command in a script next to the step, and run it with `bash "$FACTORY_STEP_DIR/<id>.sh"`.
- The command sets its own outputs with `factory state set <key> <value>`. For a `file` output, get a path with `factory artifact path <name>`. The session never sets them.
- Exit code 0 means success.

### `group` step

- `steps` lists the child step ids, in order. A child can be a group.
- No body.
- No `outputs`. They come from the child steps.
- No loop: a group cannot contain itself at any depth.

### Exclusive steps

- `exclusive: <name>` marks a step that uses a resource shared by all tasks, like an emulator. Only one task at a time runs a step with this name. Steps with the same name share the resource.
- The first task takes the resource when its step starts. Other tasks wait in a queue. `factory next` tells them to end their turn. The factory starts them when the resource is free.
- A task keeps the resource until it leaves the step, or until it is released. It leaves the step on `factory done`, `factory skip`, `factory goto`, a loop jump, the end of the pipeline and `factory delete`. If the next current step has the same exclusive name, the task keeps the resource. It also keeps it while it is paused.
- Before a long wait for the user, the session frees it with `factory exclusive release <name>`. It takes it again with `factory exclusive acquire <name>`. The step footer says so.
- A stuck holder can be freed with `factory exclusive release <name> --force`.
- The name is per repository. Use it only for a resource that cannot be shared.

### Outputs and `factory done`

- Each output has a `type`, a `description`, and `optional: true` when the step may leave it unset.
- `factory done` checks, in this order:
  1. Every output that is not optional is set.
  2. Every `file` output points to a path that exists.
  3. For a `command` step, the last `factory run-command` exited with 0.
  4. The `done_check`, when there is one.

### Config and `with`

- `config` declares the values a step needs. Each one has a `description` and an optional `default`.
- A value comes from, in this order:
  1. `with` in the pipeline entry,
  2. the value saved in `.factory/config.yaml`,
  3. the `default`.
- When no value exists:
  - The launch dry run asks only for the config of `create-worktree`.
  - For any other step, `factory next` asks the user for the value when the step starts.
- `with` on a group entry applies to each child step that declares that config key.
- The check does not see a `with` key that the step does not declare. Check each `with` key by hand against the step `config`.

### Pipeline file

- `id`: the pipeline id. It is also the file name.
- `description`: one line.
- `worktree`: required. Set `true` or `false`.
  - `true`: each task gets its own git worktree.
  - `false`: the task runs in the workspace root. There is no worktree and no branch.
  - A pipeline with `worktree: false` cannot list `create-worktree` and cannot have a `branch` input.
- `inputs`: map of key name to `type` and `description`. The launch asks for each one. A relative `file` path is resolved from the main repository.
  - Every input is required at launch. A `file` input must point to a file that exists at launch.
  - An input named `branch` makes the launch create the worktree on that branch, new or existing. Use the name `branch` only for that.
  - Without a `branch` input, the worktree starts in detached HEAD. A step that commits must first create a branch.
- `steps`: the list of entries. An entry is a step id, or a map with:
  - `id`: the step id,
  - `with`: config values for this entry,
  - `model` and `effort`: for a step that runs in a subagent,
  - `column`: the board column when this entry starts.
  - `loop`: repeat a range of steps while a key is set. See Loops.
- `claude`: `model` and `effort` of the task session.
- `start_column`: the board column of a new task.
- `create-worktree`: the factory adds the built-in step `create-worktree` as the first step. List it only to set its `with` values, and then only as the first step.

### Loops

A pipeline entry can repeat a range of steps while a task key is set.

```yaml
steps:
  - write-spec
  - id: review-spec
    loop:
      back_to: write-spec
      while: findings
      max: 2
  - user-validation
```

- `loop` has three fields:
  - `back_to`: the id of this entry or of an earlier entry. When the id appears more than once, the nearest one at or before this entry is used. It cannot be `create-worktree`.
  - `while`: a task key name.
  - `max`: an integer from 1 to 20. It is the most jumps back for this loop.
- The entry can be a normal step or a group step. `back_to` can be the entry itself, to repeat one round.
- The loop range is the steps from the `back_to` entry to the loop entry.
- When `factory done` succeeds on the last step of the loop entry, the factory reads the `while` key:
  - The key is not set when it is missing, empty or `none`, ignoring case and spaces around it.
  - Set, with fewer than `max` jumps: the task goes back to the first step of `back_to`. `factory done` prints "Loop <n> of <max>: back to `<step>`. Run `factory next`."
  - Set, after `max` jumps: the task moves to the next step and is blocked: "Loop limit reached on `<entry>`: `<key>` is still set". The session asks the user what to do. When the user says to go on, the session runs `factory unblock`. For one more round, after the user approves, the session runs `factory goto`.
  - Not set: the task moves on.
- At the limit on the last entry of the pipeline, the task finishes without asking the user. So put a step after a loop, for example `user-validation`.
- A skipped step never makes its loop jump.
- An approval on a `user-validation` step does not stop a loop. If that step is the last step of the loop entry, the task still jumps back while the key is set.
- The factory makes the jump. The session never runs `factory goto` for a loop.
- The jump keeps the task keys. It runs in the same task session, so a `session` step keeps the conversation of the earlier rounds. A `subagent` step starts a new agent each time.
- A loop's count goes back to 0 when the task jumps to a step before its range. So an inner loop gets its full `max` in each round of an outer loop.
- `factory status` and the dashboard card show "loop <n> of <max>".
- A step inside the range that outputs the `while` key gets this footer line: "This step controls a loop. Set `<key>` to `none` when nothing is left."
- Each step that outputs the `while` key must set it to `none` when nothing is left. Task keys keep their values, so a clean round must reset the key. Say this in the step prompt.
- In a `command` step, the command sets the key itself, also to `none`.
- Inside the range, a step can use a key that a later step of the range outputs. It is `(not set)` in the first round.
- `factory pipeline check` refuses a bad `loop` and two loops that overlap without one being inside the other. It warns when no step in the range outputs the key, when the key is optional in every step that outputs it, and when the loop is on the last entry.

## Examples

One flow: collect a crash report with a command, fix the crash with the agent, then ask the user to validate with the built-in step `user-validation`.

#### .factory/steps/collect-crash.md

```markdown
---
id: collect-crash
description: Copy the end of the crash log into a crash report artifact
category: build
type: command
outputs:
  crash_report:
    type: file
    description: The last lines of the crash log
done_when: The crash report is written.
config:
  lines:
    description: How many lines of the log to keep
    default: 200
---

bash "$FACTORY_STEP_DIR/collect-crash.sh"
```

#### .factory/steps/collect-crash.sh

```bash
#!/usr/bin/env bash
set -euo pipefail
report="$(factory artifact path crash-report.md)"
tail -n "$FACTORY_CONFIG_LINES" "$FACTORY_KEY_CRASH_LOG" > "$report"
factory state set crash_report "$report"
```

#### .factory/steps/fix-crash.md

```markdown
---
id: fix-crash
description: Find the cause of a crash and fix it
category: build
type: ai
outputs:
  fix_summary:
    type: long-text
    description: What caused the crash and what changed
done_when: The cause is fixed and the tests pass.
config:
  test_hint:
    description: How to run the tests of this repository
    default: the test command of the README
---

Fix this crash: {{description}}.

1. Read the crash report at {{crash_report}}.
2. Find the cause in the code and fix it.
3. Run the tests. Use {{config.test_hint}}.
```

#### .factory/steps/crash-triage.md

```markdown
---
id: crash-triage
description: Collect the crash report, then fix the crash
category: build
type: group
steps:
  - collect-crash
  - fix-crash
---
```

#### .factory/pipelines/crash-fix.yaml

```yaml
id: crash-fix
description: Fix a crash from its log, then ask the user to validate
worktree: true
inputs:
  crash_log:
    type: file
    description: The crash log file
steps:
  - id: crash-triage
    with:
      lines: 100
  - user-validation
```

What the example shows:
- The input `crash_log` is used by the script as `"$FACTORY_KEY_CRASH_LOG"`.
- The output `crash_report` of `collect-crash` is used by `fix-crash` as `{{crash_report}}`.
- The config value `lines` is set with `with` on the group entry. `test_hint` uses its default.

## Exclusive example

#### .factory/steps/run-on-emulator.md

```markdown
---
id: run-on-emulator
description: Run the app on the shared Android emulator and check the screen
category: test
type: ai
exclusive: android-emulator
outputs:
  emulator_result:
    type: text
    description: What the app showed on the emulator
---
Install the app on the Android emulator and open the screen you changed.
Describe what you see.
```

## Loop examples

### Review loop

Write a spec in the session, review it in a subagent, and fix it until the review is clean, at most 2 times.

#### .factory/steps/write-spec.md

```markdown
---
id: write-spec
description: Write the spec, or fix it from the review findings
category: planning
type: ai
outputs:
  spec:
    type: file
    description: The spec file
done_when: The spec file is written and its path is saved.
---

Write a spec for: {{description}}.
Save it at the path printed by `factory artifact path spec.md`.

Findings of the last review: {{findings}}.
In the first round, there is no review yet. In a later round, fix each finding in the spec.
```

#### .factory/steps/review-spec.md

```markdown
---
id: review-spec
description: Review the spec and list the real problems
category: planning
type: ai
outputs:
  findings:
    type: long-text
    description: The real problems of the spec, one per line, or none
done_when: The findings are saved.
run_in: subagent
model: opus
effort: high
---

Review the spec at {{spec}} for: {{description}}.
List only real problems: a missing case, a contradiction, a vague rule. Skip style comments.
Set `findings` to the list, one problem per line.
When you find no real problem, set `findings` to `none`.
```

#### .factory/pipelines/spec-review.yaml

```yaml
id: spec-review
description: Write a spec, review it, and fix it until the review is clean
worktree: false
steps:
  - write-spec
  - id: review-spec
    loop:
      back_to: write-spec
      while: findings
      max: 2
  - id: user-validation
    with:
      target: artifact
      artifact_key: spec
```

### Ticket loop

Split the work into tickets, then run one round of steps per ticket, for any number of tickets.

#### .factory/steps/split-tickets.md

```markdown
---
id: split-tickets
description: Split the work into small tickets
category: planning
type: ai
outputs:
  remaining:
    type: long-text
    description: The tickets left, one per line, or none
done_when: The tickets are saved.
---

Split this work into small tickets: {{description}}.
Each ticket is one line. Each ticket can be built and tested alone.
Set `remaining` to the tickets, one per line.
When there is no ticket, set `remaining` to `none`.
```

#### .factory/steps/pick-ticket.md

```markdown
---
id: pick-ticket
description: Take the next ticket from the list
category: planning
type: ai
outputs:
  current_ticket:
    type: text
    description: The ticket of this round, or none
  remaining:
    type: long-text
    description: The tickets left after this one, one per line, or none
done_when: The ticket and the tickets left are saved.
---

The tickets left: {{remaining}}.

- When this is `none`, set `current_ticket` to `none` and `remaining` to `none`.
- Otherwise, set `current_ticket` to the first line.
- Set `remaining` to the other lines. When no line is left, set it to `none`.
```

#### .factory/steps/build-ticket.md

```markdown
---
id: build-ticket
description: Build one ticket and commit it
category: build
type: ai
done_when: The ticket is built, tested and committed.
---

The ticket of this round: {{current_ticket}}.

When it is `none`, do nothing and run `factory done`.
Otherwise, build the ticket, run the tests and commit the change.
```

#### .factory/steps/ticket-round.md

```markdown
---
id: ticket-round
description: Take the next ticket and build it
category: build
type: group
steps:
  - pick-ticket
  - build-ticket
---
```

#### .factory/pipelines/ticket-loop.yaml

```yaml
id: ticket-loop
description: Split the work into tickets and build them one by one
worktree: true
steps:
  - split-tickets
  - id: ticket-round
    loop:
      back_to: ticket-round
      while: remaining
      max: 20
  - user-validation
```

What the examples show:
- `review-spec` runs in a subagent and sets `findings` to `none` when the review is clean.
- `write-spec` uses `{{findings}}`, an output of a later step of its loop. It is `(not set)` in the first round.
- `ticket-round` loops back to itself. `pick-ticket` controls the loop: it sets `remaining` to `none` after the last ticket.
- With zero tickets, `pick-ticket` sets `current_ticket` to `none`, and `build-ticket` does nothing.
- Each loop has a step after it, so the user decides at the limit.
