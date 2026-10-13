# Pipeline loop verification report

Date: 2026-10-14 00:00

## Milestone 1. Loop runtime

31 of 31 tests pass.

| Test | Result |
|---|---|
| `test_loops::test_is_set` | PASS |
| `test_loops::test_snapshot_positions` | PASS |
| `test_loops::test_check_errors_and_warnings` | PASS |
| `test_loops::test_overlap_names_both_loops_and_nested_is_fine` | PASS |
| `test_loops::test_back_to_uses_the_nearest_earlier_entry` | PASS |
| `test_loops::test_key_set_later_in_the_loop_is_available_inside_the_range` | PASS |
| `test_loops::test_review_loop_jumps_twice_then_moves_on` | PASS |
| `test_loops::test_limit_moves_on_and_blocks` | PASS |
| `test_loops::test_goto_after_limit_gives_one_more_round` | PASS |
| `test_loops::test_limit_on_last_entry_finishes` | PASS |
| `test_loops::test_group_loop_back_to_itself` | PASS |
| `test_loops::test_nested_inner_loop_resets_after_outer_jump` | PASS |
| `test_loops::test_goto_resets_only_before_the_range` | PASS |
| `test_loops::test_not_set_values_move_on` | PASS |
| `test_loops::test_skipped_loop_step_does_not_jump` | PASS |
| `test_loops::test_three_loop_rounds_do_not_block_like_goto` | PASS |
| `test_loops::test_jump_resets_fields_and_keeps_keys` | PASS |
| `test_loops::test_wait_step_loop_jumps_on_external_done` | PASS |
| `test_loops::test_old_task_without_loops` | PASS |
| `test_loops::test_footer_line_only_on_the_controlling_step` | PASS |
| `test_loops::test_footer_line_for_subagent_and_command` | PASS |
| `test_loops::test_status_shows_loop_count` | PASS |
| `test_loops::test_status_shows_the_innermost_loop` | PASS |
| `test_loops::test_limit_message_text` | PASS |
| `test_loops::test_limit_is_one_atomic_update` | PASS |
| `test_loops::test_loop_decision_reads_the_key_inside_the_update` | PASS |
| `test_loops::test_limit_on_last_entry_sends_one_notification` | PASS |
| `test_loops::test_limit_through_end_wait` | PASS |
| `test_loops::test_inner_loop_on_the_same_first_step_gets_its_full_max_again` | PASS |
| `test_loops::test_running_task_keeps_its_loop_snapshot` | PASS |
| `test_loops::test_check_skips_the_loop_of_an_unknown_step` | PASS |

## Milestone 2. Loop authoring

21 of 21 tests pass.

| Test | Result |
|---|---|
| `test_authoring_skill::test_skill_file_and_frontmatter` | PASS |
| `test_authoring_skill::test_skill_commands_exist` | PASS |
| `test_authoring_skill::test_fallback_factory_path_exists` | PASS |
| `test_authoring_skill::test_examples_load_and_check_clean` | PASS |
| `test_authoring_skill::test_example_command_step_runs` | PASS |
| `test_authoring_skill::test_every_field_is_described` | PASS |
| `test_authoring_skill::test_named_builtin_steps_exist` | PASS |
| `test_authoring_skill::test_readme_describes_authoring_skill` | PASS |
| `test_authoring_skill::test_skill_covers_review_findings` | PASS |
| `test_authoring_skill::test_skill_documents_loops` | PASS |
| `test_docs::test_readme_commands_exist` | PASS |
| `test_docs::test_skill_and_builtin_commands_exist` | PASS |
| `test_docs::test_readme_sections` | PASS |
| `test_docs::test_checker_scans_fenced_blocks_and_inline_spans_but_not_prose` | PASS |
| `test_docs::test_readme_describes_step_editor` | PASS |
| `test_loop_authoring::test_editor_api_saves_and_loads_loop_unchanged` | PASS |
| `test_loop_authoring::test_editor_page_has_loop_controls` | PASS |
| `test_loop_authoring::test_editor_model_keeps_loop_on_load_and_save` | PASS |
| `test_loop_authoring::test_editor_back_to_lists_nearest_ids_and_missing_target` | PASS |
| `test_loop_authoring::test_task_row_shows_loop_count` | PASS |
| `test_loop_authoring::test_readme_documents_loops` | PASS |

## Full test suite

398 of 398 tests pass.

## Updated tests

- tests/test_authoring_skill.py::test_examples_load_and_check_clean: the skill has two new example pipelines, `spec-review` and `ticket-loop`. The test now checks all three example pipelines.
- tests/conftest.py `task_from_pipeline` (a helper, not a test): it now saves the loops of the pipeline in the task snapshot, as `factory launch` does.

## Definition Of Done

### Workflow Complete

- The plan is `plans/2026-10-13-pipeline-loop.md`. It was committed in the first commit of the branch, before the implementation.
- The work is on the branch `pipeline-loop`. `master` is unchanged.
- Every existing test still passes: see "Full test suite". Updated tests: see "Updated tests".

### Loop field

- `back_to`, `while`, `max`, the nearest `back_to`, a loop back to the entry itself, a group entry: covered by `test_loops::test_snapshot_positions`, `test_back_to_uses_the_nearest_earlier_entry`, `test_group_loop_back_to_itself`.

### Runtime

- Snapshot of each loop: `test_snapshot_positions`. A changed file does not change a running loop: `test_running_task_keeps_its_loop_snapshot`. A task without loops: `test_old_task_without_loops`.
- Jump, "Loop <n> of <max>" and `loop_back`: `test_review_loop_jumps_twice_then_moves_on`.
- Limit, block, reason and `loop_limit`: `test_limit_moves_on_and_blocks`. The limit message: `test_limit_message_text`. Move and block in one update: `test_limit_is_one_atomic_update`. The loop decision reads the key inside the update: `test_loop_decision_reads_the_key_inside_the_update`. One more round with `factory goto`: `test_goto_after_limit_gives_one_more_round`.
- Limit on the last entry: `test_limit_on_last_entry_finishes`. One notification only: `test_limit_on_last_entry_sends_one_notification`.
- Not set values: `test_is_set`, `test_not_set_values_move_on`.
- Skip: `test_skipped_loop_step_does_not_jump`.
- Reset of `started`, `command_result`, `approval`, task keys kept: `test_jump_resets_fields_and_keeps_keys`.
- Counts apart from `goto_counts`, no `goto` block: `test_three_loop_rounds_do_not_block_like_goto`, `test_group_loop_back_to_itself`.
- Count reset by an outer loop and by `factory goto`: `test_nested_inner_loop_resets_after_outer_jump`, `test_goto_resets_only_before_the_range`. An inner loop that starts on the same step as its outer loop: `test_inner_loop_on_the_same_first_step_gets_its_full_max_again`.
- Wait steps: `test_wait_step_loop_jumps_on_external_done`. The limit through a wait step: `test_limit_through_end_wait`.
- Same session for session steps, new agent for subagent steps: the jump only moves the position. Real sessions: manual check 1.
- `factory status`: `test_status_shows_loop_count`, `test_status_shows_the_innermost_loop`.

### Footer

- `test_footer_line_only_on_the_controlling_step`, `test_footer_line_for_subagent_and_command`.

### Pipeline check

- Every error and warning: `test_check_errors_and_warnings`, `test_overlap_names_both_loops_and_nested_is_fine`. An entry with an unknown step gets no loop check: `test_check_skips_the_loop_of_an_unknown_step`.
- A key output later in the loop is available inside the range: `test_key_set_later_in_the_loop_is_available_inside_the_range`.

### Pipeline editor and dashboard

- Save and load with `loop` unchanged: `test_loop_authoring::test_editor_api_saves_and_loads_loop_unchanged` (server) and `test_editor_model_keeps_loop_on_load_and_save` (editor model, run with node).
- Entry form controls and row mark: `test_editor_page_has_loop_controls`. The `back_to` list shows the nearest entry of each id and a missing target: `test_editor_back_to_lists_nearest_ids_and_missing_target` (run with node). Browser look: manual check 3.
- Live checks: the editor calls `/api/pipelines/check`, see `test_editor_api_saves_and_loads_loop_unchanged`.
- Dashboard card: `test_task_row_shows_loop_count`. Browser look: manual check 4.

### Authoring skill and documentation

- Skill loop section, footer line, the rule to set the key to `none`, the two examples with a subagent review step: `test_authoring_skill::test_skill_documents_loops`, `test_examples_load_and_check_clean`.
- README: `test_loop_authoring::test_readme_documents_loops`.
- Every `factory` command in the README and the skills exists: `test_docs::test_readme_commands_exist`, `test_authoring_skill::test_skill_commands_exist`.

### Verification

- This report, and the manual check list `pipeline-loop-manual-check.md`.
