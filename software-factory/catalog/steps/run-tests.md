---
id: run-tests
description: Run the test command of the repository
category: test
type: script
done_when: The test command passes.
done_check: bash -c "$FACTORY_CONFIG_TEST_COMMAND"
required: false
config:
  test_command:
    description: The command that runs the tests, for example `make test` or `npm test`
---

run-tests.sh
