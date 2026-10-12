import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

SF = Path(__file__).resolve().parents[1]
VERIF = SF.parent / "verification" / "software-factory"
BIN = SF / "bin" / "factory"
LINK = Path.home() / ".local" / "bin" / "factory"
RESULTS = VERIF / "e2e-results.json"
ROOT = VERIF / "work" / "e2e"
TRUST_FAIL = "trust dialog: run --prepare and trust the repo"
results = []
handles = []

STEP_ONE = "---\nid: e2e-one\ndescription: Write one.txt\ncategory: test\ntype: script\ndone_when: one.txt exists\ndone_check: test -f \"$(factory artifact path one.txt)\"\n---\n\ne2e-one.sh\n"
STEP_HOLD = "---\nid: e2e-hold\ndescription: Wait for the test\ncategory: test\ntype: prompt\ndone_when: The test marks it done.\nwait_external: true\n---\n\nRun `factory wait`. Then stop and wait for a message.\n"
STEP_TWO = "---\nid: e2e-two\ndescription: Write two.txt\ncategory: test\ntype: script\ndone_when: two.txt exists\ndone_check: test -f \"$(factory artifact path two.txt)\"\n---\n\ne2e-two.sh\n"
PIPELINE = "id: e2e\ndescription: End-to-end test pipeline\nsteps:\n  - e2e-one\n  - e2e-hold\n  - e2e-two\n"


class TrustDialog(Exception):
    pass


def prepare_instructions():
    return (f"Open a Herdr pane, cd {ROOT / 'repo'}, run `claude`, choose 'Yes, I trust this folder', "
            "then exit Claude. Then run the e2e.")


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
    return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []


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


def configure_git_user(repo):
    sh(["git", "config", "user.name", "E2E"], cwd=repo)
    sh(["git", "config", "user.email", "e2e@example.com"], cwd=repo)


def create_origin_and_seed():
    origin, seed = ROOT / "origin.git", ROOT / "seed"
    sh(["git", "init", "--bare", "-b", "main", origin])
    sh(["git", "clone", origin, seed])
    configure_git_user(seed)
    (seed / "README.md").write_text("e2e\n")
    sh(["git", "add", "-A"], cwd=seed)
    sh(["git", "commit", "-m", "init"], cwd=seed)
    sh(["git", "push", "origin", "HEAD:main"], cwd=seed)
    return origin


def clone_repo(origin):
    repo = ROOT / "repo"
    repo.mkdir(exist_ok=True)
    sh(["git", "clone", origin, "."], cwd=repo)
    configure_git_user(repo)
    return repo


def empty_folder(folder):
    for child in folder.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink()


def clear_root_keeping_repo():
    if not ROOT.exists():
        return
    for child in ROOT.iterdir():
        if child.name == "repo":
            empty_folder(child)
        else:
            shutil.rmtree(child, ignore_errors=True)


def prepare():
    if (ROOT / "repo").exists():
        print(f"{ROOT / 'repo'} already exists. Trust is kept.")
        return 0
    ROOT.mkdir(parents=True, exist_ok=True)
    clone_repo(create_origin_and_seed())
    print(prepare_instructions())
    return 0


def setup():
    clear_root_keeping_repo()
    ROOT.mkdir(parents=True, exist_ok=True)
    repo = clone_repo(create_origin_and_seed())
    lib_root = ROOT / "libroot"
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


def remember_handle(handle):
    if handle and handle not in handles:
        handles.append(handle)


def close_recorded_handles():
    for handle in handles:
        for workspace_id in handle.get("extra_workspaces", []):
            sh(["herdr", "workspace", "close", workspace_id], check=False)
        if handle.get("tab"):
            sh(["herdr", "tab", "close", handle["tab"]], check=False)
        if handle.get("created_workspace") and handle.get("workspace"):
            sh(["herdr", "workspace", "close", handle["workspace"]], check=False)


def launch_task(repo):
    r = sh(["factory", "launch", "e2e", "--description", "E2E task", "--json"], cwd=repo, check=False)
    if r.returncode != 0:
        if "trust" in (r.stdout + r.stderr).lower():
            raise TrustDialog()
        raise RuntimeError(f"factory launch failed: {r.stdout}{r.stderr}")
    return json.loads(r.stdout)


def run():
    repo, lib = setup()
    worktree_root = ROOT / "worktrees"

    sh([BIN, "init", "--library", lib, "--create-library"], cwd=repo)
    sh(["factory", "config", "set", "create-worktree", "worktree_root", worktree_root], cwd=repo)
    fdir = repo / ".factory"
    write_pipeline(fdir)

    task = launch_task(repo)
    tid, wt = task["id"], Path(task["worktree"])
    remember_handle(task["terminal_handle"])
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
    remember_handle(resumed["terminal_handle"])
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


def restore_link(previous):
    if previous is not None:
        LINK.unlink(missing_ok=True)
        LINK.symlink_to(previous)
    elif LINK.is_symlink():
        LINK.unlink()


def clean_up_root():
    clear_root_keeping_repo()


def main():
    if "--prepare" in sys.argv[1:]:
        return prepare()
    if not (ROOT / "repo").exists():
        print(prepare_instructions())
        return 2
    if os.environ.get("HERDR_ENV") != "1":
        print("Run this script inside a Herdr pane.")
        return 2
    if LINK.exists() and not LINK.is_symlink():
        print(f"{LINK} exists and is not a link. Stop.")
        return 2
    previous = os.readlink(LINK) if LINK.is_symlink() else None
    try:
        run()
    except TrustDialog:
        record("Claude starts without the trust dialog", False, TRUST_FAIL)
    except Exception as e:
        record("e2e run completed without error", False, str(e))
    finally:
        close_recorded_handles()
        restore_link(previous)
        clean_up_root()
        RESULTS.write_text(json.dumps(results, indent=2) + "\n")
    return 0 if results and all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
