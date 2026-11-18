# Workspaces manual check

Date: 2026-11-18. Branch: `repo_panel`. Browser: Chrome.

Setup: `FACTORY_HOME` in a scratch folder, `FACTORY_TERMINAL=fake`, three test repositories `alpha`, `beta`, `gamma`. The `factory init` command ran in `alpha` and `beta`. Demo tasks: `alpha` has one `blocked` task and one `active` task, `beta` has one `paused` task.

| Check | Result |
|---|---|
| `factory dashboard` from a folder outside any repository opens the page. | Pass |
| The sidebar lists `alpha` and `beta`. The `alpha` badge shows 1. | Pass |
| A click on `beta` shows the `beta` board. The URL gets `ws=beta`. | Pass |
| "+" on `gamma` (no factory) shows "Set up the factory in <path>?" with the file list and the "Library folder" field. | Pass |
| "Set up and add" runs init, adds `gamma`, and selects it. | Pass |
| The "⋯" menu shows Rename and Delete. Rename with Enter saves "Gamma Repo". | Pass |
| Delete shows the exact text. Remove takes the row away. | Pass |
| `beta` removed through the API while the page shows `beta`: the next refresh selects `alpha`, with no error banner. | Pass |
| No console errors. | Pass |

Not checked in the browser:
- "Choose folder…". It opens a macOS dialog on the screen of the user. The route is covered by `test_pick_folder`.
- Rename with Escape.
