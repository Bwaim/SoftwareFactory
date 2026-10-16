# Software Factory

## What it does

The Software Factory starts each task in its own git worktree, its own Herdr tab and its own named Claude session.
Each type of task is a pipeline. A pipeline is an ordered list of reusable steps.
One task is one run of a pipeline.
You start and manage tasks from one orchestrator session in the main repository.

## Concepts

- **Task**: one run of a pipeline. It has a worktree, a Herdr tab and a Claude session.
- **Display name**: the ticket key of a task, when the ticket is known only after the launch. Without it, the display name is the id.
- **Pipeline**: a YAML file with an ordered list of steps.
- **Step**: a markdown file. The frontmatter is the manifest. The body holds the instructions.
- **Task keys**: values a task holds. A step uses them and sets them. A key name uses lowercase letters, digits and `_`, and starts with a letter.
- **Key types**: `text` (one line), `long-text` (several lines), `file` (an absolute path). A missing type means `text`.
- **Key sources**: a pipeline input, an output of an earlier step, or the factory. The factory keys are `task_id`, `description` and `summary`. `summary` is set only when the task starts from a backlog entry.
- **Step types**: `ai` (a prompt sent to the agent), `command` (a shell command), `group` (a list of other steps).
- **Placeholders**: in an `ai` prompt, `{{<key>}}` is replaced with a task key and `{{config.<key>}}` with a config value. A key that is not set becomes `(not set)`.
- **Outputs**: the keys a step sets, each with a type and a description. `optional: true` means the step may leave it unset.
- **Command variables**: a `command` step gets each key as `FACTORY_KEY_<KEY>`, each config value as `FACTORY_CONFIG_<KEY>`, and the folder of the step file as `FACTORY_STEP_DIR`.
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

To write pipelines and steps with an agent, call `/factory-authoring` in any Claude session. See "Authoring skill" in the reference.

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
- `herdr workspace rename`, `herdr tab rename`, `herdr agent rename`
- `open -a <terminal app>`
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
   - Choose "Create a new step". The pipeline editor opens on the step form.
   - Write the id, the description and the prompt. Click a key on the right to insert it.
   - Click "Preview". Choose local or generic. Click "Save".
   - Expected: the new step file is in `.factory/steps/` or in `<library>/steps/`.
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
- **Focus a task**: switch the terminal to the task session. Then it brings the terminal app that shows Herdr to the front, with `open -a <terminal_app>` on macOS.
- **Send a prompt to a task**: send text to a task session.
- **Resume a task**: restart a paused task, or a task whose session is gone.
- **Delete a task**: close its terminal, remove its worktree and archive its folder.
- **Clean finished tasks**: delete finished tasks whose work is merged. A squash-merged branch counts as merged.
- **Create or edit a pipeline**: open the pipeline editor in the browser.
- **Create a new step**: open the step form in the pipeline editor.
- **Delete a step**: delete a local or generic step. It first shows what the delete does, then asks you to confirm.
- **Browse the catalog**: list and install catalog pipelines and steps.
- **Add a backlog entry**: add an entry to the backlog.
- **Remove a backlog entry**: remove an entry from the backlog.
- **Open dashboard**: start the local server and print the dashboard URL.
- **Init the factory**: set up the repository. Shown only before init.
- **Exit**: ask to pause all tasks. Then stop the local server, unless a task waits on a done check.

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
- `factory run-command`: run the command of the current `command` step. It prints the output and the exit code, then names each output that is not optional and still not set. The session never sets these outputs itself.
- `factory goto <step_path> --reason <text>`: go back to an earlier step.
- `factory config get <step> <key>`: read a step config value.
- `factory config set <step> <key> <value>`: save a step config value.
- `factory state get <key>`: read a task state value.
- `factory state set <key> <value>`: save a task state value. The first time `ticket` gets a Jira key after the launch, the task gets a display name. The Herdr agent, tab and workspace are renamed. The Claude session is renamed with `/rename` when it is idle with no question box, or at the next resume with `--name`. The id and the worktree folder do not change. A failed rename only prints a warning.
- `factory artifact path <name>`: print the path of an artifact.

Task life:

- `factory launch <pipeline> [--description <text>] [--input <name=value>] [--id <id>] [--from-backlog <id>] [--dry-run]`: start a task. When the pipeline input `ticket` holds a Jira key (`HT-4549`, a URL or a text), the task id is that key in lowercase, for example `ht-4549`, plus `-2` when taken.
- `factory tasks`: list the tasks.
- `factory status`: show the status of the current task.
- `factory block <reason>`: block the task.
- `factory unblock`: unblock the task.
- `factory approve [--send]`: approve the result of a `user-validation` step.
- `factory request-changes <text> [--send]`: ask for changes.
- `factory approval check`: check that the result is approved.
- `factory wait`: set the task to waiting for an external event.
- `factory poll [--task <id>]`: run the done check of every waiting task, or of one task. Only one check of a task runs at a time, across processes (lock file `.factory/tasks/<id>/check.lock`). A second check returns "A check is already running." After each check, the task saves `last_check`: the time, whether the wait ended, and the end of the output.
- `factory external-done <id>`: end a wait that has no done check.
- `factory pause [<id>] [--all] [--wait]`: pause a task or all tasks.
- `factory resume <id>`: resume a task.
- `factory delete <id> [--dry-run] [--confirm-unpushed]`: delete a task.
- `factory clean`: list finished tasks that can be deleted.
- `factory open-ide`: open the task worktree in the IDE.
- `factory terminal focus <id>`: focus the task session. Then it runs `open -a <terminal_app>`. `terminal_app` is asked on first use: `factory config set terminal terminal_app Ghostty`. An empty value means only the focus inside Herdr.
- `factory terminal send-prompt <id> <text> [--wait]`: send a prompt to a task session.
- `factory terminal start-session <name> <cwd> <prompt> -- <claude args>`: start a Claude session in the terminal. Prints the session handle as JSON. Herdr accepts names that match `^[a-z][a-z0-9_-]{0,31}$`, so the adapter turns any name into a valid one: lowercase, other characters become `-`, the prefix `t-` when it does not start with a letter, and a name longer than 32 characters ends with `-` and 4 characters of a hash. The `agent` field of the handle is the real Herdr name. Later calls use the handle.
- `factory terminal close <handle-json>`: close a session.
- `factory terminal state <handle-json>`: print the session state.
- `factory terminal wait-idle <handle-json> [--timeout <seconds>]`: wait until the session is idle.
- `factory terminal notify <text>`: show a notification.

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
- `factory pipeline keys <id> [--at <position>]`: list the task keys available before the step at this position, with their type, their source and "always set" or "maybe set".
- `factory step edit [<id>]`: open the step form in the pipeline editor.
- `factory step list [--all]`: list the steps. Hidden steps are left out. `--all` lists them too, marked `hidden`.
- `factory step hide <id>`: hide a step from the pipeline editor and from `factory step list`. Pipelines that use it still run it.
- `factory step unhide <id>`: show a hidden step again.
- `factory step show <id>`: show a step.
- `factory step delete <id> [--level local|generic] [--dry-run]`: delete a step. `--dry-run` only shows the files it removes, the step that replaces it and the users that block it. Built-in steps cannot be deleted.
- `factory catalog list`: list the catalog items and their status.
- `factory catalog install <id> --generic|--local [--with-steps] [--replace] [--dry-run]`: install a catalog item.
- `factory library commit <message> <paths...>`: commit files of the library.

Local server:

- `factory serve`: run the local server in the foreground.
- `factory dashboard`: start the local server if needed and print the dashboard URL.
- `factory server stop`: stop the local server.
- `factory server stop --unless-waiting`: stop the local server only when no task waits on a done check.

### Pipeline editor

`factory pipeline edit [<id>]` opens the editor in the browser.

- Left: the available steps. Filter them by category or by text. "Reload steps" reads the step files again.
- Middle: the pipeline. Drag steps into it and reorder them. The checks run while you edit. You can save with warnings, never with errors.
- Right: the step detail. Click a step to see its manifest, its level, its file and its body.
- Keys: click a step in the pipeline to see the keys available at its position.
- Loop: "Edit" on a pipeline step shows the loop fields. Pick `back_to` from this step and the earlier steps, `while` from the keys available after the step, and `max`. A step with a loop shows a mark, for example "↺ write-spec ×2".
- Step form: "New step" above the available steps opens it. The start screen of the editor has a "New step" button too. In the step detail, "Edit" changes a local or generic step, "Copy to local" copies a generic or built-in step to a local step with the same id, and "Duplicate" copies any step under a new id.
  - The form shows the fields of the manifest, a table for config keys, a table for outputs, and the prompt or the command. A `group` step shows a list of child steps. Drag them to change the order.
  - Next to the body, click a key to insert `{{<key>}}` in a prompt or `$FACTORY_KEY_<KEY>` in a command.
  - "Preview" shows the text `factory next` prints, with each placeholder shown as `<key>`.
  - Saving a step that exists first shows the pipelines and the unfinished tasks that use it. A task uses the change from its next step.
  - Errors block the save. Warnings do not. For a generic step, the editor offers the library commit.
  - Built-in steps cannot be edited. Copy them to local instead.
  - The form never writes a script file. Put a script next to the step by hand.
- Delete: the detail of a local or generic step has a "Delete" button.
  - It first shows what the delete does: the files it removes, the step that replaces it, and the pipelines, group steps and tasks that still use it.
  - A step that is still used cannot be deleted. Remove it from its users first.
  - "Confirm delete" removes the files. The list of steps reloads.
  - For a generic step, the editor offers the library commit.
  - The editor and the menu delete the step that is used now. To delete a generic step that a local step overrides, run `factory step delete <id> --level generic`.
  - Built-in steps cannot be deleted. Hide them instead.
- Hide: each available step has a "Hide" button. A hidden step is not in the list. Pipelines that use it still run it. The choice is saved in `.factory/factory.yaml` and is never committed.
  - "Show hidden steps" shows the hidden steps, greyed, each with an "Unhide" button. The browser remembers this choice.
  - A hidden step in the pipeline has a `hidden` mark. The checks warn: "A hidden step is used". It does not block the save.

### Authoring skill

The `factory-authoring` skill writes step and pipeline files for you, in any Claude session.
You do not need the orchestrator, the local server or the browser.

What it does:

- It reads your request, or a prompt file that describes a pipeline.
- It reuses the existing steps. It writes the new step files, then the pipeline files.
- It runs `factory pipeline check` and `factory pipeline keys`. It fixes the files until the check has no error.
- It writes local files, unless you ask for generic files. For generic files, it offers the library commit.
- It needs the factory in the repository: `.factory/factory.yaml` must exist.

How to call it:

- Ask Claude in your own words, for example "Create a factory pipeline that fixes a crash". Claude loads the skill.
- Or call it: `/factory-authoring <file or request>`. The full name is `/software-factory:factory-authoring`.

Example. The file `prompts/crash-pipeline.md`:

```markdown
# Crash fix pipeline

- Input: `crash_log`, the path of a crash log file.
- Step 1, a command: copy the last 200 lines of the log into an artifact.
- Step 2, the agent: read that artifact, find the cause of the crash and fix it.
- Step 3: the user validates the change.
```

The request: "Implement `prompts/crash-pipeline.md`".

Then review the pipeline in the browser with `factory pipeline edit <id>`.

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

- The ticket, then the display name, then the id when it differs. A failed rename is shown in red. The ticket is a link when `ticket_url` is set.
- The description.
- The pipeline and the current step.
- The status, with an icon and the time in this status. The reason is shown below when there is one.
- A red "Session gone" tag when the terminal session is not there. Not shown for `paused` and `finished` tasks.
- The artifacts of the task. Click a name to read it. The viewer closes with Escape, a click outside it, or its Close button. Its title bar stays visible, and the text scrolls inside it. A form, for example "Request changes", never closes on a click outside. Escape on a form with typed text asks "Discard the typed text?".
- For a task that is `waiting_external` on a step with a `done_check`: "Next check in m:ss", counted down in the page, and the last check with its time and result.
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

- **Focus**: switch the terminal to the task session. Shown when the session exists, the task is not finished and the terminal supports it. Then it brings the terminal app to the front. The first time, it asks for the app name. When it fails, the card says so.
- **Show MR**: open the merge request. Shown when the task has an MR link.
- **Approve** and **Request changes**: shown when the status is `awaiting_approval`. "Request changes" asks for a text.
- **Mark done**: shown when the status is `waiting_external` and the wait has no done check.
- **Check now**: shown when the status is `waiting_external` and the wait has a done check. It runs `factory poll --task <id>` as a background job. The button shows "Checking…" until the result.
- **Send prompt**: send text to the session. If the session is working, choose "Wait until idle" or "Send now".
- **Pause**: shown when the session exists and the task is not paused. Choose "Wait until idle" or "Stop now". The card shows "Pausing..." until it ends.
- **Resume**: shown when the task is paused or its session is gone.
- A finished task has no Focus, Send prompt, Pause or Resume button.

"Send prompt", "Pause", "Resume", "Launch", "Check" and the backlog "Start" are disabled when the terminal check fails.

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

A branch merged with a squash merge counts as merged when its content is already in `origin/<base_ref>`: `git merge-tree --write-tree` gives the tree of `origin/<base_ref>`. Its commits are not listed as lost, the reason is "merged (squash)", and the delete removes the local branch. When `origin/<base_ref>` later changed the same lines, the task counts as not merged, and the delete asks for `--confirm-unpushed`.

#### Backlog view

- **Add**: ask for a title, a summary and an optional pipeline.
- **Drag** a card to change its priority.
- **Start**: open the Launch form with the description, the pipeline and the entry filled in. The entry leaves the backlog when the task starts.
- **Delete**: remove the entry after a confirmation.

#### Banner

The server runs the terminal check once, when it starts.
If the check fails, an orange banner shows the message at the top of the page.
The buttons that need the terminal are disabled. This includes "Start" in the backlog.
To clear the banner, fix the terminal problem (see Troubleshooting). Then run `factory server stop` and `factory dashboard`.

#### Ticket links

Set `ticket_url` in `.factory/factory.yaml` to make tickets links.
Use `{key}` where the ticket goes. Example: `ticket_url: https://example.atlassian.net/browse/{key}`.
Only `http` and `https` URLs are used.

#### Security

- The server listens on `127.0.0.1` only. It uses a random port.
- Each start makes a new token. The URL holds it: `?token=...`. Every API call must send it.
- The server checks the `Host` header. It must be `127.0.0.1` and the server port.
- The server checks the `Origin` header. If present, it must be the server itself.
- The server stops after 30 minutes without requests. `factory dashboard` starts it again.
- While a task waits on a step with a `done_check`, the server keeps running, so the checks run without an open page.
- `factory wait`, `factory resume` and `factory tasks` start the server when a task waits on a done check. After a restart of the computer, the orchestrator start runs `factory tasks`, so the polling starts again.
- Only one server runs per repository. A server that is replaced stops by itself.
- `factory server stop` stops it now. The menu action "Exit" runs `factory server stop --unless-waiting`.
- The file `.factory/server.json` holds the port and the token. Only you can read it.
- The log is `.factory/server.log`.

### Step manifest fields

`id`, `description`, `category`, `type` (`ai`, `command` or `group`), `outputs`, `done_when`, `done_check`, `config`, `required`, `run_in`, `model`, `effort` (only for `ai`), `requires`, `column`, `wait_external`, `exclusive`, `steps` (only for `group`).

`factory done` checks, in this order: every output that is not optional is set, every `file` output points to a path that exists, a `command` step's last `factory run-command` exited with 0, then the `done_check`.

### Pipeline fields

- `id`, `description`
- `inputs`: values asked at launch, each with a `type` and a `description`. A relative `file` path is resolved from the main repository.
- `steps`: a list of entries with `id`, `with`, `model`, `effort`, `column` and `loop`.
- `loop`: repeat a range of steps while a task key is set.
  - `back_to`: this entry or an earlier entry. The loop range goes from there to this entry.
  - `while`: a task key name.
  - `max`: the most jumps back, from 1 to 20.

  A review loop:

  ```yaml
  steps:
    - write-spec
    - id: review-spec
      loop:
        back_to: write-spec
        while: findings
        max: 2
    - next-step
  ```
- `claude`: `model` and `effort` of the task session.
- `start_column`: the board column of a new task.

### Loops

- When `factory done` succeeds on the last step of a loop entry, the factory reads the `while` key.
- The key is not set when it is missing, empty or `none`, ignoring case and spaces around it.
- Set, with fewer than `max` jumps: the task goes back to the first step of `back_to`. `factory done` prints "Loop <n> of <max>: back to `<step>`. Run `factory next`."
- Set, after `max` jumps: the task moves to the next step and is blocked. The session asks the user what to do. When the user says to go on, the session runs `factory unblock`. For one more round, after the user approves, the session runs `factory goto`.
- Not set: the task moves on. A skipped step never makes its loop jump.
- At the limit on the last entry, the task finishes. The check warns about a loop on the last entry.
- The jump keeps the task keys. Session steps run again in the same session, with the conversation of the earlier rounds.
- A loop's count goes back to 0 when the task jumps to a step before its range. An inner loop gets its full `max` in each round of an outer loop.
- A step inside the range that outputs the `while` key gets a footer line: "This step controls a loop. Set `<key>` to `none` when nothing is left." A clean round must reset the key, because task keys keep their values.
- `factory status` and the dashboard card show "loop <n> of <max>".

### Events

Each task logs its events in `.factory/tasks/<id>/events.jsonl`, one JSON object per line. Loops add two events:

- `loop_back`: the loop jumped back. It has `entry`, `to` (the target step), `round` (the jump number) and `max`.
- `loop_limit`: the loop reached `max` with the key still set. It has `entry` and `key`.

Renames add `task_renamed` (`name`), `rename_failed` (`name`, `reason`) and `claude_renamed` (`name`).

### `.factory/factory.yaml` fields

`version`, `library`, `terminal`, `columns`, `poll_minutes`, `ticket_url`, `hidden_steps` (optional: the ids of hidden steps).

When `factory.yaml` or `config.yaml` is not valid YAML, every command prints `Error: <path>: <problem>, line <n>.` and exits with code 1.

## Troubleshooting

- **Terminal check failed.** Start Claude inside a Herdr pane. The pane sets `HERDR_ENV=1`. If `herdr` is missing, install it.
- **Data version mismatch.**
  - Older data: start the orchestrator. It runs the migration.
  - Newer data: update the plugin.
  - The migration to version 2 stops if a key name breaks the rule or a task uses the old step assistant. It lists what to fix.
- **Rename failed.** The ticket rename did not work. It was the rename of the Herdr agent, tab or workspace, or the Claude `/rename`. The id and the worktree do not change. A resume applies the name with `--name`.
- **Could not bring the app to the front.** Check the terminal app with `factory config get terminal terminal_app`. Set it with `factory config set terminal terminal_app '<app>'`. An empty value means only the focus inside Herdr. This works only on macOS.
- **Session gone.** Choose "Resume a task" in the menu, or run `factory resume <id>`.
- **Folder trust dialog.**
  - Worktrees of a repository you already trust in Claude show no trust dialog.
  - If the dialog appears, the repository is not trusted. The launch fails with a clear message.
  - Open Claude once in the main repository and trust it. Then launch again.
