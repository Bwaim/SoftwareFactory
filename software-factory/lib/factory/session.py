import uuid

from . import adapters, state
from .adapters.base import AdapterError
from .registry import NO_WORKTREE_PIPELINES

FIRST_PROMPT = (
    "You run factory task `{id}`. Run `{next}` and follow its instructions. "
    "When the step is done, run `{done}`. Repeat until `{next}` says the pipeline is finished."
)
RESUME_PROMPT = "The factory resumed this task. Run `{status}`, then continue with `{next}`."


def factory_cmd(task, sub):
    return f"factory {sub}" + ("" if task.get("worktree") else f" --task {task['id']}")


def first_prompt(task):
    return FIRST_PROMPT.format(id=task["id"], next=factory_cmd(task, "next"), done=factory_cmd(task, "done"))


def resume_prompt(task, extra=None):
    text = RESUME_PROMPT.format(status=factory_cmd(task, "status"), next=factory_cmd(task, "next"))
    return f"{text}\n\n{extra}" if extra else text


def new_session_id():
    return str(uuid.uuid4())


def claude_args(ctx, task, resume=False):
    args = ["--name", task["id"]]
    args += ["--resume", task["session_id"]] if resume else ["--session-id", task["session_id"]]
    args += ["--settings", str(ctx.fdir / "claude-settings.json")]
    args += ["--add-dir", str(state.task_dir(ctx, task["id"]) / "artifacts")]
    if task["pipeline"] in NO_WORKTREE_PIPELINES and ctx.library():
        args += ["--add-dir", str(ctx.library())]
    claude = task.get("claude") or {}
    if claude.get("model"):
        args += ["--model", str(claude["model"])]
    if claude.get("effort"):
        args += ["--effort", str(claude["effort"])]
    return args


def start(ctx, task, prompt, resume=False):
    cwd = task["worktree"] or str(ctx.main)
    return adapters.get_adapter(ctx).start_session(
        task["id"], cwd, prompt, claude_args(ctx, task, resume), bool(task.get("worktree"))
    )


def notify(ctx, text):
    try:
        adapter = adapters.get_adapter(ctx)
        if "notify" not in adapter.capabilities():
            return
        adapter.notify(text)
    except AdapterError:
        pass


def live_state(ctx, task):
    handle = task.get("terminal_handle")
    if not handle:
        return "gone"
    try:
        adapter = adapters.get_adapter(ctx)
        if "state" not in adapter.capabilities():
            return "unknown"
        return adapter.state(handle)
    except AdapterError:
        return "unknown"
