import json
import os
import shutil
import stat
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


@pytest.fixture(autouse=True)
def factory_home(tmp_path, monkeypatch):
    home = tmp_path / "factory-home"
    monkeypatch.setenv("FACTORY_HOME", str(home))
    # Never build or run the real notifier app in ~/Applications.
    monkeypatch.setenv("FACTORY_NOTIFIER_APP", str(tmp_path / "Applications" / "CAPTN Dashboard Notifier.app"))
    monkeypatch.setenv("FACTORY_DASHBOARD_APP", str(tmp_path / "Applications" / "CAPTN Dashboard.app"))
    monkeypatch.setenv("FACTORY_LSREGISTER", "")
    monkeypatch.setenv("FACTORY_NO_UPDATE_CHECK", "1")
    return home


@pytest.fixture
def work(request):
    d = WORK / f"{request.node.name[:40]}-{uuid.uuid4().hex[:6]}"
    d.mkdir(parents=True)
    yield d.resolve()
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def origin_repo(work):
    return make_repo(work)


def make_repo(work):
    work.mkdir(parents=True, exist_ok=True)
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


@pytest.fixture
def no_git(monkeypatch, tmp_path):
    bin_dir = tmp_path / "no-git-bin"
    bin_dir.mkdir()
    (bin_dir / "uv").symlink_to(shutil.which("uv"))
    (bin_dir / "python3").symlink_to(sys.executable)
    monkeypatch.setenv("PATH", str(bin_dir))
    return bin_dir


@pytest.fixture
def plain(work, factory_home, monkeypatch):
    from factory import init

    monkeypatch.setenv("FACTORY_TERMINAL", "fake")
    monkeypatch.setenv("FACTORY_NO_OPEN", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(work))
    path = work / "plain"
    path.mkdir()
    init.init(path)
    return path


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
def factory(work, origin_repo, factory_home):
    link_dir = work / "bin"
    env = {
        **os.environ,
        "FACTORY_LINK_DIR": str(link_dir),
        "FACTORY_HOME": str(factory_home),
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
    def __init__(self, repo, library, factory, work, home):
        self.repo = repo
        self.home = home
        self.library = library
        self.factory = factory
        self.work = work
        self.fdir = repo / ".factory"
        self.worktrees = work / "worktrees"


@pytest.fixture
def inited(factory, origin_repo, library_path, work, factory_home):
    factory("init", "--library", library_path, "--create-library")
    factory("config", "set", "create-worktree", "worktree_root", work / "worktrees")
    yield Inited(origin_repo, library_path, factory, work, factory_home)
    if (factory_home / "server.json").exists():
        factory("server", "stop", check=False)


def write_step(root, sid, manifest, body="Do the step.\n"):
    d = Path(root) / "steps"
    d.mkdir(parents=True, exist_ok=True)
    data = {"id": sid, "description": f"Step {sid}", "category": "test", "type": "ai", **manifest}
    (d / f"{sid}.md").write_text("---\n" + yaml.safe_dump(data, sort_keys=False) + "---\n\n" + body)
    return d / f"{sid}.md"


def write_pipeline(root, data):
    d = Path(root) / "pipelines"
    d.mkdir(parents=True, exist_ok=True)
    full = {"description": f"Pipeline {data['id']}", **data}
    full.setdefault("worktree", True)
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


def make_task(ctx, tid="t1", worktree=None, steps=None, **fields):
    from factory import state

    task = {
        "id": tid, "description": "d", "pipeline": "p",
        "steps": steps if steps is not None else [{"id": "s", "path": ["s"], "with": {}, "column": None, "model": None, "effort": None}],
        "position": 0, "started": None, "status": "active", "status_reason": None,
        "status_since": state.now(), "saved_status": None, "column": "Discovery",
        "worktree": worktree, "base_ref": "main", "session_id": "sid", "terminal_handle": None,
        "goto_counts": {}, "approval": None, "claude": {}, "state": {},
        "created_at": state.now(), "updated_at": state.now(),
        **fields,
    }
    state.create(ctx, task)
    return task


def task_from_pipeline(inited, pid, tid="t1", worktree=None, **fields):
    from factory import repo
    from factory.registry import Registry
    ctx = repo.load_ctx(cwd=inited.repo)
    reg = Registry.load(ctx)
    from factory import loops
    pipeline = reg.pipeline(pid)
    snapshot = reg.expand(pipeline)
    position = 1 if snapshot and snapshot[0]["id"] == "create-worktree" else 0
    fields.setdefault("loops", loops.snapshot(reg, pipeline))
    return make_task(ctx, tid=tid, worktree=worktree, steps=snapshot, position=position, pipeline=pid, **fields)


@pytest.fixture
def att(inited):
    from factory import repo
    ctx = repo.load_ctx(cwd=inited.repo)
    make_task(ctx, "t1", session_id="sid-1", terminal_handle={"agent": "t1"})
    return inited


def hook(inited, kind, payload, delay="60", stdin=None, cwd=None):
    text = stdin if stdin is not None else json.dumps(payload)
    return inited.factory("hook", kind, input=text, cwd=cwd, check=False, env={"FACTORY_ATTENTION_DELAY": delay})


def silent(r):
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""


FAKE_SWIFTC = """#!/bin/sh
echo "swiftc $*" >> "$FAKE_TOOLS_LOG"
[ -z "$FAKE_SWIFTC_STDERR" ] || echo "$FAKE_SWIFTC_STDERR" >&2
[ "${FAKE_SWIFTC_EXIT:-0}" = 0 ] || exit "$FAKE_SWIFTC_EXIT"
while [ "$1" != "-o" ]; do shift; done
cat > "$2" <<'APP'
#!/bin/sh
"$FAKE_PYTHON" -c 'import json,sys,os; open(os.environ["FAKE_APP_LOG"],"a").write(json.dumps(sys.argv[1:])+"\\n")' "$@"
exit "${FAKE_NOTIFY_EXIT:-0}"
APP
chmod +x "$2"
"""

FAKE_CODESIGN = """#!/bin/sh
echo "codesign $*" >> "$FAKE_TOOLS_LOG"
"""


@pytest.fixture
def tools(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, text in (("swiftc", FAKE_SWIFTC), ("codesign", FAKE_CODESIGN)):
        exe = bindir / name
        exe.write_text(text)
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    tools_log, app_log = tmp_path / "tools.log", tmp_path / "app.log"
    monkeypatch.setenv("PATH", f"{bindir}:/bin")
    monkeypatch.setenv("FAKE_PYTHON", sys.executable)
    monkeypatch.setenv("FAKE_TOOLS_LOG", str(tools_log))
    monkeypatch.setenv("FAKE_APP_LOG", str(app_log))

    def compiles():
        return sum(line.startswith("swiftc ") for line in tools_log.read_text().splitlines()) if tools_log.exists() else 0

    def sent():
        return [json.loads(line) for line in app_log.read_text().splitlines()] if app_log.exists() else []

    return compiles, sent
