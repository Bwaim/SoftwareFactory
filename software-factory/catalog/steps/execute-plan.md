---
id: execute-plan
description: Execute the implementation plan
category: build
type: ai
run_in: session
done_when: Every task of the plan is done and committed.
required: false
requires: [/superpowers:executing-plans]
column: Implementation
---

Run `/superpowers:executing-plans` on the plan file {{plan}}.
Work in this worktree. When the skill offers to finish the branch, stop there: the next steps run the tests, push and create the pull request.
