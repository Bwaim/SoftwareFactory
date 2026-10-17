# Token optimization: analysis and next steps

Working notes, started 2026-10-18. Resume from here. Update the "Log" section after each change and its measure.

## Goal

- Lower the token cost of the factory pipelines, without losing quality.
- One change at a time. Measure each change on enough tasks before the next one. Document the impact.

## Principle

- A task should not need a long context. Its state is in artifacts: analysis → spec → plan → implementation → review.
- So each phase should work from the artifacts, not from the whole history of the task.

## Baseline (2026-10-18, one-off script)

- Script: `prompts/token_optimization_per_step.py`. It reads the transcripts in `~/.claude/projects/` and the `events.jsonl` of each task, and gives each API call to the step that was running.
- One API call can appear on several transcript lines with the same `message.id`. The script counts it once. A first version did not, and gave numbers about 1.6 times too high.
- Tasks of `NEXTORY_REPO`. `ht-4567` was still running.

| Task | Pipeline | Session calls | Largest context | Session reads | Subagent reads | Biggest step |
|---|---|---|---|---|---|---|
| ht-4550 | nx-fix-bug-ticket | 326 | 595k | 119M | 21M | nx-reproduce-bug (19%) |
| ht-4551 | nx-fix-bug-ticket | 296 | 471k | 87M | 8M | nx-reproduce-bug (36%) |
| library-following-opening-the | nx-fix-bug-ticket | 317 | 528k | 94M | 11M | nx-reproduce-bug (25%) |
| ht-4561 | nx-implement-ticket | 125 | 272k | 21M | 8M | nx-execute-plan (31%) |
| ht-4564 | nx-implement-ticket | 104 | 220k | 15M | 5M | nx-execute-plan (23%) |
| ht-4565 | nx-implement-planned-ticket | 95 | 220k | 15M | 11M | nx-execute-plan (41%) |
| ht-4566 | nx-implement-planned-ticket | 114 | 282k | 23M | 12M | nx-execute-plan (41%) |
| ht-4567 | nx-implement-planned-ticket | 32 | 150k | 4M | 8M | nx-review-ticket-plan (73%) |
| feature-follow-red-dot | nx-implement-feature | 321 | 719k | 127M | 68M | nx-write-feature-plans (28%) |

"Reads" are cache reads, in tokens.

## Findings

- F1. **Cache reads are 98–99% of all input tokens.** Output tokens are small (0.3–0.8M per task). The cost is the number of calls times the size of the context.
- F2. **The context only grows.** A task runs in one Claude session. It starts at about 80k tokens and ends at 300–700k. There is no `/clear` and no compaction (the window is 1M). Late steps that do little, such as `nx-wait-review` or `nx-create-merge-request`, re-read 500k tokens per call.
- F3. **`nx-reproduce-bug` is the main problem of bug tasks.**
    - It makes 19–36% of the reads, with about 130–160 calls.
    - It makes the context grow by about 230k tokens (about 85k → 320k), mostly with `adb`, screenshot and log output (2–7M characters of tool results).
    - Every later step carries these 230k tokens. In ht-4550, the steps after the reproduction re-read this emulator history on every call.
- F4. **Bug tasks cost 4–6 times more than implement tasks.** They have about 3 times more session calls, at a larger context. The emulator steps explain most of it.
- F5. **Interactive steps in a session that is already large cost a lot.**
    - `user-validation` in the feature task: 120 calls, 26% of the task, at 174k → 562k context.
    - `nx-wait-review` while answering comments: up to 29 calls at about 550k context.
- F6. **The fixed context is about 58k tokens** (from `/context` in a task tab, 2026-10-18):

| Part | Tokens |
|---|---|
| System prompt | 6.7k |
| System tools | 16.7k |
| MCP server instructions | 2.6k |
| Custom agents (8) | 2.4k |
| Memory files | 19.6k |
| Skills (118) | 10k |
| MCP tools (220) | 0, loaded on demand |

- F7. **Most of the memory files come from `CLAUDE.md` imports.** `NEXTORY_REPO/CLAUDE.md` imports 7 files of `docs/agents/` (about 34k characters), and the project auto-memory adds `MEMORY.md` (5.8k characters, 37 memory files). They load in every session, also in steps that only call Jira, `glab` or `factory wait`.
- F8. **On the tab measured above, the messages were 215k of 273k (79%).** The history is the cost, not the fixed part.

## Levers

Ranked by the expected gain. The gains are estimates from the baseline. The measures must confirm them.

### L1. A fresh session per phase (biggest)

- At chosen points, for example at each column change, the factory ends the Claude session and starts a new one with the task keys and the artifact paths.
- Expected gain: most calls run at 100–150k context instead of 300–600k. About 50–70% fewer reads on bug tasks. Probably better quality: above about 50% of the window, a model gets confused (cheat sheet).
- Bonus: each new session can start with its own `--model` and `--effort`. This answers the first question of this work (session steps cannot choose their model) with no relay and no subagent. The user still talks directly to the session.
- Risks:
    - Anything not written into an artifact is lost at the cut. The steps must write what the next phase needs. The measure shows where this breaks: more questions, more loops, more changes requested.
    - Each new session pays one setup of about 77k tokens written to the cache, once per phase.
- Where: the factory source (`session.py`, hooks, resume, attention, rename, the Herdr pane). Medium complexity.
- Start with one cut: at the end of Discovery, after the reproduction. Add more cuts if the numbers confirm it.

### L2. A smaller fixed context

- Move the `docs/agents` imports of `CLAUDE.md` to path-scoped rules, which load only when a matching file is read. About 10k tokens. This changes tracked files of the Nextory repo, so it is a team decision.
- Load only the needed plugins and skills in factory sessions. Maybe 5k tokens.
- Gain: about 5% today. About 10–15% after L1, when the average context is small. Its effect shows on the first call of each new task, so it is easy to measure.
- Not worth it: limiting MCP servers (F6: 0 tokens), compressing `CLAUDE.md` (small).

### L3. Shorter command output in the emulator steps

- In `nx-repro-attempt` and `nx-verify-fix`: write the `adb`, logcat, Gradle and UI-dump output to files and return short summaries. Group several commands into one script ("fewer cycles").
- Check that RTK really applies in task sessions.
- Gain: fewer calls and a slower context growth in the most expensive steps. Library change only.

### L4. A model and effort per step or phase

- Easy after L1.
- Test "big model, low effort" (`opus` / `medium`) before `sonnet`. The cheat sheet says it is often the better trade.
- Measure quality next to the tokens.

### L5. Subagent with resume

- The factory already runs `subagent` steps. When a subagent needs the user, the session asks, then `factory next` starts a new subagent, which loses its work.
- With `SendMessage`, the session can resume the same subagent with its full history. This works without agent teams, and after a restart of the session.
- Open points: does `effort` stay on resume? Do skills work in a subagent? Every question to the user adds a relay hop.
- With L1, this matters less. Keep it for heavy parts inside a phase, for example "Answer comments" in `nx-wait-review`.

### Not chosen

- Agent teams: experimental, in-process teammates are not restored on resume, permission prompts still go to the lead, model fixed at spawn.
- Cross-session messaging: the factory already moves state between steps with task keys and artifacts. A session per step would be L1, without the messaging.
- `/model` typed into the session before a step: every model switch re-reads the whole context without cache, and the factory must switch back.
- Output style ("caveman"): output tokens are small (F1).
- Indexing MCP servers (Serena and others): speculative here.

## Cheat sheet notes

Source: "Optimiser les tokens", Philippe Prados, carbon, 12.10.2026 (`~/Downloads/Optimiser-les-tokens-----Cheat-sheet.pdf`).

- Used: history above 50% of the context gives confusion, `/clear` (L1); limit skills and rules, rules filtered by file type (L2); compress command output, combine commands in a script (L3); `/model` and `/effort` per task, "big model, low effort" (L4).
- Not used: output style (F1), MCP list (F6), memory tools, indexing MCP servers.

## Measure plan

- M1. The factory stores the usage per step run in each task: calls, cache reads and writes, output, context size at the start and the end, tool result size, and a cost index. See `prompts/token_measure.md`.
- M2. The baseline comes from the existing transcripts, at once.
- M3. Quality and time per task, from the events: loop jumps and limits, `goto`s, changes requested, failed `done_check`s, findings per review round, time per step and per column, time waiting for the user.
- Tags at launch: library commit and factory version. A change is compared by grouping the tasks by tag.

### Decision rules

- Compare per-step medians, not task totals. Tasks differ a lot.
- A big effect (about 2 times, like L1): 3 tasks per pipeline type are enough.
- A small effect (10–20%, like L2): about 5 tasks or more, or a direct measure (the first call of a task).
- Quality must not drop: compare the loops, the changes requested and the review findings before and after.
- Only one change at a time in the measured pipelines, until its group has enough tasks.

## Order

1. M1 + M3: measurement in the factory (`prompts/token_measure.md`), and the baseline.
2. L1: a fresh session per phase, starting with one cut after Discovery.
3. L3: shorter command output in the emulator steps.
4. L2: the `docs/agents` imports and the unused plugins, after L1. Check with the team first.
5. L4: a model and effort per phase, with the quality numbers in place.
6. L5: only if a heavy part inside a phase stays expensive.

## Log

| Date | Change | Tasks measured | Result | Decision |
|---|---|---|---|---|
| 2026-10-18 | Baseline, one-off script | 9 | See the table above | Build M1 + M3 |
