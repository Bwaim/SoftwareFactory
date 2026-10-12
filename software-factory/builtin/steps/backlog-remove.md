---
id: backlog-remove
description: Remove an entry from the backlog
category: backlog
type: prompt
done_when: The entry is no longer in the backlog.
required: false
---

Run in the orchestrator session.

1. Run `factory backlog list --json` and show a numbered list.
2. Ask which entry to remove, and confirm.
3. Run `factory backlog remove <id>`.
