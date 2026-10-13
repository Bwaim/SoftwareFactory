# Updated tests

- tests/test_authoring_skill.py::test_examples_load_and_check_clean: the skill has two new example pipelines, `spec-review` and `ticket-loop`. The test now checks all three example pipelines.
- tests/conftest.py `task_from_pipeline` (a helper, not a test): it now saves the loops of the pipeline in the task snapshot, as `factory launch` does.
