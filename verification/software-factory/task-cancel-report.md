# Task cancel verification report

Date: 2026-10-22 16:34

## Milestone 1. Merged branch check

55 of 55 tests pass.

| Test | Result |
|---|---|
| `test_clean::test_clean_detects_merge_cases` | PASS |
| `test_delete::test_dry_run_shows_changes_and_changes_nothing` | PASS |
| `test_delete::test_delete_refuses_without_confirm_then_archives` | PASS |
| `test_delete::test_launch_and_delete_never_call_herdr` | PASS |
| `test_delete::test_pushed_branch_is_deleted` | PASS |
| `test_delete::test_branch_merged_then_deleted_on_origin_is_deleted` | PASS |
| `test_delete::test_failed_check_refuses_without_confirm` | PASS |
| `test_herdr_adapter::test_start_in_worktree` | PASS |
| `test_herdr_adapter::test_extra_workspace_recorded_and_closed` | PASS |
| `test_herdr_adapter::test_extra_workspace_with_live_agent_left_open` | PASS |
| `test_herdr_adapter::test_workspace_with_other_tab_only_our_tab_closed` | PASS |
| `test_herdr_adapter::test_already_open_worktree_workspace_not_owned` | PASS |
| `test_herdr_adapter::test_exception_after_open_closes_what_was_opened` | PASS |
| `test_herdr_adapter::test_preexisting_workspace_never_closed` | PASS |
| `test_herdr_adapter::test_trust_dialog_reported_and_cleaned` | PASS |
| `test_herdr_adapter::test_state_gone` | PASS |
| `test_herdr_adapter::test_check_outside_herdr` | PASS |
| `test_herdr_adapter::test_unreadable_tab_list_closes_only_our_tab[not json]` | PASS |
| `test_herdr_adapter::test_unreadable_tab_list_closes_only_our_tab[{}]` | PASS |
| `test_herdr_adapter::test_unreadable_tab_list_closes_only_our_tab[{"result": {}}]` | PASS |
| `test_herdr_adapter::test_missing_key_after_open_still_cleans_up` | PASS |
| `test_herdr_adapter::test_taken_agent_name_refused_and_untouched` | PASS |
| `test_herdr_adapter::test_failed_start_does_not_send_keys_to_agent` | PASS |
| `test_herdr_adapter::test_actions_refused_when_agent_in_other_tab` | PASS |
| `test_herdr_adapter::test_state_gone_when_agent_in_other_tab` | PASS |
| `test_herdr_adapter::test_actions_allowed_in_own_tab_or_workspace` | PASS |
| `test_herdr_adapter::test_herdr_focused_reads_agent_get` | PASS |
| `test_herdr_adapter::test_herdr_focused_refused_when_agent_in_other_tab` | PASS |
| `test_herdr_adapter::test_close_fails_when_tab_stays` | PASS |
| `test_herdr_adapter::test_close_of_gone_tab_is_success` | PASS |
| `test_herdr_adapter::test_close_fails_when_list_fails` | PASS |
| `test_merge_check::test_patch_id_finds_squash_after_later_change` | PASS |
| `test_merge_check::test_empty_branch_diff_is_not_patch_merged` | PASS |
| `test_merge_check::test_commit_on_other_files_is_ignored` | PASS |
| `test_merge_check::test_file_name_with_space` | PASS |
| `test_merge_check::test_missing_base_is_no_match` | PASS |
| `test_merge_check::test_task_branch_prefers_worktree` | PASS |
| `test_merge_check::test_task_branch_uses_state_when_worktree_gone_or_detached` | PASS |
| `test_merge_check::test_task_branch_missing_local_ref_is_none` | PASS |
| `test_merge_check::test_remote_deleted_without_merge_is_not_by_content` | PASS |
| `test_merge_check::test_delete_removes_squash_merged_branch_after_later_change` | PASS |
| `test_merge_check::test_local_commit_after_squash_is_lost_work` | PASS |
| `test_merge_check::test_worktree_removed_by_hand_squash_branch_is_deleted` | PASS |
| `test_merge_check::test_remote_deleted_without_merge_asks_and_keeps_branch` | PASS |
| `test_merge_check::test_detached_worktree_commits_are_listed` | PASS |
| `test_merge_check::test_detached_commits_listed_even_when_state_branch_merged` | PASS |
| `test_removal_failures::test_close_failure_changes_nothing` | PASS |
| `test_removal_failures::test_gone_terminal_is_success` | PASS |
| `test_removal_failures::test_branch_delete_failure_still_archives` | PASS |
| `test_squash_merge::test_squash_merged_branch_loses_nothing_and_is_deleted` | PASS |
| `test_squash_merge::test_local_commit_after_squash_is_listed` | PASS |
| `test_squash_merge::test_merge_commit_is_unchanged` | PASS |
| `test_squash_merge::test_never_pushed_branch_is_unchanged` | PASS |
| `test_squash_merge::test_clean_reports_squash_when_worktree_is_gone` | PASS |
| `test_squash_merge::test_later_change_of_same_lines_is_merged_by_patch_id` | PASS |

## Milestone 2. Cancel in the CLI

25 of 25 tests pass.

| Test | Result |
|---|---|
| `test_cancel::test_cancel_removes_everything` | PASS |
| `test_cancel::test_cancel_saves_uncommitted_changes` | PASS |
| `test_cancel::test_dry_run_lists_and_changes_nothing` | PASS |
| `test_cancel::test_remote_branch_is_never_deleted` | PASS |
| `test_cancel::test_cancel_paused_task` | PASS |
| `test_cancel::test_cancel_gone_session_and_missing_worktree` | PASS |
| `test_cancel::test_cancel_task_without_worktree_or_handle` | PASS |
| `test_cancel::test_finished_task_is_refused` | PASS |
| `test_cancel::test_cancel_close_failure_changes_nothing` | PASS |
| `test_cancel::test_cancel_branch_delete_failure_still_archives` | PASS |
| `test_cancel::test_change_made_during_close_is_saved` | PASS |
| `test_cancel::test_commit_made_during_close_is_restore_commit` | PASS |
| `test_cancel::test_stash_failure_stops` | PASS |
| `test_cancel::test_cancelled_task_missing_from_lists` | PASS |
| `test_cancel::test_detached_commits_are_lost_work_and_restorable` | PASS |
| `test_cancel_races::test_cancel_waits_for_running_check` | PASS |
| `test_cancel_races::test_cancelled_holder_hands_resource_to_next` | PASS |
| `test_cancel_races::test_cancelled_waiting_task_leaves_queue` | PASS |
| `test_cancel_races::test_stop_hook_and_poll_after_cancel_do_not_recreate` | PASS |
| `test_cancel_races::test_second_cancel_fails_cleanly` | PASS |
| `test_cancel_races::test_resume_after_archive_closes_new_session` | PASS |
| `test_no_recreate::test_event_log_for_missing_task_writes_nothing` | PASS |
| `test_no_recreate::test_state_update_after_folder_removed_raises` | PASS |
| `test_no_recreate::test_stop_hook_and_poll_after_delete_do_not_recreate` | PASS |
| `test_no_recreate::test_artifact_path_for_archived_task_does_not_recreate` | PASS |

## Milestone 3. Dashboard and docs

17 of 17 tests pass.

| Test | Result |
|---|---|
| `test_cancel_api::test_dry_run_route_matches_cli` | PASS |
| `test_cancel_api::test_cancel_route_archives_and_removes_from_list` | PASS |
| `test_cancel_api::test_routes_reject_missing_token` | PASS |
| `test_cancel_api::test_parts_left_reply` | PASS |
| `test_cancel_api::test_close_failure_reply` | PASS |
| `test_dashboard_page::test_modal_has_fixed_bar_and_scrolling_content` | PASS |
| `test_dashboard_page::test_artifact_viewer_is_dismissable` | PASS |
| `test_dashboard_page::test_card_has_countdown_and_check_now` | PASS |
| `test_dashboard_page::test_focus_asks_terminal_app` | PASS |
| `test_dashboard_page::test_card_shows_display_name_and_rename_error` | PASS |
| `test_dashboard_page::test_cancel_button_and_dialog` | PASS |
| `test_docs::test_readme_commands_exist` | PASS |
| `test_docs::test_skill_and_builtin_commands_exist` | PASS |
| `test_docs::test_readme_sections` | PASS |
| `test_docs::test_checker_scans_fenced_blocks_and_inline_spans_but_not_prose` | PASS |
| `test_docs::test_readme_describes_step_editor` | PASS |
| `test_docs::test_readme_describes_cancel` | PASS |

## Full test suite

670 of 670 tests pass.

## Updated tests

`tests/test_squash_merge.py::test_later_change_of_same_lines_is_not_merged` is renamed to `test_later_change_of_same_lines_is_merged_by_patch_id`. It checked the old bug: a later change of the same lines hid a squash merge. It now expects "merged (squash)". The user approved the change.

## Master

`git rev-parse master` is `f8ee5474c500d51f1b080a83daf3350e4ca9fe3b`: unchanged (expected `f8ee5474c500d51f1b080a83daf3350e4ca9fe3b`).
