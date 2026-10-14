# Background Poll Implementation Plan

**Goal:** Keep the local server and its poll loop alive while a task waits on a `done_check`, start it from `wait`, `resume` and `tasks`, keep one server per repository, and turn invalid YAML into a one-line error.

**Spec:** `specs/2026-10-14-background-poll-design.md`

**Branch:** `background-poll`, from master.

**Execution:** native. I build the tasks in this session, in order, with TDD. A final review runs on the whole branch before the commit.

**Test command** (from `software-factory/`): `uv run --with pytest --with pyyaml pytest -q tests`. New tests go in `tests/test_background_poll.py`.

## Global Constraints

- Tests use the fake adapter (`FACTORY_TERMINAL=fake`) and the `inited` test repository. Never a real `.factory/`.
- Every test that can start a server leaves no server behind.
- Warning text: `Warning: the local server did not start, so done checks do not run. See .factory/server.log.`
- Keep text: `The server keeps running for the done checks of tasks <id>, <id>.`
- YAML error text: `<path>: <problem>, line <n>.`, or `<path>: <problem>.` without a line. The CLI prefixes `Error: `.
- Map error text: `<path>: the file must be a map of keys.`
- No code comments.

## Review Focus

- RF1: a broken task or step file must not crash `watch_idle`. Otherwise the thread dies and the server never stops.
- RF2: `factory tasks --json` must keep valid JSON on stdout when the start fails. The warning goes to stderr. Test: `test_tasks_json_stays_valid_when_the_server_does_not_start` (Task 2).
- RF3: `ensure_server` must not deadlock. `Server.run` writes `server.json` with an atomic rename and never takes the lock.
- RF4: `--unless-waiting` with waiting checks but no running server says `The server was not running.`, not "keeps running".

---

### Task 1: Waiting checks and the server life

**Files:**
- Modify: `software-factory/lib/factory/engine.py`: add `waiting_checks`
- Modify: `software-factory/lib/factory/server.py`: `watch_idle`, `ensure_server` lock, `keep_polling`
- Modify: `software-factory/tests/conftest.py`: `inited` stops the server at teardown
- Create: `software-factory/tests/test_background_poll.py`

**Interfaces:**
- Produces: `engine.waiting_checks(ctx) -> list[str]` (task ids). `server.keep_polling(ctx) -> None`. `server.START_WARNING`.

- [ ] **Step 1: Write the failing tests (T1, T9)**

```python
import os
import subprocess
import sys
import time

import pytest

from conftest import BIN, task_from_pipeline, task_json, write_pipeline, write_step
from serverutil import alive, info, wait_dead

FAST = {"FACTORY_SERVER_IDLE_SECONDS": "2"}


@pytest.fixture
def waits(inited):
    flag = inited.work / "approved.flag"
    write_step(inited.fdir, "wait-review", {"wait_external": True, "done_when": "Approved.", "done_check": f"test -f {flag}"})
    write_step(inited.fdir, "wait-qa", {"wait_external": True, "done_when": "QA is done."})
    write_step(inited.fdir, "after", {})
    write_pipeline(inited.fdir, {"id": "w", "steps": ["wait-review", "after"]})
    write_pipeline(inited.fdir, {"id": "q", "steps": ["wait-qa", "after"]})
    return inited, flag


def server_pid(inited):
    path = inited.fdir / "server.json"
    return info(inited.fdir)["pid"] if path.exists() else None


def test_server_stays_while_a_check_waits(waits):
    inited, flag = waits
    task_from_pipeline(inited, "w", worktree=str(inited.repo), terminal_handle={"agent": "t1"})
    inited.factory("next", "--task", "t1")
    inited.factory("wait", "--task", "t1", env=FAST)
    pid = server_pid(inited)
    time.sleep(6)
    assert alive(pid)
    flag.write_text("ok")
    inited.factory("poll")
    assert wait_dead(pid, 15)


def test_a_second_server_stops_the_first(waits):
    inited, _ = waits
    task_from_pipeline(inited, "w", worktree=str(inited.repo), status="waiting_external")
    inited.factory("tasks", env=FAST)
    first = server_pid(inited)
    env = {**inited.factory.env, **FAST}
    subprocess.Popen([sys.executable, str(BIN), "serve"], cwd=inited.repo, env=env,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    end = time.time() + 15
    while time.time() < end and server_pid(inited) in (None, first):
        time.sleep(0.2)
    second = server_pid(inited)
    assert second not in (None, first)
    assert wait_dead(first, 15)
    assert alive(second)
```

- [ ] **Step 2: Run the tests and check they fail**

Run: `pytest -q tests/test_background_poll.py`
Expected: both FAIL. `factory wait` starts no server, so `server_pid` is `None`.

- [ ] **Step 3: Add `waiting_checks` to `engine.py`**, after `poll`:

```python
def is_waiting_check(reg, task):
    if task["status"] != "waiting_external":
        return False
    entry = state.current_entry(task)
    return entry is not None and bool(reg.step(entry["id"]).done_check)


def waiting_checks(ctx):
    try:
        reg = Registry.load(ctx)
        tasks = state.list_tasks(ctx)
    except Exception:
        return []
    ids = []
    for task in tasks:
        try:
            if is_waiting_check(reg, task):
                ids.append(task["id"])
        except Exception:
            continue
    return ids
```

- [ ] **Step 4: Change `server.py`**

```python
START_WARNING = "Warning: the local server did not start, so done checks do not run. See .factory/server.log."
```

```python
    def replaced(self):
        return (read_info(self.ctx) or {}).get("pid") != os.getpid()

    def watch_idle(self):
        from . import engine
        while True:
            time.sleep(min(30, IDLE_SECONDS))
            if self.replaced() or (time.time() - self.last > IDLE_SECONDS and not engine.waiting_checks(self.ctx)):
                self.stop()
                return
```

Wrap the body of `ensure_server` in the lock:

```python
def ensure_server(ctx):
    with fsio.locked(info_path(ctx)):
        info = running(ctx)
        if info:
            return info
        ...the current start code, unchanged...
```

```python
def keep_polling(ctx):
    try:
        ensure_server(ctx)
    except FactoryError:
        print(START_WARNING, file=sys.stderr)
```

- [ ] **Step 5: Call `keep_polling` in `commands.py`**
  - `wait_cmd`: after `print(engine.wait(ctx, tid))`, add `if tid in engine.waiting_checks(ctx): server.keep_polling(ctx)`.
  - `tasks_cmd`: after printing the rows, add `if engine.waiting_checks(ctx): server.keep_polling(ctx)`.

- [ ] **Step 6: Stop the server at fixture teardown in `conftest.py`**

```python
@pytest.fixture
def inited(factory, origin_repo, library_path, work):
    factory("init", "--library", library_path, "--create-library")
    factory("config", "set", "create-worktree", "worktree_root", work / "worktrees")
    yield Inited(origin_repo, library_path, factory, work)
    if (origin_repo / ".factory" / "server.json").exists():
        factory("server", "stop", check=False)
```

- [ ] **Step 7: Run the tests and check they pass**

Run: `pytest -q tests/test_background_poll.py tests/test_server.py tests/test_waiting.py`
Expected: PASS.

### Task 2: Commands that start the server, Exit flag, warning (T2 to T5, T8)

**Files:**
- Modify: `software-factory/lib/factory/commands.py`: `resume_cmd`, `server stop --unless-waiting`
- Modify: `software-factory/tests/test_background_poll.py`

**Interfaces:**
- Consumes: `engine.waiting_checks`, `server.keep_polling`, `server.running`, `server.START_WARNING` from Task 1.

- [ ] **Step 1: Write the failing tests**

```python
def test_wait_starts_the_server_only_with_a_check(waits):
    inited, _ = waits
    task_from_pipeline(inited, "q", tid="t2", worktree=str(inited.repo), terminal_handle={"agent": "t2"})
    inited.factory("next", "--task", "t2")
    inited.factory("wait", "--task", "t2")
    assert server_pid(inited) is None
    task_from_pipeline(inited, "w", tid="t1", worktree=str(inited.repo), terminal_handle={"agent": "t1"})
    inited.factory("next", "--task", "t1")
    inited.factory("wait", "--task", "t1")
    assert alive(server_pid(inited))


def test_resume_starts_the_server(waits):
    inited, _ = waits
    task_from_pipeline(inited, "w", worktree=str(inited.repo), status="waiting_external")
    inited.factory("pause", "t1")
    inited.factory("server", "stop")
    inited.factory("resume", "t1")
    assert task_json(inited.fdir, "t1")["status"] == "waiting_external"
    assert alive(server_pid(inited))


def test_tasks_starts_the_server_only_with_a_check(waits):
    inited, _ = waits
    task_from_pipeline(inited, "q", tid="t2", worktree=str(inited.repo), status="waiting_external")
    inited.factory("tasks")
    assert server_pid(inited) is None
    task_from_pipeline(inited, "w", tid="t1", worktree=str(inited.repo), status="waiting_external")
    inited.factory("tasks", "--json")
    assert alive(server_pid(inited))


def test_stop_unless_waiting(waits):
    inited, _ = waits
    task_from_pipeline(inited, "w", worktree=str(inited.repo), status="waiting_external")
    inited.factory("tasks")
    pid = server_pid(inited)
    out = inited.factory("server", "stop", "--unless-waiting").stdout
    assert out.strip() == "The server keeps running for the done checks of tasks t1."
    assert alive(pid)
    inited.factory("pause", "t1")
    assert inited.factory("server", "stop", "--unless-waiting").stdout.strip() == "Server stopped."
    assert wait_dead(pid)


def test_wait_warns_when_the_server_does_not_start(waits, monkeypatch, capsys):
    from factory import cli, server
    from factory.errors import FactoryError
    inited, _ = waits
    task_from_pipeline(inited, "w", worktree=str(inited.repo), terminal_handle={"agent": "t1"})
    inited.factory("next", "--task", "t1")
    for key, value in inited.factory.env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(inited.repo)

    def fail(ctx):
        raise FactoryError("The local server did not start. See .factory/server.log.")

    monkeypatch.setattr(server, "ensure_server", fail)
    assert cli.main(["wait", "--task", "t1"]) == 0
    assert capsys.readouterr().err.strip() == server.START_WARNING
    assert task_json(inited.fdir, "t1")["status"] == "waiting_external"


def test_tasks_json_stays_valid_when_the_server_does_not_start(waits, monkeypatch, capsys):
    from factory import cli, server
    from factory.errors import FactoryError
    inited, _ = waits
    task_from_pipeline(inited, "w", worktree=str(inited.repo), status="waiting_external")
    for key, value in inited.factory.env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(inited.repo)

    def fail(ctx):
        raise FactoryError("The local server did not start. See .factory/server.log.")

    monkeypatch.setattr(server, "ensure_server", fail)
    assert cli.main(["tasks", "--json"]) == 0
    out = capsys.readouterr()
    assert [row["id"] for row in json.loads(out.out)] == ["t1"]
    assert out.err.strip() == server.START_WARNING
```

- [ ] **Step 2: Run the tests and check the new ones fail**

Run: `pytest -q tests/test_background_poll.py`
Expected: `test_resume_starts_the_server` and `test_stop_unless_waiting` FAIL. The other three pass after Task 1.

- [ ] **Step 3: Implement in `commands.py`**
  - Parser: `st = svs.add_parser("stop", parents=[common]); st.add_argument("--unless-waiting", action="store_true")`.
  - `resume_cmd`:

```python
@cli.command("resume")
def resume_cmd(args):
    from . import engine, server, session
    ctx = ctx_of(args)
    session.resume(ctx, args.id)
    print(f"Task {args.id} resumed.")
    if args.id in engine.waiting_checks(ctx):
        server.keep_polling(ctx)
```

  - `server_stop_cmd`:

```python
@cli.command("server stop")
def server_stop_cmd(args):
    from . import engine, server
    ctx = ctx_of(args)
    ids = engine.waiting_checks(ctx) if args.unless_waiting else []
    if ids and server.running(ctx):
        print(f"The server keeps running for the done checks of tasks {', '.join(ids)}.")
        return
    print("Server stopped." if server.stop_server(ctx) else "The server was not running.")
```

- [ ] **Step 4: Run the tests and check they pass**

Run: `pytest -q tests/test_background_poll.py`
Expected: PASS.

### Task 3: YAML errors (T6, T7)

**Files:**
- Modify: `software-factory/lib/factory/fsio.py`: `read_yaml`, `require_map`
- Modify: `software-factory/lib/factory/repo.py`: `Ctx.factory_yaml`
- Modify: `software-factory/lib/factory/config.py`: `saved_section`, `set_value`
- Modify: `software-factory/tests/test_background_poll.py`

- [ ] **Step 1: Write the failing tests**

```python
import re


def one_line_error(result, path):
    assert result.returncode == 1
    assert "Traceback" not in result.stdout + result.stderr
    assert result.stderr.startswith(f"Error: {path}: ")
    return result.stderr.strip()


def test_invalid_factory_yaml(inited):
    path = (inited.fdir / "factory.yaml").resolve()
    path.write_text("version: 2\ncolumns: [a, b\n")
    text = one_line_error(inited.factory("tasks", check=False), path)
    assert re.search(r", line \d+\.$", text)


def test_invalid_config_yaml(inited):
    path = (inited.fdir / "config.yaml").resolve()
    path.write_text("create-worktree: {worktree_root: [x\n")
    text = one_line_error(inited.factory("config", "set", "create-worktree", "worktree_root", "y", check=False), path)
    assert re.search(r", line \d+\.$", text)


def test_factory_yaml_must_be_a_map(inited):
    path = (inited.fdir / "factory.yaml").resolve()
    path.write_text("- a\n- b\n")
    text = one_line_error(inited.factory("tasks", check=False), path)
    assert text == f"Error: {path}: the file must be a map of keys."
```

- [ ] **Step 2: Run the tests and check they fail**

Expected: FAIL with a traceback in stderr.

- [ ] **Step 3: Implement**

`fsio.py` (import `FactoryError` from `.errors`):

```python
def yaml_problem(path, error):
    problem = getattr(error, "problem", None) or str(error)
    mark = getattr(error, "problem_mark", None)
    line = f", line {mark.line + 1}" if mark else ""
    return f"{path}: {problem}{line}."


def read_yaml(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise FactoryError(yaml_problem(path, e))
    return default if data is None else data


def require_map(path, data):
    if not isinstance(data, dict):
        raise FactoryError(f"{path}: the file must be a map of keys.")
    return data
```

`repo.py`:

```python
    def factory_yaml(self):
        path = self.fdir / "factory.yaml"
        return fsio.require_map(path, fsio.read_yaml(path, {}) or {})
```

`config.py`:

```python
def saved_section(ctx, step_id):
    data = fsio.require_map(config_path(ctx), fsio.read_yaml(config_path(ctx), {}) or {})
    return data.get(step_id) or {}
```

In `set_value`, the first line of `change(data)` is `fsio.require_map(config_path(ctx), data)`.

- [ ] **Step 4: Run the tests and check they pass**

Run: `pytest -q tests/test_background_poll.py tests/test_migrate_v2.py`
Expected: PASS.

### Task 4: Docs, full suite, commit

**Files:**
- Modify: `software-factory/README.md`: the Exit line (130), `factory server stop` (214), the server section (371-372), the `factory.yaml` section (429)
- Modify: `software-factory/skills/software-factory/SKILL.md`: the Exit action (65)

- [ ] **Step 1: README**
  - Line 130: `- **Exit**: ask to pause all tasks. Then stop the local server, unless a task waits on a done check.`
  - Line 214: add `` - `factory server stop --unless-waiting`: stop the local server only when no task waits on a done check. ``
  - Lines 371-372:

```markdown
- The server stops after 30 minutes without requests. While a task waits on a step with a `done_check`, it keeps running, so the checks run without an open page.
- `factory wait`, `factory resume` and `factory tasks` start the server when a task waits on a done check. After a restart of the computer, the orchestrator start runs `factory tasks`, so the polling starts again.
- Only one server runs per repository. A server that is replaced stops by itself.
- `factory server stop` stops it now. The menu action "Exit" runs `factory server stop --unless-waiting`.
```

  - After line 429: `When factory.yaml or config.yaml is not valid YAML, every command prints Error: <path>: <problem>, line <n>. and exits with code 1.`
- [ ] **Step 2: Skill.** In the Exit action, replace `Then run \`factory server stop\` and stop the menu.` with `Then run \`factory server stop --unless-waiting\`, show its output, and stop the menu.`
- [ ] **Step 3: Check the skill and README tests.** Run `grep -rn "server stop" tests`. Update any test that checks the old Exit text.
- [ ] **Step 4: Run the full suite.**
  - Run: `uv run --with pytest --with pyyaml pytest -q tests`
  - Expected: all pass. Today 402 tests pass, plus 12 new tests.
- [ ] **Step 5: Final review.** One review agent reads the branch diff against the spec. Fix the real findings, then run the full suite again.
- [ ] **Step 6: Commit** on `background-poll`, with no co-author line:

```bash
git add software-factory specs/2026-10-14-background-poll-design.md plans/2026-10-14-background-poll.md
git commit -m "background poll: server life while a check waits, one server, YAML errors"
```
