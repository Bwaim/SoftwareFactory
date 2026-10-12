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


if args[:2] == ["worktree", "open"]:
    print(json.dumps({"result": {"workspace": {"workspace_id": "w9"}, "tab": {"tab_id": "w9:t1"}, "root_pane": pane}}))
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
    print("Quick safety check: Is this a project you created or one you trust?\n Yes, I trust this folder" if mode == "trust" else "ready")
elif args[:2] == ["agent", "get"]:
    if mode == "gone":
        print(json.dumps({"error": {"code": "agent_not_found"}}))
        sys.exit(1)
    print(json.dumps({"result": {"agent": {"name": args[2], "agent_status": "idle"}}}))
else:
    print(json.dumps({"result": {"type": "ok"}}))
