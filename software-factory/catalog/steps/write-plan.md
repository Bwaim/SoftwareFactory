---
id: write-plan
description: Write an implementation plan from the spec
category: planning
type: skill
run_in: session
reads: [spec]
writes: [plan]
done_when: The plan file exists and its path is saved.
done_check: test -f "$(factory state get plan)"
required: false
requires: [/superpowers:writing-plans]
column: Plan
config:
  plan_style:
    description: Extra instructions for the plan, for example the commit size
    default: small commits
---

Run `/superpowers:writing-plans` on the spec file at `spec`, following `plan_style`.
Save the plan at the path printed by `factory artifact path plan.md`, not in the repository.
Save the path with `factory state set plan <path>`.
Stop when the plan is written. The next step asks the user to validate it.
