# Step editor verification report

Date: 2026-10-13 18:31

## Milestone 1. Step format and runtime

90 of 90 tests pass.

| Test | Result |
|---|---|
| `test_builtin::test_builtin_steps_are_version_2` | PASS |
| `test_builtin::test_step_assistant_is_gone` | PASS |
| `test_catalog::test_list_and_install_pipeline_with_missing_steps` | PASS |
| `test_catalog::test_replace_needs_flag_and_shows_diff` | PASS |
| `test_catalog::test_missing_requires` | PASS |
| `test_catalog::test_catalog_is_generic` | PASS |
| `test_catalog::test_catalog_steps_parse_with_registry` | PASS |
| `test_catalog::test_catalog_steps_are_version_2` | PASS |
| `test_catalog::test_catalog_prompts_use_placeholders` | PASS |
| `test_engine::test_next_done_check_fails_then_passes` | PASS |
| `test_engine::test_skip_refused_for_required_and_composite_path` | PASS |
| `test_engine::test_last_done_finishes` | PASS |
| `test_engine::test_missing_config_asks` | PASS |
| `test_engine::test_subagent_call_model_effort_precedence` | PASS |
| `test_engine::test_done_check_timeout` | PASS |
| `test_engine::test_next_tells_session_about_block_skip_and_goto` | PASS |
| `test_keys::test_key_rule_and_env_name` | PASS |
| `test_keys::test_placeholders` | PASS |
| `test_keys::test_env_refs` | PASS |
| `test_keys::test_outputs_and_leaf_uses` | PASS |
| `test_migrate::test_older_refused_then_migrated` | PASS |
| `test_migrate::test_dirty_library_refused` | PASS |
| `test_migrate::test_shared_library_migrated_once` | PASS |
| `test_migrate::test_newer_refused` | PASS |
| `test_migrate_v2::test_converts_every_type` | PASS |
| `test_migrate_v2::test_absolute_script_path_is_kept` | PASS |
| `test_migrate_v2::test_every_converted_step_passes_version_2_validation` | PASS |
| `test_migrate_v2::test_refuses_what_version_2_refuses[empty----\nid: empty\ndescription: E\ntype: prompt\n---\n\n-the prompt is empty]` | PASS |
| `test_migrate_v2::test_refuses_what_version_2_refuses[noscript----\nid: noscript\ndescription: N\ntype: script\n---\n\n-names no script file]` | PASS |
| `test_migrate_v2::test_refuses_what_version_2_refuses[nokids----\nid: nokids\ndescription: K\ntype: composite\n---\n-has no `steps` list]` | PASS |
| `test_migrate_v2::test_refuses_what_version_2_refuses[badrun----\nid: badrun\ndescription: R\ntype: prompt\nrun_in: elsewhere\n---\n\nDo it.\n-`run_in` must be]` | PASS |
| `test_migrate_v2::test_refuses_what_version_2_refuses[badouts----\nid: badouts\ndescription: O\ntype: prompt\noutputs: nope\nwrites: [x]\n---\n\nDo it.\n-`outputs` must be a mapping]` | PASS |
| `test_migrate_v2::test_refuses_what_version_2_refuses[badname----\nid: badname\ndescription: O\ntype: prompt\noutputs:\n  Bad-Name: {}\n---\n\nDo it.\n-the output `Bad-Name`]` | PASS |
| `test_migrate_v2::test_refuses_what_version_2_refuses[badtype----\nid: badtype\ndescription: O\ntype: prompt\noutputs:\n  x:\n    type: blob\n---\n\nDo it.\n-unknown type `blob`]` | PASS |
| `test_migrate_v2::test_refuses_what_version_2_refuses[grpouts----\nid: grpouts\ndescription: G\ntype: composite\nsteps: [ask]\noutputs:\n  x: {}\n---\n-a group step cannot have `outputs`]` | PASS |
| `test_migrate_v2::test_refuses_what_version_2_refuses[Bad_Id----\nid: Bad_Id\ndescription: I\ntype: prompt\n---\n\nDo it.\n-the step id `Bad_Id`]` | PASS |
| `test_migrate_v2::test_migrated_pipeline_runs_to_the_end` | PASS |
| `test_migrate_v2::test_bad_key_name_refuses_before_any_change` | PASS |
| `test_migrate_v2::test_assistant_task_refuses_before_any_change` | PASS |
| `test_migrate_v2::test_bad_state_key_is_a_warning` | PASS |
| `test_migrate_v2::test_dry_run_lists_errors_without_change` | PASS |
| `test_migrate_v2::test_bad_frontmatter_refuses_before_any_change[---\nid: [oops\n---\n\nDo it.\n-invalid YAML frontmatter]` | PASS |
| `test_migrate_v2::test_bad_frontmatter_refuses_before_any_change[---\n- a\n- b\n---\n\nDo it.\n-the frontmatter must be a YAML mapping]` | PASS |
| `test_migrate_v2::test_bad_pipeline_yaml_refuses_before_any_change` | PASS |
| `test_registry::test_local_overrides_generic_overrides_builtin` | PASS |
| `test_registry::test_group_paths_uses_and_outputs` | PASS |
| `test_registry::test_group_loop_refused` | PASS |
| `test_registry::test_invalid_step_stops_the_load_with_its_file` | PASS |
| `test_registry::test_expand_always_adds_create_worktree` | PASS |
| `test_registry::test_expand_adds_create_worktree_and_overrides` | PASS |
| `test_runtime_v2::test_next_prints_exact_prompt_then_footer` | PASS |
| `test_runtime_v2::test_subagent_prompt_is_the_same_text_with_a_report_line` | PASS |
| `test_runtime_v2::test_wait_external_ends_with_factory_wait` | PASS |
| `test_runtime_v2::test_group_step_shows_full_path` | PASS |
| `test_runtime_v2::test_first_prompt_never_adds_task_flag` | PASS |
| `test_runtime_v2::test_command_next_and_env` | PASS |
| `test_runtime_v2::test_done_refused_until_command_exits_0` | PASS |
| `test_runtime_v2::test_goto_clears_command_result` | PASS |
| `test_runtime_v2::test_command_key_value_is_never_run` | PASS |
| `test_runtime_v2::test_file_output_must_exist` | PASS |
| `test_runtime_v2::test_state_set_file_relative_to_caller` | PASS |
| `test_runtime_v2::test_run_script_is_gone` | PASS |
| `test_runtime_v2::test_subagent_wait_external_ends_with_factory_wait` | PASS |
| `test_step_assistant::test_assistant_pipeline_and_step_do_not_exist` | PASS |
| `test_step_assistant::test_next_never_prints_task_flag` | PASS |
| `test_step_assistant::test_task_without_worktree_cannot_start` | PASS |
| `test_step_format::test_valid_ai_step_has_no_error` | PASS |
| `test_step_format::test_load_errors[manifest0-x-data version 1]` | PASS |
| `test_step_format::test_load_errors[manifest1-x-must be `ai`, `command` or `group`]` | PASS |
| `test_step_format::test_load_errors[manifest2-x-`reads` is from data version 1]` | PASS |
| `test_step_format::test_load_errors[manifest3-x-`writes` is from data version 1]` | PASS |
| `test_step_format::test_load_errors[manifest4-x-The id `Bad`]` | PASS |
| `test_step_format::test_load_errors[manifest5-x-The output `Bad-Key`]` | PASS |
| `test_step_format::test_load_errors[manifest6-x-unknown type `number`]` | PASS |
| `test_step_format::test_load_errors[manifest7-x-`outputs` must be a mapping]` | PASS |
| `test_step_format::test_load_errors[manifest8-x-The config key `Bad`]` | PASS |
| `test_step_format::test_load_errors[manifest9-Use {{Bad}}.-Invalid placeholder {{Bad}}]` | PASS |
| `test_step_format::test_load_errors[manifest10-Use {{config.style}}.-{{config.style}} uses a config key]` | PASS |
| `test_step_format::test_load_errors[manifest11-  \n-The prompt is empty]` | PASS |
| `test_step_format::test_load_errors[manifest12-echo {{x}}-A command cannot use]` | PASS |
| `test_step_format::test_load_errors[manifest13--The command is empty]` | PASS |
| `test_step_format::test_load_errors[manifest14--needs a `steps` list]` | PASS |
| `test_step_format::test_load_errors[manifest15-text-A group step has no body]` | PASS |
| `test_step_format::test_load_errors[manifest16--Remove `outputs`]` | PASS |
| `test_step_format::test_load_errors[manifest17-x-`done_check` cannot use]` | PASS |
| `test_step_format::test_load_errors[manifest18-x-`run_in` must be]` | PASS |
| `test_step_format::test_warnings` | PASS |
| `test_step_format::test_single_braces_are_not_placeholders` | PASS |
| `test_step_format::test_dump_order_and_empty_values` | PASS |
| `test_step_format::test_clean_keeps_required_only` | PASS |

## Milestone 2. Available keys

13 of 13 tests pass.

| Test | Result |
|---|---|
| `test_pipeline_check::test_each_problem_type` | PASS |
| `test_pipeline_check::test_valid_pipeline_has_no_problem` | PASS |
| `test_pipeline_check::test_cli_pipeline_check` | PASS |
| `test_pipeline_keys::test_keys_cli_text_and_json` | PASS |
| `test_pipeline_keys::test_latest_source_wins` | PASS |
| `test_pipeline_keys::test_new_check_warnings` | PASS |
| `test_pipeline_keys::test_own_output_is_not_an_unset_key` | PASS |
| `test_pipeline_keys::test_bad_input_name_and_type_are_errors` | PASS |
| `test_pipeline_keys::test_keys_route` | PASS |
| `test_typed_inputs::test_missing_file_input_is_a_dry_run_error` | PASS |
| `test_typed_inputs::test_relative_file_input_saved_absolute` | PASS |
| `test_typed_inputs::test_pipeline_list_has_typed_inputs` | PASS |
| `test_typed_inputs::test_dashboard_has_textarea_for_long_text` | PASS |

## Milestone 3. Step editor

20 of 20 tests pass.

| Test | Result |
|---|---|
| `test_docs::test_readme_commands_exist` | PASS |
| `test_docs::test_skill_and_builtin_commands_exist` | PASS |
| `test_docs::test_readme_sections` | PASS |
| `test_docs::test_checker_scans_fenced_blocks_and_inline_spans_but_not_prose` | PASS |
| `test_docs::test_readme_describes_step_editor` | PASS |
| `test_step_editor_api::test_save_new_local_step` | PASS |
| `test_step_editor_api::test_save_generic_offers_commit` | PASS |
| `test_step_editor_api::test_duplicate_id_refused_hidden_included` | PASS |
| `test_step_editor_api::test_builtin_edit_refused_and_copy_to_local` | PASS |
| `test_step_editor_api::test_errors_block_save_warnings_do_not` | PASS |
| `test_step_editor_api::test_save_drops_empty_fields` | PASS |
| `test_step_editor_api::test_check_returns_uses_and_group_problems` | PASS |
| `test_step_editor_api::test_impact` | PASS |
| `test_step_editor_api::test_preview` | PASS |
| `test_step_editor_api::test_form_data` | PASS |
| `test_step_editor_api::test_routes_need_token` | PASS |
| `test_step_editor_api::test_step_edit_cli` | PASS |
| `test_step_editor_api::test_skill_create_step_runs_step_edit` | PASS |
| `test_step_editor_api::test_editor_page_has_step_form_controls` | PASS |
| `test_step_editor_api::test_check_warns_about_a_missing_command_script` | PASS |

## Full test suite

342 of 342 tests pass.

## Updated tests

- tests/test_catalog.py::test_replace_needs_flag_and_shows_diff: an invalid step file now stops Registry.load, so the test appends to push.md instead of overwriting it
- tests/conftest.py::write_step: default type is `ai` (version 2)
- tests/test_registry.py::test_group_paths_uses_and_outputs: replaces test_composite_paths_and_io; reads and writes became computed uses and declared outputs
- tests/test_registry.py::test_group_loop_refused: replaces test_composite_loop_refused; composite became group
- tests/test_editor_api.py::test_steps_list_and_detail: reads and writes became computed uses and declared outputs
- tests/test_step_delete.py (script and group tests): script became command with $FACTORY_STEP_DIR reference; composite became group
- tests/test_pipeline_check.py::test_valid_pipeline_has_no_problem and the problems test: reads and writes are gone; the reads warning returns in Task 10
- tests/test_engine.py (flow fixture, test_subagent_call_model_effort_precedence): writes became outputs, composite became group, reads removed
- tests/test_goto.py, tests/test_approval.py, tests/test_backlog.py: writes and reads became outputs and body keys
- tests/test_engine.py::test_next_done_check_fails_then_passes: `factory next` now prints the exact prompt and footer, never `--task`
- tests/test_engine.py::test_missing_config_asks: `factory next` now prints the exact prompt and footer, never `--task`
- tests/test_engine.py::test_subagent_call_model_effort_precedence: `factory next` now prints the exact prompt and footer, never `--task`
- tests/test_engine.py::test_next_tells_session_about_block_skip_and_goto: `factory next` now prints the exact prompt and footer, never `--task`
- tests/test_approval.py::test_awaiting_approval_then_approve: `factory next` now prints the exact prompt and footer, never `--task`
- tests/test_waiting.py::test_end_wait_adds_period_to_done_when: `factory next` now prints the exact prompt and footer, never `--task`
- tests/test_question_box.py::test_prompts_ask_in_plain_text: `factory next` now prints the exact prompt and footer, never `--task`
- tests/test_engine.py::test_run_script_gets_config_and_task: deleted; Task 6 replaces it with the run-command tests
- tests/test_minor_fixes.py::test_run_check_reports_missing_folder: run_check now takes the step as its third argument.
- tests/test_step_assistant.py (whole file): tasks without a worktree and the step assistant are removed
- tests/test_launch.py::test_no_worktree_pipeline_uses_task_flag: deleted; tasks without a worktree and the step assistant are removed
- tests/test_launch.py (start-session call check): tasks without a worktree and the step assistant are removed
- tests/test_terminal_cli.py::test_start_session_close_state_notify_wait_idle: tasks without a worktree and the step assistant are removed
- tests/test_terminal_cli.py::test_start_session_without_worktree_flag_or_args: replaced by test_start_session_has_no_worktree_flag; tasks without a worktree are removed
- tests/test_herdr_adapter.py::test_main_repo_uses_existing_workspace, test_main_repo_creates_workspace_when_missing: deleted; tasks without a worktree are removed
- tests/test_herdr_adapter.py (all start_session calls): in_worktree argument removed
- tests/test_adapters.py::start_session call: in_worktree argument removed
- tests/test_minor_fixes.py::test_pipeline_id_must_be_a_plain_string: the step assistant is removed; the copy check now uses a real source pipeline
- tests/test_step_hide.py::test_docs_describe_hide: tasks without a worktree and the step assistant are removed
- tests/test_session.py (live fixture): a task now needs a worktree to start a session
- tests/test_dashboard_api.py::test_actions_call_cli_functions: a task now needs a worktree to start a session
- tests/test_waiting.py (waits fixture): a task now needs a worktree to start a session
- tests/test_migrate.py::v2 (fixture): the data version default is now 2, so the fixture writes version 1 data
- tests/test_repo_version.py::test_version_mismatch_refused: version 2 is now current, so the mismatching data is version 1
- tests/test_repo_version.py::test_version_report_states: the current version is now 2
- tests/test_init_menu.py::test_init_creates_files_and_exclude: init now writes data version 2
- tests/test_library.py::test_commit_adds_changed_library_factory_yaml: the library was already at version 2, so the test changes it to 3 to make a real change
- tests/test_pipeline_check.py::test_each_problem_type: the `reads` warning was replaced by the computed-keys warning

## Definition Of Done

### Workflow Complete

- Plan exists under `plans/`, written before implementation: covered by `plans/2026-10-13-step-editor.md`. The build followed its tasks, one commit per task on the branch.
- Work is on `step-editor`, `master` is unchanged: `git log master -1 --format=%h` gives `6929935`, the branch base.
- Existing tests pass or are updated on purpose: covered by the full suite above (339 of 339) and the "Updated tests" list. `tests/e2e_herdr.py` was updated but not run, because it needs a real Herdr.

### Task keys

- Key name rule, types, missing type means `text`: covered by `test_keys::test_key_rule_and_env_name`, `test_pipeline_keys::test_bad_input_name_and_type_are_errors`.
- Three key sources and the factory keys (`task_id`, `description`, `summary`): covered by `test_pipeline_keys::test_keys_cli_text_and_json`, `test_keys_route`.
- "maybe set" for `summary` and optional outputs: covered by `test_pipeline_keys::test_keys_cli_text_and_json`.

### Pipeline inputs

- Input `type` and `description`: covered by `test_typed_inputs::test_pipeline_list_has_typed_inputs`.
- Dashboard text area for `long-text`: covered by `test_typed_inputs::test_dashboard_has_textarea_for_long_text`. Browser look: manual check 6.
- Menu tells the user they can write several lines: covered by the orchestrator instructions in `skills/software-factory/SKILL.md` (Launch a new pipeline). The text is not run by a test.
- `file` input: missing path is a dry run error, relative path saved as absolute: covered by `test_typed_inputs::test_missing_file_input_is_a_dry_run_error`, `test_relative_file_input_saved_absolute`. Browser check: manual check 6.

### Step format

- Types `ai`, `command`, `group`; `outputs`; `reads` removed; computed uses: covered by `test_step_format::test_valid_ai_step_has_no_error`, `test_load_errors`, `test_keys::test_outputs_and_leaf_uses`, `test_registry::test_group_paths_uses_and_outputs`.
- `ai` placeholders, `(not set)`, `{{config.<key>}}` check, `{{...}}` refused in `command`, single braces: covered by `test_keys::test_placeholders`, `test_step_format::test_load_errors`, `test_step_format::test_single_braces_are_not_placeholders`, `test_runtime_v2::test_next_prints_exact_prompt_then_footer`.
- `command` env variables and `FACTORY_STEP_DIR`: covered by `test_runtime_v2::test_command_next_and_env`, `test_command_key_value_is_never_run`.
- `group` step, loop refused, full path: covered by `test_registry::test_group_loop_refused`, `test_runtime_v2::test_group_step_shows_full_path`.
- `done_when` and `done_check` stay: covered by `test_engine::test_next_done_check_fails_then_passes`.

### Step runtime

- `factory next` prompt and footer, subagent prompt, `wait_external`: covered by `test_runtime_v2::test_next_prints_exact_prompt_then_footer`, `test_subagent_prompt_is_the_same_text_with_a_report_line`, `test_wait_external_ends_with_factory_wait`.
- `factory run-command` and `factory done` order of checks: covered by `test_runtime_v2::test_done_refused_until_command_exits_0`, `test_goto_clears_command_result`, `test_file_output_must_exist`.
- `factory state set` for `file` outputs, absolute path: covered by `test_runtime_v2::test_file_output_must_exist`, `test_state_set_file_relative_to_caller`.
- Catalog steps drop the `test -f` done checks: covered by `test_catalog::test_catalog_steps_are_version_2`.

### No more step assistant

- `new-step-assistant` and `new-step` removed: covered by `test_builtin::test_step_assistant_is_gone`.
- No main repository pipeline, no `--task` in printed commands, option stays: covered by `test_runtime_v2::test_next_prints_exact_prompt_then_footer`, `test_step_assistant::test_next_never_prints_task_flag`, `test_runtime_v2::test_first_prompt_never_adds_task_flag` and `test_terminal_cli::test_start_session_has_no_worktree_flag`.

### Built-in and catalog steps

- Built-in and catalog steps in the new format, real output types: covered by `test_builtin::test_builtin_steps_are_version_2`, `test_catalog::test_catalog_steps_are_version_2`, `test_catalog_steps_parse_with_registry`, `test_catalog_prompts_use_placeholders`.
- No project-specific skill or tool in the catalog: covered by `test_catalog::test_catalog_is_generic`.

### Migration from version 1 to version 2

- Conversion of every step type, `writes`, `reads`, `config` blocks, script body: covered by `test_migrate_v2::test_converts_every_type`, `test_every_converted_step_passes_version_2_validation`.
- Migrated pipeline runs to the end with the fake adapter: covered by `test_migrate_v2::test_migrated_pipeline_runs_to_the_end`.
- Refusals before any change (bad key name, unfinished `new-step-assistant` task): covered by `test_migrate_v2::test_bad_key_name_refuses_before_any_change`, `test_assistant_task_refuses_before_any_change`, `test_dry_run_lists_errors_without_change`.
- Library commit message and the `migrate` step: covered by `test_migrate_v2` and `test_migrate::test_older_refused_then_migrated`, `test_shared_library_migrated_once` (message `Factory library: migrate to version 2`).
- Migration of the user's real data: manual check 8.

### Available keys

- `factory pipeline keys` with `--at` and `--json`, sources, latest source wins: covered by `test_pipeline_keys::test_keys_cli_text_and_json`, `test_latest_source_wins`.
- Server route, same function: covered by `test_pipeline_keys::test_keys_route`.
- New pipeline check warnings: covered by `test_pipeline_keys::test_new_check_warnings`, `test_own_output_is_not_an_unset_key`.

### Step editor

- Step form in the pipeline editor, buttons New, Edit, Copy to local, Duplicate: covered by `test_step_editor_api::test_editor_page_has_step_form_controls`. Real browser behavior: manual checks 1 to 4.
- `factory step edit [<id>]` and menu action "Create a new step": covered by `test_step_editor_api::test_step_edit_cli`, `test_skill_create_step_runs_step_edit`. Browser check: manual check 7.
- Form fields and form data (categories, columns, levels): covered by `test_step_editor_api::test_form_data`. Drag and drop of group children and the look of the form: manual check 4.
- Duplicate id refused, hidden included: covered by `test_step_editor_api::test_duplicate_id_refused_hidden_included`.
- Available keys next to the body, insert by click: the keys by `test_pipeline_keys::test_keys_route`; the click is manual check 1 and 5.
- Preview: covered by `test_step_editor_api::test_preview`. Browser check: manual check 1.
- Save impact (pipelines, unfinished tasks, other repositories text): covered by `test_step_editor_api::test_impact`, `test_check_returns_uses_and_group_problems`. Browser check: manual check 2.
- Errors block, warnings do not: covered by `test_step_editor_api::test_errors_block_save_warnings_do_not`.
- Save new local and generic step, library commit offer: covered by `test_step_editor_api::test_save_new_local_step`, `test_save_generic_offers_commit`, `test_save_drops_empty_fields`. Real commit: manual check 2.
- Built-in cannot be edited, copy to local: covered by `test_step_editor_api::test_builtin_edit_refused_and_copy_to_local`. Browser check: manual check 3.
- Detail panel keys, outputs, children: covered by `test_editor_api::test_steps_list_and_detail`. Browser look: manual check 4.
- Requests without the token are rejected: covered by `test_step_editor_api::test_routes_need_token`.

### Orchestrator

- "Create a new step" runs `factory step edit`: covered by `test_step_editor_api::test_skill_create_step_runs_step_edit`. Browser opens the form: manual check 7.

### Documentation

- README sections for key types, step types, placeholders, outputs, variables, the form and the commands: covered by `test_docs::test_readme_sections`, `test_readme_describes_step_editor`.
- Every `factory` command in the README exists: covered by `test_docs::test_readme_commands_exist`, `test_skill_and_builtin_commands_exist`.
- Tutorial step "Create a step" uses the form, simple English: covered by `test_docs::test_readme_describes_step_editor`. Simple English is read by hand, not by a test.

### Verification

- Report at `verification/software-factory/step-editor-report.md`, one section per milestone, full suite result: this file, built by `software-factory/tests/report_step_editor.py` from `step-editor-junit.xml`.
- Test setup with test repository and test library: covered by the `inited` fixture in `software-factory/tests/conftest.py`.
- CLI test bullets: each is listed above under its feature.
- Manual browser check list: `verification/software-factory/step-editor-manual-check.md`.

### Gaps

None found in code. Manual-only: browser checks 1 to 8 in the manual check list, including the migration of the user's real data. `tests/e2e_herdr.py` was updated but not run.
