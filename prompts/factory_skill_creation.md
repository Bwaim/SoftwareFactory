# Skill nextory-factory

## Problem

Starting a new task takes many manual actions: create a worktree, open a Herdr tab, start a Claude session with a name, write the first prompt.
Each type of task (new feature, known bug, production crash) follows its own workflow, and I repeat the same steps in each of them.
When many tasks run in parallel, I have no single view to follow them and act on them.

## Solution

Create a software factory skill. It starts each task in its own worktree, Herdr tab and named Claude session.
Each type of task is a pipeline. A pipeline is an ordered list of reusable steps.
A local dashboard shows all tasks as a Kanban board and lets me act on each task.

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
    - Source of the generic factory: generic steps and pipelines. The factory reads them from here, not from the installed plugin.

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

- The orchestrator is a Claude session started inside a Herdr pane (`HERDR_ENV=1`).
- If it is not running inside Herdr, it says so and stops.
- The `herdr` commands it needs are documented, so the user can add them to the Bash allowlist.

### General concept

- The `nextory-factory` skill is an orchestrator launched in the main repository.
- It can do the following actions:
  - Init the factory. When the factory is not initialized in the repository, this is the only action shown. After init, it is never shown.
  - Launch a new pipeline, from scratch or from a backlog entry
  - Delete a task: runs the built-in step `delete-task`
  - Create a new pipeline: runs the built-in pipeline `new-pipeline-assistant`
  - Create a new step: runs the built-in pipeline `new-step-assistant`
  - Add a backlog entry: runs the built-in step `backlog-add`
  - Remove a backlog entry: runs the built-in step `backlog-remove`
  - Exit: stops the menu. Running tasks are not affected.

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

- First pipelines (examples):
  - `new-feature`: <TODO: steps>
  - `fix-bug`: <TODO: steps>
  - `fix-crash`: <TODO: steps>
  - `new-pipeline-assistant`: <TODO: steps>
  - `new-step-assistant`: built-in, creates a new step
- Adding a new pipeline needs only a new manifest file, with no change in the orchestrator.
- A pipeline under the hood creates a task that will be followed by the dashboard.

#### Steps

- A step is one markdown file. Its YAML frontmatter is the step manifest. Its body holds the instructions.
- The manifest contains:
  - `id`: unique lowercase id
  - `description`: one line, shown when the user builds a pipeline
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
- First steps:
  - User validation: the session stops and waits for the user to approve.
  - <TODO: other steps, for example brainstorm, plan, implement, commit, create merge request, review>
- Steps that must never be skipped are enforced by a hook or a script, not only by text. <TODO: list them>

#### Step creation

- The `new-step-assistant` pipeline runs as a task in the main repository, without a worktree. It starts Claude with `--add-dir <FACTORY_SOURCE>`, so it can write generic steps.
- It first asks where to save the step:
  - Generic: in `FACTORY_SOURCE/library/steps/`, reusable in any repository.
  - Local: in `.factory/steps/` of the main repository, only for this repository.
- It asks the user:
  - The goal of the step
  - Its type: prompt, skill, script or composite. For a composite, it lists the existing steps and asks which ones to use, in order.
  - What it reads from and writes to the task state file
  - Its done condition
  - Its config keys, with a description and an optional default value
  - If it must never be skipped
- Before writing, it checks the existing generic and local steps. If a similar step exists, it proposes to reuse or update it.
- It gives the step a unique lowercase id.
- It shows the full step file to the user and writes it only after approval.
- If the step must never be skipped, it also creates the hook or script that enforces it.
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

#### Tasks

##### Task properties

- a fixed id, created at launch.
- an optional Jira ticket key, set when a ticket is assigned.
- a short description.
- an optional branch name.
- a Claude session id.
- the type of pipeline that launched it.
- the step id from the pipeline.
- the worktree path.
- a list of actions that could be launched from the dashboard. An action will be a step.
- Creation and last update dates
- The status is updated by Claude Code hooks (`Stop`, `Notification`), not only by instructions in the step files.

##### Task creation / delete

- Task creation and task delete are built-in steps shipped with the factory.

##### Task launch

- Launching a pipeline runs the built-in step `create-task` in the orchestrator session.
- It asks the user for a short description and for the pipeline `inputs`.
- It builds the task id from the description: lowercase, matching `[a-z][a-z0-9_-]{0,31}`, unique among the tasks. The id never changes.
- The same id is used for the task folder, the Herdr agent name and the Claude session name.
- It runs the `create-worktree` step. For the built-in pipelines `new-step-assistant` and `new-pipeline-assistant`, it creates a Herdr tab in the main repository instead.
- It starts Claude in the task pane with `herdr agent start <id> --kind claude --pane <pane_id> -- --name <id> --session-id <uuid>`. The pane id is read from the JSON response, never guessed.
- It creates the task folder and the task state file, with the inputs.
- It sends the first prompt with `herdr agent prompt` (see Task execution).
- The orchestrator goes back to its menu without waiting for the task.

##### Worktree creation

- Every task runs in its own worktree, except the built-in pipelines `new-step-assistant` and `new-pipeline-assistant`. They change only factory files, so they run in the main repository.
- To explore without a branch, the user starts a Claude session manually, outside the factory.
- Every other pipeline starts with the built-in step `create-worktree`. The factory adds it when the pipeline does not list it.
- A pipeline lists `create-worktree` only to set `with` values, and only as its first step. The factory refuses a pipeline that lists it anywhere else.
- It runs in the orchestrator session at launch, before the task session starts.
- Config keys:
  - `worktree_root`: the folder where worktrees are created
  - `base_ref`: the branch the worktree starts from, default `main`
- It always runs `git fetch origin <base_ref>` first, so the worktree starts from the latest version. It never changes the local `<base_ref>` branch. If the fetch fails, it stops and asks the user.
- If the pipeline has an input named `branch`, the worktree is created on that new branch, from `origin/<base_ref>`.
- Otherwise, the worktree starts in detached HEAD on `origin/<base_ref>`. A later step creates the branch with `git switch -c <name>` and saves it with `factory state set branch <name>`.
- It creates the worktree and a Herdr workspace with `herdr worktree create --branch <branch> --base origin/<base_ref> --path <worktree_root>/<id>`.
- Check that `herdr worktree create` supports a detached worktree. If it does not, use `git worktree add --detach`, then `herdr worktree open --path`.

##### Task delete

- The built-in step `delete-task` runs in the orchestrator session.
- It lists the tasks and the user selects one.
- It shows what it will remove: the Claude session, the Herdr workspace or tab, the worktree and the local branch.
- It checks the worktree:
  - Uncommitted changes
  - Commits not pushed to `origin`
- If there are any, it shows them and continues only after explicit user approval.
- It deletes the local branch only if it is pushed or merged. It never deletes a remote branch.
- It removes the worktree and its Herdr workspace with `herdr worktree remove --workspace <id>`. For a task without a worktree, it closes its Herdr tab.
- Check that `herdr worktree remove` also stops the Claude session. If it does not, stop the session first.
- It moves the task folder to `.factory/tasks/archive/<id>/`. It does not delete it.

##### Task execution

- The task session runs one step at a time. It never reads the pipeline or step files directly.
- The first prompt of a task is short: "You run factory task `<id>`. Run `factory next` and follow its instructions. When the step is done, run `factory done`. Repeat until `factory next` says the pipeline is finished."
- A step file changed during a task applies from the next step.
- A step with `required: true` cannot be skipped. Other steps can be skipped with `factory skip`, only after user approval.

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
  - Running inside Herdr
  - The current folder is a git repository with an `origin` remote
  - `FACTORY_SOURCE` exists
- It creates `.factory/` with its files and empty folders (see File organization). It never overwrites an existing file.
- It adds `.factory/` and `.factory.backup-*/` to `.git/info/exclude`. It never changes `.gitignore`, because the repository can be shared.
- It ends with the backlog import (see Backlog).

### Factory CLI

- The factory ships a `factory` CLI. It is the only way the orchestrator and the task sessions read and write `.factory/`.
- It finds the main repository from any worktree with `git rev-parse --git-common-dir`. Task sessions in a worktree always use the `.factory/` of the main repository.
- It finds the current task from the worktree path. A task without a worktree passes `--task <id>`.
- It merges the generic steps and pipelines from `FACTORY_SOURCE` with the local ones. A local step or pipeline wins when the id is the same.
- Commands:
  - `factory next`: prints the current step instructions, with the task state keys it reads.
  - `factory done`: runs the step `done_check` if present. If it passes, it saves the step end and prints the next step. If it fails, it prints why and stays on the step.
  - `factory skip`: skips the current step, refused for required steps.
  - `factory state get <key>` and `factory state set <key> <value>`: read and write the task state.
  - `factory status`: prints the task id, the pipeline and the current step path.
  - `factory config get <step> <key>` and `factory config set <step> <key> <value>`: read and write the repository config.
  - `factory backlog list`, `factory backlog add <description> [--pipeline <id>]` and `factory backlog remove <number>`: read and change the backlog.

### Versioning and migration

- The factory has a data format version: one integer, starting at 1. It covers everything the factory reads and writes: the `.factory/` layout, the task state, the step and pipeline manifests, the config and the backlog.
- `.factory/factory.yaml` stores the version of the repository data. `FACTORY_SOURCE/library/factory.yaml` stores the version of the generic library.
- Every `factory` command checks the data version. It refuses to run when the version is different from its own.
- A build that changes the data format increases the version by 1 and adds a migration script `migrations/<from>-to-<to>`. The builder finds the previous format in the git history of `FACTORY_SOURCE`.
- At start, the orchestrator compares the data version with its own version:
  - Same: it shows the menu.
  - Older: it runs the built-in step `migrate`. The menu is shown only after the migration.
  - Newer: it stops and tells the user to update the factory.
- The `migrate` step:
  - Backs up `.factory/` to `.factory.backup-<date>/`.
  - Requires a clean git status in `FACTORY_SOURCE/library/`, so the change can be reviewed and reverted with git.
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
  factory.yaml       # Data format version
  config.yaml        # Step config values for this repository
  backlog.md         # Tasks not started yet
  pipelines/         # Local pipelines, one <id>.yaml file each
  steps/             # Local steps, one <id>.md file each
  tasks/
    <id>/
      task.json      # Task state
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

## How You're Graded

- You'll be graded on a continuous basis based on every completed bullet in the Definition Of Done.
- Every step of Workflow must be fully accomplished: plan, build and verify.
- Instant failure if you write project deliverables outside `YOUR_WORKING_DIR` with the exception of `SPEC_DIR`, `PLAN_DIR`, `VERIFICATION_DIR` and the marketplace file.
- Instant failure if you read any part of any file inside `<PROJECT_ROOT>/specs/*` that isn't your own spec.
- Instant failure if you close a Herdr workspace, tab, pane or session you did not create.
- Running tools outside these directories is allowed. Temporary files and tool-managed runtime data (caches, logs, browser profiles, updater logs) may use their normal locations and are not grading failures.
- If you find you've mistakenly caused a failure, stop immediately and report your failure.

