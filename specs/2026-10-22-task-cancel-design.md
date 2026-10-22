# Task cancel and merged branch check: design

Date: 2026-10-22
Source: `prompts/factory_task_cancel.md`. Full factory requirements: `prompts/factory_skill_creation.md` (Task delete, Task cancel, Exclusive steps, External waiting).
Code: `software-factory/`. Branch: `task-cancel`, from `master`.

## Intent

- The user cannot stop an unfinished task from the dashboard. `factory delete` keeps an unpushed branch and asks a second approval. The user wants one action that drops a task fully.
- Clean and delete disagree on squash merged branches. The user often deletes local branches by hand after a squash merge.
- Success: one red "Cancel" button per unfinished card, one confirmation, and the task is gone: session, terminal, worktree, local branch, task folder moved to the archive. Clean, delete and cancel agree on what "merged" means.

## Goals

- G1. One merge function, used by Clean, delete and cancel, that finds squash merges also after a later change of the same lines (patch id).
- G2. `factory cancel <id> [--dry-run]`, built on the delete code.
- G3. Dashboard Cancel button and dialog, with two API routes.
- G4. Delete and cancel never ignore an error, and never recreate an archived task folder.

## Non-goals

- No change to the data format version. `cancelled` exists only in archived task state.
- Never delete a remote branch. Never close a merge request.
- No change to the README tutorial.
- No cleanup or refactor outside the parts named here.

## Anti-goals

- Losing work the user did not see in the dry run.
- A cancel that starts a new Claude session for the task it cancels.
- A task folder that comes back after the archive.

## Part 1: merged branch check (milestone 1)

### Branch of a task (`delete.task_branch`)

1. When the worktree folder exists and is on a branch: that branch. The worktree is the truth. The task state can be stale if the session switched branches.
2. Otherwise (worktree gone, or detached HEAD): the task state `branch`.
3. Otherwise: no branch.

### Merge function (`delete.merge_state(ctx, branch, base_ref)`)

Returns `merged`, `reason` and `by_content`. Checks in this order, all run in the main repository on `refs/heads/<branch>` and `refs/remotes/origin/<base_ref>`:

| # | Check | Reason | by_content |
|---|---|---|---|
| 1 | No branch | `no branch` | no |
| 2 | Branch is an ancestor of `origin/<base_ref>` | `merged into origin/<base_ref>` | yes |
| 3 | `git merge-tree --write-tree` gives the tree of `origin/<base_ref>` | `merged (squash)` | yes |
| 4 | Patch id match (below) | `merged (squash)` | yes |
| 5 | Branch tracks its own remote branch, and that remote branch is gone | `pushed, and its remote branch was deleted` | no |
| 6 | None of the above | `not merged` | no |

Patch id check:
- `<merge-base>` = `git merge-base refs/heads/<branch> origin/<base_ref>`.
- Branch patch id: `git diff <merge-base> refs/heads/<branch> | git patch-id --stable`.
- An empty branch diff gives no patch id, and never matches.
- `<files>` = `git diff --name-only -z <merge-base> refs/heads/<branch>`.
- Base patch ids: `git log -p --no-merges <merge-base>..origin/<base_ref> -- <files>`, piped to `git patch-id --stable`.
- Match when one base patch id equals the branch patch id.
- A local commit added after the squash changes the branch patch id, so its work is never hidden.

Clean (`clean_report`) uses this function, so it shows "merged (squash)" for case 4, and still selects case 5.

### Delete plan (`delete.plan_delete`)

- Uncommitted changes: `git status --porcelain` in the worktree, only when the worktree exists.
- Commits not on `origin`: as today. In the worktree, `git log <upstream>..HEAD`, with `<upstream>` = `origin/<branch>` when it exists, else `origin/<base_ref>`. When the worktree is gone, the same `git log` runs in the main repository on `refs/heads/<branch>`.
- Merged by content (rows 2 to 4 only): no commits listed, no `--confirm-unpushed` needed, and the local branch is deleted.
- Row 1 (no branch) counts as merged for Clean, but not by content. A worktree in detached HEAD can have commits that were never pushed. The delete lists them and needs `--confirm-unpushed`.
- Row 5 alone: the commits are listed, the delete needs `--confirm-unpushed`, and after approval the worktree is removed and the branch is kept.
- The existing plan keys stay (`squash_merged`, `delete_branch`, `needs_confirm`, `unpushed`, `uncommitted`, `check_errors`), so the Clean dialog keeps working. `squash_merged` is true for rows 3 and 4.

### Failure rules (delete and cancel)

- Terminal close fails: stop before any change, report the error. The task stays.
- A close of a tab or session that is already gone is a success.
  - Herdr adapter: `close` fails only when a `herdr tab close` or `herdr workspace close` command fails and the tab or workspace still exists. When the `herdr` binary cannot run, `close` fails.
  - A paused task has no terminal handle, so its close never calls the adapter.
  - Fake adapter: a config flag makes `close` fail, for tests.
- A later part fails (worktree remove, branch delete): go on with the other parts, still archive, then fail with the list of what is left, for example "The branch `<branch>` was not deleted: `<git error>`."

### Test change

`tests/test_squash_merge.py::test_later_change_of_same_lines_is_not_merged` checked the old bug. It now expects "merged (squash)", and is renamed to match. The user approved this.

## Part 2: `factory cancel` in the CLI (milestone 2)

### Command

- `factory cancel <id> [--dry-run] [--json]`. It does not use Claude.
- A `finished` task is refused: "The task is finished. Use Clean or `factory delete <id>`."
- Every other status works: also `paused`, session gone, worktree folder gone.

### Differences with delete

- The local branch is always deleted (`git branch -D`), also when not pushed or merged.
- No `--confirm-unpushed`. The user confirms once, after the dry run.
- Event `task_cancelled`, not `task_deleted`.
- The archived `task.json` has `status: cancelled`.
- A remote branch is never deleted.

### Dry run

`factory cancel <id> --dry-run` changes nothing and prints:
- What it removes: the Claude session and its terminal, the worktree, the local branch, the move of the task folder to the archive.
- "Uncommitted changes (saved as a commit you can restore):", with the uncommitted changes, when there are any. They are not lost, because step 4 saves them.
- "Lost work:", with the commits not on `origin`, when there are any, and the line that the branch can be restored with `git branch <branch> <commit>`. None for a branch merged by content.
- When `origin/<branch>` exists or `mr_url` is set: "The remote branch and the merge request stay open. Close them by hand.", with `mr_url`.

The dry run fetches `origin`, like the delete dry run.

### Run order

The cancel and the delete share one removal function. Order, as the user set it:

1. Wait for `.factory/tasks/<id>/check.lock` and hold it. `factory poll` takes it without waiting (`fsio.try_locked`), so a running check ends first, and no check starts during the cancel. This stops a check that ends after the close from resuming the session.
2. Run the checks again. Never trust the dry run result.
3. Close the terminal. If it fails, stop before any change.
4. Cancel only: save the uncommitted changes. In the worktree, `git add -A`, then `git stash create "factory cancel <id>"`. This makes a commit that no branch points to. It includes new files and does not change the stash list. Skipped when the worktree is gone or has no uncommitted changes. If it fails, stop and report the error: keep the worktree, the branch and the task, with no archive. The terminal is already closed, and a close of a gone terminal is a success, so a new cancel works.
5. Remove the worktree (`git worktree remove --force`, then `git worktree prune`).
6. Delete the local branch.
7. Cancel only: set the status to `cancelled` and log `task_cancelled`. Delete: log `task_deleted`.
8. Move the folder to `.factory/tasks/archive/<id>/` (with a date suffix when taken, as today).
9. Release the lock.
10. Release the exclusive resource and leave every queue (`exclusive.forget`). The task that waited the longest and is not paused gets the resource.
11. When parts are left from steps 5 or 6: fail with the list.

After a cancel, the CLI prints:
- The deleted branch and its last commit: "Restore it with `git branch <branch> <commit>`."
- When step 4 saved changes: "Uncommitted changes saved in <commit>: `git stash apply <commit>`."

With these two lines, no work is lost, whatever the session does between the dry run and the click. No fingerprint, no new CLI option, no API field. The user chose this.

### No folder recreated after the archive

- Today `events.log` calls `fsio.append_line`, and `fsio.append_line`, `fsio.locked` and `fsio.atomic_write_text` create missing parent folders. So an event or a state write after the archive recreates the task folder.
- New rule: writes inside a task folder never create it. `events.log`, `state.update` and the task locks (`check`, `rename`) use a mode of the `fsio` helpers that does not create the parent folder.
- `events.log` for a task whose folder is gone writes nothing and does not fail.
- `state.update` for a task whose folder is gone fails with "Unknown task <id>.", also when the folder goes away during the call.
- Hooks (`hook stop`, `hook prompt`, `hook notify-later`) for a task that is not found exit 0 and write nothing. This already holds: they find tasks from the task list, which skips the archive.
- `factory poll --task <id>` for a cancelled task stops on "Unknown task" before it opens the lock, and writes nothing.
- A background job of the task that ends after the cancel (Pause, Check now, Send prompt with wait) changes nothing. Its writes fail on "Unknown task" or are skipped.

## Part 3: dashboard (milestone 3)

### API

- `POST /api/tasks/<id>/cancel/dry-run`: the cancel plan, from the same function as `factory cancel --dry-run`.
- `POST /api/tasks/<id>/cancel`: the cancel, from the same function as `factory cancel`.
- Both need the token, like every route.
- When parts are left after the archive, the error reply also says the task is archived and lists the parts, so the page can remove the card.

### Card and dialog

- Each card not in the Done column has a red "Cancel" button. Done cards keep Clean.
- The button stays enabled when the terminal check fails. A disabled button would hide why the cancel is not possible. A failed close then shows its error in the dialog.
- A click opens a dialog in the page, never `confirm()`:
  - "Loading…" while the dry run runs.
  - Then the dry run text.
  - Buttons "Cancel task" (red) and "Keep task". The word "Cancel" alone is never used in this dialog.
  - "Cancel task" is disabled until the dry run is shown.
  - Escape and a click outside do the same as "Keep task".
  - During the cancel: "Cancelling…" on the button, both buttons disabled.
- After the cancel: the card is removed at once, without waiting for the 5 second refresh. It does not come back.
- Failure before the archive: the dialog shows the error, the card stays.
- Parts left after the archive: the card is removed, the dialog stays open with the list.

### Documentation

- README commands: `factory cancel <id> [--dry-run]`.
- README dashboard reference: the Cancel button and its dialog.
- README Clean paragraph: rewritten for the new merged branch check, with the patch id case and the "remote branch deleted" rule.
- README menu actions: unchanged, except where they describe the merge check.
- README tutorial: unchanged. Simple English, short sentences.

## Verification

- Tests follow the existing setup: `tests/conftest.py`, a test repository with a local bare `origin` under `verification/software-factory/work/`, the fake adapter. Never a real `.factory/`.
- New tests cover every CLI test bullet of the prompt Verification section.
- The full suite runs after each milestone. Baseline before the work: 617 passed.
- Report: `verification/software-factory/task-cancel-report.md`, one section per milestone, plus the full suite result.
- Manual browser check list: `verification/software-factory/task-cancel-manual-check.md`.

## Calls I made (builder may change only with a reason)

- C1. The merge function returns `by_content` next to the reason, so delete and cancel decide from one value. Only rows 2 to 4 set it. (User confirmed for row 1.)
- C2. Delete also takes `check.lock` and follows the same run order, because both share one removal function.
- C3. Parts left after the archive are reported as a failure (CLI exit 1). The API error reply carries `archived: true` and the list.
- C4. `factory poll --task <id>` for a missing task keeps its current "Unknown task" error and exit code 1. It writes nothing. Hooks exit 0.
- C5. `cancelled` is not added to the live status list. It appears only in archived task state.
- C6. The Herdr close checks that the tab or workspace still exists only when the close command fails.
- C7. A task state branch that no longer exists locally (deleted by hand) counts as "no branch": nothing to delete, no failure. (User approved.)
- C8. When a resume starts a new session and then finds the task archived (its state write fails on "Unknown task"), it closes the session it just started. This covers Resume, Send prompt and the exclusive handover, without a new lock. (User approved.)
- C9. The Herdr close stops a delete or cancel only when the task's own tab or workspace cannot be closed. A failed close of an extra workspace is listed in the parts left. (User approved.)
- C10. When saving the uncommitted changes (step 4) fails, the cancel stops and reports the error. The worktree, the branch and the task stay, with no archive. A kept worktree would make the branch delete fail anyway. (User decided.)
- C11. The saved commit is not reachable from any ref, so `git gc` can prune it after its expiry time (2 weeks by default). The README says so.

## Left to the builder

- Names of new helpers and of the `fsio` "do not create" parameter.
- How tests make `git branch -D` fail and how the fake adapter simulates a gone terminal.
- The exact text layout of the dry run, within the content listed above.
