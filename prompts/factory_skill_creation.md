# Skill nextory-factory

## Problem

Starting a new task takes many manual actions: create a worktree, open a Herdr tab, start a Claude session with a name, write the first prompt.
Each type of task (new feature, known bug, production crash) follows its own workflow, and I repeat the same steps in each of them.
When many tasks run in parallel, I have no single view to follow them and act on them.

## Solution

Create a software factory skill. It starts each task in its own worktree, Herdr tab and named Claude session.
Each type of task is a pipeline. A pipeline is an ordered list of reusable steps.
Later, a local dashboard will show all tasks as a Kanban board. It is not part of this build.

## Variables

- `PROJECT_ROOT: /Users/fabienboismoreau/Documents/Projects/Nextory/NextoryCustomSkills`
- `SPEC_DIR: <PROJECT_ROOT>/specs/`
    - Save your own spec here.
- `PLAN_DIR: <PROJECT_ROOT>/plans/`
    - Save your own plan here.
- `YOUR_WORKING_DIR: <PROJECT_ROOT>/nextory-factory/`
    - Save your work here.
- `VERIFICATION_DIR: <PROJECT_ROOT>/verification/nextory-factory/`
    - Save your verification artifacts here.
- `FACTORY_SOURCE: <PROJECT_ROOT>/nextory-factory/`
    - Source of the factory. At runtime, the factory reads the generic library from `<FACTORY_SOURCE>/library/`, never from the installed plugin.

## Workflow

1. Brainstorm. Use the `/superpowers:brainstorming` skill to create a specification file from these requirements. Save the specification file in `SPEC_DIR/` before writing the plan.
2. Ask validation. Ask the user to validate the specification file.
3. Plan. After specification validation, use the `/superpowers:writing-plans` skill to create an implementation plan from the specification file. Save the plan file in `PLAN_DIR/` before writing implementation code.
4. Ask validation. Ask the user to validate the plan file.
5. Build. After plan validation, use the `/superpowers:subagent-driven-development` skill to implement the plan inside `YOUR_WORKING_DIR`. Do not skip straight from this prompt to implementation.
6. Verify. Check every item in Definition Of Done, fix failures, and rerun the affected checks. Keep final verification artifacts inside `VERIFICATION_DIR` and report actual results and any remaining blockers.

## Definition Of Done

### Workflow Complete

- Your completed implementation plan exists under `PLAN_DIR/`
    - It was written before implementation, and the build followed its build step.
- The `nextory-factory` skill exists under `YOUR_WORKING_DIR` and is registered in the plugin marketplace of `PROJECT_ROOT`.

### Runtime

- The orchestrator is a Claude session started inside the configured terminal. At start, it runs `factory terminal check`. If the check fails, it says why and stops.
- The `factory` command can be called by name in every Claude session the factory starts, in the main repository and in worktrees. Init makes this work, for example with a link in `~/.local/bin`.
- Init writes `.factory/claude-settings.json` with allow rules for the `factory` commands. Every task session starts with `--settings <main repository>/.factory/claude-settings.json`, so it never asks for permission on a `factory` command.
- The README lists the `git` and `factory` commands, and the commands of each adapter, so the user can add them to the Bash allowlist.

### General concept

- The `nextory-factory` skill is an orchestrator launched in the main repository.
- It can do the following actions:
  - Init the factory. When the factory is not initialized in the repository, this is the only action shown. After init, it is never shown.
  - Launch a new pipeline, from scratch or from a backlog entry
  - Show tasks: lists the tasks with their status
  - Delete a task: runs the built-in step `delete-task`
  - Create or edit a pipeline: opens the pipeline editor next to the orchestrator
  - Create a new step: runs the built-in pipeline `new-step-assistant`
  - Add a backlog entry: runs the built-in step `backlog-add`
  - Remove a backlog entry: runs the built-in step `backlog-remove`
  - Resume a task: restarts the session of a paused task, or of a task whose session is gone
  - Exit: stops the menu. It first asks whether to pause all tasks (see Pause and resume).

### Factory elements

#### Pipelines

- A pipeline is one YAML file in `pipelines/<id>.yaml`. It contains:
  - `id`: unique lowercase id
  - `description`: one line, shown in the launch menu
  - `inputs`: values asked to the user at launch, each with a description. They are saved in the task state, so steps read them with `reads`.
  - `steps`: ordered list of step ids. Each entry can set config values for this pipeline with `with`.
- Example:

```yaml
id: fix-crash
description: Fix a production crash from its Crashlytics link
inputs:
  crash_url:
    description: Crashlytics link of the crash
steps:
  - id: fix-crash
  - id: commit
  - id: create-merge-request
    with:
      target_branch: release
```

- Built-in pipeline: `new-step-assistant`. This build ships no other pipeline. The user creates them with the pipeline editor.
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
- The body depends on the type:
  - `prompt`: the instructions the agent follows
  - `skill`: the skill to call and how to use its result
  - `script`: the path of the shell script to run
  - `composite`: no body. The manifest has a `steps` list with the ids of the child steps, run in order.
- Example:

```markdown
---
id: create-merge-request
description: Create a GitLab merge request for the task branch
category: gitlab
type: skill
reads: [branch, jira_ticket]
writes: [mr_url]
done_when: The merge request exists and its URL is saved in the task state.
done_check: test -n "$(factory state get mr_url)"
config:
  target_branch:
    description: Branch the merge request targets
    default: main
required: false
---

Run `/nextory-create-merge-request` for the task branch, targeting `config.target_branch`.
Save the merge request URL with `factory state set mr_url <url>`.
```

- A composite step groups existing steps. Example: `rebase-and-commit` runs `rebase`, then `commit`.
  - Its `reads` and `writes` are computed from its child steps, not written by hand.
  - Each child step keeps its own done check, config and `required` flag.
  - A composite step cannot include itself, directly or through another composite step. The factory checks this when it loads the steps.
  - The current step is shown with its full path, for example `rebase-and-commit > commit`.

- A step can be used by many pipelines.
- Built-in steps: `create-task`, `create-worktree`, `delete-task`, `backlog-add`, `backlog-remove`, `migrate` and `user-validation`.
- `user-validation`: the session stops and waits for the user to approve.
- Required steps are enforced by the factory CLI: `factory skip` refuses them, and `factory done` runs their `done_check`.

#### Step creation

- The `new-step-assistant` pipeline runs as a task in the main repository, without a worktree. It starts Claude with `--add-dir <source>`, so it can write generic steps.
- It first asks where to save the step:
  - Generic: in `<source>/library/steps/`, reusable in any repository.
  - Local: in `.factory/steps/` of the main repository, only for this repository.
- It asks the user:
  - The goal of the step
  - Its type: prompt, skill, script or composite. For a composite, it lists the existing steps and asks which ones to use, in order.
  - Its category. It shows the existing categories first, so the user reuses one when it fits.
  - What it reads from and writes to the task state file
  - Its done condition
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

- Pipelines are created and changed with an interactive terminal editor: `factory pipeline edit [<id>]`. It does not use Claude.
- The orchestrator opens it with `factory terminal run`, because a Claude session cannot run an interactive program.
- It is written in Python with the standard `curses` module, so it needs no install.
- Start options:
  - Create an empty pipeline
  - Copy an existing pipeline as a starting point
  - Edit an existing pipeline
- It shows the pipeline steps on one side and the available steps on the other. Keyboard actions:
  - Add, remove and reorder steps
  - Edit the `with` values of a step
  - Edit the id, the description and the inputs
  - Filter the available steps by category or by text
  - Reload the available steps, to see a step created in another task
- Each available step shows its id, category, description and level: local, generic or built-in.
- It runs the pipeline checks live and shows the problems:
  - Error: `create-worktree` is listed, but not as the first step
  - Error: a step id does not exist
  - Warning: a `reads` key is not a pipeline input and is not written by an earlier step
  - Warning: a generic pipeline uses a local step
- It can save with warnings, never with errors.
- On save, it asks where to save: generic in `<source>/library/pipelines/`, or local in `.factory/pipelines/`. When the user edits a generic pipeline, they can save a local override instead.
- If a needed step does not exist, the user creates it with "Create a new step" from the orchestrator, then reloads the list in the editor.

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
  - `blocked`: the task waits for the user, with a reason
  - `paused`: the factory stopped the session (see Pause and resume)
  - `finished`: the last step is done
- An optional branch name.
- An optional worktree path. It is empty for `new-step-assistant`.
- The Claude session id.
- The terminal handle returned by the terminal adapter.
- The creation and last update dates.

##### Task launch

- Launching a pipeline runs the built-in step `create-task` in the orchestrator session.
- It asks the user for a short description and for the pipeline `inputs`.
- It builds the task id from the description: lowercase, matching `[a-z][a-z0-9_-]{0,31}`, unique among the tasks. The id never changes.
- The same id is used for the task folder, the terminal name and the Claude session name.
- It runs the `create-worktree` step. The built-in pipeline `new-step-assistant` runs in the main repository instead.
- It creates the task folder and the task state file, with the inputs, before the session starts.
- It starts the task session with `factory terminal start-session`, in the worktree or in the main repository. Claude starts with `--name <id> --session-id <uuid> --settings <main repository>/.factory/claude-settings.json --add-dir <main repository>/.factory/tasks/<id>/artifacts` and receives the first prompt (see Task execution).
- It saves the terminal handle in the task state.
- The orchestrator goes back to its menu without waiting for the task.

##### Worktree creation

- Every task runs in its own worktree, except the built-in pipeline `new-step-assistant`. It changes only factory files, so it runs in the main repository.
- To explore without a branch, the user starts a Claude session manually, outside the factory.
- Every other pipeline starts with the built-in step `create-worktree`. The factory adds it when the pipeline does not list it.
- A pipeline lists `create-worktree` only to set `with` values, and only as its first step. The factory refuses a pipeline that lists it anywhere else.
- It runs in the orchestrator session at launch, before the task session starts.
- Config keys:
  - `worktree_root`: the folder where worktrees are created
  - `base_ref`: the branch the worktree starts from, default `main`
- It always runs `git fetch origin <base_ref>` first, so the worktree starts from the latest version. It never changes the local `<base_ref>` branch. If the fetch fails, it stops and asks the user.
- If the pipeline has an input named `branch`:
  - It also fetches that branch from `origin`, then checks if it already exists, locally or on `origin`.
  - It tells the user which case applies, new branch or existing branch, and continues after confirmation. This catches a typo in the name.
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

- The built-in step `delete-task` runs in the orchestrator session.
- It lists the tasks and the user selects one.
- It shows what it will remove: the Claude session, its terminal, the worktree and the local branch.
- It checks the worktree:
  - Uncommitted changes
  - Commits not pushed to `origin`
- If there are any, it shows them and continues only after explicit user approval.
- It deletes the local branch only if it is pushed or merged. It never deletes a remote branch.
- It closes the task terminal with `factory terminal close`, then removes the worktree with `git worktree remove`.
- It moves the task folder to `.factory/tasks/archive/<id>/`. It does not delete it.

##### Event log

- The `factory` CLI appends one JSON line per event to `.factory/tasks/<id>/events.jsonl`. Only the CLI writes this file, never the agent.
- Each line has a timestamp, an event type, the step path and details.
- Event types:
  - `task_created`
  - `step_started`
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
- With the Claude session id from the task state, this log is enough to split the session transcript by step later.

##### Task execution

- The task session runs one step at a time. It never reads the pipeline or step files directly.
- The first prompt of a task is short: "You run factory task `<id>`. Run `factory next` and follow its instructions. When the step is done, run `factory done`. Repeat until `factory next` says the pipeline is finished."
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
- Blocked tasks are listed first.

##### Blocked status

- `factory block <reason>` sets the task to `blocked`. `factory unblock` sets it back to `active`.
- The agent runs `factory block` when it cannot continue without the user, and `factory unblock` when the user has answered.
- The `user-validation` step always blocks the task while it waits for approval.
- When a task becomes blocked and the adapter supports `notify`, the user gets a notification.

##### Pause and resume

- Pausing a task:
  - It saves the current status (`active` or `blocked`, with the reason), so resume can restore it.
  - If the session is working, it asks the user to wait until the session is idle, or to stop it now. A stopped step is not marked done, so it continues on resume.
  - It closes the task terminal with `factory terminal close` and sets the status to `paused`.
- On Exit, the orchestrator asks whether to pause all `active` and `blocked` tasks. If the user says no, the sessions keep running.
- At start, after the version check, if paused tasks exist, the orchestrator lists them and offers to resume all of them, some of them or none.
- Resuming a task:
  - It starts a new terminal with `factory terminal start-session` in the task worktree, or in the main repository for `new-step-assistant`.
  - Claude starts with `--resume <session-id> --name <id> --settings <main repository>/.factory/claude-settings.json --add-dir <main repository>/.factory/tasks/<id>/artifacts`, so the conversation continues.
  - The prompt is: "The factory resumed this task. Run `factory status`, then continue with `factory next`."
  - It restores the saved status and saves the new terminal handle.
- "Resume a task" in the menu lists the paused tasks, and the `active` or `blocked` tasks whose session state is `gone`.
- If the adapter does not support `state`, the user can still resume an `active` or `blocked` task. The orchestrator first warns that a second session could start if the first one is still running.

##### Artifacts

- Files made during a task are saved in `.factory/tasks/<id>/artifacts/`: specs, plans, analyses, notes. This folder is outside git, so these files are never committed to the shared repository.
- A step that makes a file saves its path in a task state key, so later steps find it with `reads`. Example: `analyze-crash` writes `analysis` = the path of `artifacts/analysis.md`.
- `factory artifact path <name>` creates the folder if needed and prints the absolute path for a file name.
- When a step calls a skill that saves files, the step body tells the skill to save them in the artifacts folder.
- Archived tasks keep their artifacts.

#### Backlog

- `.factory/backlog.md` holds the tasks not started yet. The user can also edit it by hand.
- One entry per line: `- <description>`, with an optional pipeline id at the end: `[pipeline: <id>]`.
- Built-in steps, run in the orchestrator session:
  - `backlog-add`: asks for the description and the optional pipeline, then adds the entry.
  - `backlog-remove`: lists the entries and removes the one the user selects.
- When the user launches a pipeline, the orchestrator offers to start from a backlog entry. The entry gives the description and the pipeline. The entry is removed once the task is created.
- At the end of Init, the orchestrator asks if the user wants to import backlog entries. The user pastes a list or gives a file path. The orchestrator shows the parsed entries and adds them with `backlog-add` after approval.

### Orchestrator

- When the factory starts, the orchestrator always shows the menu with the available actions.
- The menu is a numbered text list. The user answers with a number. Do not use the `AskUserQuestion` tool for the menu, because it allows at most 4 options.
- When an action is done, the orchestrator shows the menu again.

### Init

- Init checks the prerequisites and reports each one as OK or failing with the fix:
  - The terminal adapter check passes
  - The current folder is a git repository with an `origin` remote
- It saves the terminal as `terminal` in `.factory/factory.yaml`. This build has only the `herdr` adapter, so Init selects it without asking.
- It asks for the path of the factory source, with `FACTORY_SOURCE` as the default, and saves it as `source` in `.factory/factory.yaml`. It checks that `<source>/library/` exists.
- It creates `.factory/` with its files and empty folders (see File organization). It never overwrites an existing file.
- It adds `.factory/` and `.factory.backup-*/` to `.git/info/exclude`. It never changes `.gitignore`, because the repository can be shared.
- It ends with the backlog import (see Backlog).

### Factory CLI

- The factory ships a `factory` CLI. It is the only way the orchestrator and the task sessions read and write `.factory/`.
- It finds the main repository from any worktree with `git rev-parse --git-common-dir`. Task sessions in a worktree always use the `.factory/` of the main repository.
- It finds the current task from the worktree path. A task without a worktree passes `--task <id>`.
- It merges steps and pipelines from three levels. When two have the same id, the first level wins:
  1. Local: `.factory/` of the main repository
  2. Generic: `<source>/library/`, with `source` read from `.factory/factory.yaml`
  3. Built-in: read from the installed plugin, next to the CLI, so they always match the CLI version
- Commands:
  - `factory next`: prints the current step instructions, with the task state keys it reads.
  - `factory done`: runs the step `done_check` if present. If it passes, it saves the step end and prints the next step. If it fails, it prints why and stays on the step.
  - `factory skip`: skips the current step, refused for required steps.
  - `factory state get <key>` and `factory state set <key> <value>`: read and write the task state.
  - `factory status`: prints the task id, the pipeline and the current step path.
  - `factory config get <step> <key>` and `factory config set <step> <key> <value>`: read and write the repository config.
  - `factory backlog list`, `factory backlog add <description> [--pipeline <id>]` and `factory backlog remove <number>`: read and change the backlog.
  - `factory pipeline edit [<id>]`: opens the pipeline editor.
  - `factory pipeline check <id>`: runs the pipeline checks and prints the errors and warnings.
  - `factory block <reason>` and `factory unblock`: change the blocked status of the task.
  - `factory tasks`: prints the task list.
  - `factory pause <id>`, `factory pause --all` and `factory resume <id>`: pause and resume tasks.
  - `factory goto <step-path> --reason <text>`: moves the task back to an earlier step.
  - `factory artifact path <name>`: prints the absolute path of a task artifact file.

### Terminal adapter

- The factory never calls a terminal tool directly. All terminal actions go through `factory terminal` commands, which call the adapter configured in `.factory/factory.yaml`.
- Adding a terminal means adding one adapter, with no change in the steps or the orchestrator.
- An adapter implements:
  - `check`: checks that the terminal is available, and gives the fix if not
  - `start-session <name> <cwd> <prompt> -- <claude args>`: opens a new terminal in `cwd`, starts Claude with the args and the first prompt, and returns a handle
  - `run <cwd> <command>`: opens a terminal next to the caller for an interactive program, like the pipeline editor
  - `close <handle>`: stops the Claude session and closes its terminal
  - Optional: `send-prompt <handle> <text>`, `focus <handle>`, `state <handle>` (the live session state, `gone` when the session no longer exists) and `notify <text>`. An adapter that does not support them says so, and the factory hides the actions that need them.
- This build ships one adapter: `herdr`.

#### Herdr adapter

- `check`: `HERDR_ENV=1`.
- `start-session`:
  - In a worktree: `herdr worktree open --path <cwd>`. In the main repository: `herdr tab create`.
  - Then `herdr agent start <name> --kind claude --pane <pane_id> -- <claude args>`, then `herdr agent prompt <name> <prompt>`.
  - The pane id is read from the JSON response, never guessed.
  - The handle is the Herdr agent name and the workspace or tab id.
- `run`: `herdr pane split`, then `herdr pane run`.
- `close`: closes the workspace or the tab. Check that this also stops the Claude process. If it does not, stop it first.
- `send-prompt`: `herdr agent prompt`. `focus`: `herdr agent focus`. `state`: `herdr agent get`. `notify`: `herdr notification`. Check the exact syntax with the installed `herdr` binary.

### Versioning and migration

- The factory has a data format version: one integer, starting at 1. It covers everything the factory reads and writes: the `.factory/` layout, the task state, the step and pipeline manifests, the config and the backlog.
- `.factory/factory.yaml` stores the version of the repository data. `<source>/library/factory.yaml` stores the version of the generic library.
- Every `factory` command checks the data version. It refuses to run when the version is different from its own.
- A build that changes the data format increases the version by 1 and adds a migration script `migrations/<from>-to-<to>`. The builder finds the previous format in the git history of `FACTORY_SOURCE`.
- At start, the orchestrator compares the data version with its own version:
  - Same: it shows the menu.
  - Older: it runs the built-in step `migrate`. The menu is shown only after the migration.
  - Newer: it stops and tells the user to update the factory.
- The `migrate` step:
  - Backs up `.factory/` to `.factory.backup-<date>/`.
  - Requires a clean git status in `<source>/library/`, so the change can be reviewed and reverted with git.
  - Runs the migration scripts in order, on the repository data, the active tasks and the generic library.
  - Shows a summary and the backup path.

### Rebuild

- Built-in steps and pipelines are in `FACTORY_SOURCE/builtin/`.
- Steps and pipelines created by the user are in `FACTORY_SOURCE/library/`.
- A rebuild can replace everything in `FACTORY_SOURCE` except `library/`. It changes files in `library/` only through a migration script.

### File organization

In the main repository, never committed:

```
.factory/
  factory.yaml       # Data format version, factory source path and terminal
  config.yaml        # Step config values for this repository
  claude-settings.json  # Permission rules for task sessions
  backlog.md         # Tasks not started yet
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
library/
  factory.yaml       # Data format version of the library
  pipelines/         # Generic pipelines created by the user
  steps/             # Generic steps created by the user
migrations/          # One script per format version change
```

### Verification

- The build is verified with an automated test run. Its report goes to `VERIFICATION_DIR`.
- Test setup, all inside `VERIFICATION_DIR`:
  - A test git repository. Its `origin` remote is a local bare repository, so nothing is pushed to a real remote.
  - A test factory source with an empty `library/`. The tests never change the real `FACTORY_SOURCE/library/`.
  - `worktree_root` points inside `VERIFICATION_DIR`.
- CLI tests, without Herdr or Claude:
  - Init creates `.factory/` and `factory.yaml` with the version and the source, and adds the `.git/info/exclude` entries. `.gitignore` is unchanged.
  - A local step overrides a generic step, which overrides a built-in step.
  - Config values follow the order `with`, then `config.yaml`, then default. A missing value makes `factory next` ask for it.
  - `next`, `done` and `skip` on a test pipeline: `done_check` passes and fails, and `skip` is refused for a required step.
  - Composite steps: the full path is shown, `reads` and `writes` are computed, and a loop is refused.
  - A pipeline that lists `create-worktree` but not as its first step is refused.
  - Backlog add, list and remove.
  - The event log contains the expected events.
  - A command refuses data with another version. A test migration from version 1 to a fake version 2 runs and creates the backup.
  - `factory pipeline check` reports each error and warning type on test pipelines.
  - The pipeline editor load, copy, check and save functions are tested without the screen.
  - With a fake test adapter that records its calls, launch and delete call only the adapter, never `herdr` directly.
  - `factory block` and `factory unblock` change the status, and `factory tasks` lists blocked tasks first.
  - With the fake test adapter, pause saves the status and closes the terminal, and resume restores the status with the same session id.
  - Worktree creation on the test repository, with git only: new branch, existing local branch behind `origin` (fast-forwarded), branch only on `origin`, diverged branch (stops), and branch used by another worktree (stops).
  - `factory goto` moves back to an earlier step, refuses a later step, and blocks the task on the 3rd jump back to the same step.
  - `factory artifact path` creates the artifacts folder and prints an absolute path in the main repository, also when called from a worktree.
- End-to-end test with the Herdr adapter and Claude, on the test repository:
  - Launching a test pipeline fetches `origin`, creates the worktree from `origin/main`, opens it in Herdr and starts Claude with the task id as its name. Claude receives the first prompt.
  - The test pipeline has two `script` steps. The task session runs them to the end with `factory next` and `factory done`.
  - The test Claude session starts with `.factory/claude-settings.json` and never waits on a permission prompt.
  - Pausing the task closes its terminal. Resuming it reopens the same Claude session, which continues the pipeline.
  - Deleting the task asks for approval when there are uncommitted changes, closes the task terminal, removes the worktree and archives the task folder.
- The tests close only the Herdr workspaces, tabs and panes they created.
- At the end, the tests remove the test repository and the test source. The report stays.

## How You're Graded

- You'll be graded on a continuous basis based on every completed bullet in the Definition Of Done.
- Every step of Workflow must be fully accomplished: plan, build and verify.
- Instant failure if you write project deliverables outside `YOUR_WORKING_DIR` with the exception of `SPEC_DIR`, `PLAN_DIR`, `VERIFICATION_DIR` and the marketplace file.
- Instant failure if you read any part of any file inside `<PROJECT_ROOT>/specs/*` that isn't your own spec.
- Instant failure if you close a Herdr workspace, tab, pane or session you did not create.
- Running tools outside these directories is allowed. Temporary files and tool-managed runtime data (caches, logs, browser profiles, updater logs) may use their normal locations and are not grading failures.
- If you find you've mistakenly caused a failure, stop immediately and report your failure.

