---
id: brainstorm
description: Brainstorm the task with the user and write a spec
category: planning
type: skill
run_in: session
reads: [summary]
writes: [spec]
done_when: The spec file exists and its path is saved.
done_check: test -f "$(factory state get spec)"
required: false
requires: [/superpowers:brainstorming]
column: Specification
---

Run `/superpowers:brainstorming` on the task description and the `summary`.
Save the spec file at the path printed by `factory artifact path spec.md`, not in the repository.
Save the path with `factory state set spec <path>`.
Stop when the spec is written. The next step asks the user to validate it.
