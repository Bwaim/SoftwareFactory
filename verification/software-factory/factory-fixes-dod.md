# Factory fixes: Definition Of Done check

Date: 2026-10-16. Branch `factory-fixes`, head `c815ede` before this file. Source: `prompts/factory_fixes.md`.

Full suite: `uv run --with pytest --with pyyaml pytest -q tests` in `software-factory/` gives **478 passed** in 322 s (baseline 416). Report: `factory-fixes-junit.xml`.

## Workflow Complete

| Item | Result | Evidence |
| --- | --- | --- |
| Plan exists under `PLAN_DIR`, written before implementation | PASS | `plans/2026-10-16-factory-fixes.md`, committed in `375ec9c`, the first commit of the branch. All code commits come after it |
| Spec exists under `SPEC_DIR` | PASS | `specs/2026-10-16-factory-fixes-design.md` (same commit) |
| Build followed the build step | PASS | Branch `factory-fixes` from `master`. Subagent-driven development, one milestone at a time, in the plan order. Full suite run and commit after each milestone. Commits: `a4838d3` (1), `4510706` (2), `9eba2ac` (3), `05a9da1` (4), `3f69cfc` (5), `2d36c96` + `df4abf5` (6), `c815ede` (final review fixes) |
| Work is on `factory-fixes`, `master` unchanged | PASS | `git rev-parse master` = `5c3b44e779c0bab597e3cfe3a4f7e235d5bd3da7`, the value saved in `factory-fixes-master-before.txt` before the branch. No `origin/factory-fixes`: nothing was pushed |
| Every existing test still passes, each milestone adds tests | PASS | 478 passed. New files: `test_herdr_names.py`, `test_squash_merge.py`, `test_dashboard_page.py`, `test_check_now.py`, `test_focus_front.py`, `test_ticket_names.py`, `test_poll_loop_rename.py` |
| README describes each change | PASS | README: `terminal start-session` (names), Clean dialog (squash), Tasks view artifacts (viewer), `factory poll [--task]`, card countdown and "Check now", Focus (menu, command, card), Concepts "Display name", `factory launch` and `factory state set` (ticket), Events, Bash allowlist, Troubleshooting "Rename failed" and "Could not bring the app to the front" |
| No co-author in commits | PASS | `git log --format='%(trailers)' master..factory-fixes` has no `Co-Authored-By` |

## Facts, checked again on 2026-10-16

| Fact | Result |
| --- | --- |
| Herdr 0.9.3 rename commands | `herdr 0.9.3`. `herdr workspace rename <WORKSPACE_ID> <LABEL>...`, `herdr tab rename <TAB_ID> <LABEL>...`, `herdr agent rename <TARGET> <NAME>\|--clear` |
| Git 2.55 with `merge-tree --write-tree` | `git version 2.55.0`. Used by `delete.content_merged` |
| Claude Code 2.1.301 `--name`, live rename | `2.1.301 (Claude Code)`. `--name` exists. The `/rename [name]` command exists ("Rename the current conversation"), so the live rename types `/rename <name>` |
| Adapter labels, task id slug, poll loop, delete upstream, dashboard modal | Read in the code before the build. Each is changed by its milestone |

## 1. Herdr name limit

| Item | Result | Evidence |
| --- | --- | --- |
| Name rule: lowercase, `-` runs, `t-` prefix, hash after 32, valid name unchanged | PASS | `adapters/base.py::herdr_name`. `test_rule`, `test_long_name_is_valid_and_short` |
| Handle saves the real name, later calls use the handle | PASS | `test_fake_adapter_returns_the_real_name`, `test_herdr_adapter_starts_with_the_real_name` (stub `herdr`: `agent start` and `--label` use the real name, the long name never reaches Herdr) |
| `start-session` prints the handle | PASS | Unchanged command prints the handle with the real `agent` name. README says so |
| Long review-mr name valid, starts with fake and stubbed herdr | PASS | Both tests above use `library-following-opening-the-review-mr` |
| Names that differ after char 32 differ | PASS | `test_names_that_differ_after_32_characters_stay_different` |
| `HT-4549 Fix` → `ht-4549-fix`, `4549` → `t-4549` | PASS | `test_rule` |

## 2. Clean after a squash merge

| Item | Result | Evidence |
| --- | --- | --- |
| `merge-tree` in the main repo, tree equals `origin/<base_ref>` tree; worktree HEAD only without a branch | PASS | `delete.content_merged`, `plan_delete` |
| Dry run: no lost commit, squash sentence, local branch deleted | PASS | `test_squash_merged_branch_loses_nothing_and_is_deleted` |
| A change not in `origin/<base_ref>`: same as today | PASS | `test_local_commit_after_squash_is_listed` |
| Clean reason "merged (squash)" | PASS | `test_clean_reports_squash_when_worktree_is_gone` |
| Fetch before the check | PASS | `plan_delete` runs `git fetch origin --prune`, like `factory clean` (ruling R2) |
| Merge commit and never-pushed branch unchanged | PASS | `test_merge_commit_is_unchanged`, `test_never_pushed_branch_is_unchanged` |
| Later change of same lines: not merged | PASS | `test_later_change_of_same_lines_is_not_merged` |

## 3. Artifact viewer

| Item | Result | Evidence |
| --- | --- | --- |
| Escape, click outside, Close | PASS | Browser checks 2, 3, 4 in `factory-fixes-artifact-viewer.md` |
| Title bar always visible, text scrolls inside | PASS | Browser check 1 (2000-line file) |
| Forms never close on a click outside; Escape with typed text asks | PASS | Browser checks 6, 7, 8. Also a drag from the text to the backdrop keeps the viewer open (check 5) |
| Tests | PASS | `test_dashboard_page.py` plus the written browser check for a short and a long artifact |

## 4. Poll countdown and "Check now"

| Item | Result | Evidence |
| --- | --- | --- |
| Next poll time saved before each sleep, returned by the tasks API | PASS | `server.poll_loop`, `board.task_row` `next_check_at`. `test_api_returns_next_check_time` |
| `factory poll --task <id>` | PASS | `test_poll_task_failing_check_saves_result`, `test_poll_task_passing_check_ends_wait` |
| Result saved after each check | PASS | `last_check` (`at`, `ended`, `output`). Same two tests |
| Card: countdown each second, last check, "Check now" as a job with "Checking…" | PASS | Browser checks 9, 10, 11. `test_card_has_countdown_and_check_now` |
| Paused task: no countdown, no button | PASS | `test_paused_task_has_no_countdown` |
| One check at a time, wait ends once, one message | PASS | `test_two_threads_end_the_wait_once` |
| Cross-process lock (CLI and server) | PASS | `check.lock` with `flock`. `test_cli_and_in_process_check_end_the_wait_once`, `test_cli_check_is_refused_while_the_lock_is_held` (a second process gets "A check is already running.") |
| 5-second check: API answers at once, page usable | PASS | `test_check_now_answers_at_once_with_a_job` (route under 1 s, `/api/tasks` answers while the job runs). Browser check 10 |

## 5. Focus brings the terminal app to the front

| Item | Result | Evidence |
| --- | --- | --- |
| Focus still runs `factory terminal focus`, then `open -a <terminal_app>` | PASS | `session.focus`. `test_open_runs_after_the_herdr_focus` (stub `open`, called after the fake adapter focus) |
| `terminal_app` asked on first use | PASS | `test_missing_app_asks`. Dashboard form and menu skill text |
| Not macOS or a failed command: Herdr focus still works, the dashboard says so | PASS | `test_failed_open_keeps_the_focus`, `test_not_macos_reports_failure`. The card shows the message |
| Empty value: no ask, only Herdr focus | PASS | `test_empty_app_skips_open` |

## 6. Names from the ticket

| Item | Result | Evidence |
| --- | --- | --- |
| Id base from the first Jira key of `ticket` (key, URL, text), else the slug; `-2` suffix | PASS | `test_ticket_key` (includes `https://x.atlassian.net/browse/HT-4549` → `ht-4549`), `test_launch_ids_from_ticket` (`ht-4549`, then `ht-4549-2`), `test_launch_without_key_uses_the_slug` |
| `launch --dry-run` shows the id | PASS | `test_dry_run_shows_the_id` |
| After launch, first Jira key: id, folder, events and worktree unchanged; display name unique; Herdr agent, tab and workspace renamed; handle saves the new agent name | PASS | `test_state_set_ticket_renames_and_keeps_the_id`, `test_herdr_names_are_renamed_with_the_stub` (stub `herdr`: `agent rename`, `tab rename`, `workspace rename`), `test_display_name_is_unique`, `test_partial_rename_keeps_the_new_agent_name` |
| Old value without a key (user change Z1) | PASS | `test_old_value_without_key_still_renames` |
| Claude rename: pending field, applied when idle and no question box, at resume with `--name` (user change Z2) | PASS | `test_working_session_gets_rename_later` (one `/rename`, field cleared), `test_question_box_blocks_the_live_rename`, `test_resume_applies_the_name`, `test_poll_loop_applies_pending_renames` |
| A working session is not renamed live | PASS | `test_working_session_gets_rename_later` |
| A failed rename does not fail `state set`, logs `rename_failed`, the card shows it | PASS | `test_failed_rename_does_not_fail_state_set`, `test_unexpected_rename_error_is_saved_and_logged` |
| A Claude rename never erases a Herdr rename error (user change P2) | PASS | `test_claude_rename_keeps_the_tab_error`, `test_failed_claude_rename_is_cleared_by_a_later_success` |
| Dashboard and `factory tasks` show the display name and the id | PASS | `test_rows_and_task_list_show_display_name`, `test_card_shows_display_name_and_rename_error` |
| Display name optional, no migration, no version change | PASS | `state.display_name(task)` falls back to the id. No change in `migrations/` or the data version |
| A launch id never equals a live display name | PASS | `test_launch_id_avoids_a_renamed_task_display_name` (final review fix) |

## Safety

- No real Herdr workspace, tab or agent was started, renamed or closed. Tests use the fake adapter or `tests/fake_herdr.py` on `PATH`.
- No real `open -a` ran. Tests use a stub `open` on `PATH`.
- No real task, worktree or branch was deleted. Squash tests use temp repos with a local bare `origin`. The browser check used a throwaway repo in the session scratchpad.
- Nothing was pushed. `master` is unchanged.

## Remaining blockers

None.
