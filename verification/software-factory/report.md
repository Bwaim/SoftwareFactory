# Software factory verification report

Date: 2026-10-13 04:05

Total: 226 of 226 checks pass.

## Milestone 1. Core

| Test | Result |
|---|---|
| `test_adapters::test_fake_records_calls` | PASS |
| `test_adapters::test_capabilities_and_check` | PASS |
| `test_builtin::test_builtin_steps_parse` | PASS |
| `test_config_state::test_config_order` | PASS |
| `test_config_state::test_cli_config_set_get` | PASS |
| `test_config_state::test_state_set_get_and_artifact_path` | PASS |
| `test_config_state::test_artifact_name_must_be_simple` | PASS |
| `test_config_state::test_events_append` | PASS |
| `test_delete::test_dry_run_shows_changes_and_changes_nothing` | PASS |
| `test_delete::test_delete_refuses_without_confirm_then_archives` | PASS |
| `test_delete::test_launch_and_delete_never_call_herdr` | PASS |
| `test_delete::test_pushed_branch_is_deleted` | PASS |
| `test_delete::test_branch_merged_then_deleted_on_origin_is_deleted` | PASS |
| `test_delete::test_failed_check_refuses_without_confirm` | PASS |
| `test_engine::test_next_done_check_fails_then_passes` | PASS |
| `test_engine::test_skip_refused_for_required_and_composite_path` | PASS |
| `test_engine::test_last_done_finishes` | PASS |
| `test_engine::test_missing_config_asks` | PASS |
| `test_engine::test_subagent_call_model_effort_precedence` | PASS |
| `test_engine::test_done_check_timeout` | PASS |
| `test_engine::test_run_script_gets_config_and_task` | PASS |
| `test_engine::test_next_tells_session_about_block_skip_and_goto` | PASS |
| `test_fsio::test_atomic_write_creates_parents_and_leaves_no_temp` | PASS |
| `test_fsio::test_update_yaml_returns_fn_result` | PASS |
| `test_fsio::test_lock_file_is_separate` | PASS |
| `test_fsio::test_two_processes_lose_no_write` | PASS |
| `test_herdr_adapter::test_start_in_worktree` | PASS |
| `test_herdr_adapter::test_extra_workspace_recorded_and_closed` | PASS |
| `test_herdr_adapter::test_extra_workspace_with_live_agent_left_open` | PASS |
| `test_herdr_adapter::test_workspace_with_other_tab_only_our_tab_closed` | PASS |
| `test_herdr_adapter::test_already_open_worktree_workspace_not_owned` | PASS |
| `test_herdr_adapter::test_exception_after_open_closes_what_was_opened` | PASS |
| `test_herdr_adapter::test_preexisting_workspace_never_closed` | PASS |
| `test_herdr_adapter::test_main_repo_uses_existing_workspace` | PASS |
| `test_herdr_adapter::test_main_repo_creates_workspace_when_missing` | PASS |
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
| `test_init_menu::test_init_creates_files_and_exclude` | PASS |
| `test_init_menu::test_init_never_overwrites` | PASS |
| `test_init_menu::test_init_needs_existing_library_or_flag` | PASS |
| `test_init_menu::test_init_reports_failed_prerequisite` | PASS |
| `test_init_menu::test_link_fixes_wrong_target` | PASS |
| `test_init_menu::test_menu_before_and_after_init` | PASS |
| `test_init_menu::test_terminal_defaults_to_herdr_and_init_saves_it` | PASS |
| `test_init_menu::test_init_lists_failed_terminal_check` | PASS |
| `test_init_menu::test_init_lists_missing_uv_with_fix` | PASS |
| `test_launch::test_slug_rules` | PASS |
| `test_launch::test_dry_run_changes_nothing_and_reports` | PASS |
| `test_launch::test_launch_detached` | PASS |
| `test_launch::test_taken_id_gets_suffix` | PASS |
| `test_launch::test_new_branch` | PASS |
| `test_launch::test_existing_local_branch_behind_is_fast_forwarded` | PASS |
| `test_launch::test_remote_only_branch` | PASS |
| `test_launch::test_diverged_branch_stops` | PASS |
| `test_launch::test_branch_in_other_worktree_stops` | PASS |
| `test_launch::test_failed_start_rolls_back_but_keeps_existing_branch` | PASS |
| `test_launch::test_failure_after_start_closes_the_terminal` | PASS |
| `test_launch::test_create_worktree_listed_late_refused` | PASS |
| `test_launch::test_no_worktree_pipeline_uses_task_flag` | PASS |
| `test_launch::test_missing_input_and_config` | PASS |
| `test_launch::test_cli_dry_run_json` | PASS |
| `test_pipeline_check::test_each_problem_type` | PASS |
| `test_pipeline_check::test_valid_pipeline_has_no_problem` | PASS |
| `test_pipeline_check::test_cli_pipeline_check` | PASS |
| `test_registry::test_local_overrides_generic_overrides_builtin` | PASS |
| `test_registry::test_composite_paths_and_io` | PASS |
| `test_registry::test_composite_loop_refused` | PASS |
| `test_registry::test_expand_adds_create_worktree_and_overrides` | PASS |
| `test_repo_version::test_main_repo_from_worktree` | PASS |
| `test_repo_version::test_current_task_matches_symlinked_path` | PASS |
| `test_repo_version::test_unknown_task_says_add_task` | PASS |
| `test_repo_version::test_factory_task_env` | PASS |
| `test_repo_version::test_version_mismatch_refused` | PASS |
| `test_repo_version::test_version_report_states` | PASS |
| `test_scaffold::test_version_prints` | PASS |
| `test_scaffold::test_uv_installs_dependencies_on_first_run` | PASS |
| `test_scaffold::test_marketplace_points_to_plugin` | PASS |
| `test_skill::test_skill_frontmatter_and_menu_rule` | PASS |

## Milestone 2. Task life

| Test | Result |
|---|---|
| `test_approval::test_awaiting_approval_then_approve` | PASS |
| `test_approval::test_request_changes` | PASS |
| `test_approval::test_approve_refused_when_not_waiting` | PASS |
| `test_approval::test_open_ide_needs_command` | PASS |
| `test_approval::test_open_ide_bad_command_is_factory_error` | PASS |
| `test_backlog::test_add_list_remove_move` | PASS |
| `test_backlog::test_hand_written_file_is_kept` | PASS |
| `test_backlog::test_launch_from_backlog` | PASS |
| `test_backlog::test_failed_launch_keeps_entry` | PASS |
| `test_backlog::test_import` | PASS |
| `test_backlog::test_two_processes_lose_no_write` | PASS |
| `test_backlog::test_listing_a_file_with_ids_does_not_rewrite_it` | PASS |
| `test_board::test_block_unblock_and_order` | PASS |
| `test_board::test_session_state_column` | PASS |
| `test_board::test_columns_follow_steps` | PASS |
| `test_board::test_launch_uses_start_column` | PASS |
| `test_clean::test_clean_detects_merge_cases` | PASS |
| `test_event_log::test_all_event_types` | PASS |
| `test_goto::test_goto_back_into_composite` | PASS |
| `test_goto::test_goto_forward_refused` | PASS |
| `test_goto::test_third_jump_blocks` | PASS |
| `test_session::test_pause_saves_status_and_closes` | PASS |
| `test_session::test_pause_wait_uses_wait_idle` | PASS |
| `test_session::test_resume_restores_status_same_session` | PASS |
| `test_session::test_resume_refused_when_session_runs` | PASS |
| `test_session::test_deliver_to_gone_session_sends_one_prompt` | PASS |
| `test_session::test_send_prompt_and_focus` | PASS |
| `test_session::test_pause_all` | PASS |
| `test_waiting::test_wait_then_poll_ends_on_check` | PASS |
| `test_waiting::test_paused_task_not_polled` | PASS |
| `test_waiting::test_external_done_manual` | PASS |
| `test_waiting::test_external_done_refused_with_check` | PASS |
| `test_waiting::test_wait_refused_on_normal_step` | PASS |
| `test_waiting::test_end_wait_refused_when_not_waiting` | PASS |
| `test_waiting::test_end_wait_adds_period_to_done_when` | PASS |

## Milestone 3. Authoring

| Test | Result |
|---|---|
| `test_catalog::test_list_and_install_pipeline_with_missing_steps` | PASS |
| `test_catalog::test_replace_needs_flag_and_shows_diff` | PASS |
| `test_catalog::test_missing_requires` | PASS |
| `test_catalog::test_catalog_is_generic` | PASS |
| `test_catalog::test_catalog_steps_parse_with_registry` | PASS |
| `test_editor_api::test_steps_list_and_detail` | PASS |
| `test_editor_api::test_load_copy_check_save` | PASS |
| `test_editor_api::test_cli_lists` | PASS |
| `test_editor_api::test_save_drops_empty_nested_fields` | PASS |
| `test_editor_api::test_copy_to_existing_id_refused` | PASS |
| `test_editor_api::test_new_pipeline_over_existing_file_refused_then_replaced` | PASS |
| `test_editor_api::test_editing_the_same_pipeline_at_the_same_level_is_allowed` | PASS |
| `test_editor_api::test_editing_another_pipeline_or_level_over_existing_refused` | PASS |
| `test_library::test_commit_only_given_files` | PASS |
| `test_library::test_refuses_paths_outside_library` | PASS |
| `test_library::test_disabled_without_git` | PASS |
| `test_library::test_commit_adds_new_library_factory_yaml` | PASS |
| `test_library::test_commit_adds_changed_library_factory_yaml` | PASS |
| `test_server::test_server_survives_the_command_and_is_reused` | PASS |
| `test_server::test_security_checks` | PASS |
| `test_server::test_stop` | PASS |
| `test_server::test_idle_stop` | PASS |
| `test_server::test_adapter_check_failure_reported` | PASS |
| `test_server::test_non_ascii_token_is_refused` | PASS |
| `test_server::test_invalid_json_body_is_refused` | PASS |
| `test_server::test_server_info_file_is_private` | PASS |
| `test_server::test_pages_send_privacy_headers` | PASS |
| `test_server::test_shutdown_needs_token_and_safe_origin` | PASS |
| `test_server::test_refused_requests_do_not_keep_server_alive` | PASS |
| `test_server::test_adapter_check_exception_reported` | PASS |
| `test_server::test_server_polls_waiting_tasks_on_its_own` | PASS |
| `test_step_assistant::test_builtin_assistant_runs_in_main_repo` | PASS |

## Milestone 4. Lifecycle and docs

| Test | Result |
|---|---|
| `test_docs::test_readme_commands_exist` | PASS |
| `test_docs::test_skill_and_builtin_commands_exist` | PASS |
| `test_docs::test_readme_sections` | PASS |
| `test_docs::test_checker_scans_fenced_blocks_and_inline_spans_but_not_prose` | PASS |
| `test_migrate::test_older_refused_then_migrated` | PASS |
| `test_migrate::test_dirty_library_refused` | PASS |
| `test_migrate::test_shared_library_migrated_once` | PASS |
| `test_migrate::test_newer_refused` | PASS |

## Milestone 5. Dashboard

| Test | Result |
|---|---|
| `test_dashboard_api::test_launch_dry_run_then_launch` | PASS |
| `test_dashboard_api::test_actions_call_cli_functions` | PASS |
| `test_dashboard_api::test_approve_from_card` | PASS |
| `test_dashboard_api::test_backlog_routes` | PASS |
| `test_dashboard_api::test_artifact_and_errors` | PASS |
| `test_dashboard_api::test_clean_and_delete_routes` | PASS |
| `test_dashboard_api::test_missing_body_field_is_400` | PASS |
| `test_dashboard_api::test_delete_rejects_non_task_ids[../x]` | PASS |
| `test_dashboard_api::test_delete_rejects_non_task_ids[archive/x]` | PASS |
| `test_dashboard_api::test_artifact_for_unknown_task_creates_nothing` | PASS |
| `test_dashboard_api::test_artifact_symlink_outside_is_refused` | PASS |
| `test_dashboard_api::test_confirm_unpushed_must_be_true` | PASS |

## Other tests

| Test | Result |
|---|---|
| `test_minor_fixes::test_poll_survives_a_task_with_a_missing_folder` | PASS |
| `test_minor_fixes::test_poll_reports_a_broken_task_and_goes_on` | PASS |
| `test_minor_fixes::test_run_check_reports_missing_folder` | PASS |
| `test_minor_fixes::test_herdr_missing_binary_is_adapter_error` | PASS |
| `test_minor_fixes::test_end_wait_on_last_step_only_notifies` | PASS |
| `test_minor_fixes::test_list_tasks_skips_a_folder_that_vanished` | PASS |
| `test_minor_fixes::test_create_refuses_an_existing_task_folder` | PASS |
| `test_minor_fixes::test_goto_and_block_refuse_finished_tasks` | PASS |
| `test_minor_fixes::test_block_refuses_paused_tasks` | PASS |
| `test_minor_fixes::test_artifact_name_must_be_a_plain_string[plan.md\n]` | PASS |
| `test_minor_fixes::test_artifact_name_must_be_a_plain_string[]` | PASS |
| `test_minor_fixes::test_artifact_name_must_be_a_plain_string[5]` | PASS |
| `test_minor_fixes::test_artifact_name_must_be_a_plain_string[None]` | PASS |
| `test_minor_fixes::test_artifact_name_must_be_a_plain_string[bad4]` | PASS |
| `test_minor_fixes::test_pipeline_id_must_be_a_plain_string[ab\n]` | PASS |
| `test_minor_fixes::test_pipeline_id_must_be_a_plain_string[5]` | PASS |
| `test_minor_fixes::test_pipeline_id_must_be_a_plain_string[bad2]` | PASS |
| `test_minor_fixes::test_api_rejects_non_string_values_with_400` | PASS |
| `test_minor_fixes::test_approve_send_with_delivery_failure_keeps_approval` | PASS |
| `test_minor_fixes::test_cli_approve_send_warns_and_exits_zero` | PASS |
| `test_minor_fixes::test_api_approve_returns_delivery_error` | PASS |
| `test_question_box::test_send_prompt_refused_when_question_box_shows` | PASS |
| `test_question_box::test_send_prompt_failure_logs_prompt_failed` | PASS |
| `test_question_box::test_approve_send_refused_when_question_box_shows` | PASS |
| `test_question_box::test_request_changes_send_refused_when_question_box_shows` | PASS |
| `test_question_box::test_approve_send_logs_prompt_sent` | PASS |
| `test_question_box::test_dashboard_approve_shows_question_box_error` | PASS |
| `test_question_box::test_prompts_ask_in_plain_text` | PASS |
| `test_question_box::test_herdr_detects_question_box_on_screen` | PASS |
| `test_races::test_second_advance_with_same_position_refused` | PASS |
| `test_races::test_done_racing_with_skip_advances_once` | PASS |
| `test_races::test_approve_after_request_changes_race_is_factory_error` | PASS |
| `test_races::test_request_changes_after_approve_race_is_factory_error` | PASS |
| `test_races::test_unblock_racing_with_unblock_refused` | PASS |
| `test_races::test_end_wait_twice_ends_once` | PASS |
| `test_terminal_cli::test_start_session_close_state_notify_wait_idle` | PASS |
| `test_terminal_cli::test_start_session_without_worktree_flag_or_args` | PASS |
| `test_terminal_cli::test_bad_handle_json_is_an_error` | PASS |

## End-to-end (Herdr and Claude)

| Check | Result |
|---|---|
| launch fetches origin and creates the worktree from origin/main | PASS (worktree cc42261f new origin cc42261f clone head c582708b) |
| Claude runs in Herdr named with the task id, with the factory settings | PASS (status idle kind claude processes 1) |
| Claude receives the first prompt and runs factory next | PASS |
| first script step runs with factory next and factory done | PASS |
| send-prompt reads the screen, sees no question box and sends | PASS (exit 0 last event prompt_sent ) |
| pause closes the task terminal | PASS |
| resume reopens the Claude process with --resume and the same session id | PASS (resume processes 1) |
| the resumed session continues the pipeline to the end | PASS |
| the same Claude transcript file exists and grew after resume | PASS (/Users/fabienboismoreau/.claude/projects/-Users-fabienboismoreau-Documents-Projects-SoftwareFactory-SoftwareFactory-verification-software-factory-work-e2e-worktrees-e2e-task/884569b1-e2fd-41f7-816c-882b5daff3c0.jsonl 356319 -> 390486) |
| the session never waits on a permission prompt | PASS (13 samples, blocked 0, error 0) |
| delete asks for approval when there are uncommitted changes | PASS |
| delete closes the terminal, removes the worktree and archives the task | PASS |
| no Herdr workspace or tab is left open after the run | PASS |
