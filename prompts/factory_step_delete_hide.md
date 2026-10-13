# Software factory: delete and hide steps

## Problem

The software factory can create steps, but it cannot delete them. The user must find the step file and remove it by hand, with no check that a pipeline, a composite step or a running task still uses it.
The pipeline editor shows every step of every level. Steps the user never wants in a new pipeline, for example built-in steps or old steps, make the list long and hard to read.

## Solution

Add two features to the existing software factory:
- Delete a step, with a dry run and safety checks.
- Hide a step, so it is not shown in the pipeline editor, while pipelines that use it keep working.

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
    - The full factory requirements. Read it for context. It already contains these two features.

## Workflow

1. Read. Read `MAIN_PROMPT`, `YOUR_WORKING_DIR/README.md` and the factory code, so the new features follow the existing design, modules and tests.
2. Brainstorm. Use the `/superpowers:brainstorming` skill to create a specification file from these requirements. Save the specification file in `SPEC_DIR/` before writing the plan.
3. Ask validation. Ask the user to validate the specification file.
4. Plan. After specification validation, use the `/superpowers:writing-plans` skill to create an implementation plan from the specification file. Save the plan file in `PLAN_DIR/` before writing implementation code. Split the plan into these milestones, in this order:
    1. Delete a step: CLI, menu action, server API, editor button, library commit, README.
    2. Hide a step: CLI, server API, editor list and buttons, pipeline check warning, README.
5. Ask validation. Ask the user to validate the plan file.
6. Build. After plan validation, create the branch `step-delete-hide` from `master`. Use the `/superpowers:subagent-driven-development` skill to implement the plan inside `YOUR_WORKING_DIR`, one milestone at a time. Run the full test suite of the factory after each milestone, fix the failures, and commit before starting the next milestone. Do not skip straight from this prompt to implementation.
7. Verify. Check every item in Definition Of Done, fix failures, and rerun the affected checks. Keep final verification artifacts inside `VERIFICATION_DIR` and report actual results and any remaining blockers.

## Definition Of Done

### Workflow Complete

- Your completed implementation plan exists under `PLAN_DIR/`
    - It was written before implementation, and the build followed its build step.
- The work is on the branch `step-delete-hide`. `master` is unchanged.
- Every existing test still passes.

### Delete a step

- A step is deleted with `factory step delete <id> [--level local|generic] [--dry-run]`. It does not use Claude.
- Without `--level`, it deletes the step at the level that is used now: local first, then generic.
- Built-in steps cannot be deleted. The error says: "Built-in steps cannot be deleted. Hide the step instead: `factory step hide <id>`."
- `factory step delete --dry-run` prints what would happen, and changes nothing:
  - The files it removes: the step `.md` file and, for a `script` step, the script file named in its body, when that file is in the same `steps/` folder and no other step names it.
  - The step that replaces it, when another level has a step with the same id. Example: deleting a local override makes the generic step used again.
  - The users of the step, when no other level has the same id:
    - Pipelines, at every level, that list the step
    - Composite steps that include the step
    - Tasks that are not finished and whose saved step list contains the step
  - For a generic step, a warning: "Other repositories that use this library are not checked."
- The delete is refused while the step has users and no other level replaces it. The error lists the users. The user removes the step from them first.
- When the delete runs:
  - It removes the files listed by the dry run.
  - It removes the id from `hidden_steps` (see Hide a step), unless another level still has a step with this id.
  - It keeps the step section in `.factory/config.yaml`, so the values come back if the step is installed again.
  - A catalog step that is deleted shows as not installed in the catalog.
- For a generic step, it offers the library commit, with the message `Factory library: delete step <id>`. The commit contains the removed files and nothing else.
- The orchestrator menu has a new action "Delete a step", in the group "Pipelines and steps", after "Create a new step":
  - It lists the local and generic steps, with their level and category.
  - The user selects one. The orchestrator shows the dry run, and deletes only after the user confirms.
  - For a generic step, it then offers the library commit.
- The pipeline editor detail panel has a "Delete" button for local and generic steps:
  - It shows the dry run in the page, and deletes only after the user confirms.
  - After the delete, it reloads the step list.
  - For a generic step, it offers the library commit, like after a save.
- The server has one API route for the dry run and one for the delete. Both call the same function as the CLI.

### Hide a step

- The hidden steps are a list of step ids in `.factory/factory.yaml`, key `hidden_steps`. The choice is per repository and is never committed.
- `hidden_steps` is optional. A missing key means no hidden step. Data without it stays valid, so the data format version does not change.
- `factory step hide <id>` adds the id. `factory step unhide <id>` removes it. Hiding an id that no level has is refused. Hiding a hidden step or unhiding a visible step does nothing and says so.
- Hiding works on any level: local, generic and built-in. It applies to the id, so it covers every level that has this id.
- A hidden step is not shown in:
  - The available steps of the pipeline editor, by default
  - `factory step list`, unless `--all` is given. With `--all`, hidden steps are marked `hidden`.
  - The step lists that the step assistant shows to choose the steps of a composite step
- A hidden step still works everywhere else:
  - Pipelines that use it launch and run as before.
  - `factory step show <id>` shows it, marked `hidden`.
  - The step assistant still sees it when it checks for a similar step or a duplicate id.
- "Hide" is the only way to deactivate a step. A hidden step is never blocked from running.
- Pipeline editor:
  - Each available step has a "Hide" button.
  - A "Show hidden steps" toggle shows the hidden steps in the list, greyed, each with an "Unhide" button. The toggle is saved in the browser.
  - A hidden step that a pipeline already uses is shown in the pipeline with a `hidden` mark.
- Pipeline checks have a new warning: "Warning: a hidden step is used." It does not block a save.
- The server has API routes to hide and unhide a step. They call the same functions as the CLI.

### Documentation

- The README menu actions, commands and pipeline editor parts describe the two features.
- The README tutorial is unchanged.
- The README uses simple English and short sentences.

### Verification

- The build is verified with an automated test run. Its report goes to `VERIFICATION_DIR/step-delete-hide-report.md`.
- The report has one section per milestone, with the tests run and their results, and the result of the full test suite.
- Test setup: the same as the existing factory tests. A test repository, a test library in its own test git repository, never a real library or a real `.factory/`.
- CLI tests, without Herdr or Claude:
  - Deleting a local step removes its file. Deleting a local override makes the generic step used again, and the dry run says so.
  - Deleting a generic step removes its file and offers the library commit. The commit contains only the removed files. Another staged file in the test library repository stays staged and is not committed.
  - Deleting a `script` step also removes its script file, unless another step names it.
  - A built-in step cannot be deleted, and the error says to hide it.
  - The delete is refused when a pipeline, a composite step or an unfinished task uses the step and no other level replaces it. The error lists each user.
  - `--dry-run` changes nothing.
  - A deleted step is removed from `hidden_steps`, unless another level still has it.
  - A deleted catalog step shows as not installed.
  - `factory step hide` and `factory step unhide` change `hidden_steps`. An unknown id is refused.
  - `factory step list` hides hidden steps, and shows them marked with `--all`. `factory step show` shows a hidden step.
  - A pipeline that uses a hidden step launches and runs to the end with the fake adapter.
  - `factory pipeline check` warns about a hidden step.
  - Data without `hidden_steps` works, and the data version is unchanged.
  - The editor server API, tested without a browser: the delete dry run, the delete, hide and unhide routes call the same functions as the CLI. Requests without the token are rejected.
  - Every `factory` command written in the README exists in the CLI.
- Manual browser check list in `VERIFICATION_DIR/step-delete-hide-manual-check.md`, for the user to run:
  - The "Delete" button, its dry run and its confirmation, for a local and a generic step, and its absence on a built-in step.
  - The "Hide" and "Unhide" buttons, the "Show hidden steps" toggle and its saved choice, and the `hidden` mark on a pipeline step.
  - The orchestrator "Delete a step" action.

## How You're Graded

- You'll be graded on a continuous basis based on every completed bullet in the Definition Of Done.
- Every step of Workflow must be fully accomplished: plan, build and verify.
- Instant failure if you write project deliverables outside `YOUR_WORKING_DIR` with the exception of `SPEC_DIR`, `PLAN_DIR` and `VERIFICATION_DIR`.
- Instant failure if you read any part of any file inside `<PROJECT_ROOT>/specs/*` that isn't your own spec.
- Instant failure if you change a real library or a real `.factory/` folder. Tests use test repositories only.
- Instant failure if you close a Herdr workspace, tab, pane or session you did not create.
- Running tools outside these directories is allowed. Temporary files and tool-managed runtime data (caches, logs, browser profiles, updater logs) may use their normal locations and are not grading failures.
- If you find you've mistakenly caused a failure, stop immediately and report your failure.
