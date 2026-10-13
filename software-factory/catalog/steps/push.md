---
id: push
description: Push the branch to origin
category: git
type: command
outputs:
  branch:
    type: text
    description: The pushed branch
done_when: The branch is on origin with all local commits.
done_check: b=$(git symbolic-ref --short -q HEAD) && git rev-parse --verify -q "refs/remotes/origin/$b" >/dev/null && test -z "$(git log "origin/$b..HEAD" --oneline)"
required: false
requires: [git]
---

bash "$FACTORY_STEP_DIR/push.sh"
