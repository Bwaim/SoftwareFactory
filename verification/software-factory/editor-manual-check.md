# Editor check (scripted, no browser)

Method: a server was started on a test repository with `FACTORY_NO_OPEN=1` and the fake terminal. `/editor` and every API route the page calls were fetched with the token. The page script was extracted and checked with `node --check`. The server was stopped and the work folder deleted.

Scripted results:
- `factory pipeline edit base` printed the editor URL. `pipeline list`, `step list --json` and `step show` worked.
- `/editor` served the page (371 lines). `node --check` on its script: pass.
- `GET /api/info`, `/api/steps`, `/api/steps/<id>`, `/api/pipelines`, `/api/pipelines/<id>`: 200.
- `POST /api/pipelines/copy`, `/check`, `/save`: 200 with the expected data. A missing step gave an error problem.
- `POST /api/library/commit`: 404, because the route comes with Task 25.

Per behavior item:

| Item | Result |
| --- | --- |
| 1. Token, `X-Factory-Token`, red `#error` bar | API calls pass with the token. The error bar needs a human browser check. |
| 2. Start panel (empty, copy, edit) | Routes pass. Page behavior not verifiable without a browser. |
| 3. Available steps, filters, "Reload steps" | `GET /api/steps` passes. Rendering and filters not verifiable without a browser. |
| 4. Form fields and inputs editor | Not verifiable without a browser. |
| 5. Drag to add, reorder, remove, per-row form | Not verifiable without a browser. |
| 6. Detail panel (manifest, body, path, children) | `GET /api/steps/<id>` passes. Rendering not verifiable without a browser. |
| 7. Live check after 300 ms, Save disabled on error | `POST /api/pipelines/check` passes. Timing and the disabled button not verifiable without a browser. |
| 8. Save with level choice, commit button | `POST /api/pipelines/save` passes. The commit button needs Task 25 and a browser. |

A human must check items 1 to 8 in a browser (dark and light mode too).
