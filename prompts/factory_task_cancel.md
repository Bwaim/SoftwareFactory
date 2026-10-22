# Software factory: cancel a task, and fix the merged branch check

## Problem

The user cannot stop a task that is not finished from the dashboard. Today the only way is `factory delete` from the menu or the CLI.
`factory delete` keeps a local branch that is not pushed or merged, and asks a second approval for unpushed work. For a task the user wants to drop, this leaves a branch behind and adds steps.
The Done column has a "Clean" button, but the other columns have no way to remove a task.
Clean also has a bug. After a squash merge, the user often deletes the local branch by hand. Two causes, both reproduced with a test:
1. A branch is squash merged, its remote branch is deleted, and a later commit on `origin/main` changes the same lines. Clean shows it as merged: "pushed, and its remote branch was deleted". The delete does not use this reason. Its `git merge-tree` check fails on the later change. So it lists the branch commits as not pushed, asks for `--confirm-unpushed`, and keeps the branch.
2. When the worktree folder is already gone, the delete reads the branch only from the worktree. It finds no branch and never deletes it.

## Solution

Add a "Cancel" button to each task card that is not finished. It does what Clean does for a finished task, with one confirmation:
- Close the Claude session and its terminal
- Delete the worktree
- Delete the local branch
- Move the task folder to the archive

After the cancel, the task is not visible in the dashboard.

Fix the merged branch check, so Clean, delete and cancel use one check, and a squash merged branch is found and deleted.

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
    - The full factory requirements. It already contains the cancel, in Task cancel, and the merged branch fix, in Task delete. Read it for context.

## Workflow

1. Read. Read `MAIN_PROMPT`, `YOUR_WORKING_DIR/README.md` and the factory code, so the feature follows the existing design, modules and tests. Start with `lib/factory/delete.py`, `lib/factory/api.py`, `lib/factory/exclusive.py`, `lib/factory/attention.py` (the hooks), `lib/factory/engine.py` (the check of a waiting task), `lib/factory/fsio.py` and `lib/factory/web/dashboard.html`.
2. Brainstorm. Use the `/superpowers:brainstorming` skill to create a specification file from these requirements. Save the specification file in `SPEC_DIR/` before writing the plan.
3. Ask validation. Ask the user to validate the specification file.
4. Plan. After specification validation, use the `/superpowers:writing-plans` skill to create an implementation plan from the specification file. Save the plan file in `PLAN_DIR/` before writing implementation code. Split the plan into these milestones, in this order:
    1. Fix the merged branch check.
    2. Cancel in the CLI: `factory cancel`, its dry run, the archive status, the event, the lock with `factory poll`, the exclusive release, and no folder recreated after the archive.
    3. Cancel in the dashboard: the server API routes, the card button and its dialog, README.
5. Ask validation. Ask the user to validate the plan file.
6. Build. After plan validation, create the branch `task-cancel` from `master`. Save `git rev-parse master` first, to check at the end that `master` did not change. Use the `/superpowers:subagent-driven-development` skill to implement the plan inside `YOUR_WORKING_DIR`, one milestone at a time. Run the full test suite of the factory after each milestone, fix the failures, and commit before starting the next milestone. Do not skip straight from this prompt to implementation.
7. Verify. Check every item in Definition Of Done, fix failures, and rerun the affected checks. Keep final verification artifacts inside `VERIFICATION_DIR` and report actual results and any remaining blockers.

## Definition Of Done

### Workflow Complete

- Your completed implementation plan exists under `PLAN_DIR/`
    - It was written before implementation, and the build followed its build step.
- The work is on the branch `task-cancel`. `master` is unchanged.
- Every existing test still passes.

### Fix the merged branch check

- Clean, delete and cancel use one function to decide if a branch is merged. A branch merged by content has no lost commits, so the cancel dry run does not list them as lost work.
- A branch also counts as merged (squash) when one commit of `origin/<base_ref>` has the same patch id as the whole branch diff:
  - Branch patch id: `git diff <merge-base> refs/heads/<branch> | git patch-id --stable`, with `<merge-base>` from `git merge-base refs/heads/<branch> origin/<base_ref>`.
  - Patch ids of `origin/<base_ref>`: `git log -p --no-merges <merge-base>..origin/<base_ref> -- <files>`, piped to `git patch-id --stable`. `<files>` are the files the branch changes, from `git diff --name-only -z <merge-base> refs/heads/<branch>`. The squash commit changes exactly these files, so the filter keeps the result and reads far less history.
  - An empty branch diff gives no patch id. It never counts as merged by patch id.
  - This finds a squash merge also after a later change of the same lines. A local commit added after the squash changes the branch patch id, so its work is never lost.
- The patch id check runs after the ancestor check and the `git merge-tree` check, and before the "remote branch deleted" reason. Clean shows "merged (squash)" for it.
- When the branch is merged by content (ancestor, `git merge-tree` or patch id), the delete lists no lost commits, needs no `--confirm-unpushed`, and deletes the local branch.
- "Pushed, and its remote branch was deleted" alone does not prove that the work is merged, for example after a merge request closed without merge. Clean still selects it. The delete still lists its commits and asks for approval. After the approval, it removes the worktree and keeps the branch.
- The delete reads the branch from the task state `branch` when the worktree folder is gone or in detached HEAD. It deletes it with the same rules.
- Today a failed terminal close and a failed branch delete are ignored. When the terminal close fails, the delete stops before any change and reports the error. The task stays, and the user can run it again. A close of a tab or session that is already gone counts as a success, for example for a paused task or a task whose session is gone.
- When a later part fails (worktree remove, branch delete), the delete goes on with the other parts and still archives the task. At the end it fails with the list of what is left, for example "The branch <branch> was not deleted: <git error>", so the user removes it by hand. It never ignores an error.

### Cancel in the CLI

- A task is cancelled with `factory cancel <id> [--dry-run]`. It does not use Claude.
- It reuses the code of `delete-task`, with these differences:
  - It always deletes the local branch, also when it is not pushed or merged. It never deletes a remote branch.
  - It needs no `--confirm-unpushed`. The user confirms the cancel once, after seeing the lost work.
  - It logs `task_cancelled`, not `task_deleted`.
  - The archived task state has the status `cancelled`. The data format version does not change.
- It refuses a `finished` task with: "The task is finished. Use Clean or `factory delete <id>`."
- It works in every other status, also when the task is paused, its session is gone, or its worktree folder no longer exists.
- `factory cancel --dry-run` changes nothing and prints:
  - What it removes: the Claude session and its terminal, the worktree, the local branch, and the move of the task folder to the archive.
  - "Lost work:", with the uncommitted changes and the commits that are not on `origin`, when there are any.
  - When the branch exists on `origin`, or `mr_url` is set: "The remote branch and the merge request stay open. Close them by hand.", with `mr_url`.
- After the cancel, it prints the deleted branch and its last commit, so the user can restore it with `git branch <branch> <commit>`.
- Before it removes the worktree, it saves the uncommitted changes, new files included, as a commit that no branch points to: `git add -A`, then `git stash create "factory cancel <id>"`, in the worktree. This does not change the stash list. It prints the commit, so the user can get the changes back with `git stash apply <commit>`. This covers the edits the session makes between the dry run and the cancel.
- The save and the branch commit in the restore line are read after the terminal close, never from the plan made before it. The session can still edit and commit until it is closed.
- When this save fails, the cancel stops and reports the error. The worktree and the branch stay, and the task stays on the board. The terminal is already closed, so a new cancel works.
- It runs its checks again when it runs, and does not trust the dry run result, because the task can change between the dry run and the confirmation.
- It handles failures like the delete: a failed terminal close stops it before any change, a later failure is reported after the archive.
- It takes the lock that `factory poll` uses for one task: `.factory/tasks/<id>/check.lock`. The check takes it with `fsio.try_locked`, which does not wait. The cancel waits for it as its first action, before the terminal close, and holds it until the folder is moved. Otherwise a check that ends after the close resumes the session (see External waiting in `MAIN_PROMPT`). A check that starts after the move stops on "task not found" before it opens the lock.
- It releases the exclusive resource that the task holds, and the task leaves every waiting queue. The task that waited the longest gets the resource, as when a task leaves the step (see Exclusive steps in `MAIN_PROMPT`).
- Closing the terminal can still run the Claude hooks of the closing session. After the archive, no `factory` command recreates the task folder `.factory/tasks/<id>/`. A hook for a task that is not found exits 0 and writes nothing. A command for it fails with "Unknown task <id>." and writes nothing. The same rule applies to `factory delete`.
  - Today `events.log` calls `fsio.append_line`, and both `fsio.append_line` and `fsio.locked` create missing parent folders. So an event logged after the archive creates the task folder again. Writes inside a task folder must not create it.
- A background job of the task that ends after the cancel, for example Pause or Check now, changes nothing.

### Cancel in the dashboard

- Each card that is not in the Done column has a "Cancel" button, in red. Done cards keep using Clean.
- A click opens a dialog in the page. It shows "Loading…" while the dry run runs, because the dry run fetches `origin`. Then it shows the `factory cancel --dry-run` result. It never uses the browser `confirm()`.
- "Cancel task" is disabled until the dry run result is shown.
- The dialog buttons are "Cancel task", in red, and "Keep task". The dialog does not use the word "Cancel" alone, so the two actions are never confused.
- Escape and a click outside the dialog do the same as "Keep task".
- "Cancel task" runs the cancel. During the cancel, the button shows "Cancelling…" and both buttons are disabled.
- After the cancel, the card is removed at once, without waiting for the 5 second refresh. The task does not come back after a refresh.
- When the cancel fails before the archive, the dialog shows the error and the card stays.
- When some parts are left after the archive, the card is removed and the dialog stays open with the list of what is left.
- The server has one API route for the dry run and one for the cancel. Both call the same function as the CLI. Requests without the token are rejected.

### Documentation

- The README commands and the dashboard reference describe the Cancel button and `factory cancel`.
- The README Clean section describes the new merged branch check, with the patch id case.
- The README tutorial is unchanged.
- The README uses simple English and short sentences.

### Verification

- The build is verified with an automated test run. Its report goes to `VERIFICATION_DIR/task-cancel-report.md`.
- The report has one section per milestone, with the tests run and their results, and the result of the full test suite.
- Test setup: the same as the existing factory tests. A test repository with a local bare `origin`, never a real `.factory/`.
- CLI tests, with the fake adapter, without Herdr or Claude:
  - A branch squash merged into `origin/main`, with its remote branch deleted and a later commit on `origin/main` that changes the same lines: Clean shows "merged (squash)", and the delete removes the local branch with no `--confirm-unpushed`.
  - The same case with a local commit added after the squash: the commit is listed as lost, and the delete asks for approval.
  - A squash merged branch whose worktree folder was removed by hand: the delete removes the local branch.
  - A pushed branch whose remote branch was deleted without a merge: Clean selects it, and the delete lists its commits and asks for approval.
  - A branch with no change against its merge base is not reported as merged by patch id.
  - A commit on `origin/main` that changes other files is ignored by the patch id check.
  - With the fake adapter failing to close the terminal, the delete and the cancel change nothing, report the error, and the task stays. A close of a terminal that is already gone counts as a success.
  - With `git branch -D` failing, the delete and the cancel still archive the task and report the branch that is left.
  - The existing tests in `tests/test_squash_merge.py` and `tests/test_clean.py` still pass, except `test_later_change_of_same_lines_is_not_merged`. It checks the old behavior. Change it to expect "merged (squash)".
  - Cancel closes the terminal with the adapter, removes the worktree, deletes a local branch with unpushed commits, archives the task folder with the status `cancelled`, and logs `task_cancelled`.
  - The task is missing from `factory tasks` and from the dashboard task list API after the cancel.
  - The dry run lists uncommitted changes and unpushed commits, warns about a pushed branch and `mr_url`, and changes nothing.
  - A remote branch is never deleted.
  - Cancel saves uncommitted changes and new files as a commit, prints it, and `git stash apply <commit>` brings them back after the cancel. The stash list is unchanged.
  - Cancel works on a `paused` task, a task whose session is gone (its old terminal handle no longer exists), and a task whose worktree folder was removed by hand.
  - A `finished` task is refused with the message above.
  - A cancelled task that holds an exclusive resource gives it to the next waiting task. A cancelled waiting task leaves the queue.
  - The `Stop` hook and `factory poll`, run for a cancelled task, do not recreate `.factory/tasks/<id>/`.
  - A cancel that starts while a check of the task runs waits for the check to end.
  - The cancel and dry run API routes call the same function as the CLI. Requests without the token are rejected.
  - Every `factory` command written in the README exists in the CLI.
- Manual browser check list in `VERIFICATION_DIR/task-cancel-manual-check.md`, for the user to run:
  - The red "Cancel" button on each card that is not done, and its absence on Done cards.
  - The dialog: "Loading…", the dry run text, the "Cancel task" and "Keep task" buttons, Escape and a click outside.
  - The card disappears after the cancel and does not come back after a refresh.

## How You're Graded

- You'll be graded on a continuous basis based on every completed bullet in the Definition Of Done.
- Every step of Workflow must be fully accomplished: plan, build and verify.
- Instant failure if you write project deliverables outside `YOUR_WORKING_DIR` with the exception of `SPEC_DIR`, `PLAN_DIR` and `VERIFICATION_DIR`.
- Instant failure if you read any part of any file inside `<PROJECT_ROOT>/specs/*` that isn't your own spec.
- Instant failure if you change a real `.factory/` folder or delete a real branch. Tests use test repositories only.
- Instant failure if you close a Herdr workspace, tab, pane or session you did not create.
- Running tools outside these directories is allowed. Temporary files and tool-managed runtime data (caches, logs, browser profiles, updater logs) may use their normal locations and are not grading failures.
- If you find you've mistakenly caused a failure, stop immediately and report your failure.
