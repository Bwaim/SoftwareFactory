# Step delete and hide: manual browser check

Setup: a test repository with the factory initialized and a test library in its own git repository. Never a real library.
Create a local step `m-local`, a generic step `m-generic` (commit it in the test library), and a pipeline `m-pipe` that uses `m-local`.
Open the editor with `factory pipeline edit`.

## Delete

1. Click `m-generic`. The detail has a "Delete" button.
2. Click "Delete". The panel shows the file, the warning "Other repositories that use this library are not checked." and "Confirm delete".
3. Click "Cancel". Nothing changes.
4. Click "Delete", then "Confirm delete". The step leaves the list. The panel shows "Commit to library" with `Factory library: delete step m-generic`.
5. Click "Commit to library". The test library has a new commit with only the removed file.
6. Click `m-local`, then "Delete". The panel lists `pipeline m-pipe (local)` and has no "Confirm delete".
7. Click `user-validation`. The detail has no "Delete" button.

## Hide

8. Click "Hide" on `m-local`. It leaves the list. The pipeline row of `m-local` in `m-pipe` shows a `hidden` mark. The checks show "Warning: A hidden step is used: `m-local`.". Save still works.
9. Tick "Show hidden steps". `m-local` is back, greyed, with "Unhide".
10. Reload the page. The toggle is still ticked.
11. Click `m-local` in the list. The detail has a "Delete" button.
12. Click "Unhide". The step is no longer greyed. The `hidden` mark and the warning disappear.

## Orchestrator

13. In the orchestrator, choose "Delete a step". The list has the local and generic steps with level and category, and hidden ones marked `hidden`. No built-in step.
14. Choose a step. The orchestrator shows the dry run and waits for your confirmation.
15. Confirm. The step is deleted. For a generic step, the orchestrator offers the library commit.

| Item | Result | Notes |
|---|---|---|
| 1-7 Delete | | |
| 8-12 Hide | | |
| 13-15 Orchestrator | | |
