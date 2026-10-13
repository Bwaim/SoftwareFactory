# Pipeline loops: manual checks

Use a test repository with the factory initialized and a test library in its own git repository. Never a real library or a real `.factory/`.

## Setup

1. Install the plugin from the branch `pipeline-loop`, or start Claude with `--plugin-dir <path to software-factory>`.
2. Copy the examples of the "Loop examples" section of `skills/factory-authoring/SKILL.md` into `.factory/steps/` and `.factory/pipelines/` of the test repository.
3. Run `factory pipeline check spec-review` and `factory pipeline check ticket-loop`. Expected: no problem.

## Checks

1. **Review loop with a real session.**
   - Launch `spec-review` with a description that has gaps, for example "Add a login page".
   - Expected: `review-spec` runs in a subagent and sets `findings`. `factory done` prints "Loop 1 of 2: back to `write-spec`."
   - Expected: `write-spec` runs again in the same session, with the findings in its prompt.
   - Expected: after the second jump, if findings remain, the task moves to `user-validation` and is blocked with "Loop limit reached on `review-spec`: `findings` is still set".
2. **Ticket loop with three tickets.**
   - Launch `ticket-loop` with a description of three small changes.
   - Expected: `pick-ticket` and `build-ticket` run three times. "Loop 1 of 20" and "Loop 2 of 20" appear. After the third ticket, `remaining` is `none` and the task moves to `user-validation`.
3. **Pipeline editor.**
   - Run `factory pipeline edit spec-review`.
   - Expected: the row `review-spec` shows "↺ write-spec ×2".
   - Click "Edit" on `review-spec`. Change `max` to 0. Expected: the live checks show "Step `review-spec`: `loop.max` must be an integer from 1 to 20." Set it back to 2.
   - Pick a `while` key from the list. Save. Expected: the saved file keeps `loop`.
4. **Dashboard card.**
   - Run `factory dashboard` while the review loop of check 1 runs.
   - Expected: after the first jump, the card shows "loop 1 of 2" after the step.

Write the result of each check: pass or fail, with what you saw.
