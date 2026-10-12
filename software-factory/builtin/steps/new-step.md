---
id: new-step
description: Ask the user for a new step, write it, and add it to pipelines
category: factory
type: prompt
run_in: session
done_when: The step file is written after approval, and the chosen pipelines are updated.
required: false
---

You create one new factory step with the user. Ask one question at a time.

1. Ask where to save the step:
   - Generic: in `<library>/steps/` (the library path is in `.factory/factory.yaml`, key `library`), reusable in any repository that uses this library.
   - Local: in `.factory/steps/` of this repository, only for this repository.
2. Ask the goal of the step.
3. Ask its type: `prompt`, `skill`, `script` or `composite`. For a composite, show `factory step list` and ask which steps to use, in order.
4. Ask its category. First show the existing categories from `factory step list --json` (field `category`), so the user reuses one when it fits.
5. Ask what it reads from and writes to the task state.
6. Ask its done condition. Offer a `done_check` shell command when one is possible.
7. Ask where it runs: in the session or in a subagent. If the step asks the user anything, it must run in the session.
8. For a subagent: ask its `model` and `effort`.
9. Ask its config keys, each with a description and an optional default value.
10. Ask if it must never be skipped (`required`).
11. Ask its board column, if any (`factory menu` is not needed: the columns are in `.factory/factory.yaml`).

Before writing:
- Run `factory step list`. If a similar generic or local step exists, show it with `factory step show <id>` and propose to reuse or update it.
- Choose a unique lowercase id: letters, digits, `-` or `_`, starting with a letter.

Then:
- Show the full step file: YAML frontmatter with `id, description, category, type, reads, writes, done_when, done_check, config, required, run_in, model, effort, requires, column, wait_external` (only the fields that apply), then the body. A composite step has a `steps` list and no body. A script step body is the script file name, and the script file goes next to the step file.
- Write the file only after the user approves.
- For a generic step, show the file and the message `Factory library: add step <id>`, and run `factory library commit "<message>" <path>...` only after approval. Pass every file written for the step: the `.md` file and, for a script step, its `.sh` file.

At the end:
- Run `factory pipeline list`. Ask if the new step should be added to some pipelines, and where.
- For each approved pipeline, edit its YAML file, run `factory pipeline check <id>`, and fix every error. For a generic pipeline, offer the library commit `Factory library: update pipeline <id>`.
