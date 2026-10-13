# Step editor manual check list

Run these in a test repository, or on copies made by you. Never on a real `.factory/` or a real library you do not want to change.

1. Create a new `ai` step from the form.
   - Run `factory step edit`. Fill the id, the description and the prompt.
   - Click two keys on the right. Expected: `{{key}}` is inserted at the cursor.
   - Click "Preview". Expected: the prompt with `<key>`, then the footer with the outputs.
   - Save local. Expected: the file is in `.factory/steps/`. The step is in the list.
   - Add it to a pipeline and save the pipeline.
2. Edit a generic step.
   - Click the step, then "Edit". Change the description. Click "Save".
   - Expected: the pipelines and unfinished tasks that use it, and "Other repositories that use this library are not checked."
   - Click "Confirm save", then "Commit to library". Expected: `git log -1` in the library shows `Factory library: update step <id>`.
3. Copy a built-in step to local, and duplicate a step.
   - Click `user-validation`, then "Copy to local", then "Save". Expected: `.factory/steps/user-validation.md` exists. The list shows it as local.
   - Click any step, then "Duplicate". Give a new id and save. Expected: a new step with the same fields.
4. Create a `group` step.
   - Set the type to `group`. Add three child steps. Drag the last one to the top. Save.
   - Expected: the file lists the child steps in the new order. The detail shows them.
5. Select a step in a pipeline.
   - Open a pipeline with inputs. Click its third step. Expected: "Keys available here" lists the inputs, the outputs of the first two steps and the factory keys, with "always set" or "maybe set".
6. Launch from the dashboard.
   - Pick a pipeline with a `long-text` input. Expected: a text area.
   - Pick a pipeline with a `file` input. Type a path that does not exist and click "Check". Expected: a red error with the absolute path.
7. Orchestrator.
   - Choose "Create a new step". Expected: the step form opens in the browser.
8. Migration.
   - Make a copy of a real version 1 `.factory/` folder and of its library, in a test repository.
   - Start the orchestrator there. Expected: the migration dry run, then the summary with the backup path. The library commit `Factory library: migrate to version 2` is offered.
   - Launch a migrated pipeline and run it to the end.
