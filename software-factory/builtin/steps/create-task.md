---
id: create-task
description: Create a task from a pipeline, with its worktree (if any) and session
category: factory
type: ai
done_when: The task exists and its session started.
required: true
---

Run in the orchestrator session, never in a task session.

1. Collect the pipeline id, the description and every pipeline input from the user. Offer to start from a backlog entry first (`factory backlog list --json`). `factory pipeline list --json` gives the inputs of each pipeline, with their type and description:
   - `text`: ask for one line.
   - `long-text`: tell the user they can write several lines.
   - `file`: ask for a path, absolute or relative to the main repository.
2. Run `factory launch <pipeline> --description "<text>" --input <key>=<value> ... --dry-run --json` and show the result: task id, worktree path (if any), branch case, missing inputs, missing config and errors.
3. For each missing config value, ask the user and run `factory config set <step> <key> <value>`. Then run the dry run again.
4. Launch only after the user confirms: the same command without `--dry-run`. Add `--from-backlog <id>` when started from a backlog entry.
