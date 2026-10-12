# Skill software-factory

## Problem

Starting a new task takes many manual actions: create a worktree, open a Herdr tab, start a Claude session with a name, write the first prompt.
Each type of task (new feature, known bug, production crash) follows its own workflow, and I repeat the same steps in each of them.
When many tasks run in parallel, I have no single view to follow them and act on them.

## Solution

Create a software factory skill. It starts each task in its own worktree, Herdr tab and named Claude session.
Each type of task is a pipeline. A pipeline is an ordered list of reusable steps.
A local dashboard shows all tasks as a Kanban board and the backlog, and lets me act on each task.

## Variables

- `PROJECT_ROOT: /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory`
- `SPEC_DIR: <PROJECT_ROOT>/specs/`
    - Save your own spec here.
- `PLAN_DIR: <PROJECT_ROOT>/plans/`
    - Save your own plan here.
- `YOUR_WORKING_DIR: <PROJECT_ROOT>/software-factory/`
    - Save your work here.
- `VERIFICATION_DIR: <PROJECT_ROOT>/verification/software-factory/`
    - Save your verification artifacts here.
- `FACTORY_SOURCE: <PROJECT_ROOT>/software-factory/`
    - Source of the factory: code, built-in steps and pipelines, catalog and migrations. It holds no user data.

## Workflow

1. Brainstorm. Use the `/superpowers:brainstorming` skill to create a specification file from these requirements. Save the specification file in `SPEC_DIR/` before writing the plan.
2. Ask validation. Ask the user to validate the specification file.
3. Plan. After specification validation, use the `/superpowers:writing-plans` skill to create an implementation plan from the specification file. Save the plan file in `PLAN_DIR/` before writing implementation code. Split the plan into these milestones, in this order:
    1. Core: the `factory` CLI, task state, step execution, config, worktree creation, the terminal adapter with the Herdr adapter, task launch and delete with their dry runs, Init and the orchestrator menu.
    2. Task life: statuses, blocked, approval, board columns, external waiting, pause and resume, goto, artifacts, focus and send prompt, clean, backlog, event log.
    3. Authoring: step assistant, pipeline editor and its local server, catalog, library commits.
    4. Lifecycle and docs: versioning, migration, README without the dashboard parts.
    5. Dashboard: the dashboard views, their server API, and the README dashboard parts (tutorial step 6, dashboard reference).
4. Ask validation. Ask the user to validate the plan file.
5. Build. After plan validation, use the `/superpowers:subagent-driven-development` skill to implement the plan inside `YOUR_WORKING_DIR`, one milestone at a time. Run the tests of a milestone, fix the failures, and commit before starting the next milestone. Do not skip straight from this prompt to implementation.
6. Verify. Check every item in Definition Of Done, fix failures, and rerun the affected checks. Keep final verification artifacts inside `VERIFICATION_DIR` and report actual results and any remaining blockers.

## Definition Of Done

### Workflow Complete

- Your completed implementation plan exists under `PLAN_DIR/`
    - It was written before implementation, and the build followed its build step.
- The `software-factory` skill exists under `YOUR_WORKING_DIR`.
- `PROJECT_ROOT/.claude-plugin/marketplace.json` exists. It defines a marketplace named `software-factory` with one plugin that points to `YOUR_WORKING_DIR`. The user can install it from any repository with `/plugin marketplace add <PROJECT_ROOT>`.

### Runtime

- The factory code is Python 3. There is one entry script, `factory`, run with `uv run --script`. It declares its dependencies inline, for example `pyyaml`, so `uv` installs them on first run. Dependencies are kept to the minimum.
- The code is split into small modules in a `lib/` folder next to the entry script, one per area, each tested on its own.
- The local server is the `factory serve` subcommand. `factory dashboard` and `factory pipeline edit` start it in the background. The server and the CLI share the same functions.
- `uv` can also install the Python version the scripts need, so the machine needs only `uv`.
- The orchestrator is a Claude session started inside the configured terminal. At start, it runs `factory terminal check`. If the check fails, it says why and stops.
- The `factory` command can be called by name in every Claude session the factory starts, in the main repository and in worktrees. Init makes this work, for example with a link in `~/.local/bin`.
- Init writes `.factory/claude-settings.json` with allow rules for the `factory` commands. Every task session starts with `--settings <main repository>/.factory/claude-settings.json`, so it never asks for permission on a `factory` command.
- The README lists the `git` and `factory` commands, and the commands of each adapter, so the user can add them to the Bash allowlist.

### General concept

- The `software-factory` skill is an orchestrator launched in the main repository.
- It can do the following actions, grouped in the menu:
  - Tasks
    - Launch a new pipeline, from scratch or from a backlog entry
    - Show tasks: lists the tasks with their status
    - Check waiting tasks: runs `factory poll`, and lets the user mark a manual external event as done
    - Focus a task: switches the terminal to the task session
    - Send a prompt to a task
    - Resume a task: restarts the session of a paused task, or of a task whose session is gone
    - Delete a task: runs the built-in step `delete-task`
    - Clean finished tasks: deletes finished tasks whose work is merged
  - Pipelines and steps
    - Create or edit a pipeline: opens the pipeline editor in the browser
    - Create a new step: runs the built-in pipeline `new-step-assistant`
    - Browse the catalog: lists the catalog pipelines and steps, and installs them
  - Backlog
    - Add a backlog entry: runs the built-in step `backlog-add`
    - Remove a backlog entry: runs the built-in step `backlog-remove`
  - Factory
    - Open dashboard: starts the local server if needed and opens the dashboard in the browser
    - Init the factory. When the factory is not initialized in the repository, this is the only action shown. After init, it is never shown.
    - Exit: stops the menu and the local server. It first asks whether to pause all tasks (see Pause and resume).

### Factory elements

#### Pipelines

- A pipeline is one YAML file in `pipelines/<id>.yaml`. It contains:
  - `id`: unique lowercase id
  - `description`: one line, shown in the launch menu
  - `inputs`: values asked to the user at launch, each with a description. They are saved in the task state, so steps read them with `reads`.
  - `steps`: ordered list of step ids. Each entry can set config values for this pipeline with `with`.
  - `claude`: optional `model` and `effort` for the task session, passed at launch as `--model` and `--effort`.
  - A `steps` entry can also set `model` and `effort`. They override the step manifest values for this pipeline.
  - `start_column`: the board column of a new task. Default: the first column.
  - A `steps` entry can also set `column`. It overrides the step manifest value for this pipeline.
- Example:

```yaml
id: fix-crash
description: Fix a production crash from its Crashlytics link
claude:
  model: sonnet
  effort: medium
inputs:
  crash_url:
    description: Crashlytics link of the crash
steps:
  - id: analyze-crash
    effort: high
  - id: user-validation
  - id: fix-crash
  - id: commit
  - id: create-merge-request
    with:
      target_branch: release
```

- Built-in pipeline: `new-step-assistant`. Other pipelines come from the catalog or from the pipeline editor.
- Adding a new pipeline needs only a new pipeline file, with no change in the orchestrator.
- Each pipeline run is a task.

#### Steps

- A step is one markdown file. Its YAML frontmatter is the step manifest. Its body holds the instructions.
- The manifest contains:
  - `id`: unique lowercase id
  - `description`: one line, shown when the user builds a pipeline
  - `category`: one word to group steps, for example `git`, `jira`, `gitlab`, `review`
  - `type`: `prompt`, `skill`, `script` or `composite`
  - `reads`: task state keys the step needs
  - `writes`: task state keys the step sets
  - `done_when`: the condition that ends the step, in plain text
  - `done_check`: optional shell command. Exit code 0 means the step is done. When present, the factory checks it before moving to the next step.
  - `config`: config keys, each with a description and an optional default value
  - `required`: `true` if the step must never be skipped
  - `run_in`: `session` (default) or `subagent`. Used by `prompt` and `skill` steps.
  - `model` and `effort`: optional, used only when `run_in` is `subagent`. Example: `model: opus`, `effort: high`.
  - `requires`: optional list of tools and skills the step needs, for example `[gh]` or `[/superpowers:writing-plans]`
  - `column`: optional board column. The task moves to it when the step starts.
  - `wait_external`: `true` if the step waits for an external event (see External waiting)
- The body depends on the type:
  - `prompt`: the instructions the agent follows
  - `skill`: the skill to call and how to use its result
  - `script`: the path of the shell script to run
  - `composite`: no body. The manifest has a `steps` list with the ids of the child steps, run in order.
- Example:

```markdown
---
id: write-plan
description: Write an implementation plan from the spec
category: planning
type: skill
reads: [spec]
writes: [plan]
done_when: The plan file exists and its path is saved in the task state.
done_check: test -f "$(factory state get plan)"
config:
  plan_style:
    description: Extra instructions for the plan, for example the commit size
    default: small commits
required: false
requires: [/superpowers:writing-plans]
---

Run `/superpowers:writing-plans` on the spec file at `spec`, following `config.plan_style`.
Save the plan in the artifacts folder with `factory artifact path plan.md`.
Save the path with `factory state set plan <path>`.
```

- A composite step groups existing steps. Example: `rebase-and-commit` runs `rebase`, then `commit`.
  - Its `reads` and `writes` are computed from its child steps, not written by hand.
  - Each child step keeps its own done check, config and `required` flag.
  - A composite step cannot include itself, directly or through another composite step. The factory checks this when it loads the steps.
  - The current step is shown with its full path, for example `rebase-and-commit > commit`.
- A step that asks the user anything must use `run_in: session`. A subagent cannot talk to the user. `user-validation` always runs in the session.
- For a `subagent` step, `factory next` prints the Agent tool call to make: the model, the effort and a full prompt. The prompt holds the step body, the values of the keys it reads, its config values and the artifact paths. The subagent sees nothing of the session conversation.
- The subagent writes its outputs with `factory state set` and ends with a short report. If it needs the user, it says so in its report, and the session asks the user and runs the step again.
- The session runs `factory done` after the subagent ends.

- A step can be used by many pipelines.
- Built-in steps: `create-task`, `create-worktree`, `delete-task`, `backlog-add`, `backlog-remove`, `migrate` and `user-validation`.
- `user-validation`: the task waits for the user to approve a result (see Approval).
- Required steps are enforced by the factory CLI: `factory skip` refuses them, and `factory done` runs their `done_check`.

#### Step creation

- The `new-step-assistant` pipeline runs as a task in the main repository, without a worktree. It starts Claude with `--add-dir <library>`, so it can write generic steps.
- It first asks where to save the step:
  - Generic: in `<library>/steps/`, reusable in any repository that uses this library.
  - Local: in `.factory/steps/` of the main repository, only for this repository.
- It asks the user:
  - The goal of the step
  - Its type: prompt, skill, script or composite. For a composite, it lists the existing steps and asks which ones to use, in order.
  - Its category. It shows the existing categories first, so the user reuses one when it fits.
  - What it reads from and writes to the task state file
  - Its done condition
  - Where it runs: in the session or in a subagent. If the step asks the user anything, it must run in the session.
  - For a subagent: its model and effort
  - Its config keys, with a description and an optional default value
  - If it must never be skipped
- Before writing, it checks the existing generic and local steps. If a similar step exists, it proposes to reuse or update it.
- It gives the step a unique lowercase id.
- It shows the full step file to the user and writes it only after approval.
- At the end, it lists the pipelines and asks if the new step should be added to some of them. It updates a pipeline only after approval.
- When a local step and a generic step have the same id, the local step is used.

#### Step configuration

- Config values for a repository are saved in `.factory/config.yaml`, in one section per step. This file is never committed.
- When a step runs, each config key gets its value from the first source that has it:
  1. The `with` block of the step in the current pipeline
  2. `.factory/config.yaml`
  3. The default value in the step manifest
- If no source has a value, `factory next` tells the agent to ask the user, then to save the answer with `factory config set <step> <key> <value>`. The next runs do not ask again.
- `factory next` prints the resolved config values with the step instructions.
- No secrets in config files. Tokens stay in the tools' own configuration.

#### Pipeline editor

- Pipelines are created and changed in a web page served by the local server (see Local server): `factory pipeline edit [<id>]` starts the server and opens the page with `open <url>`. It does not use Claude.
- The page uses plain HTML, CSS and JavaScript, with no external library, so it works offline. Drag and drop uses the browser's native support.
- Start options:
  - Create an empty pipeline
  - Copy an existing pipeline as a starting point
  - Edit an existing pipeline
- The page shows the available steps on one side and the pipeline steps on the other:
  - Drag a step from the list into the pipeline, and drag pipeline steps to reorder them
  - Remove a step from the pipeline
  - Edit the `with` values, `model` and `effort` of a pipeline step in a form
  - Edit the id, the description, the inputs, and the session `model` and `effort` in a form
  - Filter the available steps by category or by text
  - Reload the available steps, to see a step created in another task
- Each available step shows its id, category, description, level (local, generic or built-in) and where it runs (session or subagent).
- Clicking a step, in the list or in the pipeline, opens a read-only detail panel:
  - The full manifest: type, `reads`, `writes`, `done_when`, `done_check`, config keys with their defaults, `required`, `run_in`, `model`, `effort`, `requires`
  - The body, as plain text
  - The level and the file path, so the user can open the file in their own editor
  - For a composite step, its child steps, each one clickable
- It runs the pipeline checks live, through the server, and shows the problems:
  - Error: `create-worktree` is listed, but not as the first step
  - Error: a step id does not exist
  - Warning: a `reads` key is not a pipeline input and is not written by an earlier step
  - Warning: a generic pipeline uses a local step
  - Warning: `model` or `effort` set on a step that runs in the session. It has no effect.
- It can save with warnings, never with errors.
- On save, it asks where to save: generic in `<library>/pipelines/`, or local in `.factory/pipelines/`. When the user edits a generic pipeline, they can save a local override instead.
- If a needed step does not exist, the user creates it with "Create a new step" from the orchestrator, then reloads the list in the editor.

#### Local server

- One small local HTTP server, written with the Python standard `http.server` module, serves the pipeline editor, the dashboard and their API.
- `factory pipeline edit` and `factory dashboard` start it if it is not running, then open their page with `open <url>`. The running server writes its port, token and process id to `.factory/server.json`, so the factory reuses it.
- API: list steps, get one step (manifest and body), list pipelines, load, check and save a pipeline, list tasks, list the backlog, and one route per dashboard action. The pages use only this API. They never read or write files directly.
- Every action route calls the same function as the matching CLI command. The server holds no task logic.
- While it runs, the server runs `factory poll` every `poll_minutes` (see External waiting).
- Security:
  - It listens on `127.0.0.1` only, on a free port.
  - It generates a random token at start. The page URL carries it, and every API request must send it.
  - It rejects requests whose `Origin` header is not the server itself.
- It stops on Exit from the orchestrator, or after 30 minutes without requests. An open dashboard page sends requests every 5 seconds, so the server stays alive while a page is open.

#### Dashboard

- `factory dashboard` opens the dashboard. It has two views: Tasks and Backlog.
- The pages use plain HTML, CSS and JavaScript, with no external library, so they work offline. They refresh every 5 seconds.
- Every button calls an API route, which calls the same function as the matching CLI command. Errors are shown in the page.

##### Tasks view

- One column per board column from `.factory/factory.yaml`, plus Done at the end.
- The user can hide and show columns. The choice is saved in the browser.
- Cards cannot be dragged between columns. The steps set the column.
- One card per task, not archived. A card shows:
  - The Jira ticket key, when set, as a link that opens `ticket_url` in a new tab. `ticket_url` is in `.factory/factory.yaml`, with `{key}` in its place, for example `https://<company>.atlassian.net/browse/{key}`.
  - The description, the pipeline and the current step
  - The status as text and an icon, and the time in the current status, for example "blocked for 2 h"
  - A background color from the status: `active` green, `blocked` red, `awaiting_approval` amber, `waiting_external` blue, `paused` grey. Done cards are neutral.
  - A clear marker when the session state is `gone`
  - The list of artifacts. Clicking one shows it in the page, as plain text.
- Card buttons, shown only when they apply:
  - Focus: `factory terminal focus`
  - Show MR: opens `mr_url` from the task state in a new tab, whenever it is set
  - Approve and Request changes, when the task is `awaiting_approval`. The card shows what to validate: a link to the artifact, or an "Open in IDE" button for `target: worktree`.
  - Mark done, when the task is `waiting_external` on a step without a `done_check`
  - Send prompt: free text, sent with `factory terminal send-prompt`
  - Pause: asks to wait until the session is idle, or to stop now. Waiting runs in the background on the server with the adapter `wait-idle`, so the page never freezes.
  - Resume, when the task is `paused` or its session is `gone`
- A "Launch" button opens a form: pipeline, description and inputs. The form shows the `factory launch --dry-run` result, and launches after the user confirms.
- The Done column has a "Clean" button. It shows the `factory clean` result, and deletes the selected tasks with `delete-task`.

##### Backlog view

- One card per entry, in priority order: title, summary and pipeline.
- Drag a card to change its priority. This calls `factory backlog move`.
- "Add" opens a form: title, summary and optional pipeline.
- "Delete" removes an entry after confirmation.
- "Start" opens the Launch form, filled from the entry, and launches with `--from-backlog <id>`.

#### Catalog

- The factory ships a catalog of ready-to-use pipelines and steps in `FACTORY_SOURCE/catalog/`.
- Catalog items are templates. Installing an item copies it to the generic library or to the local factory, as the user chooses. The user owns the copy.
- "Browse the catalog" lists each item with its category, its description and its status: not installed, installed, or installed and changed since.
- Installing a pipeline lists the steps it uses that are not installed, and installs them after approval.
- An installed item that already exists is replaced only after the user sees the difference and approves.
- Init offers the starter pack: the `quick-task` pipeline and its steps.
- The catalog is generic. It never refers to a project-specific skill or tool.
- "Browse the catalog" also shows the `requires` of each item that are missing on this machine.
- Catalog content for this build:
  - Pipelines:
    - `quick-task`: `implement`, `user-validation`, `commit`
    - `plan-and-build`: `brainstorm`, `user-validation`, `write-plan`, `user-validation`, `execute-plan`, `run-tests`, `commit`, `push`, `create-pr`, `wait-review`, `wait-qa`
  - Steps:
    - `implement`: prompt step, do the task description
    - `commit`: prompt step, commit the changes with a message that follows the repository's existing commit style
    - `rebase`: prompt step, rebase on `origin/<base_ref>` and resolve simple conflicts. It blocks the task for the user on complex conflicts.
    - `push`: script step, push the branch to `origin`
    - `run-tests`: script step, runs `config.test_command`. Its `done_check` is the same command.
    - `create-pr`: prompt step, create a pull request or merge request with `gh` or `glab`, from `config.forge`
    - `review`: prompt step, review the branch diff against `origin/<base_ref>` and save the findings as an artifact
    - `address-review-comments`: prompt step, read the open review comments with `gh` or `glab` and fix them
    - `brainstorm`: wraps `/superpowers:brainstorming`, saves the spec as an artifact
    - `write-plan`: wraps `/superpowers:writing-plans`, saves the plan as an artifact
    - `execute-plan`: wraps `/superpowers:executing-plans` on the plan artifact
    - `wait-review`: waits until the pull request or merge request is approved. `wait_external: true`, with a `done_check` that uses `gh` or `glab` from `config.forge`. Column: Review.
    - `wait-qa`: waits until the user marks QA as done. `wait_external: true`, without a `done_check`. Column: QA.
- The builder reads each wrapped skill to set `run_in`: `session` if the skill asks the user anything, otherwise `subagent`.
- `config.forge` is `github` or `gitlab`. It is asked once per repository, like any config key.

#### Library commits

- After each write to `<library>/`, the factory offers to commit it in the git repository that contains the library:
  - The step assistant saves a generic step
  - The pipeline editor saves a generic pipeline
  - A catalog item is installed to the generic library
  - `migrate` changes the library
- It shows the changed files and the commit message, and commits only after approval.
- The message is `Factory library: <action> <kind> <id>`, for example `Factory library: add step create-merge-request`. A migration uses `Factory library: migrate to version <n>`.
- It commits only the changed files in the library, with a pathspec. Other changes in that repository are never included, even if they are staged.
- If the library is not in a git repository, library commits are disabled.
- It never pushes.

#### Tasks

##### Task properties

- A fixed id, created at launch.
- An optional Jira ticket key, set when a ticket is assigned.
- A short description.
- The pipeline id.
- The pipeline inputs.
- The current step path.
- A status:
  - `active`: the pipeline runs
  - `blocked`: the session waits for an answer from the user, with a reason
  - `awaiting_approval`: the user must validate a result (see Approval)
  - `waiting_external`: the task waits for an external event, like a merge request review (see External waiting)
  - `paused`: the factory stopped the session (see Pause and resume)
  - `finished`: the last step is done
- The board column (see Board columns).
- An optional branch name.
- An optional worktree path. It is empty for `new-step-assistant`.
- The Claude session id.
- The terminal handle returned by the terminal adapter.
- The creation and last update dates.

##### Task launch

- A pipeline is launched with `factory launch <pipeline> --description <text> [--input <key>=<value> ...] [--id <id>] [--from-backlog <id>]`. It does not use Claude. It is the built-in step `create-task`.
- The orchestrator menu and the dashboard both use it. They only collect the values: the menu asks the user, the dashboard shows a form.
- `factory launch --dry-run` with the same values prints what would happen: the task id, the worktree path, the branch case (new, existing or detached), the missing inputs and the errors. The caller shows it, and launches only after the user confirms.
- The task id is a slug of the description: lowercase, matching `[a-z][a-z0-9_-]{0,31}`. If the id is taken, a suffix `-2`, `-3` is added. `--id` sets it by hand. The id never changes.
- If a part of the launch fails, it removes what it already created (worktree, branch, task folder, terminal) and reports the error.
- With `--from-backlog`, the backlog entry is removed only after the launch succeeds.
- The same id is used for the task folder, the terminal name and the Claude session name.
- It runs the `create-worktree` step. The built-in pipeline `new-step-assistant` runs in the main repository instead.
- It creates the task folder and the task state file, with the inputs, before the session starts.
- It starts the task session with `factory terminal start-session`, in the worktree or in the main repository. Claude starts with `--name <id> --session-id <uuid> --settings <main repository>/.factory/claude-settings.json --add-dir <main repository>/.factory/tasks/<id>/artifacts`, plus `--model` and `--effort` when the pipeline sets them, and receives the first prompt (see Task execution).
- It saves the terminal handle in the task state.
- The orchestrator goes back to its menu without waiting for the task.

##### Worktree creation

- Every task runs in its own worktree, except the built-in pipeline `new-step-assistant`. It changes only factory files, so it runs in the main repository.
- To explore without a branch, the user starts a Claude session manually, outside the factory.
- Every other pipeline starts with the built-in step `create-worktree`. The factory adds it when the pipeline does not list it.
- A pipeline lists `create-worktree` only to set `with` values, and only as its first step. The factory refuses a pipeline that lists it anywhere else.
- It runs inside `factory launch`, before the task session starts.
- Config keys:
  - `worktree_root`: the folder where worktrees are created
  - `base_ref`: the branch the worktree starts from, default `main`
- It always runs `git fetch origin <base_ref>` first, so the worktree starts from the latest version. It never changes the local `<base_ref>` branch. If the fetch fails, it stops and asks the user.
- If the pipeline has an input named `branch`:
  - It also fetches that branch from `origin`, then checks if it already exists, locally or on `origin`.
  - `factory launch --dry-run` reports which case applies, new branch or existing branch, so the user confirms it before the launch. This catches a typo in the name.
  - New branch: the worktree is created on it, from `origin/<base_ref>`.
  - Existing branch: the worktree is created on it. If the local branch is behind `origin`, it is fast-forwarded. If the local and remote branches have diverged, it stops and asks the user.
  - If the branch is already checked out in another worktree, it stops and names the task or the folder that uses it.
- Otherwise, the worktree starts in detached HEAD on `origin/<base_ref>`. A later step creates the branch with `git switch -c <name>` and saves it with `factory state set branch <name>`.
- It creates the worktree with git only:
  - New branch: `git worktree add -b <branch> <worktree_root>/<id> origin/<base_ref>`
  - Existing local branch: `git worktree add <worktree_root>/<id> <branch>`
  - Branch only on `origin`: `git worktree add --track -b <branch> <worktree_root>/<id> origin/<branch>`
  - Without a branch: `git worktree add --detach <worktree_root>/<id> origin/<base_ref>`

##### Task delete

- A task is deleted with `factory delete <id> [--dry-run] [--confirm-unpushed]`. It does not use Claude. It is the built-in step `delete-task`.
- The orchestrator menu and the dashboard both use it. The menu lists the tasks and the user selects one. The dashboard uses the Clean dialog.
- `factory delete --dry-run` prints what would be removed and the checks below. The caller shows it and deletes only after the user confirms.
- It shows what it will remove: the Claude session, its terminal, the worktree and the local branch.
- It checks the worktree:
  - Uncommitted changes
  - Commits not pushed to `origin`
- If there are any, the dry run shows them, and the delete runs only with `--confirm-unpushed`, after explicit user approval.
- It deletes the local branch only if it is pushed or merged. It never deletes a remote branch.
- It closes the task terminal with `factory terminal close`, then removes the worktree with `git worktree remove`.
- It moves the task folder to `.factory/tasks/archive/<id>/`. It does not delete it.

##### Event log

- The `factory` CLI appends one JSON line per event to `.factory/tasks/<id>/events.jsonl`. Only the CLI writes this file, never the agent.
- Each line has a timestamp, an event type, the step path and details.
- Event types:
  - `task_created`
  - `step_started`, with where the step runs, the model and the effort
  - `step_done`
  - `step_skipped`
  - `done_check_failed`, with the command output
  - `config_asked`, with the key
  - `migrated`, with the versions
  - `task_deleted`
  - `task_blocked`, with the reason
  - `task_unblocked`
  - `task_paused`
  - `task_resumed`
  - `step_goto`, with the from step, the to step and the reason
  - `task_finished`
  - `prompt_sent`, with the text
  - `column_changed`, with the from and to columns
  - `approval_requested`, with the target
  - `approved`
  - `changes_requested`, with the text
  - `waiting_started`, with the reason
  - `external_event`, with how it ended: check or manual
- With the Claude session id from the task state, this log is enough to split the session transcript by step later.

##### Task execution

- The task session runs one step at a time. It never reads the pipeline or step files directly.
- The first prompt of a task is short: "You run factory task `<id>`. Run `factory next` and follow its instructions. When the step is done, run `factory done`. Repeat until `factory next` says the pipeline is finished."
- When the last step is done, `factory done` sets the task to `finished`. It sends a notification if the adapter supports `notify`. The session tells the user that the task is finished.
- A step file changed during a task applies from the next step.
- A step with `required: true` cannot be skipped. Other steps can be skipped with `factory skip`, only after user approval.
- `factory goto <step-path> --reason <text>` moves the task back to an earlier step, only after user approval. The path can point inside a composite step, for example `rebase-and-commit > commit`.
  - It refuses a step that is not before the current step. Moving forward is a skip.
  - State keys keep their values. Steps that run again overwrite the keys they write.
  - After 3 jumps back to the same step, the task is blocked for the user, with the reason "loop on <step>".

##### Task list

- "Show tasks" prints one line per task, not archived:
  - Id and description
  - Pipeline and current step path
  - Status, with the reason when blocked
  - Live session state from the terminal adapter, or `unknown` if the adapter does not support it
- Tasks that need the user are listed first: `blocked`, then `awaiting_approval`.

##### Focus and send a prompt

- "Focus a task" lists the tasks with a live session and calls `factory terminal focus` on the selected one.
- "Send a prompt to a task" lists the tasks with a live session, asks for the text and calls `factory terminal send-prompt`.
  - If the session is working, it asks the user to wait until the session is idle, or to send now.
  - If the session is gone or the task is paused, it offers to resume the task first.
- Both actions are hidden when the adapter does not support them.

##### Clean finished tasks

- It lists the `finished` tasks. For each one, it shows if its work is merged:
  - The branch is merged into `origin/<base_ref>`, or
  - The branch was pushed and its remote branch no longer exists, as after a merge request with "delete source branch". This also covers squash merges.
- A finished task without a branch counts as merged.
- Merged tasks are selected by default. The user can change the selection.
- Each selected task goes through `delete-task`, with all its checks.

##### Blocked status

- `factory block <reason>` sets the task to `blocked`. `factory unblock` sets it back to `active`.
- The agent runs `factory block` when it cannot continue without the user, and `factory unblock` when the user has answered.
- When a task becomes blocked and the adapter supports `notify`, the user gets a notification.

##### Board columns

- The board columns are a list in `.factory/factory.yaml`. Default: Discovery, Specification, Plan, Implementation, Review, QA.
- A finished task goes to a Done column, which is always last.
- A new task starts in the pipeline `start_column`.
- When a step starts, the task moves to the step `column`, from the pipeline entry first, then from the step manifest. A step without a column leaves the task where it is.
- `factory pipeline check` reports an error for a column that is not in the list.

##### Approval

- `user-validation` sets the task to `awaiting_approval`. Its `with` says what to validate:
  - `target: artifact`, with `artifact_key`: the state key that holds the artifact path, for example `spec`
  - `target: worktree`: the code in the task worktree
- The user approves or requests changes, from the dashboard or by answering in the session:
  - `factory approve` saves the approval. The `done_check` of `user-validation` checks it. The session gets "The user approved. Run `factory done`."
  - `factory request-changes <text>` sets the task back to `active`. The session gets the text as feedback and continues the step.
- `factory open-ide` opens the task worktree with the config key `ide_command`, for example `open -a "Android Studio" {path}` or `code {path}`. The key is asked on first use, like any config key.
- When the dashboard or the menu approves, it sends the message to the session with the adapter `send-prompt`.

##### External waiting

- A step with `wait_external: true` first does its actions, then the agent runs `factory wait`. The task becomes `waiting_external`, with the step `done_when` as the reason.
- The wait ends in one of two ways:
  - With a `done_check`: `factory poll` runs the `done_check` of every `waiting_external` task. Each check has a timeout of 60 seconds.
  - Without a `done_check`: the user marks the event as done with `factory external-done <id>`, from the dashboard or the menu.
- When the wait ends:
  - The step is done, the task becomes `active`, and the user gets a notification if the adapter supports `notify`.
  - The session gets "The external event happened: <done_when>. Run `factory next`." If the session is gone, the factory resumes it first.
- `factory poll` runs:
  - Every `poll_minutes` while the dashboard server runs. `poll_minutes` is in `.factory/factory.yaml`, default 5.
  - From the menu action "Check waiting tasks".
- `paused` tasks are not polled. Resume restores `waiting_external`, and polling starts again.

##### Pause and resume

- Pausing a task:
  - It saves the current status, with its reason, so resume can restore it.
  - If the session is working, it asks the user to wait until the session is idle, or to stop it now. A stopped step is not marked done, so it continues on resume.
  - It closes the task terminal with `factory terminal close` and sets the status to `paused`.
- On Exit, the orchestrator asks whether to pause all tasks that are not `paused` or `finished`. If the user says no, the sessions keep running.
- At start, after the version check, if paused tasks exist, the orchestrator lists them and offers to resume all of them, some of them or none.
- Resuming a task:
  - It starts a new terminal with `factory terminal start-session` in the task worktree, or in the main repository for `new-step-assistant`.
  - Claude starts with the same args as at launch (see Task launch), plus `--resume <session-id>`, so the conversation continues.
  - The prompt is: "The factory resumed this task. Run `factory status`, then continue with `factory next`."
  - It restores the saved status and saves the new terminal handle.
- "Resume a task" in the menu lists the paused tasks, and the tasks that are not `finished` whose session state is `gone`.
- If the adapter does not support `state`, the user can still resume a task that is not `finished`. The orchestrator first warns that a second session could start if the first one is still running.

##### Artifacts

- Files made during a task are saved in `.factory/tasks/<id>/artifacts/`: specs, plans, analyses, notes. This folder is outside git, so these files are never committed to the shared repository.
- A step that makes a file saves its path in a task state key, so later steps find it with `reads`. Example: `analyze-crash` writes `analysis` = the path of `artifacts/analysis.md`.
- `factory artifact path <name>` creates the folder if needed and prints the absolute path for a file name.
- When a step calls a skill that saves files, the step body tells the skill to save them in the artifacts folder.
- Archived tasks keep their artifacts.

#### Backlog

- `.factory/backlog.md` holds the tasks not started yet. The user can also edit it by hand.
- Each entry is a section:
  - A `##` heading with the title
  - A hidden id line: `<!-- id: <id> -->`
  - An optional `pipeline: <id>` line
  - A short summary, in free text
- Example:

```markdown
## Add dark mode to settings
<!-- id: b7 -->
pipeline: plan-and-build
Users ask for a dark theme. Start with the settings screen only.
```

- The order of the entries in the file is the priority. The first entry is the most important.
- The id is stable. Entries written by hand without an id get one the next time the CLI writes the file.
- Built-in steps, run in the orchestrator session:
  - `backlog-add`: asks for the title, the summary and the optional pipeline, then adds the entry at the end.
  - `backlog-remove`: lists the entries and removes the one the user selects.
- When the user launches a pipeline, the orchestrator offers to start from a backlog entry. The title becomes the task description, and the summary is saved in the task state key `summary`, so steps can read it. The launch uses `--from-backlog <id>`, so the entry is removed once the task is created.
- At the end of Init, the orchestrator asks if the user wants to import backlog entries. The user pastes a list or gives a file path. Each line becomes the title of an entry. The orchestrator shows the parsed entries and adds them with `backlog-add` after approval.

### Orchestrator

- When the factory starts, the orchestrator always shows the menu with the available actions.
- The menu is a numbered text list, with one heading per group and one number sequence for the whole menu. The user answers with a number. Do not use the `AskUserQuestion` tool for the menu, because it allows at most 4 options.
- When an action is done, the orchestrator shows the menu again.

### Init

- Init checks the prerequisites and reports each one as OK or failing with the fix:
  - The terminal adapter check passes
  - The current folder is a git repository with an `origin` remote
  - `uv` is installed. If it is not, Init shows the install command.
- It saves the terminal as `terminal` in `.factory/factory.yaml`. This build has only the `herdr` adapter, so Init selects it without asking.
- It asks for the path of the library folder and saves it as `library` in `.factory/factory.yaml`.
  - If the folder does not exist, it offers to create it with `factory.yaml`, `steps/` and `pipelines/`.
  - If the folder is not in a git repository, it warns that library commits are disabled.
- It creates `.factory/` with its files and empty folders (see File organization). It never overwrites an existing file.
- It adds `.factory/` and `.factory.backup-*/` to `.git/info/exclude`. It never changes `.gitignore`, because the repository can be shared.
- It offers to install the catalog starter pack (see Catalog).
- It ends with the backlog import (see Backlog).

### Factory CLI

- The factory ships a `factory` CLI. It is the only way the orchestrator and the task sessions read and write `.factory/`.
- It finds the main repository from any worktree with `git rev-parse --git-common-dir`. Task sessions in a worktree always use the `.factory/` of the main repository.
- It finds the current task from the worktree path. A task without a worktree passes `--task <id>`:
  - Its first prompt and its resume prompt say to add `--task <id>` to every `factory` command.
  - `factory next` prints every `factory` command with `--task <id>` already in it, also in the subagent prompt.
  - When the task cannot be found, the error message says to add `--task <id>`.
- It writes every file atomically: it writes a temporary file, then renames it. It holds a lock while it changes a shared file (`config.yaml`, `backlog.md`), so parallel sessions never lose a write.
- It merges steps and pipelines from three levels. When two have the same id, the first level wins:
  1. Local: `.factory/` of the main repository
  2. Generic: `<library>/`, with `library` read from `.factory/factory.yaml`
  3. Built-in: read from the installed plugin, next to the CLI, so they always match the CLI version
- Commands:
  - `factory dashboard`: starts the local server if needed and opens the dashboard.
  - `factory launch <pipeline> ...` and `factory launch --dry-run ...`: create a task, or show what the launch would do.
  - `factory delete <id>` and `factory delete --dry-run <id>`: delete a task, or show what the delete would do.
  - `factory next`: prints the current step instructions, with the task state keys it reads.
  - `factory done`: runs the step `done_check` if present. If it passes, it saves the step end and prints the next step. If it fails, it prints why and stays on the step.
  - `factory skip`: skips the current step, refused for required steps.
  - `factory state get <key>` and `factory state set <key> <value>`: read and write the task state.
  - `factory status`: prints the task id, the pipeline and the current step path.
  - `factory config get <step> <key>` and `factory config set <step> <key> <value>`: read and write the repository config.
  - `factory backlog list`, `factory backlog add <title> [--summary <text>] [--pipeline <id>]`, `factory backlog remove <id>` and `factory backlog move <id> --to <position>`: read and change the backlog.
  - `factory pipeline edit [<id>]`: opens the pipeline editor.
  - `factory pipeline check <id>`: runs the pipeline checks and prints the errors and warnings.
  - `factory block <reason>` and `factory unblock`: change the blocked status of the task.
  - `factory tasks`: prints the task list.
  - `factory pause <id>`, `factory pause --all` and `factory resume <id>`: pause and resume tasks.
  - `factory goto <step-path> --reason <text>`: moves the task back to an earlier step.
  - `factory artifact path <name>`: prints the absolute path of a task artifact file.
  - `factory catalog list` and `factory catalog install <id> --generic|--local`: browse and install catalog items.
  - `factory terminal focus <id>` and `factory terminal send-prompt <id> <text>`: focus a task session and send it a prompt.
  - `factory clean`: lists finished tasks and whether their work is merged.
  - `factory approve`, `factory request-changes <text>` and `factory open-ide`: approval actions.
  - `factory wait`, `factory poll` and `factory external-done <id>`: external waiting.
  - `factory library commit <message> <paths...>`: commits the given library files in the repository that contains the library, and nothing else.

### Terminal adapter

- The factory never calls a terminal tool directly. All terminal actions go through `factory terminal` commands, which call the adapter configured in `.factory/factory.yaml`.
- Adding a terminal means adding one adapter, with no change in the steps or the orchestrator.
- An adapter implements:
  - `check`: checks that the terminal is available, and gives the fix if not
  - `start-session <name> <cwd> <prompt> -- <claude args>`: opens a new terminal in `cwd`, starts Claude with the args and the first prompt, and returns a handle
  - `close <handle>`: stops the Claude session and closes its terminal
  - Optional: `send-prompt <handle> <text>`, `focus <handle>`, `state <handle>` (the live session state, `gone` when the session no longer exists), `wait-idle <handle>` (waits until the session finishes its current turn) and `notify <text>`. An adapter that does not support them says so, and the factory hides the actions that need them.
- This build ships one adapter: `herdr`.

#### Herdr adapter

- `check`: `HERDR_ENV=1`.
- `start-session`:
  - In a worktree: `herdr worktree open --path <cwd>`. In the main repository: `herdr tab create`.
  - Then `herdr agent start <name> --kind claude --pane <pane_id> -- <claude args>`, then `herdr agent prompt <name> <prompt>`.
  - The pane id is read from the JSON response, never guessed.
  - The handle is the Herdr agent name and the workspace or tab id.
- `close`: closes the workspace or the tab. Check that this also stops the Claude process. If it does not, stop it first.
- `send-prompt`: `herdr agent prompt`. `focus`: `herdr agent focus`. `state`: `herdr agent get`. `wait-idle`: `herdr agent wait`. `notify`: `herdr notification`. Check the exact syntax with the installed `herdr` binary.

### Versioning and migration

- The factory has a data format version: one integer, starting at 1. It covers everything the factory reads and writes: the `.factory/` layout, the task state, the step and pipeline manifests, the config and the backlog.
- `.factory/factory.yaml` stores the version of the repository data. `<library>/factory.yaml` stores the version of the generic library.
- Every `factory` command checks the data version. It refuses to run when the version is different from its own.
- A build that changes the data format increases the version by 1 and adds a migration script `migrations/<from>-to-<to>`. The builder finds the previous format in the git history of `FACTORY_SOURCE`.
- At start, the orchestrator compares the data version with its own version:
  - Same: it shows the menu.
  - Older: it runs the built-in step `migrate`. The menu is shown only after the migration.
  - Newer: it stops and tells the user to update the factory.
- The `migrate` step:
  - Backs up `.factory/` to `.factory.backup-<date>/`.
  - If the library is in a git repository, requires a clean git status in the library, so the change can be reviewed and reverted with git. Otherwise, backs up the library to `<library>.backup-<date>/`.
  - Runs the migration scripts in order, on the repository data, the active tasks and the generic library.
  - Shows a summary and the backup path.

### Rebuild

- `FACTORY_SOURCE` holds no user data. A rebuild can replace all of it.
- A rebuild never changes a library or a `.factory/` folder, except through a migration script.

### File organization

In the main repository, never committed:

```
.factory/
  factory.yaml       # Data format version, library path and terminal
  config.yaml        # Step config values for this repository
  claude-settings.json  # Permission rules for task sessions
  backlog.md         # Tasks not started yet
  server.json        # Port, token and process id of the running local server
  pipelines/         # Local pipelines, one <id>.yaml file each
  steps/             # Local steps, one <id>.md file each
  tasks/
    <id>/
      task.json      # Task state
      events.jsonl   # Event log, written by the factory CLI
      artifacts/     # Files made during the task
    archive/         # Deleted tasks, kept for history
```

In `FACTORY_SOURCE`:

```
builtin/
  pipelines/         # Built-in pipelines
  steps/             # Built-in steps
catalog/
  pipelines/         # Pipeline templates, installed by copy
  steps/             # Step templates, installed by copy
migrations/          # One script per format version change
```

The library, a folder in any git repository:

```
<library>/
  factory.yaml       # Data format version of the library
  pipelines/         # Generic pipelines created by the user
  steps/             # Generic steps created by the user
```

### Documentation

- `YOUR_WORKING_DIR/README.md` contains:
  - What the factory does, in a few lines.
  - The concepts, one line each: task, pipeline, step, step types, local / generic / built-in levels, catalog, artifacts.
  - Install and prerequisites: the plugin marketplace, Herdr, the Bash allowlist.
  - A tutorial with the exact actions and the expected result of each:
    1. Init the factory in a repository and install the starter pack.
    2. Run `quick-task` on a small change: follow it in Herdr, show tasks, approve the `user-validation` step, check the commit.
    3. Pause all tasks on Exit, start the factory again, and resume.
    4. Create a step with "Create a new step".
    5. Copy `quick-task` in the pipeline editor, add the new step, save, and run it.
    6. Open the dashboard, follow a task across the columns, and approve a `user-validation` from a card.
  - A reference: the menu actions, the `factory` commands, and the step and pipeline fields.
  - Troubleshooting: terminal check failed, data version mismatch, session gone.
- The README uses simple English and short sentences.

### Verification

- The build is verified with an automated test run. Its report goes to `VERIFICATION_DIR`.
- The report has one section per milestone, with the tests run and their results.
- Test setup, all inside `VERIFICATION_DIR`:
  - A test git repository. Its `origin` remote is a local bare repository, so nothing is pushed to a real remote.
  - A test library in its own test git repository. The tests never change a real library.
  - `worktree_root` points inside `VERIFICATION_DIR`.
- CLI tests, without Herdr or Claude:
  - Init creates `.factory/` and `factory.yaml` with the version and the library path, and adds the `.git/info/exclude` entries. `.gitignore` is unchanged.
  - A local step overrides a generic step, which overrides a built-in step.
  - Config values follow the order `with`, then `config.yaml`, then default. A missing value makes `factory next` ask for it.
  - `next`, `done` and `skip` on a test pipeline: `done_check` passes and fails, and `skip` is refused for a required step.
  - Composite steps: the full path is shown, `reads` and `writes` are computed, and a loop is refused.
  - A pipeline that lists `create-worktree` but not as its first step is refused.
  - Backlog add, list, remove and move, by id. A hand-written entry without an id gets one. Launching from an entry saves its summary in the task state and removes the entry.
  - The event log contains the expected events.
  - A command refuses data with another version. A test migration from version 1 to a fake version 2 runs and creates the backup.
  - `factory pipeline check` reports each error and warning type on test pipelines.
  - The editor server API, tested without a browser: list, get a step, load, copy, check and save. Requests without the token or with a wrong `Origin` are rejected.
  - The dashboard API, tested without a browser: the task list returns column, status and session state. Each action route calls the same function as its CLI command, checked with the fake adapter. Backlog move changes the order. The launch form route returns the dry-run result.
  - A second `factory dashboard` reuses the running server from `.factory/server.json`.
  - With a fake test adapter that records its calls, launch and delete call only the adapter, never `herdr` directly.
  - `factory block` and `factory unblock` change the status, and `factory tasks` lists blocked tasks first.
  - With the fake test adapter, pause saves the status and closes the terminal, and resume restores the status with the same session id.
  - Worktree creation on the test repository, with git only: new branch, existing local branch behind `origin` (fast-forwarded), branch only on `origin`, diverged branch (stops), and branch used by another worktree (stops).
  - `factory goto` moves back to an earlier step, refuses a later step, and blocks the task on the 3rd jump back to the same step.
  - `factory artifact path` creates the artifacts folder and prints an absolute path in the main repository, also when called from a worktree.
  - For a subagent step, `factory next` prints the Agent call with the right model and effort: the pipeline entry value wins over the manifest value.
  - `factory pipeline check` warns about `model` or `effort` on a step that runs in the session.
  - Installing a catalog pipeline copies it and offers its missing steps. The status shows not installed, installed, and installed and changed since.
  - Every `factory` command written in the README exists in the CLI.
  - No catalog file refers to a project-specific skill or tool.
  - `factory catalog list` shows the missing `requires` of an item.
  - The CLI runs on a machine with only `uv` installed: `uv` installs the dependencies on the first run.
  - A task starts in `start_column` and moves when a step with a `column` starts. The pipeline entry wins over the manifest. An unknown column is a pipeline check error.
  - `user-validation` sets `awaiting_approval`. `factory approve` lets `factory done` pass. `factory request-changes` sets `active` and sends the text with the fake adapter.
  - `factory wait` sets `waiting_external`. `factory poll` ends the wait when the `done_check` passes, sends the message with the fake adapter, and skips paused tasks. `factory external-done` ends a wait without a `done_check`.
  - `factory launch --dry-run` reports the id, the worktree path and the branch case, and changes nothing. A taken id gets a suffix.
  - When the fake adapter fails to start the session, `factory launch` removes the worktree, the branch and the task folder it created.
  - `factory delete --dry-run` shows uncommitted changes and unpushed commits, and changes nothing. `factory delete` refuses them without `--confirm-unpushed`.
  - Two processes writing `config.yaml` and `backlog.md` at the same time lose no write.
  - For a task without a worktree, `factory next` prints commands with `--task <id>`, and a command without it fails with a message that says to add it.
  - `factory done` on the last step sets the task to `finished` and logs `task_finished`.
  - With the fake test adapter, focus and send prompt call the adapter, and are hidden when the adapter does not support them.
  - `factory clean` detects a branch merged into `origin/<base_ref>`, a pushed branch whose remote branch was deleted, and a branch not merged.
  - `factory library commit` commits only the given library files. Another staged file in the test library repository stays staged and is not committed.
- End-to-end test with the Herdr adapter and Claude, on the test repository:
  - Launching a test pipeline fetches `origin`, creates the worktree from `origin/main`, opens it in Herdr and starts Claude with the task id as its name. Claude receives the first prompt.
  - The test pipeline has two `script` steps. The task session runs them to the end with `factory next` and `factory done`.
  - The test Claude session starts with `.factory/claude-settings.json` and never waits on a permission prompt.
  - Pausing the task closes its terminal. Resuming it reopens the same Claude session, which continues the pipeline.
  - Deleting the task asks for approval when there are uncommitted changes, closes the task terminal, removes the worktree and archives the task folder.
- The tests close only the Herdr workspaces, tabs and panes they created.
- At the end, the tests remove the test repositories. The report stays.

## How You're Graded

- You'll be graded on a continuous basis based on every completed bullet in the Definition Of Done.
- Every step of Workflow must be fully accomplished: plan, build and verify.
- Instant failure if you write project deliverables outside `YOUR_WORKING_DIR` with the exception of `SPEC_DIR`, `PLAN_DIR`, `VERIFICATION_DIR` and `PROJECT_ROOT/.claude-plugin/marketplace.json`.
- Instant failure if you read any part of any file inside `<PROJECT_ROOT>/specs/*` that isn't your own spec.
- Instant failure if you close a Herdr workspace, tab, pane or session you did not create.
- Running tools outside these directories is allowed. Temporary files and tool-managed runtime data (caches, logs, browser profiles, updater logs) may use their normal locations and are not grading failures.
- If you find you've mistakenly caused a failure, stop immediately and report your failure.

