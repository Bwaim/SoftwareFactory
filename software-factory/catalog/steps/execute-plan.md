---
id: execute-plan
description: Execute the implementation plan
category: build
type: skill
run_in: session
reads: [plan]
done_when: Every task of the plan is done and committed.
required: false
requires: [/superpowers:executing-plans]
column: Implementation
---

Run `/superpowers:executing-plans` on the plan file at `plan`.
Work in this worktree. When the skill offers to finish the branch, stop there: the next steps run the tests, push and create the pull request.
