---
id: commit
description: Commit the changes with a message in the repository's commit style
category: git
type: prompt
reads: [branch]
writes: [branch]
done_when: All changes are committed on a branch.
done_check: test -z "$(git status --porcelain)" && git symbolic-ref -q HEAD >/dev/null
required: false
---

1. If HEAD is detached, create a branch named after the task id: `git switch -c <task id>`. Save it with `factory state set branch <name>`.
2. Read `git log -n 10 --oneline` and follow the same message style.
3. Stage and commit all changes of the task. Do not commit unrelated files.
