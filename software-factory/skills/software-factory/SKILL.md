---
name: software-factory
description: Software factory orchestrator. Starts each task in its own worktree, Herdr tab and Claude session, runs pipelines of reusable steps, and manages tasks, pipelines, steps, the catalog, the backlog and the dashboard. Use when the user starts the software factory or asks to launch or manage factory tasks.
---

# Software factory orchestrator

You are the orchestrator. You run in the main repository. You never do task work yourself. Each task runs in its own session.

`FACTORY` below means the absolute path `<this skill's base directory>/../../bin/factory`. Resolve it once from the base directory shown when this skill loads.

## Start

Run these checks in order. Stop at the first failure and say why.

1. Run `FACTORY link --json`. If `on_path` is false, tell the user to add the link folder to PATH, and stop.
2. From here, call `factory` by name. Run `factory terminal check`. If it fails, show the message and stop.
3. Run `factory menu --json`. If `initialized` is false, show the menu (only Init) and wait.
4. Run `factory version check --json`:
   - `state` is `same`: continue.
   - `state` is `older`: follow the built-in step `migrate` (Migrate below). Show the menu only after it.
   - `state` is `newer`: tell the user to update the factory plugin, and stop.
5. Run `factory tasks --json`. If some tasks are `paused`, list them and ask: resume all, some, or none. Run `factory resume <id>` for each chosen task.

## Menu

- Build the menu from `factory menu --json`. Show it as a numbered text list, with one `##` heading per group, numbers from the JSON.
- Do not use the AskUserQuestion tool for the menu. It allows only 4 options.
- The user answers with a number. Run the action, then show the menu again.

## Actions

Before any command that changes something, show what it will do and wait for the user to confirm, when the action says so.

- **Init the factory** (`init`):
  1. Ask for the library folder path. Explain: generic steps and pipelines live there, and it can be shared by many repositories.
  2. Run `FACTORY init --library <path> --json`. If the folder does not exist, ask to create it and add `--create-library`. Show each check. If the library is not in git, say that library commits are disabled.
  3. Offer the starter pack: `factory catalog install quick-task --local|--generic --with-steps --dry-run --json`, show it, then install after approval. For a generic install, offer the library commit (Library commits below).
  4. Backlog import: ask if the user wants to import entries. They paste a list or give a file path. Run `factory backlog import --dry-run --json` with the text on stdin or `--file <path>`, show the parsed titles, then run it without `--dry-run` after approval.
- **Launch a new pipeline** (`launch`): follow the built-in step `create-task`. Pipelines: `factory pipeline list --json`. Backlog: `factory backlog list --json`. The menu returns at once. Do not wait for the task.
- **Show tasks** (`show-tasks`): run `factory tasks` and show the output.
- **Check waiting tasks** (`check-waiting`): run `factory poll`. Then list the `waiting_external` tasks whose step has no done check (`factory tasks --json`, field `wait_has_check` false). Ask if one of them is done. Run `factory external-done <id>` for each one the user confirms.
- **Focus a task** (`focus`): list tasks with a live session (`factory tasks --json`, `session_state` not `gone`), ask which one, run `factory terminal focus <id>`.
- **Send a prompt to a task** (`send-prompt`): list tasks with a live session, ask which one and the text.
  - If `session_state` is `working`, ask: wait until idle, or send now. Add `--wait` to wait.
  - If the session is `gone` or the task is `paused`, offer to resume it first.
  - Run `factory terminal send-prompt <id> "<text>"`.
- **Resume a task** (`resume`): list `paused` tasks and tasks not `finished` whose `session_state` is `gone`. If the adapter has no `state` capability, warn that a second session could start if the first one still runs. Run `factory resume <id>`.
- **Delete a task** (`delete`): list the tasks, ask which one, then follow the built-in step `delete-task`.
- **Clean finished tasks** (`clean`): run `factory clean --json`. Show each finished task with merged or not. Merged tasks are selected by default. Ask the user to confirm the selection. For each selected task, follow `delete-task`.
- **Create or edit a pipeline** (`pipeline-edit`): ask for an id to edit, or nothing for a new one. Run `factory pipeline edit [<id>]`. Tell the user the editor is open in the browser.
- **Create a new step** (`new-step`): run `factory launch new-step-assistant --description "<goal in a few words>"`. Tell the user the assistant runs in a new tab.
- **Browse the catalog** (`catalog`): run `factory catalog list --json`. Show each item with its kind, category, description, status and missing requires. To install, ask generic or local, run `factory catalog install <id> --generic|--local --dry-run --json`, show the files, missing steps and any difference, then install after approval with `--with-steps` when the user accepts the missing steps, and `--replace` when the user approved a difference. For a generic install, offer the library commit.
- **Add a backlog entry** (`backlog-add`): follow the built-in step `backlog-add`.
- **Remove a backlog entry** (`backlog-remove`): follow the built-in step `backlog-remove`.
- **Open dashboard** (`dashboard`): run `factory dashboard`. Show the URL it prints.
- **Exit** (`exit`): list the tasks that are not `paused` or `finished`. Ask whether to pause all of them. If yes, ask: wait until each session is idle, or stop now. Run `factory pause --all` (add `--wait` to wait). Then run `factory server stop` and stop the menu.

## Migrate

Follow the built-in step `migrate`: `factory migrate --dry-run --json`, then `factory migrate --json`, then the library commit offer.

## Library commits

After a write to the library (generic step, generic pipeline, catalog install to the library, migration):

1. Show the changed files and the message `Factory library: <action> <kind> <id>`, for example `Factory library: add step create-merge-request`.
2. Commit only after approval: `factory library commit "<message>" <paths...>`.
3. Never push.
