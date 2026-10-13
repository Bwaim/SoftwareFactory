---
id: write-plan
description: Write an implementation plan from the spec
category: planning
type: ai
outputs:
  plan:
    type: file
    description: The implementation plan
done_when: The plan file is written and its path is saved.
config:
  plan_style:
    description: Extra instructions for the plan, for example the commit size
    default: small commits
required: false
run_in: session
requires: [/superpowers:writing-plans]
column: Plan
---

Run `/superpowers:writing-plans` on the spec file {{spec}}, following this style: {{config.plan_style}}.
Save the plan at the path printed by `factory artifact path plan.md`, not in the repository.
Stop when the plan is written. The next step asks the user to validate it.
