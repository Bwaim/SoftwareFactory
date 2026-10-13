# Step delete and hide verification report

Date: 2026-10-13 11:27

## Milestone 1. Delete a step

27 of 27 tests pass.

| Test | Result |
|---|---|
| `test_step_delete::test_registry_keeps_every_level` | PASS |
| `test_step_delete::test_all_pipeline_files_includes_overridden` | PASS |
| `test_step_delete::test_hidden_ids_and_discard` | PASS |
| `test_step_delete::test_plan_local_step` | PASS |
| `test_step_delete::test_delete_local_step_removes_file` | PASS |
| `test_step_delete::test_local_override_is_replaced_by_generic` | PASS |
| `test_step_delete::test_generic_under_local_override` | PASS |
| `test_step_delete::test_unknown_step` | PASS |
| `test_step_delete::test_generic_step_offers_commit_of_removed_file_only` | PASS |
| `test_step_delete::test_untracked_generic_step_has_no_commit_offer` | PASS |
| `test_step_delete::test_script_step_removes_its_script` | PASS |
| `test_step_delete::test_shared_script_stays` | PASS |
| `test_step_delete::test_script_step_with_missing_script` | PASS |
| `test_step_delete::test_builtin_step_cannot_be_deleted` | PASS |
| `test_step_delete::test_refused_while_used` | PASS |
| `test_step_delete::test_overridden_pipeline_is_a_user` | PASS |
| `test_step_delete::test_dry_run_changes_nothing` | PASS |
| `test_step_delete::test_delete_removes_id_from_hidden_steps` | PASS |
| `test_step_delete::test_config_section_is_kept` | PASS |
| `test_step_delete::test_deleted_catalog_step_shows_not_installed` | PASS |
| `test_step_delete::test_cli_delete_and_dry_run` | PASS |
| `test_step_delete::test_cli_refusals` | PASS |
| `test_step_delete::test_cli_generic_offer_text` | PASS |
| `test_step_delete::test_api_dry_run_and_delete` | PASS |
| `test_step_delete::test_editor_page_has_delete_flow` | PASS |
| `test_step_delete::test_menu_has_delete_step_after_new_step` | PASS |
| `test_step_delete::test_docs_describe_delete` | PASS |

## Milestone 2. Hide a step

10 of 10 tests pass.

| Test | Result |
|---|---|
| `test_step_hide::test_hide_and_unhide` | PASS |
| `test_step_hide::test_hide_unknown_refused_unhide_stale_allowed` | PASS |
| `test_step_hide::test_hide_any_level` | PASS |
| `test_step_hide::test_step_list_and_show` | PASS |
| `test_step_hide::test_data_without_hidden_steps` | PASS |
| `test_step_hide::test_pipeline_check_warns_hidden_once` | PASS |
| `test_step_hide::test_pipeline_with_hidden_step_runs_to_end` | PASS |
| `test_step_hide::test_api_hide_unhide_list_check` | PASS |
| `test_step_hide::test_editor_page_has_hide_ui` | PASS |
| `test_step_hide::test_docs_describe_hide` | PASS |

## Full test suite

250 of 250 tests pass.

