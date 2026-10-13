---
id: run-tests
description: Run the test command of the repository
category: test
type: command
done_when: The test command passes.
required: false
config:
  test_command:
    description: The command that runs the tests, for example `make test` or `npm test`
---

bash "$FACTORY_STEP_DIR/run-tests.sh"
