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
- When finished to create a new step, we need a way to exit the session and close the herdr tab.
- In the dashboard, add the possibility to edit a backlog entry.
- we need a better management of the inputs and outputs in the pipeline editor and having a kind of mapping between inputs available to map to the input of a step. 
- in the pipeline editor, we should be able to save and go back to the list of pipelines to have the option to create a new one or edit an existing one. We should also be able to delete a pipeline from here.
- add a boolean value for parameters
- add action to some cards to allow to send a specific prompt (like running a skill to fix comments)
- define the poll at step level
- In the card display the step number
- Save findings in artifact to be able to have better first execution

- agents communication to have subagents

- Step to change ticket owner
- We need a new Step `nx-update-ticket-assigned` to change the ticket assigned
- Add missing merge at the end when "Needs QA"
- Add a missing merge step at the end when "Needs QA"
- `nx-reproduce-bug` "Repro approved" no information on the dashboard that it's waiting me
- `nx-review-mr` when Dobby let comments opened, no information on the dashboard that it's waiting me
- `nx-reproduce-bug` and `nx-verify-fix` allow only one task at this step (because of emulator concurrency)
- For your future run, ask me to prepare the emulator for you when needed, don't spend time trying to configure an account, you should go directly to the reproduction steps. Don't need to clear data neither
- When capturing logcat, clear the logs before capturing
- emulator, set timeout of 3 minutes if nothing change
- `nx-wait-qa` check when ticket moved to "QA finished" to merge the branch if needed and update ticket state to done