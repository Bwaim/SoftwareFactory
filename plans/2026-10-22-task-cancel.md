# Task Cancel and Merged Branch Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `factory cancel` (CLI and dashboard) and make Clean, delete and cancel share one merged branch check that finds squash merges by patch id.

**Architecture:** All removal logic stays in `lib/factory/delete.py`: one merge function, one plan function per mode, one removal function with a fixed run order shared by delete and cancel. `fsio` gets a "do not create the parent folder" mode used for every write inside a task folder. The server adds two routes that call the same functions as the CLI. The dashboard adds a card button and an in-page dialog.

**Tech Stack:** Python 3 (stdlib + pyyaml), git CLI, pytest, plain HTML/CSS/JS.

**Spec:** `specs/2026-10-22-task-cancel-design.md`. Requirements: `prompts/factory_task_cancel.md`. Read both.

## Global Constraints

- All code changes stay in `software-factory/`. Verification files go in `verification/software-factory/`.
- Work on branch `task-cancel`, created from `master`. Save `git rev-parse master` before. `master` must not change.
- Never touch a real `.factory/`, a real branch, or a Herdr tab you did not create. Tests use the `inited` / `origin_repo` fixtures of `tests/conftest.py` and the fake adapter.
- No code comments. Match the style of the surrounding code (short functions, no docstrings).
- Commit messages: short, plain. Never add a `Co-Authored-By` line.
- Data format version does not change. `cancelled` appears only in archived `task.json`.
- Never delete a remote branch.
- Run tests from `software-factory/` with `uv run --with pytest --with pyyaml pytest -q <paths>`. Full suite: `... pytest -q tests` (about 9 minutes, baseline 617 passed).
- Exact texts:
  - Refusal: `The task is finished. Use Clean or `factory delete <id>`.`
  - Warning: `The remote branch and the merge request stay open. Close them by hand.`
  - Dry run headings: `Uncommitted changes (saved as a commit you can restore):` and `Lost work:`
  - Branch left: `The branch <branch> was not deleted: <git error>`
  - Restore lines: `Restore it with `git branch <branch> <commit>`.` and `Uncommitted changes saved in <commit>: `git stash apply <commit>`.`
  - Clean reasons: `no branch`, `merged into origin/<base_ref>`, `merged (squash)`, `pushed, and its remote branch was deleted`, `not merged`.
  - Dashboard: button `Cancel` (red, class `danger`), dialog buttons `Cancel task` (red) and `Keep task`, `Loading…`, `Cancelling…`.

## Review Focus

1. A branch that changes a file whose name has a space: the patch id check must still match (use `-z` names as pathspecs). Test in Task 1.
2. `origin/<base_ref>` missing or no merge base: the patch id check returns no match, never raises. Test in Task 1.
3. A task with no worktree path and no terminal handle (a broken launch): cancel still archives it. Test in Task 5.
4. Cancel run twice on the same id: the second fails with "Unknown task" and recreates nothing. Test in Task 6.
5. A branch name with a slash (`feat/x`) across all checks and `git branch -D`. Covered by tests that use `feat/...` names in every task.

---

## Milestone 1: Fix the merged branch check

### Task 1: One merge function with the patch id check

**Files:**
- Modify: `software-factory/lib/factory/delete.py` (`merge_state`, `task_branch`, `clean_report`; add `patch_id_merged`)
- Modify: `software-factory/tests/test_squash_merge.py` (rename and flip `test_later_change_of_same_lines_is_not_merged`)
- Create: `software-factory/tests/test_merge_check.py`

**Interfaces:**
- Produces:
  - `delete.patch_id_merged(ctx, branch: str, base_ref: str) -> bool`
  - `delete.merge_state(ctx, branch: str | None, base_ref: str) -> tuple[bool, str, bool]` returning `(merged, reason, by_content)`. Rows, in order: no branch `(True, "no branch", False)`; ancestor `(True, "merged into origin/<base_ref>", True)`; merge-tree `(True, "merged (squash)", True)`; patch id `(True, "merged (squash)", True)`; own remote branch gone `(True, "pushed, and its remote branch was deleted", False)`; else `(False, "not merged", False)`.
  - `delete.task_branch(ctx, task: dict) -> str | None`: worktree branch when the worktree exists and is on a branch; else `task["state"]["branch"]`; returns `None` when that name has no `refs/heads/<name>` in the main repository (spec C7).
  - `clean_report` rows keep their keys; `reason` comes from `merge_state`.

- [ ] **Step 1: Write the failing tests** in `tests/test_merge_check.py`, reusing the helpers of `tests/test_squash_merge.py` (`env` fixture, `task_with_commit`, `squash_into_main`, `finish`; import them or copy the fixture). Tests:
  - `test_patch_id_finds_squash_after_later_change`: branch changes `README.md` to `branch\n`, squash into main with remote deleted, then main commits `README.md` = `main later\n`. `delete.merge_state(ctx, "feat/x", "main") == (True, "merged (squash)", True)` and `inited.factory.json("clean")` row reason is `merged (squash)`.
  - `test_empty_branch_diff_is_not_patch_merged`: launch on `feat/empty`, no commit, push it, add an unrelated commit on main. `delete.patch_id_merged(ctx, "feat/empty", "main") is False`.
  - `test_commit_on_other_files_is_ignored`: branch changes `a.txt`; main gets a commit on `b.txt` only. `patch_id_merged` is `False`.
  - `test_file_name_with_space`: branch changes `a b.txt`, squash merged, later main change of `a b.txt`. `patch_id_merged` is `True`.
  - `test_missing_base_is_no_match`: `patch_id_merged(ctx, "feat/x", "no-such-base") is False` and does not raise.
  - `test_task_branch_prefers_worktree`: task state `branch` = `old`, worktree on `feat/real`: `task_branch(ctx, task) == "feat/real"`.
  - `test_task_branch_uses_state_when_worktree_gone_or_detached`: remove the worktree by hand: returns state branch. Detach HEAD in a worktree: returns state branch.
  - `test_task_branch_missing_local_ref_is_none`: state `branch` = `feat/deleted`, no such local branch, worktree gone: `None`; `merge_state(ctx, None, "main")[1] == "no branch"`.
  - `test_remote_deleted_without_merge_is_not_by_content`: branch pushed with `-u`, remote branch deleted, never merged: `merge_state` returns `(True, "pushed, and its remote branch was deleted", False)`.
- [ ] **Step 2: In `tests/test_squash_merge.py`**, rename `test_later_change_of_same_lines_is_not_merged` to `test_later_change_of_same_lines_is_merged_by_patch_id` and assert `rows[tid]["merged"] and rows[tid]["reason"] == "merged (squash)"`.
- [ ] **Step 3: Run** `uv run --with pytest --with pyyaml pytest -q tests/test_merge_check.py tests/test_squash_merge.py`. Expected: the new tests and the flipped test FAIL.
- [ ] **Step 4: Implement** `patch_id_merged`, the new `merge_state`, `task_branch(ctx, task)` and update `clean_report`. Patch id algorithm (all in `ctx.main`, all `check=False`, any failure means `False`):
  - `mb = git merge-base refs/heads/<branch> refs/remotes/origin/<base_ref>`.
  - `files = git diff --name-only -z <mb> refs/heads/<branch>` split on `\0`, empty items dropped. No files: `False`.
  - Branch id: run `git diff <mb> refs/heads/<branch>` and feed its stdout to `git patch-id --stable` (stdin via `subprocess.run(input=...)`; add an `input` parameter to `repo.git` if needed). First field of the first line. Empty: `False`.
  - Base ids: `git log -p --no-merges <mb>..refs/remotes/origin/<base_ref> -- <files...>` piped the same way. Each output line is `<patch-id> <commit>`. Match when the branch id is in the set.
- [ ] **Step 5: Run** the same command. Expected: PASS. Also run `tests/test_clean.py`. Expected: PASS.
- [ ] **Step 6: Commit** `Merged branch check: patch id, one merge function`.

### Task 2: Delete plan uses the merge function

**Files:**
- Modify: `software-factory/lib/factory/delete.py` (`plan_delete`, `render_plan`; drop `branch_merged_or_pushed` if unused)
- Test: `software-factory/tests/test_merge_check.py`

**Interfaces:**
- Consumes: Task 1 `merge_state`, `task_branch`.
- Produces: `delete.plan_delete(ctx, tid) -> dict` with the existing keys (`task_id, session_id, terminal_handle, worktree, branch, base_ref, uncommitted, unpushed, squash_merged, delete_branch, needs_confirm, check_errors`) plus `reason: str` and `by_content: bool`. Also a helper `delete.lost_commits(ctx, worktree, branch, base_ref, errors) -> list[str]` used by Task 5.

Rules (spec, Part 1 "Delete plan"):
- `uncommitted`: `git status --porcelain` only when the worktree exists.
- `lost_commits`: worktree exists: `git log --oneline <upstream>..HEAD` in the worktree, `<upstream>` = `origin/<branch>` if that ref exists, else `origin/<base_ref>`. Worktree gone and branch set: same `git log` in `ctx.main` on `refs/heads/<branch>`. Neither: `[]`.
- `by_content` true: `unpushed = []`, `delete_branch = True` (when branch set), `squash_merged = reason == "merged (squash)"`.
- Otherwise: `unpushed` listed. `delete_branch` only when there are no errors, no unpushed commits and the branch is an ancestor of `origin/<branch>` (pushed). Row 5 keeps the branch.
- `needs_confirm = bool(uncommitted or unpushed or check_errors)`. `git fetch origin --prune` runs once, always (also when the worktree is gone).

- [ ] **Step 1: Write the failing tests** in `tests/test_merge_check.py`:
  - `test_delete_removes_squash_merged_branch_after_later_change`: same setup as the patch id test, task not finished. `plan_delete` has `unpushed == []`, `not needs_confirm`, `delete_branch`; `delete.delete(ctx, tid)` without confirm; `git branch --list feat/x` is empty.
  - `test_local_commit_after_squash_is_lost_work`: then add a local commit `late work`. `plan_delete`: `needs_confirm`, `late work` in `unpushed`, `not delete_branch`; `delete.delete(ctx, tid)` raises `FactoryError` matching `--confirm-unpushed`.
  - `test_worktree_removed_by_hand_squash_branch_is_deleted`: squash merged, `git worktree remove --force` by hand, then `delete.delete(ctx, tid)`; branch gone.
  - `test_remote_deleted_without_merge_asks_and_keeps_branch`: pushed, remote deleted, not merged, finished. Clean row `selected` is true; `plan_delete` lists the commit and `needs_confirm`; `delete.delete(ctx, tid, confirm_unpushed=True)` removes the worktree and the branch still exists.
  - `test_detached_worktree_commits_are_listed`: task from a pipeline without `branch` input (detached HEAD), one local commit: `plan_delete` lists it and `needs_confirm`.
- [ ] **Step 2: Run** `uv run --with pytest --with pyyaml pytest -q tests/test_merge_check.py`. Expected: new tests FAIL.
- [ ] **Step 3: Implement** the rules above in `plan_delete`. `render_plan` keeps its texts.
- [ ] **Step 4: Run** `tests/test_merge_check.py tests/test_squash_merge.py tests/test_delete.py tests/test_clean.py`. Expected: PASS.
- [ ] **Step 5: Commit** `Delete plan uses the merge function and the task state branch`.

### Task 3: Failure rules for the terminal close and later parts

**Files:**
- Modify: `software-factory/lib/factory/delete.py` (`close_terminal`, `delete`; add `RemovalIncomplete`)
- Modify: `software-factory/lib/factory/adapters/herdr.py` (`close_own`, `close_extra`, `close`)
- Modify: `software-factory/lib/factory/adapters/fake.py` (`close`; config `on_close`: `{"cwd": <path>, "commands": [[argv...], ...]}` runs these commands with `subprocess.run` before recording the close, so tests can change the worktree "during" the close)
- Modify: `software-factory/tests/fake_herdr.py` (env `FAKE_HERDR_CLOSE_FAILS=1`: `tab close` / `workspace close` exit 1 and the tab stays listed; env `FAKE_HERDR_GONE=1`: tab and workspace lists are empty and close exits 1; env `FAKE_HERDR_LIST_FAILS=1`: close exits 1 and `tab list` / `workspace list` exit 1)
- Modify: `software-factory/lib/factory/server.py` (FactoryError reply carries `details`)
- Test: `software-factory/tests/test_removal_failures.py`, `software-factory/tests/test_herdr_adapter.py`

**Interfaces:**
- Produces:
  - `class delete.RemovalIncomplete(FactoryError)` with attribute `details: dict` = `{"archived": True, "left": [str, ...]}` plus mode fields added in Task 5. Its message is the lines of `left`.
  - `delete.close_terminal(ctx, handle) -> None` raises `FactoryError` on `AdapterError`.
  - `HerdrAdapter.target_state(handle) -> str`: `"present"`, `"gone"` or `"unknown"`. `"gone"` only when a list command worked and the own tab (or workspace) is missing from it. A failed `herdr tab list` or `herdr workspace list` gives `"unknown"`. Do not reuse `tabs()` for this, because it returns `None` both on failure and on a missing tab.
  - `HerdrAdapter.close(handle, stop=True) -> list[str]`: when its own tab or workspace close command fails, it calls `target_state`; `"gone"` is a success, `"present"` and `"unknown"` raise `AdapterError`. Returns a list of problems for extra workspaces that failed to close. `FakeAdapter.close` returns `[]`, and raises `AdapterError("The fake adapter failed to close the terminal.")` when config `fail_close` is true.
  - Server: `except FactoryError as e: reply(400, {"error": str(e), **getattr(e, "details", {})})`.

- [ ] **Step 1: Write the failing tests** in `tests/test_removal_failures.py` (fixture like `started` in `tests/test_delete.py`):
  - `test_close_failure_changes_nothing`: `fake_config(fdir, fail_close=True)`; `delete.delete(ctx, tid, confirm_unpushed=True)` raises `FactoryError` matching `failed to close`; worktree, branch and `tasks/<tid>/task.json` still exist; no `task_deleted` event.
  - `test_gone_terminal_is_success`: fake config `states: {<agent>: "gone"}`; delete works and archives.
  - `test_branch_delete_failure_still_archives`: branch pushed (so it is deleted); create `.git/refs/heads/feat/del.lock` in the main repo; `delete.delete` raises `RemovalIncomplete` with `details["archived"] is True` and a `left` item starting `The branch feat/del was not deleted:`; the folder is in `tasks/archive/`; remove the lock file at the end.
  In `tests/test_herdr_adapter.py`:
  - `test_close_fails_when_tab_stays`: `FAKE_HERDR_CLOSE_FAILS=1`: `adapter.close(handle)` raises `AdapterError`.
  - `test_close_of_gone_tab_is_success`: `FAKE_HERDR_GONE=1`: `adapter.close(handle)` returns without error.
  - `test_close_fails_when_list_fails`: `FAKE_HERDR_LIST_FAILS=1`: `adapter.close(handle)` raises `AdapterError`.
- [ ] **Step 2: Run** `uv run --with pytest --with pyyaml pytest -q tests/test_removal_failures.py tests/test_herdr_adapter.py`. Expected: new tests FAIL.
- [ ] **Step 3: Implement.** `delete.delete` order for now: plan, confirm check, close (stop on error), worktree remove (error to `left`), prune, branch delete (error to `left` with the exact text), `task_deleted` event, archive, `exclusive.forget`, then raise `RemovalIncomplete` when `left` (extra workspace problems from close go in `left` too). Task 5 reorders this into the shared function.
- [ ] **Step 4: Run** the step 2 command plus `tests/test_delete.py tests/test_merge_check.py tests/test_server.py`. Expected: PASS.
- [ ] **Step 5: Full suite and commit.** Run `uv run --with pytest --with pyyaml pytest -q tests`. Expected: all pass. Commit `Delete never ignores a failed close or a part left`. This ends milestone 1.

---

## Milestone 2: Cancel in the CLI

### Task 4: Writes inside a task folder never create it

**Files:**
- Modify: `software-factory/lib/factory/fsio.py`, `events.py`, `state.py`, `engine.py` (`check_task`), `rename.py` (`apply_pending`)
- Test: `software-factory/tests/test_no_recreate.py`

**Interfaces:**
- Produces:
  - `fsio.atomic_write_text(path, text, create=True)`, `fsio.locked(path, create=True)`, `fsio.append_line(path, line, create=True)`, `fsio.update_json(path, fn, default_factory=dict, create=True)`. With `create=False`, a missing parent raises `FileNotFoundError` and nothing is created.
  - `fsio.try_locked(path)` unchanged: a missing parent raises `FileNotFoundError`.
  - `events.log(...)`: uses `create=False`; a missing task folder writes nothing and does not raise.
  - `state.update(...)`: uses `create=False`; `FileNotFoundError` becomes `FactoryError("Unknown task <tid>.")`.
  - `engine.check_task`: `FileNotFoundError` from the lock becomes `FactoryError("Unknown task <tid>.")`.
  - `rename.apply_pending`: `FileNotFoundError` from the lock returns `False`.

- [ ] **Step 1: Write the failing tests** in `tests/test_no_recreate.py`:
  - `test_event_log_for_missing_task_writes_nothing`: `events.log(ctx, "ghost", "x")` returns; `tasks/ghost` does not exist.
  - `test_state_update_after_folder_removed_raises`: create task, then call `state.update` with an `fn` that moves the task folder away (simulates the race); expect `FactoryError` "Unknown task" and the folder not recreated.
  - `test_stop_hook_and_poll_after_delete_do_not_recreate`: task with `session_id="sid-1"`, delete it with `delete.delete`; run `hook(inited, "stop", {"session_id": "sid-1", "last_assistant_message": "hi"})` → `silent(r)`; run `inited.factory("poll", "--task", tid, check=False)`; `tasks/<tid>` does not exist.
- [ ] **Step 2: Run** `uv run --with pytest --with pyyaml pytest -q tests/test_no_recreate.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the interfaces above.
- [ ] **Step 4: Run** `tests/test_no_recreate.py tests/test_fsio.py tests/test_event_log.py tests/test_attention_hooks.py tests/test_check_now.py tests/test_races.py`. Expected: PASS.
- [ ] **Step 5: Commit** `Writes inside a task folder never create it`.

### Task 5: `factory cancel` and its dry run

**Files:**
- Modify: `software-factory/lib/factory/delete.py` (add `plan_cancel`, `render_cancel_plan`, `cancel`, `render_cancel_result`, shared `remove`)
- Modify: `software-factory/lib/factory/commands.py` (parser `cancel <id> [--dry-run]`, command `cancel`)
- Test: `software-factory/tests/test_cancel.py`

**Interfaces:**
- Consumes: Task 2 `plan_delete`, `lost_commits`; Task 3 `RemovalIncomplete`, `close_terminal`.
- Produces:
  - `delete.plan_cancel(ctx, tid) -> dict`: keys `task_id, session_id, terminal_handle, worktree, branch, branch_commit, base_ref, uncommitted, unpushed, check_errors, by_content, reason, remote_branch: bool, mr_url`. Raises `FactoryError` with the exact refusal text for a `finished` task. `unpushed` is `[]` when `by_content`.
  - `delete.render_cancel_plan(plan) -> str`: "Cancel task <id>:" then the removed items (session and terminal, worktree, local branch, folder move); the `Uncommitted changes (saved as a commit you can restore):` block; the `Lost work:` block with the commits and the line "Restore the branch with `git branch <branch> <branch_commit>`."; the remote warning with `mr_url` when `remote_branch` or `mr_url`.
  - `delete.cancel(ctx, tid) -> dict`: `{"task_id", "branch", "branch_commit", "saved_commit", "left": []}`. Raises `RemovalIncomplete` (details also carry `branch`, `branch_commit`, `saved_commit`) when parts are left.
  - `delete.render_cancel_result(result) -> str`: "Task <id> cancelled and archived." plus the two restore lines when they apply.
  - `delete.remove(ctx, tid, mode: str, confirm_unpushed=False) -> dict` with `mode` in `("delete", "cancel")`; `delete.delete` calls it.
  - CLI: `factory cancel <id> [--dry-run] [--json]`. Dry run prints `render_cancel_plan` (or the plan as JSON). Run prints `render_cancel_result`. `RemovalIncomplete` prints `Error: ...` and exits 1, like every `FactoryError`.

Run order inside `remove` (spec, user set it; Task 6 adds the lock as step 1):
2. Plan again (`plan_delete` or `plan_cancel`); delete refuses `needs_confirm` without `confirm_unpushed`.
3. `close_terminal`.
4. Cancel only, worktree exists: always, after the close, in the worktree `git add -A`, then `git stash create "factory cancel <id>"`. Never use `uncommitted` from the step 2 plan: the session can edit files until step 3. Empty stdout means nothing to save (`saved_commit = None`). Otherwise stdout is `saved_commit`. On failure raise `FactoryError` and stop (worktree, branch, task kept).
5. Worktree remove, prune.
6. Branch delete: delete mode when `delete_branch`; cancel mode always when `branch` is set (`git branch -D`). Cancel reads `branch_commit` with `git rev-parse refs/heads/<branch>` just before `git branch -D`, never from the plan: the session can commit until the close.
7. Cancel: `state.update` sets status `cancelled` (via `state.set_status`), then `task_cancelled` event. Delete: `task_deleted` event.
8. Archive move.
10. `exclusive.forget`.
11. `RemovalIncomplete` when `left`.

- [ ] **Step 1: Write the failing tests** in `tests/test_cancel.py` (pipeline with `branch` input, like `tests/test_delete.py`):
  - `test_cancel_removes_everything`: commit on `feat/c` not pushed. `inited.factory("cancel", tid)` succeeds; last fake call op is `close`; worktree gone; `git branch --list feat/c` empty; `tasks/archive/<tid>/task.json` status `cancelled`; last event `task_cancelled`; stdout has `git branch feat/c <sha>` with the old branch head.
  - `test_cancel_saves_uncommitted_changes`: modify a tracked file and add `new.txt`; cancel; stdout has `git stash apply <commit>`; in the main repo `git show <commit> --stat` lists both files; `git stash list` is empty.
  - `test_dry_run_lists_and_changes_nothing`: uncommitted file, unpushed commit, branch pushed earlier, `mr_url` set via `state.set_key`. `factory cancel <tid> --dry-run` output has `Uncommitted changes (saved as a commit you can restore):`, `Lost work:`, the commit subject, the remote warning and the `mr_url`; task folder, worktree and branch unchanged; no new fake adapter call.
  - `test_remote_branch_is_never_deleted`: push branch, cancel; `git ls-remote origin feat/c` still lists it.
  - `test_cancel_paused_task`: `session.pause`, then cancel succeeds without a `close` call after the pause.
  - `test_cancel_gone_session_and_missing_worktree`: fake `states` gone for the agent; remove the worktree by hand; cancel succeeds and the branch is deleted.
  - `test_cancel_task_without_worktree_or_handle`: `make_task(ctx, "bare")` (no worktree, no handle); cancel archives it.
  - `test_finished_task_is_refused`: finish the task; `factory cancel` exits 1 with the exact refusal text.
  - `test_cancel_close_failure_changes_nothing`: `fail_close`; exit 1; task, worktree and branch stay.
  - `test_cancel_branch_delete_failure_still_archives`: ref lock file as in Task 3; exit 1 with `The branch feat/c was not deleted:`; folder archived.
  - `test_change_made_during_close_is_saved`: no change at plan time; fake config `on_close` writes `late.txt` in the worktree (for example `["sh", "-c", "echo late > late.txt"]` with `cwd` = worktree); cancel; the printed saved commit lists `late.txt` in `git show --stat`.
  - `test_commit_made_during_close_is_restore_commit`: fake config `on_close` runs `["sh", "-c", "git commit --allow-empty -m during-close && git rev-parse HEAD > <work>/sha.txt"]` in the worktree; cancel; the restore line commit equals the content of `sha.txt`.
  - `test_stash_failure_stops`: make `git stash create` fail (for example a `.git/worktrees/<name>/index.lock` file in the main repo's git dir); cancel exits 1; worktree, branch and task folder stay.
  - `test_cancelled_task_missing_from_lists`: after cancel, `inited.factory.json("tasks")` has no row with the id.
- [ ] **Step 2: Run** `uv run --with pytest --with pyyaml pytest -q tests/test_cancel.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the interfaces and the run order.
- [ ] **Step 4: Run** `tests/test_cancel.py tests/test_delete.py tests/test_removal_failures.py tests/test_merge_check.py tests/test_squash_merge.py`. Expected: PASS.
- [ ] **Step 5: Commit** `Add factory cancel and its dry run`.

### Task 6: Lock, exclusive release, resume race, no recreate after cancel

**Files:**
- Modify: `software-factory/lib/factory/delete.py` (`remove` takes the check lock)
- Modify: `software-factory/lib/factory/session.py` (`resume`)
- Test: `software-factory/tests/test_cancel_races.py`

**Interfaces:**
- Consumes: Task 4 `fsio.locked(path, create=False)`, Task 5 `remove`.
- Produces:
  - `remove` step 1: `with fsio.locked(state.task_dir(ctx, tid) / "check", create=False):` around steps 2 to 8. Missing folder: `FactoryError("Unknown task <tid>.")`. Steps 10 and 11 run after the lock is released.
  - `session.resume`: when the `state.update` after `start` raises `FactoryError` and the task file no longer exists, close the new handle with the adapter (ignore close errors there) and re-raise.

- [ ] **Step 1: Write the failing tests** in `tests/test_cancel_races.py`:
  - `test_cancel_waits_for_running_check`: hold the lock from a thread with `fsio.try_locked(task_dir / "check")` for 1.5 s; start `delete.cancel` in the main thread; it returns after the holder released (measure time ≥ 1.0 s), and the folder is archived.
  - `test_cancelled_holder_hands_resource_to_next`: two tasks on a step with `exclusive: emu` (see `tests/test_exclusive_flow.py` for setup); task A holds, task B waits; cancel A; `exclusive.read(ctx, "emu")["holder"] == B` and B status `active`.
  - `test_cancelled_waiting_task_leaves_queue`: cancel B while it waits; queue is empty.
  - `test_stop_hook_and_poll_after_cancel_do_not_recreate`: as in Task 4, with `cancel`.
  - `test_second_cancel_fails_cleanly`: cancel twice; second raises `FactoryError` "Unknown task"; `tasks/<tid>` does not exist.
  - `test_resume_after_archive_closes_new_session`: monkeypatch `state.update` in `session` to move the task folder to the archive before raising (or archive the folder from a fake `start` hook), call `session.resume`; expect `FactoryError`, and the fake adapter calls end with `start_session` then `close` of the new handle.
- [ ] **Step 2: Run** `uv run --with pytest --with pyyaml pytest -q tests/test_cancel_races.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the lock in `remove` and the resume guard.
- [ ] **Step 4: Full suite and commit.** Run `uv run --with pytest --with pyyaml pytest -q tests`. Expected: all pass. Commit `Cancel takes the check lock and releases exclusive resources`. This ends milestone 2.

---

## Milestone 3: Cancel in the dashboard

### Task 7: API routes

**Files:**
- Modify: `software-factory/lib/factory/api.py`
- Test: `software-factory/tests/test_cancel_api.py`

**Interfaces:**
- Consumes: Task 5 `plan_cancel`, `render_cancel_plan`, `cancel`, `render_cancel_result`; Task 3 server `details`.
- Produces:
  - `POST /api/tasks/<id>/cancel/dry-run` → `{**plan_cancel(ctx, tid), "text": render_cancel_plan(plan)}`.
  - `POST /api/tasks/<id>/cancel` → `{**cancel(ctx, tid), "text": render_cancel_result(result)}`. `RemovalIncomplete` → 400 with `error`, `archived: true`, `left`.

- [ ] **Step 1: Write the failing tests** (fixture like `dash` in `tests/test_dashboard_api.py`):
  - `test_dry_run_route_matches_cli`: route reply `text` equals `factory cancel <tid> --dry-run` stdout (strip both).
  - `test_cancel_route_archives_and_removes_from_list`: route returns 200; `GET /api/tasks` has no row with the id; archived status `cancelled`.
  - `test_routes_reject_missing_token`: both routes with `token=False` return 401.
  - `test_parts_left_reply`: branch ref lock file; reply 400 with `archived` true and a `left` item.
  - `test_close_failure_reply`: `fail_close`; reply 400 without `archived`; task still listed.
- [ ] **Step 2: Run** `uv run --with pytest --with pyyaml pytest -q tests/test_cancel_api.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the two routes.
- [ ] **Step 4: Run** the same file plus `tests/test_dashboard_api.py tests/test_server.py`. Expected: PASS.
- [ ] **Step 5: Commit** `Dashboard API: cancel and its dry run`.

### Task 8: Card button and dialog

**Files:**
- Modify: `software-factory/lib/factory/web/dashboard.html`
- Modify: `software-factory/tests/test_dashboard_page.py`
- Create: `verification/software-factory/task-cancel-manual-check.md`

**Interfaces:**
- Consumes: Task 7 routes.
- Produces in the page:
  - `api()` attaches the reply body to the thrown error (`err.data`).
  - `state.removed` (a `Set` of task ids). `render` and `refresh` drop tasks in it. An id leaves the set when `/api/tasks` no longer returns it.
  - `openCancel(t)`: `showModal` with title `Cancel task <display name>`, `dismissable: true` (Escape and outside click close it, same as "Keep task"), content `Loading…`, footer buttons `Keep task` and `Cancel task` (class `danger`, disabled). It calls the dry run route, shows `text` in a `pre`, then enables `Cancel task`. On a dry run error it shows the error in the dialog.
  - "Cancel task": both buttons disabled, label `Cancelling…`, POST the cancel route. Success: add id to `state.removed`, close the dialog, `render()`, show `text` nowhere else. Error with `err.data.archived`: add id to `state.removed`, `render()`, dialog stays open with the `left` list and a Close button. Other error: dialog shows the error, buttons enabled again, card stays.
  - In `taskButtons`: when `!finished`, append `button("Cancel", () => openCancel(t), { cls: "danger" })`. Never disabled.
  - The dialog never uses `confirm()`.

- [ ] **Step 1: Write the failing page tests** in `tests/test_dashboard_page.py`:
  - `test_cancel_button_and_dialog`: `PAGE` contains `"Cancel task"`, `"Keep task"`, `"Cancelling…"`, `"Loading…"`, `"/cancel/dry-run"`, `"openCancel"`, `"state.removed"`, and `"confirm("` is not in `PAGE`.
- [ ] **Step 2: Run** `uv run --with pytest --with pyyaml pytest -q tests/test_dashboard_page.py`. Expected: FAIL.
- [ ] **Step 3: Implement** the page changes.
- [ ] **Step 4: Run** the same file. Expected: PASS.
- [ ] **Step 5: Write** `verification/software-factory/task-cancel-manual-check.md`: numbered checks for the user with expected results: red Cancel on each card not in Done, no Cancel on Done cards; dialog shows `Loading…` then the dry run; `Cancel task` disabled until then; `Keep task`, Escape and an outside click close it and keep the card; `Cancel task` shows `Cancelling…`, the card disappears at once and does not come back after 5 s and after a page reload; a failed close (Herdr not running) shows the error and the card stays.
- [ ] **Step 6: Commit** `Dashboard: Cancel button and dialog`.

### Task 9: README

**Files:**
- Modify: `software-factory/README.md`
- Modify: `software-factory/tests/test_docs.py`

- [ ] **Step 1: Write the failing test** `test_readme_describes_cancel` in `tests/test_docs.py`: README contains `factory cancel <id> [--dry-run]`, `**Cancel**`, `Cancel task`, `Keep task`, `patch id`, `git stash apply`, and no longer contains `the task counts as not merged`.
- [ ] **Step 2: Run** `uv run --with pytest --with pyyaml pytest -q tests/test_docs.py`. Expected: FAIL.
- [ ] **Step 3: Edit the README** (simple English, short sentences, tutorial unchanged):
  - Commands, "Task life": `factory cancel <id> [--dry-run]`: what it removes, always deletes the local branch, never a remote one, refuses finished tasks, prints the restore lines.
  - Dashboard "Card buttons": **Cancel** and its dialog.
  - Clean dialog paragraph: the five reasons in order, the patch id case (also after a later change of the same lines), and that "pushed, and its remote branch was deleted" still asks for approval and keeps the branch.
  - One line: the saved uncommitted changes commit is not on any branch, so `git gc` can remove it after about 2 weeks.
- [ ] **Step 4: Run** `tests/test_docs.py`. Expected: PASS (also `test_readme_commands_exist`).
- [ ] **Step 5: Full suite and commit.** Run `uv run --with pytest --with pyyaml pytest -q tests`. Expected: all pass. Commit `README: cancel and the merged branch check`. This ends milestone 3.

### Task 10: Verification report

**Files:**
- Create: `software-factory/tests/report_task_cancel.py` (same shape as `tests/report_pipeline_loop.py`)
- Create: `verification/software-factory/task-cancel-report.md`

- [ ] **Step 1: Write** the report script: runs pytest with `--junitxml` on the full suite, groups cases by milestone (1: `test_merge_check`, `test_squash_merge`, `test_clean`, `test_delete`, `test_removal_failures`, `test_herdr_adapter`; 2: `test_no_recreate`, `test_cancel`, `test_cancel_races`; 3: `test_cancel_api`, `test_dashboard_page`, `test_docs`), and writes one section per milestone with each test and its result, then the full suite totals.
- [ ] **Step 2: Run** it. Expected: report written, all PASS.
- [ ] **Step 3: Check** `git rev-parse master` equals the saved value.
- [ ] **Step 4: Commit** `Task cancel verification report`.
