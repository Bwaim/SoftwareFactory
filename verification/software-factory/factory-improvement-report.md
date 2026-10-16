# Factory improvement: test report

Date: 2026-10-16. Branch `factory-improvement`. Command: `uv run --with pytest --with pyyaml pytest -q -p no:cacheprovider tests --junitxml ...`.

Whole suite: 617 passed, 0 failed, 0 skipped. Baseline before the work: 478 passed.

## Milestone 1. Exclusive steps

### `test_exclusive_format` (13/13 passed)
- `test_valid_exclusive_name`: PASS
- `test_bad_exclusive_name[Android]`: PASS
- `test_bad_exclusive_name[1emu]`: PASS
- `test_bad_exclusive_name[emu lator]`: PASS
- `test_bad_exclusive_name[]`: PASS
- `test_exclusive_on_group_is_error`: PASS
- `test_footer_names_resource`: PASS
- `test_footer_in_command_step`: PASS
- `test_no_footer_without_exclusive`: PASS
- `test_released_line`: PASS
- `test_pipeline_check_accepts_exclusive`: PASS
- `test_step_api_saves_exclusive`: PASS
- `test_editor_has_exclusive_field`: PASS

### `test_exclusive_store` (29/29 passed)
- `test_claim_free_resource`: PASS
- `test_read_unknown_resource_is_free`: PASS
- `test_claim_by_holder_is_true`: PASS
- `test_claim_busy_waits`: PASS
- `test_claim_twice_queues_once`: PASS
- `test_claim_again_keeps_wait_status`: PASS
- `test_release_hands_over_in_order`: PASS
- `test_release_by_non_holder_is_false`: PASS
- `test_release_logs_event`: PASS
- `test_paused_waiter_is_skipped_and_keeps_place`: PASS
- `test_free_resource_not_blocked_by_paused_waiter`: PASS
- `test_acquire_mode_message`: PASS
- `test_force_release_logs_both`: PASS
- `test_force_release_free_resource_errors`: PASS
- `test_names_do_not_block_each_other`: PASS
- `test_recheck_drops_missing_holder`: PASS
- `test_recheck_keeps_paused_holder`: PASS
- `test_handover_drops_invalid_waiters`: PASS
- `test_step_name`: PASS
- `test_sync_keeps_same_name`: PASS
- `test_sync_releases_other_name`: PASS
- `test_forget_leaves_everything`: PASS
- `test_task_info`: PASS
- `test_holder_text`: PASS
- `test_status_rows`: PASS
- `test_delivery_error_keeps_handover`: PASS
- `test_handover_skips_task_removed_before_grant`: PASS
- `test_blocked_waiter_gets_resource_and_stays_blocked`: PASS
- `test_waiters_reason_names_new_holder`: PASS

### `test_exclusive_flow` (32/32 passed)
- `test_second_task_waits_then_starts_after_done`: PASS
- `test_holder_next_again_has_no_released_line`: PASS
- `test_three_tasks_in_wait_order`: PASS
- `test_third_task_cannot_jump_queue`: PASS
- `test_acquire_waiter_continues_step`: PASS
- `test_acquire_by_holder`: PASS
- `test_acquire_refused_on_other_name_or_not_started`: PASS
- `test_release_refused_when_not_holder`: PASS
- `test_paused_waiter_then_resume`: PASS
- `test_resume_gets_free_resource_at_once`: PASS
- `test_deleted_waiter_leaves_queue`: PASS
- `test_delete_holder_hands_over`: PASS
- `test_moves_release[skip]`: PASS
- `test_moves_release[goto]`: PASS
- `test_moves_release[loop]`: PASS
- `test_skip_of_waiting_task_leaves_queue`: PASS
- `test_next_step_with_same_name_keeps_resource`: PASS
- `test_paused_holder_keeps`: PASS
- `test_finish_releases`: PASS
- `test_release_mid_step_then_acquire_waits`: PASS
- `test_force_release_blocked_holder`: PASS
- `test_force_release_without_task`: PASS
- `test_external_done_refused_while_waiting`: PASS
- `test_done_and_run_command_refused_while_waiting`: PASS
- `test_poll_ignores_exclusive_wait`: PASS
- `test_poll_recovers_missed_handover`: PASS
- `test_status_shows_holder`: PASS
- `test_exclusive_status_command`: PASS
- `test_step_without_exclusive_unchanged`: PASS
- `test_two_processes_claim_once`: PASS
- `test_waiter_reason_follows_handover`: PASS
- `test_waiter_skip_to_same_name_leaves_queue`: PASS

### `test_exclusive_display` (9/9 passed)
- `test_row_for_waiting_task`: PASS
- `test_waiting_task_with_done_check_has_no_check`: PASS
- `test_row_without_exclusive_step_is_null`: PASS
- `test_api_release_route`: PASS
- `test_api_release_free_resource_is_an_error`: PASS
- `test_status_command_lists_queue`: PASS
- `test_menu_has_release_action`: PASS
- `test_dashboard_page_has_release`: PASS
- `test_skill_documents_exclusive`: PASS

## Milestone 2. May wait for you

### `test_hook_settings` (5/5 passed)
- `test_init_writes_hooks`: PASS
- `test_existing_settings_keep_rules_and_get_hooks_once`: PASS
- `test_version_check_adds_missing_hooks`: PASS
- `test_invalid_settings_do_not_crash`: PASS
- `test_link_dir_with_space_is_idempotent`: PASS

### `test_attention_hooks` (39/39 passed)
- `test_stop_on_active_sets_attention_and_notifies`: PASS
- `test_stop_without_message_notifies_short_text`: PASS
- `test_stop_uses_display_name`: PASS
- `test_message_is_trimmed`: PASS
- `test_stop_other_status_changes_nothing[blocked]`: PASS
- `test_stop_other_status_changes_nothing[waiting_external]`: PASS
- `test_stop_other_status_changes_nothing[awaiting_approval]`: PASS
- `test_stop_other_status_changes_nothing[paused]`: PASS
- `test_stop_other_status_changes_nothing[finished]`: PASS
- `test_stop_with_background_tasks_changes_nothing`: PASS
- `test_stop_with_empty_background_tasks_sets_attention`: PASS
- `test_prompt_clears`: PASS
- `test_clear_returns_false_when_not_set`: PASS
- `test_bad_input_is_silent[stop-]`: PASS
- `test_bad_input_is_silent[stop-not json]`: PASS
- `test_bad_input_is_silent[stop-[1, 2]]`: PASS
- `test_bad_input_is_silent[stop-{"session_id": "unknown"}]`: PASS
- `test_bad_input_is_silent[prompt-]`: PASS
- `test_bad_input_is_silent[prompt-not json]`: PASS
- `test_bad_input_is_silent[prompt-[1, 2]]`: PASS
- `test_bad_input_is_silent[prompt-{"session_id": "unknown"}]`: PASS
- `test_hook_outside_factory_is_silent`: PASS
- `test_hook_in_repo_without_factory_is_silent`: PASS
- `test_hook_other_data_version_is_silent`: PASS
- `test_hook_error_logs_hook_failed`: PASS
- `test_notify_later_bad_args_is_silent`: PASS
- `test_not_focused_notifies_at_once`: PASS
- `test_focused_uses_delay`: PASS
- `test_focused_prompt_during_delay_no_notify`: PASS
- `test_no_handle_uses_delay`: PASS
- `test_no_focus_capability_uses_delay`: PASS
- `test_no_notify_capability_sets_attention_only`: PASS
- `test_attention_at_is_unique`: PASS
- `test_transcript_fallback`: PASS
- `test_transcript_missing_gives_no_message`: PASS
- `test_last_message_unit`: PASS
- `test_now_precise_has_microseconds`: PASS
- `test_archived_task_not_found`: PASS
- `test_bad_delay_falls_back_to_60`: PASS

### `test_attention_display` (9/9 passed)
- `test_block_clears_attention`: PASS
- `test_dashboard_send_prompt_clears`: PASS
- `test_failed_send_keeps_attention`: PASS
- `test_tasks_sort_attention_with_blocked`: PASS
- `test_row_has_attention`: PASS
- `test_text_list_says_may_wait`: PASS
- `test_text_list_without_message`: PASS
- `test_cleared_logged_once`: PASS
- `test_dashboard_page_has_attention`: PASS

## Existing tests

481/481 passed in 55 existing test files.

## Real check

See `real-attention-check.md`: PASS with Claude Code 2.1.301.
