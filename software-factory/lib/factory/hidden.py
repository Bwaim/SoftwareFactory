from . import fsio

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
