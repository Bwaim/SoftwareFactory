---
id: review
description: Review the branch diff and save the findings as an artifact
category: review
type: prompt
run_in: subagent
model: opus
effort: high
writes: [review]
done_when: The review file exists and its path is saved.
done_check: test -f "$(factory state get review)"
required: false
config:
  base_ref:
    description: The base branch to compare with
    default: main
---

1. Run `git fetch origin <base_ref>` and read `git diff origin/<base_ref>...HEAD`.
2. Find real problems: bugs, missing tests, security issues. Skip style comments.
3. Write the findings to `$(factory artifact path review.md)`, one numbered item per finding with the file and line.
4. Save the path with `factory state set review <path>`.
