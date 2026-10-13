---
id: review
description: Review the branch diff and save the findings as an artifact
category: review
type: ai
outputs:
  review:
    type: file
    description: The review findings
done_when: The review file is written and its path is saved.
config:
  base_ref:
    description: The base branch to compare with
    default: main
required: false
run_in: subagent
model: opus
effort: high
---

1. Run `git fetch origin {{config.base_ref}}` and read `git diff origin/{{config.base_ref}}...HEAD`.
2. Find real problems: bugs, missing tests, security issues. Skip style comments.
3. Write the findings to the path printed by `factory artifact path review.md`, one numbered item per finding with the file and line.
