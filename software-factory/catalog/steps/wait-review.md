---
id: wait-review
description: Wait until the pull request or merge request is approved
category: forge
type: prompt
reads: [mr_url]
done_when: The pull request or merge request is approved.
done_check: 'if [ "$FACTORY_CONFIG_FORGE" = github ]; then gh pr view "$(factory state get mr_url)" --json reviewDecision -q .reviewDecision | grep -qx APPROVED; else glab api "projects/:id/merge_requests/$(basename "$(factory state get mr_url)")/approvals" | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get(\"approved\") else 1)"; fi'
wait_external: true
required: false
column: Review
config:
  forge:
    description: The forge of this repository, `github` or `gitlab`
---

Tell the user the pull request is waiting for review, with its URL (`mr_url`).
Then run `factory wait`.
