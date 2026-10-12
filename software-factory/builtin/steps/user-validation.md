---
id: user-validation
description: Wait until the user approves a result
category: review
type: prompt
done_when: The user approved the result.
done_check: factory approval check
required: false
run_in: session
config:
  target:
    description: What to validate, `artifact` or `worktree`
    default: worktree
  artifact_key:
    description: The task state key that holds the artifact path, when target is artifact
    default: ""
---

The task is now `awaiting_approval`.

1. Show what to validate:
   - When `target` is `artifact`: the path stored in the task state key named by `artifact_key`, and a short summary of the file.
   - When `target` is `worktree`: `git status` and a short summary of the diff. Offer `factory open-ide`.
2. Ask the user to approve or to request changes. The user can also answer from the dashboard.
3. When the user approves here, run `factory approve`, then `factory done`.
4. When the user requests changes here, run `factory request-changes "<text>"`, make the changes, then run `factory next`.
5. When you receive "The user approved. Run `factory done`.", run `factory done`.
6. When you receive "The user requested changes: ...", make the changes, then run `factory next`.
