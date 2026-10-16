from . import events, fsio, state
from .errors import FactoryError
from .registry import Registry
from .step_format import EXCLUSIVE_RE

HANDOVER = {
    "next": "`{name}` is yours now. Run `factory next`.",
    "acquire": "`{name}` is yours now. Continue the step.",
}


def empty():
    return {"holder": None, "since": None, "queue": []}


def resource_dir(ctx):
    return ctx.fdir / "exclusive"


def resource_file(ctx, name):
    if not isinstance(name, str) or EXCLUSIVE_RE.fullmatch(name) is None:
        raise FactoryError(f"Invalid resource name `{name}`.")
    return resource_dir(ctx) / f"{name}.json"


def read(ctx, name):
    return {**empty(), **(fsio.read_json(resource_file(ctx, name)) or {})}


def change(ctx, name, fn):
    return fsio.update_json(resource_file(ctx, name), fn, default_factory=empty)


def resource_names(ctx):
    return sorted(p.stem for p in resource_dir(ctx).glob("*.json") if EXCLUSIVE_RE.fullmatch(p.stem))


def load_task(ctx, tid):
    try:
        return state.load(ctx, tid)
    except FactoryError:
        return None


def name_of(reg, task):
    entry = state.current_entry(task)
    step = reg.steps.get(entry["id"]) if entry else None
    return step.exclusive if step else None


def step_name(ctx, task):
    return name_of(Registry.load(ctx), task)


def log(ctx, tid, type, **details):
    task = load_task(ctx, tid)
    if task:
        events.log(ctx, tid, type, state.step_path_str(task), **details)


def wait_reason(name, holder):
    return f"Waiting for {name}, used by {holder or 'another task'}"


def prune(ctx, reg, data, name):
    tasks = {q["task"]: load_task(ctx, q["task"]) for q in data["queue"]}
    data["queue"] = [q for q in data["queue"] if tasks[q["task"]] and tasks[q["task"]]["status"] != "finished"
                     and name_of(reg, tasks[q["task"]]) == name]
    return tasks


def is_paused(tasks, tid):
    return tasks[tid]["status"] == "paused"


def grant(ctx, data, tid, mode, activate):
    data["holder"] = tid
    data["since"] = state.now()
    data["queue"] = [q for q in data["queue"] if q["task"] != tid]

    def fn(t):
        waited = t.pop("exclusive_wait", None)
        if activate or (waited and t["status"] == "waiting_external"):
            state.set_status(t, "active")
        if mode == "acquire":
            t.pop("exclusive_released", None)

    state.update(ctx, tid, fn)


def free(data):
    data["holder"] = None
    data["since"] = None


def claim(ctx, tid, name, mode):
    reg = Registry.load(ctx)

    def fn(data):
        if data["holder"] == tid:
            return True, None, False
        tasks = prune(ctx, reg, data, name)
        ahead = []
        for q in data["queue"]:
            if q["task"] == tid:
                break
            if not is_paused(tasks, q["task"]):
                ahead.append(q["task"])
        if data["holder"] is None and not ahead:
            grant(ctx, data, tid, mode, False)
            return True, None, False
        entry = next((q for q in data["queue"] if q["task"] == tid), None)
        joined = entry is None
        if joined:
            entry = {"task": tid, "since": state.now(), "mode": mode}
            data["queue"].append(entry)

        want = {"name": name, "mode": entry["mode"]}

        def wait(t):
            if t.get("exclusive_wait") == want and t["status"] == "waiting_external":
                return
            state.set_status(t, "waiting_external", wait_reason(name, data["holder"]))
            t["exclusive_wait"] = want

        state.update(ctx, tid, wait)
        return False, data["holder"], joined

    ok, holder, joined = change(ctx, name, fn)
    if joined:
        log(ctx, tid, "exclusive_wait", name=name, holder=holder)
    if not ok and holder is None:
        handover(ctx, name)
    return ok, holder


def handover(ctx, name):
    from . import engine
    reg = Registry.load(ctx)

    def fn(data):
        tasks = prune(ctx, reg, data, name)
        if data["holder"] is not None:
            return None
        pick = next((q for q in data["queue"] if not is_paused(tasks, q["task"])), None)
        if pick:
            grant(ctx, data, pick["task"], pick["mode"], True)
        return pick

    pick = change(ctx, name, fn)
    if pick is None:
        return None
    tid, mode = pick["task"], pick["mode"]
    log(ctx, tid, "exclusive_start", name=name, mode=mode)
    engine.deliver_quietly(ctx, tid, HANDOVER[mode].format(name=name))
    return tid


def release(ctx, tid, name, event=None):
    def fn(data):
        if data["holder"] != tid:
            return False
        free(data)
        return True

    freed = change(ctx, name, fn)
    if freed and event:
        log(ctx, tid, event, name=name)
    handover(ctx, name)
    return freed


def force_release(ctx, name, by=None):
    def fn(data):
        old = data["holder"]
        if old is None:
            raise FactoryError(f"`{name}` is free.")
        free(data)
        if load_task(ctx, old):
            state.update(ctx, old, lambda t: t.__setitem__("exclusive_released", name))
        return old

    old = change(ctx, name, fn)
    for tid in dict.fromkeys([old, by]):
        if tid:
            log(ctx, tid, "exclusive_forced", name=name, holder=old, by=by)
    handover(ctx, name)
    return old


def leave(ctx, tid, name):
    current = read(ctx, name)
    if current["holder"] != tid and all(q["task"] != tid for q in current["queue"]):
        return

    def fn(data):
        freed = data["holder"] == tid
        if freed:
            free(data)
        queued = any(q["task"] == tid for q in data["queue"])
        data["queue"] = [q for q in data["queue"] if q["task"] != tid]
        if queued and load_task(ctx, tid):
            def drop(t):
                if (t.get("exclusive_wait") or {}).get("name") == name:
                    t.pop("exclusive_wait")
            state.update(ctx, tid, drop)
        return freed

    if change(ctx, name, fn):
        handover(ctx, name)


def sync(ctx, tid):
    task = load_task(ctx, tid)
    current = name_of(Registry.load(ctx), task) if task else None
    for name in resource_names(ctx):
        if name != current:
            leave(ctx, tid, name)


def forget(ctx, tid):
    for name in resource_names(ctx):
        leave(ctx, tid, name)


def valid_holder(ctx, reg, tid, name):
    task = load_task(ctx, tid)
    if not task or task["status"] == "finished":
        return False
    return task["status"] == "paused" or name_of(reg, task) == name


def recheck(ctx):
    reg = Registry.load(ctx)
    out = []
    for name in resource_names(ctx):
        current = read(ctx, name)
        if current["holder"] is None and not current["queue"]:
            continue

        def fn(data):
            if data["holder"] and not valid_holder(ctx, reg, data["holder"], name):
                free(data)
            prune(ctx, reg, data, name)

        change(ctx, name, fn)
        if handover(ctx, name):
            out.append(name)
    return out


def task_info(ctx, task, reg=None):
    name = name_of(reg or Registry.load(ctx), task)
    if name is None:
        return None
    data = read(ctx, name)
    return {
        "name": name,
        "holder": data["holder"],
        "holds": data["holder"] == task["id"],
        "waiting": any(q["task"] == task["id"] for q in data["queue"]),
        "released": task.get("exclusive_released") == name,
        "paused": task["status"] == "paused",
    }


def holder_text(ctx, task):
    info = task_info(ctx, task)
    if info is None:
        return None
    name = info["name"]
    if info["holds"]:
        return f"Exclusive: `{name}`, held by this task"
    if info["waiting"]:
        used = f", used by `{info['holder']}`" if info["holder"] else ""
        return f"Exclusive: waiting for `{name}`{used}"
    if info["released"]:
        return f"Exclusive: `{name}`, released"
    return None


def task_status(ctx, tid):
    task = load_task(ctx, tid) if tid else None
    return task["status"] if task else None


def status_rows(ctx):
    reg = Registry.load(ctx)
    names = {s.exclusive for s in reg.steps.values() if s.exclusive} | set(resource_names(ctx))
    rows = []
    for name in sorted(names):
        data = read(ctx, name)
        rows.append({
            "name": name,
            "holder": data["holder"],
            "holder_status": task_status(ctx, data["holder"]),
            "queue": [{"task": q["task"], "status": task_status(ctx, q["task"]), "since": q["since"],
                       "mode": q["mode"]} for q in data["queue"]],
        })
    return rows
