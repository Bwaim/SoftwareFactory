---
id: wait-review
description: Wait until the pull request or merge request is approved
category: forge
type: ai
done_when: The pull request or merge request is approved.
done_check: 'if [ "$FACTORY_CONFIG_FORGE" = github ]; then gh pr view "$FACTORY_KEY_MR_URL" --json reviewDecision -q .reviewDecision | grep -qx APPROVED; elif [ "$FACTORY_CONFIG_FORGE" = gitlab ]; then glab api "projects/:id/merge_requests/$(basename "$FACTORY_KEY_MR_URL")/approvals" | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get(\"approved\") else 1)"; else exit 1; fi'
wait_external: true
required: false
column: Review
config:
  forge:
    description: The forge of this repository, `github` or `gitlab`
---

Tell the user the pull request {{mr_url}} is waiting for review.
Then run `factory wait`.

On GitHub, the check needs a required review: without it, `reviewDecision` stays empty and the wait never ends. Then mark it done by hand.
