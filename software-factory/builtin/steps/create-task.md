---
id: create-task
description: Create a task from a pipeline, with its worktree and session
category: factory
type: prompt
reads: []
writes: []
done_when: The task exists and its session started.
required: true
---

Run in the orchestrator session, never in a task session.

1. Collect the pipeline id, the description and every pipeline input from the user. Offer to start from a backlog entry first (`factory backlog list --json`).
2. Run `factory launch <pipeline> --description "<text>" --input <key>=<value> ... --dry-run --json` and show the result: task id, worktree path, branch case, missing inputs, missing config and errors.
3. For each missing config value, ask the user and run `factory config set <step> <key> <value>`. Then run the dry run again.
4. Launch only after the user confirms: the same command without `--dry-run`. Add `--from-backlog <id>` when started from a backlog entry.
