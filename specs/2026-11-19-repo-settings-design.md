# Workspace settings in the dashboard

Source: user request in the session of 2026-11-19.

## Intent

The user edits `.factory/factory.yaml` and `.factory/config.yaml` by hand. The dashboard must show the settings of a workspace in a popup, check the values, and save them.

## Terms

- Settings popup: a modal over the dashboard. It shows the settings of one workspace and the server settings.
- Open task: a task with a status other than `finished` (`board.open_tasks`).
- Removed column: a name in the saved `columns` that is not in the new `columns`.
- Column user: a step file or a pipeline file that names a column. A step file names it in `column`. A pipeline file names it in `start_column` or in the `column` of an entry.
- Task snapshot: the step entries that a task keeps from the launch time (`Registry.expand`). Each entry can name a column. Loops and goto can run an earlier entry again, so every entry counts.
- Server settings file: `$FACTORY_HOME/server.yaml`. It holds settings for all workspaces.

## Goals

1. Each workspace menu ("⋯") has a "Settings" item. It selects the workspace and opens the settings popup.
2. The popup has three sections: "Repository", "Built-in step settings" and "Server".
3. The dashboard checks the values on Save. Nothing is written if a check fails.
4. Changes apply without a server restart.

## Non-goals

- Settings of catalog steps (`forge`, `test_command`, `plan_style` and others). A pipeline gives them with `with:`, or the step asks for them.
- Settings of `user-validation`. A pipeline gives them with `with:`.
- Rename of a column that also updates tasks and pipelines.
- Edit of `version` or `.factory/claude-settings.json`.

## Anti-goals

- A save removes a column that a step file or a pipeline file names. This breaks launches of that pipeline.
- A save leaves an open task in a removed column without a choice of the user.
- A save writes keys that the user did not change. Other writers (`factory config set`, the "Hide" button) can change the same files at the same time.
- A partial save: one file is written and the next check fails.

## Section "Repository"

The values are in `.factory/factory.yaml`.

1. Library folder (`library`).
   - A text field and a "Choose folder…" button. The button shows only when `/api/host` returns `folder_picker: true`. It uses `/api/workspaces/pick-folder`.
   - A checkbox "Create the folder if it is missing".
   - An empty value means no library.
   - The value must be an absolute path after `~` expansion.
   - If the folder does not exist and the checkbox is off, the save fails.
   - If the checkbox is on, the save calls `init.create_library_folder`.
   - If the value changed and the workspace has open tasks, the popup shows a warning before Save. The save is not blocked.
2. Terminal (`terminal`).
   - A dropdown. The choices are `herdr`, plus the saved value if it is not `herdr`.
   - If the value changed and the workspace has open tasks, the save fails.
   - The server rebuilds the runtime of a workspace when `factory.yaml` changes, so the new adapter applies at the next request.
3. Columns (`columns`).
   - An ordered list of text fields. Each row has "↑", "↓" and "✕" buttons. An "Add column" button adds an empty row at the end.
   - Each name is trimmed. The list must have at least one name. A name cannot be empty, cannot be `Done`, cannot be longer than 40 characters, and cannot be in the list two times.
   - Removed columns are checked against column users. The check uses the library of this save (the new value if it changed). It skips files that it cannot read or parse. If a removed column has a column user, the save fails and lists each file.
   - An open task needs a move if its column is a removed column, or if an entry of its task snapshot names a removed column.
   - If open tasks need a move, the save fails with the code `moves_needed`. The popup then shows one dropdown for each such column, with the new columns as choices. The next Save sends `moves` (`{removed column: new column}`).
   - In one task update, the save changes the task column if it is a removed column, and replaces each removed column in the task snapshot with its target. It logs a `column_changed` event only when the task column changed.
   - Finished tasks are not moved. The board shows them in `Done`.
   - After a save, the board shows the new columns.
4. Ticket URL (`ticket_url`).
   - The placeholder is `https://nextory.atlassian.net/browse/{key}`.
   - `factory init` writes this URL as the default for new repositories.
   - An empty value is allowed. A value that is not empty must start with `http://` or `https://` and must contain `{key}`.
5. Hidden steps (`hidden_steps`).
   - A list of the hidden step ids. Each row has an "Unhide" button. A click marks the row.
   - The popup sends only the marked ids (`unhide`). The save removes these ids inside the write of `factory.yaml`. A step that another writer hid while the popup was open stays hidden.
   - With no hidden steps, the section shows "No hidden steps."
   - If the list becomes empty, the save removes the key.

## Section "Built-in step settings"

The values are in `.factory/config.yaml`, in the section `create-worktree`.

1. Worktree folder (`worktree_root`). The hint is "Used by the built-in step `create-worktree` only."
   - The value cannot be empty, because the step has no default and launches need it.
   - The value must be an absolute path after `~` expansion. The server runs in `$FACTORY_HOME`, so a relative path points to the wrong folder.
2. Base branch (`base_ref`). The placeholder is `main`. The hint is "Used by the built-in step `create-worktree` only."
   - An empty value removes the key from `config.yaml`. The step default `main` applies again.

## Section "Server"

1. Poll interval in seconds (`poll_seconds` in `$FACTORY_HOME/server.yaml`). The hint is "Applies to all workspaces."
2. The value is a whole number from 10 to 86400. An empty value removes the key.
3. Order of precedence: `FACTORY_POLL_SECONDS`, then `poll_seconds`, then 300.
   - A value that is not valid goes to the next item. This includes a `server.yaml` that is not valid YAML. A bad file never stops the poll loop.
4. If `FACTORY_POLL_SECONDS` is set, the field is disabled. The text is "Set by FACTORY_POLL_SECONDS (<n> seconds)."
5. A save wakes the poll loop. The loop computes the next poll time with the new interval. It does not poll at this wake.

## Save

1. The popup sends only the changed values. If no repository value changed, it does not send the repository save.
2. The server checks all values first. If a check fails, it writes nothing and returns all errors.
   - A value with a wrong type is a check error, not a server error.
   - An unknown key, an unknown step id in `steps`, or an unknown key in a step is a check error.
   - If `steps` changes, the check reads `config.yaml` first. A `config.yaml` that is not a valid YAML map is a check error.
3. The server then writes `factory.yaml` in one `fsio.update_yaml` call, `config.yaml` in one `fsio.update_yaml` call, and moves the tasks.
   - The server writes a file only if it has changed keys. This keeps the comments and does not rebuild the runtime for nothing.
   - The move skips a task that no longer exists. It changes the task column only if it is still a removed column. It always replaces removed columns in the task snapshot.
4. The popup saves the repository settings first, then the server settings.
   - If the server settings save fails, the popup stays open and shows the error. The repository settings stay saved.
5. A note above the buttons says: "Save rewrites .factory/factory.yaml and .factory/config.yaml. Comments in these files are lost."
6. Cancel closes the popup without a save. A click on the backdrop does not close it.

## API

1. Workspace routes:
   - `GET /api/w/<id>/settings`: the current values, the terminal choices, the ticket default, the hidden steps, the `create-worktree` values, and the open task count.
   - `POST /api/w/<id>/settings/save`: the changed values. On a failed check, HTTP 400 with `errors` (a list of texts). On missing moves, HTTP 400 with `code: "moves_needed"` and `moves_needed` (`{column: [task ids]}`).
2. Global routes:
   - `GET /api/server-settings`: `poll_seconds`, `saved_poll_seconds`, `env_poll_seconds`, `default_poll_seconds`.
   - `POST /api/server-settings/save` with `{poll_seconds}`.

## Docs

The README gets a "Settings" section for the dashboard. It also lists `server.yaml` in the `$FACTORY_HOME` files and gives the new poll interval rule.
