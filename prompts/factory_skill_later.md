# nextory-factory: saved for later

Ideas and requirements not in the current build. Move them to `factory_skill_creation.md` when needed.

### Dashboard

- Menu actions: "Start the dashboard". "Exit" also stops the dashboard.
- Each task has a list of actions that can be started from the dashboard. An action is a step.
- The task status shown on the dashboard is updated by Claude Code hooks (`Stop`, `Notification`).
- The orchestrator starts the dashboard with one command and opens it in the browser.
- The dashboard is served by a local HTTP server.
- It shows one card per task, in Kanban columns:
  - <TODO: final column list, for example Running, Waiting for me, Review, Done>
- Columns are lifecycle states, the same for all pipelines.
- Each card shows the slug, the pipeline, the current step and the live agent state from `herdr agent list` (`idle`, `working`, `blocked`, `done`).
- The user can hide and show columns. The choice is kept in the browser.
- Each card has action buttons:
  - Focus: runs `herdr agent focus <slug>` and brings the terminal window to the front.
  - Send prompt: sends a prompt to the task session with `herdr agent prompt`.
  - Resume: when the Claude session is gone, opens a new Herdr tab in the worktree and runs `claude --resume <session-id>`.
  - <TODO: other actions>

### Dashboard security

- The server listens on `127.0.0.1` only.
- It requires a random token generated at start.
- It rejects requests whose `Origin` header is not the dashboard.
- <TODO: decide if Send prompt allows free text or only fixed prompt templates>

### Limits

- The number of tasks running at the same time is limited. <TODO: max number>

### Verification

- A dry run creates one test task in a named Herdr test session, then:
  - Checks the worktree, the Herdr tab and the named Claude session exist.
  - Checks the first prompt was received.
  - Checks the task state file is created and updated by the hooks.
  - Starts the dashboard and checks each action button works on the test task.
  - Checks the dashboard rejects a request without a token or with a wrong `Origin`.
- The dry run removes the test task, its worktree and its Herdr test session at the end.
- The dry run writes its output to `VERIFICATION_DIR`.

## Ideas

- Schedule a pipeline.
- Analyze a finished task: split the Claude transcript by step with the event log, find failed commands, retries and user corrections, and propose step improvements in the right location (generic or local).
