# Workspaces without git

Source: user request in the session of 2026-11-20.

## Intent

Today the factory runs only in a git repository. Each task runs in its own git worktree, and the workspace is found with git. The user wants to add folders that are not in git as workspaces. A pipeline then says if its tasks need a worktree.

## Terms

- Worktree pipeline: a pipeline with `worktree: true`. Each task gets its own git worktree, as today.
- Folder pipeline: a pipeline with `worktree: false`. The task runs in the workspace root folder. It has no worktree and no branch.
- Git workspace: a workspace whose root folder is in a git repository.
- Plain workspace: a workspace whose root folder is not in a git repository.
- Workspace root: the main repository root for a git workspace. The folder that holds `.factory/` for a plain workspace.

## Goals

1. A user can add a folder that is not in git as a workspace, and init the factory in it. This also works on a machine where the `git` program is not installed.
2. Every pipeline has the key `worktree`, with the value `true` or `false`. The key has no default.
3. Folder pipelines run in the workspace root, in git workspaces and in plain workspaces.
4. Worktree pipelines run as today in git workspaces.
5. The data version changes from `2` to `3`. The migration adds `worktree: true` to existing pipelines.

## Non-goals

- A lock that lets only one folder-pipeline task run at a time. The user is in charge of this. Two folder-pipeline tasks in one workspace can change the same files.
- A warning when a folder pipeline edits the main checkout of a git workspace. This is the choice of the user.
- Any other way to isolate tasks in a plain workspace (folder copies, snapshots).
- Semantic version numbers (for example `2.0.1`) for the data version. The data version stays an integer.

## Anti-goals

- A pipeline without the `worktree` key launches. The value must be explicit.
- A change of behavior for existing worktree pipelines in git workspaces. The one accepted exception is `quick-task`, which becomes a folder pipeline (D1).
- A folder-pipeline session whose `factory` commands without `--task` find another task, or no task. An explicit `--task` still wins, as today.

## Approaches

1. A required `worktree` key on each pipeline (chosen by the user). The pipeline author decides. One workspace can have both kinds of pipeline.
2. A `worktree` setting per workspace. This is simpler, but a git workspace cannot mix quick in-place tasks and isolated tasks.
3. Detect git and use worktrees only when git is present. There is no explicit choice, and a git workspace cannot run a task in place.

## Decisions

### D1. Data version 3

- `DATA_VERSION` changes from `2` to `3` (`lib/factory/version.py`).
- The user asked for `v2.0.1`. The data version is an integer. The migration engine loads `N-to-N+1.py` and compares versions with `<` and `>`. Version `3` needs no engine change.
- New script `migrations/2-to-3.py`, with the same entry points as `1-to-2.py`: `check_repo`, `check_library`, `migrate_repo`, `migrate_library`.
- `migrate_repo` and `migrate_library` add `worktree: true` to each `pipelines/*.yaml` file that has no `worktree` key. They keep the other keys and their order.
- The `check_*` functions report a pipeline file that has a `worktree` value that is not `true` or `false`. A file that cannot be parsed is reported.
- `builtin/pipelines/*.yaml` and `catalog/pipelines/*.yaml` ship with the code. They are edited by hand in the same change. `quick-task` gets `worktree: false`. Nobody uses it yet, so the change has no impact. `plan-and-build` gets `worktree: true`, because it runs `commit`, `push` and `create-pr`. Each other shipped pipeline gets the value that fits its steps.

### D2. The `worktree` pipeline key

- `pipeline_check` gives an error when `worktree` is missing, or when it is not a boolean.
- A folder pipeline gives an error when:
  - it lists `create-worktree`;
  - it has a `branch` input.
- A folder pipeline gives a warning for each step with `category: git` (`commit`, `push`, `rebase`, and others).
- In a plain workspace, launch of a worktree pipeline fails: "This workspace is not in a git repository. The pipeline `<id>` needs a worktree. Set `worktree: false`, or use a git workspace."
- The pipeline editor (`pipeline_store.py`, the `edit-pipeline` built-in step, `editor.html`) reads and writes the key. A new pipeline has no value until the user picks one.

### D3. Workspace root

- `repo.main_repo` keeps the git lookup when the folder is in git.
- When git fails, the factory walks up from the folder to the first folder that has `.factory/factory.yaml`. That folder is the workspace root.
- When no such folder exists (a new plain workspace before init), the given folder is the workspace root.
- `workspaces.resolve_main` and `repo.load_ctx` use this lookup.

### D4. Init

- The `git` prerequisite is not required. In a plain workspace, the init report shows "This folder is not in a git repository. Only pipelines with `worktree: false` can run."
- `add_excludes` runs only in a git workspace.
- The no-remote message shows only in a git workspace.

### D5. Launch

For a folder pipeline:

- `plan_worktree` and `create_worktree` do not run.
- `worktree_root` and `base_ref` are not required.
- `Registry.expand` does not add `create-worktree`, and `position` starts at `0`.
- The task has `worktree: null`, `base_ref: null` and no branch.
- No `fetch` runs.
- The rollback has no worktree or branch to remove.

### D6. Session

- A task with `worktree: null` is a folder task. Launch always sets a path for a worktree task, and no code sets it back to `null`. So the kind of a task cannot change after launch, and v2 tasks need no migration.
- `session.start` passes `task["worktree"]` directly today (`lib/factory/session.py:57-59`). It changes to use `engine.task_cwd`, which falls back to `ctx.main`.
- `session.start` keeps an error only when `worktree` is set but the folder is missing.

### D7. Task lookup

- In a folder-pipeline session, the folder does not identify the task. `current_task_id` needs `FACTORY_TASK` or `--task`.
- Step bodies call `factory state get`, `factory done` and others without `--task`. A prompt change cannot fix all of them.
- Every session gets `FACTORY_TASK=<id>` in its environment. The factory writes a per-task Claude settings file with an `env` entry and the content of `.factory/claude-settings.json`, and passes it with `--settings`. `session.start` writes this file again at each start and resume, so that changes to `.factory/claude-settings.json` reach running tasks. The builder confirms that the Claude `env` setting reaches Bash commands. If it does not, the builder reports it before a fallback is chosen.
- The factory writes the per-task settings file for every task, worktree tasks and folder tasks, so the code has one path. For a worktree task, `FACTORY_TASK` and the lookup by folder give the same task.
- The hooks find their task by `session_id` (`attention.find_task`), not by folder. Only the Bash commands of the session need `FACTORY_TASK`.

### D8. Herdr adapter

- `HerdrAdapter.start_session` calls `herdr worktree open`, which needs a git checkout. `main_repo_workspace_ids` and `has_linked_workspaces` read git worktree data from Herdr.
- For a folder-pipeline task, the adapter opens a new tab in a Herdr workspace for the workspace root (`tab create --cwd <root>`). The builder finds the Herdr command that finds or creates that workspace for a plain folder.
- The handle of a folder task stores only `tab`, never the Herdr `workspace` id. `close_own` closes the whole workspace when the task tab is the last tab, and that workspace belongs to the user. The existing `already_open` path (`lib/factory/adapters/herdr.py:79`) already stores only the tab.
- Worktree tasks keep the current path.

### D9. Delete

For a task without a worktree:

- No check for uncommitted, unpushed or detached commits.
- No `git worktree remove`, no `git worktree prune`, no branch delete.
- Delete closes the terminal and archives the task folder.

### D10. Migrate and step delete

- `migrate.require_clean_library` runs only when `library.in_git(lib)` is true.
- `step_delete.tracked` returns an empty list when the library is not in git.

### D11. Dashboard and API

- The add-workspace flow accepts a plain folder.
- In a plain workspace, the launch popup shows worktree pipelines as not available, with the reason. They cannot launch there.
- The launch popup shows no worktree and no branch for a folder pipeline. It does not ask for `worktree_root` or `base_ref`.
- The task details and the board show nothing for an empty `worktree` and `branch`.
- The settings popup shows the "Built-in step settings" for `create-worktree` only in a git workspace.

### D12. Machines without git

The user decided this on 2026-11-20. The factory must run when the `git` program is not installed.

- `repo.git` turns a missing `git` program (`FileNotFoundError`) into a `FactoryError`: "The `git` program is not installed."
- A new function `repo.git_installed()` tells if the program exists.
- Calls that only ask "is this in git?" treat a missing program as "not in git": `main_repo` (D3), `has_origin`, `library.in_git`, `step_delete.tracked`, `init.add_excludes`, `current_task_id`, and the Herdr adapter lookups.
- In a plain workspace with no `FACTORY_TASK` and no `--task`, `current_task_id` shows the existing message "Cannot find the task for this folder. Add --task <id> to the command." It does not show a git error.
- Calls that need git for a worktree task (launch of a worktree pipeline, delete of a worktree task) fail with the `FactoryError` above.
- Every module that calls `repo.git` is checked for this case.

### D13. Step text for folder pipelines

The user decided this on 2026-11-20. Keep `target: worktree` in `user-validation`. The migration does not touch it.

- `user-validation`: with git, summarize the diff, as today. Without git, list the files that the task changed and summarize them.
- Limit: without git, nothing records the changed files. The agent lists them from its own context. After a resume or a context compaction, the list can be incomplete.
- `implement`: "Implement the request in this worktree" changes to text that fits a worktree and a plain folder.
- The builder checks the other built-in and catalog steps for text that assumes a worktree. Steps with `category: git` keep their text. D2 already warns about them.
- With this change, `quick-task` ships with `worktree: false` (D1).

### D14. Tests and docs

- Tests for: the migration; the pipeline checks of D2; a plain workspace add, init, launch and delete; a folder pipeline in a git workspace; the `FACTORY_TASK` lookup; a run with no `git` program on `PATH`.
- README: the `worktree` key, plain workspaces, and that the user is in charge of parallel folder-pipeline tasks.

## Left to the builder

- The order of the work and the file layout of the changes.
- The Herdr commands for D8.
- The test fixtures for a plain workspace in `verification/software-factory/`.
