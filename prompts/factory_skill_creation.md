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
  - Create a new step: runs the built-in pipeline `new-step-assistant`
  - Exit: That will also turn down the dashboard.

### Factory elements

#### Pipelines

- A pipeline is a manifest file with an ordered list of steps.
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

- The `new-step-assistant` pipeline runs as a task in a new Herdr tab, without a worktree.
- It first asks where to save the step:
  - Generic: in `FACTORY_SOURCE/steps/`, reusable in any repository.
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

