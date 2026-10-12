import re
import shutil
import sys
import unicodedata
from pathlib import Path

from . import adapters, config, events, pipeline_check, repo, session, state
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


def rollback(undo):
    for action in reversed(undo):
        try:
            action()
        except Exception as e:
            print(f"Rollback step failed: {e}", file=sys.stderr)


def launch(ctx, pipeline_id, description, inputs, task_id=None, from_backlog=None):
    report = plan_launch(ctx, pipeline_id, description, inputs, task_id, from_backlog)
    if not report["ok"]:
        raise FactoryError(render_report(report))
    reg = Registry.load(ctx)
    undo = []
    try:
        if report["worktree"]:
            created_branch = create_worktree(ctx, report)
            if created_branch:
                undo.append(lambda: repo.git(["branch", "-D", report["branch"]], ctx.main))
            undo.append(lambda: repo.git(["worktree", "remove", "--force", report["worktree"]], ctx.main))
        task = new_task(ctx, reg, report, inputs)
        state.create(ctx, task)
        undo.append(lambda: shutil.rmtree(state.task_dir(ctx, task["id"]), ignore_errors=True))
        handle = session.start(ctx, task, session.first_prompt(task))
        undo.append(lambda: adapters.get_adapter(ctx).close(handle))
        task = state.update(ctx, task["id"], lambda t: t.__setitem__("terminal_handle", handle))
    except Exception:
        rollback(undo)
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
