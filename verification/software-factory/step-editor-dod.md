## Definition Of Done

### Workflow Complete

- Plan exists under `plans/`, written before implementation: covered by `plans/2026-10-13-step-editor.md`. The build followed its tasks, one commit per task on the branch.
- Work is on `step-editor`, `master` is unchanged: `git log master -1 --format=%h` gives `6929935`, the branch base.
- Existing tests pass or are updated on purpose: covered by the full suite above and the "Updated tests" list. `tests/e2e_herdr.py` was updated but not run, because it needs a real Herdr.

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
- A `command` step whose command sets the wrong key: `factory run-command` names the missing output, and the `factory next` text has no `factory state set` line: covered by `test_runtime_v2::test_command_sets_wrong_key`.
- `factory done` on a `command` step with a missing output names the output and says `factory block`, never `factory state set`. An `ai` step keeps the `factory state set` message: covered by `test_runtime_v2::test_command_sets_wrong_key`, `test_done_refused_until_command_exits_0`, `test_file_output_must_exist`.
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
