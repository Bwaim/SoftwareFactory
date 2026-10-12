# Dashboard check

Scripted check, no browser. A temporary pytest file started `factory dashboard` in a test repo (fake terminal, `FACTORY_NO_OPEN=1`, temp link folder), fetched `/dashboard`, and called every API route the page uses with the token. It ran `factory next/done/wait` between calls. The file, the servers and the work folder were deleted afterwards.

"pass" means the page's API calls work as the page expects. "needs-browser" means the page code was written for it but a human must see it in a browser.

## Scripted results

| Item | Result | Evidence |
| --- | --- | --- |
| `/dashboard` served with the token | pass | 200, title present |
| Script syntax | pass | `node --check` on the extracted script |
| 1. Refresh every 5 s, no redraw while a form is open | needs-browser | `setInterval` and the skip rule are in the code. `/api/info`, `/api/tasks`, `/api/backlog` all return 200 |
| 2. Banner and disabled buttons (herdr, `HERDR_ENV=0`) | pass (API) / needs-browser (look) | `/api/info` gave `adapter.ok == false`, the Herdr message, `capabilities == []` |
| 3. Columns, Done column, hide toggles, localStorage | needs-browser | Rows carry `column` and `status`. `/api/info` lists the columns |
| 3. Card fields, status icon, tint, time in status, Session gone marker | needs-browser | `status_since`, `session_state`, `ticket`, `mr_url` are in the rows |
| 3. Artifact list and dialog | pass (API) | list in the row, `GET .../artifacts/spec.md` returns the text (HTML is kept as text), a missing file gives 404 and an error |
| 3. Focus, Send prompt (wait job), Pause (wait job and polling), Resume | pass (API) | focus 200, send-prompt with `wait` gave a job id, pause with `wait` gave a job that ended `done`, row became `paused`, resume 200 |
| 3. Approve | pass (API) | row `awaiting_approval` with `approval.target worktree`, approve 200, task active |
| 3. Request changes | pass (API) | 400 `Missing field: text.` without text, 200 with text, task active again |
| 3. Open in IDE | pass (API) | route answers, with the "IDE command is not set" error as 400 when no command is set. The page shows it in the error bar |
| 3. Mark done on a QA wait | pass (API) | `wait_has_check == false`, external-done 200, task moved on |
| 3. Finished task in Done | pass (API) | status `finished` after the last `done` |
| 3. Launch: pipelines, inputs, dry run, launch | pass (API) | `/api/pipelines`, `/api/pipelines/<id>` give `data.inputs`. Dry run reports missing input, then `ok` with branch case `new`. Launch creates the task |
| 3. Missing config field and `/api/config/set` | pass (API, route only) | route returns 200. The missing-config dry run path was not triggered |
| 3. Clean: report, dry run, delete | pass (API) | `/api/clean` listed the merged task as selected, dry run gave empty `uncommitted` and `unpushed`, delete moved the task out of the list |
| 3. `confirm_unpushed` only for ticked tasks | needs-browser | The page sends it only for ticked tasks. A task with unpushed work was not built in this check |
| 4. Backlog list, add, move, remove, start | pass (API) | order kept, `pipeline` kept, move `to: 1` reordered, start dry run `ok` and launch with `from_backlog` removed the entry, unknown id gives 400 |
| 4. Drag and drop, confirm dialog look | needs-browser | native drag events and the in-page dialog cannot be driven here |
| 5. Errors in the error bar | pass (API) / needs-browser (look) | every failing call returned `{"error": ...}` with 400 or 404 |

## Still needs a human browser check

- Cards: layout, tint colors in light and dark mode, icons, "blocked for 2 h" text, Session gone marker.
- Column hide and show, and that the choice survives a reload.
- The 5 s refresh keeps an open form or dialog and its typed text.
- Banner and disabled buttons with Herdr off (start with `HERDR_ENV=0` and `terminal: herdr`).
- Drag a backlog card up, down and to the end.
- Launch form: Check, missing-config field, Launch enabled only after a good check.
- Clean dialog with a task that has unpushed work, and the "I accept losing these changes" box.
- Pause dialog: "Pausing..." shows while the job runs.
