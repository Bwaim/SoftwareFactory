import os
import re

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


def registry(server):
    from .registry import Registry
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
