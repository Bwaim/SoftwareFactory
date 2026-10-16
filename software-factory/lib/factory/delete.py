import shutil
from datetime import datetime
from pathlib import Path

from . import adapters, events, exclusive, repo, state
from .adapters.base import AdapterError
from .errors import FactoryError


def git_lines(args, cwd, label, errors):
    r = repo.git(args, cwd, check=False)
    if r.returncode != 0:
        errors.append(f"{label}: {(r.stderr or r.stdout).strip()}")
        return []
    return [line for line in r.stdout.splitlines() if line.strip()]


def ref_exists(cwd, ref):
    return repo.git(["rev-parse", "--verify", "--quiet", ref], cwd, check=False).returncode == 0


def is_ancestor(cwd, a, b):
    return repo.git(["merge-base", "--is-ancestor", a, b], cwd, check=False).returncode == 0


def content_merged(ctx, rev, base_ref):
    base = f"refs/remotes/origin/{base_ref}"
    if not ref_exists(ctx.main, base):
        return False
    r = repo.git(["merge-tree", "--write-tree", base, rev], ctx.main, check=False)
    if r.returncode != 0 or not r.stdout.strip():
        return False
    base_tree = repo.git(["rev-parse", f"{base}^{{tree}}"], ctx.main, check=False).stdout.strip()
    return r.stdout.splitlines()[0].strip() == base_tree


def head_commit(worktree):
    return repo.git(["rev-parse", "HEAD"], worktree, check=False).stdout.strip()


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


def task_branch(task):
    branch = task["state"].get("branch")
    worktree = task.get("worktree")
    if not branch and worktree and Path(worktree).exists():
        branch = current_branch(worktree)
    return branch


def tracks_own_branch(ctx, branch):
    r = repo.git(["config", "--get", f"branch.{branch}.merge"], ctx.main, check=False)
    return r.returncode == 0 and r.stdout.strip() == f"refs/heads/{branch}"


def merge_state(ctx, branch, base_ref):
    if not branch:
        return True, "no branch"
    local = f"refs/heads/{branch}"
    base = f"refs/remotes/origin/{base_ref}"
    if ref_exists(ctx.main, local) and ref_exists(ctx.main, base) and is_ancestor(ctx.main, local, base):
        return True, f"merged into origin/{base_ref}"
    if ref_exists(ctx.main, local) and content_merged(ctx, local, base_ref):
        return True, "merged (squash)"
    if tracks_own_branch(ctx, branch) and not ref_exists(ctx.main, f"refs/remotes/origin/{branch}"):
        return True, "pushed, and its remote branch was deleted"
    return False, "not merged"


def clean_report(ctx):
    repo.git(["fetch", "origin", "--prune"], ctx.main, check=False)
    rows = []
    for task in state.list_tasks(ctx):
        if task["status"] != "finished":
            continue
        branch = task_branch(task)
        merged, reason = merge_state(ctx, branch, task.get("base_ref") or "main")
        rows.append({"id": task["id"], "description": task["description"], "branch": branch,
                     "merged": merged, "reason": reason, "selected": merged})
    return rows


def plan_delete(ctx, tid):
    task = state.load(ctx, tid)
    worktree = task.get("worktree")
    base_ref = task.get("base_ref") or "main"
    plan = {
        "task_id": tid, "session_id": task.get("session_id"), "terminal_handle": task.get("terminal_handle"),
        "worktree": worktree, "branch": None, "base_ref": base_ref, "uncommitted": [], "unpushed": [],
        "squash_merged": False, "delete_branch": False, "needs_confirm": False, "check_errors": [],
    }
    errors = plan["check_errors"]
    if worktree and Path(worktree).exists():
        repo.git(["fetch", "origin", "--prune"], ctx.main, check=False)
        plan["uncommitted"] = git_lines(["status", "--porcelain"], worktree, "Cannot check uncommitted changes", errors)
        branch = current_branch(worktree)
        plan["branch"] = branch
        upstream = f"origin/{branch}" if branch and ref_exists(worktree, f"refs/remotes/origin/{branch}") else f"origin/{base_ref}"
        plan["unpushed"] = git_lines(["log", "--oneline", f"{upstream}..HEAD"], worktree, "Cannot check unpushed commits", errors)
        if plan["unpushed"] and not errors:
            rev = f"refs/heads/{branch}" if branch else head_commit(worktree)
            if rev and content_merged(ctx, rev, base_ref):
                plan["squash_merged"] = True
                plan["unpushed"] = []
        if branch:
            merged = plan["squash_merged"] or branch_merged_or_pushed(ctx, branch, base_ref)
            plan["delete_branch"] = not errors and not plan["unpushed"] and merged
    plan["needs_confirm"] = bool(plan["uncommitted"] or plan["unpushed"] or errors)
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
    if plan.get("squash_merged"):
        lines.append(f"The branch is merged into origin/{plan['base_ref']} (squash merge). Its commits are not lost.")
    if plan["uncommitted"]:
        lines += ["Uncommitted changes:"] + [f"  {line}" for line in plan["uncommitted"]]
    if plan["unpushed"]:
        lines += ["Commits not pushed to origin:"] + [f"  {line}" for line in plan["unpushed"]]
    if plan["check_errors"]:
        lines += ["Checks that failed, so the work may not be safe to delete:"] + [f"  {error}" for error in plan["check_errors"]]
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
    exclusive.forget(ctx, tid)
    return plan
