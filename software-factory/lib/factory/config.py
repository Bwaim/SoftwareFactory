from . import fsio


def config_path(ctx):
    return ctx.fdir / "config.yaml"


def saved_section(ctx, step_id):
    data = fsio.read_yaml(config_path(ctx), {}) or {}
    return data.get(step_id) or {}


def resolve(ctx, step, entry_with):
    saved = saved_section(ctx, step.id)
    values, missing = {}, []
    for key, spec in step.config_spec.items():
        if key in (entry_with or {}):
            values[key] = entry_with[key]
        elif key in saved:
            values[key] = saved[key]
        elif "default" in spec:
            values[key] = spec["default"]
        else:
            missing.append(key)
    return values, missing


def get_value(ctx, step_id, key):
    return saved_section(ctx, step_id).get(key)


def set_value(ctx, step_id, key, value):
    def change(data):
        section = data.get(step_id) or {}
        section[key] = value
        data[step_id] = section

    fsio.update_yaml(config_path(ctx), change)
