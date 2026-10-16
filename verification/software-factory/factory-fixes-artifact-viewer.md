# Browser check: artifact viewer, poll countdown and Check now

Date: 2026-10-16. Code: branch `factory-fixes` at commit `05a9da1`. Browser: Chrome, through Claude in Chrome.

## Setup

A throwaway repo in the session scratchpad, never a real repo. Fake terminal adapter.

1. `git init --bare origin.git`, `git clone origin.git repo`, one empty commit pushed to `main`.
2. `FACTORY_TERMINAL=fake factory init --library <scratch>/lib --create-library`.
3. A local step `wait-review` with `wait_external: true` and `done_check: "echo CodeRabbit review pending; sleep 5; false"`, and a pipeline `w` with that step.
4. With `conftest.make_task`:
   - `t1`, `awaiting_approval`, with the artifacts `short.md` (3 lines) and `long.md` (2000 lines).
   - `t2`, `waiting_external` on `wait-review`.
5. `FACTORY_POLL_SECONDS=120 factory dashboard`, then open the printed URL.

The Python used is a scratchpad venv with PyYAML, because the system Python has no PyYAML.

## Artifact viewer

| # | Check | Result |
| --- | --- | --- |
| 1 | Open `long.md`, scroll inside the text by 10 wheel ticks | PASS: the text scrolls inside the viewer, the title bar "t1 / long.md" with "Close" stays at the top |
| 2 | Escape on `long.md` | PASS: `#modal.hidden` is true |
| 3 | Open `long.md`, click the dark area outside the box | PASS: closed |
| 4 | Open `short.md`, click "Close" | PASS: closed. The short viewer fits its 3 lines, the bar is at the top |
| 5 | Open `long.md`, drag from inside the text to the dark area | PASS: the viewer stays open and the text is selected |
| 6 | "Request changes" on t1, type "abc", click outside | PASS: the form stays open, the text is still "abc" |
| 7 | Escape on the form with "abc" | PASS: the row "Discard the typed text?" with "Discard" and "Keep editing" appears. "Keep editing" removes the row and keeps "abc". Escape again, then "Discard": the form closes |
| 8 | Open "Request changes" again, no text, Escape | PASS: closes at once |

## Poll countdown and Check now

| # | Check | Result |
| --- | --- | --- |
| 9 | Card t2 after load | PASS: "Next check in 1:33", then 1:27, 1:26, 1:16, 0:44 in later screenshots. It also counts down while a viewer is open |
| 10 | Click "Check now" | PASS: the button shows "Checking…" and is disabled at once. A page script call during the check ran without delay |
| 11 | After the 5-second check | PASS: the card shows "Last check: 02:08:10, still waiting: CodeRabbit review pending", and the button is "Check now" again |
| 12 | Paused task | Covered by `tests/test_check_now.py::test_paused_task_has_no_countdown` (the API returns no `next_check_at`) |

The server was stopped with `factory server stop` after the check.
