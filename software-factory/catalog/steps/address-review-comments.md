---
id: address-review-comments
description: Read the open review comments and fix them
category: review
type: prompt
reads: [mr_url]
done_when: Every open review comment is fixed or answered.
required: false
config:
  forge:
    description: The forge of this repository, `github` or `gitlab`
---

1. Read the open comments: `gh pr view <mr_url> --comments` for `github`, `glab mr view <mr_url> --comments` for `gitlab`.
2. Fix each comment in the code. If a comment is wrong or unclear, ask the user before you answer it.
3. Commit the fixes and push the branch.
