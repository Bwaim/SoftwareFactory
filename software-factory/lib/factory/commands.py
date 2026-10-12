from . import cli
from .errors import FactoryError


def register(sub, common):
    p = sub.add_parser("version")
    vs = p.add_subparsers(dest="action", required=True)
    vs.add_parser("check", parents=[common])
    p = sub.add_parser("pipeline")
    ps = p.add_subparsers(dest="action", required=True)
    pc = ps.add_parser("check", parents=[common])
    pc.add_argument("id")
    p = sub.add_parser("config")
    cs = p.add_subparsers(dest="action", required=True)
    g = cs.add_parser("get", parents=[common]); g.add_argument("step"); g.add_argument("key")
    s = cs.add_parser("set", parents=[common]); s.add_argument("step"); s.add_argument("key"); s.add_argument("value")
    p = sub.add_parser("state")
    ss = p.add_subparsers(dest="action", required=True)
    g = ss.add_parser("get", parents=[common]); g.add_argument("key")
    s = ss.add_parser("set", parents=[common]); s.add_argument("key"); s.add_argument("value")
    sub.add_parser("status", parents=[common])
    p = sub.add_parser("block", parents=[common]); p.add_argument("reason")
    sub.add_parser("unblock", parents=[common])
    sub.add_parser("tasks", parents=[common])
    p = sub.add_parser("pause", parents=[common])
    p.add_argument("id", nargs="?")
    p.add_argument("--all", action="store_true")
    p.add_argument("--wait", action="store_true")
    p = sub.add_parser("resume", parents=[common]); p.add_argument("id")
    for name in ("next", "done", "skip", "run-script"):
        sub.add_parser(name, parents=[common])
    p = sub.add_parser("artifact")
    a = p.add_subparsers(dest="action", required=True)
    ap = a.add_parser("path", parents=[common]); ap.add_argument("name")
    p = sub.add_parser("launch", parents=[common])
    p.add_argument("pipeline")
    p.add_argument("--description", default="")
    p.add_argument("--input", action="append", default=[])
    p.add_argument("--id", default=None)
    p.add_argument("--from-backlog", default=None)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("terminal")
    ts = p.add_subparsers(dest="action", required=True)
    ts.add_parser("check", parents=[common])
    tf = ts.add_parser("focus", parents=[common]); tf.add_argument("id")
    tp = ts.add_parser("send-prompt", parents=[common]); tp.add_argument("id"); tp.add_argument("text"); tp.add_argument("--wait", action="store_true")
    p = sub.add_parser("delete", parents=[common])
    p.add_argument("id")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm-unpushed", action="store_true")
    p = sub.add_parser("init", parents=[common])
    p.add_argument("--library", required=True)
    p.add_argument("--create-library", action="store_true")
    sub.add_parser("link", parents=[common])
    sub.add_parser("open-ide", parents=[common])
    sub.add_parser("wait", parents=[common])
    sub.add_parser("poll", parents=[common])
    p = sub.add_parser("external-done", parents=[common]); p.add_argument("id")
    p = sub.add_parser("approve", parents=[common]); p.add_argument("--send", action="store_true")
    p = sub.add_parser("request-changes", parents=[common]); p.add_argument("text"); p.add_argument("--send", action="store_true")
    p = sub.add_parser("approval")
    aps = p.add_subparsers(dest="action", required=True)
    aps.add_parser("check", parents=[common])
    sub.add_parser("menu", parents=[common])


@cli.command("next")
def next_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.next_step(ctx, tid))


@cli.command("done")
def done_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.done(ctx, tid))


@cli.command("skip")
def skip_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.skip(ctx, tid))


@cli.command("run-script")
def run_script_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    return engine.run_script(ctx, tid)


@cli.command("status")
def status_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.status_text(ctx, tid))


@cli.command("block")
def block_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.block(ctx, tid, args.reason))


@cli.command("unblock")
def unblock_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.unblock(ctx, tid))


@cli.command("tasks")
def tasks_cmd(args):
    from . import board
    rows = board.task_rows(ctx_of(args))
    if args.json:
        cli.emit(rows, True)
    else:
        print(board.render_rows(rows))


@cli.command("pause")
def pause_cmd(args):
    from . import session
    ctx = ctx_of(args)
    if args.all:
        ids = session.pause_all(ctx, args.wait)
        print("Paused: " + (", ".join(ids) if ids else "none"))
        return
    if not args.id:
        raise FactoryError("Give a task id, or --all.")
    session.pause(ctx, args.id, args.wait)
    print(f"Task {args.id} paused.")


@cli.command("resume")
def resume_cmd(args):
    from . import session
    session.resume(ctx_of(args), args.id)
    print(f"Task {args.id} resumed.")


@cli.command("terminal focus")
def focus_cmd(args):
    from . import session
    session.focus(ctx_of(args), args.id)


@cli.command("terminal send-prompt")
def send_prompt_cmd(args):
    from . import session
    session.send_prompt(ctx_of(args), args.id, args.text, args.wait)
    print("Prompt sent.")


@cli.command("terminal check")
def terminal_check(args):
    from . import adapters, repo
    ctx = repo.load_ctx(task_opt=args.task)
    ok, message = adapters.get_adapter(ctx).check()
    print(("OK: " if ok else "FAILED: ") + message)
    return 0 if ok else 1


def parse_inputs(items):
    inputs = {}
    for item in items:
        if "=" not in item:
            raise FactoryError(f"Invalid input `{item}`. Use --input <key>=<value>.")
        key, value = item.split("=", 1)
        inputs[key] = value
    return inputs


@cli.command("launch")
def launch_cmd(args):
    from . import launch
    ctx = ctx_of(args)
    inputs = parse_inputs(args.input)
    if args.dry_run:
        report = launch.plan_launch(ctx, args.pipeline, args.description, inputs, args.id, args.from_backlog)
        cli.emit(report, True) if args.json else print(launch.render_report(report))
        return 0 if report["ok"] else 1
    task = launch.launch(ctx, args.pipeline, args.description, inputs, args.id, args.from_backlog)
    cli.emit(task, True) if args.json else print(f"Task {task['id']} started." + (f" Worktree: {task['worktree']}" if task["worktree"] else ""))


@cli.command("delete")
def delete_cmd(args):
    from . import delete
    ctx = ctx_of(args)
    if args.dry_run:
        plan = delete.plan_delete(ctx, args.id)
        if args.json:
            cli.emit(plan, True)
        else:
            print(delete.render_plan(plan))
        return
    delete.delete(ctx, args.id, args.confirm_unpushed)
    print(f"Task {args.id} deleted and archived.")


@cli.command("init")
def init_cmd(args):
    from . import init
    report = init.init(".", args.library, args.create_library)
    if args.json:
        cli.emit(report, True)
        return
    for check in report["checks"]:
        print(f"{'OK' if check['ok'] else 'FAILED'}: {check['name']}: {check['message']}")
    print(f"Created: {len(report['created'])} files. Kept: {len(report['kept'])} files.")
    if not report["library_git"]:
        print("Warning: the library is not in a git repository. Library commits are disabled.")


@cli.command("link")
def link_cmd(args):
    from . import init
    info = init.ensure_link()
    if args.json:
        cli.emit(info, True)
        return
    print(f"{info['path']} -> {info['target']}" + (" (updated)" if info["changed"] else ""))
    if not info["on_path"]:
        print(f"Warning: {init.link_dir()} is not in PATH.")


@cli.command("menu")
def menu_cmd(args):
    from . import menu, repo
    model = menu.build(repo.load_ctx(task_opt=args.task))
    if args.json:
        cli.emit(model, True)
    else:
        print(menu.render(model))


@cli.command("version check")
def version_check(args):
    from . import repo, version
    cli.emit(version.report(repo.load_ctx(task_opt=args.task)), args.json)


@cli.command("pipeline check")
def pipeline_check_cmd(args):
    from . import pipeline_check, repo
    from .registry import Registry
    ctx = repo.load_ctx(task_opt=args.task)
    reg = Registry.load(ctx)
    pipeline = reg.pipeline(args.id)
    problems = pipeline_check.check(reg, pipeline.data, ctx.columns(), pipeline.level)
    if args.json:
        cli.emit([p.to_dict() for p in problems], True)
    elif not problems:
        print(f"Pipeline `{args.id}`: no problem.")
    else:
        for p in problems:
            print(f"{p.level.upper()}: {p.message}")
    return 1 if pipeline_check.errors(problems) else 0


def ctx_of(args):
    from . import repo
    return repo.load_ctx(task_opt=args.task)


def task_of(args):
    from . import repo
    ctx = ctx_of(args)
    return ctx, repo.current_task_id(ctx)


@cli.command("config get")
def config_get(args):
    from . import config
    value = config.get_value(ctx_of(args), args.step, args.key)
    if value is None:
        raise FactoryError(f"`{args.step}.{args.key}` is not set.")
    print(value)


@cli.command("config set")
def config_set(args):
    from . import config
    config.set_value(ctx_of(args), args.step, args.key, args.value)
    print(f"Saved `{args.step}.{args.key}`.")


@cli.command("state get")
def state_get(args):
    from . import state
    ctx, tid = task_of(args)
    value = state.get_key(ctx, tid, args.key)
    cli.emit(value, args.json) if args.json else print(value)


@cli.command("state set")
def state_set(args):
    from . import state
    ctx, tid = task_of(args)
    state.set_key(ctx, tid, args.key, args.value)
    print(f"Saved `{args.key}`.")


@cli.command("artifact path")
def artifact_path_cmd(args):
    from . import state
    ctx, tid = task_of(args)
    print(state.artifact_path(ctx, tid, args.name))


@cli.command("approve")
def approve_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.approve(ctx, tid, args.send))


@cli.command("request-changes")
def request_changes_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.request_changes(ctx, tid, args.text, args.send))


@cli.command("approval check")
def approval_check_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    ok = engine.approval_check(ctx, tid)
    print("Approved." if ok else "Not approved yet.")
    return 0 if ok else 1


@cli.command("open-ide")
def open_ide_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print("Opened: " + " ".join(engine.open_ide(ctx, tid)))


@cli.command("wait")
def wait_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.wait(ctx, tid))


@cli.command("poll")
def poll_cmd(args):
    from . import engine
    results = engine.poll(ctx_of(args))
    if args.json:
        cli.emit(results, True)
        return
    if not results:
        print("No task waits on a done check.")
    for r in results:
        print(f"{r['id']}: " + ("the wait ended." if r["ended"] else "still waiting."))


@cli.command("external-done")
def external_done_cmd(args):
    from . import engine
    engine.external_done(ctx_of(args), args.id)
    print(f"Task {args.id}: the external event is marked done.")
