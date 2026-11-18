import os
import re
import subprocess
import sys

from . import workspaces
from .errors import FactoryError

NO_FACTORY = "This repository has no factory. Run `factory init` in it first."
LIBRARY_MISSING = "The library folder does not exist. Create it, or leave the field blank."
PICKER_ONLY_MACOS = "The folder picker works only on macOS."

ROUTES = {"global": [], "workspace": []}
WORKSPACE_PATH = re.compile(r"^/api/w/([a-z0-9-]{1,40})(/.*)$")


class NotFound(Exception):
    pass


class DetailedError(FactoryError):
    def __init__(self, message, **details):
        super().__init__(message)
        self.details = details


def route(method, pattern, scope="workspace"):
    regex = re.compile("^" + pattern + "$")

    def register(fn):
        ROUTES[scope].append((method, regex, fn))
        return fn

    return register


def run(routes, target, method, path, query, body):
    for m, regex, fn in routes:
        match = regex.match(path)
        if m == method and match:
            return fn(target, *match.groups(), query=query, body=body or {})
    raise NotFound(path)


def dispatch(server, method, path, query, body):
    match = WORKSPACE_PATH.match(path)
    if not match:
        return run(ROUTES["global"], server, method, path, query, body)
    ws = server.fresh(match.group(1))
    if ws is None:
        raise NotFound(path)
    if ws.error:
        raise FactoryError(ws.error)
    return run(ROUTES["workspace"], ws, method, "/api" + match.group(2), query, body)


@route("GET", "/api/ping", scope="global")
def ping(server, query, body):
    return {"ok": True, "pid": os.getpid()}


@route("GET", "/api/info")
def info(server, query, body):
    ctx = server.ctx
    return {
        "workspace": {"id": server.id, "name": server.name},
        "columns": ctx.columns(),
        "ticket_url": ctx.factory_yaml().get("ticket_url") or "",
        "adapter": server.adapter,
        "capabilities": server.capabilities,
    }


@route("POST", "/api/shutdown", scope="global")
def shutdown(server, query, body):
    server.stop()
    return {"ok": True}


@route("GET", "/api/jobs/([a-f0-9]+)", scope="global")
def job(server, job_id, query, body):
    if job_id not in server.jobs:
        raise NotFound(job_id)
    return server.jobs[job_id]


def workspace_row(server, entry):
    from . import board, state
    ws = server.fresh(entry["id"])
    row = {**entry, "needs_you": 0, "open_tasks": 0, "error": ws.error if ws else "Unknown workspace."}
    if ws and not ws.error:
        tasks = state.list_tasks(ws.ctx)
        row.update(needs_you=board.needs_you(tasks), open_tasks=board.open_tasks(tasks))
    return row


@route("GET", "/api/workspaces", scope="global")
def workspaces_list(server, query, body):
    server.reload_if_changed()
    return [workspace_row(server, w) for w in workspaces.list_all()]


def init_workspace(main, body):
    from . import init
    try:
        init.init(main, body.get("library"))
    except init.MissingLibraryError:
        raise DetailedError(LIBRARY_MISSING, checks=[])
    except init.InitChecksError:
        raise
    except FactoryError as e:
        raise DetailedError(str(e), checks=[])


@route("POST", "/api/workspaces/add", scope="global")
def workspace_add(server, query, body):
    main = workspaces.resolve_main(body["path"])
    existing = workspaces.find_by_path(main)
    if existing:
        raise FactoryError(f"{main} is already the workspace {existing['name']}.")
    if not (main / ".factory" / "factory.yaml").exists():
        if not body.get("init"):
            raise DetailedError(NO_FACTORY, code="no_factory", main=str(main))
        init_workspace(main, body)
    entry = workspaces.add(main)
    server.reload()
    return entry


@route("POST", "/api/workspaces/([a-z0-9-]{1,40})/rename", scope="global")
def workspace_rename(server, wid, query, body):
    if workspaces.get(wid) is None:
        raise NotFound(wid)
    entry = workspaces.rename(wid, body["name"])
    server.reload()
    return entry


@route("POST", "/api/workspaces/([a-z0-9-]{1,40})/delete", scope="global")
def workspace_delete(server, wid, query, body):
    if workspaces.get(wid) is None:
        raise NotFound(wid)
    entry = workspaces.remove(wid)
    server.reload()
    return entry


@route("POST", "/api/workspaces/pick-folder", scope="global")
def pick_folder(server, query, body):
    if sys.platform != "darwin":
        raise FactoryError(PICKER_ONLY_MACOS)
    r = subprocess.run(["osascript", "-e", "POSIX path of (choose folder)"], capture_output=True, text=True)
    if r.returncode != 0:
        return {"path": None}
    return {"path": r.stdout.strip().rstrip("/") or None}


@route("GET", "/api/host", scope="global")
def host(server, query, body):
    return {"folder_picker": sys.platform == "darwin"}


def registry(server):
    from .registry import Registry
    return Registry.load(server.ctx)


@route("GET", "/api/steps")
def steps(server, query, body):
    from . import hidden, pipeline_store
    hidden_ids = set(hidden.ids(server.ctx))
    return [pipeline_store.step_summary(s, hidden_ids) for s in sorted(registry(server).steps.values(), key=lambda s: s.id)]


@route("GET", "/api/steps/([a-z][a-z0-9_-]*)")
def step(server, sid, query, body):
    from . import hidden, pipeline_store
    reg = registry(server)
    return pipeline_store.step_detail(reg, reg.step(sid), set(hidden.ids(server.ctx)))


@route("POST", "/api/steps/([a-z][a-z0-9_-]*)/hide")
def step_hide(server, sid, query, body):
    from . import hidden
    return {"message": hidden.hide(server.ctx, sid)}


@route("POST", "/api/steps/([a-z][a-z0-9_-]*)/unhide")
def step_unhide(server, sid, query, body):
    from . import hidden
    return {"message": hidden.unhide(server.ctx, sid)}


@route("POST", "/api/steps/([a-z][a-z0-9_-]*)/delete/dry-run")
def step_delete_dry_run(server, sid, query, body):
    from . import step_delete
    return step_delete.plan(server.ctx, sid, body.get("level"))


@route("POST", "/api/steps/([a-z][a-z0-9_-]*)/delete")
def step_delete_run(server, sid, query, body):
    from . import step_delete
    return step_delete.delete(server.ctx, sid, body.get("level"))


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


@route("POST", "/api/pipelines/keys")
def pipeline_keys(server, query, body):
    from . import keys
    return keys.available(registry(server), body["data"], body.get("at"))


@route("POST", "/api/library/commit")
def library_commit(server, query, body):
    from . import library
    return {"sha": library.commit(server.ctx, body["message"], body["paths"])}


@route("POST", "/api/pipelines/save")
def pipeline_save(server, query, body):
    from . import pipeline_store
    return pipeline_store.save(server.ctx, body["data"], body["level"], body.get("original_id"), body.get("original_level"), bool(body.get("replace")))


TASK = "([a-z][a-z0-9_-]{0,31})"


@route("GET", "/api/tasks")
def tasks(server, query, body):
    from . import board, rename
    rename.apply_all_pending(server.ctx)
    return board.task_rows(server.ctx, server.next_poll)


@route("GET", f"/api/tasks/{TASK}/artifacts/([^/]+)")
def artifact(server, tid, name, query, body):
    from . import state
    state.load(server.ctx, tid)
    path = state.artifact_file(server.ctx, tid, name)
    if not path.is_file():
        raise NotFound(name)
    return {"name": name, "text": path.read_text(errors="replace")}


@route("GET", f"/api/tasks/{TASK}/detail")
def task_detail(server, tid, query, body):
    from . import task_detail
    return task_detail.detail(server.ctx, tid, server.next_poll)


@route("POST", f"/api/tasks/{TASK}/focus")
def focus(server, tid, query, body):
    from . import session
    return {"ok": True, **session.focus(server.ctx, tid)}


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
    message, delivery_error = engine.approve(server.ctx, tid, send=True)
    return {"message": message, "delivery_error": delivery_error}


@route("POST", f"/api/tasks/{TASK}/request-changes")
def request_changes(server, tid, query, body):
    from . import engine
    message, delivery_error = engine.request_changes(server.ctx, tid, body["text"], send=True)
    return {"message": message, "delivery_error": delivery_error}


@route("POST", f"/api/tasks/{TASK}/external-done")
def external_done(server, tid, query, body):
    from . import engine
    engine.external_done(server.ctx, tid)
    return {"ok": True}


@route("POST", f"/api/tasks/{TASK}/check")
def check_now(server, tid, query, body):
    from . import engine, state
    state.load(server.ctx, tid)
    return {"job": server.start_job(lambda: engine.check_task(server.ctx, tid))}


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


@route("POST", "/api/exclusive/([a-z][a-z0-9_-]*)/release")
def exclusive_release(server, name, query, body):
    from . import exclusive
    return {"holder": exclusive.force_release(server.ctx, name, body.get("task"))}


@route("GET", "/api/clean")
def clean(server, query, body):
    from . import delete
    return delete.clean_report(server.ctx)


@route("POST", f"/api/tasks/{TASK}/cancel/dry-run")
def cancel_dry_run(server, tid, query, body):
    from . import delete
    plan = delete.plan_cancel(server.ctx, tid)
    return {**plan, "text": delete.render_cancel_plan(plan)}


@route("POST", f"/api/tasks/{TASK}/cancel")
def cancel_task(server, tid, query, body):
    from . import delete
    result = delete.cancel(server.ctx, tid)
    return {**result, "text": delete.render_cancel_result(result)}


@route("POST", "/api/delete/dry-run")
def delete_dry_run(server, query, body):
    from . import delete
    return delete.plan_delete(server.ctx, body["id"])


@route("POST", "/api/delete")
def delete_task(server, query, body):
    from . import delete
    return delete.delete(server.ctx, body["id"], body.get("confirm_unpushed") is True)


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


@route("GET", "/api/step-form")
def step_form(server, query, body):
    from . import step_store
    return step_store.form_data(server.ctx)


@route("POST", "/api/steps/check")
def step_check(server, query, body):
    from . import step_store
    return step_store.check(server.ctx, body["manifest"], body.get("body", ""), body.get("level") or "local")


@route("POST", "/api/steps/preview")
def step_preview(server, query, body):
    from . import step_store
    return step_store.preview(server.ctx, body["manifest"], body.get("body", ""))


@route("POST", "/api/steps/impact")
def step_impact(server, query, body):
    from . import step_store
    return step_store.impact(server.ctx, body["id"])


@route("POST", "/api/steps/save")
def step_save(server, query, body):
    from . import step_store
    return step_store.save(server.ctx, body["manifest"], body["body"], body.get("level", "local"), body["mode"])
