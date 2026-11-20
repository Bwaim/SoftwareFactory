# Software Factory

## What it does

The Software Factory starts each task in its own Herdr tab and its own named Claude session.
A task gets its own git worktree when its pipeline has `worktree: true`.
Each type of task is a pipeline. A pipeline is an ordered list of reusable steps.
One task is one run of a pipeline.
You start and manage tasks from one orchestrator session in the main repository.

## Concepts

- **Task**: one run of a pipeline. It has a Herdr tab and a Claude session. It has a git worktree when its pipeline has `worktree: true`.
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
- A terminal: Herdr (https://herdr.dev, the default) or Warp (https://www.warp.dev) with tmux (`brew install tmux`). See [Terminal: Herdr or Warp](#terminal-herdr-or-warp).
- git, only for pipelines with `worktree: true`. Each repository can have an `origin` remote, but it is optional.
- Claude Code.
- Optional: `gh` or `glab`, for the forge steps of the catalog.

Install the factory with this command:

```sh
curl -fsSL https://raw.githubusercontent.com/Bwaim/SoftwareFactory/main/install.sh | sh
```

The script downloads the latest release into `~/.local/share/software-factory` and makes sure that its SHA-256 matches the release. It creates the link `~/.local/bin/factory`. If `~/.local/bin` is not in your `PATH`, add it. `factory init` does not create the link. If the link is missing, run `factory link`.

Then the script asks which multi-terminal tool you already have: Herdr, Warp (macOS, with tmux), or none.

- With none, it asks which one to install. It can run the install for you, after you say yes: Herdr's own install script, or `brew install --cask warp` and `brew install tmux`.
- It saves the choice in `~/.config/software-factory/terminal`. `factory init` writes it into each new repository's `.factory/factory.yaml` (`terminal:`). A repository already set up keeps its own choice.
- The questions read the terminal, so they work with `curl ... | sh`. Without a terminal (CI), nothing is asked. Set `FACTORY_INSTALL_TERMINAL=herdr` or `warp` to choose without a question.

To update the factory, run the same command again.

If you used the plugin before, uninstall it in Claude Code:

```
/plugin uninstall software-factory@software-factory
```

Hooks run the installed copy through `~/.local/bin/factory`, and the plugin skill runs its own copy. Two code versions on the same `.factory` data are not supported. Older plugin copies also move the link back to the plugin.

Start the factory:

1. In the main repository, run `factory init`. To use a library, run `factory init --library <path>`. The library folder holds the generic steps and pipelines.
2. Run `factory dashboard`. The dashboard launches and manages tasks.

The library is optional. Without a library, only built-in and local steps exist. To add a library later, set `library:` in `.factory/factory.yaml`.

A repository without an `origin` remote also works. `factory init` shows a warning. Tasks start from the local base branch, with no fetch. Push and pull request steps fail.

Some actions exist only in the CLI:

- `factory init`: add the factory to a repository.
- `factory migrate`: migrate the data after an update.
- `factory catalog install`: install a step or pipeline from the catalog.
- `factory library commit`: commit changes in the library.
- `factory pipeline edit`: open the pipeline editor.
- `factory step edit`: open the step form.

To write pipelines and steps with an agent, call `/factory-authoring` in any Claude session. See "Authoring skill" in the reference.

### Bash allowlist

Task sessions use `.factory/claude-settings.json`, which allows every `factory` command and runs two hooks (see "May wait for you"). `factory init` and `factory version check` add what is missing to this file. They keep your own rules and hooks.
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
- `herdr agent start`, `herdr agent prompt`, `herdr agent get`, `herdr agent read`, `herdr agent attach`
- `herdr agent focus`, `herdr agent wait`, `herdr agent send-keys`
- `herdr workspace rename`, `herdr tab rename`, `herdr agent rename`
- `open -a <terminal app>`
- `herdr notification show`

Warp adapter:

- `tmux -L captn new-session`, `has-session`, `kill-session`, `rename-session`
- `tmux -L captn capture-pane`, `send-keys`, `load-buffer`, `paste-buffer`, `list-clients`, `display-message`, `attach-session`
- `open warp://tab_config/<name>`, `open -a Warp`, `open -Ra Warp`
- `~/Applications/CAPTN Factory.app/Contents/MacOS/captn-notify <title> <body> <sound>`, and to build that app: `swiftc`, `codesign --sign -`, `lsregister -f`
- `osascript` (`display notification`), when the CAPTN Factory app cannot be used

## Terminal: Herdr or Warp

The factory runs each Claude session through a terminal adapter. Choose it with `terminal:` in `.factory/factory.yaml` (`herdr` or `warp`). The `FACTORY_TERMINAL` environment variable is used when the file has no value. Run `factory terminal check` after a change.

With **Warp** (macOS only):

- Warp cannot be driven from outside: its control tool (`warpctrl`) is off in the Stable release and cannot send input or read a pane. So Claude runs in a tmux session that the factory owns, and Warp only shows it.
- tmux keeps a terminal session running in the background. The factory uses its own tmux server (`tmux -L captn`), so your own tmux sessions are not touched.
- At launch the factory starts `claude` in a detached tmux session named after the task, in the task worktree. Then it writes a Warp tab config `~/.warp/tab_configs/captn-<name>.toml` and opens it: a new Warp tab attaches to the session.
- Closing the Warp tab does not stop Claude. **Focus a task** opens a new tab when none is attached, or brings Warp to the front. It cannot pick the tab inside Warp.
- Working or idle comes from the factory's Claude hooks (`Stop` and `UserPromptSubmit`), saved in `.factory/session-activity/`.
- Close, pause and delete stop Claude and end the tmux session. The Warp tab then closes, and the tab config file is removed.
- To look at a session by hand: `tmux -L captn ls`, then `tmux -L captn attach -t <name>`.
- Notifications show the CAPTN icon. macOS shows the icon of the app that sends a notification, so the factory sends through its own small app, `~/Applications/CAPTN Factory.app`. The first notification builds it with `swiftc` (from the Xcode command line tools) and signs it for this Mac only. It is built again when its sources change.
- The first time, macOS asks whether CAPTN Factory may show notifications. Click **Allow**. If you closed the question or clicked **Don't Allow**, turn it on in **System Settings → Notifications → CAPTN Factory**: macOS does not ask again.
- Until the app is allowed, or without `swiftc`, notifications still come, through `osascript`, with the Script Editor icon.

## Tutorial

1. **Init the factory.**
   - Open the orchestrator in a repository. Choose "Init the factory".
   - If you want a library, give the library folder path. Say yes to create it if it does not exist. If you do not want a library, say no.
   - Say yes to the starter pack. Without a library, the starter pack is local.
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
- **Release a shared resource**: free an exclusive resource that a stuck task holds. It shows the holder and the waiting tasks, and asks you to confirm.
- **Create or edit a pipeline**: open the pipeline editor in the browser.
- **Create a new step**: open the step form in the pipeline editor.
- **Create or edit a pipeline in this session**: answer the questions of the orchestrator. It writes the pipeline file and checks it.
- **Create or edit a step in this session**: answer the questions of the orchestrator. It writes the step file and checks it.
- **Delete a step**: delete a local or generic step. It first shows what the delete does, then asks you to confirm.
- **Browse the catalog**: list and install catalog pipelines and steps.
- **Add a backlog entry**: add an entry to the backlog.
- **Remove a backlog entry**: remove an entry from the backlog.
- **Open dashboard**: start the local server, add this repository to the dashboard list and print the dashboard URL.
- **Init the factory**: set up the repository. Shown only before init.
- **Exit**: ask to pause all tasks. The local server keeps running and stops by itself after the idle time.

### Commands

Global option: `factory --version`.
Most commands take `--task <id>` and `--json`.
Inside a task worktree, the task is found from the folder.

Setup:

- `factory init [--library <path>] [--create-library]`: set up the factory in this repository and add it to the dashboard list. The library is optional.
- `factory link`: create or fix the `~/.local/bin/factory` link.
- `factory menu`: show the orchestrator menu.
- `factory terminal check`: check the terminal adapter.
- `factory version check`: compare the data version with the plugin.
- `factory hook stop`, `factory hook prompt`: used by the Claude hooks. They read the hook input on stdin, print nothing and always exit 0. `factory hook notify-later <id> <at>` is started by `hook stop`.
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

- `factory launch <pipeline> [--description <text>] [--input <name=value>] [--id <id>] [--from-backlog <id>] [--dry-run]`: start a task. When the pipeline input `ticket` holds a Jira key (`HT-4549`, a URL or a text), the task id is that key in lowercase, for example `ht-4549`, plus `-2` when taken. Without an `origin` remote, the task starts from the local base branch.
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
- `factory cancel <id> [--dry-run]`: drop an unfinished task. It closes the Claude session and its terminal, removes the worktree, deletes the local branch and moves the task folder to the archive. It always deletes the local branch, even when the work is not merged or not pushed. It never deletes a remote branch and never closes a merge request. It refuses a finished task: use Clean or `factory delete <id>`. `--dry-run` changes nothing. It lists the uncommitted changes, the commits that are not on `origin` and the open remote branch. Without `--dry-run`, it asks for no second approval. After the cancel, it prints the restore lines: `git branch <branch> <commit>` for the branch, and `git stash apply <commit>` for the uncommitted changes. When the worktree was in detached HEAD, it also prints the commit where it was. The commit of the uncommitted changes is not on any branch, so `git gc` can remove it after about 2 weeks.
- `factory clean`: list finished tasks that can be deleted.
- `factory exclusive status [--json]`: list each exclusive resource with its holder and its queue.
- `factory exclusive release <name> [--force]`: free a resource. Without `--force`, only the holder can do it. With `--force`, anyone can, and the holder loses it.
- `factory exclusive acquire <name>`: take a resource again after a release. It waits in the queue when the resource is used.
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
- `factory dashboard`: start the local server if needed, add this repository to the dashboard list and print the dashboard URL. It works from any folder.
- `factory server stop`: stop the local server.
- `factory server stop --unless-waiting`: stop the local server only when no task waits on a done check.

### Folder pipelines

Each pipeline has a required key `worktree`. Its value is `true` or `false`.

- `worktree: true`: each task gets its own git worktree and branch. The repository must be a git repository.
- `worktree: false`: the task runs in the workspace folder. It has no worktree and no branch. The folder does not need git.

A workspace can be a plain folder outside git. Add it in the dashboard like any repository. `factory init` works in it. Only pipelines with `worktree: false` run there. A pipeline with `worktree: true` is listed as unavailable.

A machine without the `git` program runs only pipelines with `worktree: false`. The factory does not call git for these tasks.

The data version is 3. Run `factory migrate` after an update. It adds `worktree: true` to each pipeline that has no `worktree` key.

The built-in pipeline `quick-task` ships with `worktree: false`. The steps `implement` and `user-validation` work in both kinds of pipeline. `user-validation` shows `git status` with git. Without git, it lists the files that the task changed.

Two tasks of folder pipelines in one workspace can change the same files. You are in charge of this.

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

Open it with the menu action "Open dashboard" or with `factory dashboard`. `factory dashboard` works from any folder.
The page refreshes every 5 seconds.
The header has two views: **Tasks** and **Backlog**.

#### Workspaces

One server serves all your repositories. Each repository in the dashboard is a workspace.
The sidebar lists the workspaces. Each entry shows the number of tasks that need you.
If there is no workspace, the main area shows "No workspace. Click + to add a factory."

- Click `+` to add a workspace. Type the path of a repository, or click the folder picker.
- The folder picker works only on macOS. On another platform, type the path.
- If the repository has no factory, a confirm step opens with the title "Set up the factory in <main>?". It has the field "Library folder". Leave the field blank for no library. Click "Set up and add" to run `factory init` and add the workspace.
- If the library folder does not exist, the dashboard shows an error. Create the folder, or leave the field blank.
- Click `⋯` on a workspace, then "Rename", to change its name in the sidebar.
- Click `⋯` on a workspace, then "Delete", to remove it from the dashboard. The repository and its tasks stay on disk. Done checks of this workspace stop.

A workspace comes back when you run `factory init` or `factory dashboard` in the repository. It also comes back when `factory tasks`, `factory resume` or `factory wait` finds a task in the repository that waits for a done check. `factory launch` does not add it.

The commands `factory pipeline edit` and `factory step edit` need the repository in the dashboard list. If it is not, they print "This repository is not in the dashboard. Run `factory dashboard` in it first."

The server keeps its data in `$FACTORY_HOME`. The default is `~/.config/software-factory`. It has these files:

- `workspaces.yaml`: the list of workspaces.
- `server.json`: the port and the token.
- `server.yaml`: the server settings, for all workspaces. Today it has `poll_seconds`.
- `server.log`: the server log.

#### Settings

Click `⋯` on a workspace, then "Settings". The popup has three sections.

"Repository" edits `.factory/factory.yaml`:

- "Library folder": an absolute path, or empty for no library. "Create the folder if it is missing" makes the folder on save. A change shows a warning when the workspace has open tasks.
- "Terminal": the terminal adapter. A change fails when the workspace has open tasks.
- "Columns": the board columns. Use "↑", "↓" and "✕" to order and remove them, and "Add column" to add one.
- "Ticket URL": empty, or a `http` or `https` URL with `{key}`. `factory init` writes the Nextory ticket URL `https://nextory.atlassian.net/browse/{key}` as the default `ticket_url`.
- "Hidden steps": click "Unhide" to show a step again.

"Built-in step settings" edits the section `create-worktree` of `.factory/config.yaml`:

- "Worktree folder" (`worktree_root`): an absolute path. It cannot be empty.
- "Base branch" (`base_ref`): empty means `main`.

"Server" edits `poll_seconds` in `$FACTORY_HOME/server.yaml`. It is the poll interval in seconds, from 10 to 86400. It applies to all workspaces. The order is `FACTORY_POLL_SECONDS`, then `poll_seconds`, then 5 minutes. If `FACTORY_POLL_SECONDS` is set, the field is disabled. A save applies at once, without a restart.

Column rules:

- A column name cannot be empty, cannot be `Done`, cannot have more than 40 characters, and cannot appear two times.
- A column that a step file or a pipeline file names cannot be removed. The popup lists the files.
- If an open task is in a removed column, or its snapshot names one, the popup asks for a new column for each removed column. The next "Save" moves these tasks. Finished tasks stay in `Done`.

The dashboard makes sure that all values are valid. If one is not, it writes nothing. The popup sends only the changed values. A file without changed values is not written. The popup shows this note above the buttons: "Save rewrites .factory/factory.yaml and .factory/config.yaml. Comments in these files are lost." Cancel closes the popup without a save.

#### Tasks view

The page itself does not scroll: the board, the workspaces, the details and the terminal each scroll on their own, and reaching the end of one does not scroll another.
The **Workspaces** column on the left has a vertical tab on its right edge, like the task columns. It is open by default; click the tab to hide or show the list. Drag its right edge to change its width (220 px by default); the arrow keys work on a focused edge and a double click resets it. The browser remembers your choices.

The board has one column for each name in `columns` of `.factory/factory.yaml`, plus a `Done` column.
A finished task is always in `Done`.
Any other task is in the column of its current step.
If the column is unknown, the task goes in the first column.
The "Columns" buttons hide or show a column. The browser remembers your choice.

Each card shows:

- The ticket, then the display name, then the id when it differs. A failed rename is shown in red. The ticket is a link when `ticket_url` is set.
- The description.
- The pipeline and the current step.
- The status, as a coloured pill with the time in this status. The reason is shown below when there is one.
- A red "Session gone" tag when the terminal session is not there. Not shown for `paused` and `finished` tasks.
- The artifacts of the task. Click a name to read it. The viewer closes with Escape, a click outside it, or its Close button. Its title bar stays visible, and the text scrolls inside it. A form, for example "Request changes", never closes on a click outside. Escape on a form with typed text asks "Discard the typed text?".
- For a task that is `waiting_external` on a step with a `done_check`: "Next check in m:ss", counted down in the page, and the last check with its time and result.
- For a task that waits for an exclusive resource: "Waiting for <name>, used by <holder>". The holder shows "Uses <name>", or "Keeps <name> while paused".
- For a task with `attention`: a pink "May wait for you" pill with the time since the turn ended, and the last lines of the message as plain text. An `active` task then shows only this pill.
- "To validate", when the step waits for your approval. The artifact to read has a "to validate" tag in the artifact list. If the step validates code, the card has an "Open in IDE" button.

Status pill colors:

| Status | Color |
| --- | --- |
| `active` | green |
| `blocked` | pink |
| `awaiting_approval` | yellow |
| `waiting_external` | purple |
| `paused` | grey |
| `finished` | grey, green dot |

The header has a light and dark mode button. The browser remembers your choice, for the dashboard and the pipeline editor.
The browser tab title shows how many tasks need you, for example "(2) CAPTN Factory". An "Offline" tag shows when the page cannot reach the server.

Card buttons. Send prompt, Pause and Cancel are in the "⋯" menu.

- **Focus**: switch the terminal to the task session. Shown when the session exists, the task is not finished and the terminal supports it. Then it brings the terminal app to the front. The first time, it asks for the app name. When it fails, the card says so.
- **Show MR**: open the merge request. Shown when the task has an MR link.
- **Approve** and **Request changes**: shown when the status is `awaiting_approval`. "Request changes" asks for a text.
- **Mark done**: shown when the status is `waiting_external` and the wait has no done check.
- **Check now**: shown when the status is `waiting_external` and the wait has a done check. It runs `factory poll --task <id>` as a background job. The button shows "Checking…" until the result.
- **Release**: shown on a task that waits for an exclusive resource. It asks "Release <name> from task <holder>? Its session loses the resource." in a dialog. The task has no "Mark done" or "Check now" button.
- **Send prompt**: send text to the session. If the session is working, choose "Wait until idle" or "Send now".
- **Pause**: shown when the session exists and the task is not paused. Choose "Wait until idle" or "Stop now". The card shows "Pausing..." until it ends.
- **Resume**: shown when the task is paused or its session is gone.
- **Cancel**: red button, shown on every card that is not in `Done`. It opens a dialog that shows "Loading…" while the dry run runs, then what the cancel removes and what is lost. Click "Cancel task" (red) to cancel, or "Keep task" to stay. Escape and a click outside the dialog do the same as "Keep task". While it runs, the button shows "Cancelling…", and Escape and a click outside do nothing. The card is removed at once. When a part is left, for example a branch that git could not delete, the dialog stays open with the list.
- A finished task has no Focus, Send prompt, Pause or Resume button.

"Send prompt", "Pause", "Resume", "Launch", "Check" and the backlog "Start" are disabled when the terminal check fails.

#### Task details

Two columns sit on the right of the board: **Details**, then **Terminal**. Each column has a vertical tab on its left edge. A tab opens or closes only its own column; a closed column shows only its tab. The browser remembers which columns are open.
The board always has a selected task, shown with a pink outline: the task in the address (`#task=<id>`), else the last task you opened in this workspace, else the first task of the leftmost column. Click a card, or its name, to select it: this opens both columns. When the narrower board would hide the card's column, the board scrolls sideways just enough to show it.
By default, the two open columns together cover about a third of the page; one open column alone also covers about a third. A width you drag stays.
Click a column's tab, or press Escape outside the terminal for the details, to close it; the task stays selected.
Below 900 px, an open column fills the page.
The details refresh every 3 seconds while their column is open. They show:

- The name, the ticket, the description, the status and the same buttons as the card.
- **Pipeline**: every step of the pipeline. Done steps have a check, the current step says "now" and the loop count.
- **Timeline**: the events of the task, newest first, from `events.jsonl`. It shows the last 200 events.
- **Details**: pipeline, ticket, MR, branch, base, worktree, created and updated times, the values of the task state and the artifacts.

#### Task terminal

The Terminal tab opens the session terminal of the selected task. Its title shows the task name.
Drag the left edge of the details or of the terminal to change its width. The arrow keys move a focused edge too, and a double click resets it. The browser remembers the widths.

The terminal is a real terminal, attached to the session:

- The server runs the adapter's attach command (`herdr agent attach <agent>`, or `tmux -L captn attach-session -t <name>` with Warp) in a pseudo-terminal and streams it to the page. The page shows it with xterm.js, served by the local server from `lib/factory/web/vendor/xterm` (no CDN).
- Click in the terminal and type: every key goes to the session as you press it. The key buttons (Esc, Tab, the arrows, Backspace, Space, Enter, Ctrl+C) send the same keys.
- The terminal follows the size of its column.
- One terminal per task is shared by every open page. A new page gets the last 256 KB of output first.
- A terminal nobody watches closes after 30 seconds. At most 8 are open at once.
- "Reconnect" shows when the terminal or the connection ends.
- Typing clears "May wait for you". The timeline shows "Opened the live terminal" once per task, the first time; not each key, and not each restart.
- It needs a live session and a terminal adapter with `attach`. Otherwise the terminal says why.
- Escape inside the terminal never closes the panel.

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

Clean, delete and cancel use the same check. The reason of a task is one of these, in this order:

1. `no branch`: the task has no local branch. A worktree in detached HEAD can still hold commits that were never pushed. They are listed, and the delete asks for approval.
2. `merged into origin/<base_ref>`: the branch is an ancestor of `origin/<base_ref>`.
3. `merged (squash)`: `git merge-tree --write-tree` gives the tree of `origin/<base_ref>`. The content of the branch is already there.
4. `merged (squash)`, by patch id: the changes of the branch have the same patch id as a commit of `origin/<base_ref>`. This also works when a later commit changed the same lines. A commit added to the branch after the squash changes its patch id, so it is listed as lost.
5. `pushed, and its remote branch was deleted`: the branch tracks its own remote branch, and that branch is gone. The delete asks for approval only when something would be lost: commits, uncommitted changes or failed checks. It always keeps the local branch.
6. `not merged`: none of the above.

Without an `origin` remote, the checks compare with the local `<base_ref>` branch. Reason 2 is then `merged into <base_ref>`. Reason 5 never happens.

For reasons 2 to 4, the commits are not listed as lost, and the delete removes the local branch. Uncommitted changes still need approval. So do commits on a detached HEAD.

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
You can also set it in the "Settings" popup.

#### Security

- The server listens on `127.0.0.1` only. It uses a random port.
- Each start makes a new token. The URL holds it: `?token=...`. Every API call must send it.
- The server checks the `Host` header. It must be `127.0.0.1` and the server port.
- The server checks the `Origin` header. If present, it must be the server itself.
- The server stops after 30 minutes without requests. `factory dashboard` starts it again.
- While a task waits on a step with a `done_check`, the server keeps running, so the checks run without an open page.
- `factory wait`, `factory resume` and `factory tasks` start the server when a task waits on a done check. After a restart of the computer, the orchestrator start runs `factory tasks`, so the polling starts again.
- Only one server runs for all workspaces. A server that is replaced stops by itself.
- `factory server stop` stops it now. The menu action "Exit" does not stop the server.
- The file `$FACTORY_HOME/server.json` holds the port and the token. Only you can read it.
- The log is `$FACTORY_HOME/server.log`. `server.json` and `server.log` are not in `.factory/` any more.

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

### Exclusive steps

A step with `exclusive: <name>` uses a resource that only one task at a time can use, like an emulator.

- Hold: the first task takes the resource when its step starts. Other tasks wait in a queue. They are `waiting_external`, but not for an external event: `factory poll` does not run their `done_check`, and `factory external-done` refuses them.
- Release: the holder frees the resource when it leaves the step. This happens on `factory done`, `factory skip`, `factory goto`, a loop jump, the end of the pipeline and `factory delete`. If the next current step has the same exclusive name, the task keeps the resource. A session can free it earlier with `factory exclusive release <name>`, and take it again with `factory exclusive acquire <name>`. A paused task keeps it.
- Handover: when the resource is free, the first waiting task gets it. The factory sends its session a message. A paused task is passed over.
- Force: `factory exclusive release <name> --force` frees a resource that a stuck task holds. The menu action "Release a shared resource" and the "Release" button do the same.
- Scope: the name is per repository. The state is in `.factory/exclusive/<name>.json`.

### May wait for you

A task session may end its turn to ask you a question. The factory notices it with two Claude hooks.

- Hooks: `.factory/claude-settings.json` has a `Stop` hook (`factory hook stop`) and a `UserPromptSubmit` hook (`factory hook prompt`). The command uses the absolute path of the `factory` link. `factory init` and `factory version check` add the hooks when they are missing, and keep your other rules and hooks.
- When it is set: the `Stop` hook sets the task field `attention` (`at` and `message`) when the task is `active`. The message is the end of the last answer of the session (12 lines at most). Nothing is set for any other status, or when the session still has background work.
- Notification: the terminal shows "<name> may wait for you: <first line>" when the adapter supports `notify`. If the pane of the task is not focused, you are notified at once. If it is focused, the 60 second rule applies: the factory waits 60 seconds and notifies only if `attention` is still the same. An adapter without the `focused` check also uses the 60 second rule. A focused pane does not always mean you look at it, so the card shows "May wait for you" at once in both cases.
- Clearing: `attention` is cleared when you send a prompt (the hook, the dashboard or the menu) and when the task status changes (block, wait, approve, pause, finish and so on).
- Display: `factory tasks` and the dashboard sort tasks with `attention` first, together with `blocked` tasks, then `awaiting_approval`. The text list adds ", may wait for you: <first line>".
- Hooks never print anything and always exit 0. A hook error is logged as `hook_failed` on the task.
- `FACTORY_ATTENTION_DELAY` changes the 60 seconds (for tests).

### Events

Each task logs its events in `.factory/tasks/<id>/events.jsonl`, one JSON object per line. Loops add two events:

- `loop_back`: the loop jumped back. It has `entry`, `to` (the target step), `round` (the jump number) and `max`.
- `loop_limit`: the loop reached `max` with the key still set. It has `entry` and `key`.

Exclusive steps add `exclusive_wait`, `exclusive_start`, `exclusive_release`, `exclusive_acquire` and `exclusive_forced`. Each has `name`.

"May wait for you" adds `attention` (`message`: the first line), `attention_cleared` (`reason`: `prompt` or `status`) and `hook_failed` (`hook`, `error`).

Renames add `task_renamed` (`name`), `rename_failed` (`name`, `reason`) and `claude_renamed` (`name`).

### `.factory/factory.yaml` fields

`version`, `library`, `terminal`, `columns`, `ticket_url`, `hidden_steps` (optional: the ids of hidden steps).

The key `poll_minutes` is not used any more. The poll interval is `FACTORY_POLL_SECONDS`, else `poll_seconds` in `$FACTORY_HOME/server.yaml`, else 5 minutes.

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
