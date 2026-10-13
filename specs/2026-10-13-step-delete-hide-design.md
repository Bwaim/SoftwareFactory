# Software factory: delete and hide steps (design)

Date: 2026-10-13
Source: `prompts/factory_step_delete_hide.md` (requirements and Definition Of Done). Context: `prompts/factory_skill_creation.md`, sections "Step delete", "Step hide", "Pipeline editor", "Local server".
Target: the existing factory in `software-factory/`. Branch `step-delete-hide`, made from `master`.

## Goal

- Delete a local or generic step, with a dry run and safety checks.
- Hide a step id from the pipeline editor and from the step lists, while pipelines that use it keep working.

## Decisions

- D1. Two new modules. `lib/factory/step_delete.py` holds the delete logic. `lib/factory/hidden.py` holds the hidden list. The CLI, the server API and the orchestrator all call these functions. No logic in the server or the pages.
- D2. `Registry` keeps every level of a step id, not only the one in use (see Registry).
- D3. `hidden_steps` lives in `.factory/factory.yaml`. `.factory/` is already in the git local exclude list, so it is never committed. The key is optional. The data format version does not change.
- D4. The library commit rule F1 stays: every library commit also takes the library `factory.yaml` when it is new or changed.
- D5. The delete commit offer lists only removed files that git tracks. When none is tracked, there is no offer.
- D6. Accepted risk: deleting a local override changes running tasks too. A task loads its steps by id, so from its next step start it uses the step of the next level. Users are checked only when no other level replaces the step.

## Registry

- `Registry.load` reads the levels in order built-in, generic, local. Today a later level replaces an earlier one in `steps`.
- New field `variants`: a dict from step id to the list of `Step` objects for this id, one per level, in level order. `steps[sid]` stays the one in use (the last of `variants[sid]`).
- New helper `all_pipeline_files(ctx)`: every pipeline file at every level, including the ones another level overrides, as `(level, pipeline id, data)`.

## Hide a step

Module `hidden.py`:

- `ids(ctx)`: the list `hidden_steps` from `.factory/factory.yaml`, or `[]` when the key is missing.
- `hide(ctx, sid)`: refuses an id that no level has (`The step \`<id>\` does not exist.`). If the id is already hidden, it changes nothing and returns `Step <id> is already hidden.`. Else it adds the id and returns `Step <id> is hidden.`.
- `unhide(ctx, sid)`: accepts any id in `hidden_steps`, even when no level has it anymore, so a stale id can be removed. If the id is not hidden, it changes nothing and returns `Step <id> is not hidden.`. Else it removes it and returns `Step <id> is visible again.`.
- `discard(ctx, sid)`: removes the id without a message. Used by delete.
- Writes use `fsio.update_yaml` with its lock file.

Where a hidden step is not shown:

- `factory step list`, unless `--all`. With `--all`, every row has `hidden: true|false`, and the text output adds `hidden` to hidden rows. The JSON rows always have the `hidden` field.
- The available steps of the pipeline editor, by default.
- The step lists that the step assistant shows to choose the steps of a composite step: `new-step.md` uses `factory step list` for that.

Where a hidden step still works:

- Launch, `factory next`, `factory done` and every other runtime command ignore `hidden_steps`.
- `factory step show <id>`: the text output prints `hidden` after the path. The JSON has `hidden: true`.
- The step assistant uses `factory step list --all` when it checks for a similar step or a duplicate id.

Pipeline check:

- New warning, one per hidden step used by the pipeline entries: ``A hidden step is used: `<id>`.`` The CLI prints `WARNING: A hidden step is used: ...`. It never blocks a save.
- `pipeline_check.check` gets the hidden ids as a new argument. Its callers pass `hidden.ids(ctx)`.

## Delete a step

Module `step_delete.py`.

`plan(ctx, sid, level=None)` returns a dict and changes nothing:

- Target:
  - `level` given (`local` or `generic`): the step at this level. If this level has no step with this id: `There is no <level> step \`<id>\`.`.
  - `level` missing: the step in use.
  - An unknown id: `The step \`<id>\` does not exist.`.
  - The target is built-in, or the id exists only as built-in: `Built-in steps cannot be deleted. Hide the step instead: \`factory step hide <id>\`.`.
- `files`: the step `.md` file. For a `script` step, also the script named on the first line of its body, when the script resolves to a file in the same `steps/` folder and no other step file in that folder names the same script.
- `replaced_by`: the level that is used after the delete, when another level has this id:
  - Target is the step in use: the previous level in `variants` (generic, then built-in).
  - Target is not in use (a local step overrides it): the step in use stays. The plan says `in_use_stays: <level>`.
  - No other level: `null`.
- `users`: only when `replaced_by` is null and nothing stays in use. Each user is a dict `{kind, id, level}`:
  - `pipeline`: every pipeline file at every level whose entries list the id.
  - `composite`: every composite step file at every level, other than the target file, whose `steps` list the id.
  - `task`: every task whose status is not `finished` and whose saved step list has the id in any step path.
- `warnings`: for a generic target, `Other repositories that use this library are not checked.`
- `blocked`: true when `users` is not empty.

`delete(ctx, sid, level=None)`:

- Runs `plan` again. If `blocked`: refuses with `Step <id> is still used. Remove it from these first:` and one line per user, for example `- pipeline quick-task (generic)`, `- composite step build (local)`, `- task fix-login`.
- Before the delete, for a generic target in a git library: notes which of the files git tracks.
- Removes the files.
- Calls `hidden.discard(ctx, sid)` unless another level still has the id.
- Keeps the step section in `.factory/config.yaml`.
- Returns the plan plus `removed` (the files) and `library_commit`:
  - Generic target, library in git, at least one removed file was tracked: `{"message": "Factory library: delete step <id>", "paths": [tracked removed files]}`.
  - Else `null`.
- The catalog needs no change. Its status reads the files, so a deleted catalog step shows as not installed, or as installed at the other level if that level still has it.

## CLI

- `factory step delete <id> [--level local|generic] [--dry-run] [--json]`. The text output lists the files, the replacing level, the users and the warnings. After a delete with an offer, it prints the message and the paths and tells the user to run `factory library commit "<message>" <paths...>`.
- `factory step hide <id>` and `factory step unhide <id>`. They print the message from `hidden.py`.
- `factory step list [--all]` and `factory step show <id>` as described in Hide a step.
- None of these use Claude.

## Server API

All routes keep the token, Host and Origin checks.

- `GET /api/steps`: every step, each with `hidden`. The editor filters.
- `GET /api/steps/<id>`: adds `hidden`.
- `POST /api/steps/<id>/delete/dry-run`, body `{"level": "local"|"generic"|null}`: returns `step_delete.plan`.
- `POST /api/steps/<id>/delete`, same body: returns `step_delete.delete`. A blocked delete is a 400 with the error text.
- `POST /api/steps/<id>/hide` and `POST /api/steps/<id>/unhide`: return `{"message": ...}`.
- `POST /api/pipelines/check` passes the hidden ids to the check.

## Pipeline editor

- Each available step has a "Hide" button.
- A "Show hidden steps" toggle shows the hidden steps in the list, greyed, each with an "Unhide" button instead of "Hide". The toggle is saved in `localStorage` (wrapped in try/catch).
- A pipeline row whose step is hidden shows a `hidden` mark.
- The detail panel of a local or generic step has a "Delete" button. This includes a hidden step shown with the toggle. Built-in steps have no "Delete".
  - "Delete" calls the dry-run route and shows the files, the replacing level, the users and the warnings in the panel.
  - When the plan is blocked, it shows the users and no Confirm button.
  - Else it shows a "Confirm delete" button. No browser dialog.
  - After the delete, it reloads the step list and closes the panel.
  - When the result has `library_commit`, it shows the existing "Commit to library" box.
- The editor never blocks a save for hidden steps.

## Orchestrator

- Menu action `step-delete`, label "Delete a step", group "Pipelines and steps", after "Create a new step".
- SKILL.md flow:
  1. Run `factory step list --all --json`. List the local and generic steps with their level, their category and `hidden` when hidden. Built-in steps are not listed.
  2. The user selects one. Run `factory step delete <id> --level <level> --dry-run --json` and show it.
  3. When it is blocked, show the users and stop.
  4. Delete only after the user confirms: `factory step delete <id> --level <level> --json`.
  5. For a generic step with `library_commit`, offer the library commit (Library commits section).

## README

- The menu action "Delete a step".
- The commands `factory step delete`, `factory step hide`, `factory step unhide`, `factory step list [--all]`.
- The pipeline editor parts: Hide, Unhide, Show hidden steps, the `hidden` mark, Delete in the detail panel, the hidden step warning.
- The tutorial stays unchanged. Simple English, short sentences.

## Errors

- Every refusal is a `FactoryError` with the text above. The CLI prints it and exits 1. The API returns 400 with `{"error": ...}`.
- A missing script file of a `script` step does not block the delete. Only the `.md` file is listed then.
- A file that disappears between the plan and the delete is skipped.

## Testing

Same setup as the existing tests: a test repository with a bare origin, a test library in its own git repository, the fake adapter. Never a real library or a real `.factory/`.

Milestone 1, Delete (`tests/test_step_delete.py`):

- Delete a local step: its file is removed.
- Delete a local override: the generic step is used again, and the dry run says `replaced_by: generic`.
- Delete a generic step: its file is removed and the commit offer has the message `Factory library: delete step <id>`. Committing it with `factory library commit` commits only the removed file (the library `factory.yaml` is committed before). Another staged file stays staged and is not committed.
- Delete a generic step that git does not track: no commit offer.
- Delete a `script` step: its script is removed. When another step names the same script, the script stays.
- A built-in step: refused with the exact error that says to hide it.
- Refused when a pipeline, a composite step or an unfinished task uses the step and no level replaces it. The error lists each user. A finished task does not block.
- `--dry-run` changes nothing (the file tree and `factory.yaml` are the same before and after).
- The deleted id leaves `hidden_steps`, unless another level still has it.
- A deleted catalog step shows as not installed.
- `--level generic` while a local override exists: the local step stays in use.
- API: dry run and delete routes return the same results as the functions. A request without the token is rejected.
- Menu: `step-delete` is after `new-step`.

Milestone 2, Hide (`tests/test_step_hide.py`):

- `hide` and `unhide` change `hidden_steps`. Repeated calls say so and change nothing. `hide` refuses an unknown id. `unhide` removes a stale id that no level has.
- Hide works on a built-in step.
- `factory step list` leaves hidden steps out. `--all` shows them marked. `factory step show` shows a hidden step, marked.
- A pipeline that uses a hidden step launches and runs to the end with the fake adapter.
- `factory pipeline check` warns ``A hidden step is used: `<id>`.`` and returns 0.
- Data without `hidden_steps` works and `factory version check` still reports the same data version.
- API: hide, unhide, steps list with `hidden`, check with the warning. A request without the token is rejected.

Both milestones:

- The full suite passes after each milestone.
- `tests/test_docs.py` keeps checking that every `factory` command in the README exists in the CLI.
- Report: `verification/software-factory/step-delete-hide-report.md`, one section per milestone with its tests and results, and the full suite result.
- Manual browser check list: `verification/software-factory/step-delete-hide-manual-check.md`, covering Delete (local, generic, absent on built-in, on a hidden step), Hide, Unhide, the toggle and its saved choice, the `hidden` mark, and the orchestrator "Delete a step" action.
