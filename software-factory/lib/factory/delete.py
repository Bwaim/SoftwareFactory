import shutil
from datetime import datetime
from pathlib import Path

from . import adapters, events, repo, state
from .adapters.base import AdapterError
from .errors import FactoryError


def git_lines(args, cwd):
    r = repo.git(args, cwd, check=False)
    return [line for line in r.stdout.splitlines() if line.strip()] if r.returncode == 0 else []


def ref_exists(cwd, ref):
    return repo.git(["rev-parse", "--verify", "--quiet", ref], cwd, check=False).returncode == 0


def is_ancestor(cwd, a, b):
    return repo.git(["merge-base", "--is-ancestor", a, b], cwd, check=False).returncode == 0


def branch_merged_or_pushed(ctx, branch, base_ref):
    local = f"refs/heads/{branch}"
    if not ref_exists(ctx.main, local):
        return False
    for target in (f"refs/remotes/origin/{branch}", f"refs/remotes/origin/{base_ref}"):
        if ref_exists(ctx.main, target) and is_ancestor(ctx.main, local, target):
            return True
    return False


def current_branch(worktree):
    return repo.git(["symbolic-ref", "--short", "-q", "HEAD"], worktree, check=False).stdout.strip() or None


def plan_delete(ctx, tid):
    task = state.load(ctx, tid)
    worktree = task.get("worktree")
    base_ref = task.get("base_ref") or "main"
    plan = {
        "task_id": tid, "session_id": task.get("session_id"), "terminal_handle": task.get("terminal_handle"),
        "worktree": worktree, "branch": None, "uncommitted": [], "unpushed": [],
        "delete_branch": False, "needs_confirm": False,
    }
    if worktree and Path(worktree).exists():
        plan["uncommitted"] = git_lines(["status", "--porcelain"], worktree)
        branch = current_branch(worktree)
        plan["branch"] = branch
        upstream = f"origin/{branch}" if branch and ref_exists(worktree, f"refs/remotes/origin/{branch}") else f"origin/{base_ref}"
        plan["unpushed"] = git_lines(["log", "--oneline", f"{upstream}..HEAD"], worktree)
        if branch:
            plan["delete_branch"] = not plan["unpushed"] and branch_merged_or_pushed(ctx, branch, base_ref)
    plan["needs_confirm"] = bool(plan["uncommitted"] or plan["unpushed"])
    return plan


def render_plan(plan):
    lines = [f"Delete task {plan['task_id']}:", f"- Claude session {plan['session_id']} and its terminal"]
    if plan["worktree"]:
        lines.append(f"- Worktree {plan['worktree']}")
    if plan["branch"]:
        if plan["delete_branch"]:
            lines.append(f"- Local branch {plan['branch']}")
        else:
            lines.append(f"- Local branch {plan['branch']} is kept: it is not pushed or merged")
    lines.append("- The task folder moves to .factory/tasks/archive/")
    if plan["uncommitted"]:
        lines += ["Uncommitted changes:"] + [f"  {line}" for line in plan["uncommitted"]]
    if plan["unpushed"]:
        lines += ["Commits not pushed to origin:"] + [f"  {line}" for line in plan["unpushed"]]
    return "\n".join(lines)


def archive_target(ctx, tid):
    target = ctx.fdir / "tasks" / "archive" / tid
    if target.exists():
        target = target.with_name(f"{tid}-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    return target


def close_terminal(ctx, handle):
    if not handle:
        return
    try:
        adapters.get_adapter(ctx).close(handle)
    except AdapterError:
        pass


def delete(ctx, tid, confirm_unpushed=False):
    plan = plan_delete(ctx, tid)
    if plan["needs_confirm"] and not confirm_unpushed:
        raise FactoryError(render_plan(plan) + "\nRun again with --confirm-unpushed after the user approves.")
    close_terminal(ctx, plan["terminal_handle"])
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
