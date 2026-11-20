import http.client
import json
import os
import time
from pathlib import Path

GLOBAL = ("/api/ping", "/api/shutdown", "/api/jobs/", "/api/workspaces", "/api/host", "/api/server-settings", "/api/update")


def home():
    return Path(os.environ["FACTORY_HOME"])


def info(fdir=None):
    from factory import workspaces
    data = json.loads((home() / "server.json").read_text())
    entry = workspaces.find_by_path(Path(fdir).parent) if fdir is not None else None
    return {**data, "ws": entry["id"]} if entry else data


def api_path(info, path):
    if info.get("ws") and path.startswith("/api/") and not path.startswith(GLOBAL):
        return f"/api/w/{info['ws']}/{path[len('/api/'):]}"
    return path


def request(info, method, path, body=None, token=True, origin=None, host=None):
    path = api_path(info, path)
    conn = http.client.HTTPConnection("127.0.0.1", info["port"], timeout=30)
    headers = {"Host": host or f"127.0.0.1:{info['port']}"}
    if token:
        headers["X-Factory-Token"] = info["token"] if token is True else token
    if origin:
        headers["Origin"] = origin
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=data, headers=headers)
    r = conn.getresponse()
    raw = r.read()
    try:
        return r.status, json.loads(raw)
    except json.JSONDecodeError:
        return r.status, raw.decode()


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def wait_dead(pid, seconds=10):
    end = time.time() + seconds
    while time.time() < end:
        if not alive(pid):
            return True
        time.sleep(0.2)
    return False
