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
- `NEXTORY_REPO: /Users/fabienboismoreau/Documents/Projects/Nextory/Nextory_ai/nextory`
- `TASKS_DIR: <TODO: where the task state files live at runtime>`

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

- The `nextry-factory` skill is an orchestrator launched on the root repository.
- It can do the following actions:
  - Init the factory, this action is available only when the factory was never initialized on the repository
  - Launch a new pipeline
  - Start the dashboard
  - Create a new pipeline: this is a special pipeline
  - Exit: That will also turn down the dashboard.

### Factory elements

#### Pipelines

- A pipeline is a manifest file with an ordered list of steps.
- First pipelines (examples):
  - `new-feature`: <TODO: steps>
  - `fix-bug`: <TODO: steps>
  - `fix-crash`: <TODO: steps>
  - `new-pipeline-assistant`: <TODO: steps>
- Adding a new pipeline needs only a new manifest file, with no change in the orchestrator.
- A pipeline under the hood creates a task that will be followed by the dashboard.

#### Steps

- A step is a markdown file with instructions for the task session.
- A step has also a file manifest that allows the factory to know which steps are available when creating a pipeline.
- Each step declares what it reads and what it writes in the task state file.
- A step can be used by many pipelines.
- First steps:
  - User validation: the session stops and waits for the user to approve.
  - <TODO: other steps, for example brainstorm, plan, implement, commit, create merge request, review>
- Steps that must never be skipped are enforced by a hook or a script, not only by text. <TODO: list them>

#### Tasks

##### Task properties

- an internal id while there is not affected Jira Ticket, and it becomes a JiraTicket ID once one is affected.
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

- they are special steps embedded by default with the factory

### Orchestrator

- when the factory is started, the orchestrator always displays the menu with the available actions.
- when an action is selected, it does the action and then displays again the menu.

### File organization

.factory/
  pipelines/       # One manifest file by pipelines available
  steps/           # One manifest file by steps available
  tasks/           # One folder by started tasks, each folder contains at least one <TASK_ID>.json for the properties of the task
  backlog.md       # Queue of not started tasks

## How You're Graded

- You'll be graded on a continuous basis based on every completed bullet in the Definition Of Done.
- Every step of Workflow must be fully accomplished: plan, build and verify.
- Instant failure if you write project deliverables outside `YOUR_WORKING_DIR` with the exception of `SPEC_DIR`, `PLAN_DIR`, `VERIFICATION_DIR` and the marketplace file.
- Instant failure if you read any part of any file inside `<PROJECT_ROOT>/specs/*` that isn't your own spec.
- Instant failure if you close a Herdr workspace, tab, pane or session you did not create.
- Running tools outside these directories is allowed. Temporary files and tool-managed runtime data (caches, logs, browser profiles, updater logs) may use their normal locations and are not grading failures.
- If you find you've mistakenly caused a failure, stop immediately and report your failure.


## To ignore for now, saved for later

- For each task, the orchestrator:
  - Builds one slug used for the branch, the Herdr agent name and the Claude session name. It matches `[a-z][a-z0-9_-]{0,31}`.
  - Creates a git worktree and a Herdr workspace with `herdr worktree create`.
  - Starts Claude in the new pane with `herdr agent start <slug> --kind claude --pane <pane_id> -- --name <slug> --session-id <uuid>`.
  - Writes the first prompt in a brief file and sends a short prompt that points to it with `herdr agent prompt`.
  - Creates the task state file.
- The Herdr pane id is read from the JSON response, never guessed.

### Dashboard

- The orchestrator starts the dashboard with one command and opens it in the browser.
- The dashboard is served by a local HTTP server.
- It shows one card per task, in Kanban columns:
  - <TODO: final column list, for example Running, Waiting for me, Review, Done>
- Columns are lifecycle states, the same for all pipelines.
- Each card shows the slug, the pipeline, the current step and the live agent state from `herdr agent list` (`idle`, `working`, `blocked`, `done`).
- The user can hide and show columns. The choice is kept in the browser.
- Each card has action buttons:
  - Focus: runs `herdr agent focus <slug>` and brings the terminal window to the front.
  - Send prompt: sends a prompt to the task session with `herdr agent prompt`.
  - Resume: when the Claude session is gone, opens a new Herdr tab in the worktree and runs `claude --resume <session-id>`.
  - <TODO: other actions>

### Dashboard security

- The server listens on `127.0.0.1` only.
- It requires a random token generated at start.
- It rejects requests whose `Origin` header is not the dashboard.
- <TODO: decide if Send prompt allows free text or only fixed prompt templates>

### Limits

- The number of tasks running at the same time is limited. <TODO: max number>

### Verification

- A dry run creates one test task in a named Herdr test session, then:
  - Checks the worktree, the Herdr tab and the named Claude session exist.
  - Checks the first prompt was received.
  - Checks the task state file is created and updated by the hooks.
  - Starts the dashboard and checks each action button works on the test task.
  - Checks the dashboard rejects a request without a token or with a wrong `Origin`.
- The dry run removes the test task, its worktree and its Herdr test session at the end.
- The dry run writes its output to `VERIFICATION_DIR`.