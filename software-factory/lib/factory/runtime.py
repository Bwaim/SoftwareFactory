from pathlib import Path

from . import adapters, repo, version
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


def load(path):
    if not Path(path).is_dir():
        raise FactoryError(f"The folder {path} does not exist.")
    ctx = repo.load_ctx(cwd=path)
    version.require_repo(ctx)
    return ctx


class Workspace:
    def __init__(self, server, entry):
        self.server = server
        self.entry = dict(entry)
        self.id = entry["id"]
        self.name = entry["name"]
        self.path = entry["path"]
        self.yaml_mtime = factory_mtime(self.path)
        self.ctx, self.error = None, None
        self.adapter, self.capabilities = {"ok": False, "message": ""}, []
        try:
            self.ctx = load(self.path)
            self.adapter, self.capabilities = check_adapter(self.ctx)
        except Exception as e:
            self.ctx, self.error = None, str(e)

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
