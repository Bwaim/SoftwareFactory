# Background poll and config errors

Source: `prompts/factory_skill_creation.md`, commit `6ba1ee4` ("Factory skill step 62").

## Goal

- The `done_check` of a waiting task keeps running without an open dashboard page.
- After a restart of the computer, the polling starts again by itself.
- An invalid `factory.yaml` or `config.yaml` gives a one-line error, not a Python traceback.

## Terms

- **Waiting check**: a task in status `waiting_external` whose current step has a `done_check`. A `paused` task is never a waiting check.

## Server life

1. The server stops after `IDLE_SECONDS` without requests (30 minutes, or `FACTORY_SERVER_IDLE_SECONDS`) only when no task is a waiting check. Otherwise it keeps running.
2. When the last waiting check ends, the normal idle rule applies again. The idle time counts from the last request, so a server idle for a long time stops at the next idle check.
3. A task that cannot be read (broken task file, unknown step) is not a waiting check. It never keeps the server alive.

## Commands that start the server

4. `factory wait` on a step with a `done_check` starts the server if it is not running. On a step without a `done_check`, it does not.
5. `factory resume <id>` starts the server when the resumed task is a waiting check.
6. `factory tasks` starts the server when at least one task is a waiting check. The orchestrator runs it at start, so this covers a restart of the computer.
7. These commands never fail because the server did not start. The command does its work, then prints one warning line on stderr: `Warning: the local server did not start, so done checks do not run. See .factory/server.log.` The exit code stays 0. `factory tasks --json` keeps valid JSON on stdout.
   A failed start can take up to `START_TIMEOUT` (30 s) before the warning.

## Single server

- B1: only one server runs per repository.
  - `ensure_server` holds a file lock on `.factory/server.json` (the lock file `server.json.lock`) from the running check to the end of the start. Two commands at the same time never start two servers. The second one waits, then finds the first server running.
  - In `watch_idle`, a server whose PID is no longer the PID in `server.json` stops at once. This includes a missing `server.json`. Without this, a duplicate server would never stop while a check waits, because of rule 1.

## Exit

8. New flag: `factory server stop --unless-waiting`.
   - No waiting check: it stops the server, as today.
   - Waiting checks: it keeps the server and prints `The server keeps running for the done checks of tasks <id>, <id>.`
9. `factory server stop` without the flag always stops the server. It is an explicit user command.
10. The orchestrator skill's Exit action runs `factory server stop --unless-waiting` and shows its output. Paused tasks are not waiting checks, so "pause all" then Exit stops the server.

## Config errors

11. `fsio.read_yaml` turns a YAML syntax error into a `FactoryError`: `<path>: <problem>, line <n>.` `<path>` is the absolute path. `<n>` starts at 1. Without a line number, the text is `<path>: <problem>.`
12. `cli.main` already prints `Error: <message>` and returns 1 for a `FactoryError`. So every command that reads `factory.yaml` or `config.yaml` prints `Error: <path>: <problem>, line <n>.` and exits with code 1.
13. The same rule applies to the other YAML files read by `read_yaml` (pipelines, the library `factory.yaml`). This is one change in one place.
14. A `factory.yaml` or `config.yaml` that is valid YAML but not a map (for example a list) gives `Error: <path>: the file must be a map of keys.` and exit code 1.

## Docs

15. README: the server section and the Exit line describe rules 1, 4 to 6 and 8. The README config section says that an invalid file gives a one-line error.
16. The orchestrator skill (`skills/software-factory/SKILL.md`): the Exit action uses rule 10.

## Tests

All tests use the fake adapter and a test repository. Each test that can start a server stops it at the end.

- T1: with `FACTORY_SERVER_IDLE_SECONDS=2`, the server keeps running while a task is a waiting check. It stops after the check ends (the flag file is created and `factory poll` runs).
- T2: `factory wait` on a step with a `done_check` starts the server. `factory wait` on a step without one does not.
- T3: `factory resume` of a paused waiting-check task starts the server.
- T4: `factory tasks` starts the server when a waiting check exists, and does not start it when none exists.
- T5: `factory server stop --unless-waiting` keeps the server and names the task when a waiting check exists. It stops the server when none exists.
- T6: an invalid `factory.yaml` gives `Error: <path>: <problem>, line <n>.`, exit code 1, and no `Traceback` in the output. The same for `config.yaml`.
- T7: a `factory.yaml` that is a list gives `Error: <path>: the file must be a map of keys.` and exit code 1.
- T8: when the server cannot start, `factory wait` still sets `waiting_external`, prints the warning on stderr and exits with 0.
- T9: with one server running, a second `factory serve` starts. The first server stops by itself, and one server process remains.
- The test fixture `inited` stops a running server at teardown, so no test leaves a server behind.

## Out of scope

- No change to `poll_minutes`, the poll loop, or the dashboard page.
- No new state in `task.json`.
