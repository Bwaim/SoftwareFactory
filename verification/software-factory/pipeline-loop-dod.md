## Definition Of Done

### Workflow Complete

- The plan is `plans/2026-10-13-pipeline-loop.md`. It was committed in the first commit of the branch, before the implementation.
- The work is on the branch `pipeline-loop`. `master` is unchanged.
- Every existing test still passes: see "Full test suite". Updated tests: see "Updated tests".

### Loop field

- `back_to`, `while`, `max`, the nearest `back_to`, a loop back to the entry itself, a group entry: covered by `test_loops::test_snapshot_positions`, `test_back_to_uses_the_nearest_earlier_entry`, `test_group_loop_back_to_itself`.

### Runtime

- Snapshot of each loop: `test_snapshot_positions`. A changed file does not change a running loop: the loop is read from `task.json` only, see `test_old_task_without_loops` for a task without loops.
- Jump, "Loop <n> of <max>" and `loop_back`: `test_review_loop_jumps_twice_then_moves_on`.
- Limit, block, reason and `loop_limit`: `test_limit_moves_on_and_blocks`. One more round with `factory goto`: `test_goto_after_limit_gives_one_more_round`.
- Limit on the last entry: `test_limit_on_last_entry_finishes`.
- Not set values: `test_is_set`, `test_not_set_values_move_on`.
- Skip: `test_skipped_loop_step_does_not_jump`.
- Reset of `started`, `command_result`, `approval`, task keys kept: `test_jump_resets_fields_and_keeps_keys`.
- Counts apart from `goto_counts`, no `goto` block: `test_three_loop_rounds_do_not_block_like_goto`, `test_group_loop_back_to_itself`.
- Count reset by an outer loop and by `factory goto`: `test_nested_inner_loop_resets_after_outer_jump`, `test_goto_resets_only_before_the_range`.
- Wait steps: `test_wait_step_loop_jumps_on_external_done`.
- Same session for session steps, new agent for subagent steps: the jump only moves the position. Real sessions: manual check 1.
- `factory status`: `test_status_shows_loop_count`, `test_status_shows_the_innermost_loop`.

### Footer

- `test_footer_line_only_on_the_controlling_step`, `test_footer_line_for_subagent_and_command`.

### Pipeline check

- Every error and warning: `test_check_errors_and_warnings`, `test_overlap_names_both_loops_and_nested_is_fine`.
- A key output later in the loop is available inside the range: `test_key_set_later_in_the_loop_is_available_inside_the_range`.

### Pipeline editor and dashboard

- Save and load with `loop` unchanged: `test_loop_authoring::test_editor_api_saves_and_loads_loop_unchanged` (server) and `test_editor_model_keeps_loop_on_load_and_save` (editor model, run with node).
- Entry form controls and row mark: `test_editor_page_has_loop_controls`. Browser look: manual check 3.
- Live checks: the editor calls `/api/pipelines/check`, see `test_editor_api_saves_and_loads_loop_unchanged`.
- Dashboard card: `test_task_row_shows_loop_count`. Browser look: manual check 4.

### Authoring skill and documentation

- Skill loop section, footer line, the rule to set the key to `none`, the two examples with a subagent review step: `test_authoring_skill::test_skill_documents_loops`, `test_examples_load_and_check_clean`.
- README: `test_loop_authoring::test_readme_documents_loops`.
- Every `factory` command in the README and the skills exists: `test_docs::test_readme_commands_exist`, `test_authoring_skill::test_skill_commands_exist`.

### Verification

- This report, and the manual check list `pipeline-loop-manual-check.md`.
