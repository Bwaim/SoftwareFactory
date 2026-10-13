# Pipeline loops: design

Source: `prompts/factory_pipeline_loop.md`. Context: `prompts/factory_skill_creation.md` (pipeline fields, Task execution, pipeline editor, dashboard, events, authoring skill).

## 1. Goal

- A pipeline entry can repeat a range of steps while a task key is set, at most `max` times.
- The factory makes the jump in `factory done`. The session never runs `goto` for a loop.
- After `max` jumps with the key still set, the task moves on and is blocked for the user.

Not in scope:
- No new step type.
- No data version change. A task without loops in its snapshot works as today.
- No change to `factory goto`, its 3-jump limit or `goto_counts`.

## 2. The `loop` field

A pipeline `steps` entry can be a map with `loop`:

```yaml
steps:
  - write-spec
  - id: review-spec
    loop:
      back_to: write-spec
      while: findings
      max: 2
  - next-step
```

- `back_to`: the id of this entry or of an earlier entry. When the id appears more than once, the nearest one at or before this entry is used.
- `while`: a task key name.
- `max`: an integer from 1 to 20. It is the most jumps back for this loop.
- The entry can be a normal step or a group step.
- The **loop range** is the entries from the `back_to` entry to the loop entry, both included. In the task snapshot, it is the steps from the first step of the `back_to` entry to the last step of the loop entry.

## 3. Module layout

| File | Change |
| --- | --- |
| `lib/factory/loops.py` | New. Pure functions: `is_set(value)`, `entry_ranges(reg, entries)`, `snapshot(reg, pipeline)`, `loop_ending_at(task, position)`, `reset_counts(task, target, jumping=None)`, `current_loop(task)`, `controls_loop(task, step)`, `check(reg, entries)`. |
| `lib/factory/launch.py` | `new_task` adds `"loops": loops.snapshot(reg, pipeline)`. |
| `lib/factory/engine.py` | `done` and `end_wait` run the loop decision. `goto` resets loop counts. Footer line in `render_step`. `status_text` shows the loop count. |
| `lib/factory/render.py` | The footer takes an optional extra line. |
| `lib/factory/pipeline_check.py` | Calls `loops.check` and adds its problems. |
| `lib/factory/board.py` | `task_row` gets `loop`. |
| `lib/factory/web/editor.html` | Entry form edits `loop`. Row mark. Keeps `loop` on load and save. |
| `lib/factory/web/dashboard.html` | The card shows the loop count. |
| `skills/factory-authoring/SKILL.md` | Documents `loop`, with two examples. |
| `README.md` | `loop` in the pipeline fields, the review example, the events. |

`pipeline_store.compact` already keeps unknown entry fields. A test checks that `loop` survives a save and a load.

## 4. Task snapshot

- `launch.new_task` adds `task["loops"]`, a list. One item per loop entry:
  - `entry`: the id of the loop entry.
  - `back_to`: the id of the `back_to` entry.
  - `first`: the position of the first step of the `back_to` entry.
  - `last`: the position of the last step of the loop entry.
  - `while`: the key name.
  - `max`: the integer.
  - `jumps`: 0. The number of jumps made by this loop. It resets to 0 by the rule of section 5.6.
- Positions use `Registry.expand`. When the pipeline does not list `create-worktree`, the factory adds it first, so every position shifts by one. `loops.entry_ranges` uses the same rule.
- A step file or pipeline file changed later does not change a running loop.
- Old tasks have no `loops` key. The code reads `task.get("loops") or []`.
- Each position is the `last` of at most one loop, because one entry has at most one `loop`.

## 5. Runtime

### 5.1 Set or not set

`loops.is_set(value)`: false for a missing key, `None`, and a value that is empty or `none` after stripping spaces, ignoring case. `"none"`, `" None "`, `""`, `"  "` and a key never set are all not set.

### 5.2 `factory done`

After the existing checks pass (outputs, file paths, command result, `done_check`), and only then:

1. If the current position is the `last` of a loop, read the `while` key from the task state.
2. **Set, and `jumps < max`:** in the same `state.update` as the move:
   - `jumps += 1`.
   - `position = first`. Reset `started`, `command_result` and `approval`, as `factory goto` does. Status `active`. Task keys keep their values. `goto_counts` does not change.
   - Reset the counts of the loops inside, by section 5.6.
   - Events: `step_done` on the current step, then `loop_back` with `entry`, `to` (the path of the target step), `round` (the jump number `n`, after the increment) and `max`.
   - Output: "Loop <n> of <max>: back to `<step>`. Run `factory next`." `<n>` is the number of this jump, from 1 to `max`. `<step>` is the path of the target step.
3. **Set, and `jumps == max`:** in the same `state.update`, the task moves to the next step and is blocked:
   - Reason: "Loop limit reached on `<entry>`: `<key>` is still set".
   - Events: `step_done`, `loop_limit` with `entry` and `key`, then `task_blocked` with the reason.
   - A notification, as `factory block` sends.
   - Output: "Loop limit reached on `<entry>`: `<key>` is still set. The task is blocked. Ask the user what to do. When the user says to go on, run `factory unblock`. For one more round, after the user approves, run `factory goto "<path of the first step of back_to>" --reason "<why>"`."
4. **Not set:** the task moves to the next step, as today.
- A loop on the last entry of the pipeline that ends (key not set) finishes the task, as today.
- At the limit on the last entry, no next step exists. The task finishes as today. The factory also logs `loop_limit` and sends the notification "Task <id> finished, but the loop limit was reached on `<entry>`: `<key>` is still set." It is the only notification. `loop_limit` is logged before `task_finished`. The `factory done` output says the same. The pipeline check warns about this case (section 8).
- `factory skip` never runs the loop decision.

### 5.3 Wait steps

A `wait_external` step ends with `factory poll` or `factory external-done`, through `engine.end_wait`, not `factory done`. The same loop decision runs there. The message sent to the session is "The external event happened: <done_when>. <loop or limit message>".

### 5.4 Session

- The jump runs in the same task session. A `session` step that runs again keeps the conversation of the earlier rounds.
- A `subagent` step starts a new agent each time, as today.

### 5.5 `factory goto` after the limit

- The task is after the loop. `factory goto <back_to>` works as today and counts in `goto_counts`.
- A `goto` to the first step of the loop range does not reset the loop count (section 5.6). The loop keeps `jumps == max`. If the key is still set at the end of that round, the limit blocks the task again.

### 5.6 Count reset

- When the task jumps back to position `p`, by a loop or by `factory goto`, every loop whose range starts after `p` (`first > p`) gets `jumps = 0`.
- When loop `L` jumps back, every other loop inside `L`'s range (`first >= L.first` and `last <= L.last`) also gets `jumps = 0`. This covers an inner loop that starts on the same step as `L`.
- So an inner loop gets its full `max` in each round of an outer loop.
- A `goto` to the first step of a loop range does not reset that loop.
- `factory skip` and moves forward never reset a count.

## 6. Loop count display

- `loops.current_loop(task)`: among the loops whose range `first..last` holds the current position and whose `jumps >= 1`, take the innermost one (the smallest range). It returns `{"n": jumps, "max": max, "entry": entry}`, or `None`.
- `factory status`: the step line gets ", loop <n> of <max>". Example: `Step: review-spec (3 of 4), loop 1 of 2`.
- `board.task_row` gets `"loop"`: the same dict or `None`. The dashboard card shows "loop <n> of <max>" after the step.

## 7. Footer line

- `loops.controls_loop(task, step)`: the `while` keys of the loops whose range holds the current position, when the step outputs that key.
- For each such key, `factory next` adds one line to the footer, after the outputs: "This step controls a loop. Set `<key>` to `none` when nothing is left."
- It applies to `ai` steps in the session and in a subagent (inside the subagent prompt), and to `command` steps.
- For a `command` step, the line says: "This step controls a loop. The command sets `<key>` to `none` when nothing is left." The command footer forbids the session to set outputs.
- No other step gets the line.

## 8. Pipeline check

`loops.check(reg, entries)` returns problems. `pipeline_check.check` adds them.

Errors:
- `loop` is not a map: "Step `<id>`: `loop` must be a map with `back_to`, `while` and `max`."
- A field other than `back_to`, `while`, `max`: "Step `<id>`: `loop` has an unknown field `<f>`."
- `back_to` is not the id of this entry or of an earlier entry: "Step `<id>`: `loop.back_to` must be this step or an earlier step of the pipeline."
- `back_to` is `create-worktree`: "Step `<id>`: `loop.back_to` cannot be `create-worktree`. It cannot run again." The prompt does not list it. It follows from `factory goto`, which refuses `create-worktree`.
- `max` is not an integer from 1 to 20 (`true` and `2.0` are refused): "Step `<id>`: `loop.max` must be an integer from 1 to 20."
- `while` is not a valid key name: "Step `<id>`: `loop.while` must be a key name: lowercase letters, digits and `_`, starting with a letter."
- Two loops overlap without one being inside the other: "The loops of `<a>` and `<b>` overlap. One loop must be inside the other."
  - Ranges are entry index ranges. Two ranges overlap when they share an entry, and neither holds the other.

Warnings:
- No step inside the loop range outputs the `while` key: "Step `<id>`: no step inside the loop outputs `<key>`. The loop never ends early."
- The key is an optional output of every step inside the range that outputs it: "Step `<id>`: `<key>` is optional in every step that outputs it inside the loop."
- The loop entry is the last entry of the pipeline: "Step `<id>`: the loop is on the last step. At the limit, the task finishes without asking the user. Add a step after it, for example `user-validation`."
- Steps inside a group count, through `reg.leaves`.

Key flow inside a loop:
- The existing warning "Step `<id>` uses `<key>`, which no input, earlier step or factory key sets" ignores a key that a step inside the same loop range outputs. In a later round, that key is set. Example: `write-spec` uses `{{findings}}` from `review-spec`. Outside the range, the warning stays.

The range checks run only when `back_to` is valid. An entry whose step does not exist is skipped, because the check already reports it.

## 9. Pipeline editor

- `entryOf` reads `loop` into `{back_to, while, max}`, or no loop. `dataOf` writes `loop` back only when `back_to` is set. `max` is written as an integer.
- The entry form, under "Edit", gets a "loop" block:
  - `back_to`: a select with "(no loop)", this entry and the earlier entries, shown as "<n>. <id>". The value saved is the id.
  - `while`: a text input with a `datalist`. The list holds the keys available at the end of the entry, from `/api/pipelines/keys` with `at = i + 2` (1-based position after this entry). Free text is allowed.
  - `max`: a number input, 1 to 20, default 2.
- A row with a loop shows a tag "↺ <back_to> ×<max>", for example "↺ write-spec ×2".
- The live checks already call `/api/pipelines/check` on each change, so the new errors and warnings show without new code.

## 10. Dashboard

- The card line "`<pipeline> › <step>`" gets " · loop <n> of <max>" when `t.loop` is set.

## 11. Authoring skill

New section "Loops" in the format reference, and two examples in the "Examples" format (`####` path heading, one fenced block):
- **Review loop.**
  - `.factory/steps/write-spec.md`: an `ai` step. Outputs `spec` (`file`). It uses `{{findings}}` to fix the spec in a later round.
  - `.factory/steps/review-spec.md`: an `ai` step with `run_in: subagent`. Outputs `findings` (`long-text`, not optional). The prompt says to set `findings` to `none` when nothing is left.
  - `.factory/pipelines/spec-review.yaml`: the review example of section 2, then `user-validation`.
- **Ticket loop.**
  - `.factory/steps/split-tickets.md`: an `ai` step. Outputs `remaining` (`long-text`), one ticket per line.
  - `.factory/steps/pick-ticket.md`: an `ai` step. Outputs `ticket` and `remaining`. It takes the first line of `{{remaining}}`, sets `ticket` to it and `remaining` to the other lines, or `none`. When `remaining` is already `none` (zero tickets), it sets `ticket` to `none`.
  - `.factory/steps/build-ticket.md`: an `ai` step that implements `{{ticket}}`. When `ticket` is `none`, it does nothing.
  - `.factory/steps/ticket-round.md`: a `group` step with `pick-ticket` and `build-ticket`.
  - `.factory/pipelines/ticket-loop.yaml`: `split-tickets`, then `ticket-round` with `loop: {back_to: ticket-round, while: remaining, max: 20}`.
- The section says:
  - The fields and their rules.
  - The runtime: the jump, the loop message, the count reset, the limit and the block, `none`, skip.
  - The footer line.
  - Each step that outputs the `while` key must set it to `none` when nothing is left. Task keys keep their values, so a clean round must reset the key.
  - In a `command` step, the command sets the key itself.
- `test_examples_load_and_check_clean` checks the new pipelines too: no error and no warning.

## 12. README

- "Pipeline fields": `loop` with its three fields and the review example.
- A short "Loops" paragraph in Reference: the jump, the limit and the block, the footer line, "loop <n> of <max>" in `factory status` and on the card.
- "Events": a short list with `loop_back` and `loop_limit`. The README has no event list today, so the paragraph also says that events are in `.factory/tasks/<id>/events.jsonl`.

## 13. Tests

New file `tests/test_loops.py` (milestone 1):
- Review loop, key set twice then `none`: two jumps back, then the next step. The `factory done` outputs show "Loop 1 of 2" and "Loop 2 of 2". The `loop_back` events show `round` 1 and 2 with `max` 2.
- Key still set after `max` jumps: the task moves to the next step and is blocked with the limit reason. A `loop_limit` event is logged.
- Loop on a group entry back to itself: one round per value, until the key is `none`.
- Nested loops: an inner loop that reached its limit gets its full `max` again after the outer loop jumps back.
- A `goto` before a loop range resets its count. A `goto` to the first step of the range does not.
- At the limit on the last entry, the task finishes and a `loop_limit` event is logged.
- A `wait_external` loop step that ends with `factory external-done` makes the jump.
- `none`, ` None `, an empty value and a key never set count as not set (unit test of `is_set`, and one CLI run).
- A skipped loop step does not jump.
- Loop jumps do not change `goto_counts`. Three loop rounds do not block the task.
- The jump resets `command_result` and `approval`, and keeps task keys.
- Each check error and warning of section 8 on a test pipeline.
- The footer line on the step that outputs the `while` key inside the range, and on no other step: not on a step before the range, not on a step in the range that does not output the key.
- `factory status` shows "loop <n> of <max>", and the innermost loop when loops are nested.
- The snapshot: positions with and without a listed `create-worktree`, a group entry, and a nested loop.
- An old task without `loops` runs `factory done` as today.

Milestone 2:
- The pipeline editor API saves and loads a pipeline with `loop` unchanged (`tests/test_editor_api.py`).
- The editor page has the loop controls and the mark text (page source check).
- The dashboard API row has `loop` (`tests/test_dashboard_api.py`).
- The authoring skill examples load, and `factory pipeline check` on each example pipeline gives no error and no warning.
- Every `factory` command in the README and the skills exists (existing tests).

Report: `tests/report_pipeline_loop.py` writes `verification/software-factory/pipeline-loop-report.md` from `pipeline-loop-junit.xml`, with one section per milestone, the full suite and the updated tests.

## 14. Manual check list

`verification/software-factory/pipeline-loop-manual-check.md`:
1. Run a review loop pipeline with a real session. The spec step runs again in the same session with the findings. After the last round with findings left, the task is blocked.
2. Run a ticket loop pipeline with three tickets.
3. In the pipeline editor, add a loop to a pipeline. Check the mark and the live checks. Save.
4. Follow "loop <n> of <max>" on a dashboard card.

## 15. Decisions

User answers to the first spec review:
- D1: the text counts jumps: "Loop <n> of <max>", `<n>` from 1 to `max`.
- D2: at the limit on the last entry, the task finishes, logs `loop_limit` and notifies. The check warns about a loop on the last entry.
- D3: counts reset by the rule of section 5.6.
- D4: the loop decision also runs in `end_wait`.
- D5: the command wording of section 7.
- D6: `back_to: create-worktree` is an error.
- The ticket example handles zero tickets.
- D7 (found while planning): a key output inside a loop range counts as available for every step of the range, so the review example checks clean.
