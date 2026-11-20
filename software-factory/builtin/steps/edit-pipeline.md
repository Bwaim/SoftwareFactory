---
id: edit-pipeline
description: Create a pipeline or change an existing pipeline
category: factory
type: ai
done_when: The pipeline file is written and `factory pipeline check` reports no error for it.
required: false
---

Run in the orchestrator session.

1. Ask the user which pipeline to create or change. Run `factory pipeline list --json` to show the existing pipelines.
2. Collect what the pipeline needs. Ask the user for each item that is missing:
   - the input parameters: the keys the launch asks for,
   - the steps to use, in order. Run `factory step list --all --json` to show them.
   - whether the pipeline runs in a worktree. Set `worktree: true` or `worktree: false` in every pipeline you write.
3. Write the pipeline with the skill `/software-factory:factory-authoring`. Give it the answers of the user.
