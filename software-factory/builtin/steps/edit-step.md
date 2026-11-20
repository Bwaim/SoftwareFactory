---
id: edit-step
description: Create a step or change an existing step
category: factory
type: ai
done_when: The step file is written and `factory pipeline check` reports no error for any pipeline.
required: false
---

Run in the orchestrator session.

1. Ask the user which step to create or change. Run `factory step list --all --json` to show the existing steps.
2. Collect what the step needs. Ask the user for each item that is missing:
   - the parameters in: the keys and config keys the step uses,
   - the parameters out: the outputs the step sets,
   - what the step does,
   - when the step is done.
3. Write the step with the skill `/software-factory:factory-authoring`. Give it the answers of the user.
