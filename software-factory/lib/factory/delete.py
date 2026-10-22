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


def current_branch(worktree):
    return repo.git(["symbolic-ref", "--short", "-q", "HEAD"], worktree, check=False).stdout.strip() or None


def task_branch(ctx, task):
    worktree = task.get("worktree")
    branch = current_branch(worktree) if worktree and Path(worktree).exists() else None
    branch = branch or task["state"].get("branch")
    if branch and ref_exists(ctx.main, f"refs/heads/{branch}"):
        return branch
    return None


def tracks_own_branch(ctx, branch):
    r = repo.git(["config", "--get", f"branch.{branch}.merge"], ctx.main, check=False)
    return r.returncode == 0 and r.stdout.strip() == f"refs/heads/{branch}"


def patch_id_merged(ctx, branch, base_ref):
    local = f"refs/heads/{branch}"
    base = f"refs/remotes/origin/{base_ref}"
    mb = repo.git(["merge-base", local, base], ctx.main, check=False)
    if mb.returncode != 0 or not mb.stdout.strip():
        return False
    mb = mb.stdout.strip()
    names = repo.git(["diff", "--name-only", "-z", mb, local], ctx.main, check=False)
    files = [f for f in names.stdout.split("\0") if f] if names.returncode == 0 else []
    if not files:
        return False
    d = repo.git(["diff", mb, local], ctx.main, check=False)
    if d.returncode != 0 or not d.stdout.strip():
        return False
    p = repo.git(["patch-id", "--stable"], ctx.main, check=False, input=d.stdout)
    ids = p.stdout.split()
    if p.returncode != 0 or not ids:
        return False
    log = repo.git(["log", "-p", "--no-merges", f"{mb}..{base}", "--", *files], ctx.main, check=False)
    if log.returncode != 0 or not log.stdout.strip():
        return False
    q = repo.git(["patch-id", "--stable"], ctx.main, check=False, input=log.stdout)
    return q.returncode == 0 and ids[0] in {line.split()[0] for line in q.stdout.splitlines() if line.strip()}


def merge_state(ctx, branch, base_ref):
    if not branch:
        return True, "no branch", False
    local = f"refs/heads/{branch}"
    base = f"refs/remotes/origin/{base_ref}"
    if ref_exists(ctx.main, local) and ref_exists(ctx.main, base):
        if is_ancestor(ctx.main, local, base):
            return True, f"merged into origin/{base_ref}", True
        if content_merged(ctx, local, base_ref) or patch_id_merged(ctx, branch, base_ref):
            return True, "merged (squash)", True
    if tracks_own_branch(ctx, branch) and not ref_exists(ctx.main, f"refs/remotes/origin/{branch}"):
        return True, "pushed, and its remote branch was deleted", False
    return False, "not merged", False


def clean_report(ctx):
    repo.git(["fetch", "origin", "--prune"], ctx.main, check=False)
    rows = []
    for task in state.list_tasks(ctx):
        if task["status"] != "finished":
            continue
        branch = task_branch(ctx, task)
        merged, reason, _ = merge_state(ctx, branch, task.get("base_ref") or "main")
        rows.append({"id": task["id"], "description": task["description"], "branch": branch,
                     "merged": merged, "reason": reason, "selected": merged})
    return rows


def lost_commits(ctx, worktree, branch, base_ref, errors):
    if worktree and Path(worktree).exists():
        upstream = f"origin/{branch}" if branch and ref_exists(worktree, f"refs/remotes/origin/{branch}") else f"origin/{base_ref}"
        return git_lines(["log", "--oneline", f"{upstream}..HEAD"], worktree, "Cannot check unpushed commits", errors)
    if branch:
        upstream = f"origin/{branch}" if ref_exists(ctx.main, f"refs/remotes/origin/{branch}") else f"origin/{base_ref}"
        return git_lines(["log", "--oneline", f"{upstream}..refs/heads/{branch}"], ctx.main, "Cannot check unpushed commits", errors)
    return []


def plan_delete(ctx, tid):
    task = state.load(ctx, tid)
    worktree = task.get("worktree")
    base_ref = task.get("base_ref") or "main"
    repo.git(["fetch", "origin", "--prune"], ctx.main, check=False)
    branch = task_branch(ctx, task)
    merged, reason, by_content = merge_state(ctx, branch, base_ref)
    plan = {
        "task_id": tid, "session_id": task.get("session_id"), "terminal_handle": task.get("terminal_handle"),
        "worktree": worktree, "branch": branch, "base_ref": base_ref, "uncommitted": [], "unpushed": [],
        "squash_merged": by_content and reason == "merged (squash)", "delete_branch": False, "needs_confirm": False,
        "check_errors": [], "reason": reason, "by_content": by_content,
    }
    errors = plan["check_errors"]
    if worktree and Path(worktree).exists():
        plan["uncommitted"] = git_lines(["status", "--porcelain"], worktree, "Cannot check uncommitted changes", errors)
    detached = bool(worktree) and Path(worktree).exists() and current_branch(worktree) is None
    if by_content:
        plan["delete_branch"] = bool(branch)
        if detached:
            plan["unpushed"] = lost_commits(ctx, worktree, branch, base_ref, errors)
    else:
        plan["unpushed"] = lost_commits(ctx, worktree, branch, base_ref, errors)
        pushed = bool(branch) and ref_exists(ctx.main, f"refs/remotes/origin/{branch}") and is_ancestor(ctx.main, f"refs/heads/{branch}", f"refs/remotes/origin/{branch}")
        plan["delete_branch"] = not errors and not plan["unpushed"] and pushed
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


class RemovalIncomplete(FactoryError):
    def __init__(self, left):
        super().__init__("\n".join(left))
        self.details = {"archived": True, "left": list(left)}


def close_terminal(ctx, handle):
    if not handle:
        return []
    try:
        return adapters.get_adapter(ctx).close(handle) or []
    except AdapterError as e:
        raise FactoryError(f"The terminal failed to close, so nothing was changed: {e}")


def delete(ctx, tid, confirm_unpushed=False):
    plan = plan_delete(ctx, tid)
    if plan["needs_confirm"] and not confirm_unpushed:
        raise FactoryError(render_plan(plan) + "\nRun again with --confirm-unpushed after the user approves.")
    left = close_terminal(ctx, plan["terminal_handle"])
    if plan["worktree"] and Path(plan["worktree"]).exists():
        r = repo.git(["worktree", "remove", "--force", plan["worktree"]], ctx.main, check=False)
        if r.returncode != 0:
            left.append(f"The worktree {plan['worktree']} was not removed: {(r.stderr or r.stdout).strip()}")
    repo.git(["worktree", "prune"], ctx.main, check=False)
    if plan["branch"] and plan["delete_branch"]:
        r = repo.git(["branch", "-D", plan["branch"]], ctx.main, check=False)
        if r.returncode != 0:
            left.append(f"The branch {plan['branch']} was not deleted: {(r.stderr or r.stdout).strip()}")
    events.log(ctx, tid, "task_deleted", None)
    target = archive_target(ctx, tid)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(state.task_dir(ctx, tid)), str(target))
    exclusive.forget(ctx, tid)
    if left:
        raise RemovalIncomplete(left)
    return plan
