from pathlib import Path

from . import adapters, library, migrate, repo, version
from .errors import FactoryError


def factory_mtime(path):
    try:
        return (Path(path) / ".factory" / "factory.yaml").stat().st_mtime_ns
    except OSError:
        return None


def check_adapter(ctx):
    try:
        adapter = adapters.get_adapter(ctx)
        ok, message = adapter.check()
        capabilities = sorted(adapter.capabilities()) if ok else []
    except Exception as e:
        ok, message, capabilities = False, str(e), []
    return {"ok": ok, "message": message}, capabilities


def open_ctx(path):
    if not Path(path).is_dir():
        raise FactoryError(f"The folder {path} does not exist.")
    return repo.load_ctx(cwd=path)


def load(path):
    ctx = open_ctx(path)
    version.require_repo(ctx)
    return ctx


def migrate_if_older(ctx):
    if not ctx.initialized():
        return None
    p = migrate.plan(ctx)
    if p["repo"]["migrate"] or p["library"]["migrate"]:
        return migrate.migrate(ctx)
    return None


def library_changes(lib):
    top = library.repo_root(lib)
    if top is None:
        return []
    out = repo.git(["status", "--porcelain", "-uall", "--", str(lib)], top).stdout
    return [line[3:] for line in out.splitlines() if line.strip()]


class Workspace:
    def __init__(self, server, entry):
        self.server = server
        self.entry = dict(entry)
        self.id = entry["id"]
        self.name = entry["name"]
        self.path = entry["path"]
        self.ctx, self.error = None, None
        self.adapter, self.capabilities = {"ok": False, "message": ""}, []
        try:
            ctx = open_ctx(self.path)
            self.remember_commit(migrate_if_older(ctx))
            version.require_repo(ctx)
            self.ctx = ctx
            self.adapter, self.capabilities = check_adapter(self.ctx)
        except Exception as e:
            self.ctx, self.error = None, str(e)
        self.yaml_mtime = factory_mtime(self.path)

    def remember_commit(self, migrated):
        if migrated and migrated["library_commit"]:
            self.server.library_commits[self.id] = migrated["library_commit"]

    @property
    def library_commit(self):
        offer = self.server.library_commits.get(self.id)
        if not offer:
            return None
        files = library_changes(self.ctx.library())
        if not files:
            self.server.library_commits.pop(self.id, None)
            return None
        return {**offer, "files": files}

    @property
    def jobs(self):
        return self.server.jobs

    @property
    def next_poll(self):
        return self.server.next_poll

    def start_job(self, fn):
        return self.server.start_job(fn)

    def stale(self):
        return factory_mtime(self.path) != self.yaml_mtime

    def rebuilt(self):
        return Workspace(self.server, self.entry)
