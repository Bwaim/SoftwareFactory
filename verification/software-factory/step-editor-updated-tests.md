# Updated tests
- tests/test_catalog.py::test_replace_needs_flag_and_shows_diff: an invalid step file now stops Registry.load, so the test appends to push.md instead of overwriting it
- tests/conftest.py::write_step: default type is `ai` (version 2)
- tests/test_registry.py::test_group_paths_uses_and_outputs: replaces test_composite_paths_and_io; reads and writes became computed uses and declared outputs
- tests/test_registry.py::test_group_loop_refused: replaces test_composite_loop_refused; composite became group
- tests/test_editor_api.py::test_steps_list_and_detail: reads and writes became computed uses and declared outputs
- tests/test_step_delete.py (script and group tests): script became command with $FACTORY_STEP_DIR reference; composite became group
- tests/test_pipeline_check.py::test_valid_pipeline_has_no_problem and the problems test: reads and writes are gone; the reads warning returns in Task 10
- tests/test_engine.py (flow fixture, test_subagent_call_model_effort_precedence): writes became outputs, composite became group, reads removed
- tests/test_goto.py, tests/test_approval.py, tests/test_backlog.py: writes and reads became outputs and body keys
