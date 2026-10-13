from . import fsio
from .errors import FactoryError
from .registry import Registry

KEY = "hidden_steps"


def path(ctx):
    return ctx.fdir / "factory.yaml"


def ids(ctx):
    return [str(i) for i in ctx.factory_yaml().get(KEY) or []]


def remove(data, sid):
    current = list(data.get(KEY) or [])
    if sid not in current:
        return False
    rest = [i for i in current if i != sid]
    if rest:
        data[KEY] = rest
    else:
        data.pop(KEY, None)
    return True


def discard(ctx, sid):
    if sid in ids(ctx):
        fsio.update_yaml(path(ctx), lambda data: remove(data, sid))


def hide(ctx, sid):
    if sid not in Registry.load(ctx).variants:
        raise FactoryError(f"The step `{sid}` does not exist.")

    def add(data):
        current = list(data.get(KEY) or [])
        if sid in current:
            return False
        data[KEY] = current + [sid]
        return True

    if sid in ids(ctx) or not fsio.update_yaml(path(ctx), add):
        return f"Step {sid} is already hidden."
    return f"Step {sid} is hidden."


def unhide(ctx, sid):
    if sid not in ids(ctx) or not fsio.update_yaml(path(ctx), lambda data: remove(data, sid)):
        return f"Step {sid} is not hidden."
    return f"Step {sid} is visible again."
