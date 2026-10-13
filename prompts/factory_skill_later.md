# software-factory: saved for later

Ideas and requirements not in the current build. Move them to `factory_skill_creation.md` when needed.

### Limits

- The number of tasks running at the same time is limited. <TODO: max number>

## Ideas

- Schedule a pipeline.
- Analyze a finished task: split the Claude transcript by step with the event log, find failed commands, retries and user corrections, and propose step improvements in the right location (generic or local).
- Custom card actions: a dashboard button that runs a chosen step on a task.
- Update the live session state with Claude Code hooks (`Stop`, `Notification`), for terminals whose adapter has no `state` operation.
- In the dashboard automatically hides the empty columns. 