---
id: create-worktree
description: Create the task worktree from the latest origin base branch
category: git
type: ai
done_when: The worktree exists.
required: true
config:
  worktree_root:
    description: The folder where the factory creates the task worktrees
  base_ref:
    description: The branch the worktree starts from
    default: main
---

`factory launch` runs this step before the task session starts. A task session never runs it.
