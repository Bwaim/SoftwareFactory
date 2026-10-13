---
id: create-pr
description: Create a pull request or merge request with gh or glab
category: forge
type: ai
outputs:
  mr_url:
    type: text
    description: The URL of the pull request or merge request
done_when: The pull request or merge request exists and its URL is saved.
config:
  forge:
    description: The forge of this repository, `github` or `gitlab`
  target_branch:
    description: The branch the pull request targets
    default: main
required: false
column: Review
---

The forge is {{config.forge}}. The branch is {{branch}}. The target branch is {{config.target_branch}}.

1. When the forge is `github`, run `gh pr create --base {{config.target_branch}} --head {{branch}} --title "<title>" --body "<body>"`. When it is `gitlab`, run `glab mr create --target-branch {{config.target_branch}} --source-branch {{branch}} --title "<title>" --description "<body>" --yes`.
2. Write a short title and a body from the task description, the summary and the commits.

Task: {{description}}

Summary: {{summary}}
