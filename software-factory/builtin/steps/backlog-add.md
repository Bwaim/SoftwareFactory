---
id: backlog-add
description: Add an entry at the end of the backlog
category: backlog
type: ai
done_when: The entry is in the backlog.
required: false
---

Run in the orchestrator session.

1. Ask for the title, a short summary, and an optional pipeline id (`factory pipeline list --json` shows them).
2. Run `factory backlog add "<title>" --summary "<summary>"`, with `--pipeline <id>` when given.
