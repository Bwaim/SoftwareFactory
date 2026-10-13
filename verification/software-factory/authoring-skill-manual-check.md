# Authoring skill: manual checks

Use a test repository with the factory initialized and a test library in its own git repository. Never a real library or a real `.factory/`.

## Setup

1. Install the plugin from this branch: `/plugin marketplace add <path to the SoftwareFactory folder>`, then `/plugin install software-factory@software-factory`. Restart Claude.
2. In the test repository, check that `.factory/factory.yaml` exists and that its `library` key points to the test library.
3. Write the file `prompts/crash-pipeline.md` in the test repository:

   ```markdown
   # Crash fix pipeline

   - Input: `crash_log`, the path of a crash log file.
   - Step 1, a command: copy the last 200 lines of the log into an artifact. The artifact is a file output.
   - Step 2, the agent: read that artifact, find the cause of the crash and fix it.
   - Step 3: the user validates the change.
   ```

## Checks

1. **The skill loads from a request.** Start a normal Claude session in the test repository, not the orchestrator. Ask: "Implement `prompts/crash-pipeline.md`".
   - Expected: the `factory-authoring` skill loads.
   - Expected: the agent writes local files under `.factory/steps/` and `.factory/pipelines/`: one `ai` step, one `command` step with a `file` output, and a pipeline with the input `crash_log`.
   - Expected: the agent runs `factory pipeline check <id>`, and the last run has no error.
2. **The pipeline runs.** Launch the new pipeline from the orchestrator or with `factory launch <id> --input crash_log=<path>`. Run it to the end.
   - Expected: the command step sets its output, the `ai` step reads it, and the task ends `finished`.
3. **A generic step.** Ask: "Create a generic factory step that runs `make lint`".
   - Expected: the file is in `<library>/steps/`.
   - Expected: the agent offers `factory library commit "Factory library: add step <id>" <path>` and commits only after you approve.
4. **A changed step.** Ask: "Change the step `<id of step 2>` so it also writes a short summary".
   - Expected: the agent runs `factory pipeline list --json`, then `factory pipeline check` on every listed pipeline, including the one that uses the step.
5. **Direct call.** Run `/factory-authoring Create a local step that prints the git status`.
   - Expected: the skill runs with this request and writes the step.

Write the result of each check: pass or fail, with what you saw.
