import os
import shutil
import subprocess
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from . import fsio
from .errors import FactoryError

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COLUMNS = ["Discovery", "Specification", "Plan", "Implementation", "Review", "QA"]
DONE_COLUMN = "Done"
NO_TASK = "Cannot find the task for this folder. Add --task <id> to the command."
GIT_MISSING = "The `git` program is not installed."


def git_installed():
    return shutil.which("git") is not None


def git(args, cwd, check=True, input=None):
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, input=input)
    except FileNotFoundError:
        raise FactoryError(GIT_MISSING)
    if check and r.returncode != 0:
        raise FactoryError(f"git {' '.join(args)} failed: {(r.stderr or r.stdout).strip()}")
    return r


def in_git(path):
    return git_installed() and git(["rev-parse", "--git-common-dir"], path, check=False).returncode == 0


def has_origin(cwd):
    return in_git(cwd) and git(["remote", "get-url", "origin"], cwd, check=False).returncode == 0


def main_repo(cwd):
    if in_git(cwd):
        r = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd)
        return Path(r.stdout.strip()).resolve().parent
    start = Path(cwd).resolve()
    for folder in (start, *start.parents):
        if (folder / ".factory" / "factory.yaml").exists():
            return folder
    return start


@dataclass
class Ctx:
    cwd: Path
    main: Path
    task_opt: str | None = None

    @cached_property
    def git(self):
        return in_git(self.main)

    @property
    def fdir(self):
        return self.main / ".factory"

    def factory_yaml(self):
        path = self.fdir / "factory.yaml"
        return fsio.require_map(path, fsio.read_yaml(path, {}))

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
    if not ctx.git:
        raise FactoryError(NO_TASK)
    top = Path(git(["rev-parse", "--show-toplevel"], ctx.cwd).stdout.strip()).resolve()
    for tj in sorted((ctx.fdir / "tasks").glob("*/task.json")):
        data = fsio.read_json(tj, {}) or {}
        wt = data.get("worktree")
        if wt and Path(wt).resolve() == top:
            return data["id"]
    raise FactoryError(NO_TASK)
