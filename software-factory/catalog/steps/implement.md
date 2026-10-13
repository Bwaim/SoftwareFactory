---
id: implement
description: Do the task described in the task description and summary
category: code
type: ai
done_when: The change is made in the worktree and the code builds.
required: false
column: Implementation
---

Task: {{description}}

Summary: {{summary}}

Make the change in this worktree. Keep it small and focused.
If something is unclear, run `factory block "<question>"`, ask the user, then run `factory unblock` when the user answers.
