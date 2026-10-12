# Software Factory

## What it does

The Software Factory starts each task in its own git worktree, its own Herdr tab and its own named Claude session.
Each type of task is a pipeline. A pipeline is an ordered list of reusable steps.
One task is one run of a pipeline.
You start and manage tasks from one orchestrator session in the main repository.

## Concepts

- **Task**: one run of a pipeline. It has a worktree, a Herdr tab and a Claude session.
- **Pipeline**: a YAML file with an ordered list of steps.
- **Step**: a markdown file. The frontmatter is the manifest. The body holds the instructions.
- **Step types**: `prompt` (instructions for the session), `skill` (runs a Claude skill), `script` (runs a script with `factory run-script`), `composite` (a list of other steps).
- **Levels**: a local step or pipeline lives in `.factory/` of the repository. A generic one lives in the library folder. A built-in one ships with the plugin. Local wins over generic. Generic wins over built-in.
- **Catalog**: ready-made pipelines and steps. You install them by copy, into the local level or into the library.
- **Artifacts**: files a task writes for later steps or for you. `factory artifact path <name>` prints the path.

## Install and prerequisites

You need:

- `uv`. Install it with `brew install uv`.
- Herdr: https://herdr.dev
- git, with an `origin` remote in each repository.
- Claude Code.
- Optional: `gh` or `glab`, for the forge steps of the catalog.

Install the plugin. In Claude Code, run:

```
/plugin marketplace add <path to the SoftwareFactory folder>
/plugin install software-factory@software-factory
```

Start the orchestrator:

1. Open a Herdr pane in the main repository.
2. Start `claude`.
3. Run `/software-factory:software-factory`.

The first run creates the link `~/.local/bin/factory`. Make sure `~/.local/bin` is in your `PATH`.

### Bash allowlist

Task sessions use `.factory/claude-settings.json`, which allows every `factory` command.
For the orchestrator, add these commands to your Bash allowlist.

git:

- `git status`, `git diff`, `git log`, `git fetch`, `git switch`
- `git add`, `git commit`, `git push`, `git rebase`
- `git worktree`, `git branch`, `git rev-parse`

The factory CLI: `factory *`. This covers every command in the reference below.

Herdr adapter:

- `herdr worktree open`
- `herdr tab create`, `herdr tab close`
- `herdr workspace close`
- `herdr agent start`, `herdr agent prompt`, `herdr agent get`, `herdr agent read`
- `herdr agent focus`, `herdr agent wait`, `herdr agent send-keys`
- `herdr notification show`

## Tutorial

1. **Init the factory.**
   - Open the orchestrator in a repository. Choose "Init the factory".
   - Give the library folder path. Say yes to create it if it does not exist.
   - Say yes to the starter pack.
   - Expected: the folder `.factory/` exists in the repository. `factory pipeline list` shows `quick-task`.
2. **Run `quick-task` on a small change.**
   - Choose "Launch a new pipeline". Pick `quick-task`. Write a short description.
   - Read the dry run and confirm. If asked for `worktree_root`, give the folder where worktrees go.
   - Follow the task in the new Herdr workspace.
   - Choose "Show tasks". Expected: the task is `awaiting_approval` at `user-validation`.
   - Approve in the task session.
   - Expected: `git log -1` in the worktree shows the commit. The task is `finished`.
3. **Pause and resume.**
   - Choose "Exit" and answer yes to "pause all".
   - Start the orchestrator again. Answer "resume all".
   - Expected: the task session opens again with the same conversation and continues.
4. **Create a step.**
   - Choose "Create a new step". Answer the questions of the assistant.
   - Expected: the new step file is in `<library>/steps/` or in `.factory/steps/`.
5. **Create a pipeline.**
   - Choose "Create or edit a pipeline". Copy `quick-task`.
   - Add the new step. Save.
   - Launch the new pipeline.
   - Expected: the task runs the new step.
6. **Follow a task in the dashboard.**
   - Choose "Open dashboard". Open the URL it prints in your browser.
   - Launch `plan-and-build`, or the pipeline from step 5, with the "Launch" button.
   - Watch the card move from column to column as steps start.
   - When the card turns amber (`awaiting_approval`), click "Approve".
   - Expected: the task session receives "The user approved. Run `factory done`." The card moves on.

## Reference

### Menu actions

- **Launch a new pipeline**: start a task, from scratch or from a backlog entry.
- **Show tasks**: list the tasks with their status.
- **Check waiting tasks**: poll the waiting tasks. Mark a manual external event as done.
- **Focus a task**: switch the terminal to the task session.
- **Send a prompt to a task**: send text to a task session.
- **Resume a task**: restart a paused task, or a task whose session is gone.
- **Delete a task**: close its terminal, remove its worktree and archive its folder.
- **Clean finished tasks**: delete finished tasks whose work is merged.
- **Create or edit a pipeline**: open the pipeline editor in the browser.
- **Create a new step**: run the step assistant.
- **Browse the catalog**: list and install catalog pipelines and steps.
- **Add a backlog entry**: add an entry to the backlog.
- **Remove a backlog entry**: remove an entry from the backlog.
- **Open dashboard**: start the local server and print the dashboard URL.
- **Init the factory**: set up the repository. Shown only before init.
- **Exit**: ask to pause all tasks. Then stop the local server.

### Commands

Global option: `factory --version`.
Most commands take `--task <id>` and `--json`.
Inside a task worktree, the task is found from the folder.

Setup:

- `factory init --library <path> [--create-library]`: set up the factory in this repository.
- `factory link`: create or fix the `~/.local/bin/factory` link.
- `factory menu`: show the orchestrator menu.
- `factory terminal check`: check the terminal adapter.
- `factory version check`: compare the data version with the plugin.
- `factory migrate [--dry-run]`: migrate the repository data and the library to the current version.

Step execution, inside a task session:

- `factory next`: show the current step.
- `factory done`: finish the current step.
- `factory skip`: skip the current step, when it is not required.
- `factory run-script`: run the current `script` step.
- `factory goto <step_path> --reason <text>`: go back to an earlier step.
- `factory config get <step> <key>`: read a step config value.
- `factory config set <step> <key> <value>`: save a step config value.
- `factory state get <key>`: read a task state value.
- `factory state set <key> <value>`: save a task state value.
- `factory artifact path <name>`: print the path of an artifact.

Task life:

- `factory launch <pipeline> [--description <text>] [--input <name=value>] [--id <id>] [--from-backlog <id>] [--dry-run]`: start a task.
- `factory tasks`: list the tasks.
- `factory status`: show the status of the current task.
- `factory block <reason>`: block the task.
- `factory unblock`: unblock the task.
- `factory approve [--send]`: approve the result of a `user-validation` step.
- `factory request-changes <text> [--send]`: ask for changes.
- `factory approval check`: check that the result is approved.
- `factory wait`: set the task to waiting for an external event.
- `factory poll`: check the waiting tasks.
- `factory external-done <id>`: end a wait that has no done check.
- `factory pause [<id>] [--all] [--wait]`: pause a task or all tasks.
- `factory resume <id>`: resume a task.
- `factory delete <id> [--dry-run] [--confirm-unpushed]`: delete a task.
- `factory clean`: list finished tasks that can be deleted.
- `factory open-ide`: open the task worktree in the IDE.
- `factory terminal focus <id>`: focus the task session.
- `factory terminal send-prompt <id> <text> [--wait]`: send a prompt to a task session.

Backlog:

- `factory backlog list`: list the entries.
- `factory backlog add <title> [--summary <text>] [--pipeline <id>]`: add an entry.
- `factory backlog remove <id>`: remove an entry.
- `factory backlog move <id> --to <position>`: change the order.
- `factory backlog import [--file <path>] [--dry-run]`: import entries from text or a file.

Pipelines, steps and the library:

- `factory pipeline list`: list the pipelines.
- `factory pipeline check <id>`: check a pipeline.
- `factory pipeline edit [<id>]`: open the pipeline editor.
- `factory step list`: list the steps.
- `factory step show <id>`: show a step.
- `factory catalog list`: list the catalog items and their status.
- `factory catalog install <id> --generic|--local [--with-steps] [--replace] [--dry-run]`: install a catalog item.
- `factory library commit <message> <paths...>`: commit files of the library.

Local server:

- `factory serve`: run the local server in the foreground.
- `factory dashboard`: start the local server if needed and print the dashboard URL.
- `factory server stop`: stop the local server.

### Dashboard

Open it with the menu action "Open dashboard" or with `factory dashboard`.
The page refreshes every 5 seconds.
The header has two views: **Tasks** and **Backlog**.

#### Tasks view

The board has one column for each name in `columns` of `.factory/factory.yaml`, plus a `Done` column.
A finished task is always in `Done`.
Any other task is in the column of its current step.
If the column is unknown, the task goes in the first column.
The "Columns" buttons hide or show a column. The browser remembers your choice.

Each card shows:

- The ticket, then the task id. The ticket is a link when `ticket_url` is set.
- The description.
- The pipeline and the current step.
- The status, with an icon and the time in this status. The reason is shown below when there is one.
- A red "Session gone" tag when the terminal session is not there. Not shown for `paused` and `finished` tasks.
- The artifacts of the task. Click a name to read it.
- "To validate", when the step waits for your approval. It links to the artifact to read. If the step validates code, it has an "Open in IDE" button.

Colors and icons:

| Status | Color | Icon |
| --- | --- | --- |
| `active` | green | ▶ |
| `blocked` | red | ⛔ |
| `awaiting_approval` | amber | ✋ |
| `waiting_external` | blue | ⏳ |
| `paused` | grey | ⏸ |
| `finished` | light grey | ✓ |

Card buttons:

- **Focus**: switch the terminal to the task session. Shown when the session exists, the task is not finished and the terminal supports it.
- **Show MR**: open the merge request. Shown when the task has an MR link.
- **Approve** and **Request changes**: shown when the status is `awaiting_approval`. "Request changes" asks for a text.
- **Mark done**: shown when the status is `waiting_external` and the wait has no done check.
- **Send prompt**: send text to the session. If the session is working, choose "Wait until idle" or "Send now".
- **Pause**: shown when the session exists and the task is not paused. Choose "Wait until idle" or "Stop now". The card shows "Pausing..." until it ends.
- **Resume**: shown when the task is paused or its session is gone.
- A finished task has no Focus, Send prompt, Pause or Resume button.

"Send prompt", "Pause", "Resume", "Launch" and "Check" are disabled when the terminal check fails.

#### Launch form

The "Launch" button opens the form.

1. Pick the pipeline. Write the description. Fill the inputs of the pipeline.
2. Click "Check". It runs a dry run. The report shows the task id, the worktree, the branch and the base.
3. Fix what the report shows. Missing inputs are red. For a missing config value, type it and click "Save".
4. When the report says "Ready to launch.", click "Launch".

Any change in the form turns the check off. Check again before you launch.

#### Clean dialog

The "Clean" button of the `Done` column lists the finished tasks that can be deleted.

1. Tick the tasks. Click "Check selected".
2. For each task, the dialog shows uncommitted changes, unpushed commits and failed checks.
3. If something would be lost, tick "I accept losing these changes" for that task.
4. Click "Delete selected". A task you did not accept is skipped.

#### Backlog view

- **Add**: ask for a title, a summary and an optional pipeline.
- **Drag** a card to change its priority.
- **Start**: open the Launch form with the description, the pipeline and the entry filled in. The entry leaves the backlog when the task starts.
- **Delete**: remove the entry after a confirmation.

#### Banner

When `factory terminal check` fails, an orange banner shows the message at the top of the page.
The buttons that need the terminal are disabled.
Fix the problem (see Troubleshooting). The banner goes away at the next refresh.

#### Ticket links

Set `ticket_url` in `.factory/factory.yaml` to make tickets links.
Use `{key}` where the ticket goes. Example: `ticket_url: https://example.atlassian.net/browse/{key}`.
Only `http` and `https` URLs are used.

#### Security

- The server listens on `127.0.0.1` only. It uses a random port.
- Each start makes a new token. The URL holds it: `?token=...`. Every API call must send it.
- The server checks the `Host` header. It must be `127.0.0.1` and the server port.
- The server checks the `Origin` header. It must be the server itself.
- The server stops after 30 minutes without requests. `factory dashboard` starts it again.
- `factory server stop` stops it now. The menu action "Exit" stops it too.
- The file `.factory/server.json` holds the port and the token. Only you can read it.
- The log is `.factory/server.log`.

### Step manifest fields

`id`, `description`, `category`, `type`, `reads`, `writes`, `done_when`, `done_check`, `config`, `required`, `run_in`, `model`, `effort`, `requires`, `column`, `wait_external`, `steps`.

### Pipeline fields

- `id`, `description`
- `inputs`: values asked at launch.
- `steps`: a list of entries with `id`, `with`, `model`, `effort` and `column`.
- `claude`: `model` and `effort` of the task session.
- `start_column`: the board column of a new task.

### `.factory/factory.yaml` fields

`version`, `library`, `terminal`, `columns`, `poll_minutes`, `ticket_url`.

## Troubleshooting

- **Terminal check failed.** Start Claude inside a Herdr pane. The pane sets `HERDR_ENV=1`. If `herdr` is missing, install it.
- **Data version mismatch.**
  - Older data: start the orchestrator. It runs the migration.
  - Newer data: update the plugin.
- **Session gone.** Choose "Resume a task" in the menu, or run `factory resume <id>`.
- **Folder trust dialog.**
  - Worktrees of a repository you already trust in Claude show no trust dialog.
  - If the dialog appears, the repository is not trusted. The launch fails with a clear message.
  - Open Claude once in the main repository and trust it. Then launch again.
