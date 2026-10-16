import copy
import json
import os
import shlex
import shutil
from pathlib import Path

from . import adapters, fsio, repo
from . import library as library_module
from .adapters.base import AdapterError
from .errors import FactoryError
from .version import DATA_VERSION

SETTINGS = {"permissions": {"allow": ["Bash(factory:*)", "Bash(factory *)"]}}
HOOK_EVENTS = {"Stop": "hook stop", "UserPromptSubmit": "hook prompt"}
EXCLUDES = [".factory/", ".factory.backup-*/"]
BACKLOG_HEADER = "# Backlog\n"


def link_dir():
    return Path(os.environ.get("FACTORY_LINK_DIR", "~/.local/bin")).expanduser()


def cli_path():
    return (repo.PLUGIN_ROOT / "bin" / "factory").resolve()


def ensure_link():
    d = link_dir()
    link = d / "factory"
    target = cli_path()
    changed = False
    if link.is_symlink():
        if Path(os.path.realpath(link)) != target:
            link.unlink()
            changed = True
    elif link.exists():
        raise FactoryError(f"{link} exists and is not a link. Move it away, then run again.")
    else:
        changed = True
    if changed:
        d.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
    on_path = str(d) in os.environ.get("PATH", "").split(os.pathsep)
    return {"path": str(link), "target": str(target), "changed": changed, "on_path": on_path}


def hook_command(sub):
    return shlex.quote(str(link_dir() / "factory")) + " " + sub


def settings_path(ctx):
    return ctx.fdir / "claude-settings.json"


def read_settings(path):
    try:
        data = json.loads(path.read_text())
    except (ValueError, UnicodeDecodeError) as e:
        raise FactoryError(f"{path} is not valid JSON ({e}). Fix or remove it, then run again.")
    if not isinstance(data, dict):
        raise FactoryError(f"{path} must hold a JSON object. Fix or remove it, then run again.")
    return data


def merge_settings(data, path):
    changed = False
    perms = data.setdefault("permissions", {})
    allow = perms.setdefault("allow", []) if isinstance(perms, dict) else None
    hooks = data.setdefault("hooks", {})
    if allow is None or not isinstance(allow, list) or not isinstance(hooks, dict):
        raise FactoryError(f"{path} has an unexpected shape in `permissions` or `hooks`. Fix or remove it, then run again.")
    for rule in SETTINGS["permissions"]["allow"]:
        if rule not in allow:
            allow.append(rule)
            changed = True
    for event, sub in HOOK_EVENTS.items():
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise FactoryError(f"{path} has an unexpected shape in `hooks.{event}`. Fix or remove it, then run again.")
        handlers = [h for g in groups if isinstance(g, dict) and isinstance(g.get("hooks"), list) for h in g["hooks"] if isinstance(h, dict)]
        if not any(str(h.get("command", "")).endswith("factory " + sub) for h in handlers):
            groups.append({"hooks": [{"type": "command", "command": hook_command(sub), "timeout": 10}]})
            changed = True
    return changed


def ensure_settings(ctx):
    path = settings_path(ctx)
    with fsio.locked(path):
        existed = path.exists()
        data = read_settings(path) if existed else {}
        changed = merge_settings(data, path)
        if changed or not existed:
            fsio.write_json(path, data)
            return True
        return False


def terminal_check(ctx):
    try:
        ok, message = adapters.get_adapter(ctx).check()
    except AdapterError as e:
        ok, message = False, str(e)
    return {"name": "terminal", "ok": ok, "message": message}


def git_check(ctx):
    has_origin = repo.git(["remote", "get-url", "origin"], ctx.main, check=False).returncode == 0
    message = (
        "Git repository with an origin remote."
        if has_origin
        else "This repository has no `origin` remote. Add it with `git remote add origin <url>`."
    )
    return {"name": "git", "ok": has_origin, "message": message}


def uv_check():
    has_uv = shutil.which("uv") is not None
    message = (
        "uv is installed."
        if has_uv
        else "uv is missing. Install it with `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`."
    )
    return {"name": "uv", "ok": has_uv, "message": message}


def prerequisites(cwd):
    try:
        ctx = repo.load_ctx(cwd)
    except FactoryError as e:
        return [{"name": "git", "ok": False, "message": f"{e} Run the factory in a git repository."}, uv_check()]
    return [terminal_check(ctx), git_check(ctx), uv_check()]


def write_new(path, writer, report):
    if path.exists():
        report["kept"].append(str(path))
        return
    writer(path)
    report["created"].append(str(path))


def create_library_folder(lib):
    for d in ("steps", "pipelines"):
        (lib / d).mkdir(parents=True, exist_ok=True)
    if not (lib / "factory.yaml").exists():
        fsio.write_yaml(lib / "factory.yaml", {"version": DATA_VERSION})


def add_excludes(ctx):
    rel = repo.git(["rev-parse", "--git-path", "info/exclude"], ctx.main).stdout.strip()
    path = (ctx.main / rel).resolve()
    lines = path.read_text().splitlines() if path.exists() else []
    missing = [entry for entry in EXCLUDES if entry not in lines]
    if missing:
        fsio.atomic_write_text(path, "\n".join(lines + missing) + "\n")


def init(cwd, library, create_library=False):
    checks = prerequisites(cwd)
    failed = [c for c in checks if not c["ok"]]
    if failed:
        raise FactoryError("Init stopped. Fix these first:\n" + "\n".join(f"- {c['name']}: {c['message']}" for c in failed))
    ctx = repo.load_ctx(cwd)
    lib = Path(library).expanduser().resolve()
    if not lib.exists() and not create_library:
        raise FactoryError(f"The library folder {lib} does not exist. Run again with --create-library to create it.")
    if create_library or not (lib / "factory.yaml").exists():
        create_library_folder(lib)
    report = {"created": [], "kept": [], "library": str(lib), "checks": checks}
    report["library_git"] = library_module.in_git(lib)
    f = ctx.fdir
    for d in ("steps", "pipelines", "tasks/archive"):
        (f / d).mkdir(parents=True, exist_ok=True)
    factory_data = {
        "version": DATA_VERSION, "library": str(lib), "terminal": adapters.terminal_name(ctx),
        "columns": list(repo.DEFAULT_COLUMNS), "poll_minutes": 5, "ticket_url": "",
    }
    write_new(f / "factory.yaml", lambda p: fsio.write_yaml(p, factory_data), report)
    write_new(f / "config.yaml", lambda p: fsio.write_yaml(p, {}), report)
    write_new(f / "backlog.md", lambda p: fsio.atomic_write_text(p, BACKLOG_HEADER), report)
    settings_file = settings_path(ctx)
    existed = settings_file.exists()
    try:
        ensure_settings(ctx)
        report["created" if not existed else "kept"].append(str(settings_file))
    except FactoryError as e:
        report["kept"].append(str(settings_file))
        report.setdefault("warnings", []).append(str(e))
    add_excludes(ctx)
    report["link"] = ensure_link()
    return report
