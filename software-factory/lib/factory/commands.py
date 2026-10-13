import sys

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
    ps.add_parser("list", parents=[common])
    pe = ps.add_parser("edit", parents=[common]); pe.add_argument("id", nargs="?")
    p = sub.add_parser("step")
    sts = p.add_subparsers(dest="action", required=True)
    sl = sts.add_parser("list", parents=[common]); sl.add_argument("--all", action="store_true")
    sts.add_parser("hide", parents=[common]).add_argument("id")
    sts.add_parser("unhide", parents=[common]).add_argument("id")
    sh = sts.add_parser("show", parents=[common]); sh.add_argument("id")
    sd = sts.add_parser("delete", parents=[common]); sd.add_argument("id"); sd.add_argument("--level", choices=["local", "generic"]); sd.add_argument("--dry-run", action="store_true")
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
    for name in ("next", "done", "skip", "run-command"):
        sub.add_parser(name, parents=[common])
    p = sub.add_parser("goto", parents=[common]); p.add_argument("step_path"); p.add_argument("--reason", required=True)
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
    tt = ts.add_parser("start-session", parents=[common])
    tt.add_argument("name"); tt.add_argument("cwd"); tt.add_argument("prompt")
    tc = ts.add_parser("close", parents=[common]); tc.add_argument("handle")
    tg = ts.add_parser("state", parents=[common]); tg.add_argument("handle")
    tw = ts.add_parser("wait-idle", parents=[common]); tw.add_argument("handle"); tw.add_argument("--timeout", type=float, default=3600)
    tn = ts.add_parser("notify", parents=[common]); tn.add_argument("text")
    p = sub.add_parser("delete", parents=[common])
    p.add_argument("id")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm-unpushed", action="store_true")
    sub.add_parser("clean", parents=[common])
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
    p = sub.add_parser("backlog")
    bs = p.add_subparsers(dest="action", required=True)
    bs.add_parser("list", parents=[common])
    a = bs.add_parser("add", parents=[common]); a.add_argument("title"); a.add_argument("--summary", default=""); a.add_argument("--pipeline", default=None)
    r = bs.add_parser("remove", parents=[common]); r.add_argument("id")
    m = bs.add_parser("move", parents=[common]); m.add_argument("id"); m.add_argument("--to", type=int, required=True)
    i = bs.add_parser("import", parents=[common]); i.add_argument("--file", default=None); i.add_argument("--dry-run", action="store_true")
    sub.add_parser("menu", parents=[common])
    p = sub.add_parser("migrate", parents=[common]); p.add_argument("--dry-run", action="store_true")
    sub.add_parser("serve", parents=[common])
    sub.add_parser("dashboard", parents=[common])
    p = sub.add_parser("server")
    svs = p.add_subparsers(dest="action", required=True)
    svs.add_parser("stop", parents=[common])
    p = sub.add_parser("catalog")
    cts = p.add_subparsers(dest="action", required=True)
    cts.add_parser("list", parents=[common])
    ci = cts.add_parser("install", parents=[common])
    ci.add_argument("id")
    where = ci.add_mutually_exclusive_group(required=True)
    where.add_argument("--generic", action="store_true")
    where.add_argument("--local", action="store_true")
    ci.add_argument("--with-steps", action="store_true")
    ci.add_argument("--replace", action="store_true")
    ci.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("library")
    ls = p.add_subparsers(dest="action", required=True)
    lc = ls.add_parser("commit", parents=[common]); lc.add_argument("message"); lc.add_argument("paths", nargs="+")


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


@cli.command("goto")
def goto_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.goto(ctx, tid, args.step_path, args.reason))


@cli.command("skip")
def skip_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print(engine.skip(ctx, tid))


@cli.command("run-command")
def run_command_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    return engine.run_command(ctx, tid)


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


def adapter_of(args):
    from . import adapters
    return adapters.get_adapter(ctx_of(args))


def parse_handle(text):
    import json
    try:
        handle = json.loads(text)
    except json.JSONDecodeError:
        raise FactoryError("The handle must be JSON, as printed by `factory terminal start-session`.")
    if not isinstance(handle, dict):
        raise FactoryError("The handle must be a JSON object.")
    return handle


@cli.command("terminal start-session")
def terminal_start_session(args):
    handle = adapter_of(args).start_session(args.name, args.cwd, args.prompt, args.passthrough)
    cli.emit(handle, True)


@cli.command("terminal close")
def terminal_close(args):
    adapter_of(args).close(parse_handle(args.handle))
    print("Closed.")


@cli.command("terminal state")
def terminal_state(args):
    print(adapter_of(args).state(parse_handle(args.handle)))


@cli.command("terminal wait-idle")
def terminal_wait_idle(args):
    adapter_of(args).wait_idle(parse_handle(args.handle), args.timeout)
    print("Idle.")


@cli.command("terminal notify")
def terminal_notify(args):
    adapter_of(args).notify(args.text)
    print("Notification sent.")


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
    cli.emit(task, True) if args.json else print(f"Task {task['id']} started. Worktree: {task['worktree']}")


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


@cli.command("clean")
def clean_cmd(args):
    from . import delete
    rows = delete.clean_report(ctx_of(args))
    if args.json:
        cli.emit(rows, True)
        return
    if not rows:
        print("No finished task.")
    for r in rows:
        mark = "[x]" if r["selected"] else "[ ]"
        print(f"{mark} {r['id']}: {r['description']} ({r['reason']})")


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
    from . import hidden, pipeline_check, repo
    from .registry import Registry
    ctx = repo.load_ctx(task_opt=args.task)
    reg = Registry.load(ctx)
    pipeline = reg.pipeline(args.id)
    problems = pipeline_check.check(reg, pipeline.data, ctx.columns(), pipeline.level, hidden.ids(ctx))
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
    from . import engine
    ctx, tid = task_of(args)
    engine.set_state(ctx, tid, args.key, args.value)
    print(f"Saved `{args.key}`.")


@cli.command("artifact path")
def artifact_path_cmd(args):
    from . import state
    ctx, tid = task_of(args)
    print(state.artifact_path(ctx, tid, args.name))


def print_delivery(message, delivery_error):
    print(message)
    if delivery_error:
        print(f"Warning: the prompt was not delivered to the session: {delivery_error}", file=sys.stderr)


@cli.command("approve")
def approve_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print_delivery(*engine.approve(ctx, tid, args.send))


@cli.command("request-changes")
def request_changes_cmd(args):
    from . import engine
    ctx, tid = task_of(args)
    print_delivery(*engine.request_changes(ctx, tid, args.text, args.send))


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
        print(f"{r['id']}: " + ("the wait ended." if r["ended"] else "still waiting.") + (f" Error: {r['error']}" if r["error"] else ""))


@cli.command("external-done")
def external_done_cmd(args):
    from . import engine
    engine.external_done(ctx_of(args), args.id)
    print(f"Task {args.id}: the external event is marked done.")


def print_entries(entries, as_json):
    if as_json:
        cli.emit([e.to_dict() for e in entries], True)
        return
    if not entries:
        print("The backlog is empty.")
    for n, e in enumerate(entries, 1):
        pipeline = f" [{e.pipeline}]" if e.pipeline else ""
        print(f"{n}. {e.title}{pipeline} (id {e.id})")


@cli.command("backlog list")
def backlog_list(args):
    from . import backlog
    print_entries(backlog.list_entries(ctx_of(args)), args.json)


@cli.command("backlog add")
def backlog_add(args):
    from . import backlog
    e = backlog.add(ctx_of(args), args.title, args.summary, args.pipeline)
    if args.json:
        cli.emit(e.to_dict(), True)
    else:
        print(f"Added {e.title} (id {e.id}).")


@cli.command("backlog remove")
def backlog_remove(args):
    from . import backlog
    e = backlog.remove(ctx_of(args), args.id)
    print(f"Removed {e.title}.")


@cli.command("backlog move")
def backlog_move(args):
    from . import backlog
    print_entries(backlog.move(ctx_of(args), args.id, args.to), args.json)


@cli.command("backlog import")
def backlog_import(args):
    import sys
    from pathlib import Path
    from . import backlog
    text = Path(args.file).read_text() if args.file else sys.stdin.read()
    titles = backlog.parse_import(text)
    if args.dry_run:
        cli.emit(titles, True) if args.json else print("\n".join(titles))
        return
    print_entries(backlog.import_titles(ctx_of(args), titles), args.json)


@cli.command("serve")
def serve_cmd(args):
    from . import server
    server.Server(ctx_of(args)).run()


@cli.command("dashboard")
def dashboard_cmd(args):
    from . import server
    info = server.ensure_server(ctx_of(args))
    url = server.page_url(info, "dashboard")
    server.open_page(url)
    print(f"Dashboard: {url}")


@cli.command("server stop")
def server_stop_cmd(args):
    from . import server
    print("Server stopped." if server.stop_server(ctx_of(args)) else "The server was not running.")


@cli.command("pipeline list")
def pipeline_list_cmd(args):
    from . import pipeline_store
    from .registry import Registry
    rows = pipeline_store.list_pipelines(Registry.load(ctx_of(args)))
    if args.json:
        cli.emit(rows, True)
        return
    for r in rows:
        print(f"{r['id']} ({r['level']}): {r['description']}")


@cli.command("pipeline edit")
def pipeline_edit_cmd(args):
    from . import server
    info = server.ensure_server(ctx_of(args))
    url = server.page_url(info, "editor", **({"id": args.id} if args.id else {}))
    server.open_page(url)
    print(f"Pipeline editor: {url}")


@cli.command("step list")
def step_list_cmd(args):
    from . import hidden, pipeline_store
    from .registry import Registry
    ctx = ctx_of(args)
    hidden_ids = set(hidden.ids(ctx))
    steps = sorted(Registry.load(ctx).steps.values(), key=lambda s: s.id)
    rows = [pipeline_store.step_summary(s, hidden_ids) for s in steps if args.all or s.id not in hidden_ids]
    if args.json:
        cli.emit(rows, True)
        return
    for r in rows:
        mark = ", hidden" if r["hidden"] else ""
        print(f"{r['id']} [{r['category']}] ({r['level']}, {r['run_in']}{mark}): {r['description']}")


@cli.command("step show")
def step_show_cmd(args):
    from . import hidden, pipeline_store
    from .registry import Registry
    ctx = ctx_of(args)
    reg = Registry.load(ctx)
    detail = pipeline_store.step_detail(reg, reg.step(args.id), set(hidden.ids(ctx)))
    if args.json:
        cli.emit(detail, True)
    else:
        print(f"{detail['path']}{' (hidden)' if detail['hidden'] else ''}\n\n{detail['body']}")


@cli.command("step hide")
def step_hide_cmd(args):
    from . import hidden
    print(hidden.hide(ctx_of(args), args.id))


@cli.command("step unhide")
def step_unhide_cmd(args):
    from . import hidden
    print(hidden.unhide(ctx_of(args), args.id))


@cli.command("step delete")
def step_delete_cmd(args):
    from . import step_delete
    ctx = ctx_of(args)
    result = step_delete.plan(ctx, args.id, args.level) if args.dry_run else step_delete.delete(ctx, args.id, args.level)
    if args.json:
        cli.emit(result, True)
    else:
        print(step_delete.render(result, args.dry_run))


@cli.command("library commit")
def library_commit_cmd(args):
    from . import library
    sha = library.commit(ctx_of(args), args.message, args.paths)
    print(f"Committed {sha[:10]}. Not pushed.")


@cli.command("catalog list")
def catalog_list_cmd(args):
    from . import catalog
    rows = catalog.items(ctx_of(args))
    if args.json:
        cli.emit(rows, True)
        return
    for r in rows:
        where = f" ({r['location']})" if r["location"] else ""
        missing = f" Missing: {', '.join(r['missing_requires'])}." if r["missing_requires"] else ""
        print(f"{r['kind']} {r['id']} [{r['category']}]: {r['description']}. {r['status']}{where}.{missing}")


@cli.command("catalog install")
def catalog_install_cmd(args):
    from . import catalog
    target = "generic" if args.generic else "local"
    result = catalog.install(ctx_of(args), args.id, target, args.with_steps, args.replace, args.dry_run)
    if args.json:
        cli.emit(result, True)
        return
    for path in result["written"] or result["files"]:
        print(path)
    if result["missing_steps"] and not args.with_steps:
        print("Steps not installed: " + ", ".join(result["missing_steps"]) + ". Add --with-steps to install them.")


@cli.command("migrate")
def migrate_cmd(args):
    from . import migrate, repo
    result = migrate.migrate(repo.load_ctx(task_opt=args.task), args.dry_run)
    if args.json:
        cli.emit(result, True)
        return
    print(f"Repository data: version {result['repo']['from']} -> {result['current']}" if result["repo"]["migrate"] else "Repository data: up to date.")
    print(f"Library: version {result['library']['from']} -> {result['current']}" if result["library"]["migrate"] else "Library: up to date.")
    for b in result["backups"]:
        print(f"Backup: {b}")
