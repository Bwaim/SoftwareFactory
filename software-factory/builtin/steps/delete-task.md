---
id: delete-task
description: Delete a task, its session, terminal, worktree (if any) and local branch
category: factory
type: ai
done_when: The task folder is in the archive.
required: true
---

Run in the orchestrator session.

1. Run `factory delete <id> --dry-run --json` and show what will be removed, the uncommitted changes and the unpushed commits.
2. Ask the user to confirm. If there are uncommitted changes or unpushed commits, say it clearly and ask for explicit approval.
3. Run `factory delete <id>`, with `--confirm-unpushed` only after that explicit approval.
