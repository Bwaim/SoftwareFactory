# Software Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `software-factory` Claude Code plugin: an orchestrator skill plus a `factory` CLI that runs each task in its own worktree, Herdr tab and named Claude session, through pipelines of reusable steps, with a local pipeline editor and dashboard.

**Architecture:** One entry script `bin/factory` (PEP 723 inline dependencies, run by `uv run --script`) imports the package `lib/factory/`. Every CLI command and every HTTP route of `factory serve` calls the same module function. Terminal actions go through an adapter interface (`herdr`, and `fake` for tests).

**Tech Stack:** Python 3.12+, `pyyaml` (only runtime dependency), standard library `http.server`, `fcntl`, `subprocess`. Tests: `pytest` run with `uv run --with pytest --with pyyaml`. Pages: plain HTML, CSS, JavaScript.

**Spec:** `specs/2026-10-12-software-factory-design.md`. Product source: `prompts/factory_skill_creation.md` (the prompt). Read both before any task.

## Global Constraints

- All paths below are relative to `PROJECT_ROOT = /Users/fabienboismoreau/Documents/Projects/SoftwareFactory/SoftwareFactory` unless they start with `software-factory/`, which is `YOUR_WORKING_DIR`.
- Write project files only in `software-factory/`, `verification/software-factory/`, `plans/`, `specs/` (own spec only) and `.claude-plugin/marketplace.json`. Never read other files in `specs/`.
- Never close a Herdr workspace, tab, pane or session that this build did not create. Only the e2e script and Task 9 create Herdr objects, and they record and close only their own ids.
- No code comments. Use names, small functions and constants instead. The PEP 723 `# /// script` block in `bin/factory` is metadata, not a comment, and is required.
- Runtime dependency: `pyyaml>=6` only. `requires-python = ">=3.12"`.
- Data format version: `1`.
- Task id regex: `^[a-z][a-z0-9_-]{0,31}$`. Step and pipeline id regex: `^[a-z][a-z0-9_-]{0,63}$`.
- Default board columns: `Discovery, Specification, Plan, Implementation, Review, QA`. `Done` is always last and is not in the list.
- `poll_minutes` default `5`. Poll `done_check` timeout: 60 s. `factory done` check timeout: 300 s. Server idle stop: 30 min. Page refresh: 5 s.
- Every subprocess call uses an argument list, never `shell=True`, except `done_check` commands, which are shell commands by definition.
- Every write to a data file is atomic (temp file in the same folder + `os.replace`). Every change to `task.json`, `config.yaml`, `backlog.md` and `events.jsonl` holds an `fcntl` lock on `<file>.lock` for the whole read, change and write.
- Output text and README: simple English, short sentences.
- Test-only environment variables (never documented for users): `FACTORY_LINK_DIR`, `FACTORY_TERMINAL`, `FACTORY_MIGRATIONS_DIR`, `FACTORY_DATA_VERSION`, `FACTORY_CLAUDE_HOME`, `FACTORY_NO_OPEN`, `FACTORY_SERVER_IDLE_SECONDS`, `FACTORY_POLL_SECONDS`.
- `FACTORY_TASK` is a public environment variable: same as `--task`. The CLI sets it when it runs a `done_check` or a script step.
- Commits: one per task, message `<area>: <change>`, no co-author line. Each milestone ends with all tests passing and a commit.
- Run tests from `software-factory/` with: `uv run --with pytest --with pyyaml pytest tests -q`.

## Additions to the spec made by this plan

These follow from the spec. Report them to the user with the plan.

- A1. `factory run-script`: runs the current `script` step. `factory next` tells the agent to run it. So script steps are covered by the `factory` allow rule and never ask for permission.
- A2. `factory link`, `factory terminal check` and `factory menu` also skip the version check. The orchestrator runs them before `factory version check`.
- A3. At launch, `create-worktree` is marked done and `position` is set before the session starts, because the session runs `factory next` at once. The rollback still removes the task folder on failure. `task_created` is logged after the session starts.
- A4. Built-in step `new-step` holds the step assistant instructions. The built-in pipeline `new-step-assistant` runs it.
- A5. Resume uses `--resume <session_id>` in place of `--session-id <session_id>`, because Claude refuses both together. Task 9 verifies this.
- A6. `task.json` also stores `status_since`, `started`, `base_ref` and `claude`.
- A7. The e2e test uses the real `~/.local/bin/factory` link, because Herdr panes do not inherit the test environment. It saves the previous link target and restores it at the end.
- A8. The e2e pipeline adds a `wait_external` step between its two script steps, so pause and resume happen while the task is not finished.

## Review Focus

1. A description with no ASCII letters, for example `"ÉÉ 2"` or `"!!!"`, must still give a valid task id. Expected: `task`, `task-2`, ... Test in Task 10.
2. On macOS, `/tmp` and `/var` are symlinks. A worktree path seen through a symlink must still find its task. Expected: paths are compared after `resolve()`. Test in Task 3.
3. Prompts and descriptions with quotes, `$`, backticks and new lines must reach Herdr and git unchanged. Expected: argument lists only. Test in Task 9 (fake adapter records the exact prompt) and Task 10.
4. A hand-edited `backlog.md` with text before the first heading, blank lines, or an entry without an id must not crash and must not lose text. Expected: the preamble is kept, ids are added on the next write. Test in Task 20.
5. A `done_check` that never ends must not hang the session or the poll. Expected: `done_check_failed` with "Timed out". Test in Task 7.

---

## File Map

```
.claude-plugin/marketplace.json
software-factory/
  .claude-plugin/plugin.json
  skills/software-factory/SKILL.md
  bin/factory
  lib/factory/__init__.py
  lib/factory/errors.py          FactoryError
  lib/factory/fsio.py            atomic write, locks, yaml/json helpers
  lib/factory/repo.py            Ctx, main repo, current task, PLUGIN_ROOT, git helper
  lib/factory/version.py         DATA_VERSION, version checks and report
  lib/factory/registry.py        Step, Pipeline, Registry (3 levels, composite, snapshot)
  lib/factory/pipeline_check.py  Problem, check()
  lib/factory/config.py          resolve(), get_value(), set_value()
  lib/factory/state.py           task.json model and helpers
  lib/factory/events.py          events.jsonl
  lib/factory/engine.py          next, done, skip, goto, block, approve, wait, poll checks, run-script
  lib/factory/session.py         start, pause, resume, deliver, focus, send prompt, notify
  lib/factory/launch.py          slugify, plan_launch, launch, worktree creation
  lib/factory/delete.py          plan_delete, delete, clean_report
  lib/factory/backlog.py
  lib/factory/catalog.py
  lib/factory/library.py         library commit
  lib/factory/requires.py        tool and skill presence
  lib/factory/init.py            prerequisites, init, ensure_link, backlog import
  lib/factory/menu.py            menu model
  lib/factory/migrate.py
  lib/factory/server.py          factory serve, ensure_server, routes
  lib/factory/api.py             route functions shared by editor and dashboard
  lib/factory/cli.py             argparse, dispatch
  lib/factory/adapters/__init__.py
  lib/factory/adapters/base.py
  lib/factory/adapters/herdr.py
  lib/factory/adapters/fake.py
  lib/factory/web/editor.html
  lib/factory/web/dashboard.html
  builtin/steps/{create-task,create-worktree,delete-task,backlog-add,backlog-remove,migrate,user-validation,new-step}.md
  builtin/pipelines/new-step-assistant.yaml
  catalog/pipelines/{quick-task,plan-and-build}.yaml
  catalog/steps/*.md, catalog/steps/*.sh
  migrations/.gitkeep
  tests/conftest.py
  tests/test_*.py
  tests/e2e_herdr.py
  tests/report.py
  README.md
verification/software-factory/
  report.md, e2e-results.json, junit.xml, herdr-probe.md
```

## Shared conventions

- `FactoryError(message)` is the only error shown to users. `cli.main` prints `Error: <message>` to stderr and returns exit code 1.
- `Ctx` is created once per command: `repo.load_ctx(cwd, task_opt)`.
- Each module function takes `ctx` first. Functions that act on a task take `tid` second.
- `--json` prints machine output for the orchestrator and tests. Without it, commands print short text.

---

# Milestone 1: Core

### Task 1: Plugin scaffold, entry script and test harness

**Files:**
- Create: `.claude-plugin/marketplace.json`
- Create: `software-factory/.claude-plugin/plugin.json`
- Create: `software-factory/bin/factory`
- Create: `software-factory/lib/factory/__init__.py` (empty), `errors.py`, `cli.py`
- Create: `software-factory/tests/conftest.py`, `software-factory/tests/test_scaffold.py`

**Interfaces:**
- Produces: `factory.errors.FactoryError`; `factory.cli.main(argv: list[str]) -> int`; `factory.cli.build_parser() -> argparse.ArgumentParser`; `factory.cli.COMMANDS: dict[str, Callable]` registry filled by later tasks; test fixtures `work`, `origin_repo`, `library_path`, `factory` (runner), `inited`; helpers `git()`, `write_step()`, `write_pipeline()`, `fake_calls()`, `fake_config()`.

- [ ] **Step 1: Write marketplace and plugin manifests**

`.claude-plugin/marketplace.json`:

```json
{
  "name": "software-factory",
  "owner": { "name": "Fabien Boismoreau" },
  "plugins": [
    {
      "name": "software-factory",
      "source": "./software-factory",
      "description": "Run each task in its own worktree, Herdr tab and Claude session, through pipelines of reusable steps."
    }
  ]
}
```

`software-factory/.claude-plugin/plugin.json`:

```json
{
  "name": "software-factory",
  "version": "0.1.0",
  "description": "Run each task in its own worktree, Herdr tab and Claude session, through pipelines of reusable steps."
}
```

- [ ] **Step 2: Write the entry script**

`software-factory/bin/factory` (then `chmod +x`):

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from factory.cli import main

sys.exit(main(sys.argv[1:]))
```

`software-factory/lib/factory/errors.py`:

```python
class FactoryError(Exception):
    pass
```

- [ ] **Step 3: Write the CLI skeleton**

`software-factory/lib/factory/cli.py`:

```python
import argparse
import json
import sys

from .errors import FactoryError

VERSION = "0.1.0"
NO_VERSION_CHECK = {"init", "version", "migrate", "link", "terminal check", "menu"}
COMMANDS = {}


def command(name):
    def register(fn):
        COMMANDS[name] = fn
        return fn
    return register


def emit(data, as_json):
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--task", default=None)
    common.add_argument("--json", action="store_true")
    parser = argparse.ArgumentParser(prog="factory")
    parser.add_argument("--version", action="version", version=f"factory {VERSION}")
    sub = parser.add_subparsers(dest="cmd", required=True)
    return parser, sub, common


def command_name(args):
    action = getattr(args, "action", None)
    return f"{args.cmd} {action}" if action else args.cmd


def main(argv):
    parser, sub, common = build_parser()
    from . import commands
    commands.register(sub, common)
    args = parser.parse_args(argv)
    name = command_name(args)
    try:
        if args.cmd not in NO_VERSION_CHECK and name not in NO_VERSION_CHECK:
            from . import repo, version
            ctx = repo.load_ctx(task_opt=args.task)
            version.require_repo(ctx)
        return COMMANDS[name](args) or 0
    except FactoryError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
```

Create `software-factory/lib/factory/commands.py`. Every later task adds its subparsers and handlers here.

```python
from . import cli


def register(sub, common):
    pass
```

- [ ] **Step 4: Write the test harness**

`software-factory/tests/conftest.py`:

```python
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import yaml

SF = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SF.parent
VERIF = PROJECT_ROOT / "verification" / "software-factory"
WORK = VERIF / "work"
BIN = SF / "bin" / "factory"
sys.path.insert(0, str(SF / "lib"))


def git(*args, cwd):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"git {args} failed: {r.stderr}")
    return r.stdout.strip()


def commit_all(repo, message):
    git("add", "-A", cwd=repo)
    git("commit", "-m", message, cwd=repo)


@pytest.fixture
def work(request):
    d = WORK / f"{request.node.name[:40]}-{uuid.uuid4().hex[:6]}"
    d.mkdir(parents=True)
    yield d.resolve()
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def origin_repo(work):
    origin = work / "origin.git"
    git("init", "--bare", "-b", "main", str(origin), cwd=work)
    seed = work / "seed"
    git("clone", str(origin), str(seed), cwd=work)
    git("config", "user.name", "Test", cwd=seed)
    git("config", "user.email", "test@example.com", cwd=seed)
    (seed / "README.md").write_text("test\n")
    commit_all(seed, "init")
    git("push", "origin", "HEAD:main", cwd=seed)
    repo = work / "repo"
    git("clone", str(origin), str(repo), cwd=work)
    git("config", "user.name", "Test", cwd=repo)
    git("config", "user.email", "test@example.com", cwd=repo)
    return repo


@pytest.fixture
def library_path(work):
    root = work / "libroot"
    root.mkdir()
    git("init", "-b", "main", cwd=root)
    git("config", "user.name", "Test", cwd=root)
    git("config", "user.email", "test@example.com", cwd=root)
    (root / "other.txt").write_text("x\n")
    commit_all(root, "init")
    return root / "factory-library"


class Factory:
    def __init__(self, cwd, env):
        self.cwd = cwd
        self.env = env

    def __call__(self, *args, cwd=None, check=True, input=None, env=None):
        r = subprocess.run(
            [sys.executable, str(BIN), *[str(a) for a in args]],
            cwd=cwd or self.cwd,
            env={**self.env, **(env or {})},
            capture_output=True,
            text=True,
            input=input,
            timeout=180,
        )
        if check and r.returncode != 0:
            raise AssertionError(f"factory {args} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
        return r

    def json(self, *args, **kw):
        return json.loads(self(*args, "--json", **kw).stdout)


@pytest.fixture
def factory(work, origin_repo):
    link_dir = work / "bin"
    env = {
        **os.environ,
        "FACTORY_LINK_DIR": str(link_dir),
        "FACTORY_TERMINAL": "fake",
        "FACTORY_NO_OPEN": "1",
        "FACTORY_CLAUDE_HOME": str(work / "claude-home"),
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    env.pop("FACTORY_TASK", None)
    link_dir.mkdir(parents=True, exist_ok=True)
    (link_dir / "factory").symlink_to(BIN)
    env["PATH"] = f"{link_dir}{os.pathsep}{env['PATH']}"
    os.environ["PATH"] = env["PATH"]
    return Factory(origin_repo, env)


class Inited:
    def __init__(self, repo, library, factory, work):
        self.repo = repo
        self.library = library
        self.factory = factory
        self.work = work
        self.fdir = repo / ".factory"
        self.worktrees = work / "worktrees"


def bootstrap_factory_dir(repo, library, worktree_root):
    f = repo / ".factory"
    for d in ("steps", "pipelines", "tasks/archive"):
        (f / d).mkdir(parents=True, exist_ok=True)
    (f / "factory.yaml").write_text(yaml.safe_dump({"version": 1, "library": str(library), "terminal": "fake", "poll_minutes": 5}))
    (f / "config.yaml").write_text(yaml.safe_dump({"create-worktree": {"worktree_root": str(worktree_root)}}))
    (f / "backlog.md").write_text("# Backlog\n")
    (f / "claude-settings.json").write_text('{"permissions": {"allow": ["Bash(factory:*)", "Bash(factory *)"]}}\n')
    for d in ("steps", "pipelines"):
        (library / d).mkdir(parents=True, exist_ok=True)
    (library / "factory.yaml").write_text(yaml.safe_dump({"version": 1}))


@pytest.fixture
def inited(factory, origin_repo, library_path, work):
    bootstrap_factory_dir(origin_repo, library_path, work / "worktrees")
    return Inited(origin_repo, library_path, factory, work)


def write_step(root, sid, manifest, body="Do the step.\n"):
    d = Path(root) / "steps"
    d.mkdir(parents=True, exist_ok=True)
    data = {"id": sid, "description": f"Step {sid}", "category": "test", "type": "prompt", **manifest}
    (d / f"{sid}.md").write_text("---\n" + yaml.safe_dump(data, sort_keys=False) + "---\n\n" + body)
    return d / f"{sid}.md"


def write_pipeline(root, data):
    d = Path(root) / "pipelines"
    d.mkdir(parents=True, exist_ok=True)
    full = {"description": f"Pipeline {data['id']}", **data}
    (d / f"{data['id']}.yaml").write_text(yaml.safe_dump(full, sort_keys=False))
    return d / f"{data['id']}.yaml"


def fake_calls(fdir):
    p = Path(fdir) / "fake_adapter_calls.json"
    return json.loads(p.read_text()).get("calls", []) if p.exists() else []


def fake_config(fdir, **cfg):
    (Path(fdir) / "fake_adapter_config.json").write_text(json.dumps(cfg))


def task_json(fdir, tid):
    return json.loads((Path(fdir) / "tasks" / tid / "task.json").read_text())


def events(fdir, tid):
    p = Path(fdir) / "tasks" / tid / "events.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
```

- [ ] **Step 5: Write the failing scaffold tests**

`software-factory/tests/test_scaffold.py`:

```python
import json
import os
import subprocess
import uuid

from conftest import BIN, PROJECT_ROOT, SF, VERIF


def test_version_prints():
    r = subprocess.run(["uv", "run", "--script", str(BIN), "--version"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "factory 0.1.0" in r.stdout


def test_uv_installs_dependencies_on_first_run(tmp_path_factory):
    cache = VERIF / "work" / f"uv-cache-{uuid.uuid4().hex[:6]}"
    env = {**os.environ, "UV_CACHE_DIR": str(cache)}
    r = subprocess.run(["uv", "run", "--script", str(BIN), "--version"], capture_output=True, text=True, env=env)
    subprocess.run(["rm", "-rf", str(cache)])
    assert r.returncode == 0, r.stderr
    assert "pyyaml" in r.stderr.lower() or "installed" in r.stderr.lower()


def test_marketplace_points_to_plugin():
    data = json.loads((PROJECT_ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert data["name"] == "software-factory"
    assert (PROJECT_ROOT / data["plugins"][0]["source"]).resolve() == SF
    plugin = json.loads((SF / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["name"] == "software-factory"
```

- [ ] **Step 6: Run the tests**

Run: `cd software-factory && uv run --with pytest --with pyyaml pytest tests/test_scaffold.py -q`
Expected: 3 passed. If `test_uv_installs_dependencies_on_first_run` fails on the stderr text, print `r.stderr` and match the actual uv message for an install (uv 0.13 prints `Installed N packages`).

- [ ] **Step 7: Commit**

```bash
git add .claude-plugin software-factory
git commit -m "scaffold: plugin manifests, factory entry script, test harness"
```

### Task 2: Atomic files and locks (`fsio.py`)

**Files:**
- Create: `software-factory/lib/factory/fsio.py`
- Test: `software-factory/tests/test_fsio.py`

**Interfaces:**
- Produces: `atomic_write_text(path: Path, text: str) -> None`; `locked(path: Path)` context manager (lock file `<name>.lock`); `read_text(path, default="") -> str`; `read_yaml(path, default=None)`; `write_yaml(path, data)`; `read_json(path, default=None)`; `write_json(path, data)`; `update_json(path, fn, default_factory=dict)`; `update_yaml(path, fn, default_factory=dict)`; `update_text(path, fn)`; `append_line(path, line)`. `update_*` return what `fn(data)` returns; `fn` mutates `data` in place.

- [ ] **Step 1: Write the failing tests**

```python
import subprocess
import sys
from pathlib import Path

from conftest import SF
from factory import fsio


def test_atomic_write_creates_parents_and_leaves_no_temp(tmp_path):
    p = tmp_path / "a" / "b.json"
    fsio.write_json(p, {"x": 1})
    assert fsio.read_json(p) == {"x": 1}
    assert [f.name for f in p.parent.iterdir()] == ["b.json"]


def test_update_yaml_returns_fn_result(tmp_path):
    p = tmp_path / "c.yaml"
    r = fsio.update_yaml(p, lambda d: d.setdefault("k", "v"))
    assert r == "v"
    assert fsio.read_yaml(p) == {"k": "v"}


def test_lock_file_is_separate(tmp_path):
    p = tmp_path / "d.json"
    with fsio.locked(p):
        assert (tmp_path / "d.json.lock").exists()


WRITER = """
import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from factory import fsio
p = Path(sys.argv[2])
for i in range(200):
    fsio.update_yaml(p, lambda d: d.setdefault("items", []).append(sys.argv[3] + str(i)))
"""


def test_two_processes_lose_no_write(tmp_path):
    p = tmp_path / "shared.yaml"
    procs = [subprocess.Popen([sys.executable, "-c", WRITER, str(SF / "lib"), str(p), tag]) for tag in "ab"]
    assert all(proc.wait(timeout=120) == 0 for proc in procs)
    assert len(fsio.read_yaml(p)["items"]) == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_fsio.py -q`
Expected: FAIL, `cannot import name 'fsio'`.

- [ ] **Step 3: Implement**

```python
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

import yaml


def atomic_write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


@contextmanager
def locked(path):
    path = Path(path)
    lock = path.with_name(path.name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def read_text(path, default=""):
    path = Path(path)
    return path.read_text() if path.exists() else default


def read_yaml(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    data = yaml.safe_load(path.read_text())
    return default if data is None else data


def dump_yaml(data):
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def write_yaml(path, data):
    atomic_write_text(path, dump_yaml(data))


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path, data):
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def update_json(path, fn, default_factory=dict):
    with locked(path):
        data = read_json(path)
        data = default_factory() if data is None else data
        result = fn(data)
        write_json(path, data)
        return result


def update_yaml(path, fn, default_factory=dict):
    with locked(path):
        data = read_yaml(path)
        data = default_factory() if data is None else data
        result = fn(data)
        write_yaml(path, data)
        return result


def update_text(path, fn):
    with locked(path):
        new = fn(read_text(path))
        atomic_write_text(path, new)
        return new


def append_line(path, line):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked(path):
        with open(path, "a") as f:
            f.write(line.rstrip("\n") + "\n")
```

- [ ] **Step 4: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests/test_fsio.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add software-factory/lib/factory/fsio.py software-factory/tests/test_fsio.py
git commit -m "fsio: atomic writes and separate lock files"
```

### Task 3: Repository context and data version (`repo.py`, `version.py`)

**Files:**
- Create: `software-factory/lib/factory/repo.py`, `software-factory/lib/factory/version.py`
- Modify: `software-factory/lib/factory/commands.py` (add `version check`)
- Test: `software-factory/tests/test_repo_version.py`

**Interfaces:**
- Consumes: `fsio.read_yaml`, `fsio.read_json`.
- Produces:
  - `repo.PLUGIN_ROOT: Path`
  - `repo.git(args: list[str], cwd, check=True) -> CompletedProcess`
  - `repo.main_repo(cwd) -> Path`
  - `repo.Ctx(cwd: Path, main: Path, task_opt: str|None)` with `.fdir`, `.factory_yaml() -> dict`, `.library() -> Path|None`, `.initialized() -> bool`, `.columns() -> list[str]`
  - `repo.load_ctx(cwd=None, task_opt=None) -> Ctx`
  - `repo.current_task_id(ctx) -> str` (order: `--task`, `FACTORY_TASK`, worktree match)
  - `repo.task_flag(task: dict) -> str` returns `""` or `" --task <id>"`
  - `version.DATA_VERSION: int` (env `FACTORY_DATA_VERSION` override, default 1)
  - `version.require_repo(ctx)`, `version.require_library(path)`, `version.report(ctx) -> dict` with keys `factory`, `repo`, `library`, `repo_state`, `library_state`, `state` (`same|older|newer`)

- [ ] **Step 1: Write the failing tests**

```python
import os
from pathlib import Path

import pytest
import yaml

from conftest import git
from factory import repo, version
from factory.errors import FactoryError


def test_main_repo_from_worktree(origin_repo, work):
    wt = work / "wt1"
    git("worktree", "add", "--detach", str(wt), cwd=origin_repo)
    assert repo.main_repo(wt) == origin_repo.resolve()


def test_current_task_matches_symlinked_path(origin_repo, work, tmp_path):
    wt = work / "wt2"
    git("worktree", "add", "--detach", str(wt), cwd=origin_repo)
    tdir = origin_repo / ".factory" / "tasks" / "t1"
    tdir.mkdir(parents=True)
    (tdir / "task.json").write_text('{"id": "t1", "worktree": "%s"}' % wt)
    link = tmp_path / "link"
    link.symlink_to(wt)
    ctx = repo.load_ctx(cwd=link)
    assert repo.current_task_id(ctx) == "t1"


def test_unknown_task_says_add_task(origin_repo):
    (origin_repo / ".factory" / "tasks").mkdir(parents=True)
    ctx = repo.load_ctx(cwd=origin_repo)
    with pytest.raises(FactoryError, match="--task <id>"):
        repo.current_task_id(ctx)


def test_factory_task_env(origin_repo, monkeypatch):
    tdir = origin_repo / ".factory" / "tasks" / "t9"
    tdir.mkdir(parents=True)
    (tdir / "task.json").write_text('{"id": "t9", "worktree": null}')
    monkeypatch.setenv("FACTORY_TASK", "t9")
    assert repo.current_task_id(repo.load_ctx(cwd=origin_repo)) == "t9"


def test_version_mismatch_refused(origin_repo):
    f = origin_repo / ".factory"
    f.mkdir()
    (f / "factory.yaml").write_text(yaml.safe_dump({"version": 2}))
    with pytest.raises(FactoryError, match="version"):
        version.require_repo(repo.load_ctx(cwd=origin_repo))


def test_version_report_states(origin_repo):
    f = origin_repo / ".factory"
    f.mkdir()
    (f / "factory.yaml").write_text(yaml.safe_dump({"version": 1}))
    assert version.report(repo.load_ctx(cwd=origin_repo))["state"] == "same"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_repo_version.py -q`
Expected: FAIL, import error.

- [ ] **Step 3: Implement `repo.py`**

```python
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import fsio
from .errors import FactoryError

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COLUMNS = ["Discovery", "Specification", "Plan", "Implementation", "Review", "QA"]
DONE_COLUMN = "Done"


def git(args, cwd, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise FactoryError(f"git {' '.join(args)} failed: {(r.stderr or r.stdout).strip()}")
    return r


def main_repo(cwd):
    r = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd, check=False)
    if r.returncode != 0:
        raise FactoryError("This folder is not in a git repository.")
    return Path(r.stdout.strip()).resolve().parent


@dataclass
class Ctx:
    cwd: Path
    main: Path
    task_opt: str | None = None

    @property
    def fdir(self):
        return self.main / ".factory"

    def factory_yaml(self):
        return fsio.read_yaml(self.fdir / "factory.yaml", {}) or {}

    def library(self):
        lib = self.factory_yaml().get("library")
        return Path(lib).expanduser().resolve() if lib else None

    def initialized(self):
        return (self.fdir / "factory.yaml").exists()

    def columns(self):
        return list(self.factory_yaml().get("columns") or DEFAULT_COLUMNS)


def load_ctx(cwd=None, task_opt=None):
    cwd = Path(cwd or os.getcwd()).resolve()
    return Ctx(cwd=cwd, main=main_repo(cwd), task_opt=task_opt)


def task_exists(ctx, tid):
    return (ctx.fdir / "tasks" / tid / "task.json").exists()


def current_task_id(ctx):
    explicit = ctx.task_opt or os.environ.get("FACTORY_TASK")
    if explicit:
        if not task_exists(ctx, explicit):
            raise FactoryError(f"Unknown task {explicit}.")
        return explicit
    top = Path(git(["rev-parse", "--show-toplevel"], ctx.cwd).stdout.strip()).resolve()
    for tj in sorted((ctx.fdir / "tasks").glob("*/task.json")):
        data = fsio.read_json(tj, {}) or {}
        wt = data.get("worktree")
        if wt and Path(wt).resolve() == top:
            return data["id"]
    raise FactoryError("Cannot find the task for this folder. Add --task <id> to the command.")


def task_flag(task):
    return "" if task.get("worktree") else f" --task {task['id']}"
```

- [ ] **Step 4: Implement `version.py`**

```python
import os

from . import fsio
from .errors import FactoryError

DATA_VERSION = int(os.environ.get("FACTORY_DATA_VERSION", "1"))


def compare(v):
    if v == DATA_VERSION:
        return "same"
    return "older" if v < DATA_VERSION else "newer"


def repo_version(ctx):
    return ctx.factory_yaml().get("version")


def library_version(lib):
    if not lib or not (lib / "factory.yaml").exists():
        return None
    return (fsio.read_yaml(lib / "factory.yaml", {}) or {}).get("version")


def require_repo(ctx):
    if not ctx.initialized():
        raise FactoryError("The factory is not initialized in this repository. Run Init from the orchestrator.")
    v = repo_version(ctx)
    if v != DATA_VERSION:
        raise FactoryError(
            f"The repository data version is {v}, and this factory uses version {DATA_VERSION}. "
            "Start the orchestrator to migrate, or update the factory."
        )


def require_library(lib):
    v = library_version(lib)
    if v is not None and v != DATA_VERSION:
        raise FactoryError(
            f"The library data version is {v}, and this factory uses version {DATA_VERSION}. "
            "Start the orchestrator to migrate, or update the factory."
        )


def report(ctx):
    rv = repo_version(ctx) if ctx.initialized() else None
    lv = library_version(ctx.library()) if ctx.initialized() else None
    states = [compare(v) for v in (rv, lv) if v is not None]
    overall = "newer" if "newer" in states else "older" if "older" in states else "same"
    return {
        "factory": DATA_VERSION,
        "repo": rv,
        "library": lv,
        "repo_state": compare(rv) if rv is not None else None,
        "library_state": compare(lv) if lv is not None else None,
        "state": overall,
        "initialized": ctx.initialized(),
    }
```

- [ ] **Step 5: Add the `version check` command**

In `commands.py`:

```python
from . import cli


def register(sub, common):
    p = sub.add_parser("version")
    vs = p.add_subparsers(dest="action", required=True)
    vs.add_parser("check", parents=[common])


@cli.command("version check")
def version_check(args):
    from . import repo, version
    cli.emit(version.report(repo.load_ctx(task_opt=args.task)), True)
```

From now on, every task that adds commands appends its `add_parser` calls at the end of `register` and its handlers at the end of the file, in the same style. Rule: only leaf parsers get `parents=[common]`. A group parser (`version`, `state`, `config`, `terminal`, `backlog`, `pipeline`, `catalog`, `library`, `approval`) has no parents and a `add_subparsers(dest="action", required=True)`. Otherwise argparse resets `--task` to its default.

- [ ] **Step 6: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add software-factory
git commit -m "repo: main repository, current task, data version check"
```

### Task 4: Steps, pipelines and checks (`registry.py`, `pipeline_check.py`)

**Files:**
- Create: `software-factory/lib/factory/registry.py`, `software-factory/lib/factory/pipeline_check.py`
- Modify: `software-factory/lib/factory/commands.py` (add `pipeline check <id>`)
- Test: `software-factory/tests/test_registry.py`, `software-factory/tests/test_pipeline_check.py`

**Interfaces:**
- Consumes: `repo.Ctx`, `repo.PLUGIN_ROOT`, `fsio.read_yaml`.
- Produces:
  - `registry.STEP_ID_RE`, `registry.NO_WORKTREE_PIPELINES = {"new-step-assistant"}`
  - `registry.Step(id, level, path, manifest, body)` with properties `type`, `run_in`, `required`, `children`, `column`, `model`, `effort`, `done_check`, `done_when`, `wait_external`, `requires`, `category`, `description`, `config_spec`, and `get(key, default)`
  - `registry.Pipeline(id, level, path, data)` with `entries -> list[dict]`, `inputs -> dict`, `claude -> dict`, `start_column -> str|None`
  - `registry.parse_step_text(text, path) -> (dict, str)`
  - `registry.normalize_entry(e) -> dict`
  - `registry.Registry.load(ctx) -> Registry` with `.steps: dict[str, Step]`, `.pipelines: dict[str, Pipeline]`, `.step(id)`, `.pipeline(id)`, `.leaves(id) -> list[list[str]]`, `.io(id) -> (reads, writes)`, `.expand(pipeline) -> list[dict]`, `.categories() -> list[str]`
  - Snapshot entry: `{"id": leaf_id, "path": [ids...], "with": dict, "column": str|None, "model": str|None, "effort": str|None}`
  - `pipeline_check.Problem(level, message)`; `pipeline_check.check(reg, data, columns, save_level=None) -> list[Problem]`; `pipeline_check.errors(problems) -> list[Problem]`

- [ ] **Step 1: Write the failing registry tests**

```python
import pytest

from conftest import write_pipeline, write_step
from factory import repo
from factory.errors import FactoryError
from factory.registry import Registry


def ctx_of(inited):
    return repo.load_ctx(cwd=inited.repo)


def test_local_overrides_generic_overrides_builtin(inited):
    write_step(inited.library, "user-validation", {"description": "generic"})
    reg = Registry.load(ctx_of(inited))
    assert reg.step("user-validation").level == "generic"
    write_step(inited.fdir, "user-validation", {"description": "local"})
    reg = Registry.load(ctx_of(inited))
    assert reg.step("user-validation").level == "local"
    assert reg.step("user-validation").description == "local"


def test_composite_paths_and_io(inited):
    write_step(inited.fdir, "rebase", {"reads": ["base"], "writes": ["rebased"]})
    write_step(inited.fdir, "commit", {"reads": ["rebased", "msg"], "writes": ["sha"]})
    write_step(inited.fdir, "rebase-and-commit", {"type": "composite", "steps": ["rebase", "commit"]}, body="")
    reg = Registry.load(ctx_of(inited))
    assert reg.leaves("rebase-and-commit") == [["rebase-and-commit", "rebase"], ["rebase-and-commit", "commit"]]
    assert reg.io("rebase-and-commit") == (["base", "msg"], ["rebased", "sha"])


def test_composite_loop_refused(inited):
    write_step(inited.fdir, "a", {"type": "composite", "steps": ["b"]}, body="")
    write_step(inited.fdir, "b", {"type": "composite", "steps": ["a"]}, body="")
    with pytest.raises(FactoryError, match="loop"):
        Registry.load(ctx_of(inited))


def test_expand_adds_create_worktree_and_overrides(inited):
    write_step(inited.fdir, "s1", {"model": "haiku"})
    write_pipeline(inited.fdir, {"id": "p1", "steps": [{"id": "s1", "model": "opus", "column": "Plan", "with": {"k": 1}}]})
    reg = Registry.load(ctx_of(inited))
    snap = reg.expand(reg.pipeline("p1"))
    assert [e["id"] for e in snap] == ["create-worktree", "s1"]
    assert snap[1] == {"id": "s1", "path": ["s1"], "with": {"k": 1}, "column": "Plan", "model": "opus", "effort": None}
```

- [ ] **Step 2: Write the failing check tests**

```python
from conftest import write_pipeline, write_step
from factory import repo
from factory.pipeline_check import check
from factory.registry import Registry

COLUMNS = ["Discovery", "Plan"]


def msgs(problems, level):
    return [p.message for p in problems if p.level == level]


def test_each_problem_type(inited):
    write_step(inited.fdir, "local-step", {"reads": ["nothing"], "column": "Nowhere"})
    write_step(inited.fdir, "sess", {})
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    data = {
        "id": "p",
        "steps": [
            {"id": "sess", "model": "opus"},
            {"id": "create-worktree"},
            {"id": "missing"},
            {"id": "local-step"},
        ],
    }
    problems = check(reg, data, COLUMNS, save_level="generic")
    errors = " | ".join(msgs(problems, "error"))
    warnings = " | ".join(msgs(problems, "warning"))
    assert "`create-worktree` is listed, but not as the first step" in errors
    assert "`missing` does not exist" in errors
    assert "column `Nowhere`" in errors
    assert "reads `nothing`" in warnings
    assert "uses the local step `local-step`" in warnings
    assert "runs in the session" in warnings


def test_valid_pipeline_has_no_problem(inited):
    write_step(inited.fdir, "a", {"writes": ["x"]})
    write_step(inited.fdir, "b", {"reads": ["x", "ticket_in"]})
    reg = Registry.load(repo.load_ctx(cwd=inited.repo))
    data = {"id": "ok", "inputs": {"ticket_in": {"description": "t"}}, "steps": ["a", "b"]}
    assert check(reg, data, COLUMNS) == []


def test_cli_pipeline_check(inited):
    write_pipeline(inited.fdir, {"id": "bad", "steps": [{"id": "nope"}]})
    r = inited.factory("pipeline", "check", "bad", check=False)
    assert r.returncode == 1
    assert "does not exist" in r.stdout
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_registry.py tests/test_pipeline_check.py -q`
Expected: FAIL, import error. The `inited` fixture writes `.factory/` directly with `bootstrap_factory_dir` until Task 12 switches it to the real `factory init`.

- [ ] **Step 4: Implement `registry.py`**

```python
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import fsio
from .errors import FactoryError
from .repo import PLUGIN_ROOT

STEP_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
NO_WORKTREE_PIPELINES = {"new-step-assistant"}
CREATE_WORKTREE = "create-worktree"


def parse_step_text(text, path):
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise FactoryError(f"{path}: the step file has no YAML frontmatter.")
    try:
        manifest = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise FactoryError(f"{path}: invalid YAML frontmatter: {e}")
    return manifest, m.group(2).lstrip("\n")


def normalize_entry(e):
    return {"id": e} if isinstance(e, str) else dict(e or {})


@dataclass
class Step:
    id: str
    level: str
    path: Path
    manifest: dict
    body: str

    def get(self, key, default=None):
        return self.manifest.get(key, default)

    @property
    def type(self):
        return self.get("type", "prompt")

    @property
    def run_in(self):
        return self.get("run_in", "session")

    @property
    def required(self):
        return bool(self.get("required", False))

    @property
    def children(self):
        return list(self.get("steps") or [])

    @property
    def column(self):
        return self.get("column")

    @property
    def model(self):
        return self.get("model")

    @property
    def effort(self):
        return self.get("effort")

    @property
    def done_check(self):
        return self.get("done_check")

    @property
    def done_when(self):
        return self.get("done_when", "")

    @property
    def wait_external(self):
        return bool(self.get("wait_external", False))

    @property
    def requires(self):
        return list(self.get("requires") or [])

    @property
    def category(self):
        return self.get("category", "")

    @property
    def description(self):
        return self.get("description", "")

    @property
    def config_spec(self):
        return {k: (v or {}) for k, v in (self.get("config") or {}).items()}


@dataclass
class Pipeline:
    id: str
    level: str
    path: Path
    data: dict

    @property
    def entries(self):
        return [normalize_entry(e) for e in self.data.get("steps") or []]

    @property
    def inputs(self):
        return dict(self.data.get("inputs") or {})

    @property
    def claude(self):
        return dict(self.data.get("claude") or {})

    @property
    def start_column(self):
        return self.data.get("start_column")


def level_roots(ctx):
    roots = [("builtin", PLUGIN_ROOT / "builtin")]
    lib = ctx.library()
    if lib:
        roots.append(("generic", lib))
    roots.append(("local", ctx.fdir))
    return roots


class Registry:
    def __init__(self, steps, pipelines):
        self.steps = steps
        self.pipelines = pipelines

    @classmethod
    def load(cls, ctx):
        steps, pipelines = {}, {}
        for level, root in level_roots(ctx):
            for p in sorted((root / "steps").glob("*.md")):
                manifest, body = parse_step_text(p.read_text(), p)
                sid = manifest.get("id") or p.stem
                steps[sid] = Step(sid, level, p, manifest, body)
            for p in sorted((root / "pipelines").glob("*.yaml")):
                data = fsio.read_yaml(p, {}) or {}
                pid = data.get("id") or p.stem
                pipelines[pid] = Pipeline(pid, level, p, data)
        reg = cls(steps, pipelines)
        reg.check_loops()
        return reg

    def step(self, sid):
        if sid not in self.steps:
            raise FactoryError(f"The step `{sid}` does not exist.")
        return self.steps[sid]

    def pipeline(self, pid):
        if pid not in self.pipelines:
            raise FactoryError(f"The pipeline `{pid}` does not exist.")
        return self.pipelines[pid]

    def check_loops(self):
        def visit(sid, chain):
            if sid in chain:
                raise FactoryError("Composite step loop: " + " > ".join(chain + [sid]))
            step = self.steps.get(sid)
            if step and step.type == "composite":
                for child in step.children:
                    visit(child, chain + [sid])

        for sid in self.steps:
            visit(sid, [])

    def leaves(self, sid, prefix=None):
        prefix = prefix or []
        step = self.step(sid)
        if step.type != "composite":
            return [prefix + [sid]]
        out = []
        for child in step.children:
            out += self.leaves(child, prefix + [sid])
        return out

    def io(self, sid):
        step = self.step(sid)
        if step.type != "composite":
            return list(step.get("reads") or []), list(step.get("writes") or [])
        reads, writes = [], []
        for path in self.leaves(sid):
            leaf = self.step(path[-1])
            for key in leaf.get("reads") or []:
                if key not in writes and key not in reads:
                    reads.append(key)
            for key in leaf.get("writes") or []:
                if key not in writes:
                    writes.append(key)
        return reads, writes

    def expand(self, pipeline):
        entries = pipeline.entries
        if pipeline.id not in NO_WORKTREE_PIPELINES and (not entries or entries[0].get("id") != CREATE_WORKTREE):
            entries = [{"id": CREATE_WORKTREE}] + entries
        snapshot = []
        for entry in entries:
            for i, path in enumerate(self.leaves(entry["id"])):
                snapshot.append({
                    "id": path[-1],
                    "path": path,
                    "with": dict(entry.get("with") or {}),
                    "column": entry.get("column") if i == 0 else None,
                    "model": entry.get("model"),
                    "effort": entry.get("effort"),
                })
        return snapshot

    def categories(self):
        return sorted({s.category for s in self.steps.values() if s.category})
```

- [ ] **Step 5: Implement `pipeline_check.py`**

```python
from dataclasses import dataclass

from .errors import FactoryError
from .registry import CREATE_WORKTREE, STEP_ID_RE, normalize_entry

ALWAYS_AVAILABLE = {"summary", "branch", "ticket"}


@dataclass
class Problem:
    level: str
    message: str

    def to_dict(self):
        return {"level": self.level, "message": self.message}


def errors(problems):
    return [p for p in problems if p.level == "error"]


def check(reg, data, columns, save_level=None):
    problems = []
    error = lambda m: problems.append(Problem("error", m))
    warning = lambda m: problems.append(Problem("warning", m))
    pid = data.get("id") or ""
    if not STEP_ID_RE.match(pid):
        error(f"The pipeline id `{pid}` must be lowercase: letters, digits, `-` or `_`, starting with a letter.")
    entries = [normalize_entry(e) for e in data.get("steps") or []]
    if not entries:
        error("The pipeline has no step.")
    start = data.get("start_column")
    if start and start not in columns:
        error(f"The start column `{start}` is not in the board columns.")
    available = set((data.get("inputs") or {}).keys()) | ALWAYS_AVAILABLE
    for i, entry in enumerate(entries):
        sid = entry.get("id")
        if sid == CREATE_WORKTREE and i != 0:
            error("`create-worktree` is listed, but not as the first step.")
        if sid not in reg.steps:
            error(f"The step `{sid}` does not exist.")
            continue
        step = reg.steps[sid]
        if entry.get("column") and entry["column"] not in columns:
            error(f"Step `{sid}` uses the column `{entry['column']}`, which is not in the board columns.")
        if (save_level or data.get("_level")) == "generic" and step.level == "local":
            warning(f"This generic pipeline uses the local step `{sid}`.")
        try:
            leaves = reg.leaves(sid)
        except FactoryError as e:
            error(str(e))
            continue
        for path in leaves:
            leaf = reg.steps.get(path[-1])
            if leaf is None:
                error(f"The step `{path[-1]}` does not exist.")
                continue
            if leaf.column and leaf.column not in columns:
                error(f"Step `{leaf.id}` uses the column `{leaf.column}`, which is not in the board columns.")
            for key in leaf.get("reads") or []:
                if key not in available:
                    warning(f"Step `{leaf.id}` reads `{key}`, which is not a pipeline input and is not written by an earlier step.")
            available |= set(leaf.get("writes") or [])
            if (entry.get("model") or entry.get("effort")) and leaf.run_in == "session":
                warning(f"Step `{leaf.id}` runs in the session. Its `model` and `effort` have no effect.")
    return problems
```

- [ ] **Step 6: Add `pipeline check <id>`**

In `commands.py` `register`:

```python
    p = sub.add_parser("pipeline")
    ps = p.add_subparsers(dest="action", required=True)
    pc = ps.add_parser("check", parents=[common])
    pc.add_argument("id")
```

Handler:

```python
@cli.command("pipeline check")
def pipeline_check_cmd(args):
    from . import pipeline_check, repo
    from .registry import Registry
    ctx = repo.load_ctx(task_opt=args.task)
    reg = Registry.load(ctx)
    pipeline = reg.pipeline(args.id)
    problems = pipeline_check.check(reg, pipeline.data, ctx.columns(), pipeline.level)
    if args.json:
        cli.emit([p.to_dict() for p in problems], True)
    elif not problems:
        print(f"Pipeline `{args.id}`: no problem.")
    else:
        for p in problems:
            print(f"{p.level.upper()}: {p.message}")
    return 1 if pipeline_check.errors(problems) else 0
```

- [ ] **Step 7: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass. `test_local_overrides_generic_overrides_builtin` needs the built-in `user-validation` step: create it now with the content from Task 8 Step 1, so the test can find a built-in level.

- [ ] **Step 8: Commit**

```bash
git add software-factory
git commit -m "registry: three levels, composite steps, snapshot, pipeline checks"
```

### Task 5: Config, task state and event log (`config.py`, `state.py`, `events.py`)

**Files:**
- Create: `software-factory/lib/factory/config.py`, `state.py`, `events.py`
- Modify: `software-factory/lib/factory/commands.py` (add `config get|set`, `state get|set`, `status`, `artifact path`)
- Test: `software-factory/tests/test_config_state.py`

**Interfaces:**
- Consumes: `fsio`, `repo`, `registry.Step`.
- Produces:
  - `config.resolve(ctx, step, entry_with) -> (dict, list[str])`
  - `config.get_value(ctx, step_id, key)`, `config.set_value(ctx, step_id, key, value)`
  - `state.STATUSES`, `state.now() -> str`, `state.task_dir(ctx, tid) -> Path`, `state.load(ctx, tid) -> dict`, `state.update(ctx, tid, fn) -> dict`, `state.create(ctx, task)`, `state.list_tasks(ctx) -> list[dict]`, `state.current_entry(task) -> dict|None`, `state.step_path_str(task, pos=None) -> str`, `state.set_status(task, status, reason=None)`, `state.get_key(ctx, tid, key)`, `state.set_key(ctx, tid, key, value)`, `state.artifact_path(ctx, tid, name) -> Path`
  - `events.log(ctx, tid, type, step=None, **details)`, `events.read(ctx, tid) -> list[dict]`
- Task record fields: `id, description, pipeline, steps, position, started, status, status_reason, status_since, saved_status, column, worktree, base_ref, session_id, terminal_handle, goto_counts, approval, claude, state, created_at, updated_at`.

- [ ] **Step 1: Write the failing tests**

```python
import json

import pytest

from conftest import write_step
from factory import config, events, repo, state
from factory.errors import FactoryError
from factory.registry import Registry


def make_task(ctx, tid="t1", worktree=None):
    task = {
        "id": tid, "description": "d", "pipeline": "p",
        "steps": [{"id": "s", "path": ["s"], "with": {}, "column": None, "model": None, "effort": None}],
        "position": 0, "started": None, "status": "active", "status_reason": None,
        "status_since": state.now(), "saved_status": None, "column": "Discovery",
        "worktree": worktree, "base_ref": "main", "session_id": "sid", "terminal_handle": None,
        "goto_counts": {}, "approval": None, "claude": {}, "state": {},
        "created_at": state.now(), "updated_at": state.now(),
    }
    state.create(ctx, task)
    return task


def test_config_order(inited):
    write_step(inited.fdir, "s", {"config": {"a": {"description": "A", "default": "def"}, "b": {"description": "B"}, "c": {"description": "C", "default": 1}}})
    ctx = repo.load_ctx(cwd=inited.repo)
    step = Registry.load(ctx).step("s")
    config.set_value(ctx, "s", "c", "saved")
    values, missing = config.resolve(ctx, step, {"c": "with"})
    assert values == {"a": "def", "c": "with"}
    assert missing == ["b"]
    values, _ = config.resolve(ctx, step, {})
    assert values["c"] == "saved"


def test_cli_config_set_get(inited):
    inited.factory("config", "set", "s", "k", "v 1")
    assert inited.factory("config", "get", "s", "k").stdout.strip() == "v 1"


def test_state_set_get_and_artifact_path(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx)
    inited.factory("state", "set", "plan", "/x/plan.md", "--task", "t1")
    assert inited.factory("state", "get", "plan", "--task", "t1").stdout.strip() == "/x/plan.md"
    r = inited.factory("state", "get", "nope", "--task", "t1", check=False)
    assert r.returncode == 1
    p = inited.factory("artifact", "path", "spec.md", "--task", "t1").stdout.strip()
    assert p == str((inited.fdir / "tasks" / "t1" / "artifacts" / "spec.md").resolve())


def test_artifact_name_must_be_simple(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx)
    with pytest.raises(FactoryError):
        state.artifact_path(ctx, "t1", "../x")


def test_events_append(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx)
    events.log(ctx, "t1", "step_started", "s", run_in="session")
    assert events.read(ctx, "t1")[0]["type"] == "step_started"
    assert events.read(ctx, "t1")[0]["run_in"] == "session"
```

Move `make_task` into `conftest.py` (as `make_task(ctx, tid="t1", worktree=None, steps=None, **fields)`, where `steps` replaces the default list and `fields` override any key) so later test files can import it.

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_config_state.py -q`
Expected: FAIL, import error.

- [ ] **Step 3: Implement `config.py`**

```python
from . import fsio


def config_path(ctx):
    return ctx.fdir / "config.yaml"


def saved_section(ctx, step_id):
    data = fsio.read_yaml(config_path(ctx), {}) or {}
    return data.get(step_id) or {}


def resolve(ctx, step, entry_with):
    saved = saved_section(ctx, step.id)
    values, missing = {}, []
    for key, spec in step.config_spec.items():
        if key in (entry_with or {}):
            values[key] = entry_with[key]
        elif key in saved:
            values[key] = saved[key]
        elif "default" in spec:
            values[key] = spec["default"]
        else:
            missing.append(key)
    return values, missing


def get_value(ctx, step_id, key):
    return saved_section(ctx, step_id).get(key)


def set_value(ctx, step_id, key, value):
    def change(data):
        section = data.get(step_id) or {}
        section[key] = value
        data[step_id] = section
    fsio.update_yaml(config_path(ctx), change)
```

- [ ] **Step 4: Implement `state.py`**

```python
import re
from datetime import datetime, timezone

from . import fsio
from .errors import FactoryError

STATUSES = ("active", "blocked", "awaiting_approval", "waiting_external", "paused", "finished")
ARTIFACT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def tasks_dir(ctx):
    return ctx.fdir / "tasks"


def task_dir(ctx, tid):
    return tasks_dir(ctx) / tid


def task_file(ctx, tid):
    return task_dir(ctx, tid) / "task.json"


def load(ctx, tid):
    data = fsio.read_json(task_file(ctx, tid))
    if not data:
        raise FactoryError(f"Unknown task {tid}.")
    return data


def update(ctx, tid, fn):
    if not task_file(ctx, tid).exists():
        raise FactoryError(f"Unknown task {tid}.")

    def change(task):
        fn(task)
        task["updated_at"] = now()
        return task

    return fsio.update_json(task_file(ctx, tid), change)


def create(ctx, task):
    d = task_dir(ctx, task["id"])
    (d / "artifacts").mkdir(parents=True, exist_ok=True)
    fsio.write_json(task_file(ctx, task["id"]), task)


def list_tasks(ctx):
    return [fsio.read_json(p) for p in sorted(tasks_dir(ctx).glob("*/task.json"))]


def current_entry(task):
    pos = task["position"]
    return task["steps"][pos] if pos < len(task["steps"]) else None


def step_path_str(task, pos=None):
    pos = task["position"] if pos is None else pos
    if pos >= len(task["steps"]):
        return "(finished)"
    return " > ".join(task["steps"][pos]["path"])


def set_status(task, status, reason=None):
    task["status"] = status
    task["status_reason"] = reason
    task["status_since"] = now()


def get_key(ctx, tid, key):
    data = load(ctx, tid)["state"]
    if key not in data:
        raise FactoryError(f"The task state key `{key}` is not set.")
    return data[key]


def set_key(ctx, tid, key, value):
    update(ctx, tid, lambda t: t["state"].__setitem__(key, value))


def artifact_path(ctx, tid, name):
    if not ARTIFACT_NAME_RE.match(name):
        raise FactoryError("The artifact name must be a simple file name, for example `plan.md`.")
    d = task_dir(ctx, tid) / "artifacts"
    d.mkdir(parents=True, exist_ok=True)
    return (d / name).resolve()
```

- [ ] **Step 5: Implement `events.py`**

```python
import json

from . import fsio
from .state import now, task_dir


def log(ctx, tid, type, step=None, **details):
    line = json.dumps({"ts": now(), "type": type, "step": step, **details}, ensure_ascii=False)
    fsio.append_line(task_dir(ctx, tid) / "events.jsonl", line)


def read(ctx, tid):
    p = task_dir(ctx, tid) / "events.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
```

- [ ] **Step 6: Add the commands**

In `register`:

```python
    p = sub.add_parser("config")
    cs = p.add_subparsers(dest="action", required=True)
    g = cs.add_parser("get", parents=[common]); g.add_argument("step"); g.add_argument("key")
    s = cs.add_parser("set", parents=[common]); s.add_argument("step"); s.add_argument("key"); s.add_argument("value")
    p = sub.add_parser("state")
    ss = p.add_subparsers(dest="action", required=True)
    g = ss.add_parser("get", parents=[common]); g.add_argument("key")
    s = ss.add_parser("set", parents=[common]); s.add_argument("key"); s.add_argument("value")
    sub.add_parser("status", parents=[common])
    p = sub.add_parser("artifact")
    a = p.add_subparsers(dest="action", required=True)
    ap = a.add_parser("path", parents=[common]); ap.add_argument("name")
```

Handlers:

```python
def ctx_of(args):
    from . import repo
    return repo.load_ctx(task_opt=args.task)


def task_of(args):
    from . import repo
    ctx = ctx_of(args)
    return ctx, repo.current_task_id(ctx)


@cli.command("config get")
def config_get(args):
    from . import config
    value = config.get_value(ctx_of(args), args.step, args.key)
    if value is None:
        raise cli.FactoryError(f"`{args.step}.{args.key}` is not set.")
    print(value)


@cli.command("config set")
def config_set(args):
    from . import config
    config.set_value(ctx_of(args), args.step, args.key, args.value)
    print(f"Saved `{args.step}.{args.key}`.")


@cli.command("state get")
def state_get(args):
    from . import state
    ctx, tid = task_of(args)
    value = state.get_key(ctx, tid, args.key)
    cli.emit(value, args.json) if args.json else print(value)


@cli.command("state set")
def state_set(args):
    from . import state
    ctx, tid = task_of(args)
    state.set_key(ctx, tid, args.key, args.value)
    print(f"Saved `{args.key}`.")


@cli.command("artifact path")
def artifact_path_cmd(args):
    from . import state
    ctx, tid = task_of(args)
    print(state.artifact_path(ctx, tid, args.name))
```

Add `from .errors import FactoryError` in `cli.py` exports (it is already imported there, so `cli.FactoryError` works). `status` is implemented in Task 7.

- [ ] **Step 7: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add software-factory
git commit -m "state: config resolution, task state, artifacts, event log"
```

### Task 6: Terminal adapter interface and fake adapter

**Files:**
- Create: `software-factory/lib/factory/adapters/__init__.py`, `base.py`, `fake.py`
- Modify: `software-factory/lib/factory/commands.py` (add `terminal check`)
- Test: `software-factory/tests/test_adapters.py`

**Interfaces:**
- Produces:
  - `adapters.base.OPTIONAL = ("send_prompt", "focus", "state", "wait_idle", "notify")`
  - `adapters.base.AdapterError(FactoryError)`
  - `adapters.base.Adapter(ctx)` with `name`, `capabilities() -> set[str]`, `check() -> tuple[bool, str]`, `start_session(name, cwd, prompt, claude_args, in_worktree) -> dict`, `close(handle)`, `send_prompt(handle, text)`, `focus(handle)`, `state(handle) -> str`, `wait_idle(handle, timeout_s)`, `notify(text)`
  - `adapters.get_adapter(ctx) -> Adapter`; `adapters.terminal_name(ctx) -> str` (from `factory.yaml` `terminal`, else env `FACTORY_TERMINAL`, else `herdr`)
  - Fake adapter files: `.factory/fake_adapter_config.json` (`capabilities`, `check_ok`, `check_message`, `fail_start`, `state`, `states`), `.factory/fake_adapter_calls.json` (`{"calls": [{"op": ..., ...}]}`)

- [ ] **Step 1: Write the failing tests**

```python
from conftest import fake_calls, fake_config
from factory import adapters, repo


def test_fake_records_calls(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    a = adapters.get_adapter(ctx)
    h = a.start_session("t1", inited.repo, "say \"hi\" $HOME `x`", ["--name", "t1"], False)
    a.send_prompt(h, "next")
    calls = fake_calls(inited.fdir)
    assert calls[0]["op"] == "start_session"
    assert calls[0]["prompt"] == "say \"hi\" $HOME `x`"
    assert calls[1] == {"op": "send_prompt", "handle": h, "text": "next"}


def test_capabilities_and_check(inited):
    fake_config(inited.fdir, capabilities=["focus"], check_ok=False, check_message="nope")
    ctx = repo.load_ctx(cwd=inited.repo)
    a = adapters.get_adapter(ctx)
    assert a.capabilities() == {"focus"}
    assert a.check() == (False, "nope")
    r = inited.factory("terminal", "check", check=False)
    assert r.returncode == 1 and "nope" in r.stdout
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_adapters.py -q`
Expected: FAIL, import error.

- [ ] **Step 3: Implement `base.py`**

```python
from ..errors import FactoryError

OPTIONAL = ("send_prompt", "focus", "state", "wait_idle", "notify")


class AdapterError(FactoryError):
    pass


class Adapter:
    name = ""

    def __init__(self, ctx):
        self.ctx = ctx

    def capabilities(self):
        return set()

    def check(self):
        raise NotImplementedError

    def start_session(self, name, cwd, prompt, claude_args, in_worktree):
        raise NotImplementedError

    def close(self, handle):
        raise NotImplementedError

    def unsupported(self, action):
        raise AdapterError(f"The {self.name} terminal adapter does not support {action}.")

    def send_prompt(self, handle, text):
        self.unsupported("send-prompt")

    def focus(self, handle):
        self.unsupported("focus")

    def state(self, handle):
        self.unsupported("state")

    def wait_idle(self, handle, timeout_s):
        self.unsupported("wait-idle")

    def notify(self, text):
        self.unsupported("notify")
```

- [ ] **Step 4: Implement `adapters/__init__.py`**

```python
import importlib
import os
import re

from .base import AdapterError

ADAPTER_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def terminal_name(ctx):
    return ctx.factory_yaml().get("terminal") or os.environ.get("FACTORY_TERMINAL") or "herdr"


def get_adapter(ctx, name=None):
    name = name or terminal_name(ctx)
    if not ADAPTER_NAME_RE.match(name):
        raise AdapterError(f"Invalid terminal adapter name `{name}`.")
    try:
        module = importlib.import_module(f"factory.adapters.{name}")
    except ModuleNotFoundError:
        raise AdapterError(f"Unknown terminal adapter `{name}`.")
    return module.ADAPTER(ctx)
```

- [ ] **Step 5: Implement `fake.py`**

```python
from .. import fsio
from .base import OPTIONAL, Adapter, AdapterError


class FakeAdapter(Adapter):
    name = "fake"

    def cfg(self):
        return fsio.read_json(self.ctx.fdir / "fake_adapter_config.json", {}) or {}

    def record(self, op, **fields):
        fsio.update_json(
            self.ctx.fdir / "fake_adapter_calls.json",
            lambda d: d.setdefault("calls", []).append({"op": op, **fields}),
        )

    def capabilities(self):
        return set(self.cfg().get("capabilities", OPTIONAL))

    def check(self):
        cfg = self.cfg()
        return bool(cfg.get("check_ok", True)), cfg.get("check_message", "Fake terminal is available.")

    def start_session(self, name, cwd, prompt, claude_args, in_worktree):
        self.record("start_session", name=name, cwd=str(cwd), prompt=prompt, args=list(claude_args), in_worktree=in_worktree)
        if self.cfg().get("fail_start"):
            raise AdapterError("The fake adapter failed to start the session.")
        return {"agent": name, "fake": True}

    def close(self, handle):
        self.record("close", handle=handle)

    def require(self, action):
        if action not in self.capabilities():
            self.unsupported(action.replace("_", "-"))

    def send_prompt(self, handle, text):
        self.require("send_prompt")
        self.record("send_prompt", handle=handle, text=text)

    def focus(self, handle):
        self.require("focus")
        self.record("focus", handle=handle)

    def state(self, handle):
        self.require("state")
        cfg = self.cfg()
        return cfg.get("states", {}).get(handle.get("agent"), cfg.get("state", "idle"))

    def wait_idle(self, handle, timeout_s):
        self.require("wait_idle")
        self.record("wait_idle", handle=handle)

    def notify(self, text):
        self.require("notify")
        self.record("notify", text=text)


ADAPTER = FakeAdapter
```

- [ ] **Step 6: Add `terminal check`**

In `register`:

```python
    p = sub.add_parser("terminal")
    ts = p.add_subparsers(dest="action", required=True)
    ts.add_parser("check", parents=[common])
```

Handler (works before Init):

```python
@cli.command("terminal check")
def terminal_check(args):
    from . import adapters, repo
    ctx = repo.load_ctx(task_opt=args.task)
    ok, message = adapters.get_adapter(ctx).check()
    print(("OK: " if ok else "FAILED: ") + message)
    return 0 if ok else 1
```

- [ ] **Step 7: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add software-factory
git commit -m "adapters: terminal adapter interface and fake adapter"
```

Note on the `factory` fixture: it links `<work>/bin/factory` to `bin/factory` and puts that folder first in `PATH`, also for the test process, so `done_check` commands such as `factory approval check` work in tests. Task 12 makes `init` replace this link in place, which is the same target.

### Task 7: Step engine core (`engine.py`): next, done, skip, run-script, status

**Files:**
- Create: `software-factory/lib/factory/engine.py`, `software-factory/lib/factory/session.py` (only `notify` in this task)
- Modify: `software-factory/lib/factory/commands.py` (add `next`, `done`, `skip`, `run-script`, `status`)
- Modify: `software-factory/tests/conftest.py` (add `task_from_pipeline`)
- Test: `software-factory/tests/test_engine.py`

**Interfaces:**
- Consumes: `registry.Registry`, `config.resolve`, `state.*`, `events.log`, `repo.task_flag`, `adapters.get_adapter`.
- Produces:
  - `engine.DONE_CHECK_TIMEOUT = 300`, `engine.POLL_CHECK_TIMEOUT = 60`
  - `engine.cmd(task, text) -> str` (`"factory <text>"` plus `--task` when needed)
  - `engine.task_cwd(ctx, task) -> Path`
  - `engine.run_check(ctx, task, command, timeout, values=None) -> (bool, str)` (`values`: resolved config, exported as `FACTORY_CONFIG_*`)
  - `engine.load_step(ctx, task) -> (entry, Step)`
  - `engine.settings(entry, step) -> (model, effort)`
  - `engine.on_start(ctx, task, entry, step) -> list[tuple[str, dict]]` (events to log; Task 14 and 15 extend it)
  - `engine.next_step(ctx, tid) -> str`, `engine.done(ctx, tid) -> str`, `engine.skip(ctx, tid) -> str`, `engine.advance(ctx, tid, event_type) -> str`, `engine.run_script(ctx, tid) -> int`, `engine.status_text(ctx, tid) -> str`
  - `session.notify(ctx, text) -> None` (silent when the adapter has no `notify`)
- Script steps and `done_check` commands get config values as env vars `FACTORY_CONFIG_<KEY>` (key upper case, `-` replaced by `_`) and `FACTORY_TASK`.

- [ ] **Step 1: Add the test helper to `conftest.py`**

```python
def task_from_pipeline(inited, pid, tid="t1", worktree=None, **fields):
    from factory import repo
    from factory.registry import Registry
    ctx = repo.load_ctx(cwd=inited.repo)
    reg = Registry.load(ctx)
    snapshot = reg.expand(reg.pipeline(pid))
    position = 1 if snapshot and snapshot[0]["id"] == "create-worktree" else 0
    return make_task(ctx, tid=tid, worktree=worktree, steps=snapshot, position=position, pipeline=pid, **fields)
```

- [ ] **Step 2: Write the failing tests**

```python
import pytest

from conftest import events, task_from_pipeline, task_json, write_pipeline, write_step
from factory import engine, repo
from factory.errors import FactoryError


@pytest.fixture
def flow(inited):
    write_step(inited.fdir, "make", {"done_check": "test -f made.txt", "writes": ["out"]}, body="Create `made.txt`. Then run `factory state set out made.txt`.\n")
    write_step(inited.fdir, "must", {"required": True})
    write_step(inited.fdir, "rebase", {})
    write_step(inited.fdir, "commit", {})
    write_step(inited.fdir, "rebase-and-commit", {"type": "composite", "steps": ["rebase", "commit"]}, body="")
    write_pipeline(inited.fdir, {"id": "flow", "steps": ["make", "must", "rebase-and-commit"]})
    task_from_pipeline(inited, "flow")
    return inited


def run(flow, *args, check=True):
    return flow.factory(*args, "--task", "t1", check=check)


def test_next_done_check_fails_then_passes(flow):
    out = run(flow, "next").stdout
    assert "step 2 of 5: make" in out
    assert "`factory state set out made.txt --task t1`" in out
    r = run(flow, "done", check=False)
    assert r.returncode == 1 and "done check failed" in r.stderr
    (flow.repo / "made.txt").write_text("x")
    assert "Step done" in run(flow, "done").stdout
    kinds = [e["type"] for e in events(flow.fdir, "t1")]
    assert kinds == ["step_started", "done_check_failed", "step_done"]


def test_skip_refused_for_required_and_composite_path(flow):
    (flow.repo / "made.txt").write_text("x")
    run(flow, "next"); run(flow, "done"); run(flow, "next")
    r = run(flow, "skip", check=False)
    assert r.returncode == 1 and "required" in r.stderr
    run(flow, "done")
    assert "rebase-and-commit > rebase" in run(flow, "next").stdout


def test_last_done_finishes(flow):
    (flow.repo / "made.txt").write_text("x")
    for _ in range(4):
        run(flow, "next"); run(flow, "done")
    t = task_json(flow.fdir, "t1")
    assert t["status"] == "finished"
    assert t["column"] == "Done"
    assert events(flow.fdir, "t1")[-1]["type"] == "task_finished"
    assert "finished" in run(flow, "next").stdout


def test_missing_config_asks(inited):
    write_step(inited.fdir, "cfg", {"config": {"target_branch": {"description": "Target branch"}}})
    write_pipeline(inited.fdir, {"id": "c", "steps": ["cfg"]})
    task_from_pipeline(inited, "c")
    out = inited.factory("next", "--task", "t1").stdout
    assert "factory config set cfg target_branch <value>" in out
    assert events(inited.fdir, "t1")[-1] == {**events(inited.fdir, "t1")[-1], "type": "config_asked", "key": "target_branch"}
    inited.factory("config", "set", "cfg", "target_branch", "release")
    assert "- target_branch: release" in inited.factory("next", "--task", "t1").stdout


def test_subagent_call_model_effort_precedence(inited):
    write_step(inited.fdir, "sub", {"run_in": "subagent", "model": "haiku", "effort": "low", "reads": ["ticket"]}, body="Analyze it.\n")
    write_pipeline(inited.fdir, {"id": "s", "steps": [{"id": "sub", "model": "opus"}]})
    task_from_pipeline(inited, "s", state={"ticket": "ABC-1"})
    out = inited.factory("next", "--task", "t1").stdout
    assert "Call the Agent tool" in out
    assert "- model: opus" in out
    assert "- effort: low" in out
    assert "- ticket: ABC-1" in out
    assert "Analyze it." in out
    started = events(inited.fdir, "t1")[0]
    assert (started["run_in"], started["model"], started["effort"]) == ("subagent", "opus", "low")


def test_done_check_timeout(inited, monkeypatch):
    write_step(inited.fdir, "slow", {"done_check": "sleep 5"})
    write_pipeline(inited.fdir, {"id": "slow", "steps": ["slow"]})
    task_from_pipeline(inited, "slow")
    monkeypatch.setattr(engine, "DONE_CHECK_TIMEOUT", 1)
    ctx = repo.load_ctx(cwd=inited.repo)
    with pytest.raises(FactoryError, match="Timed out"):
        engine.done(ctx, "t1")
    assert events(inited.fdir, "t1")[-1]["type"] == "done_check_failed"


def test_run_script_gets_config_and_task(inited):
    step = write_step(inited.fdir, "scr", {"type": "script", "config": {"word": {"description": "w", "default": "hello"}}}, body="scr.sh\n")
    (step.parent / "scr.sh").write_text('echo "$FACTORY_CONFIG_WORD" > "$(factory artifact path out.txt)"\n')
    write_pipeline(inited.fdir, {"id": "scr", "steps": ["scr"]})
    task_from_pipeline(inited, "scr")
    assert "`factory run-script --task t1`" in inited.factory("next", "--task", "t1").stdout
    inited.factory("run-script", "--task", "t1")
    assert (inited.fdir / "tasks" / "t1" / "artifacts" / "out.txt").read_text().strip() == "hello"
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_engine.py -q`
Expected: FAIL, `invalid choice: 'next'`.

- [ ] **Step 4: Implement `session.py` (notify only)**

```python
from . import adapters
from .adapters.base import AdapterError


def notify(ctx, text):
    adapter = adapters.get_adapter(ctx)
    if "notify" not in adapter.capabilities():
        return
    try:
        adapter.notify(text)
    except AdapterError:
        pass
```

- [ ] **Step 5: Implement `engine.py`**

```python
import os
import re
import subprocess
from pathlib import Path

from . import config, events, repo, session, state
from .errors import FactoryError
from .registry import Registry

DONE_CHECK_TIMEOUT = 300
POLL_CHECK_TIMEOUT = 60
FACTORY_SPAN_RE = re.compile(r"`(factory [^`]*)`")


def cmd(task, text):
    return f"factory {text}{repo.task_flag(task)}"


def with_task_flag(text, tid):
    def add(m):
        inner = m.group(1)
        return m.group(0) if "--task" in inner else f"`{inner} --task {tid}`"
    return FACTORY_SPAN_RE.sub(add, text)


def task_cwd(ctx, task):
    return Path(task["worktree"]) if task.get("worktree") else ctx.main


def artifacts_dir(ctx, task):
    return (state.task_dir(ctx, task["id"]) / "artifacts").resolve()


def run_check(ctx, task, command, timeout, values=None):
    env = script_env(ctx, task, values or {})
    try:
        r = subprocess.run(command, shell=True, cwd=task_cwd(ctx, task), env=env,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"Timed out after {timeout} s."
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def load_step(ctx, task):
    entry = state.current_entry(task)
    if entry is None:
        raise FactoryError("The pipeline is finished.")
    return entry, Registry.load(ctx).step(entry["id"])


def settings(entry, step):
    return entry.get("model") or step.model, entry.get("effort") or step.effort


def require_running(task):
    if task["status"] == "paused":
        raise FactoryError("The task is paused. Resume it first.")


def on_start(ctx, task, entry, step):
    return []


def start(ctx, tid, entry, step):
    pending = []

    def change(t):
        t["started"] = t["position"]
        pending.extend(on_start(ctx, t, entry, step))

    task = state.update(ctx, tid, change)
    path = state.step_path_str(task)
    model, effort = settings(entry, step)
    events.log(ctx, tid, "step_started", path, run_in=step.run_in, model=model, effort=effort)
    for event_type, details in pending:
        events.log(ctx, tid, event_type, path, **details)
    return task


def header(task, step):
    lines = [
        f"Task `{task['id']}`, step {task['position'] + 1} of {len(task['steps'])}: {state.step_path_str(task)}",
        f"Type: {step.type}. Runs in: {step.run_in}.",
    ]
    if step.done_when:
        lines.append(f"Done when: {step.done_when}")
    return lines


def context_lines(ctx, task, step, values):
    lines = []
    if values:
        lines += ["", "Config:"] + [f"- {k}: {v}" for k, v in values.items()]
    reads = step.get("reads") or []
    if reads:
        lines += ["", "Task state:"] + [f"- {k}: {task['state'].get(k, '(not set)')}" for k in reads]
    writes = step.get("writes") or []
    if writes:
        lines += ["", f"Save these task state keys with `factory state set <key> <value>`: {', '.join(writes)}."]
    lines += ["", f"Artifacts folder: {artifacts_dir(ctx, task)}"]
    return lines


def subagent_block(ctx, task, entry, step, values):
    model, effort = settings(entry, step)
    prompt = [
        f"You run one step of the factory task `{task['id']}`: {state.step_path_str(task)}.",
        f"Working folder: {task_cwd(ctx, task)}",
        *context_lines(ctx, task, step, values),
        "",
        "Instructions:",
        step.body.strip(),
        "",
        "Write your outputs with `factory state set <key> <value>`.",
        "End with a short report. If you need an answer from the user, say so in the report and stop.",
    ]
    return [
        "Run this step in a subagent. Call the Agent tool with:",
        f"- model: {model or 'inherit'}",
        f"- effort: {effort or 'inherit'}",
        "- prompt:",
        "<<<",
        with_task_flag("\n".join(prompt), task["id"]),
        ">>>",
    ]


def end_line(step):
    if step.wait_external:
        return "When the actions of this step are done, run `factory wait`. The factory tells you when the external event happens."
    if step.run_in == "subagent":
        return "When the subagent ends, read its report. If it needs the user, ask the user, then run `factory next` again. Otherwise run `factory done`."
    return "When the step is done, run `factory done`."


def render(ctx, task, entry, step, values):
    lines = header(task, step)
    if step.run_in == "subagent" and step.type in ("prompt", "skill"):
        lines += [""] + subagent_block(ctx, task, entry, step, values)
    else:
        lines += context_lines(ctx, task, step, values)
        if step.type == "script":
            lines += ["", "Run the step script with `factory run-script`. It prints the script output and its exit code."]
        else:
            lines += ["", "Instructions:", step.body.strip()]
    lines += ["", end_line(step)]
    text = "\n".join(lines)
    return with_task_flag(text, task["id"]) if not task.get("worktree") else text


def render_missing(task, step, missing):
    lines = header(task, step) + ["", "Some config values are missing. Ask the user for each one, then save it:"]
    for key in missing:
        desc = step.config_spec[key].get("description", "")
        lines.append(f"- `{key}`: {desc} Save it with `factory config set {step.id} {key} <value>`.")
    lines.append("Then run `factory next` again.")
    text = "\n".join(lines)
    return with_task_flag(text, task["id"]) if not task.get("worktree") else text


def next_step(ctx, tid):
    task = state.load(ctx, tid)
    if task["status"] == "finished":
        return "The pipeline is finished."
    require_running(task)
    entry, step = load_step(ctx, task)
    values, missing = config.resolve(ctx, step, entry.get("with"))
    if missing:
        for key in missing:
            events.log(ctx, tid, "config_asked", state.step_path_str(task), key=key)
        return render_missing(task, step, missing)
    if task.get("started") != task["position"]:
        task = start(ctx, tid, entry, step)
    return render(ctx, task, entry, step, values)


def advance(ctx, tid, event_type):
    before = state.load(ctx, tid)
    events.log(ctx, tid, event_type, state.step_path_str(before))

    def change(t):
        t["position"] += 1
        t["started"] = None
        t["approval"] = None
        if t["position"] >= len(t["steps"]):
            state.set_status(t, "finished")
            t["column"] = repo.DONE_COLUMN
        elif t["status"] != "active":
            state.set_status(t, "active")

    task = state.update(ctx, tid, change)
    if task["status"] != "finished":
        return f"Step done. Run `{cmd(task, 'next')}`."
    if before["column"] != repo.DONE_COLUMN:
        events.log(ctx, tid, "column_changed", None, **{"from": before["column"], "to": repo.DONE_COLUMN})
    events.log(ctx, tid, "task_finished")
    session.notify(ctx, f"Task {tid} is finished.")
    return "The pipeline is finished. Tell the user that the task is finished."


def done(ctx, tid):
    task = state.load(ctx, tid)
    if task["status"] == "finished":
        return "The pipeline is finished."
    require_running(task)
    entry, step = load_step(ctx, task)
    if step.done_check:
        values, _ = config.resolve(ctx, step, entry.get("with"))
        ok, output = run_check(ctx, task, step.done_check, DONE_CHECK_TIMEOUT, values)
        if not ok:
            events.log(ctx, tid, "done_check_failed", state.step_path_str(task), output=output)
            raise FactoryError(f"The done check failed. The step is not done.\nCheck: {step.done_check}\n{output}")
    return advance(ctx, tid, "step_done")


def skip(ctx, tid):
    task = state.load(ctx, tid)
    require_running(task)
    entry, step = load_step(ctx, task)
    if step.required:
        raise FactoryError(f"The step `{step.id}` is required. It cannot be skipped.")
    return advance(ctx, tid, "step_skipped")


def script_env(ctx, task, values):
    env = {**os.environ, "FACTORY_TASK": task["id"]}
    for key, value in values.items():
        env["FACTORY_CONFIG_" + key.upper().replace("-", "_")] = str(value)
    return env


def run_script(ctx, tid):
    task = state.load(ctx, tid)
    require_running(task)
    entry, step = load_step(ctx, task)
    if step.type != "script":
        raise FactoryError(f"The step `{step.id}` is not a script step.")
    first_line = step.body.strip().splitlines()[0].strip() if step.body.strip() else ""
    script = (step.path.parent / first_line).resolve()
    if not first_line or not script.is_file():
        raise FactoryError(f"The script of step `{step.id}` does not exist: {script}")
    values, _ = config.resolve(ctx, step, entry.get("with"))
    r = subprocess.run(["bash", str(script)], cwd=task_cwd(ctx, task), env=script_env(ctx, task, values))
    print(f"Script exit code: {r.returncode}")
    return r.returncode


def status_text(ctx, tid):
    task = state.load(ctx, tid)
    lines = [
        f"Task: {task['id']}",
        f"Description: {task['description']}",
        f"Pipeline: {task['pipeline']}",
        f"Step: {state.step_path_str(task)} ({min(task['position'] + 1, len(task['steps']))} of {len(task['steps'])})",
        f"Status: {task['status']}" + (f" ({task['status_reason']})" if task.get("status_reason") else ""),
    ]
    return "\n".join(lines)
```

- [ ] **Step 6: Add the commands**

In `register`:

```python
    for name in ("next", "done", "skip", "run-script", "status"):
        sub.add_parser(name, parents=[common])
```

Handlers:

```python
@cli.command("next")
def next_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.next_step(ctx, tid))


@cli.command("done")
def done_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.done(ctx, tid))


@cli.command("skip")
def skip_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.skip(ctx, tid))


@cli.command("run-script")
def run_script_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    return engine.run_script(ctx, tid)


@cli.command("status")
def status_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.status_text(ctx, tid))
```

- [ ] **Step 7: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add software-factory
git commit -m "engine: next, done, skip, run-script, status"
```

### Task 8: Built-in steps

**Files:**
- Create: `software-factory/builtin/steps/create-task.md`, `create-worktree.md`, `delete-task.md`, `backlog-add.md`, `backlog-remove.md`, `migrate.md`, `user-validation.md`
- Test: `software-factory/tests/test_builtin.py`

**Interfaces:**
- Produces: built-in step ids used by later tasks. `user-validation` config keys: `target` (default `worktree`), `artifact_key` (default empty), `ide_command` (no default). `create-worktree` config keys: `worktree_root` (no default), `base_ref` (default `main`).

- [ ] **Step 1: Write the step files**

`builtin/steps/create-task.md`:

```markdown
---
id: create-task
description: Create a task from a pipeline, with its worktree and session
category: factory
type: prompt
reads: []
writes: []
done_when: The task exists and its session started.
required: true
---

Run in the orchestrator session, never in a task session.

1. Collect the pipeline id, the description and every pipeline input from the user. Offer to start from a backlog entry first (`factory backlog list --json`).
2. Run `factory launch <pipeline> --description "<text>" --input <key>=<value> ... --dry-run --json` and show the result: task id, worktree path, branch case, missing inputs, missing config and errors.
3. For each missing config value, ask the user and run `factory config set <step> <key> <value>`. Then run the dry run again.
4. Launch only after the user confirms: the same command without `--dry-run`. Add `--from-backlog <id>` when started from a backlog entry.
```

`builtin/steps/create-worktree.md`:

```markdown
---
id: create-worktree
description: Create the task worktree from the latest origin base branch
category: git
type: prompt
reads: [branch]
writes: [branch]
done_when: The worktree exists.
required: true
config:
  worktree_root:
    description: The folder where the factory creates the task worktrees
  base_ref:
    description: The branch the worktree starts from
    default: main
---

`factory launch` runs this step before the task session starts. A task session never runs it.
```

`builtin/steps/delete-task.md`:

```markdown
---
id: delete-task
description: Delete a task, its session, terminal, worktree and local branch
category: factory
type: prompt
done_when: The task folder is in the archive.
required: true
---

Run in the orchestrator session.

1. Run `factory delete <id> --dry-run --json` and show what will be removed, the uncommitted changes and the unpushed commits.
2. Ask the user to confirm. If there are uncommitted changes or unpushed commits, say it clearly and ask for explicit approval.
3. Run `factory delete <id>`, with `--confirm-unpushed` only after that explicit approval.
```

`builtin/steps/backlog-add.md`:

```markdown
---
id: backlog-add
description: Add an entry at the end of the backlog
category: backlog
type: prompt
done_when: The entry is in the backlog.
required: false
---

Run in the orchestrator session.

1. Ask for the title, a short summary, and an optional pipeline id (`factory pipeline list --json` shows them).
2. Run `factory backlog add "<title>" --summary "<summary>"`, with `--pipeline <id>` when given.
```

`builtin/steps/backlog-remove.md`:

```markdown
---
id: backlog-remove
description: Remove an entry from the backlog
category: backlog
type: prompt
done_when: The entry is no longer in the backlog.
required: false
---

Run in the orchestrator session.

1. Run `factory backlog list --json` and show a numbered list.
2. Ask which entry to remove, and confirm.
3. Run `factory backlog remove <id>`.
```

`builtin/steps/migrate.md`:

```markdown
---
id: migrate
description: Migrate the factory data and the library to the current data version
category: factory
type: prompt
done_when: factory version check reports the same version.
done_check: factory version check --json | grep -q '"state": "same"'
required: true
---

Run in the orchestrator session, before the menu.

1. Run `factory migrate --dry-run --json` and show what will be migrated and backed up.
2. Run `factory migrate --json`. Show the summary and the backup paths.
3. If the library changed and is in a git repository, show the changed files and the commit message `Factory library: migrate to version <n>`. Commit with `factory library commit` only after approval.
```

`builtin/steps/user-validation.md`:

```markdown
---
id: user-validation
description: Wait until the user approves a result
category: review
type: prompt
done_when: The user approved the result.
done_check: factory approval check
required: false
run_in: session
config:
  target:
    description: What to validate, `artifact` or `worktree`
    default: worktree
  artifact_key:
    description: The task state key that holds the artifact path, when target is artifact
    default: ""
---

The task is now `awaiting_approval`.

1. Show what to validate:
   - When `target` is `artifact`: the path stored in the task state key named by `artifact_key`, and a short summary of the file.
   - When `target` is `worktree`: `git status` and a short summary of the diff. Offer `factory open-ide`.
2. Ask the user to approve or to request changes. The user can also answer from the dashboard.
3. When the user approves here, run `factory approve`, then `factory done`.
4. When the user requests changes here, run `factory request-changes "<text>"`, make the changes, then run `factory next`.
5. When you receive "The user approved. Run `factory done`.", run `factory done`.
6. When you receive "The user requested changes: ...", make the changes, then run `factory next`.
```

- [ ] **Step 2: Write the test**

```python
from conftest import SF
from factory.registry import parse_step_text

BUILTINS = ["create-task", "create-worktree", "delete-task", "backlog-add", "backlog-remove", "migrate", "user-validation"]


def test_builtin_steps_parse():
    for sid in BUILTINS:
        path = SF / "builtin" / "steps" / f"{sid}.md"
        manifest, body = parse_step_text(path.read_text(), path)
        assert manifest["id"] == sid
        assert manifest["description"] and manifest["category"] and manifest["done_when"]
        assert body.strip()
```

- [ ] **Step 3: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add software-factory/builtin software-factory/tests/test_builtin.py
git commit -m "builtin: built-in steps"
```

### Task 9: Herdr probe and Herdr adapter

This task talks to the real Herdr session. Create only objects with labels starting with `sf-probe`. Record every id you create. Close only those ids.

**Files:**
- Create: `verification/software-factory/herdr-probe.md`
- Create: `software-factory/lib/factory/adapters/herdr.py`
- Test: `software-factory/tests/test_herdr_adapter.py`, `software-factory/tests/fake_herdr.py`

**Interfaces:**
- Consumes: `adapters.base.Adapter`, `OPTIONAL`, `AdapterError`.
- Produces: `adapters.herdr.HerdrAdapter`, `ADAPTER`. Handle: `{"agent": name, "workspace": id}` or `{"agent": name, "tab": id}`.

- [ ] **Step 1: Probe Herdr and write `herdr-probe.md`**

Run each command, paste its JSON output in `verification/software-factory/herdr-probe.md` with one heading per question:

```bash
P=verification/software-factory/work/probe; rm -rf "$P"; mkdir -p "$P"
git init -q -b main "$P/repo" && git -C "$P/repo" commit -q --allow-empty -m init
git -C "$P/repo" worktree add -q --detach "$P/wt"
herdr worktree open --cwd "$P/repo" --path "$P/wt" --label sf-probe --no-focus
SID=$(uuidgen | tr A-Z a-z)
herdr agent start sf-probe --kind claude --pane <root_pane.pane_id> --timeout 60000 -- --name sf-probe --session-id "$SID"
herdr agent read sf-probe --source recent-unwrapped --lines 60
herdr agent prompt sf-probe "Reply with the word OK only." --wait --timeout 120000
herdr agent get sf-probe
herdr notification show "Software factory" --body "Probe notification" --sound none
herdr workspace close <workspace_id>
pgrep -fl "$SID"
```

Answer these questions in the file:

1. Q1: JSON keys of `worktree open`. Does `result.root_pane` hold `pane_id` and `workspace_id`, like `tab create`?
2. Q2: Does Claude show the folder trust dialog in the new worktree? What text? What does `agent start` return then?
3. Q3: Key path of the agent status in `agent get`.
4. Q4: After `workspace close`, is the Claude process still running (`pgrep`)?
5. Q5: Resume. Open a tab with `herdr tab create --cwd "$P/wt" --label sf-probe-2 --no-focus`, start with `-- --name sf-probe --resume "$SID"`, and check that Claude remembers the first prompt. Also try `--session-id "$SID" --resume "$SID"` and record the error (A5).
6. Q6: Does `agent start` accept arguments with spaces and quotes after `--` unchanged?

Close every workspace and tab you created, using the recorded ids only. Then `rm -rf "$P"`.

- [ ] **Step 2: STOP and report the trust finding to the user**

The controller sends the user the answer to Q2 (and Q4, Q5) and asks which trust fix to use (spec D7): `worktree_root` under a trusted folder, if trust is inherited, or ask the user to accept the dialog once. Do not continue this task before the user answers. Write the decision at the end of `herdr-probe.md`.

- [ ] **Step 3: Write the fake `herdr` binary for tests**

`software-factory/tests/fake_herdr.py`:

```python
#!/usr/bin/env python3
import json
import os
import sys

log = os.environ["FAKE_HERDR_LOG"]
with open(log, "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\n")
args = sys.argv[1:]
mode = os.environ.get("FAKE_HERDR_MODE", "ok")
pane = {"pane_id": "w9:p1", "workspace_id": "w9", "tab_id": "w9:t1"}
if args[:2] == ["worktree", "open"]:
    print(json.dumps({"result": {"workspace": {"workspace_id": "w9"}, "tab": {"tab_id": "w9:t1"}, "root_pane": pane}}))
elif args[:2] == ["tab", "create"]:
    print(json.dumps({"result": {"tab": {"tab_id": "w9:t1"}, "root_pane": pane}}))
elif args[:2] == ["agent", "start"] and mode == "trust":
    print(json.dumps({"error": {"code": "agent_not_ready"}}))
    sys.exit(1)
elif args[:2] == ["agent", "read"]:
    print("Do you trust the files in this folder?" if mode == "trust" else "ready")
elif args[:2] == ["agent", "get"]:
    if mode == "gone":
        print(json.dumps({"error": {"code": "agent_not_found"}}))
        sys.exit(1)
    print(json.dumps({"result": {"agent": {"name": args[2], "agent_status": "idle"}}}))
else:
    print(json.dumps({"result": {"type": "ok"}}))
```

Adjust the canned JSON to match the real keys recorded in Q1 and Q3.

- [ ] **Step 4: Write the failing adapter tests**

```python
import json
import os
import stat

import pytest

from conftest import SF
from factory import repo
from factory.adapters.base import AdapterError
from factory.adapters.herdr import HerdrAdapter


@pytest.fixture
def herdr_env(tmp_path, monkeypatch, origin_repo):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "herdr"
    exe.write_text(f"#!/bin/sh\nexec python3 {SF / 'tests' / 'fake_herdr.py'} \"$@\"\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "herdr.log"
    monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_HERDR_LOG", str(log))
    monkeypatch.setenv("HERDR_ENV", "1")
    adapter = HerdrAdapter(repo.load_ctx(cwd=origin_repo))
    return adapter, lambda: [json.loads(l) for l in log.read_text().splitlines()]


def test_start_in_worktree(herdr_env, origin_repo):
    adapter, calls = herdr_env
    prompt = 'Run `factory next`. Say "hi" $HOME'
    handle = adapter.start_session("t1", origin_repo / "wt", prompt, ["--name", "t1", "--settings", "/a b/c.json"], True)
    assert handle == {"agent": "t1", "workspace": "w9"}
    c = calls()
    assert c[0][:2] == ["worktree", "open"] and "--no-focus" in c[0]
    assert c[1][:3] == ["agent", "start", "t1"] and c[1][c[1].index("--pane") + 1] == "w9:p1"
    assert c[1][c[1].index("--") + 1:] == ["--name", "t1", "--settings", "/a b/c.json"]
    assert c[2] == ["agent", "prompt", "t1", prompt]


def test_start_in_main_repo_uses_tab(herdr_env, origin_repo):
    adapter, calls = herdr_env
    assert adapter.start_session("t2", origin_repo, "p", [], False) == {"agent": "t2", "tab": "w9:t1"}
    assert calls()[0][:2] == ["tab", "create"]


def test_trust_dialog_reported_and_cleaned(herdr_env, origin_repo, monkeypatch):
    adapter, calls = herdr_env
    monkeypatch.setenv("FAKE_HERDR_MODE", "trust")
    with pytest.raises(AdapterError, match="trust"):
        adapter.start_session("t3", origin_repo / "wt", "p", [], True)
    assert calls()[-1][:2] == ["workspace", "close"]


def test_state_gone(herdr_env, monkeypatch):
    adapter, _ = herdr_env
    assert adapter.state({"agent": "t1", "tab": "w9:t1"}) == "idle"
    monkeypatch.setenv("FAKE_HERDR_MODE", "gone")
    assert adapter.state({"agent": "t1", "tab": "w9:t1"}) == "gone"


def test_check_outside_herdr(herdr_env, monkeypatch):
    adapter, _ = herdr_env
    monkeypatch.setenv("HERDR_ENV", "0")
    ok, message = adapter.check()
    assert not ok and "Herdr" in message
```

- [ ] **Step 5: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_herdr_adapter.py -q`
Expected: FAIL, import error.

- [ ] **Step 6: Implement `herdr.py`**

Use the probe answers. If Q4 says Claude keeps running after `workspace close`, keep `stop_agent` before the close. Otherwise remove it. If Q1 shows other keys, change `pane_info`.

```python
import json
import os
import shutil
import subprocess

from .base import OPTIONAL, Adapter, AdapterError

TRUST_MARKERS = ("trust the files", "trust this folder", "do you trust")
START_TIMEOUT_MS = 60000


def run(args, timeout=60, check=True):
    try:
        r = subprocess.run(["herdr", *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise AdapterError(f"herdr {' '.join(args[:2])} timed out.")
    if check and r.returncode != 0:
        raise AdapterError(f"herdr {' '.join(args[:2])} failed: {(r.stderr or r.stdout).strip()}")
    return r


def parse(r):
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except json.JSONDecodeError:
        return {}


def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = find_key(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = find_key(value, key)
            if found is not None:
                return found
    return None


class HerdrAdapter(Adapter):
    name = "herdr"

    def capabilities(self):
        return set(OPTIONAL)

    def check(self):
        if os.environ.get("HERDR_ENV") != "1":
            return False, "This session does not run inside Herdr (HERDR_ENV is not 1). Start Claude in a Herdr pane, then start the factory again."
        if not shutil.which("herdr"):
            return False, "The `herdr` command is not installed. Install Herdr from https://herdr.dev."
        return True, "Herdr is available."

    def open_location(self, name, cwd, in_worktree):
        if in_worktree:
            result = parse(run(["worktree", "open", "--cwd", str(self.ctx.main), "--path", str(cwd), "--label", name, "--no-focus"]))["result"]
            return {"agent": name, "workspace": result["root_pane"]["workspace_id"]}, result["root_pane"]["pane_id"]
        result = parse(run(["tab", "create", "--cwd", str(cwd), "--label", name, "--no-focus"]))["result"]
        return {"agent": name, "tab": result["tab"]["tab_id"]}, result["root_pane"]["pane_id"]

    def screen(self, name):
        r = run(["agent", "read", name, "--source", "recent-unwrapped", "--lines", "60"], check=False)
        return r.stdout

    def start_session(self, name, cwd, prompt, claude_args, in_worktree):
        handle, pane = self.open_location(name, cwd, in_worktree)
        try:
            run(["agent", "start", name, "--kind", "claude", "--pane", pane, "--timeout", str(START_TIMEOUT_MS), "--", *claude_args],
                timeout=START_TIMEOUT_MS // 1000 + 30)
            run(["agent", "prompt", name, prompt], timeout=60)
        except AdapterError as e:
            screen = self.screen(name).lower()
            self.close(handle)
            if any(marker in screen for marker in TRUST_MARKERS):
                raise AdapterError(
                    f"Claude asks to trust the folder {cwd} before it starts. "
                    "Accept the trust dialog once for this folder, or put worktree_root under a trusted folder, then launch again."
                )
            raise e
        return handle

    def stop_agent(self, handle):
        run(["agent", "send-keys", handle["agent"], "ctrl+c", "ctrl+c"], check=False)

    def close(self, handle):
        if not handle:
            return
        self.stop_agent(handle)
        if handle.get("workspace"):
            run(["workspace", "close", handle["workspace"]], check=False)
        elif handle.get("tab"):
            run(["tab", "close", handle["tab"]], check=False)

    def send_prompt(self, handle, text):
        run(["agent", "prompt", handle["agent"], text])

    def focus(self, handle):
        run(["agent", "focus", handle["agent"]])

    def state(self, handle):
        if not handle:
            return "gone"
        r = run(["agent", "get", handle["agent"]], check=False)
        if r.returncode != 0:
            return "gone"
        return find_key(parse(r), "agent_status") or "unknown"

    def wait_idle(self, handle, timeout_s):
        run(["agent", "wait", handle["agent"], "--timeout", str(int(timeout_s * 1000))], timeout=timeout_s + 30)

    def notify(self, text):
        run(["notification", "show", "Software factory", "--body", text, "--sound", "request"], check=False)


ADAPTER = HerdrAdapter
```

Apply the trust decision from Step 2. If the decision is "ask the user to accept once", keep the message above. If it is "worktree_root under a trusted folder", change the message to name the trusted folder rule, and make the `create-worktree` description of `worktree_root` say it must be under a trusted folder.

- [ ] **Step 7: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add software-factory verification/software-factory/herdr-probe.md
git commit -m "adapters: herdr adapter, verified against herdr 0.9.3"
```

### Task 10: Task launch and worktree creation (`launch.py`, `session.start`)

**Files:**
- Create: `software-factory/lib/factory/launch.py`
- Modify: `software-factory/lib/factory/session.py` (add `FIRST_PROMPT`, `claude_args`, `start`)
- Modify: `software-factory/lib/factory/commands.py` (add `launch`)
- Test: `software-factory/tests/test_launch.py`

**Interfaces:**
- Consumes: `Registry`, `pipeline_check`, `config.resolve`, `state`, `events`, `adapters`, `repo.git`.
- Produces:
  - `launch.TASK_ID_RE`, `launch.slugify(text) -> str`, `launch.unique_id(ctx, base) -> str`
  - `launch.plan_launch(ctx, pipeline_id, description, inputs, task_id=None, from_backlog=None) -> dict` with keys `ok, errors, task_id, pipeline, description, worktree, base_ref, branch, branch_case, fast_forward, missing_inputs, missing_config` (`branch_case` in `new | existing | remote | detached | none`)
  - `launch.launch(ctx, pipeline_id, description, inputs, task_id=None, from_backlog=None) -> dict` (the task)
  - `launch.branch_in_use(ctx, branch) -> str|None` (task id or folder)
  - `session.FIRST_PROMPT`, `session.RESUME_PROMPT`, `session.claude_args(ctx, task, resume=False) -> list[str]`, `session.start(ctx, task, prompt, resume=False) -> dict`
  - Backlog hooks used only when `from_backlog` is set: `backlog.get(ctx, id)` and `backlog.remove(ctx, id)` (Task 20). Until Task 20, `plan_launch` raises `FactoryError("The backlog is not available.")` when `from_backlog` is set.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from conftest import commit_all, events, fake_calls, fake_config, git, task_json, write_pipeline, write_step
from factory import launch, repo
from factory.errors import FactoryError


@pytest.fixture
def lp(inited):
    write_step(inited.fdir, "work", {})
    write_pipeline(inited.fdir, {"id": "plain", "steps": ["work"], "claude": {"model": "sonnet", "effort": "medium"}})
    write_pipeline(inited.fdir, {"id": "branchy", "inputs": {"branch": {"description": "Branch"}}, "steps": ["work"]})
    return inited


def ctx(lp):
    return repo.load_ctx(cwd=lp.repo)


def push_branch(lp, name, filename):
    git("switch", "-c", name, cwd=lp.repo)
    (lp.repo / filename).write_text(name)
    commit_all(lp.repo, name)
    git("push", "-u", "origin", name, cwd=lp.repo)
    git("switch", "main", cwd=lp.repo)


def test_slug_rules(lp):
    assert launch.slugify("Fix the Login crash!") == "fix-the-login-crash"
    assert launch.slugify("ÉÉ 2") == "ee-2"
    assert launch.slugify("!!!") == "task"
    assert launch.slugify("2 bugs") == "task-2-bugs"
    assert launch.TASK_ID_RE.match(launch.slugify("x" * 80))


def test_dry_run_changes_nothing_and_reports(lp):
    rep = launch.plan_launch(ctx(lp), "plain", "Fix it", {})
    assert rep["ok"] and rep["task_id"] == "fix-it" and rep["branch_case"] == "detached"
    assert rep["worktree"] == str(lp.worktrees / "fix-it")
    assert not (lp.worktrees / "fix-it").exists()
    assert not (lp.fdir / "tasks" / "fix-it").exists()


def test_launch_detached(lp):
    task = launch.launch(ctx(lp), "plain", 'Say "hi" $HOME', {})
    wt = lp.worktrees / task["id"]
    assert git("rev-parse", "HEAD", cwd=wt) == git("rev-parse", "origin/main", cwd=lp.repo)
    assert task_json(lp.fdir, task["id"])["position"] == 1
    call = fake_calls(lp.fdir)[0]
    args = call["args"]
    assert call["in_worktree"] is True and call["cwd"] == str(wt)
    assert args[args.index("--name") + 1] == task["id"]
    assert args[args.index("--session-id") + 1] == task["session_id"]
    assert args[args.index("--settings") + 1] == str(lp.fdir / "claude-settings.json")
    assert args[args.index("--model") + 1] == "sonnet" and args[args.index("--effort") + 1] == "medium"
    assert str(lp.fdir / "tasks" / task["id"] / "artifacts") in args
    assert "Run `factory next`" in call["prompt"]
    kinds = [e["type"] for e in events(lp.fdir, task["id"])]
    assert kinds[0] == "task_created"


def test_taken_id_gets_suffix(lp):
    launch.launch(ctx(lp), "plain", "Same", {})
    assert launch.plan_launch(ctx(lp), "plain", "Same", {})["task_id"] == "same-2"


def test_new_branch(lp):
    rep = launch.plan_launch(ctx(lp), "branchy", "B", {"branch": "feat/new"})
    assert rep["branch_case"] == "new"
    task = launch.launch(ctx(lp), "branchy", "B", {"branch": "feat/new"})
    assert git("branch", "--show-current", cwd=task["worktree"]) == "feat/new"


def test_existing_local_branch_behind_is_fast_forwarded(lp):
    push_branch(lp, "feat/ff", "a.txt")
    seed = lp.work / "seed"
    git("fetch", "origin", cwd=seed)
    git("switch", "feat/ff", cwd=seed)
    (seed / "b.txt").write_text("b")
    commit_all(seed, "more")
    git("push", "origin", "feat/ff", cwd=seed)
    rep = launch.plan_launch(ctx(lp), "branchy", "F", {"branch": "feat/ff"})
    assert rep["branch_case"] == "existing" and rep["fast_forward"] is True
    task = launch.launch(ctx(lp), "branchy", "F", {"branch": "feat/ff"})
    assert (lp.worktrees / task["id"] / "b.txt").exists()


def test_remote_only_branch(lp):
    push_branch(lp, "feat/remote", "r.txt")
    git("branch", "-D", "feat/remote", cwd=lp.repo)
    assert launch.plan_launch(ctx(lp), "branchy", "R", {"branch": "feat/remote"})["branch_case"] == "remote"
    task = launch.launch(ctx(lp), "branchy", "R", {"branch": "feat/remote"})
    assert git("rev-parse", "--abbrev-ref", "feat/remote@{upstream}", cwd=task["worktree"]) == "origin/feat/remote"


def test_diverged_branch_stops(lp):
    push_branch(lp, "feat/div", "d.txt")
    git("switch", "feat/div", cwd=lp.repo)
    (lp.repo / "local.txt").write_text("l")
    commit_all(lp.repo, "local")
    git("switch", "main", cwd=lp.repo)
    seed = lp.work / "seed"
    git("fetch", "origin", cwd=seed)
    git("switch", "feat/div", cwd=seed)
    (seed / "remote.txt").write_text("r")
    commit_all(seed, "remote")
    git("push", "origin", "feat/div", cwd=seed)
    rep = launch.plan_launch(ctx(lp), "branchy", "D", {"branch": "feat/div"})
    assert not rep["ok"] and "diverged" in " ".join(rep["errors"])


def test_branch_in_other_worktree_stops(lp):
    launch.launch(ctx(lp), "branchy", "First", {"branch": "feat/used"})
    rep = launch.plan_launch(ctx(lp), "branchy", "Second", {"branch": "feat/used"})
    assert not rep["ok"] and "first" in " ".join(rep["errors"])


def test_failed_start_rolls_back_but_keeps_existing_branch(lp):
    push_branch(lp, "feat/keep", "k.txt")
    fake_config(lp.fdir, fail_start=True)
    with pytest.raises(FactoryError):
        launch.launch(ctx(lp), "branchy", "Keep", {"branch": "feat/keep"})
    with pytest.raises(FactoryError):
        launch.launch(ctx(lp), "branchy", "Gone", {"branch": "feat/created"})
    assert not (lp.worktrees / "keep").exists() and not (lp.fdir / "tasks" / "keep").exists()
    assert git("branch", "--list", "feat/keep", cwd=lp.repo)
    assert not git("branch", "--list", "feat/created", cwd=lp.repo)


def test_create_worktree_listed_late_refused(lp):
    write_pipeline(lp.fdir, {"id": "late", "steps": ["work", "create-worktree"]})
    rep = launch.plan_launch(ctx(lp), "late", "L", {})
    assert not rep["ok"] and "not as the first step" in " ".join(rep["errors"])


def test_no_worktree_pipeline_uses_task_flag(lp):
    write_step(lp.fdir, "new-step", {})
    write_pipeline(lp.fdir, {"id": "new-step-assistant", "steps": ["new-step"]})
    task = launch.launch(ctx(lp), "new-step-assistant", "Make a step", {})
    call = fake_calls(lp.fdir)[0]
    assert call["in_worktree"] is False and call["cwd"] == str(lp.repo)
    assert f"--task {task['id']}" in call["prompt"]
    assert str(lp.library) in call["args"]
    r = lp.factory("next", check=False)
    assert r.returncode == 1 and "--task <id>" in r.stderr


def test_missing_input_and_config(lp):
    rep = launch.plan_launch(ctx(lp), "branchy", "M", {})
    assert rep["missing_inputs"] == ["branch"]
    lp.factory("config", "set", "create-worktree", "worktree_root", "")
    (lp.fdir / "config.yaml").write_text("{}\n")
    rep = launch.plan_launch(ctx(lp), "plain", "M", {})
    assert rep["missing_config"][0]["key"] == "worktree_root" and not rep["ok"]


def test_cli_dry_run_json(lp):
    rep = lp.factory.json("launch", "plain", "--description", "Cli task", "--dry-run")
    assert rep["task_id"] == "cli-task"
    out = lp.factory("launch", "plain", "--description", "Cli task").stdout
    assert "cli-task" in out
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_launch.py -q`
Expected: FAIL, import error.

- [ ] **Step 3: Extend `session.py`**

```python
import uuid

from . import adapters, state
from .adapters.base import AdapterError
from .registry import NO_WORKTREE_PIPELINES

FIRST_PROMPT = (
    "You run factory task `{id}`. Run `{next}` and follow its instructions. "
    "When the step is done, run `{done}`. Repeat until `{next}` says the pipeline is finished."
)
RESUME_PROMPT = "The factory resumed this task. Run `{status}`, then continue with `{next}`."


def factory_cmd(task, sub):
    return f"factory {sub}" + ("" if task.get("worktree") else f" --task {task['id']}")


def first_prompt(task):
    return FIRST_PROMPT.format(id=task["id"], next=factory_cmd(task, "next"), done=factory_cmd(task, "done"))


def resume_prompt(task, extra=None):
    text = RESUME_PROMPT.format(status=factory_cmd(task, "status"), next=factory_cmd(task, "next"))
    return f"{text}\n\n{extra}" if extra else text


def new_session_id():
    return str(uuid.uuid4())


def claude_args(ctx, task, resume=False):
    args = ["--name", task["id"]]
    args += ["--resume", task["session_id"]] if resume else ["--session-id", task["session_id"]]
    args += ["--settings", str(ctx.fdir / "claude-settings.json")]
    args += ["--add-dir", str(state.task_dir(ctx, task["id"]) / "artifacts")]
    if task["pipeline"] in NO_WORKTREE_PIPELINES and ctx.library():
        args += ["--add-dir", str(ctx.library())]
    claude = task.get("claude") or {}
    if claude.get("model"):
        args += ["--model", str(claude["model"])]
    if claude.get("effort"):
        args += ["--effort", str(claude["effort"])]
    return args


def start(ctx, task, prompt, resume=False):
    cwd = task["worktree"] or str(ctx.main)
    return adapters.get_adapter(ctx).start_session(
        task["id"], cwd, prompt, claude_args(ctx, task, resume), bool(task.get("worktree"))
    )


def notify(ctx, text):
    adapter = adapters.get_adapter(ctx)
    if "notify" not in adapter.capabilities():
        return
    try:
        adapter.notify(text)
    except AdapterError:
        pass
```

- [ ] **Step 4: Implement `launch.py`**

```python
import re
import shutil
import unicodedata
from pathlib import Path

from . import config, events, pipeline_check, repo, session, state
from .errors import FactoryError
from .registry import CREATE_WORKTREE, NO_WORKTREE_PIPELINES, Registry

TASK_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
ID_BASE_MAX = 29


def slugify(text):
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    if not slug:
        return "task"
    if not slug[0].isalpha():
        slug = f"task-{slug}"
    return slug[:ID_BASE_MAX].rstrip("-")


def id_taken(ctx, tid):
    return (ctx.fdir / "tasks" / tid).exists() or (ctx.fdir / "tasks" / "archive" / tid).exists()


def unique_id(ctx, base):
    if not id_taken(ctx, base):
        return base
    n = 2
    while id_taken(ctx, f"{base}-{n}"):
        n += 1
    return f"{base}-{n}"


def ref_exists(ctx, ref):
    return repo.git(["rev-parse", "--verify", "--quiet", ref], ctx.main, check=False).returncode == 0


def is_ancestor(ctx, a, b):
    return repo.git(["merge-base", "--is-ancestor", a, b], ctx.main, check=False).returncode == 0


def worktree_branches(ctx):
    out = repo.git(["worktree", "list", "--porcelain"], ctx.main).stdout
    result, path = {}, None
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = line.split(" ", 1)[1]
        elif line.startswith("branch refs/heads/"):
            result[line[len("branch refs/heads/"):]] = path
    return result


def branch_in_use(ctx, branch):
    path = worktree_branches(ctx).get(branch)
    if not path:
        return None
    for task in state.list_tasks(ctx):
        if task.get("worktree") and Path(task["worktree"]).resolve() == Path(path).resolve():
            return f"task {task['id']}"
    return f"folder {path}"


def fetch(ctx, ref, report):
    r = repo.git(["fetch", "origin", ref], ctx.main, check=False)
    if r.returncode != 0:
        report["errors"].append(f"`git fetch origin {ref}` failed: {r.stderr.strip()} Check the remote, then try again.")
        return False
    return True


def remote_has_branch(ctx, branch):
    r = repo.git(["ls-remote", "--heads", "origin", branch], ctx.main, check=False)
    return r.returncode == 0 and bool(r.stdout.strip())


def plan_branch(ctx, report, branch):
    report["branch"] = branch
    on_remote = remote_has_branch(ctx, branch)
    if on_remote and not fetch(ctx, branch, report):
        return
    local, remote = f"refs/heads/{branch}", f"refs/remotes/origin/{branch}"
    user = branch_in_use(ctx, branch)
    if user:
        report["errors"].append(f"The branch `{branch}` is already checked out by {user}.")
        return
    if ref_exists(ctx, local):
        report["branch_case"] = "existing"
        if on_remote and ref_exists(ctx, remote):
            if is_ancestor(ctx, local, remote):
                report["fast_forward"] = not is_ancestor(ctx, remote, local)
            elif not is_ancestor(ctx, remote, local):
                report["errors"].append(
                    f"The local and remote branches `{branch}` have diverged. Fix it by hand, then launch again."
                )
    elif on_remote:
        report["branch_case"] = "remote"
    else:
        report["branch_case"] = "new"


def plan_launch(ctx, pipeline_id, description, inputs, task_id=None, from_backlog=None):
    report = {
        "ok": False, "errors": [], "task_id": None, "pipeline": pipeline_id, "description": description,
        "worktree": None, "base_ref": None, "branch": None, "branch_case": "none", "fast_forward": False,
        "missing_inputs": [], "missing_config": [], "summary": None,
    }
    reg = Registry.load(ctx)
    pipeline = reg.pipeline(pipeline_id)
    for problem in pipeline_check.errors(pipeline_check.check(reg, pipeline.data, ctx.columns(), pipeline.level)):
        report["errors"].append(problem.message)
    if from_backlog:
        from . import backlog
        entry = backlog.get(ctx, from_backlog)
        report["description"] = description or entry.title
        report["summary"] = entry.summary
    if not (report["description"] or "").strip():
        report["errors"].append("The description is empty.")
    report["missing_inputs"] = [k for k in pipeline.inputs if not str(inputs.get(k, "")).strip()]
    if task_id:
        if not TASK_ID_RE.match(task_id):
            report["errors"].append(f"The id `{task_id}` must match [a-z][a-z0-9_-]{{0,31}}.")
        elif id_taken(ctx, task_id):
            report["errors"].append(f"The id `{task_id}` is already used.")
        report["task_id"] = task_id
    else:
        report["task_id"] = unique_id(ctx, slugify(report["description"] or "task"))
    if pipeline_id not in NO_WORKTREE_PIPELINES:
        plan_worktree(ctx, reg, pipeline, report, inputs)
    report["ok"] = not report["errors"] and not report["missing_inputs"] and not report["missing_config"]
    return report


def plan_worktree(ctx, reg, pipeline, report, inputs):
    entries = pipeline.entries
    entry_with = entries[0].get("with", {}) if entries and entries[0].get("id") == CREATE_WORKTREE else {}
    step = reg.step(CREATE_WORKTREE)
    values, missing = config.resolve(ctx, step, entry_with)
    values = {k: v for k, v in values.items() if str(v).strip()}
    missing += [k for k in ("worktree_root",) if k not in values and k not in missing]
    report["missing_config"] = [
        {"step": CREATE_WORKTREE, "key": k, "description": step.config_spec.get(k, {}).get("description", "")}
        for k in missing
    ]
    base_ref = values.get("base_ref", "main")
    report["base_ref"] = base_ref
    if "worktree_root" in values:
        wt = Path(str(values["worktree_root"])).expanduser().resolve() / report["task_id"]
        report["worktree"] = str(wt)
        if wt.exists():
            report["errors"].append(f"The folder {wt} already exists.")
    if not fetch(ctx, base_ref, report):
        return
    if "branch" in pipeline.inputs:
        if str(inputs.get("branch", "")).strip():
            plan_branch(ctx, report, inputs["branch"].strip())
    else:
        report["branch_case"] = "detached"


def create_worktree(ctx, report):
    wt, base, branch, case = report["worktree"], report["base_ref"], report["branch"], report["branch_case"]
    Path(wt).parent.mkdir(parents=True, exist_ok=True)
    if case == "new":
        repo.git(["worktree", "add", "-b", branch, wt, f"origin/{base}"], ctx.main)
        return True
    if case == "existing":
        if report["fast_forward"]:
            repo.git(["fetch", "origin", f"{branch}:{branch}"], ctx.main)
        repo.git(["worktree", "add", wt, branch], ctx.main)
        return False
    if case == "remote":
        repo.git(["worktree", "add", "--track", "-b", branch, wt, f"origin/{branch}"], ctx.main)
        return True
    repo.git(["worktree", "add", "--detach", wt, f"origin/{base}"], ctx.main)
    return False


def new_task(ctx, reg, report, inputs):
    pipeline = reg.pipeline(report["pipeline"])
    steps = reg.expand(pipeline)
    position = 1 if steps and steps[0]["id"] == CREATE_WORKTREE else 0
    columns = ctx.columns()
    task_state = {k: v for k, v in inputs.items()}
    if report["summary"]:
        task_state["summary"] = report["summary"]
    if report["branch"]:
        task_state["branch"] = report["branch"]
    now = state.now()
    return {
        "id": report["task_id"], "description": report["description"], "pipeline": pipeline.id,
        "steps": steps, "position": position, "started": None,
        "status": "active", "status_reason": None, "status_since": now, "saved_status": None,
        "column": pipeline.start_column or columns[0],
        "worktree": report["worktree"], "base_ref": report["base_ref"],
        "session_id": session.new_session_id(), "terminal_handle": None,
        "goto_counts": {}, "approval": None, "claude": pipeline.claude,
        "state": task_state, "created_at": now, "updated_at": now,
    }


def launch(ctx, pipeline_id, description, inputs, task_id=None, from_backlog=None):
    report = plan_launch(ctx, pipeline_id, description, inputs, task_id, from_backlog)
    if not report["ok"]:
        raise FactoryError(render_report(report))
    reg = Registry.load(ctx)
    undo = []
    try:
        if report["worktree"]:
            created_branch = create_worktree(ctx, report)
            undo.append(lambda: repo.git(["worktree", "remove", "--force", report["worktree"]], ctx.main, check=False))
            if created_branch:
                undo.append(lambda: repo.git(["branch", "-D", report["branch"]], ctx.main, check=False))
        task = new_task(ctx, reg, report, inputs)
        state.create(ctx, task)
        undo.append(lambda: shutil.rmtree(state.task_dir(ctx, task["id"]), ignore_errors=True))
        handle = session.start(ctx, task, session.first_prompt(task))
        task = state.update(ctx, task["id"], lambda t: t.__setitem__("terminal_handle", handle))
    except Exception:
        for action in reversed(undo):
            action()
        raise
    events.log(ctx, task["id"], "task_created", None, pipeline=task["pipeline"], description=task["description"])
    if task["position"] == 1:
        events.log(ctx, task["id"], "step_started", CREATE_WORKTREE, run_in="factory", model=None, effort=None)
        events.log(ctx, task["id"], "step_done", CREATE_WORKTREE)
    if from_backlog:
        from . import backlog
        backlog.remove(ctx, from_backlog)
    return task


def render_report(report):
    lines = [f"Task id: {report['task_id']}", f"Pipeline: {report['pipeline']}"]
    if report["worktree"]:
        lines.append(f"Worktree: {report['worktree']}")
    if report["branch"]:
        ff = " (fast-forward)" if report["fast_forward"] else ""
        lines.append(f"Branch: {report['branch']} ({report['branch_case']}){ff}")
    elif report["branch_case"] == "detached":
        lines.append(f"Branch: none, detached HEAD on origin/{report['base_ref']}")
    for key in report["missing_inputs"]:
        lines.append(f"Missing input: {key}")
    for item in report["missing_config"]:
        lines.append(f"Missing config: {item['step']}.{item['key']} ({item['description']})")
    for error in report["errors"]:
        lines.append(f"Error: {error}")
    return "\n".join(lines)
```

The fixture `inited` keeps `worktree_root` in `config.yaml`. The test `test_missing_input_and_config` empties `config.yaml` to see the missing key.

- [ ] **Step 5: Add `launch`**

In `register`:

```python
    p = sub.add_parser("launch", parents=[common])
    p.add_argument("pipeline")
    p.add_argument("--description", default="")
    p.add_argument("--input", action="append", default=[])
    p.add_argument("--id", default=None)
    p.add_argument("--from-backlog", default=None)
    p.add_argument("--dry-run", action="store_true")
```

Handler:

```python
def parse_inputs(items):
    inputs = {}
    for item in items:
        if "=" not in item:
            raise cli.FactoryError(f"Invalid input `{item}`. Use --input <key>=<value>.")
        key, value = item.split("=", 1)
        inputs[key] = value
    return inputs


@cli.command("launch")
def launch_cmd(args):
    from . import launch
    ctx = ctx_of(args)
    inputs = parse_inputs(args.input)
    if args.dry_run:
        report = launch.plan_launch(ctx, args.pipeline, args.description, inputs, args.id, args.from_backlog)
        cli.emit(report, True) if args.json else print(launch.render_report(report))
        return 0 if report["ok"] else 1
    task = launch.launch(ctx, args.pipeline, args.description, inputs, args.id, args.from_backlog)
    cli.emit(task, True) if args.json else print(f"Task {task['id']} started." + (f" Worktree: {task['worktree']}" if task["worktree"] else ""))
```

- [ ] **Step 6: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add software-factory
git commit -m "launch: task creation, worktree cases, dry run, rollback"
```

### Task 11: Task delete (`delete.py`)

**Files:**
- Create: `software-factory/lib/factory/delete.py`
- Modify: `software-factory/lib/factory/commands.py` (add `delete`)
- Test: `software-factory/tests/test_delete.py`

**Interfaces:**
- Consumes: `state`, `events`, `adapters`, `repo.git`.
- Produces:
  - `delete.plan_delete(ctx, tid) -> dict` keys `task_id, session_id, terminal_handle, worktree, branch, uncommitted (list[str]), unpushed (list[str]), delete_branch (bool), needs_confirm (bool)`
  - `delete.delete(ctx, tid, confirm_unpushed=False) -> dict` (the plan)
  - `delete.branch_merged_or_pushed(ctx, branch, base_ref) -> bool`
  - `delete.render_plan(plan) -> str`

- [ ] **Step 1: Write the failing tests**

```python
import json

import pytest

from conftest import fake_calls, git, write_pipeline, write_step
from factory import delete, launch, repo
from factory.errors import FactoryError


@pytest.fixture
def started(inited):
    write_step(inited.fdir, "work", {})
    write_pipeline(inited.fdir, {"id": "branchy", "inputs": {"branch": {"description": "b"}}, "steps": ["work"]})
    ctx = repo.load_ctx(cwd=inited.repo)
    task = launch.launch(ctx, "branchy", "Del me", {"branch": "feat/del"})
    return inited, ctx, task


def test_dry_run_shows_changes_and_changes_nothing(started):
    inited, ctx, task = started
    wt = task["worktree"]
    (inited.worktrees / task["id"] / "new.txt").write_text("x")
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["uncommitted"] and plan["needs_confirm"]
    git("add", "-A", cwd=wt)
    git("commit", "-m", "c", cwd=wt)
    plan = delete.plan_delete(ctx, task["id"])
    assert plan["unpushed"] and not plan["delete_branch"]
    assert (inited.fdir / "tasks" / task["id"]).exists()


def test_delete_refuses_without_confirm_then_archives(started):
    inited, ctx, task = started
    (inited.worktrees / task["id"] / "new.txt").write_text("x")
    with pytest.raises(FactoryError, match="--confirm-unpushed"):
        delete.delete(ctx, task["id"])
    delete.delete(ctx, task["id"], confirm_unpushed=True)
    assert not (inited.worktrees / task["id"]).exists()
    assert (inited.fdir / "tasks" / "archive" / task["id"] / "task.json").exists()
    assert fake_calls(inited.fdir)[-1]["op"] == "close"
    assert git("branch", "--list", "feat/del", cwd=inited.repo)
    log = inited.fdir / "tasks" / "archive" / task["id"] / "events.jsonl"
    assert json.loads(log.read_text().splitlines()[-1])["type"] == "task_deleted"


def test_launch_and_delete_never_call_herdr(inited, tmp_path, monkeypatch):
    marker = tmp_path / "herdr-called"
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "herdr").write_text(f"#!/bin/sh\ntouch {marker}\nexit 1\n")
    (bindir / "herdr").chmod(0o755)
    env = {"PATH": f"{bindir}:{inited.factory.env['PATH']}"}
    write_step(inited.fdir, "work", {})
    write_pipeline(inited.fdir, {"id": "plain", "steps": ["work"]})
    tid = inited.factory.json("launch", "plain", "--description", "No herdr", env=env)["id"]
    inited.factory("delete", tid, env=env)
    assert not marker.exists()
    assert [c["op"] for c in fake_calls(inited.fdir)] == ["start_session", "close"]


def test_pushed_branch_is_deleted(started):
    inited, ctx, task = started
    git("push", "-u", "origin", "feat/del", cwd=task["worktree"])
    delete.delete(ctx, task["id"])
    assert not git("branch", "--list", "feat/del", cwd=inited.repo)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_delete.py -q`
Expected: FAIL, import error.

- [ ] **Step 3: Implement `delete.py`**

```python
import shutil
from datetime import datetime
from pathlib import Path

from . import adapters, events, repo, state
from .adapters.base import AdapterError
from .errors import FactoryError


def git_lines(args, cwd):
    r = repo.git(args, cwd, check=False)
    return [l for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []


def ref_exists(cwd, ref):
    return repo.git(["rev-parse", "--verify", "--quiet", ref], cwd, check=False).returncode == 0


def branch_merged_or_pushed(ctx, branch, base_ref):
    local = f"refs/heads/{branch}"
    if not ref_exists(ctx.main, local):
        return False
    for target in (f"refs/remotes/origin/{branch}", f"refs/remotes/origin/{base_ref}"):
        if ref_exists(ctx.main, target) and repo.git(["merge-base", "--is-ancestor", local, target], ctx.main, check=False).returncode == 0:
            return True
    return False


def plan_delete(ctx, tid):
    task = state.load(ctx, tid)
    wt = task.get("worktree")
    plan = {
        "task_id": tid, "session_id": task.get("session_id"), "terminal_handle": task.get("terminal_handle"),
        "worktree": wt, "branch": None, "uncommitted": [], "unpushed": [], "delete_branch": False, "needs_confirm": False,
    }
    if wt and Path(wt).exists():
        plan["uncommitted"] = git_lines(["status", "--porcelain"], wt)
        branch = repo.git(["symbolic-ref", "--short", "-q", "HEAD"], wt, check=False).stdout.strip() or None
        plan["branch"] = branch
        base = f"origin/{task.get('base_ref') or 'main'}"
        upstream = f"origin/{branch}" if branch and ref_exists(wt, f"refs/remotes/origin/{branch}") else base
        plan["unpushed"] = git_lines(["log", "--oneline", f"{upstream}..HEAD"], wt)
        if branch:
            plan["delete_branch"] = branch_merged_or_pushed(ctx, branch, task.get("base_ref") or "main") and not plan["unpushed"]
    plan["needs_confirm"] = bool(plan["uncommitted"] or plan["unpushed"])
    return plan


def render_plan(plan):
    lines = [f"Delete task {plan['task_id']}:", f"- Claude session {plan['session_id']} and its terminal"]
    if plan["worktree"]:
        lines.append(f"- Worktree {plan['worktree']}")
    if plan["branch"]:
        lines.append(f"- Local branch {plan['branch']}" if plan["delete_branch"] else f"- Local branch {plan['branch']} is kept: it is not pushed or merged")
    lines.append("- The task folder moves to .factory/tasks/archive/")
    if plan["uncommitted"]:
        lines += ["Uncommitted changes:"] + [f"  {l}" for l in plan["uncommitted"]]
    if plan["unpushed"]:
        lines += ["Commits not pushed to origin:"] + [f"  {l}" for l in plan["unpushed"]]
    return "\n".join(lines)


def archive_target(ctx, tid):
    target = ctx.fdir / "tasks" / "archive" / tid
    if target.exists():
        target = target.with_name(f"{tid}-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    return target


def delete(ctx, tid, confirm_unpushed=False):
    plan = plan_delete(ctx, tid)
    if plan["needs_confirm"] and not confirm_unpushed:
        raise FactoryError(render_plan(plan) + "\nRun again with --confirm-unpushed after the user approves.")
    if plan["terminal_handle"]:
        try:
            adapters.get_adapter(ctx).close(plan["terminal_handle"])
        except AdapterError:
            pass
    if plan["worktree"] and Path(plan["worktree"]).exists():
        repo.git(["worktree", "remove", "--force", plan["worktree"]], ctx.main)
    repo.git(["worktree", "prune"], ctx.main, check=False)
    if plan["branch"] and plan["delete_branch"]:
        repo.git(["branch", "-D", plan["branch"]], ctx.main, check=False)
    events.log(ctx, tid, "task_deleted", None)
    target = archive_target(ctx, tid)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(state.task_dir(ctx, tid)), str(target))
    return plan
```

- [ ] **Step 4: Add `delete`**

```python
    p = sub.add_parser("delete", parents=[common])
    p.add_argument("id")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm-unpushed", action="store_true")
```

```python
@cli.command("delete")
def delete_cmd(args):
    from . import delete
    ctx = ctx_of(args)
    if args.dry_run:
        plan = delete.plan_delete(ctx, args.id)
        cli.emit(plan, True) if args.json else print(delete.render_plan(plan))
        return
    delete.delete(ctx, args.id, args.confirm_unpushed)
    print(f"Task {args.id} deleted and archived.")
```

- [ ] **Step 5: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add software-factory
git commit -m "delete: dry run, unpushed checks, archive"
```

### Task 12: Init, link and menu (`init.py`, `menu.py`)

**Files:**
- Create: `software-factory/lib/factory/init.py`, `software-factory/lib/factory/menu.py`
- Modify: `software-factory/lib/factory/commands.py` (add `init`, `link`, `menu`)
- Modify: `software-factory/tests/conftest.py` (the `inited` fixture now runs the real `factory init`)
- Test: `software-factory/tests/test_init_menu.py`

**Interfaces:**
- Consumes: `repo`, `fsio`, `adapters`, `version.DATA_VERSION`.
- Produces:
  - `init.link_dir() -> Path` (env `FACTORY_LINK_DIR`, default `~/.local/bin`)
  - `init.ensure_link() -> dict` keys `path, target, changed, on_path`
  - `init.prerequisites(cwd) -> list[dict]` items `name, ok, message`
  - `init.init(cwd, library, create_library=False) -> dict` keys `created, kept, library, library_git, link, checks`
  - `init.SETTINGS = {"permissions": {"allow": ["Bash(factory:*)", "Bash(factory *)"]}}`
  - `menu.ACTIONS: list[tuple[group, key, label, capability|None]]`; `menu.build(ctx) -> dict` with `groups: [{"title", "actions": [{"n", "key", "label"}]}]`

- [ ] **Step 1: Write the failing tests**

```python
import json
import os

import yaml

from conftest import fake_config, git
from factory import init, menu, repo


def test_init_creates_files_and_exclude(factory, origin_repo, library_path, work):
    gitignore_before = (origin_repo / ".gitignore").exists()
    out = factory.json("init", "--library", library_path, "--create-library")
    f = origin_repo / ".factory"
    data = yaml.safe_load((f / "factory.yaml").read_text())
    assert data["version"] == 1 and data["library"] == str(library_path) and data["terminal"] == "fake"
    for name in ("config.yaml", "backlog.md", "claude-settings.json", "steps", "pipelines", "tasks/archive"):
        assert (f / name).exists()
    assert json.loads((f / "claude-settings.json").read_text()) == init.SETTINGS
    exclude = (origin_repo / ".git" / "info" / "exclude").read_text().splitlines()
    assert ".factory/" in exclude and ".factory.backup-*/" in exclude
    assert (origin_repo / ".gitignore").exists() == gitignore_before
    assert yaml.safe_load((library_path / "factory.yaml").read_text())["version"] == 1
    assert out["library_git"] is True
    assert os.path.realpath(work / "bin" / "factory").endswith("bin/factory")


def test_init_never_overwrites(factory, origin_repo, library_path):
    factory("init", "--library", library_path, "--create-library")
    (origin_repo / ".factory" / "backlog.md").write_text("# Backlog\n\n## Keep me\n")
    factory("init", "--library", library_path)
    assert "Keep me" in (origin_repo / ".factory" / "backlog.md").read_text()


def test_init_needs_existing_library_or_flag(factory, library_path):
    r = factory("init", "--library", library_path, check=False)
    assert r.returncode == 1 and "--create-library" in r.stderr


def test_init_reports_failed_prerequisite(factory, origin_repo, library_path):
    git("remote", "remove", "origin", cwd=origin_repo)
    r = factory("init", "--library", library_path, "--create-library", check=False)
    assert r.returncode == 1 and "origin" in (r.stdout + r.stderr)


def test_link_fixes_wrong_target(factory, work):
    link = work / "bin" / "factory"
    link.unlink()
    link.symlink_to(work / "elsewhere")
    out = factory.json("link")
    assert out["changed"] is True and os.path.realpath(link).endswith("bin/factory")


def test_menu_before_and_after_init(factory, origin_repo, library_path):
    before = factory.json("menu")
    assert [a["key"] for g in before["groups"] for a in g["actions"]] == ["init"]
    factory("init", "--library", library_path, "--create-library")
    keys = [a["key"] for g in factory.json("menu")["groups"] for a in g["actions"]]
    assert "init" not in keys and keys[0] == "launch" and keys[-1] == "exit"
    fake_config(origin_repo / ".factory", capabilities=["state"])
    keys = [a["key"] for g in factory.json("menu")["groups"] for a in g["actions"]]
    assert "focus" not in keys and "send-prompt" not in keys
    numbers = [a["n"] for g in factory.json("menu")["groups"] for a in g["actions"]]
    assert numbers == list(range(1, len(numbers) + 1))
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_init_menu.py -q`
Expected: FAIL, `invalid choice: 'init'`.

- [ ] **Step 3: Implement `init.py`**

```python
import os
import shutil
from pathlib import Path

from . import adapters, fsio, repo
from .errors import FactoryError
from .version import DATA_VERSION

SETTINGS = {"permissions": {"allow": ["Bash(factory:*)", "Bash(factory *)"]}}
EXCLUDES = [".factory/", ".factory.backup-*/"]
BACKLOG_HEADER = "# Backlog\n"


def link_dir():
    return Path(os.environ.get("FACTORY_LINK_DIR", "~/.local/bin")).expanduser()


def cli_path():
    return (repo.PLUGIN_ROOT / "bin" / "factory").resolve()


def ensure_link():
    d = link_dir()
    link = d / "factory"
    target = cli_path()
    changed = False
    if link.is_symlink():
        if Path(os.path.realpath(link)) != target:
            link.unlink()
            changed = True
    elif link.exists():
        raise FactoryError(f"{link} exists and is not a link. Move it away, then run again.")
    else:
        changed = True
    if changed:
        d.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
    on_path = str(d) in os.environ.get("PATH", "").split(os.pathsep)
    return {"path": str(link), "target": str(target), "changed": changed, "on_path": on_path}


def prerequisites(cwd):
    checks = []
    try:
        ctx = repo.load_ctx(cwd)
        ok, message = adapters.get_adapter(ctx).check()
        checks.append({"name": "terminal", "ok": ok, "message": message})
        has_origin = repo.git(["remote", "get-url", "origin"], ctx.main, check=False).returncode == 0
        checks.append({"name": "git", "ok": has_origin, "message": "Git repository with an origin remote." if has_origin else "This repository has no `origin` remote. Add it with `git remote add origin <url>`."})
    except FactoryError as e:
        checks.append({"name": "git", "ok": False, "message": f"{e} Run the factory in a git repository."})
    has_uv = shutil.which("uv") is not None
    checks.append({"name": "uv", "ok": has_uv, "message": "uv is installed." if has_uv else "uv is missing. Install it with `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`."})
    return checks


def write_new(path, writer, report):
    if path.exists():
        report["kept"].append(str(path))
        return
    writer(path)
    report["created"].append(str(path))


def create_library_folder(lib):
    for d in ("steps", "pipelines"):
        (lib / d).mkdir(parents=True, exist_ok=True)
    if not (lib / "factory.yaml").exists():
        fsio.write_yaml(lib / "factory.yaml", {"version": DATA_VERSION})


def add_excludes(ctx):
    rel = repo.git(["rev-parse", "--git-path", "info/exclude"], ctx.main).stdout.strip()
    path = (ctx.main / rel).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text().splitlines() if path.exists() else []
    missing = [e for e in EXCLUDES if e not in lines]
    if missing:
        fsio.atomic_write_text(path, "\n".join(lines + missing) + "\n")


def init(cwd, library, create_library=False):
    checks = prerequisites(cwd)
    failed = [c for c in checks if not c["ok"]]
    if failed:
        raise FactoryError("Init stopped. Fix these first:\n" + "\n".join(f"- {c['name']}: {c['message']}" for c in failed))
    ctx = repo.load_ctx(cwd)
    lib = Path(library).expanduser().resolve()
    if not lib.exists() and not create_library:
        raise FactoryError(f"The library folder {lib} does not exist. Run again with --create-library to create it.")
    if create_library or not (lib / "factory.yaml").exists():
        create_library_folder(lib)
    report = {"created": [], "kept": [], "library": str(lib), "checks": checks}
    report["library_git"] = repo.git(["rev-parse", "--show-toplevel"], lib, check=False).returncode == 0
    f = ctx.fdir
    for d in ("steps", "pipelines", "tasks/archive"):
        (f / d).mkdir(parents=True, exist_ok=True)
    yaml_data = {
        "version": DATA_VERSION, "library": str(lib), "terminal": adapters.terminal_name(ctx),
        "columns": list(repo.DEFAULT_COLUMNS), "poll_minutes": 5, "ticket_url": "",
    }
    write_new(f / "factory.yaml", lambda p: fsio.write_yaml(p, yaml_data), report)
    write_new(f / "config.yaml", lambda p: fsio.write_yaml(p, {}), report)
    write_new(f / "backlog.md", lambda p: fsio.atomic_write_text(p, BACKLOG_HEADER), report)
    write_new(f / "claude-settings.json", lambda p: fsio.write_json(p, SETTINGS), report)
    add_excludes(ctx)
    report["link"] = ensure_link()
    return report
```

- [ ] **Step 4: Implement `menu.py`**

```python
from . import adapters

ACTIONS = [
    ("Tasks", "launch", "Launch a new pipeline", None),
    ("Tasks", "show-tasks", "Show tasks", None),
    ("Tasks", "check-waiting", "Check waiting tasks", None),
    ("Tasks", "focus", "Focus a task", "focus"),
    ("Tasks", "send-prompt", "Send a prompt to a task", "send_prompt"),
    ("Tasks", "resume", "Resume a task", None),
    ("Tasks", "delete", "Delete a task", None),
    ("Tasks", "clean", "Clean finished tasks", None),
    ("Pipelines and steps", "pipeline-edit", "Create or edit a pipeline", None),
    ("Pipelines and steps", "new-step", "Create a new step", None),
    ("Pipelines and steps", "catalog", "Browse the catalog", None),
    ("Backlog", "backlog-add", "Add a backlog entry", None),
    ("Backlog", "backlog-remove", "Remove a backlog entry", None),
    ("Factory", "dashboard", "Open dashboard", None),
    ("Factory", "exit", "Exit", None),
]


def build(ctx):
    if not ctx.initialized():
        return {"initialized": False, "groups": [{"title": "Factory", "actions": [{"n": 1, "key": "init", "label": "Init the factory"}]}]}
    caps = adapters.get_adapter(ctx).capabilities()
    groups, n = [], 0
    for group, key, label, needs in ACTIONS:
        if needs and needs not in caps:
            continue
        if not groups or groups[-1]["title"] != group:
            groups.append({"title": group, "actions": []})
        n += 1
        groups[-1]["actions"].append({"n": n, "key": key, "label": label})
    return {"initialized": True, "groups": groups}


def render(model):
    lines = []
    for group in model["groups"]:
        lines.append(f"## {group['title']}")
        lines += [f"{a['n']}. {a['label']}" for a in group["actions"]]
        lines.append("")
    return "\n".join(lines).rstrip()
```

- [ ] **Step 5: Add `init`, `link`, `menu`**

```python
    p = sub.add_parser("init", parents=[common])
    p.add_argument("--library", required=True)
    p.add_argument("--create-library", action="store_true")
    sub.add_parser("link", parents=[common])
    sub.add_parser("menu", parents=[common])
```

```python
@cli.command("init")
def init_cmd(args):
    from . import init
    report = init.init(".", args.library, args.create_library)
    if args.json:
        cli.emit(report, True)
        return
    for c in report["checks"]:
        print(f"OK: {c['name']}: {c['message']}")
    print(f"Created: {len(report['created'])} files. Kept: {len(report['kept'])} files.")
    if not report["library_git"]:
        print("Warning: the library is not in a git repository. Library commits are disabled.")


@cli.command("link")
def link_cmd(args):
    from . import init
    info = init.ensure_link()
    cli.emit(info, True) if args.json else print(f"{info['path']} -> {info['target']}" + (" (updated)" if info["changed"] else ""))
    if not info["on_path"] and not args.json:
        print(f"Warning: {init.link_dir()} is not in PATH.")


@cli.command("menu")
def menu_cmd(args):
    from . import menu, repo
    model = menu.build(repo.load_ctx(task_opt=args.task))
    cli.emit(model, True) if args.json else print(menu.render(model))
```

- [ ] **Step 6: Switch the `inited` fixture to the real `init`**

In `conftest.py`, replace the `inited` fixture body and delete `bootstrap_factory_dir`:

```python
@pytest.fixture
def inited(factory, origin_repo, library_path, work):
    factory("init", "--library", library_path, "--create-library")
    factory("config", "set", "create-worktree", "worktree_root", work / "worktrees")
    return Inited(origin_repo, library_path, factory, work)
```

- [ ] **Step 7: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add software-factory
git commit -m "init: prerequisites, files, exclude entries, link, menu"
```

### Task 13: Orchestrator skill and milestone 1 check

**Files:**
- Create: `software-factory/skills/software-factory/SKILL.md`
- Test: `software-factory/tests/test_skill.py`

**Interfaces:**
- Consumes: every command from Tasks 3 to 12, and the commands added in later milestones (the skill lists them all now. Later tasks only add the commands).

- [ ] **Step 1: Write `SKILL.md`**

````markdown
---
name: software-factory
description: Software factory orchestrator. Starts each task in its own worktree, Herdr tab and Claude session, runs pipelines of reusable steps, and manages tasks, pipelines, steps, the catalog, the backlog and the dashboard. Use when the user starts the software factory or asks to launch or manage factory tasks.
---

# Software factory orchestrator

You are the orchestrator. You run in the main repository. You never do task work yourself. Each task runs in its own session.

`FACTORY` below means the absolute path `<this skill's base directory>/../../bin/factory`. Resolve it once from the base directory shown when this skill loads.

## Start

Run these checks in order. Stop at the first failure and say why.

1. Run `FACTORY link --json`. If `on_path` is false, tell the user to add the link folder to PATH, and stop.
2. From here, call `factory` by name. Run `factory terminal check`. If it fails, show the message and stop.
3. Run `factory menu --json`. If `initialized` is false, show the menu (only Init) and wait.
4. Run `factory version check --json`:
   - `state` is `same`: continue.
   - `state` is `older`: follow the built-in step `migrate` (Migrate below). Show the menu only after it.
   - `state` is `newer`: tell the user to update the factory plugin, and stop.
5. Run `factory tasks --json`. If some tasks are `paused`, list them and ask: resume all, some, or none. Run `factory resume <id>` for each chosen task.

## Menu

- Build the menu from `factory menu --json`. Show it as a numbered text list, with one `##` heading per group, numbers from the JSON.
- Do not use the AskUserQuestion tool for the menu. It allows only 4 options.
- The user answers with a number. Run the action, then show the menu again.

## Actions

Before any command that changes something, show what it will do and wait for the user to confirm, when the action says so.

- **Init the factory** (`init`):
  1. Ask for the library folder path. Explain: generic steps and pipelines live there, and it can be shared by many repositories.
  2. Run `FACTORY init --library <path> --json`. If the folder does not exist, ask to create it and add `--create-library`. Show each check. If the library is not in git, say that library commits are disabled.
  3. Offer the starter pack: `factory catalog install quick-task --local|--generic --with-steps --dry-run --json`, show it, then install after approval. For a generic install, offer the library commit (Library commits below).
  4. Backlog import: ask if the user wants to import entries. They paste a list or give a file path. Run `factory backlog import --dry-run --json` with the text on stdin or `--file <path>`, show the parsed titles, then run it without `--dry-run` after approval.
- **Launch a new pipeline** (`launch`): follow the built-in step `create-task`. Pipelines: `factory pipeline list --json`. Backlog: `factory backlog list --json`. The menu returns at once. Do not wait for the task.
- **Show tasks** (`show-tasks`): run `factory tasks` and show the output.
- **Check waiting tasks** (`check-waiting`): run `factory poll`. Then list the `waiting_external` tasks whose step has no done check (`factory tasks --json`, field `wait_has_check` false). Ask if one of them is done. Run `factory external-done <id>` for each one the user confirms.
- **Focus a task** (`focus`): list tasks with a live session (`factory tasks --json`, `session_state` not `gone`), ask which one, run `factory terminal focus <id>`.
- **Send a prompt to a task** (`send-prompt`): list tasks with a live session, ask which one and the text.
  - If `session_state` is `working`, ask: wait until idle, or send now. Add `--wait` to wait.
  - If the session is `gone` or the task is `paused`, offer to resume it first.
  - Run `factory terminal send-prompt <id> "<text>"`.
- **Resume a task** (`resume`): list `paused` tasks and tasks not `finished` whose `session_state` is `gone`. If the adapter has no `state` capability, warn that a second session could start if the first one still runs. Run `factory resume <id>`.
- **Delete a task** (`delete`): list the tasks, ask which one, then follow the built-in step `delete-task`.
- **Clean finished tasks** (`clean`): run `factory clean --json`. Show each finished task with merged or not. Merged tasks are selected by default. Ask the user to confirm the selection. For each selected task, follow `delete-task`.
- **Create or edit a pipeline** (`pipeline-edit`): ask for an id to edit, or nothing for a new one. Run `factory pipeline edit [<id>]`. Tell the user the editor is open in the browser.
- **Create a new step** (`new-step`): run `factory launch new-step-assistant --description "<goal in a few words>"`. Tell the user the assistant runs in a new tab.
- **Browse the catalog** (`catalog`): run `factory catalog list --json`. Show each item with its kind, category, description, status and missing requires. To install, ask generic or local, run `factory catalog install <id> --generic|--local --dry-run --json`, show the files, missing steps and any difference, then install after approval with `--with-steps` when the user accepts the missing steps, and `--replace` when the user approved a difference. For a generic install, offer the library commit.
- **Add a backlog entry** (`backlog-add`): follow the built-in step `backlog-add`.
- **Remove a backlog entry** (`backlog-remove`): follow the built-in step `backlog-remove`.
- **Open dashboard** (`dashboard`): run `factory dashboard`. Show the URL it prints.
- **Exit** (`exit`): list the tasks that are not `paused` or `finished`. Ask whether to pause all of them. If yes, ask: wait until each session is idle, or stop now. Run `factory pause --all` (add `--wait` to wait). Then run `factory server stop` and stop the menu.

## Migrate

Follow the built-in step `migrate`: `factory migrate --dry-run --json`, then `factory migrate --json`, then the library commit offer.

## Library commits

After a write to the library (generic step, generic pipeline, catalog install to the library, migration):

1. Show the changed files and the message `Factory library: <action> <kind> <id>`, for example `Factory library: add step create-merge-request`.
2. Commit only after approval: `factory library commit "<message>" <paths...>`.
3. Never push.
````

- [ ] **Step 2: Write the test**

```python
import re

from conftest import SF


def test_skill_frontmatter_and_menu_rule():
    text = (SF / "skills" / "software-factory" / "SKILL.md").read_text()
    assert text.startswith("---\nname: software-factory\n")
    assert "Do not use the AskUserQuestion tool for the menu" in text
    assert "FACTORY link --json" in text.split("factory terminal check")[0]
```

The test `test_every_skill_command_exists` is added in Task 25, when all commands exist.

- [ ] **Step 3: Run the milestone 1 tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass. Fix any failure before the commit.

- [ ] **Step 4: Commit milestone 1**

```bash
git add software-factory
git commit -m "milestone 1: core, orchestrator skill"
```

---

# Milestone 2: Task life

### Task 14: Blocked status, board columns and task list (`board.py`)

**Files:**
- Create: `software-factory/lib/factory/board.py`
- Modify: `software-factory/lib/factory/engine.py` (`block`, `unblock`, columns in `on_start`)
- Modify: `software-factory/lib/factory/session.py` (`live_state`)
- Modify: `software-factory/lib/factory/commands.py` (add `block`, `unblock`, `tasks`)
- Test: `software-factory/tests/test_board.py`

**Interfaces:**
- Consumes: `state`, `events`, `session.notify`, `adapters`.
- Produces:
  - `engine.block(ctx, tid, reason) -> str`, `engine.unblock(ctx, tid) -> str`
  - `session.live_state(ctx, task) -> str` (`gone` without handle, `unknown` without the `state` capability or on adapter error, else the adapter state)
  - `board.PRIORITY = {"blocked": 0, "awaiting_approval": 1}`
  - `board.task_row(ctx, task, reg=None) -> dict` keys `id, description, pipeline, step, status, status_reason, status_since, column, session_state, worktree, branch, ticket, mr_url, artifacts (list[str]), approval (dict|None), wait_has_check (bool|None)`
  - `board.task_rows(ctx) -> list[dict]` sorted: blocked, then awaiting_approval, then the rest by `created_at`
  - `board.render_rows(rows) -> str`

- [ ] **Step 1: Write the failing tests**

```python
from conftest import events, fake_calls, fake_config, make_task, task_from_pipeline, task_json, write_pipeline, write_step
from factory import board, repo


def test_block_unblock_and_order(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="a")
    make_task(ctx, tid="b")
    inited.factory("block", "Which DB?", "--task", "b")
    t = task_json(inited.fdir, "b")
    assert t["status"] == "blocked" and t["status_reason"] == "Which DB?"
    assert fake_calls(inited.fdir)[-1]["op"] == "notify"
    rows = inited.factory.json("tasks")
    assert [r["id"] for r in rows] == ["b", "a"]
    assert "Which DB?" in inited.factory("tasks").stdout
    inited.factory("unblock", "--task", "b")
    assert task_json(inited.fdir, "b")["status"] == "active"
    assert [e["type"] for e in events(inited.fdir, "b")] == ["task_blocked", "task_unblocked"]


def test_session_state_column(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="a", terminal_handle={"agent": "a"})
    make_task(ctx, tid="g")
    rows = {r["id"]: r for r in inited.factory.json("tasks")}
    assert rows["a"]["session_state"] == "idle" and rows["g"]["session_state"] == "gone"
    fake_config(inited.fdir, capabilities=["notify"])
    rows = {r["id"]: r for r in inited.factory.json("tasks")}
    assert rows["a"]["session_state"] == "unknown"


def test_columns_follow_steps(inited):
    write_step(inited.fdir, "plan", {"column": "Plan"})
    write_step(inited.fdir, "code", {"column": "Plan"})
    write_step(inited.fdir, "nocol", {})
    write_pipeline(inited.fdir, {"id": "cols", "start_column": "Specification", "steps": ["plan", {"id": "code", "column": "Implementation"}, "nocol"]})
    task_from_pipeline(inited, "cols", column="Specification")
    run = lambda *a: inited.factory(*a, "--task", "t1")
    run("next")
    assert task_json(inited.fdir, "t1")["column"] == "Plan"
    run("done"); run("next")
    assert task_json(inited.fdir, "t1")["column"] == "Implementation"
    run("done"); run("next")
    assert task_json(inited.fdir, "t1")["column"] == "Implementation"
    changes = [(e["from"], e["to"]) for e in events(inited.fdir, "t1") if e["type"] == "column_changed"]
    assert changes == [("Specification", "Plan"), ("Plan", "Implementation")]


def test_launch_uses_start_column(inited):
    from factory import launch
    write_step(inited.fdir, "w", {})
    write_pipeline(inited.fdir, {"id": "sc", "start_column": "Plan", "steps": ["w"]})
    task = launch.launch(repo.load_ctx(cwd=inited.repo), "sc", "Start col", {})
    assert task["column"] == "Plan"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_board.py -q`
Expected: FAIL, `invalid choice: 'block'`.

- [ ] **Step 3: Add to `engine.py`**

Replace `on_start`:

```python
def on_start(ctx, task, entry, step):
    pending = []
    column = entry.get("column") or step.column
    if column and column != task["column"]:
        pending.append(("column_changed", {"from": task["column"], "to": column}))
        task["column"] = column
    return pending
```

Add:

```python
def block(ctx, tid, reason):
    task = state.update(ctx, tid, lambda t: state.set_status(t, "blocked", reason))
    events.log(ctx, tid, "task_blocked", state.step_path_str(task), reason=reason)
    session.notify(ctx, f"Task {tid} is blocked: {reason}")
    return f"Task {tid} is blocked. Ask the user, then run `{cmd(task, 'unblock')}` when the user has answered."


def unblock(ctx, tid):
    if state.load(ctx, tid)["status"] != "blocked":
        raise FactoryError(f"Task {tid} is not blocked.")
    task = state.update(ctx, tid, lambda t: state.set_status(t, "active"))
    events.log(ctx, tid, "task_unblocked", state.step_path_str(task))
    return f"Task {tid} is active again."
```

- [ ] **Step 4: Add `live_state` to `session.py`**

```python
def live_state(ctx, task):
    handle = task.get("terminal_handle")
    if not handle:
        return "gone"
    adapter = adapters.get_adapter(ctx)
    if "state" not in adapter.capabilities():
        return "unknown"
    try:
        return adapter.state(handle)
    except AdapterError:
        return "unknown"
```

- [ ] **Step 5: Implement `board.py`**

```python
from . import session, state
from .errors import FactoryError
from .registry import Registry

PRIORITY = {"blocked": 0, "awaiting_approval": 1}


def current_step(reg, task):
    entry = state.current_entry(task)
    if entry is None:
        return None
    try:
        return reg.step(entry["id"])
    except FactoryError:
        return None


def approval_info(ctx, task):
    approval = task.get("approval")
    if not approval or task["status"] != "awaiting_approval":
        return None
    info = {"target": approval.get("target", "worktree"), "artifact_key": approval.get("artifact_key"), "artifact": None}
    key = info["artifact_key"]
    if info["target"] == "artifact" and key:
        info["artifact"] = task["state"].get(key)
    return info


def task_row(ctx, task, reg=None):
    reg = reg or Registry.load(ctx)
    step = current_step(reg, task)
    artifacts = state.task_dir(ctx, task["id"]) / "artifacts"
    return {
        "id": task["id"],
        "description": task["description"],
        "pipeline": task["pipeline"],
        "step": state.step_path_str(task),
        "status": task["status"],
        "status_reason": task.get("status_reason"),
        "status_since": task.get("status_since"),
        "column": task.get("column"),
        "session_state": session.live_state(ctx, task),
        "worktree": task.get("worktree"),
        "branch": task["state"].get("branch"),
        "ticket": task["state"].get("ticket"),
        "mr_url": task["state"].get("mr_url"),
        "artifacts": sorted(p.name for p in artifacts.iterdir()) if artifacts.exists() else [],
        "approval": approval_info(ctx, task),
        "wait_has_check": bool(step.done_check) if step and task["status"] == "waiting_external" else None,
    }


def task_rows(ctx):
    reg = Registry.load(ctx)
    tasks = sorted(state.list_tasks(ctx), key=lambda t: (PRIORITY.get(t["status"], 2), t["created_at"]))
    return [task_row(ctx, t, reg) for t in tasks]


def render_rows(rows):
    if not rows:
        return "No task."
    lines = []
    for r in rows:
        reason = f" ({r['status_reason']})" if r["status_reason"] else ""
        lines.append(f"{r['id']}: {r['description']}")
        lines.append(f"    {r['pipeline']} > {r['step']}")
        lines.append(f"    status: {r['status']}{reason}. session: {r['session_state']}")
    return "\n".join(lines)
```

- [ ] **Step 6: Add the commands**

```python
    p = sub.add_parser("block", parents=[common]); p.add_argument("reason")
    sub.add_parser("unblock", parents=[common])
    sub.add_parser("tasks", parents=[common])
```

```python
@cli.command("block")
def block_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.block(ctx, tid, args.reason))


@cli.command("unblock")
def unblock_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.unblock(ctx, tid))


@cli.command("tasks")
def tasks_cmd(args):
    from . import board
    rows = board.task_rows(ctx_of(args))
    cli.emit(rows, True) if args.json else print(board.render_rows(rows))
```

- [ ] **Step 7: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add software-factory
git commit -m "board: blocked status, columns, task list"
```

### Task 15: Sessions: pause, resume, deliver, focus, send prompt

**Files:**
- Modify: `software-factory/lib/factory/session.py`
- Modify: `software-factory/lib/factory/commands.py` (add `pause`, `resume`, `terminal focus`, `terminal send-prompt`)
- Test: `software-factory/tests/test_session.py`

**Interfaces:**
- Consumes: `state`, `events`, `adapters`, `session.start`, `session.resume_prompt`.
- Produces:
  - `session.pause(ctx, tid, wait=False, timeout_s=3600) -> None`
  - `session.pause_all(ctx, wait=False) -> list[str]`
  - `session.resume(ctx, tid, extra=None) -> dict` (the task)
  - `session.deliver(ctx, tid, text) -> str` (`"sent"` or `"resumed"`)
  - `session.send_prompt(ctx, tid, text, wait=False) -> None`
  - `session.focus(ctx, tid) -> None`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from conftest import events, fake_calls, fake_config, make_task, task_json
from factory import repo, session
from factory.errors import FactoryError


@pytest.fixture
def live(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="t1", terminal_handle={"agent": "t1"}, status="awaiting_approval", status_reason="check")
    return inited, ctx


def test_pause_saves_status_and_closes(live):
    inited, ctx = live
    inited.factory("pause", "t1")
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "paused" and t["terminal_handle"] is None
    assert t["saved_status"] == {"status": "awaiting_approval", "reason": "check"}
    assert fake_calls(inited.fdir)[-1] == {"op": "close", "handle": {"agent": "t1"}}


def test_pause_wait_uses_wait_idle(live):
    inited, ctx = live
    inited.factory("pause", "t1", "--wait")
    ops = [c["op"] for c in fake_calls(inited.fdir)]
    assert ops == ["wait_idle", "close"]


def test_resume_restores_status_same_session(live):
    inited, ctx = live
    inited.factory("pause", "t1")
    inited.factory("resume", "t1")
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "awaiting_approval" and t["terminal_handle"] == {"agent": "t1", "fake": True}
    call = fake_calls(inited.fdir)[-1]
    assert call["op"] == "start_session"
    assert call["args"][call["args"].index("--resume") + 1] == t["session_id"]
    assert "--session-id" not in call["args"]
    assert "The factory resumed this task" in call["prompt"]
    assert [e["type"] for e in events(inited.fdir, "t1")] == ["task_paused", "task_resumed"]


def test_resume_refused_when_session_runs(live):
    inited, ctx = live
    fake_config(inited.fdir, state="working")
    with pytest.raises(FactoryError, match="still running"):
        session.resume(ctx, "t1")


def test_deliver_to_gone_session_sends_one_prompt(live):
    inited, ctx = live
    fake_config(inited.fdir, state="gone")
    assert session.deliver(ctx, "t1", "The user approved.") == "resumed"
    calls = fake_calls(inited.fdir)
    assert [c["op"] for c in calls] == ["start_session"]
    assert calls[0]["prompt"].endswith("The user approved.")


def test_send_prompt_and_focus(live):
    inited, ctx = live
    inited.factory("terminal", "send-prompt", "t1", "Hello there")
    inited.factory("terminal", "focus", "t1")
    calls = fake_calls(inited.fdir)
    assert calls[-2] == {"op": "send_prompt", "handle": {"agent": "t1"}, "text": "Hello there"}
    assert calls[-1]["op"] == "focus"
    assert events(inited.fdir, "t1")[-1] == {**events(inited.fdir, "t1")[-1], "type": "prompt_sent", "text": "Hello there"}
    fake_config(inited.fdir, capabilities=["state"])
    r = inited.factory("terminal", "focus", "t1", check=False)
    assert r.returncode == 1 and "does not support focus" in r.stderr


def test_pause_all(live):
    inited, ctx = live
    make_task(ctx, tid="t2", terminal_handle={"agent": "t2"})
    make_task(ctx, tid="t3", status="finished")
    inited.factory("pause", "--all")
    assert [task_json(inited.fdir, t)["status"] for t in ("t1", "t2", "t3")] == ["paused", "paused", "finished"]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_session.py -q`
Expected: FAIL, `invalid choice: 'pause'`.

- [ ] **Step 3: Add to `session.py`**

Add `from . import events` and `from .errors import FactoryError` to the imports.

```python
PAUSE_WAIT_SECONDS = 3600


def adapter_of(ctx):
    return adapters.get_adapter(ctx)


def pause(ctx, tid, wait=False, timeout_s=PAUSE_WAIT_SECONDS):
    task = state.load(ctx, tid)
    if task["status"] in ("paused", "finished"):
        raise FactoryError(f"Task {tid} is already {task['status']}.")
    adapter = adapter_of(ctx)
    handle = task.get("terminal_handle")
    if handle:
        if wait and "wait_idle" in adapter.capabilities():
            adapter.wait_idle(handle, timeout_s)
        try:
            adapter.close(handle)
        except AdapterError:
            pass

    def change(t):
        t["saved_status"] = {"status": t["status"], "reason": t.get("status_reason")}
        state.set_status(t, "paused")
        t["terminal_handle"] = None

    task = state.update(ctx, tid, change)
    events.log(ctx, tid, "task_paused", state.step_path_str(task))


def pause_all(ctx, wait=False):
    ids = [t["id"] for t in state.list_tasks(ctx) if t["status"] not in ("paused", "finished")]
    for tid in ids:
        pause(ctx, tid, wait)
    return ids


def resume(ctx, tid, extra=None):
    task = state.load(ctx, tid)
    if task["status"] == "finished":
        raise FactoryError(f"Task {tid} is finished.")
    if task["status"] != "paused":
        live = live_state(ctx, task)
        if live not in ("gone", "unknown"):
            raise FactoryError(f"The session of task {tid} is still running ({live}).")
    handle = start(ctx, task, resume_prompt(task, extra), resume=True)

    def change(t):
        t["terminal_handle"] = handle
        if t["status"] == "paused":
            saved = t.get("saved_status") or {"status": "active", "reason": None}
            state.set_status(t, saved["status"], saved.get("reason"))
            t["saved_status"] = None

    task = state.update(ctx, tid, change)
    events.log(ctx, tid, "task_resumed", state.step_path_str(task))
    return task


def deliver(ctx, tid, text):
    task = state.load(ctx, tid)
    if task["status"] == "paused" or live_state(ctx, task) == "gone":
        resume(ctx, tid, text)
        return "resumed"
    adapter_of(ctx).send_prompt(task["terminal_handle"], text)
    return "sent"


def live_handle(ctx, tid):
    task = state.load(ctx, tid)
    if not task.get("terminal_handle"):
        raise FactoryError(f"Task {tid} has no live session. Resume it first.")
    return task, task["terminal_handle"]


def send_prompt(ctx, tid, text, wait=False):
    task, handle = live_handle(ctx, tid)
    adapter = adapter_of(ctx)
    if wait and "wait_idle" in adapter.capabilities():
        adapter.wait_idle(handle, PAUSE_WAIT_SECONDS)
    adapter.send_prompt(handle, text)
    events.log(ctx, tid, "prompt_sent", state.step_path_str(task), text=text)


def focus(ctx, tid):
    _, handle = live_handle(ctx, tid)
    adapter_of(ctx).focus(handle)
```

- [ ] **Step 4: Add the commands**

```python
    p = sub.add_parser("pause", parents=[common])
    p.add_argument("id", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--wait", action="store_true")
    p = sub.add_parser("resume", parents=[common]); p.add_argument("id")
```

Inside the existing `terminal` group (Task 6), add:

```python
    f = ts.add_parser("focus", parents=[common]); f.add_argument("id")
    sp = ts.add_parser("send-prompt", parents=[common]); sp.add_argument("id"); sp.add_argument("text"); sp.add_argument("--wait", action="store_true")
```

```python
@cli.command("pause")
def pause_cmd(args):
    from . import session
    ctx = ctx_of(args)
    if args.all:
        ids = session.pause_all(ctx, args.wait)
        print("Paused: " + (", ".join(ids) if ids else "none"))
        return
    if not args.id:
        raise cli.FactoryError("Give a task id, or --all.")
    session.pause(ctx, args.id, args.wait)
    print(f"Task {args.id} paused.")


@cli.command("resume")
def resume_cmd(args):
    from . import session
    session.resume(ctx_of(args), args.id)
    print(f"Task {args.id} resumed.")


@cli.command("terminal focus")
def focus_cmd(args):
    from . import session
    session.focus(ctx_of(args), args.id)


@cli.command("terminal send-prompt")
def send_prompt_cmd(args):
    from . import session
    session.send_prompt(ctx_of(args), args.id, args.text, args.wait)
    print("Prompt sent.")
```

- [ ] **Step 5: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add software-factory
git commit -m "session: pause, resume, deliver, focus, send prompt"
```

### Task 16: Approval

**Files:**
- Modify: `software-factory/lib/factory/engine.py` (approval in `on_start`, `approve`, `request_changes`, `approval_check`, `open_ide`)
- Modify: `software-factory/lib/factory/commands.py` (add `approve`, `request-changes`, `approval check`, `open-ide`)
- Test: `software-factory/tests/test_approval.py`

**Interfaces:**
- Consumes: `session.deliver`, `config.resolve`, `config.get_value`.
- Produces:
  - `engine.APPROVAL_STEP = "user-validation"`
  - `engine.approve(ctx, tid, send=False) -> str`
  - `engine.request_changes(ctx, tid, text, send=False) -> str`
  - `engine.approval_check(ctx, tid) -> bool`
  - `engine.open_ide(ctx, tid) -> list[str]` (the argv started)
  - `task["approval"] = {"position", "approved", "target", "artifact_key"}`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from conftest import events, fake_calls, task_from_pipeline, task_json, write_pipeline, write_step
from factory import engine, repo
from factory.errors import FactoryError


@pytest.fixture
def uv(inited):
    write_step(inited.fdir, "spec", {"writes": ["spec"]})
    write_pipeline(inited.fdir, {"id": "uvp", "steps": ["spec", {"id": "user-validation", "with": {"target": "artifact", "artifact_key": "spec"}}]})
    task_from_pipeline(inited, "uvp", terminal_handle={"agent": "t1"}, state={"spec": "/tmp/spec.md"})
    run = lambda *a, check=True: inited.factory(*a, "--task", "t1", check=check)
    run("next"); run("done"); run("next")
    return inited, run


def test_awaiting_approval_then_approve(uv):
    inited, run = uv
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "awaiting_approval"
    assert t["approval"]["target"] == "artifact" and t["approval"]["artifact_key"] == "spec"
    rows = {r["id"]: r for r in inited.factory.json("tasks")}
    assert rows["t1"]["approval"]["artifact"] == "/tmp/spec.md"
    assert run("done", check=False).returncode == 1
    run("approve", "--send")
    assert fake_calls(inited.fdir)[-1]["text"].startswith("The user approved. Run `factory done`")
    run("done")
    assert task_json(inited.fdir, "t1")["status"] == "finished"
    kinds = [e["type"] for e in events(inited.fdir, "t1")]
    assert "approval_requested" in kinds and "approved" in kinds


def test_request_changes(uv):
    inited, run = uv
    run("request-changes", "Add a test plan", "--send")
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "active"
    assert "Add a test plan" in fake_calls(inited.fdir)[-1]["text"]
    run("next")
    assert task_json(inited.fdir, "t1")["status"] == "awaiting_approval"
    assert [e["type"] for e in events(inited.fdir, "t1")].count("approval_requested") == 2


def test_approve_refused_when_not_waiting(inited):
    from conftest import make_task
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx)
    with pytest.raises(FactoryError, match="approval"):
        engine.approve(ctx, "t1")


def test_open_ide_needs_command(uv, monkeypatch):
    inited, run = uv
    r = run("open-ide", check=False)
    assert r.returncode == 1 and "ide_command" in r.stderr
    started = []
    monkeypatch.setattr(engine.subprocess, "Popen", lambda argv: started.append(argv))
    inited.factory("config", "set", "user-validation", "ide_command", "code {path}")
    argv = engine.open_ide(repo.load_ctx(cwd=inited.repo), "t1")
    assert argv == ["code", str(inited.repo)]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_approval.py -q`
Expected: FAIL.

- [ ] **Step 3: Add to `engine.py`**

Add `import shlex` to the imports. Extend `on_start` (keep the column part):

```python
APPROVAL_STEP = "user-validation"


def on_start(ctx, task, entry, step):
    pending = []
    column = entry.get("column") or step.column
    if column and column != task["column"]:
        pending.append(("column_changed", {"from": task["column"], "to": column}))
        task["column"] = column
    if step.id == APPROVAL_STEP:
        values, _ = config.resolve(ctx, step, entry.get("with"))
        target = values.get("target") or "worktree"
        task["approval"] = {"position": task["position"], "approved": False, "target": target, "artifact_key": values.get("artifact_key") or None}
        state.set_status(task, "awaiting_approval")
        pending.append(("approval_requested", {"target": target}))
    return pending
```

Add:

```python
def require_awaiting(task):
    if task["status"] != "awaiting_approval" or not task.get("approval"):
        raise FactoryError(f"Task {task['id']} is not waiting for an approval.")


def approve(ctx, tid, send=False):
    require_awaiting(state.load(ctx, tid))

    def change(t):
        t["approval"]["approved"] = True
        state.set_status(t, "active")

    task = state.update(ctx, tid, change)
    events.log(ctx, tid, "approved", state.step_path_str(task))
    if send:
        session.deliver(ctx, tid, f"The user approved. Run `{cmd(task, 'done')}`.")
    return f"Approved. Run `{cmd(task, 'done')}`."


def request_changes(ctx, tid, text, send=False):
    require_awaiting(state.load(ctx, tid))

    def change(t):
        t["approval"] = None
        t["started"] = None
        state.set_status(t, "active")

    task = state.update(ctx, tid, change)
    events.log(ctx, tid, "changes_requested", state.step_path_str(task), text=text)
    if send:
        session.deliver(ctx, tid, f"The user requested changes: {text}\nMake the changes, then run `{cmd(task, 'next')}`.")
    return f"Changes requested. Make them, then run `{cmd(task, 'next')}`."


def approval_check(ctx, tid):
    task = state.load(ctx, tid)
    approval = task.get("approval")
    return bool(approval and approval.get("position") == task["position"] and approval.get("approved"))


def open_ide(ctx, tid):
    command = config.get_value(ctx, APPROVAL_STEP, "ide_command")
    if not command:
        raise FactoryError(
            "The IDE command is not set. Ask the user, then run "
            "`factory config set user-validation ide_command '<command with {path}>'`, for example `code {path}`."
        )
    path = str(task_cwd(ctx, state.load(ctx, tid)))
    argv = [part.replace("{path}", path) for part in shlex.split(command)]
    subprocess.Popen(argv)
    return argv
```

- [ ] **Step 4: Add the commands**

```python
    p = sub.add_parser("approve", parents=[common]); p.add_argument("--send", action="store_true")
    p = sub.add_parser("request-changes", parents=[common]); p.add_argument("text"); p.add_argument("--send", action="store_true")
    p = sub.add_parser("approval")
    aps = p.add_subparsers(dest="action", required=True)
    aps.add_parser("check", parents=[common])
    sub.add_parser("open-ide", parents=[common])
```

```python
@cli.command("approve")
def approve_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.approve(ctx, tid, args.send))


@cli.command("request-changes")
def request_changes_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.request_changes(ctx, tid, args.text, args.send))


@cli.command("approval check")
def approval_check_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    ok = engine.approval_check(ctx, tid)
    print("Approved." if ok else "Not approved yet.")
    return 0 if ok else 1


@cli.command("open-ide")
def open_ide_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print("Opened: " + " ".join(engine.open_ide(ctx, tid)))
```

- [ ] **Step 5: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add software-factory
git commit -m "approval: user-validation, approve, request changes, open IDE"
```

### Task 17: External waiting: wait, poll, external-done

**Files:**
- Modify: `software-factory/lib/factory/engine.py`
- Modify: `software-factory/lib/factory/commands.py` (add `wait`, `poll`, `external-done`)
- Test: `software-factory/tests/test_waiting.py`

**Interfaces:**
- Produces:
  - `engine.wait(ctx, tid) -> str`
  - `engine.end_wait(ctx, tid, how) -> None` (`how` in `check | manual`)
  - `engine.poll(ctx) -> list[dict]` items `id, ended (bool), output (str|None), error (str|None)`
  - `engine.external_done(ctx, tid) -> None`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from conftest import events, fake_calls, task_from_pipeline, task_json, write_pipeline, write_step


@pytest.fixture
def waits(inited):
    flag = inited.work / "approved.flag"
    write_step(inited.fdir, "wait-review", {"wait_external": True, "done_when": "The MR is approved.", "done_check": f"test -f {flag}"})
    write_step(inited.fdir, "wait-qa", {"wait_external": True, "done_when": "QA is done."})
    write_step(inited.fdir, "after", {})
    write_pipeline(inited.fdir, {"id": "w", "steps": ["wait-review", "wait-qa", "after"]})
    task_from_pipeline(inited, "w", terminal_handle={"agent": "t1"})
    return inited, flag


def run(inited, *a, check=True):
    return inited.factory(*a, "--task", "t1", check=check)


def test_wait_then_poll_ends_on_check(waits):
    inited, flag = waits
    run(inited, "next")
    run(inited, "wait")
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "waiting_external" and t["status_reason"] == "The MR is approved."
    assert inited.factory.json("poll")[0]["ended"] is False
    flag.write_text("ok")
    assert inited.factory.json("poll")[0]["ended"] is True
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "active" and t["position"] == 2
    texts = [c.get("text", "") for c in fake_calls(inited.fdir)]
    assert any(x.startswith("The external event happened: The MR is approved.") for x in texts)
    assert any(c["op"] == "notify" for c in fake_calls(inited.fdir))
    assert [e for e in events(inited.fdir, "t1") if e["type"] == "external_event"][0]["how"] == "check"


def test_paused_task_not_polled(waits):
    inited, flag = waits
    run(inited, "next"); run(inited, "wait")
    inited.factory("pause", "t1")
    flag.write_text("ok")
    assert inited.factory.json("poll") == []
    inited.factory("resume", "t1")
    assert task_json(inited.fdir, "t1")["status"] == "waiting_external"


def test_external_done_manual(waits):
    inited, flag = waits
    flag.write_text("ok")
    run(inited, "next"); run(inited, "done"); run(inited, "next"); run(inited, "wait")
    r = inited.factory("external-done", "t1")
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "active" and t["position"] == 3
    assert [e for e in events(inited.fdir, "t1") if e["type"] == "external_event"][-1]["how"] == "manual"


def test_external_done_refused_with_check(waits):
    inited, flag = waits
    run(inited, "next"); run(inited, "wait")
    r = inited.factory("external-done", "t1", check=False)
    assert r.returncode == 1 and "done check" in r.stderr


def test_wait_refused_on_normal_step(inited):
    write_step(inited.fdir, "plain", {})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["plain"]})
    task_from_pipeline(inited, "p")
    run(inited, "next")
    assert run(inited, "wait", check=False).returncode == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_waiting.py -q`
Expected: FAIL.

- [ ] **Step 3: Add to `engine.py`**

```python
def wait(ctx, tid):
    task = state.load(ctx, tid)
    require_running(task)
    entry, step = load_step(ctx, task)
    if not step.wait_external:
        raise FactoryError(f"The step `{step.id}` does not wait for an external event.")
    reason = step.done_when or "An external event."
    task = state.update(ctx, tid, lambda t: state.set_status(t, "waiting_external", reason))
    events.log(ctx, tid, "waiting_started", state.step_path_str(task), reason=reason)
    return "The task now waits for the external event. Stop here. The factory sends you a message when it happens."


def end_wait(ctx, tid, how):
    task = state.load(ctx, tid)
    entry, step = load_step(ctx, task)
    events.log(ctx, tid, "external_event", state.step_path_str(task), how=how)
    advance(ctx, tid, "step_done")
    task = state.load(ctx, tid)
    session.notify(ctx, f"Task {tid}: {step.done_when or 'the external event happened'}")
    session.deliver(ctx, tid, f"The external event happened: {step.done_when} Run `{cmd(task, 'next')}`.")


def poll(ctx):
    results = []
    for task in state.list_tasks(ctx):
        if task["status"] != "waiting_external":
            continue
        entry, step = load_step(ctx, task)
        if not step.done_check:
            continue
        values, _ = config.resolve(ctx, step, entry.get("with"))
        ok, output = run_check(ctx, task, step.done_check, POLL_CHECK_TIMEOUT, values)
        row = {"id": task["id"], "ended": ok, "output": None if ok else output[-500:], "error": None}
        if ok:
            try:
                end_wait(ctx, task["id"], "check")
            except FactoryError as e:
                row["error"] = str(e)
        results.append(row)
    return results


def external_done(ctx, tid):
    task = state.load(ctx, tid)
    if task["status"] != "waiting_external":
        raise FactoryError(f"Task {tid} is not waiting for an external event.")
    entry, step = load_step(ctx, task)
    if step.done_check:
        raise FactoryError("This step has a done check. The wait ends when the check passes. Run `factory poll`.")
    end_wait(ctx, tid, "manual")
```

- [ ] **Step 4: Add the commands**

```python
    sub.add_parser("wait", parents=[common])
    sub.add_parser("poll", parents=[common])
    p = sub.add_parser("external-done", parents=[common]); p.add_argument("id")
```

```python
@cli.command("wait")
def wait_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.wait(ctx, tid))


@cli.command("poll")
def poll_cmd(args):
    from . import engine
    results = engine.poll(ctx_of(args))
    if args.json:
        cli.emit(results, True)
        return
    if not results:
        print("No task waits on a done check.")
    for r in results:
        print(f"{r['id']}: " + ("the wait ended." if r["ended"] else "still waiting."))


@cli.command("external-done")
def external_done_cmd(args):
    from . import engine
    engine.external_done(ctx_of(args), args.id)
    print(f"Task {args.id}: the external event is marked done.")
```

- [ ] **Step 5: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add software-factory
git commit -m "waiting: wait, poll, external-done"
```

### Task 18: Go back to an earlier step (`goto`)

**Files:**
- Modify: `software-factory/lib/factory/engine.py`
- Modify: `software-factory/lib/factory/commands.py` (add `goto`)
- Test: `software-factory/tests/test_goto.py`

**Interfaces:**
- Produces: `engine.MAX_JUMPS = 3`; `engine.find_target(task, target) -> int`; `engine.goto(ctx, tid, target, reason) -> str`

- [ ] **Step 1: Write the failing tests**

```python
from conftest import events, task_from_pipeline, task_json, write_pipeline, write_step


def setup(inited):
    for sid in ("a", "rebase", "commit", "b"):
        write_step(inited.fdir, sid, {"writes": [f"{sid}_out"]})
    write_step(inited.fdir, "rebase-and-commit", {"type": "composite", "steps": ["rebase", "commit"]}, body="")
    write_pipeline(inited.fdir, {"id": "g", "steps": ["a", "rebase-and-commit", "b"]})
    task_from_pipeline(inited, "g")
    run = lambda *x, check=True: inited.factory(*x, "--task", "t1", check=check)
    for _ in range(3):
        run("next"); run("done")
    run("state", "set", "a_out", "kept")
    return run


def test_goto_back_into_composite(inited):
    run = setup(inited)
    run("goto", "rebase-and-commit > commit", "--reason", "fix commit")
    t = task_json(inited.fdir, "t1")
    assert t["position"] == 3 and t["state"]["a_out"] == "kept"
    goto = [e for e in events(inited.fdir, "t1") if e["type"] == "step_goto"][0]
    assert (goto["from"], goto["to"], goto["reason"]) == ("b", "rebase-and-commit > commit", "fix commit")


def test_goto_forward_refused(inited):
    run = setup(inited)
    run("goto", "a", "--reason", "x")
    r = run("goto", "b", "--reason", "x", check=False)
    assert r.returncode == 1 and "skip" in r.stderr


def test_third_jump_blocks(inited):
    run = setup(inited)
    for i in range(3):
        run("goto", "a", "--reason", f"try {i}")
        for _ in range(3):
            if task_json(inited.fdir, "t1")["status"] == "blocked":
                break
            run("next"); run("done")
    t = task_json(inited.fdir, "t1")
    assert t["status"] == "blocked" and t["status_reason"] == "loop on a"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_goto.py -q`
Expected: FAIL.

- [ ] **Step 3: Add to `engine.py`**

```python
MAX_JUMPS = 3


def find_target(task, target):
    parts = [p.strip() for p in target.split(">") if p.strip()]

    def matches(i):
        path = task["steps"][i]["path"]
        return path == parts or (len(parts) == 1 and path[-1] == parts[0])

    if parts and parts[-1] == CREATE_WORKTREE:
        raise FactoryError("`create-worktree` cannot run again.")
    earlier = [i for i in range(task["position"]) if matches(i)]
    if earlier:
        return earlier[-1]
    if any(matches(i) for i in range(task["position"], len(task["steps"]))):
        raise FactoryError("This step is not before the current step. To move forward, skip steps with `factory skip`, after user approval.")
    raise FactoryError(f"This task has no step `{target}`.")


def goto(ctx, tid, target, reason):
    task = state.load(ctx, tid)
    require_running(task)
    index = find_target(task, target)
    from_path, to_path = state.step_path_str(task), state.step_path_str(task, index)

    def change(t):
        key = str(index)
        t["goto_counts"][key] = t["goto_counts"].get(key, 0) + 1
        t["position"] = index
        t["started"] = None
        t["approval"] = None
        if t["goto_counts"][key] >= MAX_JUMPS:
            state.set_status(t, "blocked", f"loop on {to_path}")
        else:
            state.set_status(t, "active")

    task = state.update(ctx, tid, change)
    events.log(ctx, tid, "step_goto", to_path, **{"from": from_path, "to": to_path, "reason": reason})
    if task["status"] == "blocked":
        events.log(ctx, tid, "task_blocked", to_path, reason=task["status_reason"])
        session.notify(ctx, f"Task {tid} is blocked: {task['status_reason']}")
        return f"The task is blocked: {task['status_reason']}. Ask the user what to do."
    return f"Moved back to {to_path}. Run `{cmd(task, 'next')}`."
```

Import `CREATE_WORKTREE` from `.registry`.

- [ ] **Step 4: Add `goto`**

```python
    p = sub.add_parser("goto", parents=[common]); p.add_argument("step_path"); p.add_argument("--reason", required=True)
```

```python
@cli.command("goto")
def goto_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.goto(ctx, tid, args.step_path, args.reason))
```

- [ ] **Step 5: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add software-factory
git commit -m "engine: goto with loop protection"
```

### Task 19: Clean finished tasks

**Files:**
- Modify: `software-factory/lib/factory/delete.py` (add `clean_report`)
- Modify: `software-factory/lib/factory/commands.py` (add `clean`)
- Test: `software-factory/tests/test_clean.py`

**Interfaces:**
- Produces: `delete.clean_report(ctx) -> list[dict]` items `id, description, branch, merged (bool), reason, selected (bool)`

- [ ] **Step 1: Write the failing tests**

```python
from conftest import commit_all, git, write_pipeline, write_step
from factory import launch, repo, state


def finish(ctx, tid):
    state.update(ctx, tid, lambda t: state.set_status(t, "finished"))


def test_clean_detects_merge_cases(inited):
    write_step(inited.fdir, "w", {})
    write_pipeline(inited.fdir, {"id": "b", "inputs": {"branch": {"description": "b"}}, "steps": ["w"]})
    write_pipeline(inited.fdir, {"id": "nb", "steps": ["w"]})
    ctx = repo.load_ctx(cwd=inited.repo)
    merged = launch.launch(ctx, "b", "Merged", {"branch": "feat/merged"})
    gone = launch.launch(ctx, "b", "Gone remote", {"branch": "feat/gone"})
    open_ = launch.launch(ctx, "b", "Open", {"branch": "feat/open"})
    nobranch = launch.launch(ctx, "nb", "No branch", {})
    for task, name in ((merged, "m.txt"), (gone, "g.txt"), (open_, "o.txt")):
        (inited.worktrees / task["id"] / name).write_text("x")
        commit_all(inited.worktrees / task["id"], name)
    git("push", "origin", "feat/merged:main", cwd=inited.repo)
    git("push", "-u", "origin", "feat/gone", cwd=inited.worktrees / gone["id"])
    git("push", "origin", "--delete", "feat/gone", cwd=inited.repo)
    for t in (merged, gone, open_, nobranch):
        finish(ctx, t["id"])
    rows = {r["id"]: r for r in inited.factory.json("clean")}
    assert rows[merged["id"]]["merged"] and rows[merged["id"]]["selected"]
    assert rows[gone["id"]]["merged"]
    assert not rows[open_["id"]]["merged"] and not rows[open_["id"]]["selected"]
    assert rows[nobranch["id"]]["merged"]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_clean.py -q`
Expected: FAIL.

- [ ] **Step 3: Add to `delete.py`**

```python
def current_branch(task):
    branch = task["state"].get("branch")
    wt = task.get("worktree")
    if not branch and wt and Path(wt).exists():
        branch = repo.git(["symbolic-ref", "--short", "-q", "HEAD"], wt, check=False).stdout.strip() or None
    return branch


def merge_state(ctx, branch, base_ref):
    if not branch:
        return True, "no branch"
    local = f"refs/heads/{branch}"
    base = f"refs/remotes/origin/{base_ref}"
    if ref_exists(ctx.main, local) and ref_exists(ctx.main, base):
        if repo.git(["merge-base", "--is-ancestor", local, base], ctx.main, check=False).returncode == 0:
            return True, f"merged into origin/{base_ref}"
    has_upstream = repo.git(["config", "--get", f"branch.{branch}.remote"], ctx.main, check=False).returncode == 0
    if has_upstream and not ref_exists(ctx.main, f"refs/remotes/origin/{branch}"):
        return True, "pushed, and its remote branch was deleted"
    return False, "not merged"


def clean_report(ctx):
    repo.git(["fetch", "origin", "--prune"], ctx.main, check=False)
    rows = []
    for task in state.list_tasks(ctx):
        if task["status"] != "finished":
            continue
        branch = current_branch(task)
        merged, reason = merge_state(ctx, branch, task.get("base_ref") or "main")
        rows.append({"id": task["id"], "description": task["description"], "branch": branch,
                     "merged": merged, "reason": reason, "selected": merged})
    return rows
```

- [ ] **Step 4: Add `clean`**

```python
    sub.add_parser("clean", parents=[common])
```

```python
@cli.command("clean")
def clean_cmd(args):
    from . import delete
    rows = delete.clean_report(ctx_of(args))
    if args.json:
        cli.emit(rows, True)
        return
    if not rows:
        print("No finished task.")
    for r in rows:
        mark = "[x]" if r["selected"] else "[ ]"
        print(f"{mark} {r['id']}: {r['description']} ({r['reason']})")
```

- [ ] **Step 5: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add software-factory
git commit -m "clean: merged detection for finished tasks"
```

### Task 20: Backlog

**Files:**
- Create: `software-factory/lib/factory/backlog.py`
- Modify: `software-factory/lib/factory/commands.py` (add `backlog list|add|remove|move|import`)
- Test: `software-factory/tests/test_backlog.py`

**Interfaces:**
- Produces:
  - `backlog.Entry(id, title, summary, pipeline)` with `to_dict()`
  - `backlog.parse(text) -> (str, list[Entry])`, `backlog.render(preamble, entries) -> str`
  - `backlog.list_entries(ctx) -> list[Entry]` (writes missing ids)
  - `backlog.get(ctx, id) -> Entry`, `backlog.add(ctx, title, summary="", pipeline=None) -> Entry`, `backlog.remove(ctx, id) -> Entry`, `backlog.move(ctx, id, to) -> list[Entry]` (`to` is 1-based)
  - `backlog.parse_import(text) -> list[str]`, `backlog.import_titles(ctx, titles) -> list[Entry]`

- [ ] **Step 1: Write the failing tests**

```python
import subprocess
import sys

import pytest

from conftest import SF, task_json, write_pipeline, write_step
from factory import backlog, config, launch, repo
from factory.errors import FactoryError


def ctx_of(inited):
    return repo.load_ctx(cwd=inited.repo)


def test_add_list_remove_move(inited):
    inited.factory("backlog", "add", "First", "--summary", "One")
    inited.factory("backlog", "add", "Second", "--pipeline", "quick-task")
    inited.factory("backlog", "add", "Third")
    ids = [e["id"] for e in inited.factory.json("backlog", "list")]
    assert ids == ["b1", "b2", "b3"]
    inited.factory("backlog", "move", "b3", "--to", "1")
    assert [e["title"] for e in inited.factory.json("backlog", "list")] == ["Third", "First", "Second"]
    inited.factory("backlog", "remove", "b1")
    assert [e["id"] for e in inited.factory.json("backlog", "list")] == ["b3", "b2"]
    text = (inited.fdir / "backlog.md").read_text()
    assert "## Second\n<!-- id: b2 -->\npipeline: quick-task\n" in text


def test_hand_written_file_is_kept(inited):
    (inited.fdir / "backlog.md").write_text(
        "# Backlog\n\nNotes before entries.\n\n## Hand entry\nSome text\n\nmore text\n\n## With id\n<!-- id: b7 -->\nX\n"
    )
    entries = inited.factory.json("backlog", "list")
    assert entries[0]["id"] == "b8" and entries[0]["summary"] == "Some text\n\nmore text"
    assert entries[1]["id"] == "b7"
    text = (inited.fdir / "backlog.md").read_text()
    assert text.startswith("# Backlog\n\nNotes before entries.\n")
    assert "<!-- id: b8 -->" in text


def test_launch_from_backlog(inited):
    write_step(inited.fdir, "w", {"reads": ["summary"]})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["w"]})
    e = backlog.add(ctx_of(inited), "Dark mode", "Settings screen only.", "p")
    task = launch.launch(ctx_of(inited), "p", "", {}, from_backlog=e.id)
    t = task_json(inited.fdir, task["id"])
    assert t["description"] == "Dark mode" and t["state"]["summary"] == "Settings screen only."
    assert backlog.list_entries(ctx_of(inited)) == []


def test_failed_launch_keeps_entry(inited):
    from conftest import fake_config
    write_step(inited.fdir, "w", {})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["w"]})
    e = backlog.add(ctx_of(inited), "Keep", "", None)
    fake_config(inited.fdir, fail_start=True)
    with pytest.raises(FactoryError):
        launch.launch(ctx_of(inited), "p", "", {}, from_backlog=e.id)
    assert [x.id for x in backlog.list_entries(ctx_of(inited))] == [e.id]


def test_import(inited):
    out = inited.factory.json("backlog", "import", "--dry-run", input="- One\n2. Two\n\n* Three\n")
    assert out == ["One", "Two", "Three"]
    inited.factory("backlog", "import", input="- One\n2. Two\n")
    assert [e["title"] for e in inited.factory.json("backlog", "list")] == ["One", "Two"]


WRITER = """
import sys
sys.path.insert(0, sys.argv[1])
from factory import backlog, config, repo
ctx = repo.load_ctx(cwd=sys.argv[2])
for i in range(50):
    config.set_value(ctx, "s" + sys.argv[3], "k" + str(i), i)
    backlog.add(ctx, sys.argv[3] + str(i))
"""


def test_two_processes_lose_no_write(inited):
    procs = [subprocess.Popen([sys.executable, "-c", WRITER, str(SF / "lib"), str(inited.repo), tag]) for tag in "ab"]
    assert all(p.wait(timeout=300) == 0 for p in procs)
    ctx = ctx_of(inited)
    assert len(backlog.list_entries(ctx)) == 100
    assert len({e.id for e in backlog.list_entries(ctx)}) == 100
    for tag in "ab":
        assert all(config.get_value(ctx, "s" + tag, f"k{i}") == i for i in range(50))
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_backlog.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement `backlog.py`**

```python
import re
from dataclasses import asdict, dataclass

from . import fsio
from .errors import FactoryError

HEADING_RE = re.compile(r"^## (.+?)\s*$")
ID_LINE_RE = re.compile(r"^<!-- id: ([A-Za-z0-9_-]+) -->\s*$")
PIPELINE_LINE_RE = re.compile(r"^pipeline: ([a-z][a-z0-9_-]*)\s*$")
GENERATED_ID_RE = re.compile(r"^b(\d+)$")
LIST_MARK_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
DEFAULT_PREAMBLE = "# Backlog"


@dataclass
class Entry:
    id: str | None
    title: str
    summary: str
    pipeline: str | None

    def to_dict(self):
        return asdict(self)


def path(ctx):
    return ctx.fdir / "backlog.md"


def finish_entry(entry, lines):
    rest = []
    for line in lines:
        if entry.id is None and ID_LINE_RE.match(line):
            entry.id = ID_LINE_RE.match(line).group(1)
        elif entry.pipeline is None and PIPELINE_LINE_RE.match(line):
            entry.pipeline = PIPELINE_LINE_RE.match(line).group(1)
        else:
            rest.append(line)
    entry.summary = "\n".join(rest).strip()


def parse(text):
    preamble, entries, current, lines = [], [], None, []
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            if current:
                finish_entry(current, lines)
            current, lines = Entry(None, m.group(1), "", None), []
            entries.append(current)
        elif current:
            lines.append(line)
        else:
            preamble.append(line)
    if current:
        finish_entry(current, lines)
    return "\n".join(preamble).strip() or DEFAULT_PREAMBLE, entries


def render(preamble, entries):
    parts = [preamble.strip()]
    for e in entries:
        block = [f"## {e.title}", f"<!-- id: {e.id} -->"]
        if e.pipeline:
            block.append(f"pipeline: {e.pipeline}")
        if e.summary:
            block.append(e.summary)
        parts.append("\n".join(block))
    return "\n\n".join(parts) + "\n"


def assign_ids(entries):
    numbers = [int(m.group(1)) for e in entries if e.id and (m := GENERATED_ID_RE.match(e.id))]
    n = max(numbers, default=0)
    for e in entries:
        if not e.id:
            n += 1
            e.id = f"b{n}"


def change(ctx, fn):
    box = {}

    def update(text):
        preamble, entries = parse(text)
        assign_ids(entries)
        box["value"] = fn(entries)
        return render(preamble, entries)

    fsio.update_text(path(ctx), update)
    return box["value"]


def find(entries, entry_id):
    for i, e in enumerate(entries):
        if e.id == entry_id:
            return i
    raise FactoryError(f"No backlog entry with id `{entry_id}`.")


def list_entries(ctx):
    return change(ctx, lambda entries: list(entries))


def get(ctx, entry_id):
    entries = list_entries(ctx)
    return entries[find(entries, entry_id)]


def clean_title(title):
    title = " ".join(title.split())
    if not title:
        raise FactoryError("The title is empty.")
    return title


def add(ctx, title, summary="", pipeline=None):
    title = clean_title(title)

    def fn(entries):
        entry = Entry(None, title, (summary or "").strip(), pipeline or None)
        entries.append(entry)
        assign_ids(entries)
        return entry

    return change(ctx, fn)


def remove(ctx, entry_id):
    return change(ctx, lambda entries: entries.pop(find(entries, entry_id)))


def move(ctx, entry_id, to):
    def fn(entries):
        entry = entries.pop(find(entries, entry_id))
        index = max(0, min(int(to) - 1, len(entries)))
        entries.insert(index, entry)
        return list(entries)

    return change(ctx, fn)


def parse_import(text):
    titles = []
    for line in text.splitlines():
        title = " ".join(LIST_MARK_RE.sub("", line).split())
        if title:
            titles.append(title)
    return titles


def import_titles(ctx, titles):
    return [add(ctx, t) for t in titles]
```

In `launch.plan_launch`, remove the temporary error for `from_backlog` if you added one. The code from Task 10 already calls `backlog.get`.

- [ ] **Step 4: Add the commands**

```python
    p = sub.add_parser("backlog")
    bs = p.add_subparsers(dest="action", required=True)
    bs.add_parser("list", parents=[common])
    a = bs.add_parser("add", parents=[common]); a.add_argument("title"); a.add_argument("--summary", default=""); a.add_argument("--pipeline", default=None)
    r = bs.add_parser("remove", parents=[common]); r.add_argument("id")
    m = bs.add_parser("move", parents=[common]); m.add_argument("id"); m.add_argument("--to", type=int, required=True)
    i = bs.add_parser("import", parents=[common]); i.add_argument("--file", default=None); i.add_argument("--dry-run", action="store_true")
```

```python
def print_entries(entries, as_json):
    if as_json:
        cli.emit([e.to_dict() for e in entries], True)
        return
    if not entries:
        print("The backlog is empty.")
    for n, e in enumerate(entries, 1):
        pipeline = f" [{e.pipeline}]" if e.pipeline else ""
        print(f"{n}. {e.title}{pipeline} (id {e.id})")


@cli.command("backlog list")
def backlog_list(args):
    from . import backlog
    print_entries(backlog.list_entries(ctx_of(args)), args.json)


@cli.command("backlog add")
def backlog_add(args):
    from . import backlog
    e = backlog.add(ctx_of(args), args.title, args.summary, args.pipeline)
    cli.emit(e.to_dict(), True) if args.json else print(f"Added {e.title} (id {e.id}).")


@cli.command("backlog remove")
def backlog_remove(args):
    from . import backlog
    e = backlog.remove(ctx_of(args), args.id)
    print(f"Removed {e.title}.")


@cli.command("backlog move")
def backlog_move(args):
    from . import backlog
    print_entries(backlog.move(ctx_of(args), args.id, args.to), args.json)


@cli.command("backlog import")
def backlog_import(args):
    import sys
    from pathlib import Path
    from . import backlog
    text = Path(args.file).read_text() if args.file else sys.stdin.read()
    titles = backlog.parse_import(text)
    if args.dry_run:
        cli.emit(titles, True) if args.json else print("\n".join(titles))
        return
    print_entries(backlog.import_titles(ctx_of(args), titles), args.json)
```

- [ ] **Step 5: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add software-factory
git commit -m "backlog: entries, ids, priority, import, launch from backlog"
```

### Task 21: Event log coverage and milestone 2 check

**Files:**
- Test: `software-factory/tests/test_event_log.py`

- [ ] **Step 1: Write the test**

```python
import json

from conftest import fake_config, write_pipeline, write_step
from factory import delete, engine, launch, repo, session

EXPECTED = {
    "task_created", "step_started", "step_done", "step_skipped", "done_check_failed", "config_asked",
    "task_deleted", "task_blocked", "task_unblocked", "task_paused", "task_resumed", "step_goto",
    "task_finished", "prompt_sent", "column_changed", "approval_requested", "approved",
    "changes_requested", "waiting_started", "external_event",
}


def test_all_event_types(inited):
    flag = inited.work / "ok.flag"
    write_step(inited.fdir, "cfg", {"config": {"k": {"description": "K"}}, "column": "Plan"})
    write_step(inited.fdir, "chk", {"done_check": f"test -f {flag}"})
    write_step(inited.fdir, "opt", {})
    write_step(inited.fdir, "ext", {"wait_external": True, "done_when": "Done outside."})
    write_pipeline(inited.fdir, {"id": "all", "steps": ["cfg", "chk", "opt", "user-validation", "ext"]})
    ctx = repo.load_ctx(cwd=inited.repo)
    tid = launch.launch(ctx, "all", "All events", {})["id"]
    engine.next_step(ctx, tid)
    inited.factory("config", "set", "cfg", "k", "v")
    engine.next_step(ctx, tid); engine.done(ctx, tid)
    engine.next_step(ctx, tid)
    try:
        engine.done(ctx, tid)
    except Exception:
        pass
    flag.write_text("x")
    engine.done(ctx, tid)
    engine.next_step(ctx, tid); engine.skip(ctx, tid)
    engine.next_step(ctx, tid)
    engine.request_changes(ctx, tid, "More")
    engine.next_step(ctx, tid)
    engine.approve(ctx, tid); engine.done(ctx, tid)
    engine.block(ctx, tid, "why"); engine.unblock(ctx, tid)
    engine.goto(ctx, tid, "opt", "redo"); engine.skip(ctx, tid)
    engine.next_step(ctx, tid); engine.approve(ctx, tid); engine.done(ctx, tid)
    session.send_prompt(ctx, tid, "hello")
    session.pause(ctx, tid); session.resume(ctx, tid)
    engine.next_step(ctx, tid); engine.wait(ctx, tid); engine.external_done(ctx, tid)
    delete.delete(ctx, tid, confirm_unpushed=True)
    log = inited.fdir / "tasks" / "archive" / tid / "events.jsonl"
    kinds = {json.loads(l)["type"] for l in log.read_text().splitlines()}
    assert EXPECTED <= kinds, EXPECTED - kinds
```

`migrated` is covered in Task 26.

- [ ] **Step 2: Run the milestone 2 tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 3: Commit milestone 2**

```bash
git add software-factory
git commit -m "milestone 2: task life"
```

---

# Milestone 3: Authoring

### Task 22: Local server core (`server.py`, `api.py`)

**Files:**
- Create: `software-factory/lib/factory/server.py`, `software-factory/lib/factory/api.py`
- Modify: `software-factory/lib/factory/commands.py` (add `serve`, `server stop`)
- Test: `software-factory/tests/test_server.py`, `software-factory/tests/serverutil.py`

**Interfaces:**
- Consumes: `fsio`, `repo`, `adapters`, `engine.poll`.
- Produces:
  - `server.IDLE_SECONDS`, `server.info_path(ctx) -> Path`, `server.read_info(ctx) -> dict|None`
  - `server.Server(ctx)` with `.port`, `.token`, `.adapter` (`{"ok", "message"}`), `.capabilities` (list), `.run()`, `.stop()`, `.start_job(fn) -> str`, `.jobs`
  - `server.ensure_server(ctx) -> dict` (`port`, `token`, `pid`), `server.page_url(info, page, **params) -> str`, `server.open_page(url)`, `server.stop_server(ctx) -> bool`
  - `api.NotFound(Exception)`; `api.route(method, pattern)` decorator; `api.dispatch(server, method, path, query, body) -> dict|list`
  - Routes in this task: `GET /api/ping`, `GET /api/info`, `POST /api/shutdown`, `GET /api/jobs/<id>`
  - Pages: `GET /editor`, `GET /dashboard` serve `web/editor.html`, `web/dashboard.html` (Tasks 23 and 30 write them; create both now as minimal valid HTML files with a `<title>`).

- [ ] **Step 1: Write the test helper `tests/serverutil.py`**

```python
import http.client
import json
import os
import time


def info(fdir):
    return json.loads((fdir / "server.json").read_text())


def request(info, method, path, body=None, token=True, origin=None, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", info["port"], timeout=30)
    headers = {"Host": host or f"127.0.0.1:{info['port']}"}
    if token:
        headers["X-Factory-Token"] = info["token"] if token is True else token
    if origin:
        headers["Origin"] = origin
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=data, headers=headers)
    r = conn.getresponse()
    raw = r.read()
    try:
        return r.status, json.loads(raw)
    except json.JSONDecodeError:
        return r.status, raw.decode()


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def wait_dead(pid, seconds=10):
    end = time.time() + seconds
    while time.time() < end:
        if not alive(pid):
            return True
        time.sleep(0.2)
    return False
```

- [ ] **Step 2: Write the failing tests**

```python
import pytest

from conftest import fake_config
from serverutil import alive, info, request, wait_dead


@pytest.fixture
def served(inited):
    inited.factory("dashboard")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def test_server_survives_the_command_and_is_reused(served):
    inited, i = served
    assert alive(i["pid"])
    assert request(i, "GET", "/api/ping")[0] == 200
    inited.factory("dashboard")
    assert info(inited.fdir)["pid"] == i["pid"]


def test_security_checks(served):
    inited, i = served
    assert request(i, "GET", "/api/ping", token=False)[0] == 401
    assert request(i, "GET", "/api/ping", token="wrong")[0] == 401
    assert request(i, "GET", "/api/ping", origin="http://evil.example")[0] == 403
    assert request(i, "GET", "/api/ping", host=f"localhost:{i['port']}")[0] == 403
    assert request(i, "GET", "/api/ping", origin=f"http://127.0.0.1:{i['port']}")[0] == 200
    status, page = request(i, "GET", "/dashboard", token=False)
    assert status == 200 and "<title>" in page


def test_stop(served):
    inited, i = served
    inited.factory("server", "stop")
    assert wait_dead(i["pid"])
    assert not (inited.fdir / "server.json").exists()


def test_idle_stop(inited):
    inited.factory("dashboard", env={"FACTORY_SERVER_IDLE_SECONDS": "2"})
    assert wait_dead(info(inited.fdir)["pid"], 15)


def test_adapter_check_failure_reported(inited):
    fake_config(inited.fdir, check_ok=False, check_message="Not in Herdr.")
    inited.factory("dashboard")
    try:
        status, data = request(info(inited.fdir), "GET", "/api/info")
        assert status == 200 and data["adapter"] == {"ok": False, "message": "Not in Herdr."}
    finally:
        inited.factory("server", "stop")
```

Task 22 adds the `dashboard` command in its simple form (start the server, print the URL, open the page). Task 29 adds the dashboard routes.

- [ ] **Step 3: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_server.py -q`
Expected: FAIL, `invalid choice: 'dashboard'`.

- [ ] **Step 4: Implement `api.py` (core routes)**

```python
import os
import re

from . import adapters
from .errors import FactoryError

ROUTES = []


class NotFound(Exception):
    pass


def route(method, pattern):
    regex = re.compile("^" + pattern + "$")

    def register(fn):
        ROUTES.append((method, regex, fn))
        return fn

    return register


def dispatch(server, method, path, query, body):
    for m, regex, fn in ROUTES:
        match = regex.match(path)
        if m == method and match:
            return fn(server, *match.groups(), query=query, body=body or {})
    raise NotFound(path)


@route("GET", "/api/ping")
def ping(server, query, body):
    return {"ok": True, "pid": os.getpid()}


@route("GET", "/api/info")
def info(server, query, body):
    ctx = server.ctx
    return {
        "columns": ctx.columns(),
        "ticket_url": ctx.factory_yaml().get("ticket_url") or "",
        "adapter": server.adapter,
        "capabilities": server.capabilities,
    }


@route("POST", "/api/shutdown")
def shutdown(server, query, body):
    server.stop()
    return {"ok": True}


@route("GET", "/api/jobs/([a-f0-9]+)")
def job(server, job_id, query, body):
    if job_id not in server.jobs:
        raise NotFound(job_id)
    return server.jobs[job_id]
```

- [ ] **Step 5: Implement `server.py`**

```python
import http.server
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from . import adapters, api, fsio, repo
from .errors import FactoryError

IDLE_SECONDS = int(os.environ.get("FACTORY_SERVER_IDLE_SECONDS", "1800"))
START_TIMEOUT = 15
WEB_DIR = Path(__file__).resolve().parent / "web"
PAGES = {"/editor": "editor.html", "/dashboard": "dashboard.html"}


def info_path(ctx):
    return ctx.fdir / "server.json"


def read_info(ctx):
    return fsio.read_json(info_path(ctx))


class Server:
    def __init__(self, ctx):
        self.ctx = ctx
        self.token = secrets.token_urlsafe(24)
        self.last = time.time()
        self.jobs = {}
        try:
            adapter = adapters.get_adapter(ctx)
            ok, message = adapter.check()
            self.capabilities = sorted(adapter.capabilities()) if ok else []
        except FactoryError as e:
            ok, message, self.capabilities = False, str(e), []
        self.adapter = {"ok": ok, "message": message}
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self))
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]

    def origin(self):
        return f"http://127.0.0.1:{self.port}"

    def run(self):
        fsio.write_json(info_path(self.ctx), {"port": self.port, "token": self.token, "pid": os.getpid()})
        threading.Thread(target=self.watch_idle, daemon=True).start()
        threading.Thread(target=self.poll_loop, daemon=True).start()
        try:
            self.httpd.serve_forever()
        finally:
            info = read_info(self.ctx)
            if info and info.get("pid") == os.getpid():
                info_path(self.ctx).unlink(missing_ok=True)

    def stop(self):
        threading.Thread(target=self.httpd.shutdown, daemon=True).start()

    def watch_idle(self):
        while True:
            time.sleep(min(30, IDLE_SECONDS))
            if time.time() - self.last > IDLE_SECONDS:
                self.stop()
                return

    def poll_seconds(self):
        override = os.environ.get("FACTORY_POLL_SECONDS")
        return int(override) if override else int(self.ctx.factory_yaml().get("poll_minutes", 5)) * 60

    def poll_loop(self):
        from . import engine
        while True:
            time.sleep(self.poll_seconds())
            try:
                engine.poll(self.ctx)
            except Exception as e:
                print(f"poll failed: {e}", file=sys.stderr, flush=True)

    def start_job(self, fn):
        job_id = secrets.token_hex(6)
        self.jobs[job_id] = {"status": "running"}

        def work():
            try:
                self.jobs[job_id] = {"status": "done", "result": fn()}
            except Exception as e:
                self.jobs[job_id] = {"status": "error", "error": str(e)}

        threading.Thread(target=work, daemon=True).start()
        return job_id


def make_handler(server):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def reply(self, code, body, content_type="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def refusal(self):
            if self.headers.get("Host") != f"127.0.0.1:{server.port}":
                return "The Host header must be 127.0.0.1 and the server port."
            origin = self.headers.get("Origin")
            if origin is not None and origin != server.origin():
                return "The Origin header is not this server."
            return None

        def handle_request(self, method):
            server.last = time.time()
            why = self.refusal()
            if why:
                return self.reply(403, {"error": why})
            url = urlparse(self.path)
            if method == "GET" and url.path in PAGES:
                return self.reply(200, (WEB_DIR / PAGES[url.path]).read_bytes(), "text/html; charset=utf-8")
            if not url.path.startswith("/api/"):
                return self.reply(404, {"error": "Not found."})
            if not secrets.compare_digest(self.headers.get("X-Factory-Token", ""), server.token):
                return self.reply(401, {"error": "Missing or wrong token."})
            try:
                body = {}
                if method == "POST":
                    length = int(self.headers.get("Content-Length") or 0)
                    body = json.loads(self.rfile.read(length) or b"{}") if length else {}
                self.reply(200, api.dispatch(server, method, url.path, parse_qs(url.query), body))
            except api.NotFound:
                self.reply(404, {"error": "Not found."})
            except FactoryError as e:
                self.reply(400, {"error": str(e)})
            except Exception as e:
                self.reply(500, {"error": f"Internal error: {e}"})

        def do_GET(self):
            self.handle_request("GET")

        def do_POST(self):
            self.handle_request("POST")

    return Handler


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def ping(info):
    req = urllib.request.Request(f"http://127.0.0.1:{info['port']}/api/ping", headers={"X-Factory-Token": info["token"]})
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def running(ctx):
    info = read_info(ctx)
    return info if info and pid_alive(info.get("pid")) and ping(info) else None


def ensure_server(ctx):
    info = running(ctx)
    if info:
        return info
    old_pid = (read_info(ctx) or {}).get("pid")
    with open(ctx.fdir / "server.log", "a") as log:
        subprocess.Popen(
            [sys.executable, str(repo.PLUGIN_ROOT / "bin" / "factory"), "serve"],
            cwd=ctx.main, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            start_new_session=True, close_fds=True,
        )
    deadline = time.time() + START_TIMEOUT
    while time.time() < deadline:
        info = read_info(ctx)
        if info and info.get("pid") != old_pid and ping(info):
            return info
        time.sleep(0.2)
    raise FactoryError("The local server did not start. See .factory/server.log.")


def page_url(info, page, **params):
    return f"http://127.0.0.1:{info['port']}/{page}?" + urlencode({"token": info["token"], **params})


def open_page(url):
    if os.environ.get("FACTORY_NO_OPEN"):
        return
    subprocess.run(["open", url], check=False)


def stop_server(ctx):
    info = running(ctx)
    if not info:
        info_path(ctx).unlink(missing_ok=True)
        return False
    req = urllib.request.Request(
        f"http://127.0.0.1:{info['port']}/api/shutdown", data=b"{}", method="POST",
        headers={"X-Factory-Token": info["token"], "Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except (urllib.error.URLError, OSError):
        pass
    deadline = time.time() + 10
    while time.time() < deadline and pid_alive(info["pid"]):
        time.sleep(0.2)
    return True
```

- [ ] **Step 6: Add the commands**

```python
    sub.add_parser("serve", parents=[common])
    sub.add_parser("dashboard", parents=[common])
    p = sub.add_parser("server")
    svs = p.add_subparsers(dest="action", required=True)
    svs.add_parser("stop", parents=[common])
```

```python
@cli.command("serve")
def serve_cmd(args):
    from . import server
    server.Server(ctx_of(args)).run()


@cli.command("dashboard")
def dashboard_cmd(args):
    from . import server
    info = server.ensure_server(ctx_of(args))
    url = server.page_url(info, "dashboard")
    server.open_page(url)
    print(f"Dashboard: {url}")


@cli.command("server stop")
def server_stop_cmd(args):
    from . import server
    print("Server stopped." if server.stop_server(ctx_of(args)) else "The server was not running.")
```

Create `web/editor.html` and `web/dashboard.html` now with this content (Tasks 23 and 30 replace them):

```html
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Software factory</title></head><body></body></html>
```

- [ ] **Step 7: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add software-factory
git commit -m "server: detached local server with token, Host and Origin checks"
```

### Task 23: Pipeline editor (`pipeline_store.py`, editor routes, `editor.html`)

**Files:**
- Create: `software-factory/lib/factory/pipeline_store.py`
- Modify: `software-factory/lib/factory/api.py` (editor routes)
- Modify: `software-factory/lib/factory/commands.py` (add `pipeline list`, `pipeline edit`, `step list`, `step show`)
- Replace: `software-factory/lib/factory/web/editor.html`
- Test: `software-factory/tests/test_editor_api.py`

**Interfaces:**
- Consumes: `Registry`, `pipeline_check`, `library.in_git` (Task 25; until then use `repo.git(["rev-parse", "--show-toplevel"], lib, check=False).returncode == 0` inline in `library_commit_offer`).
- Produces:
  - `pipeline_store.step_summary(step) -> dict` keys `id, description, category, type, level, run_in, path`
  - `pipeline_store.step_detail(reg, step) -> dict` = summary plus `manifest, body, reads, writes, children`
  - `pipeline_store.list_pipelines(reg) -> list[dict]` keys `id, description, level, path`
  - `pipeline_store.load(reg, pid) -> dict` keys `data, level, path`
  - `pipeline_store.copy(reg, source_id, new_id) -> dict` (`data` with the new id, not saved)
  - `pipeline_store.check(ctx, data, level) -> list[dict]`
  - `pipeline_store.save(ctx, data, level) -> dict` keys `path, level, library_commit` (`{"message", "paths"}` or `None`)
  - Routes: `GET /api/steps`, `GET /api/steps/<id>`, `GET /api/pipelines`, `GET /api/pipelines/<id>`, `POST /api/pipelines/copy`, `POST /api/pipelines/check`, `POST /api/pipelines/save`, `POST /api/library/commit` (Task 25)

- [ ] **Step 1: Write the failing tests**

```python
import pytest
import yaml

from conftest import write_pipeline, write_step
from serverutil import info, request


@pytest.fixture
def ed(inited):
    write_step(inited.library, "gen", {"category": "git", "writes": ["x"]})
    write_step(inited.fdir, "loc", {"category": "review", "run_in": "subagent", "reads": ["x"]})
    write_step(inited.fdir, "box", {"type": "composite", "steps": ["gen", "loc"]}, body="")
    write_pipeline(inited.fdir, {"id": "base", "steps": ["gen", "loc"]})
    inited.factory("pipeline", "edit", "base")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def test_steps_list_and_detail(ed):
    inited, i = ed
    status, steps = request(i, "GET", "/api/steps")
    by_id = {s["id"]: s for s in steps}
    assert by_id["gen"]["level"] == "generic" and by_id["loc"]["run_in"] == "subagent"
    assert by_id["user-validation"]["level"] == "builtin"
    status, box = request(i, "GET", "/api/steps/box")
    assert box["children"] == ["gen", "loc"] and box["reads"] == [] and box["writes"] == ["x"]
    assert request(i, "GET", "/api/steps/nope")[0] == 400


def test_load_copy_check_save(ed):
    inited, i = ed
    status, loaded = request(i, "GET", "/api/pipelines/base")
    assert loaded["level"] == "local" and loaded["data"]["steps"] == ["gen", "loc"]
    status, copied = request(i, "POST", "/api/pipelines/copy", {"source": "base", "new_id": "base-copy"})
    data = copied["data"]
    assert data["id"] == "base-copy"
    data["steps"].insert(0, "create-worktree")
    data["steps"].append("create-worktree")
    status, problems = request(i, "POST", "/api/pipelines/check", {"data": data, "level": "generic"})
    assert any(p["level"] == "error" for p in problems)
    assert any("local step" in p["message"] for p in problems)
    assert request(i, "POST", "/api/pipelines/save", {"data": data, "level": "local"})[0] == 400
    data["steps"].pop()
    status, saved = request(i, "POST", "/api/pipelines/save", {"data": data, "level": "generic"})
    assert status == 200 and saved["library_commit"]["message"] == "Factory library: add pipeline base-copy"
    stored = yaml.safe_load((inited.library / "pipelines" / "base-copy.yaml").read_text())
    assert stored["steps"] == ["create-worktree", "gen", "loc"]


def test_cli_lists(ed):
    inited, i = ed
    ids = [p["id"] for p in inited.factory.json("pipeline", "list")]
    assert "base" in ids
    assert "gen" in [s["id"] for s in inited.factory.json("step", "list")]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_editor_api.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement `pipeline_store.py`**

```python
from . import fsio, pipeline_check, repo
from .errors import FactoryError
from .registry import STEP_ID_RE, Registry, normalize_entry


def step_summary(step):
    return {"id": step.id, "description": step.description, "category": step.category, "type": step.type,
            "level": step.level, "run_in": step.run_in, "path": str(step.path)}


def step_detail(reg, step):
    reads, writes = reg.io(step.id)
    return {**step_summary(step), "manifest": step.manifest, "body": step.body,
            "reads": reads, "writes": writes, "children": step.children}


def list_pipelines(reg):
    return [{"id": p.id, "description": p.data.get("description", ""), "level": p.level, "path": str(p.path)}
            for p in sorted(reg.pipelines.values(), key=lambda p: p.id)]


def load(reg, pid):
    p = reg.pipeline(pid)
    return {"data": p.data, "level": p.level, "path": str(p.path)}


def copy(reg, source_id, new_id):
    data = dict(reg.pipeline(source_id).data)
    data["id"] = new_id
    return {"data": data}


def check(ctx, data, level):
    reg = Registry.load(ctx)
    return [p.to_dict() for p in pipeline_check.check(reg, data, ctx.columns(), level)]


def compact(data):
    steps = []
    for entry in data.get("steps") or []:
        e = {k: v for k, v in normalize_entry(entry).items() if v not in (None, "", {}, [])}
        steps.append(e["id"] if list(e) == ["id"] else e)
    clean = {k: v for k, v in data.items() if not k.startswith("_") and v not in (None, "", {}, [])}
    clean["steps"] = steps
    return clean


def target_root(ctx, level):
    if level == "local":
        return ctx.fdir
    if level == "generic":
        lib = ctx.library()
        if not lib:
            raise FactoryError("No library is configured.")
        return lib
    raise FactoryError("Save as `generic` or `local`.")


def library_in_git(lib):
    return repo.git(["rev-parse", "--show-toplevel"], lib, check=False).returncode == 0


def save(ctx, data, level):
    problems = check(ctx, data, level)
    errors = [p["message"] for p in problems if p["level"] == "error"]
    if errors:
        raise FactoryError("The pipeline has errors:\n" + "\n".join(errors))
    pid = data["id"]
    if not STEP_ID_RE.match(pid):
        raise FactoryError("Invalid pipeline id.")
    path = target_root(ctx, level) / "pipelines" / f"{pid}.yaml"
    existed = path.exists()
    fsio.write_yaml(path, compact(data))
    offer = None
    if level == "generic" and library_in_git(ctx.library()):
        offer = {"message": f"Factory library: {'update' if existed else 'add'} pipeline {pid}", "paths": [str(path)]}
    return {"path": str(path), "level": level, "library_commit": offer, "problems": problems}
```

In Task 25, replace `library_in_git` with `library.in_git`.

- [ ] **Step 4: Add the editor routes to `api.py`**

```python
from .registry import Registry


def registry(server):
    return Registry.load(server.ctx)


@route("GET", "/api/steps")
def steps(server, query, body):
    from . import pipeline_store
    return [pipeline_store.step_summary(s) for s in sorted(registry(server).steps.values(), key=lambda s: s.id)]


@route("GET", "/api/steps/([a-z][a-z0-9_-]*)")
def step(server, sid, query, body):
    from . import pipeline_store
    reg = registry(server)
    return pipeline_store.step_detail(reg, reg.step(sid))


@route("GET", "/api/pipelines")
def pipelines(server, query, body):
    from . import pipeline_store
    return pipeline_store.list_pipelines(registry(server))


@route("GET", "/api/pipelines/([a-z][a-z0-9_-]*)")
def pipeline(server, pid, query, body):
    from . import pipeline_store
    return pipeline_store.load(registry(server), pid)


@route("POST", "/api/pipelines/copy")
def pipeline_copy(server, query, body):
    from . import pipeline_store
    return pipeline_store.copy(registry(server), body["source"], body["new_id"])


@route("POST", "/api/pipelines/check")
def pipeline_check_route(server, query, body):
    from . import pipeline_store
    return pipeline_store.check(server.ctx, body["data"], body.get("level"))


@route("POST", "/api/pipelines/save")
def pipeline_save(server, query, body):
    from . import pipeline_store
    return pipeline_store.save(server.ctx, body["data"], body["level"])
```

- [ ] **Step 5: Add the commands**

Inside the existing `pipeline` group (Task 4):

```python
    ps.add_parser("list", parents=[common])
    pe = ps.add_parser("edit", parents=[common]); pe.add_argument("id", nargs="?")
```

New `step` group:

```python
    p = sub.add_parser("step")
    sts = p.add_subparsers(dest="action", required=True)
    sts.add_parser("list", parents=[common])
    sh = sts.add_parser("show", parents=[common]); sh.add_argument("id")
```

```python
@cli.command("pipeline list")
def pipeline_list_cmd(args):
    from . import pipeline_store
    from .registry import Registry
    rows = pipeline_store.list_pipelines(Registry.load(ctx_of(args)))
    if args.json:
        cli.emit(rows, True)
        return
    for r in rows:
        print(f"{r['id']} ({r['level']}): {r['description']}")


@cli.command("pipeline edit")
def pipeline_edit_cmd(args):
    from . import server
    info = server.ensure_server(ctx_of(args))
    url = server.page_url(info, "editor", **({"id": args.id} if args.id else {}))
    server.open_page(url)
    print(f"Pipeline editor: {url}")


@cli.command("step list")
def step_list_cmd(args):
    from . import pipeline_store
    from .registry import Registry
    reg = Registry.load(ctx_of(args))
    rows = [pipeline_store.step_summary(s) for s in sorted(reg.steps.values(), key=lambda s: s.id)]
    if args.json:
        cli.emit(rows, True)
        return
    for r in rows:
        print(f"{r['id']} [{r['category']}] ({r['level']}, {r['run_in']}): {r['description']}")


@cli.command("step show")
def step_show_cmd(args):
    from . import pipeline_store
    from .registry import Registry
    reg = Registry.load(ctx_of(args))
    detail = pipeline_store.step_detail(reg, reg.step(args.id))
    cli.emit(detail, True) if args.json else print(f"{detail['path']}\n\n{detail['body']}")
```

- [ ] **Step 6: Write `web/editor.html`**

Plain HTML, CSS and JavaScript, no external library, no comments. Required behavior (each item maps to a prompt bullet in "Pipeline editor"):

1. Read `token` and `id` from `location.search`. Every request sends `X-Factory-Token`. Show API errors in a red `#error` bar.
2. Start panel when no `id`: buttons "Create an empty pipeline", "Copy an existing pipeline" (select from `GET /api/pipelines`, new id input, `POST /api/pipelines/copy`), "Edit an existing pipeline" (select).
3. Left column `#available`: steps from `GET /api/steps`, each showing id, category, description, level, and run_in. Filters: category `<select>` and text `<input>`. Button "Reload steps".
4. Right column: form fields id, description, session `model`, session `effort`, `start_column` (select from `GET /api/info` columns, with an empty option), inputs editor (rows of key + description, add/remove).
5. Pipeline step list `#pipeline`: drag from `#available` to `#pipeline` to add (native `draggable` + `dragover`/`drop`), drag inside `#pipeline` to reorder, a remove button per row, and an edit form per row for `with` (key/value rows), `model`, `effort`, `column`.
6. Clicking a step (in either list) opens `#detail`, read-only: full manifest fields, body in a `<pre>` as text (use `textContent`, never `innerHTML` for data), level and file path, and children links for a composite step.
7. After each change, wait 300 ms, then `POST /api/pipelines/check` with the current data and the chosen save level. Show errors and warnings in `#problems`. Disable Save while there is an error.
8. Save: ask "generic" or "local" (radio buttons; when the loaded pipeline is generic, the local choice is labeled "Save a local override"). `POST /api/pipelines/save`. When the result has `library_commit`, show the files and the message with a "Commit to library" button that calls `POST /api/library/commit` with that message and paths.

Data shape sent to the API: `{"id", "description", "claude": {"model", "effort"}, "start_column", "inputs": {key: {"description"}}, "steps": [{"id", "with", "model", "effort", "column"}]}`. The server compacts empty fields.

Skeleton to start from:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pipeline editor</title>
<style>
:root { --bg: #fafafa; --fg: #1d1d1f; --muted: #6e6e73; --line: #d2d2d7; --err: #c62828; --warn: #b26a00; --accent: #0a62c9; }
@media (prefers-color-scheme: dark) { :root { --bg: #161618; --fg: #f2f2f7; --muted: #a1a1a6; --line: #3a3a3c; --err: #ff6b6b; --warn: #ffb74d; --accent: #64a8ff; } }
body { margin: 0; font: 14px/1.4 -apple-system, system-ui, sans-serif; background: var(--bg); color: var(--fg); }
header { padding: 12px 16px; border-bottom: 1px solid var(--line); display: flex; gap: 12px; align-items: center; }
main { display: grid; grid-template-columns: 320px 1fr 360px; gap: 16px; padding: 16px; }
.card { border: 1px solid var(--line); border-radius: 8px; padding: 8px; margin: 6px 0; background: var(--bg); cursor: grab; }
.muted { color: var(--muted); font-size: 12px; }
#error { display: none; background: var(--err); color: white; padding: 8px 16px; }
.problem.error { color: var(--err); } .problem.warning { color: var(--warn); }
#pipeline { min-height: 200px; border: 2px dashed var(--line); border-radius: 8px; padding: 8px; }
pre { white-space: pre-wrap; }
</style>
</head>
<body>
<div id="error"></div>
<header><strong>Pipeline editor</strong><span id="title" class="muted"></span></header>
<section id="start"></section>
<main>
  <section><h3>Available steps</h3><div id="filters"></div><div id="available"></div></section>
  <section><h3>Pipeline</h3><div id="form"></div><div id="pipeline"></div><div id="problems"></div><div id="save"></div></section>
  <section><h3>Step detail</h3><div id="detail" class="muted">Click a step.</div></section>
</main>
<script>
const params = new URLSearchParams(location.search);
const TOKEN = params.get("token");
async function api(path, body) {
  const opts = { headers: { "X-Factory-Token": TOKEN } };
  if (body !== undefined) { opts.method = "POST"; opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  const r = await fetch(path, opts);
  const data = await r.json();
  if (!r.ok) { showError(data.error || r.statusText); throw new Error(data.error); }
  hideError();
  return data;
}
function showError(text) { const e = document.getElementById("error"); e.textContent = text; e.style.display = "block"; }
function hideError() { document.getElementById("error").style.display = "none"; }
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) { if (k.startsWith("on")) node.addEventListener(k.slice(2), v); else node.setAttribute(k, v); }
  for (const c of children) node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return node;
}
</script>
</body>
</html>
```

Complete the script with the behavior list above. Keep it under 500 lines.

- [ ] **Step 7: Manual check in the browser**

Run `factory pipeline edit base` in a test repository from `verification/software-factory/work/`, open the printed URL, and check items 2 to 8 by hand. Write the result (pass/fail per item) in `verification/software-factory/editor-manual-check.md`.

- [ ] **Step 8: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add software-factory verification/software-factory/editor-manual-check.md
git commit -m "editor: pipeline editor page and API"
```

### Task 24: Catalog and `requires` checks

**Files:**
- Create: `software-factory/lib/factory/requires.py`, `software-factory/lib/factory/catalog.py`
- Create: `software-factory/catalog/pipelines/quick-task.yaml`, `plan-and-build.yaml`
- Create: `software-factory/catalog/steps/{implement,commit,rebase,push,run-tests,create-pr,review,address-review-comments,brainstorm,write-plan,execute-plan,wait-review,wait-qa}.md`, `push.sh`, `run-tests.sh`
- Modify: `software-factory/lib/factory/commands.py` (add `catalog list`, `catalog install`)
- Test: `software-factory/tests/test_catalog.py`

**Interfaces:**
- Produces:
  - `requires.claude_home() -> Path`, `requires.skill_present(name, main) -> bool`, `requires.missing(requires, main) -> list[str]`
  - `catalog.CATALOG = PLUGIN_ROOT / "catalog"`
  - `catalog.items(ctx) -> list[dict]` keys `kind (step|pipeline), id, category, description, status (not installed|installed|changed), location (local|generic|None), missing_requires, steps (pipelines only)`
  - `catalog.install(ctx, item_id, target, with_steps=False, replace=False, dry_run=False) -> dict` keys `files, conflicts ([{path, diff}]), missing_steps, written, library_commit`
- Script steps in the catalog: the step body is the script file name, for example `push.sh`. Install copies the `.md` and the `.sh` side by side.
- Wrapped skills and `run_in`: `/superpowers:brainstorming`, `/superpowers:writing-plans` and `/superpowers:executing-plans` all ask the user questions (brainstorming asks clarifying questions; writing-plans asks the user to choose an execution method; executing-plans asks the user when blocked). So `brainstorm`, `write-plan` and `execute-plan` use `run_in: session`. Before writing them, read the three `SKILL.md` files under `~/.claude/plugins/` and confirm this. If one never asks the user, use `run_in: subagent` for it.

- [ ] **Step 1: Write the catalog files**

`catalog/pipelines/quick-task.yaml`:

```yaml
id: quick-task
description: Do a small change, validate it, and commit it
steps:
  - implement
  - user-validation
  - commit
```

`catalog/pipelines/plan-and-build.yaml`:

```yaml
id: plan-and-build
description: Brainstorm a spec, write a plan, build it, and follow review and QA
start_column: Discovery
steps:
  - brainstorm
  - id: user-validation
    with:
      target: artifact
      artifact_key: spec
  - write-plan
  - id: user-validation
    with:
      target: artifact
      artifact_key: plan
  - execute-plan
  - run-tests
  - commit
  - push
  - create-pr
  - wait-review
  - wait-qa
```

`catalog/steps/implement.md`:

```markdown
---
id: implement
description: Do the task described in the task description and summary
category: code
type: prompt
reads: [summary]
writes: []
done_when: The change is made in the worktree and the code builds.
required: false
column: Implementation
---

Read the task description (`factory status`) and the `summary`, when set.
Make the change in this worktree. Keep it small and focused.
If something is unclear, run `factory block "<question>"`, ask the user, then run `factory unblock` when the user answers.
```

`catalog/steps/commit.md`:

```markdown
---
id: commit
description: Commit the changes with a message in the repository's commit style
category: git
type: prompt
reads: [branch]
writes: [branch]
done_when: All changes are committed on a branch.
done_check: test -z "$(git status --porcelain)" && git symbolic-ref -q HEAD >/dev/null
required: false
---

1. If HEAD is detached, create a branch named after the task id: `git switch -c <task id>`. Save it with `factory state set branch <name>`.
2. Read `git log -n 10 --oneline` and follow the same message style.
3. Stage and commit all changes of the task. Do not commit unrelated files.
```

`catalog/steps/rebase.md`:

```markdown
---
id: rebase
description: Rebase the branch on the latest origin base branch
category: git
type: prompt
done_when: The branch is rebased on origin/<base_ref> and has no conflict.
required: false
config:
  base_ref:
    description: The base branch to rebase on
    default: main
---

1. Run `git fetch origin <base_ref>` and `git rebase origin/<base_ref>`.
2. Resolve simple conflicts: imports, formatting, independent changes in the same file.
3. On a complex conflict, run `git rebase --abort`, then `factory block "Complex rebase conflict in <files>"`, and explain the conflict to the user.
```

`catalog/steps/push.md`:

```markdown
---
id: push
description: Push the branch to origin
category: git
type: script
done_when: The branch is on origin with all local commits.
done_check: b=$(git symbolic-ref --short -q HEAD) && git rev-parse --verify -q "refs/remotes/origin/$b" >/dev/null && test -z "$(git log "origin/$b..HEAD" --oneline)"
required: false
requires: [git]
---

push.sh
```

`catalog/steps/push.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
branch=$(git symbolic-ref --short -q HEAD) || { echo "HEAD is detached. Create a branch first."; exit 1; }
git push -u origin "$branch"
factory state set branch "$branch"
```

`catalog/steps/run-tests.md`:

```markdown
---
id: run-tests
description: Run the test command of the repository
category: test
type: script
done_when: The test command passes.
done_check: bash -c "$FACTORY_CONFIG_TEST_COMMAND"
required: false
config:
  test_command:
    description: The command that runs the tests, for example `./gradlew test` or `npm test`
---

run-tests.sh
```

`catalog/steps/run-tests.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
bash -c "$FACTORY_CONFIG_TEST_COMMAND"
```

`catalog/steps/create-pr.md`:

```markdown
---
id: create-pr
description: Create a pull request or merge request with gh or glab
category: forge
type: prompt
reads: [branch, summary]
writes: [mr_url]
done_when: The pull request or merge request exists and its URL is saved.
done_check: test -n "$(factory state get mr_url)"
required: false
column: Review
config:
  forge:
    description: The forge of this repository, `github` or `gitlab`
  target_branch:
    description: The branch the pull request targets
    default: main
---

1. When `forge` is `github`, run `gh pr create --base <target_branch> --head <branch> --title "<title>" --body "<body>"`. When `forge` is `gitlab`, run `glab mr create --target-branch <target_branch> --source-branch <branch> --title "<title>" --description "<body>" --yes`.
2. Write a short title and a body from the task description, the summary and the commits.
3. Save the URL with `factory state set mr_url <url>`.
```

`catalog/steps/review.md`:

```markdown
---
id: review
description: Review the branch diff and save the findings as an artifact
category: review
type: prompt
run_in: subagent
model: opus
effort: high
writes: [review]
done_when: The review file exists and its path is saved.
done_check: test -f "$(factory state get review)"
required: false
config:
  base_ref:
    description: The base branch to compare with
    default: main
---

1. Run `git fetch origin <base_ref>` and read `git diff origin/<base_ref>...HEAD`.
2. Find real problems: bugs, missing tests, security issues. Skip style comments.
3. Write the findings to `$(factory artifact path review.md)`, one numbered item per finding with the file and line.
4. Save the path with `factory state set review <path>`.
```

`catalog/steps/address-review-comments.md`:

```markdown
---
id: address-review-comments
description: Read the open review comments and fix them
category: review
type: prompt
reads: [mr_url]
done_when: Every open review comment is fixed or answered.
required: false
config:
  forge:
    description: The forge of this repository, `github` or `gitlab`
---

1. Read the open comments: `gh pr view <mr_url> --comments` for `github`, `glab mr view <mr_url> --comments` for `gitlab`.
2. Fix each comment in the code. If a comment is wrong or unclear, ask the user before you answer it.
3. Commit the fixes and push the branch.
```

`catalog/steps/brainstorm.md`:

```markdown
---
id: brainstorm
description: Brainstorm the task with the user and write a spec
category: planning
type: skill
run_in: session
reads: [summary]
writes: [spec]
done_when: The spec file exists and its path is saved.
done_check: test -f "$(factory state get spec)"
required: false
requires: [/superpowers:brainstorming]
column: Specification
---

Run `/superpowers:brainstorming` on the task description and the `summary`.
Save the spec file at the path printed by `factory artifact path spec.md`, not in the repository.
Save the path with `factory state set spec <path>`.
Stop when the spec is written. The next step asks the user to validate it.
```

`catalog/steps/write-plan.md`:

```markdown
---
id: write-plan
description: Write an implementation plan from the spec
category: planning
type: skill
run_in: session
reads: [spec]
writes: [plan]
done_when: The plan file exists and its path is saved.
done_check: test -f "$(factory state get plan)"
required: false
requires: [/superpowers:writing-plans]
column: Plan
config:
  plan_style:
    description: Extra instructions for the plan, for example the commit size
    default: small commits
---

Run `/superpowers:writing-plans` on the spec file at `spec`, following `plan_style`.
Save the plan at the path printed by `factory artifact path plan.md`, not in the repository.
Save the path with `factory state set plan <path>`.
Stop when the plan is written. The next step asks the user to validate it.
```

`catalog/steps/execute-plan.md`:

```markdown
---
id: execute-plan
description: Execute the implementation plan
category: build
type: skill
run_in: session
reads: [plan]
done_when: Every task of the plan is done and committed.
required: false
requires: [/superpowers:executing-plans]
column: Implementation
---

Run `/superpowers:executing-plans` on the plan file at `plan`.
Work in this worktree. When the skill offers to finish the branch, stop there: the next steps run the tests, push and create the pull request.
```

`catalog/steps/wait-review.md`:

```markdown
---
id: wait-review
description: Wait until the pull request or merge request is approved
category: forge
type: prompt
reads: [mr_url]
done_when: The pull request or merge request is approved.
done_check: 'if [ "$FACTORY_CONFIG_FORGE" = github ]; then gh pr view "$(factory state get mr_url)" --json reviewDecision -q .reviewDecision | grep -qx APPROVED; else glab api "projects/:id/merge_requests/$(basename "$(factory state get mr_url)")/approvals" | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get(\"approved\") else 1)"; fi'
wait_external: true
required: false
column: Review
config:
  forge:
    description: The forge of this repository, `github` or `gitlab`
---

Tell the user the pull request is waiting for review, with its URL (`mr_url`).
Then run `factory wait`.
```

`catalog/steps/wait-qa.md`:

```markdown
---
id: wait-qa
description: Wait until the user marks QA as done
category: qa
type: prompt
done_when: QA is done.
wait_external: true
required: false
column: QA
---

Tell the user the task waits for QA. The user marks it done from the dashboard or the menu.
Then run `factory wait`.
```

- [ ] **Step 2: Write the failing tests**

```python
import re

import yaml

from conftest import SF, write_step
from factory import repo, requires

FORBIDDEN = ["nextory", "android", "kotlin", "gradlew", "crashlytics", "jira", "herdr", "fabien"]


def by_id(items):
    return {i["id"]: i for i in items}


def test_list_and_install_pipeline_with_missing_steps(inited):
    items = by_id(inited.factory.json("catalog", "list"))
    assert items["quick-task"]["status"] == "not installed"
    dry = inited.factory.json("catalog", "install", "quick-task", "--local", "--dry-run")
    assert sorted(dry["missing_steps"]) == ["commit", "implement"]
    inited.factory("catalog", "install", "quick-task", "--local", "--with-steps")
    assert (inited.fdir / "pipelines" / "quick-task.yaml").exists()
    assert (inited.fdir / "steps" / "commit.md").exists()
    items = by_id(inited.factory.json("catalog", "list"))
    assert items["quick-task"]["status"] == "installed" and items["quick-task"]["location"] == "local"
    (inited.fdir / "steps" / "commit.md").write_text((inited.fdir / "steps" / "commit.md").read_text() + "\nMore.\n")
    assert by_id(inited.factory.json("catalog", "list"))["commit"]["status"] == "changed"


def test_replace_needs_flag_and_shows_diff(inited):
    inited.factory("catalog", "install", "push", "--generic")
    assert (inited.library / "steps" / "push.sh").exists()
    (inited.library / "steps" / "push.md").write_text("changed\n")
    dry = inited.factory.json("catalog", "install", "push", "--generic", "--dry-run")
    assert dry["conflicts"] and "changed" in dry["conflicts"][0]["diff"]
    r = inited.factory("catalog", "install", "push", "--generic", check=False)
    assert r.returncode == 1 and "--replace" in r.stderr
    out = inited.factory.json("catalog", "install", "push", "--generic", "--replace")
    assert out["library_commit"]["message"] == "Factory library: add step push"


def test_missing_requires(inited, work):
    items = by_id(inited.factory.json("catalog", "list"))
    assert "/superpowers:brainstorming" in items["brainstorm"]["missing_requires"]
    skill = work / "claude-home" / "plugins" / "cache" / "m" / "superpowers" / "1.0" / "skills" / "brainstorming"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("x")
    items = by_id(inited.factory.json("catalog", "list"))
    assert items["brainstorm"]["missing_requires"] == []
    assert requires.missing(["definitely-not-a-tool-xyz", "git"], inited.repo) == ["definitely-not-a-tool-xyz"]


def test_catalog_is_generic():
    for path in (SF / "catalog").rglob("*"):
        if path.is_file():
            text = path.read_text().lower()
            assert not [w for w in FORBIDDEN if w in text], path
    for path in (SF / "catalog" / "steps").glob("*.md"):
        manifest = yaml.safe_load(path.read_text().split("---")[1])
        for item in manifest.get("requires") or []:
            assert not item.startswith("/") or item.startswith("/superpowers:"), path
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_catalog.py -q`
Expected: FAIL.

- [ ] **Step 4: Implement `requires.py`**

```python
import os
import shutil
from pathlib import Path


def claude_home():
    return Path(os.environ.get("FACTORY_CLAUDE_HOME", "~/.claude")).expanduser()


def skill_present(name, main):
    plugin, _, skill = name.lstrip("/").rpartition(":")
    if not plugin:
        for root in (claude_home() / "skills", Path(main) / ".claude" / "skills"):
            if (root / skill / "SKILL.md").exists():
                return True
    plugins = claude_home() / "plugins"
    if not plugins.exists():
        return False
    pattern = f"**/{plugin}/**/skills/{skill}/SKILL.md" if plugin else f"**/skills/{skill}/SKILL.md"
    return next(plugins.glob(pattern), None) is not None


def missing(items, main):
    out = []
    for item in items:
        present = skill_present(item, main) if item.startswith("/") else shutil.which(item) is not None
        if not present:
            out.append(item)
    return out
```

- [ ] **Step 5: Implement `catalog.py`**

```python
import difflib
import shutil
from pathlib import Path

from . import fsio, repo, requires
from .errors import FactoryError
from .registry import Registry, parse_step_text

CATALOG = repo.PLUGIN_ROOT / "catalog"


def step_files(sid):
    files = [CATALOG / "steps" / f"{sid}.md"]
    script = CATALOG / "steps" / f"{sid}.sh"
    if script.exists():
        files.append(script)
    return files


def item_files(kind, item_id):
    if kind == "pipeline":
        return [CATALOG / "pipelines" / f"{item_id}.yaml"]
    return step_files(item_id)


def catalog_items():
    out = []
    for p in sorted((CATALOG / "pipelines").glob("*.yaml")):
        data = fsio.read_yaml(p, {})
        out.append({"kind": "pipeline", "id": data["id"], "category": "pipeline", "description": data.get("description", ""),
                    "requires": [], "steps": [s if isinstance(s, str) else s["id"] for s in data.get("steps", [])]})
    for p in sorted((CATALOG / "steps").glob("*.md")):
        manifest, _ = parse_step_text(p.read_text(), p)
        out.append({"kind": "step", "id": manifest["id"], "category": manifest.get("category", ""),
                    "description": manifest.get("description", ""), "requires": list(manifest.get("requires") or []), "steps": None})
    return out


def find_item(item_id):
    for item in catalog_items():
        if item["id"] == item_id:
            return item
    raise FactoryError(f"The catalog has no item `{item_id}`.")


def dest_root(ctx, target):
    if target == "local":
        return ctx.fdir
    lib = ctx.library()
    if not lib:
        raise FactoryError("No library is configured.")
    return lib


def dest_of(root, src):
    return root / src.parent.name / src.name


def status_in(root, kind, item_id):
    files = item_files(kind, item_id)
    dests = [dest_of(root, f) for f in files]
    if not dests[0].exists():
        return None
    same = all(d.exists() and d.read_bytes() == f.read_bytes() for f, d in zip(files, dests))
    return "installed" if same else "changed"


def items(ctx):
    roots = [("local", ctx.fdir)] + ([("generic", ctx.library())] if ctx.library() else [])
    out = []
    for item in catalog_items():
        status, location = "not installed", None
        for name, root in roots:
            found = status_in(root, item["kind"], item["id"])
            if found:
                status, location = found, name
                break
        out.append({**item, "status": status, "location": location,
                    "missing_requires": requires.missing(item["requires"], ctx.main)})
    return out


def diff(dest, src):
    return "".join(difflib.unified_diff(dest.read_text().splitlines(True), src.read_text().splitlines(True),
                                        fromfile=str(dest), tofile=f"catalog/{src.parent.name}/{src.name}"))


def missing_steps(ctx, item):
    if item["kind"] != "pipeline":
        return []
    reg = Registry.load(ctx)
    catalog_steps = {i["id"] for i in catalog_items() if i["kind"] == "step"}
    return sorted({s for s in item["steps"] if s not in reg.steps and s in catalog_steps})


def install(ctx, item_id, target, with_steps=False, replace=False, dry_run=False):
    item = find_item(item_id)
    root = dest_root(ctx, target)
    missing = missing_steps(ctx, item)
    sources = list(item_files(item["kind"], item_id))
    if with_steps:
        for sid in missing:
            sources += step_files(sid)
    plan = {"files": [], "conflicts": [], "missing_steps": missing, "written": [], "library_commit": None}
    for src in sources:
        dest = dest_of(root, src)
        plan["files"].append(str(dest))
        if dest.exists() and dest.read_bytes() != src.read_bytes():
            plan["conflicts"].append({"path": str(dest), "diff": diff(dest, src)})
    if dry_run:
        return plan
    if plan["conflicts"] and not replace:
        raise FactoryError("Some files already exist and differ. Show the difference to the user, then run again with --replace after approval.")
    for src in sources:
        dest = dest_of(root, src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        if src.suffix == ".sh":
            dest.chmod(0o755)
        plan["written"].append(str(dest))
    if target == "generic" and repo.git(["rev-parse", "--show-toplevel"], root, check=False).returncode == 0:
        plan["library_commit"] = {"message": f"Factory library: add {item['kind']} {item_id}", "paths": plan["written"]}
    return plan
```

- [ ] **Step 6: Add the commands**

```python
    p = sub.add_parser("catalog")
    cts = p.add_subparsers(dest="action", required=True)
    cts.add_parser("list", parents=[common])
    ci = cts.add_parser("install", parents=[common])
    ci.add_argument("id")
    where = ci.add_mutually_exclusive_group(required=True)
    where.add_argument("--generic", action="store_true")
    where.add_argument("--local", action="store_true")
    ci.add_argument("--with-steps", action="store_true")
    ci.add_argument("--replace", action="store_true")
    ci.add_argument("--dry-run", action="store_true")
```

```python
@cli.command("catalog list")
def catalog_list_cmd(args):
    from . import catalog
    rows = catalog.items(ctx_of(args))
    if args.json:
        cli.emit(rows, True)
        return
    for r in rows:
        where = f" ({r['location']})" if r["location"] else ""
        missing = f" Missing: {', '.join(r['missing_requires'])}." if r["missing_requires"] else ""
        print(f"{r['kind']} {r['id']} [{r['category']}]: {r['description']}. {r['status']}{where}.{missing}")


@cli.command("catalog install")
def catalog_install_cmd(args):
    from . import catalog
    target = "generic" if args.generic else "local"
    result = catalog.install(ctx_of(args), args.id, target, args.with_steps, args.replace, args.dry_run)
    if args.json:
        cli.emit(result, True)
        return
    for path in result["written"] or result["files"]:
        print(path)
    if result["missing_steps"] and not args.with_steps:
        print("Steps not installed: " + ", ".join(result["missing_steps"]) + ". Add --with-steps to install them.")
```

- [ ] **Step 7: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add software-factory
git commit -m "catalog: starter pipelines and steps, install, requires check"
```

### Task 25: Library commits (`library.py`)

**Files:**
- Create: `software-factory/lib/factory/library.py`
- Modify: `software-factory/lib/factory/pipeline_store.py`, `catalog.py` (use `library.in_git`)
- Modify: `software-factory/lib/factory/api.py` (`POST /api/library/commit`)
- Modify: `software-factory/lib/factory/commands.py` (add `library commit`)
- Test: `software-factory/tests/test_library.py`

**Interfaces:**
- Produces: `library.in_git(lib) -> bool`, `library.repo_root(lib) -> Path|None`, `library.message(action, kind, item_id) -> str`, `library.commit(ctx, message, paths) -> str` (commit sha)

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from conftest import git
from factory import library, repo
from factory.errors import FactoryError


def test_commit_only_given_files(inited):
    root = inited.library.parent
    git("add", "-A", cwd=root)
    git("commit", "-m", "library", cwd=root)
    (inited.library / "steps" / "a.md").write_text("a\n")
    (root / "other.txt").write_text("staged change\n")
    git("add", "other.txt", cwd=root)
    msg = library.message("add", "step", "a")
    assert msg == "Factory library: add step a"
    inited.factory("library", "commit", msg, inited.library / "steps" / "a.md")
    assert git("log", "-1", "--format=%s", cwd=root) == msg
    assert git("show", "--name-only", "--format=", "HEAD", cwd=root) == "factory-library/steps/a.md"
    assert git("diff", "--cached", "--name-only", cwd=root) == "other.txt"


def test_refuses_paths_outside_library(inited, work):
    with pytest.raises(FactoryError, match="library"):
        library.commit(repo.load_ctx(cwd=inited.repo), "x", [str(work / "x.txt")])


def test_disabled_without_git(inited, work, factory):
    lib = work / "plain-lib"
    lib.mkdir()
    import yaml
    data = yaml.safe_load((inited.fdir / "factory.yaml").read_text())
    data["library"] = str(lib)
    (inited.fdir / "factory.yaml").write_text(yaml.safe_dump(data))
    (lib / "s.md").write_text("x")
    with pytest.raises(FactoryError, match="disabled"):
        library.commit(repo.load_ctx(cwd=inited.repo), "x", [str(lib / "s.md")])
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_library.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement `library.py`**

```python
from pathlib import Path

from . import repo
from .errors import FactoryError


def repo_root(lib):
    if not lib or not Path(lib).exists():
        return None
    r = repo.git(["rev-parse", "--show-toplevel"], lib, check=False)
    return Path(r.stdout.strip()).resolve() if r.returncode == 0 else None


def in_git(lib):
    return repo_root(lib) is not None


def message(action, kind, item_id):
    return f"Factory library: {action} {kind} {item_id}"


def commit(ctx, message_text, paths):
    lib = ctx.library()
    top = repo_root(lib)
    if top is None:
        raise FactoryError("The library is not in a git repository. Library commits are disabled.")
    rels = []
    for p in paths:
        full = Path(p).expanduser()
        full = full.parent.resolve() / full.name
        if not full.is_relative_to(lib):
            raise FactoryError(f"{full} is not in the library {lib}.")
        rels.append(str(full.relative_to(top)))
    if not rels:
        raise FactoryError("No file to commit.")
    repo.git(["add", "-A", "--", *rels], top)
    repo.git(["commit", "--only", "-m", message_text, "--", *rels], top)
    return repo.git(["rev-parse", "HEAD"], top).stdout.strip()
```

Replace `library_in_git` in `pipeline_store.py` and the inline check in `catalog.py` with `library.in_git(...)`.

- [ ] **Step 4: Add the route and the command**

```python
@route("POST", "/api/library/commit")
def library_commit(server, query, body):
    from . import library
    return {"sha": library.commit(server.ctx, body["message"], body["paths"])}
```

```python
    p = sub.add_parser("library")
    ls = p.add_subparsers(dest="action", required=True)
    lc = ls.add_parser("commit", parents=[common]); lc.add_argument("message"); lc.add_argument("paths", nargs="+")
```

```python
@cli.command("library commit")
def library_commit_cmd(args):
    from . import library
    sha = library.commit(ctx_of(args), args.message, args.paths)
    print(f"Committed {sha[:10]}. Not pushed.")
```

- [ ] **Step 5: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add software-factory
git commit -m "library: commit only the given library files"
```

### Task 26: Step assistant (`new-step`, `new-step-assistant`)

**Files:**
- Create: `software-factory/builtin/steps/new-step.md`, `software-factory/builtin/pipelines/new-step-assistant.yaml`
- Test: `software-factory/tests/test_step_assistant.py`

- [ ] **Step 1: Write the built-in pipeline**

`builtin/pipelines/new-step-assistant.yaml`:

```yaml
id: new-step-assistant
description: Create a new step with an assistant
steps:
  - new-step
```

- [ ] **Step 2: Write the built-in step**

`builtin/steps/new-step.md`:

```markdown
---
id: new-step
description: Ask the user for a new step, write it, and add it to pipelines
category: factory
type: prompt
run_in: session
done_when: The step file is written after approval, and the chosen pipelines are updated.
required: false
---

You create one new factory step with the user. Ask one question at a time.

1. Ask where to save the step:
   - Generic: in `<library>/steps/` (the library path is in `.factory/factory.yaml`, key `library`), reusable in any repository that uses this library.
   - Local: in `.factory/steps/` of this repository, only for this repository.
2. Ask the goal of the step.
3. Ask its type: `prompt`, `skill`, `script` or `composite`. For a composite, show `factory step list` and ask which steps to use, in order.
4. Ask its category. First show the existing categories from `factory step list --json` (field `category`), so the user reuses one when it fits.
5. Ask what it reads from and writes to the task state.
6. Ask its done condition. Offer a `done_check` shell command when one is possible.
7. Ask where it runs: in the session or in a subagent. If the step asks the user anything, it must run in the session.
8. For a subagent: ask its `model` and `effort`.
9. Ask its config keys, each with a description and an optional default value.
10. Ask if it must never be skipped (`required`).
11. Ask its board column, if any (`factory menu` is not needed: the columns are in `.factory/factory.yaml`).

Before writing:
- Run `factory step list --json`. If a similar generic or local step exists, show it with `factory step show <id>` and propose to reuse or update it.
- Choose a unique lowercase id: letters, digits, `-` or `_`, starting with a letter.

Then:
- Show the full step file: YAML frontmatter with `id, description, category, type, reads, writes, done_when, done_check, config, required, run_in, model, effort, requires, column, wait_external` (only the fields that apply), then the body. A composite step has a `steps` list and no body. A script step body is the script file name, and the script file goes next to the step file.
- Write the file only after the user approves.
- For a generic step, show the file and the message `Factory library: add step <id>`, and run `factory library commit "<message>" <path>` only after approval.

At the end:
- Run `factory pipeline list`. Ask if the new step should be added to some pipelines, and where.
- For each approved pipeline, edit its YAML file, run `factory pipeline check <id>`, and fix every error. For a generic pipeline, offer the library commit `Factory library: update pipeline <id>`.
```

- [ ] **Step 3: Write the test**

```python
from conftest import fake_calls, git
from factory import launch, repo
from factory.registry import Registry


def test_builtin_assistant_runs_in_main_repo(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    reg = Registry.load(ctx)
    assert reg.pipeline("new-step-assistant").level == "builtin"
    assert [e["id"] for e in reg.expand(reg.pipeline("new-step-assistant"))] == ["new-step"]
    task = launch.launch(ctx, "new-step-assistant", "Create merge request step", {})
    assert task["worktree"] is None
    call = fake_calls(inited.fdir)[-1]
    assert call["in_worktree"] is False
    assert call["args"].count("--add-dir") == 2 and str(inited.library) in call["args"]
    out = inited.factory("next", "--task", task["id"]).stdout
    assert "`factory step list --task" in out
```

- [ ] **Step 4: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 5: Commit milestone 3**

```bash
git add software-factory
git commit -m "milestone 3: authoring, step assistant"
```

---

# Milestone 4: Lifecycle and docs

### Task 27: Migration (`migrate.py`)

**Files:**
- Create: `software-factory/lib/factory/migrate.py`, `software-factory/migrations/.gitkeep`
- Modify: `software-factory/lib/factory/commands.py` (add `migrate`)
- Test: `software-factory/tests/test_migrate.py`

**Interfaces:**
- Consumes: `version`, `library.in_git`, `library.repo_root`, `events`, `state`.
- Produces:
  - `migrate.migrations_dir() -> Path` (env `FACTORY_MIGRATIONS_DIR`, default `PLUGIN_ROOT/migrations`)
  - `migrate.plan(ctx) -> dict` keys `current, repo {from, migrate}, library {path, from, migrate, in_git}`
  - `migrate.migrate(ctx, dry_run=False) -> dict` = plan plus `backups (list[str])`, `library_commit ({message, paths}|None)`
  - Migration script contract: `migrations/<n>-to-<n+1>.py` defines `migrate_repo(factory_dir: Path) -> None` and `migrate_library(library_dir: Path) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
import json
import shutil

import pytest
import yaml

from conftest import commit_all, git, make_task
from factory import repo

SCRIPT = '''
from pathlib import Path
def migrate_repo(factory_dir):
    (Path(factory_dir) / "migrated-repo.txt").write_text("ok")
def migrate_library(library_dir):
    (Path(library_dir) / "migrated-lib.txt").write_text("ok")
'''


@pytest.fixture
def v2(inited, work):
    mdir = work / "migrations"
    mdir.mkdir()
    (mdir / "1-to-2.py").write_text(SCRIPT)
    git("add", "-A", cwd=inited.library.parent)
    git("commit", "-m", "library", cwd=inited.library.parent)
    make_task(repo.load_ctx(cwd=inited.repo), tid="t1")
    env = {"FACTORY_DATA_VERSION": "2", "FACTORY_MIGRATIONS_DIR": str(mdir)}
    return inited, env


def test_older_refused_then_migrated(v2):
    inited, env = v2
    assert inited.factory.json("version", "check", env=env)["state"] == "older"
    r = inited.factory("tasks", env=env, check=False)
    assert r.returncode == 1 and "version" in r.stderr
    out = inited.factory.json("migrate", env=env)
    assert len(out["backups"]) == 1 and (inited.repo / out["backups"][0].split("/")[-1]).exists()
    assert yaml.safe_load((inited.fdir / "factory.yaml").read_text())["version"] == 2
    assert yaml.safe_load((inited.library / "factory.yaml").read_text())["version"] == 2
    assert (inited.fdir / "migrated-repo.txt").exists() and (inited.library / "migrated-lib.txt").exists()
    assert out["library_commit"]["message"] == "Factory library: migrate to version 2"
    log = (inited.fdir / "tasks" / "t1" / "events.jsonl").read_text().splitlines()
    assert json.loads(log[-1])["type"] == "migrated"
    assert inited.factory("tasks", env=env).returncode == 0


def test_dirty_library_refused(v2):
    inited, env = v2
    (inited.library / "steps" / "dirty.md").write_text("x")
    r = inited.factory("migrate", env=env, check=False)
    assert r.returncode == 1 and "uncommitted" in r.stderr


def test_shared_library_migrated_once(v2, origin_repo, work):
    inited, env = v2
    inited.factory("migrate", env=env)
    (inited.library / "migrated-lib.txt").unlink()
    inited.fdir.joinpath("factory.yaml").write_text(
        yaml.safe_dump({**yaml.safe_load((inited.fdir / "factory.yaml").read_text()), "version": 1})
    )
    out = inited.factory.json("migrate", env=env)
    assert out["library"]["migrate"] is False
    assert not (inited.library / "migrated-lib.txt").exists()


def test_newer_refused(v2):
    inited, env = v2
    data = yaml.safe_load((inited.fdir / "factory.yaml").read_text())
    (inited.fdir / "factory.yaml").write_text(yaml.safe_dump({**data, "version": 3}))
    assert inited.factory.json("version", "check", env=env)["state"] == "newer"
    r = inited.factory("migrate", env=env, check=False)
    assert r.returncode == 1 and "update the factory" in r.stderr
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_migrate.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement `migrate.py`**

```python
import importlib.util
import os
import shutil
from datetime import datetime
from pathlib import Path

from . import events, fsio, library, repo, state, version
from .errors import FactoryError


def migrations_dir():
    return Path(os.environ.get("FACTORY_MIGRATIONS_DIR") or repo.PLUGIN_ROOT / "migrations")


def load_script(from_version):
    path = migrations_dir() / f"{from_version}-to-{from_version + 1}.py"
    if not path.exists():
        raise FactoryError(f"The migration script {path.name} is missing.")
    spec = importlib.util.spec_from_file_location(f"factory_migration_{from_version}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def plan(ctx):
    current = version.DATA_VERSION
    rv = version.repo_version(ctx)
    lib = ctx.library()
    lv = version.library_version(lib)
    if (rv or 0) > current or (lv or 0) > current:
        raise FactoryError("The data is newer than this factory. Update the factory plugin.")
    return {
        "current": current,
        "repo": {"from": rv, "migrate": rv is not None and rv < current},
        "library": {"path": str(lib) if lib else None, "from": lv, "migrate": lv is not None and lv < current,
                    "in_git": library.in_git(lib)},
    }


def require_clean_library(lib):
    top = library.repo_root(lib)
    status = repo.git(["status", "--porcelain", "--", str(lib)], top).stdout.strip()
    if status:
        raise FactoryError("The library has uncommitted changes. Commit or stash them, then migrate again.\n" + status)


def bump(path, new_version):
    fsio.update_yaml(path, lambda d: d.__setitem__("version", new_version))


def migrate(ctx, dry_run=False):
    p = plan(ctx)
    p["backups"], p["library_commit"] = [], None
    if dry_run:
        return p
    lib = ctx.library()
    if p["library"]["migrate"]:
        if p["library"]["in_git"]:
            require_clean_library(lib)
        else:
            target = lib.with_name(f"{lib.name}.backup-{stamp()}")
            shutil.copytree(lib, target)
            p["backups"].append(str(target))
    if p["repo"]["migrate"]:
        target = ctx.main / f".factory.backup-{stamp()}"
        shutil.copytree(ctx.fdir, target)
        p["backups"].append(str(target))
        for v in range(p["repo"]["from"], p["current"]):
            load_script(v).migrate_repo(ctx.fdir)
            bump(ctx.fdir / "factory.yaml", v + 1)
            for task in state.list_tasks(ctx):
                events.log(ctx, task["id"], "migrated", None, from_version=v, to_version=v + 1)
    if p["library"]["migrate"]:
        for v in range(p["library"]["from"], p["current"]):
            load_script(v).migrate_library(lib)
            bump(lib / "factory.yaml", v + 1)
        if p["library"]["in_git"]:
            p["library_commit"] = {"message": f"Factory library: migrate to version {p['current']}", "paths": [str(lib)]}
    return p
```

`migrations/.gitkeep` is an empty file.

- [ ] **Step 4: Add `migrate`**

```python
    p = sub.add_parser("migrate", parents=[common]); p.add_argument("--dry-run", action="store_true")
```

```python
@cli.command("migrate")
def migrate_cmd(args):
    from . import migrate, repo
    result = migrate.migrate(repo.load_ctx(task_opt=args.task), args.dry_run)
    if args.json:
        cli.emit(result, True)
        return
    print(f"Repository data: version {result['repo']['from']} -> {result['current']}" if result["repo"]["migrate"] else "Repository data: up to date.")
    print(f"Library: version {result['library']['from']} -> {result['current']}" if result["library"]["migrate"] else "Library: up to date.")
    for b in result["backups"]:
        print(f"Backup: {b}")
```

- [ ] **Step 5: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add software-factory
git commit -m "migrate: independent repo and library migration with backups"
```

### Task 28: README (without the dashboard parts) and doc checks

**Files:**
- Create: `software-factory/README.md`
- Test: `software-factory/tests/test_docs.py`

- [ ] **Step 1: Write `README.md`**

Write it in simple English with short sentences. Required sections and content:

1. **What it does** (3 to 5 lines): one task = one worktree + one Herdr tab + one named Claude session; tasks follow pipelines of reusable steps; a dashboard shows them.
2. **Concepts**, one line each: task, pipeline, step, step types (`prompt`, `skill`, `script`, `composite`), levels (local `.factory/`, generic `<library>/`, built-in), catalog, artifacts.
3. **Install and prerequisites**:
   - `uv` (`brew install uv`), Herdr (https://herdr.dev), git, Claude Code. Optional: `gh` or `glab` for forge steps.
   - Plugin: in Claude Code, run `/plugin marketplace add <path to the SoftwareFactory folder>`, then `/plugin install software-factory@software-factory`.
   - Start: open a Herdr pane in the main repository, start `claude`, and run `/software-factory:software-factory`.
   - Bash allowlist. List these commands so the user can add them:
     - git: `git status`, `git diff`, `git log`, `git fetch`, `git switch`, `git add`, `git commit`, `git push`, `git rebase`, `git worktree`, `git branch`, `git rev-parse`.
     - factory: every `factory` command of the reference (or `factory *`).
     - Herdr adapter: `herdr worktree open`, `herdr tab create`, `herdr tab close`, `herdr workspace close`, `herdr agent start`, `herdr agent prompt`, `herdr agent get`, `herdr agent read`, `herdr agent focus`, `herdr agent wait`, `herdr agent send-keys`, `herdr notification show`.
4. **Tutorial**, each step with exact actions and the expected result:
   1. Init the factory in a repository and install the starter pack (menu "Init the factory", library path, starter pack yes). Expected: `.factory/` exists, `quick-task` is listed by `factory pipeline list`.
   2. Run `quick-task` on a small change: menu "Launch a new pipeline", pick `quick-task`, give a description, confirm the dry run. Follow it in the new Herdr workspace. Use "Show tasks": the task is `awaiting_approval` at `user-validation`. Approve in the task session. Expected: `git log -1` in the worktree shows the commit, and the task is `finished`.
   3. Exit with "pause all", start the factory again, accept "resume all". Expected: the task session opens with the same conversation and continues.
   4. "Create a new step": answer the assistant's questions. Expected: the step file is in `<library>/steps/` or `.factory/steps/`.
   5. "Create or edit a pipeline": copy `quick-task`, drag the new step in, save, then launch the new pipeline. Expected: the task runs the new step.
   6. (Added in Task 31.)
5. **Reference**:
   - Menu actions: the list from the skill, one line each.
   - `factory` commands: every command, with its arguments, one line each. Use the exact syntax of `factory <cmd> --help`.
   - Step manifest fields: `id, description, category, type, reads, writes, done_when, done_check, config, required, run_in, model, effort, requires, column, wait_external, steps`.
   - Pipeline fields: `id, description, inputs, steps (id, with, model, effort, column), claude (model, effort), start_column`.
   - `.factory/factory.yaml` fields: `version, library, terminal, columns, poll_minutes, ticket_url`.
   - (Dashboard reference added in Task 31.)
6. **Troubleshooting**:
   - Terminal check failed: start Claude inside a Herdr pane (`HERDR_ENV=1`), install `herdr`.
   - Data version mismatch: older data, start the orchestrator to migrate; newer data, update the plugin.
   - Session gone: menu "Resume a task", or `factory resume <id>`.
   - The folder trust dialog, with the fix chosen in Task 9.

- [ ] **Step 2: Write the doc checks**

```python
import re

from conftest import SF
from factory import cli, commands


def command_names():
    parser, sub, common = cli.build_parser()
    commands.register(sub, common)
    names = set()
    for name, p in sub.choices.items():
        names.add(name)
        for action in p._actions:
            if getattr(action, "choices", None) and isinstance(action.choices, dict):
                for child in action.choices:
                    names.add(f"{name} {child}")
    return names


def used_commands(text):
    found = set()
    for m in re.finditer(r"\bfactory ([a-z][a-z-]*)(?: ([a-z][a-z-]*))?", text):
        found.add((m.group(1), m.group(2)))
    return found


def check(text, names):
    missing = []
    for first, second in used_commands(text):
        if first not in names:
            missing.append(first)
        elif second and any(n.startswith(first + " ") for n in names) and f"{first} {second}" not in names:
            missing.append(f"{first} {second}")
    return missing


def test_readme_commands_exist():
    assert check((SF / "README.md").read_text(), command_names()) == []


def test_skill_and_builtin_commands_exist():
    names = command_names()
    texts = [(SF / "skills" / "software-factory" / "SKILL.md").read_text()]
    texts += [p.read_text() for p in (SF / "builtin" / "steps").glob("*.md")]
    texts += [p.read_text() for p in (SF / "catalog" / "steps").glob("*.md")]
    for text in texts:
        assert check(text, names) == []


def test_readme_sections():
    text = (SF / "README.md").read_text()
    for heading in ("Concepts", "Install", "Tutorial", "Reference", "Troubleshooting"):
        assert heading in text
```

- [ ] **Step 3: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass. A failure names a command written in the docs that the CLI does not have: fix the doc or the CLI.

- [ ] **Step 4: Commit milestone 4**

```bash
git add software-factory
git commit -m "milestone 4: migration, README"
```

---

# Milestone 5: Dashboard

### Task 29: Dashboard API routes

**Files:**
- Modify: `software-factory/lib/factory/api.py`
- Test: `software-factory/tests/test_dashboard_api.py`

**Interfaces:**
- Consumes: `board.task_rows`, `state.artifact_path`, `session.*`, `engine.approve/request_changes/external_done/open_ide`, `launch.plan_launch/launch`, `delete.clean_report/plan_delete/delete`, `backlog.*`, `config.set_value`, `Server.start_job`.
- Produces routes (all JSON):
  - `GET /api/tasks`
  - `GET /api/tasks/<id>/artifacts/<name>` -> `{name, text}`
  - `POST /api/tasks/<id>/focus`, `/send-prompt {text, wait}`, `/approve`, `/request-changes {text}`, `/external-done`, `/pause {wait}` (returns `{job}` when `wait`), `/resume`, `/open-ide`
  - `POST /api/launch/dry-run` and `POST /api/launch` with `{pipeline, description, inputs, id, from_backlog}`
  - `GET /api/clean`, `POST /api/delete/dry-run {id}`, `POST /api/delete {id, confirm_unpushed}`
  - `GET /api/backlog`, `POST /api/backlog/add {title, summary, pipeline}`, `/remove {id}`, `/move {id, to}`
  - `POST /api/config/set {step, key, value}`

- [ ] **Step 1: Write the failing tests**

```python
import time

import pytest

from conftest import events, fake_calls, make_task, task_json, write_pipeline, write_step
from factory import repo
from serverutil import info, request


@pytest.fixture
def dash(inited):
    write_step(inited.fdir, "w", {"column": "Plan"})
    write_pipeline(inited.fdir, {"id": "p", "steps": ["w", "user-validation"]})
    inited.factory("dashboard")
    yield inited, info(inited.fdir)
    inited.factory("server", "stop", check=False)


def test_launch_dry_run_then_launch(dash):
    inited, i = dash
    body = {"pipeline": "p", "description": "From dashboard", "inputs": {}}
    status, rep = request(i, "POST", "/api/launch/dry-run", body)
    assert status == 200 and rep["task_id"] == "from-dashboard" and rep["ok"]
    assert not (inited.fdir / "tasks" / "from-dashboard").exists()
    status, task = request(i, "POST", "/api/launch", body)
    assert task["id"] == "from-dashboard"
    status, rows = request(i, "GET", "/api/tasks")
    row = rows[0]
    assert row["id"] == "from-dashboard" and row["status"] == "active" and row["session_state"] == "idle" and row["column"] == "Discovery"


def test_actions_call_cli_functions(dash):
    inited, i = dash
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="t1", terminal_handle={"agent": "t1"})
    assert request(i, "POST", "/api/tasks/t1/focus", {})[0] == 200
    assert request(i, "POST", "/api/tasks/t1/send-prompt", {"text": "hi"})[0] == 200
    ops = [c["op"] for c in fake_calls(inited.fdir)]
    assert ops[-2:] == ["focus", "send_prompt"]
    assert events(inited.fdir, "t1")[-1]["type"] == "prompt_sent"
    status, job = request(i, "POST", "/api/tasks/t1/pause", {"wait": True})
    for _ in range(50):
        state = request(i, "GET", f"/api/jobs/{job['job']}")[1]
        if state["status"] != "running":
            break
        time.sleep(0.1)
    assert state["status"] == "done"
    assert [c["op"] for c in fake_calls(inited.fdir)][-2:] == ["wait_idle", "close"]
    assert request(i, "POST", "/api/tasks/t1/resume", {})[0] == 200
    assert task_json(inited.fdir, "t1")["status"] == "active"


def test_approve_from_card(dash):
    inited, i = dash
    request(i, "POST", "/api/launch", {"pipeline": "p", "description": "Card", "inputs": {}})
    inited.factory("next", "--task", "card", cwd=inited.worktrees / "card")
    inited.factory("done", "--task", "card", cwd=inited.worktrees / "card")
    inited.factory("next", "--task", "card", cwd=inited.worktrees / "card")
    rows = request(i, "GET", "/api/tasks")[1]
    assert rows[0]["status"] == "awaiting_approval" and rows[0]["approval"]["target"] == "worktree"
    assert request(i, "POST", "/api/tasks/card/approve", {})[0] == 200
    assert fake_calls(inited.fdir)[-1]["text"].startswith("The user approved.")


def test_backlog_routes(dash):
    inited, i = dash
    for title in ("A", "B", "C"):
        request(i, "POST", "/api/backlog/add", {"title": title, "summary": "", "pipeline": None})
    request(i, "POST", "/api/backlog/move", {"id": "b3", "to": 1})
    assert [e["title"] for e in request(i, "GET", "/api/backlog")[1]] == ["C", "A", "B"]
    request(i, "POST", "/api/backlog/remove", {"id": "b1"})
    assert [e["id"] for e in request(i, "GET", "/api/backlog")[1]] == ["b3", "b2"]


def test_artifact_and_errors(dash):
    inited, i = dash
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, tid="t1")
    (inited.fdir / "tasks" / "t1" / "artifacts" / "spec.md").write_text("# Spec")
    assert request(i, "GET", "/api/tasks/t1/artifacts/spec.md")[1]["text"] == "# Spec"
    assert request(i, "GET", "/api/tasks/t1/artifacts/..%2Fx")[0] in (400, 404)
    status, err = request(i, "POST", "/api/tasks/t1/approve", {})
    assert status == 400 and "approval" in err["error"]


def test_clean_and_delete_routes(dash):
    inited, i = dash
    request(i, "POST", "/api/launch", {"pipeline": "p", "description": "Del", "inputs": {}})
    from factory import state
    state.update(repo.load_ctx(cwd=inited.repo), "del", lambda t: state.set_status(t, "finished"))
    rows = request(i, "GET", "/api/clean")[1]
    assert rows[0]["id"] == "del" and rows[0]["merged"]
    assert request(i, "POST", "/api/delete/dry-run", {"id": "del"})[1]["needs_confirm"] is False
    assert request(i, "POST", "/api/delete", {"id": "del", "confirm_unpushed": False})[0] == 200
    assert (inited.fdir / "tasks" / "archive" / "del").exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_dashboard_api.py -q`
Expected: FAIL (404 on the new routes).

- [ ] **Step 3: Add the routes to `api.py`**

```python
TASK = "([a-z][a-z0-9_-]{0,31})"


@route("GET", "/api/tasks")
def tasks(server, query, body):
    from . import board
    return board.task_rows(server.ctx)


@route("GET", f"/api/tasks/{TASK}/artifacts/([^/]+)")
def artifact(server, tid, name, query, body):
    from . import state
    path = state.artifact_path(server.ctx, tid, name)
    if not path.is_file():
        raise NotFound(name)
    return {"name": name, "text": path.read_text(errors="replace")}


@route("POST", f"/api/tasks/{TASK}/focus")
def focus(server, tid, query, body):
    from . import session
    session.focus(server.ctx, tid)
    return {"ok": True}


@route("POST", f"/api/tasks/{TASK}/send-prompt")
def send_prompt(server, tid, query, body):
    from . import session
    if body.get("wait"):
        return {"job": server.start_job(lambda: session.send_prompt(server.ctx, tid, body["text"], True))}
    session.send_prompt(server.ctx, tid, body["text"])
    return {"ok": True}


@route("POST", f"/api/tasks/{TASK}/approve")
def approve(server, tid, query, body):
    from . import engine
    return {"message": engine.approve(server.ctx, tid, send=True)}


@route("POST", f"/api/tasks/{TASK}/request-changes")
def request_changes(server, tid, query, body):
    from . import engine
    return {"message": engine.request_changes(server.ctx, tid, body["text"], send=True)}


@route("POST", f"/api/tasks/{TASK}/external-done")
def external_done(server, tid, query, body):
    from . import engine
    engine.external_done(server.ctx, tid)
    return {"ok": True}


@route("POST", f"/api/tasks/{TASK}/pause")
def pause(server, tid, query, body):
    from . import session
    if body.get("wait"):
        return {"job": server.start_job(lambda: session.pause(server.ctx, tid, True))}
    session.pause(server.ctx, tid)
    return {"ok": True}


@route("POST", f"/api/tasks/{TASK}/resume")
def resume(server, tid, query, body):
    from . import session
    session.resume(server.ctx, tid)
    return {"ok": True}


@route("POST", f"/api/tasks/{TASK}/open-ide")
def open_ide(server, tid, query, body):
    from . import engine
    return {"argv": engine.open_ide(server.ctx, tid)}


def launch_args(body):
    return (body["pipeline"], body.get("description", ""), body.get("inputs") or {}, body.get("id") or None, body.get("from_backlog") or None)


@route("POST", "/api/launch/dry-run")
def launch_dry_run(server, query, body):
    from . import launch
    return launch.plan_launch(server.ctx, *launch_args(body))


@route("POST", "/api/launch")
def launch_task(server, query, body):
    from . import launch
    return launch.launch(server.ctx, *launch_args(body))


@route("GET", "/api/clean")
def clean(server, query, body):
    from . import delete
    return delete.clean_report(server.ctx)


@route("POST", "/api/delete/dry-run")
def delete_dry_run(server, query, body):
    from . import delete
    return delete.plan_delete(server.ctx, body["id"])


@route("POST", "/api/delete")
def delete_task(server, query, body):
    from . import delete
    return delete.delete(server.ctx, body["id"], bool(body.get("confirm_unpushed")))


@route("GET", "/api/backlog")
def backlog_list(server, query, body):
    from . import backlog
    return [e.to_dict() for e in backlog.list_entries(server.ctx)]


@route("POST", "/api/backlog/add")
def backlog_add(server, query, body):
    from . import backlog
    return backlog.add(server.ctx, body["title"], body.get("summary", ""), body.get("pipeline")).to_dict()


@route("POST", "/api/backlog/remove")
def backlog_remove(server, query, body):
    from . import backlog
    return backlog.remove(server.ctx, body["id"]).to_dict()


@route("POST", "/api/backlog/move")
def backlog_move(server, query, body):
    from . import backlog
    return [e.to_dict() for e in backlog.move(server.ctx, body["id"], body["to"])]


@route("POST", "/api/config/set")
def config_set(server, query, body):
    from . import config
    config.set_value(server.ctx, body["step"], body["key"], body["value"])
    return {"ok": True}
```

- [ ] **Step 4: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add software-factory
git commit -m "dashboard: API routes"
```

### Task 30: Dashboard page (`dashboard.html`)

**Files:**
- Replace: `software-factory/lib/factory/web/dashboard.html`
- Create: `verification/software-factory/dashboard-manual-check.md`

Plain HTML, CSS and JavaScript, no external library, no comments. Reuse the `api()`, `el()`, `showError()` helpers and the color tokens of `editor.html` (copy them; the two pages are separate files). Use `textContent` for every data value.

Required behavior (each item maps to a prompt bullet in "Dashboard"):

1. Two views, "Tasks" and "Backlog", switched by tabs. Refresh every 5 seconds (`setInterval`), without losing open forms (skip the redraw while a form or dialog is open).
2. Banner: when `GET /api/info` returns `adapter.ok == false`, show a banner with `adapter.message`, and disable the buttons that need the adapter (Focus, Send prompt, Pause, Resume, Launch).
3. Tasks view:
   - One column per `info.columns`, plus "Done" last. Finished tasks go to "Done".
   - Column hide/show toggles. Save the hidden list in `localStorage` (key `factory.hiddenColumns`, wrapped in try/catch).
   - Cards are not draggable.
   - A card shows: the ticket key as a link to `ticket_url` with `{key}` replaced (when both are set, `target="_blank" rel="noopener"`), the description, the pipeline, the step, the status as text plus an icon (`active` ▶, `blocked` ⛔, `awaiting_approval` ✋, `waiting_external` ⏳, `paused` ⏸, `finished` ✓), and the time in status ("blocked for 2 h", computed from `status_since`).
   - Card background by status: `active` green, `blocked` red, `awaiting_approval` amber, `waiting_external` blue, `paused` grey, finished neutral. Use light tints in light mode and dark tints in dark mode.
   - A clear "Session gone" marker when `session_state == "gone"` and the task is not paused or finished.
   - The artifact list. Clicking an artifact opens a dialog with its text in a `<pre>` (`GET /api/tasks/<id>/artifacts/<name>`).
   - Buttons, only when they apply:
     - Focus (live session, adapter supports `focus`).
     - Show MR, when `mr_url` is set (`target="_blank" rel="noopener"`).
     - Approve and Request changes, when `awaiting_approval`. Show what to validate: a link that opens the artifact dialog for `target: artifact`, or an "Open in IDE" button (`POST /open-ide`) for `target: worktree`. Request changes asks for the text in a form.
     - Mark done, when `waiting_external` and `wait_has_check` is false.
     - Send prompt: a form with a text area. If `session_state == "working"`, ask "Wait until idle" or "Send now".
     - Pause: ask "Wait until idle" or "Stop now". Waiting uses the job route and shows "Pausing..." until the job ends.
     - Resume, when `paused` or the session is gone.
   - "Launch" button: a form with the pipeline (`GET /api/pipelines`), the description and one field per pipeline input (`GET /api/pipelines/<id>`, `data.inputs`). "Check" calls `/api/launch/dry-run` and shows the task id, worktree, branch case, missing inputs, missing config (with a field per key that saves with `/api/config/set`) and errors. "Launch" is enabled only after a dry run with `ok == true`, and calls `/api/launch`.
   - The Done column has a "Clean" button: `GET /api/clean`, a list with check boxes (merged tasks checked), a dry run per selected task (`/api/delete/dry-run`) showing uncommitted changes and unpushed commits, and a "Delete selected" button that calls `/api/delete` (with `confirm_unpushed` only for the tasks where the user ticked "I accept losing these changes").
4. Backlog view:
   - One card per entry in order: title, summary, pipeline.
   - Drag a card to change its position (native drag and drop), then `POST /api/backlog/move` with the new 1-based position.
   - "Add" opens a form: title, summary, optional pipeline.
   - "Delete" asks for confirmation in an in-page dialog (no `confirm()`), then removes the entry.
   - "Start" opens the Launch form filled from the entry (`description` = title, `from_backlog` = id, pipeline = entry pipeline).
5. Every button shows API errors in the error bar.

- [ ] **Step 1: Write `dashboard.html`** following the list above. Keep it under 700 lines.

- [ ] **Step 2: Manual check**

In a test repository under `verification/software-factory/work/`, with the fake adapter (`terminal: fake`), run `factory dashboard`, open the URL, and check items 1 to 5 by hand: launch a task, move it with `factory next`/`done`, approve from the card, mark a QA wait done, reorder the backlog, start a task from the backlog, clean a finished task. Then switch `terminal` to `herdr` and check the banner by starting the server outside Herdr (`HERDR_ENV=0 factory dashboard`). Write pass/fail per item in `verification/software-factory/dashboard-manual-check.md`.

- [ ] **Step 3: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add software-factory verification/software-factory/dashboard-manual-check.md
git commit -m "dashboard: tasks board and backlog page"
```

### Task 31: README dashboard parts

**Files:**
- Modify: `software-factory/README.md`

- [ ] **Step 1: Add tutorial step 6**

"Open the dashboard, follow a task across the columns, and approve a `user-validation` from a card": menu "Open dashboard"; launch `plan-and-build` or the pipeline from step 5; watch the card move from column to column as steps start; when the card turns amber (`awaiting_approval`), click Approve. Expected: the task session receives "The user approved. Run `factory done`." and the card moves on.

- [ ] **Step 2: Add the dashboard reference**

Views (Tasks, Backlog), card content, colors and icons, every card button and when it shows, the Launch form, the Clean dialog, the backlog actions, the banner when the terminal check fails, `ticket_url` in `.factory/factory.yaml`, and the security model (127.0.0.1 only, token in the URL, Host and Origin checks, stop after 30 minutes without requests).

- [ ] **Step 3: Run tests**

Run: `uv run --with pytest --with pyyaml pytest tests -q`
Expected: all pass (`test_docs.py` checks the new commands).

- [ ] **Step 4: Commit milestone 5**

```bash
git add software-factory
git commit -m "milestone 5: dashboard, README dashboard parts"
```

---

# Final verification

### Task 32: End-to-end test with Herdr and Claude (`tests/e2e_herdr.py`)

**Files:**
- Create: `software-factory/tests/e2e_herdr.py`

This script runs real Claude sessions in Herdr. It creates only the Herdr objects that `factory launch` and `factory resume` create for its own test task, reads their ids from `task.json`, and closes only those ids.

- [ ] **Step 1: Write the script**

Apply the trust decision from Task 9: when the decision was "worktree_root under a trusted folder", set `WORKTREE_ROOT` below to that folder plus a unique subfolder. Otherwise keep it under `VERIF/work`.

```python
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

SF = Path(__file__).resolve().parents[1]
VERIF = SF.parent / "verification" / "software-factory"
BIN = SF / "bin" / "factory"
LINK = Path.home() / ".local" / "bin" / "factory"
RESULTS = VERIF / "e2e-results.json"
results = []
handles = []

STEP_ONE = "---\nid: e2e-one\ndescription: Write one.txt\ncategory: test\ntype: script\ndone_when: one.txt exists\ndone_check: test -f \"$(factory artifact path one.txt)\"\n---\n\ne2e-one.sh\n"
STEP_HOLD = "---\nid: e2e-hold\ndescription: Wait for the test\ncategory: test\ntype: prompt\ndone_when: The test marks it done.\nwait_external: true\n---\n\nRun `factory wait`. Then stop and wait for a message.\n"
STEP_TWO = "---\nid: e2e-two\ndescription: Write two.txt\ncategory: test\ntype: script\ndone_when: two.txt exists\ndone_check: test -f \"$(factory artifact path two.txt)\"\n---\n\ne2e-two.sh\n"
PIPELINE = "id: e2e\ndescription: End-to-end test pipeline\nsteps:\n  - e2e-one\n  - e2e-hold\n  - e2e-two\n"


def sh(args, cwd=None, check=True):
    r = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{args} failed: {r.stdout}{r.stderr}")
    return r


def record(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + (f": {detail}" if detail else ""), flush=True)


def task_json(fdir, tid, archived=False):
    base = fdir / "tasks" / ("archive" if archived else "") / tid
    return json.loads((base / "task.json").read_text())


def task_events(fdir, tid):
    p = fdir / "tasks" / tid / "events.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def agent_status(name):
    r = sh(["herdr", "agent", "get", name], check=False)
    if r.returncode != 0:
        return "gone"
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return "unknown"
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if "agent_status" in item:
                return item["agent_status"]
            stack += list(item.values())
        elif isinstance(item, list):
            stack += item
    return "unknown"


def wait_for(predicate, timeout, watch_agent=None, blocked_seen=None):
    end = time.time() + timeout
    while time.time() < end:
        if watch_agent and agent_status(watch_agent) == "blocked" and blocked_seen is not None:
            blocked_seen.append(time.time())
        if predicate():
            return True
        time.sleep(3)
    return False


def setup(root):
    origin, seed, repo, lib_root = root / "origin.git", root / "seed", root / "repo", root / "libroot"
    sh(["git", "init", "--bare", "-b", "main", origin])
    sh(["git", "clone", origin, seed])
    for d in (seed,):
        sh(["git", "config", "user.name", "E2E"], cwd=d)
        sh(["git", "config", "user.email", "e2e@example.com"], cwd=d)
    (seed / "README.md").write_text("e2e\n")
    sh(["git", "add", "-A"], cwd=seed)
    sh(["git", "commit", "-m", "init"], cwd=seed)
    sh(["git", "push", "origin", "HEAD:main"], cwd=seed)
    sh(["git", "clone", origin, repo])
    sh(["git", "config", "user.name", "E2E"], cwd=repo)
    sh(["git", "config", "user.email", "e2e@example.com"], cwd=repo)
    lib_root.mkdir()
    sh(["git", "init", "-b", "main"], cwd=lib_root)
    return repo, lib_root / "factory-library"


def write_pipeline(fdir):
    steps = fdir / "steps"
    (steps / "e2e-one.md").write_text(STEP_ONE)
    (steps / "e2e-hold.md").write_text(STEP_HOLD)
    (steps / "e2e-two.md").write_text(STEP_TWO)
    (steps / "e2e-one.sh").write_text('echo one > "$(factory artifact path one.txt)"\n')
    (steps / "e2e-two.sh").write_text('echo two > "$(factory artifact path two.txt)"\n')
    (fdir / "pipelines" / "e2e.yaml").write_text(PIPELINE)


def close_created():
    for h in handles:
        if h.get("workspace"):
            sh(["herdr", "workspace", "close", h["workspace"]], check=False)
        elif h.get("tab"):
            sh(["herdr", "tab", "close", h["tab"]], check=False)


def run(root):
    repo, lib = setup(root)
    worktree_root = root / "worktrees"
    sh([BIN, "init", "--library", lib, "--create-library"], cwd=repo)
    sh(["factory", "config", "set", "create-worktree", "worktree_root", worktree_root], cwd=repo)
    fdir = repo / ".factory"
    write_pipeline(fdir)

    task = json.loads(sh(["factory", "launch", "e2e", "--description", "E2E task", "--json"], cwd=repo).stdout)
    tid, wt = task["id"], Path(task["worktree"])
    handles.append(task["terminal_handle"])
    head = sh(["git", "rev-parse", "HEAD"], cwd=wt).stdout.strip()
    origin_main = sh(["git", "rev-parse", "origin/main"], cwd=repo).stdout.strip()
    record("launch fetches origin and creates the worktree from origin/main", wt.exists() and head == origin_main)
    record("Claude runs in Herdr with the task id as its name", agent_status(tid) != "gone")

    blocked = []
    started = wait_for(lambda: any(e["type"] == "step_started" and e["step"] == "e2e-one" for e in task_events(fdir, tid)), 180, tid, blocked)
    record("Claude receives the first prompt and runs factory next", started)
    waiting = wait_for(lambda: task_json(fdir, tid)["status"] == "waiting_external", 300, tid, blocked)
    record("first script step runs with factory next and factory done", waiting and (fdir / "tasks" / tid / "artifacts" / "one.txt").exists())

    sh(["factory", "pause", tid], cwd=repo)
    gone = wait_for(lambda: agent_status(tid) == "gone", 30)
    record("pause closes the task terminal", gone and task_json(fdir, tid)["status"] == "paused")

    sh(["factory", "resume", tid], cwd=repo)
    resumed = task_json(fdir, tid)
    handles.append(resumed["terminal_handle"])
    record("resume reopens the same Claude session", resumed["session_id"] == task["session_id"] and agent_status(tid) != "gone"
           and resumed["status"] == "waiting_external")

    sh(["factory", "external-done", tid], cwd=repo)
    finished = wait_for(lambda: task_json(fdir, tid)["status"] == "finished", 300, tid, blocked)
    record("the resumed session continues the pipeline to the end", finished and (fdir / "tasks" / tid / "artifacts" / "two.txt").exists())
    record("the session never waits on a permission prompt", not blocked, f"blocked seen {len(blocked)} times" if blocked else "")

    (wt / "uncommitted.txt").write_text("x")
    refused = sh(["factory", "delete", tid], cwd=repo, check=False)
    record("delete asks for approval when there are uncommitted changes", refused.returncode == 1 and "--confirm-unpushed" in refused.stderr)
    sh(["factory", "delete", tid, "--confirm-unpushed"], cwd=repo)
    archived = (fdir / "tasks" / "archive" / tid / "task.json").exists()
    record("delete closes the terminal, removes the worktree and archives the task",
           agent_status(tid) == "gone" and not wt.exists() and archived)


def main():
    if os.environ.get("HERDR_ENV") != "1":
        print("Run this script inside a Herdr pane.")
        return 2
    if LINK.exists() and not LINK.is_symlink():
        print(f"{LINK} exists and is not a link. Stop.")
        return 2
    previous = os.readlink(LINK) if LINK.is_symlink() else None
    root = VERIF / "work" / f"e2e-{uuid.uuid4().hex[:6]}"
    root.mkdir(parents=True)
    try:
        run(root)
    except Exception as e:
        record("e2e run completed without error", False, str(e))
    finally:
        close_created()
        if previous is not None:
            LINK.unlink(missing_ok=True)
            LINK.symlink_to(previous)
        elif LINK.is_symlink():
            LINK.unlink()
        shutil.rmtree(root, ignore_errors=True)
        RESULTS.write_text(json.dumps(results, indent=2) + "\n")
    return 0 if results and all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
```

`factory init` (called by the script, without `FACTORY_LINK_DIR`) creates `~/.local/bin/factory`. The `finally` block restores the previous link, or removes the new one.

- [ ] **Step 2: Run it**

Run (inside the Herdr pane of this session): `cd software-factory && uv run --with pyyaml python tests/e2e_herdr.py`
Expected: every line `PASS`, exit code 0. On a `FAIL`, fix the cause and run again. Do not change the checks to make them pass.

- [ ] **Step 3: Commit**

```bash
git add software-factory/tests/e2e_herdr.py verification/software-factory/e2e-results.json
git commit -m "verification: end-to-end test with Herdr and Claude"
```

### Task 33: Verification report and Definition Of Done check

**Files:**
- Create: `software-factory/tests/report.py`
- Create: `verification/software-factory/report.md`, `verification/software-factory/dod-checklist.md`

- [ ] **Step 1: Write the report generator**

```python
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

SF = Path(__file__).resolve().parents[1]
VERIF = SF.parent / "verification" / "software-factory"
MILESTONES = {
    "1. Core": ["test_scaffold", "test_fsio", "test_repo_version", "test_registry", "test_pipeline_check", "test_config_state",
                "test_adapters", "test_engine", "test_builtin", "test_herdr_adapter", "test_launch", "test_delete",
                "test_init_menu", "test_skill"],
    "2. Task life": ["test_board", "test_session", "test_approval", "test_waiting", "test_goto", "test_clean", "test_backlog",
                     "test_event_log"],
    "3. Authoring": ["test_server", "test_editor_api", "test_catalog", "test_library", "test_step_assistant"],
    "4. Lifecycle and docs": ["test_migrate", "test_docs"],
    "5. Dashboard": ["test_dashboard_api"],
}


def cases(junit):
    out = []
    for case in ET.parse(junit).getroot().iter("testcase"):
        module = case.get("classname", "").split(".")[-1]
        failure = case.find("failure") if case.find("failure") is not None else case.find("error")
        skipped = case.find("skipped") is not None
        status = "FAIL" if failure is not None else "SKIP" if skipped else "PASS"
        out.append({"module": module, "name": case.get("name"), "status": status,
                    "message": (failure.get("message") or "")[:300] if failure is not None else ""})
    return out


def table(rows):
    lines = ["| Test | Result |", "|---|---|"]
    for r in rows:
        extra = f" ({r['message']})" if r["message"] else ""
        lines.append(f"| `{r['module']}::{r['name']}` | {r['status']}{extra} |")
    return lines


def main():
    rows = cases(VERIF / "junit.xml")
    e2e = json.loads((VERIF / "e2e-results.json").read_text()) if (VERIF / "e2e-results.json").exists() else []
    lines = [f"# Software factory verification report", "", f"Date: {datetime.now():%Y-%m-%d %H:%M}", ""]
    total = len(rows) + len(e2e)
    passed = sum(r["status"] == "PASS" for r in rows) + sum(r["ok"] for r in e2e)
    lines += [f"Total: {passed} of {total} checks pass.", ""]
    known = set()
    for title, modules in MILESTONES.items():
        known |= set(modules)
        lines += [f"## Milestone {title}", ""] + table([r for r in rows if r["module"] in modules]) + [""]
    other = [r for r in rows if r["module"] not in known]
    if other:
        lines += ["## Other tests", ""] + table(other) + [""]
    lines += ["## End-to-end (Herdr and Claude)", "", "| Check | Result |", "|---|---|"]
    lines += [f"| {r['name']} | {'PASS' if r['ok'] else 'FAIL'}{(' (' + r['detail'] + ')') if r['detail'] else ''} |" for r in e2e]
    if not e2e:
        lines.append("| e2e not run | FAIL |")
    (VERIF / "report.md").write_text("\n".join(lines) + "\n")
    return 0 if passed == total and e2e else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run everything**

```bash
cd software-factory
uv run --with pytest --with pyyaml pytest tests -q --junitxml ../verification/software-factory/junit.xml
uv run --with pyyaml python tests/e2e_herdr.py
uv run python tests/report.py
```

Expected: `report.md` says every check passes. If something fails, fix it, rerun the affected checks, and regenerate the report.

- [ ] **Step 3: Write `dod-checklist.md`**

Copy every bullet of the prompt's "Definition Of Done" (Workflow Complete, Runtime, General concept, Factory elements, Tasks, Backlog, Orchestrator, Init, Factory CLI, Terminal adapter, Versioning and migration, Rebuild, File organization, Documentation, Verification). For each bullet write: `PASS` or `FAIL`, and the evidence: a test name from `report.md`, an e2e check, a manual check file, or a file path. Bullets that only the orchestrator conversation covers (for example, the menu never uses AskUserQuestion) get the `SKILL.md` line as evidence. List remaining blockers at the end, or "None".

- [ ] **Step 4: Check the working directory rule**

Run: `git status --porcelain` and `git diff --stat <first commit of the build>..HEAD -- . ':!software-factory' ':!verification/software-factory' ':!plans' ':!specs' ':!.claude-plugin'`
Expected: no output from the second command. Also check that `verification/software-factory/work/` is empty or absent.

- [ ] **Step 5: Commit**

```bash
git add software-factory/tests/report.py verification/software-factory
git commit -m "verification: report and Definition Of Done checklist"
```

- [ ] **Step 6: Report to the user**

Send the totals from `report.md`, the FAIL lines if any, the blockers from `dod-checklist.md`, and the trust decision from Task 9.
