import datetime
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SF = HERE.parents[1] / "software-factory"
BIN = SF / "bin" / "factory"
CLAUDE = os.environ.get("CLAUDE_BIN") or shutil.which("claude")
PROMPT = "Ask me which color I prefer, in plain text. Do not use any tool. Then stop."
REPORT = HERE / "real-attention-check.md"


def run(args, cwd, env, timeout=180, check=True):
    r = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"{args} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
    return r


def git(*args, cwd, env):
    return run(["git", *args], cwd, env).stdout.strip()


def write_files(fdir):
    (fdir / "steps").mkdir(parents=True, exist_ok=True)
    (fdir / "pipelines").mkdir(parents=True, exist_ok=True)
    step = {"id": "work", "description": "Step work", "category": "test", "type": "ai"}
    (fdir / "steps" / "work.md").write_text("---\n" + yaml.safe_dump(step, sort_keys=False) + "---\n\nDo the step.\n")
    pipe = {"id": "plain", "description": "Pipeline plain", "steps": ["work"]}
    (fdir / "pipelines" / "plain.yaml").write_text(yaml.safe_dump(pipe, sort_keys=False))


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def read_events(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def check(work):
    link_dir = work / "bin"
    link_dir.mkdir()
    (link_dir / "factory").symlink_to(BIN)
    env = {
        **os.environ,
        "FACTORY_LINK_DIR": str(link_dir),
        "FACTORY_TERMINAL": "fake",
        "FACTORY_NO_OPEN": "1",
        "FACTORY_CLAUDE_HOME": str(work / "claude-home"),
        "FACTORY_ATTENTION_DELAY": "2",
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "PATH": f"{link_dir}{os.pathsep}{os.environ['PATH']}",
    }
    env.pop("FACTORY_TASK", None)
    origin = work / "origin.git"
    git("init", "--bare", "-b", "main", str(origin), cwd=work, env=env)
    seed = work / "seed"
    git("clone", str(origin), str(seed), cwd=work, env=env)
    (seed / "README.md").write_text("test\n")
    git("add", "-A", cwd=seed, env=env)
    git("commit", "-m", "init", cwd=seed, env=env)
    git("push", "origin", "HEAD:main", cwd=seed, env=env)
    repo = work / "repo"
    git("clone", str(origin), str(repo), cwd=work, env=env)
    libroot = work / "libroot"
    libroot.mkdir()
    git("init", "-b", "main", cwd=libroot, env=env)
    (libroot / "other.txt").write_text("x\n")
    git("add", "-A", cwd=libroot, env=env)
    git("commit", "-m", "init", cwd=libroot, env=env)
    lib = libroot / "factory-library"

    def factory(*args):
        return run([sys.executable, str(BIN), *[str(a) for a in args]], repo, env)

    commands = []
    factory("init", "--library", lib, "--create-library")
    commands.append("factory init --library <lib> --create-library")
    factory("config", "set", "create-worktree", "worktree_root", work / "worktrees")
    commands.append("factory config set create-worktree worktree_root <work>/worktrees")
    fdir = repo / ".factory"
    write_files(fdir)
    launched = factory("launch", "plain", "--description", "real check")
    commands.append('factory launch plain --description "real check"')
    tasks = sorted(p for p in (fdir / "tasks").iterdir() if (p / "task.json").exists())
    task_dir = tasks[0]
    task = read_json(task_dir / "task.json", {})
    sid = task["session_id"]
    worktree = Path(task["worktree"])
    uuid.UUID(sid)
    cmd = [CLAUDE, "-p", PROMPT, "--session-id", sid, "--settings", str(fdir / "claude-settings.json"), "--model", "haiku"]
    commands.append(" ".join(["claude", "-p", repr(PROMPT), "--session-id", "<task session_id>", "--settings", "<repo>/.factory/claude-settings.json", "--model", "haiku"]))
    started = time.time()
    r = subprocess.run(cmd, cwd=worktree, env=env, capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)
    elapsed = time.time() - started
    attention = None
    deadline = time.time() + 30
    while time.time() < deadline:
        attention = read_json(task_dir / "task.json", {}).get("attention")
        if attention:
            break
        time.sleep(1)
    time.sleep(3)
    task = read_json(task_dir / "task.json", {})
    calls = read_json(fdir / "fake_adapter_calls.json", {}).get("calls", [])
    notifies = [c.get("text") for c in calls if c.get("op") == "notify"]
    evs = [e for e in read_events(task_dir / "events.jsonl") if "attention" in json.dumps(e)]
    settings = (fdir / "claude-settings.json").read_text()
    return {
        "commands": commands,
        "task_id": task_dir.name,
        "claude_rc": r.returncode,
        "claude_stdout": r.stdout.strip(),
        "claude_stderr": r.stderr.strip()[-2000:],
        "elapsed": round(elapsed, 1),
        "attention": task.get("attention"),
        "notifies": notifies,
        "events": evs,
        "settings": settings,
        "pass": bool(task.get("attention") and task["attention"].get("message")),
    }


def claude_version():
    return subprocess.run([CLAUDE, "--version"], capture_output=True, text=True).stdout.strip()


def write_report(res, error):
    ok = res is not None and res["pass"]
    lines = [
        "# Real attention check",
        "",
        f"Date: {datetime.datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"Claude version: {claude_version()}",
        f"Result: {'PASS' if ok else 'FAIL'}",
        "",
    ]
    if error:
        lines += ["Error:", "", "```", error, "```", ""]
    if res:
        lines += [
            "## Commands",
            "",
            *[f"- `{c}`" for c in res["commands"]],
            "",
            f"Environment: FACTORY_TERMINAL=fake, FACTORY_ATTENTION_DELAY=2, temp repo, temp library, task `{res['task_id']}`.",
            "",
            f"Claude exit code: {res['claude_rc']}, duration {res['elapsed']} s.",
            "",
            "Claude output:",
            "",
            "```",
            res["claude_stdout"],
            "```",
            "",
            "## Attention in task.json",
            "",
            "```json",
            json.dumps(res["attention"], indent=2),
            "```",
            "",
            "## Notify calls on the fake adapter",
            "",
            *([f"- {t}" for t in res["notifies"]] or ["- none"]),
            "",
            "## Task events about attention",
            "",
            "```json",
            *[json.dumps(e) for e in res["events"]],
            "```",
            "",
        ]
        if res["claude_stderr"]:
            lines += ["Claude stderr:", "", "```", res["claude_stderr"], "```", ""]
    REPORT.write_text("\n".join(lines))
    return ok


def main():
    if not CLAUDE:
        sys.exit("Cannot find the claude command. Put it on PATH or set CLAUDE_BIN.")
    work = HERE / "work" / f"real-attention-{uuid.uuid4().hex[:6]}"
    work.mkdir(parents=True)
    work = work.resolve()
    res = None
    error = None
    try:
        res = check(work)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    finally:
        shutil.rmtree(work, ignore_errors=True)
    ok = write_report(res, error)
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
