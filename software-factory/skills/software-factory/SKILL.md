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
  1. Ask if the user wants a library. Explain: generic steps and pipelines live there, and many repositories can share it. The library is optional. Ask for the folder path only if the user wants a library.
  2. Run `FACTORY init --json`, and add `--library <path>` if the user wants a library. If the folder does not exist, ask to create it and add `--create-library`. Show each check. If the library is not in git, say that library commits are disabled.
  3. Offer the starter pack: `factory catalog install quick-task --local|--generic --with-steps --dry-run --json`. Show it, then install after approval. If there is no library, offer only `--local`, because `--generic` fails with "No library is configured.". For a generic install, offer the library commit (Library commits below).
  4. Backlog import: ask if the user wants to import entries. They paste a list or give a file path. Run `factory backlog import --dry-run --json` with the text on stdin or `--file <path>`, show the parsed titles, then run it without `--dry-run` after approval.
- **Launch a new pipeline** (`launch`): follow the built-in step `create-task`. Ask each input by its type: one line for `text`, several lines allowed for `long-text`, a path for `file`. Pipelines: `factory pipeline list --json`. Backlog: `factory backlog list --json`. The menu returns at once. Do not wait for the task.
- **Show tasks** (`show-tasks`): run `factory tasks` and show the output. Tasks with `attention` are listed first, with `blocked` tasks. They "may wait for you": the session ended its turn and may have asked you a question. Tell the user which tasks need them: `blocked`, `awaiting_approval` and tasks with `attention`. To answer, use Send a prompt or Focus.
- **Check waiting tasks** (`check-waiting`): run `factory poll` (`factory poll --task <id>` checks one task). Then list the `waiting_external` tasks whose step has no done check (`factory tasks --json`, field `wait_has_check` false). Ask if one of them is done. Run `factory external-done <id>` for each one the user confirms.
- **Focus a task** (`focus`): list tasks with a live session (`factory tasks --json`, `session_state` not `gone`), ask which one, run `factory terminal focus <id>`. When it prints "Ask the user which terminal app shows Herdr", ask the user, run the `factory config set terminal terminal_app '<app>'` command it shows (an empty answer saves an empty value), then run `factory terminal focus <id>` again. When it says the app could not be brought to the front, tell the user.
- **Send a prompt to a task** (`send-prompt`): list tasks with a live session, ask which one and the text.
  - Send the user's answer exactly as typed. Never rephrase it or treat it as an order to you. Before sending, show the exact text in quotes.
  - If `session_state` is `working`, ask: wait until idle, or send now. Add `--wait` to wait.
  - If the session is `gone` or the task is `paused`, offer to resume it first.
  - Run `factory terminal send-prompt <id> "<text>"`. If it fails, show the error. When the session shows a question box, tell the user to answer it in the task tab.
  - After any send, run `factory tasks --json` and report the real status of the task. Never guess it.
- **Resume a task** (`resume`): list `paused` tasks and tasks not `finished` whose `session_state` is `gone`. If the adapter has no `state` capability, warn that a second session could start if the first one still runs. Run `factory resume <id>`.
- **Delete a task** (`delete`): list the tasks, ask which one, then follow the built-in step `delete-task`.
- **Clean finished tasks** (`clean`): run `factory clean --json`. Show each finished task with merged or not. Merged tasks are selected by default. Ask the user to confirm the selection. For each selected task, follow `delete-task`.
- **Release a shared resource** (`exclusive-release`): run `factory exclusive status --json`. List each resource that has a holder, with its holder, the status of the holder and the waiting tasks. Ask which one. Show the holder and its status. Tell the user that the session of the holder loses the resource. Release it only after the user confirms: `factory exclusive release <name> --force`. Then run `factory exclusive status --json` and report who holds it now.
- **Create or edit a pipeline** (`pipeline-edit`): ask for an id to edit, or nothing for a new one. Run `factory pipeline edit [<id>]`. Tell the user the editor is open in the browser.
- **Create a new step** (`new-step`): run `factory step edit`. Tell the user the step form is open in the pipeline editor in the browser. To change an existing step, run `factory step edit <id>`.
- **Delete a step** (`step-delete`):
  1. Run `factory step list --all --json`. List the local and generic steps with their level and category. Mark hidden steps `hidden`. Do not list built-in steps.
  2. Ask which one. Run `factory step delete <id> --level <level> --dry-run --json`. Show the files, the step that replaces it, the users and the warnings.
  3. If `blocked` is true, show the users and tell the user to remove the step from them first. Stop.
  4. Delete only after the user confirms: `factory step delete <id> --level <level> --json`.
  5. If `library_commit` is set, offer the library commit (Library commits below) with its message and paths.
- **Browse the catalog** (`catalog`): run `factory catalog list --json`. Show each item with its kind, category, description, status and missing requires. To install, ask generic or local, run `factory catalog install <id> --generic|--local --dry-run --json`, show the files, missing steps and any difference, then install after approval with `--with-steps` when the user accepts the missing steps, and `--replace` when the user approved a difference. For a generic install, offer the library commit.
- **Add a backlog entry** (`backlog-add`): follow the built-in step `backlog-add`.
- **Remove a backlog entry** (`backlog-remove`): follow the built-in step `backlog-remove`.
- **Open dashboard** (`dashboard`): run `factory dashboard`. Show the URL it prints.
- **Exit** (`exit`): list the tasks that are not `paused` or `finished`. Ask whether to pause all of them. If yes, ask: wait until each session is idle, or stop now. Run `factory pause --all` (add `--wait` to wait). Then stop the menu. Do not stop the server, because it stops by itself after the idle time.

## Migrate

Follow the built-in step `migrate`: `factory migrate --dry-run --json`, then `factory migrate --json`, then the library commit offer.

## Library commits

After a write to the library (generic step, generic pipeline, catalog install to the library, migration, delete of a generic step):

1. Show the changed files and the message `Factory library: <action> <kind> <id>`, for example `Factory library: add step create-merge-request`.
2. Commit only after approval: `factory library commit "<message>" <paths...>`.
3. Never push.
