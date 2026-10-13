---
id: brainstorm
description: Brainstorm the task with the user and write a spec
category: planning
type: ai
outputs:
  spec:
    type: file
    description: The spec file
done_when: The spec file is written and its path is saved.
required: false
run_in: session
requires: [/superpowers:brainstorming]
column: Specification
---

Run `/superpowers:brainstorming` on this task.

Task: {{description}}

Summary: {{summary}}

Save the spec file at the path printed by `factory artifact path spec.md`, not in the repository.
Stop when the spec is written. The next step asks the user to validate it.
