import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import fsio
from .errors import FactoryError

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COLUMNS = ["Discovery", "Specification", "Plan", "Implementation", "Review", "QA"]
DONE_COLUMN = "Done"


def git(args, cwd, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise FactoryError(f"git {' '.join(args)} failed: {(r.stderr or r.stdout).strip()}")
    return r


def main_repo(cwd):
    r = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd, check=False)
    if r.returncode != 0:
        raise FactoryError("This folder is not in a git repository.")
    return Path(r.stdout.strip()).resolve().parent


@dataclass
class Ctx:
    cwd: Path
    main: Path
    task_opt: str | None = None

    @property
    def fdir(self):
        return self.main / ".factory"

    def factory_yaml(self):
        return fsio.read_yaml(self.fdir / "factory.yaml", {}) or {}

    def library(self):
        lib = self.factory_yaml().get("library")
        return Path(lib).expanduser().resolve() if lib else None

    def initialized(self):
        return (self.fdir / "factory.yaml").exists()

    def columns(self):
        return list(self.factory_yaml().get("columns") or DEFAULT_COLUMNS)


def load_ctx(cwd=None, task_opt=None):
    cwd = Path(cwd or os.getcwd()).resolve()
    return Ctx(cwd=cwd, main=main_repo(cwd), task_opt=task_opt)


def task_exists(ctx, tid):
    return (ctx.fdir / "tasks" / tid / "task.json").exists()


def current_task_id(ctx):
    explicit = ctx.task_opt or os.environ.get("FACTORY_TASK")
    if explicit:
        if not task_exists(ctx, explicit):
            raise FactoryError(f"Unknown task {explicit}.")
        return explicit
    top = Path(git(["rev-parse", "--show-toplevel"], ctx.cwd).stdout.strip()).resolve()
    for tj in sorted((ctx.fdir / "tasks").glob("*/task.json")):
        data = fsio.read_json(tj, {}) or {}
        wt = data.get("worktree")
        if wt and Path(wt).resolve() == top:
            return data["id"]
    raise FactoryError("Cannot find the task for this folder. Add --task <id> to the command.")


def task_flag(task):
    return "" if task.get("worktree") else f" --task {task['id']}"
