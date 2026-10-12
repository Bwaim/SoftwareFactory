---
id: rebase
description: Rebase the branch on the latest origin base branch
category: git
type: prompt
done_when: The branch is rebased on origin/<base_ref> and has no conflict.
required: false
config:
  base_ref:
    description: The base branch to rebase on
    default: main
---

1. Run `git fetch origin <base_ref>` and `git rebase origin/<base_ref>`.
2. Resolve simple conflicts: imports, formatting, independent changes in the same file.
3. On a complex conflict, run `git rebase --abort`, then `factory block "Complex rebase conflict in <files>"`, and explain the conflict to the user.
