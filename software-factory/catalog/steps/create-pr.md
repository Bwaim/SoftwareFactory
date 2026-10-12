---
id: create-pr
description: Create a pull request or merge request with gh or glab
category: forge
type: prompt
reads: [branch, summary]
writes: [mr_url]
done_when: The pull request or merge request exists and its URL is saved.
done_check: test -n "$(factory state get mr_url)"
required: false
column: Review
config:
  forge:
    description: The forge of this repository, `github` or `gitlab`
  target_branch:
    description: The branch the pull request targets
    default: main
---

1. When `forge` is `github`, run `gh pr create --base <target_branch> --head <branch> --title "<title>" --body "<body>"`. When `forge` is `gitlab`, run `glab mr create --target-branch <target_branch> --source-branch <branch> --title "<title>" --description "<body>" --yes`.
2. Write a short title and a body from the task description, the summary and the commits.
3. Save the URL with `factory state set mr_url <url>`.
