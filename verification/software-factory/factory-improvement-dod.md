# Factory improvement: Definition Of Done check

Date: 2026-10-16. Branch `factory-improvement`. Prompt: `prompts/factory_improvment.md`.
Test results: `factory-improvement-report.md` and `factory-improvement-junit.xml`.

## Workflow Complete

| Item | Result | Evidence |
|---|---|---|
| Plan under `PLAN_DIR`, written before implementation, build followed it | PASS | `plans/2026-10-16-factory-improvement.md`, committed in `factory improvement: spec and plan` before the first code commit. Build used subagent-driven development, one task at a time, with a review per task. |
| Work on branch `factory-improvement`, `master` unchanged | PASS | `master` = `f16a6fc` before and after (`factory-improvement-master-before.txt`). Nothing pushed. |
| Every existing test still passes, each milestone adds tests | PASS | Baseline 478 passed. Milestone 1 gate 556 passed. Milestone 2 gate 612 passed. Final run: see report. Milestone 1 adds `test_exclusive_format`, `test_exclusive_store`, `test_exclusive_flow`, `test_exclusive_display`. Milestone 2 adds `test_hook_settings`, `test_attention_hooks`, `test_attention_display`. |
| README describes both features, `factory-authoring` describes `exclusive` | PASS | README "Exclusive steps" and "May wait for you" sections, commands, card lines, events. `skills/factory-authoring/SKILL.md` field table and "Exclusive steps" section. |

## Facts, checked again on 2026-10-16

| Fact | Result |
|---|---|
| Task session asks in plain text, then ends its turn | Still true: `session.ASK_IN_TEXT` in the first prompt. |
| Step prompts tell the session to run `factory block` | Still true: `render.IF_NEEDED`. |
| Herdr states `idle` and `working` | Seen in `herdr agent list` (Herdr 0.9.3). Herdr also returns `focused`; only one pane in all of Herdr had `focused: true`. |
| Init wrote `claude-settings.json` only when missing | Was true. Now replaced by `init.ensure_settings`, which merges. |
| Session id saved in the task state, `--resume` keeps it | Still true (`session.claude_args`). |
| Library lock `nx-emulator-lock.sh` | Not read and not changed (the library is out of scope). |
| `waiting_external` without `done_check` shows "Mark done" | Still true, except for a task that waits for a resource (`wait_has_check` is null). |
| Stop hook input | Claude Code 2.1.301 gives `last_assistant_message` and `background_tasks`. Confirmed by the real check. |

## 1. Exclusive steps

| Item | Result | Tests |
|---|---|---|
| `exclusive: <name>` field, name rule, shared at every level | PASS | `test_valid_exclusive_name`, `test_bad_exclusive_name`, `test_exclusive_on_group_is_error` |
| Hold while the step has the name and started; release on done, skip, goto, loop jump, pipeline end, delete | PASS | `test_second_task_waits_then_starts_after_done`, `test_moves_release[skip,goto,loop]`, `test_finish_releases`, `test_delete_holder_hands_over`, `test_next_step_with_same_name_keeps_resource` |
| Paused task keeps it, card says so | PASS | `test_paused_holder_keeps`, `test_dashboard_page_has_release` ("Keeps … while paused") |
| `factory exclusive release` mid-step, logs `exclusive_release` | PASS | `test_release_mid_step_then_acquire_waits`, `test_release_logs_event` |
| `factory exclusive acquire` waits like `next`, ends the turn, logs `exclusive_acquire` | PASS | `test_release_mid_step_then_acquire_waits`, `test_acquire_waiter_continues_step`, `test_acquire_by_holder` |
| `factory next` on a busy resource: no start, `waiting_external` with the reason, exact message, `exclusive_wait` | PASS | `test_second_task_waits_then_starts_after_done`, `test_claim_busy_waits`, `test_claim_twice_queues_once` |
| `release --force` from CLI, menu and card "Release", with confirmation; `exclusive_forced` on both; next waiter starts | PASS | `test_force_release_blocked_holder`, `test_force_release_logs_both`, `test_api_release_route`, `test_menu_has_release_action`, `test_dashboard_page_has_release` |
| `factory exclusive status` | PASS | `test_status_command_lists_queue`, `test_exclusive_status_command` |
| Direct handover to the longest waiter under the lock; skip paused; deleted leaves; messages; resume when gone | PASS | `test_release_hands_over_in_order`, `test_third_task_cannot_jump_queue`, `test_paused_waiter_is_skipped_and_keeps_place`, `test_paused_waiter_then_resume`, `test_resume_gets_free_resource_at_once`, `test_deleted_waiter_leaves_queue`, `test_acquire_mode_message`, `test_waiters_reason_names_new_holder` |
| `factory poll` checks the waiting tasks | PASS | `test_poll_recovers_missed_handover`, `test_recheck_drops_missing_holder` |
| Two `factory next` at the same time in two processes | PASS | `test_two_processes_claim_once` |
| `factory status` and cards show the resource and holder | PASS | `test_status_shows_holder`, `test_row_for_waiting_task` |
| Waiting card: no "Mark done", no "Check now"; `external-done` refuses | PASS | `test_waiting_task_with_done_check_has_no_check`, `test_external_done_refused_while_waiting`, `test_done_and_run_command_refused_while_waiting`, `test_poll_ignores_exclusive_wait` |
| `factory pipeline check` accepts it; step editor shows and sets it | PASS | `test_pipeline_check_accepts_exclusive`, `test_step_api_saves_exclusive`, `test_editor_has_exclusive_field` |
| A step without `exclusive` behaves as today | PASS | `test_step_without_exclusive_unchanged`, `test_no_footer_without_exclusive`, all 478 old tests |
| Two different names do not block each other | PASS | `test_names_do_not_block_each_other` |

## 2. "May wait for you"

| Item | Result | Tests |
|---|---|---|
| Init adds `Stop` and `UserPromptSubmit` hooks next to the rules | PASS | `test_init_writes_hooks` |
| Init and the version check add them to an existing file, keep rules, add once; no data version change | PASS | `test_existing_settings_keep_rules_and_get_hooks_once`, `test_version_check_adds_missing_hooks`, `test_link_dir_with_space_is_idempotent`, `test_invalid_settings_do_not_crash`. Data version stays 2. |
| Hooks read stdin, find the task by `session_id` among non-archived tasks, unknown session changes nothing | PASS | `test_stop_on_active_sets_attention_and_notifies`, `test_archived_task_not_found`, `test_bad_input_is_silent` |
| Hooks always exit 0, quickly, no output; errors to the event log | PASS | `test_bad_input_is_silent`, `test_hook_outside_factory_is_silent`, `test_hook_in_repo_without_factory_is_silent`, `test_hook_other_data_version_is_silent`, `test_hook_error_logs_hook_failed` |
| `hook stop` on `active`: `attention` with time and message, one notification, logs `attention` | PASS | `test_stop_on_active_sets_attention_and_notifies`, `test_message_is_trimmed`, `test_transcript_fallback` |
| Focus rule (user decision N1: focused uses the 60 s rule, not focused notifies at once) | PASS | `test_not_focused_notifies_at_once`, `test_focused_uses_delay`, `test_focused_prompt_during_delay_no_notify` |
| 60 s rule: detached process, notifies only if `attention` is unchanged | PASS | `test_no_focus_capability_uses_delay`, `test_no_handle_uses_delay`, `test_attention_at_is_unique` |
| Other statuses change nothing | PASS | `test_stop_other_status_changes_nothing[blocked,waiting_external,awaiting_approval,paused,finished]` |
| Cleared on prompt, status change, dashboard/menu prompt, approve, request changes; logs `attention_cleared` | PASS | `test_prompt_clears`, `test_block_clears_attention`, `test_dashboard_send_prompt_clears`, `test_cleared_logged_once`. Approve and request changes change the status, so the status rule clears it. |
| Card in the blocked color, time and message; task list and menu list it with blocked | PASS | `test_dashboard_page_has_attention`, `test_row_has_attention`, `test_tasks_sort_attention_with_blocked`, `test_text_list_says_may_wait` |
| `factory block` stays the main way | PASS | Unchanged `render.IF_NEEDED`. |
| Real check in `VERIFICATION_DIR` | PASS | `real_attention_check.py` and `real-attention-check.md`: a temp repo, the fake adapter, a real headless Claude 2.1.301 run with the task's session id and settings. The task got `attention` "Which color do you prefer?" and one notification. No user session or Herdr workspace was used. |

## Remaining limits

- Resources are per repository. Two repositories that share one emulator do not see each other. This is a known limit in the spec.
- The real Claude runs left their own transcripts in `~/.claude/projects/` (paths with `real-attention-`). This is tool-managed runtime data.
