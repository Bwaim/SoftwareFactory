#!/usr/bin/env python3
import json
import os
import sys

log = os.environ["FAKE_HERDR_LOG"]
with open(log, "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\n")
args = sys.argv[1:]
mode = os.environ.get("FAKE_HERDR_MODE", "ok")
main = os.environ.get("FAKE_HERDR_MAIN", "")
pane = {"pane_id": "w9:p1", "workspace_id": "w9", "tab_id": "w9:t1"}


def option(name):
    return args[args.index(name) + 1] if name in args else None


def logged():
    with open(log) as f:
        return [json.loads(line) for line in f]


def main_workspace(workspace_id, linked=False):
    return {
        "workspace_id": workspace_id,
        "label": "main",
        "worktree": {"checkout_path": main, "is_linked_worktree": linked, "repo_root": main},
    }


def workspace_list():
    workspaces = [{"workspace_id": "w1", "label": "other"}]
    if os.environ.get("FAKE_HERDR_EXISTING_WS") == "1":
        workspaces.append(main_workspace("w5"))
    opened = any(call[:2] == ["worktree", "open"] for call in logged())
    if opened:
        workspaces.append({"workspace_id": "w9", "label": "wt", "worktree": {"checkout_path": "/wt", "is_linked_worktree": True, "repo_root": main}})
        if os.environ.get("FAKE_HERDR_EXTRA_WS") == "1":
            workspaces.append(main_workspace("w8"))
    return workspaces


if args[:2] in (["tab", "close"], ["workspace", "close"]) and (os.environ.get("FAKE_HERDR_CLOSE_FAILS") == "1" or os.environ.get("FAKE_HERDR_GONE") == "1" or os.environ.get("FAKE_HERDR_LIST_FAILS") == "1"):
    print(json.dumps({"error": {"code": "close_failed"}}))
    sys.exit(1)
elif args[:2] in (["tab", "list"], ["workspace", "list"]) and os.environ.get("FAKE_HERDR_LIST_FAILS") == "1":
    sys.exit(1)
elif args[:2] in (["tab", "list"], ["workspace", "list"]) and os.environ.get("FAKE_HERDR_GONE") == "1":
    print(json.dumps({"result": {"type": "tab_list" if args[0] == "tab" else "workspace_list", "tabs" if args[0] == "tab" else "workspaces": []}}))
elif args[:2] == ["worktree", "open"]:
    if os.environ.get("FAKE_HERDR_NO_TAB_ID") == "1":
        del pane["tab_id"]
    already_open = os.environ.get("FAKE_HERDR_ALREADY_OPEN") == "1"
    print(json.dumps({"result": {"already_open": already_open, "type": "worktree_opened", "workspace": {"workspace_id": "w9"}, "tab": {"tab_id": "w9:t1"}, "root_pane": pane}}))
elif args[:2] == ["tab", "list"]:
    ws = option("--workspace")
    tabs = []
    if ws == "w8":
        tabs.append({"tab_id": "w8:t1", "workspace_id": ws, "agent_status": os.environ.get("FAKE_HERDR_W8_STATUS", "unknown")})
    else:
        if ws in ("w9", "w7"):
            tabs.append({"tab_id": f"{ws}:t1", "workspace_id": ws, "agent_status": "idle"})
        if any(c[:2] == ["tab", "create"] for c in logged()) and ws not in ("w9", "w7"):
            tabs.append({"tab_id": f"{ws}:t2", "workspace_id": ws, "agent_status": "idle"})
        if os.environ.get("FAKE_HERDR_OTHER_TAB") == "1":
            tabs.append({"tab_id": f"{ws}:t9", "workspace_id": ws, "agent_status": "unknown"})
    forced = os.environ.get("FAKE_HERDR_TAB_LIST_OUTPUT")
    print(forced if forced else json.dumps({"result": {"type": "tab_list", "tabs": tabs}}))
elif args[:2] == ["workspace", "list"]:
    print(json.dumps({"result": {"type": "workspace_list", "workspaces": workspace_list()}}))
elif args[:2] == ["workspace", "create"]:
    created = {"pane_id": "w7:p1", "workspace_id": "w7", "tab_id": "w7:t1"}
    print(json.dumps({"result": {"workspace": {"workspace_id": "w7"}, "tab": {"tab_id": "w7:t1"}, "root_pane": created}}))
elif args[:2] == ["tab", "create"]:
    workspace_id = option("--workspace") or "w0"
    tab_pane = {"pane_id": f"{workspace_id}:p2", "workspace_id": workspace_id, "tab_id": f"{workspace_id}:t2"}
    print(json.dumps({"result": {"tab": {"tab_id": f"{workspace_id}:t2"}, "root_pane": tab_pane}}))
elif args[:2] == ["agent", "start"] and mode == "trust":
    print(json.dumps({"error": {"code": "agent_not_ready"}}))
    sys.exit(1)
elif args[:2] == ["agent", "read"]:
    screen = os.environ.get("FAKE_HERDR_SCREEN")
    print(screen if screen else "Quick safety check: Is this a project you created or one you trust?\n Yes, I trust this folder" if mode == "trust" else "ready")
elif args[:2] == ["agent", "get"]:
    name = args[2]
    started = [c for c in logged() if c[:3] == ["agent", "start", name]]
    present = bool(started) or name in os.environ.get("FAKE_HERDR_TAKEN", "").split(",") or os.environ.get("FAKE_HERDR_PRESENT") == "1"
    if mode == "gone" or not present:
        print(json.dumps({"error": {"code": "agent_not_found"}}))
        sys.exit(1)
    tab_id = os.environ.get("FAKE_HERDR_AGENT_TAB")
    if not tab_id:
        pane_id = started[-1][started[-1].index("--pane") + 1] if started else "w9:p1"
        tab_id = pane_id.replace(":p", ":t")
    print(json.dumps({"result": {"agent": {"name": name, "agent_status": "idle", "tab_id": tab_id, "workspace_id": tab_id.split(":")[0], "focused": os.environ.get("FAKE_HERDR_FOCUSED") == "1"}}}))
else:
    print(json.dumps({"result": {"type": "ok"}}))
