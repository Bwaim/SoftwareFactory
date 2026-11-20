#!/usr/bin/env python3
"""Stand-in for tmux, open and osascript: logs each call and keeps the live sessions in a JSON file."""
import json
import os
import sys

log = os.environ["FAKE_TMUX_LOG"]
sessions_file = log + ".sessions"
tool, args = sys.argv[1], sys.argv[2:]
entry = [tool, *args]
if tool == "tmux" and "load-buffer" in args:
    entry.append({"stdin": sys.stdin.read()})
with open(log, "a") as f:
    f.write(json.dumps(entry) + "\n")
if tool != "tmux":
    sys.exit(int(os.environ.get(f"FAKE_{tool.upper()}_EXIT", "0")))


def load():
    if not os.path.exists(sessions_file):
        return []
    with open(sessions_file) as f:
        return json.load(f)


def save(names):
    with open(sessions_file, "w") as f:
        json.dump(names, f)


def option(name):
    return args[args.index(name) + 1] if name in args else None


def target():
    return (option("-t") or "").lstrip("=")


if args[:2] != ["-L", "captn"]:
    sys.stderr.write("expected the captn socket\n")
    sys.exit(2)
command, args = args[2], args[3:]
names = load()
if command == "has-session":
    sys.exit(0 if target() in names else 1)
if command == "new-session":
    if os.environ.get("FAKE_TMUX_EXITS") != "1":
        save(names + [option("-s")])
elif command == "kill-session":
    save([n for n in names if n != target()])
elif command == "rename-session":
    save([args[-1] if n == target() else n for n in names])
elif command == "capture-pane":
    sys.stdout.write(os.environ.get("FAKE_TMUX_SCREEN", "> \n"))
elif command == "list-clients":
    sys.stdout.write(os.environ.get("FAKE_TMUX_CLIENTS", ""))
elif command == "display-message":
    sys.stdout.write(os.environ.get("FAKE_TMUX_PATH", "/tmp") + "\n")
elif command in ("send-keys", "load-buffer", "paste-buffer"):
    if command != "load-buffer" and target() not in names:
        sys.stderr.write("can't find session\n")
        sys.exit(1)
else:
    sys.stderr.write(f"unknown command {command}\n")
    sys.exit(1)
