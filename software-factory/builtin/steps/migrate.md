---
id: migrate
description: Migrate the factory data and the library to the current data version
category: factory
type: ai
done_when: factory version check reports the same version.
done_check: "factory version check --json | grep -q '\"state\": \"same\"'"
required: true
---

Run in the orchestrator session, before the menu.

1. Run `factory migrate --dry-run --json`. Show what will be migrated and backed up, the `errors` and the `warnings`. If there are errors, show them, tell the user how to fix them, and stop.
2. Run `factory migrate --json`. Show the summary, the warnings and the backup paths.
3. If the library changed and is in a git repository, show the changed files and the commit message `Factory library: migrate to version <n>`. Commit with `factory library commit` only after approval.
