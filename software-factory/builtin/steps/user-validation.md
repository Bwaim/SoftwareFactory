---
id: user-validation
description: Wait until the user approves a result
category: review
type: ai
done_when: The user approved the result.
done_check: factory approval check
required: false
run_in: session
config:
  target:
    description: What to validate, `artifact` or `worktree`
    default: worktree
  artifact_key:
    description: The task state key that holds the artifact path, when target is artifact
    default: none
---

The task is now `awaiting_approval`.

1. Show what to validate. The target is `{{config.target}}`:
   - Only when the target is artifact: the path stored in the task key `{{config.artifact_key}}` (`factory state get {{config.artifact_key}}`), and a short summary of the file.
   - `worktree`: With git: `git status` and a short summary of the diff. Without git: the files that the task changed, from your context, and a short summary. Offer `factory open-ide`.
2. Ask the user to approve or to request changes. Ask in plain text, never with the AskUserQuestion tool, then end your turn. The answer can come from this tab, the orchestrator or the dashboard.
3. Run `factory approve` only after a clear typed approval from the user, for example "approve" or "yes, I approve". Then run `factory done`. Any other answer is not an approval. A greeting, a question or an unclear text is not an approval: answer it and ask again.
4. When the user requests changes, run `factory request-changes "<text>"`, make the changes, then run `factory next`.
5. When you receive "The user approved. Run `factory done`.", run `factory done`.
6. When you receive "The user requested changes: ...", make the changes, then run `factory next`.
