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
