from . import adapters

ACTIONS = [
    ("Tasks", "launch", "Launch a new pipeline", None),
    ("Tasks", "show-tasks", "Show tasks", None),
    ("Tasks", "check-waiting", "Check waiting tasks", None),
    ("Tasks", "focus", "Focus a task", "focus"),
    ("Tasks", "send-prompt", "Send a prompt to a task", "send_prompt"),
    ("Tasks", "resume", "Resume a task", None),
    ("Tasks", "delete", "Delete a task", None),
    ("Tasks", "clean", "Clean finished tasks", None),
    ("Tasks", "exclusive-release", "Release a shared resource", None),
    ("Pipelines and steps", "pipeline-edit", "Create or edit a pipeline", None),
    ("Pipelines and steps", "new-step", "Create a new step", None),
    ("Pipelines and steps", "step-delete", "Delete a step", None),
    ("Pipelines and steps", "catalog", "Browse the catalog", None),
    ("Backlog", "backlog-add", "Add a backlog entry", None),
    ("Backlog", "backlog-remove", "Remove a backlog entry", None),
    ("Factory", "dashboard", "Open dashboard", None),
    ("Factory", "exit", "Exit", None),
]
INIT_ACTION = {"n": 1, "key": "init", "label": "Init the factory"}


def build(ctx):
    if not ctx.initialized():
        return {"initialized": False, "groups": [{"title": "Factory", "actions": [dict(INIT_ACTION)]}]}
    caps = adapters.get_adapter(ctx).capabilities()
    groups, n = [], 0
    for group, key, label, needs in ACTIONS:
        if needs and needs not in caps:
            continue
        if not groups or groups[-1]["title"] != group:
            groups.append({"title": group, "actions": []})
        n += 1
        groups[-1]["actions"].append({"n": n, "key": key, "label": label})
    return {"initialized": True, "groups": groups}


def render(model):
    lines = []
    for group in model["groups"]:
        lines.append(f"## {group['title']}")
        lines += [f"{a['n']}. {a['label']}" for a in group["actions"]]
        lines.append("")
    return "\n".join(lines).rstrip()
