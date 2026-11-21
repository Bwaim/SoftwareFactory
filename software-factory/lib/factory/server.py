import http.server
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from . import api, fsio, repo, runtime, server_settings, update, workspaces
from .errors import ExistsError, FactoryError

IDLE_SECONDS = int(os.environ.get("FACTORY_SERVER_IDLE_SECONDS", "1800"))
START_TIMEOUT = 30
MAX_BODY_BYTES = 1024 * 1024
SERVER_INFO_MODE = 0o600
WEB_DIR = Path(__file__).resolve().parent / "web"
START_WARNING = "Warning: the local server did not start, so done checks do not run. See {log}."
PAGES = {"/editor": "editor.html", "/dashboard": "dashboard.html"}
STATIC = {
    "/static/xterm.js": ("vendor/xterm/xterm.js", "text/javascript; charset=utf-8"),
    "/static/xterm.css": ("vendor/xterm/xterm.css", "text/css; charset=utf-8"),
    "/static/addon-fit.js": ("vendor/xterm/addon-fit.js", "text/javascript; charset=utf-8"),
}
UPDATE_ALLOWED = ("/api/update/run", "/api/update/close", "/api/shutdown")
UPDATE_RUNNING = "An update is running."


class UpdateRunning(FactoryError):
    def __init__(self):
        super().__init__(UPDATE_RUNNING)


def info_path():
    return workspaces.home() / "server.json"


def log_path():
    return workspaces.home() / "server.log"


def start_warning():
    return START_WARNING.format(log=log_path())


def read_info():
    return fsio.read_json(info_path())


def log(text):
    print(text, file=sys.stderr, flush=True)


def poll_interval():
    return server_settings.poll_seconds()


class Server:
    def __init__(self):
        self.token = secrets.token_urlsafe(24)
        self.last = time.time()
        self.jobs = {}
        self.next_poll = None
        self.wake = threading.Event()
        self.lock = threading.Lock()
        self.runtimes = {}
        self.library_commits = {}
        self.list_mtime = None
        self.updating = False
        self.active = 0
        self.idle = threading.Condition()
        self.checker = update.Checker()
        self.updater = update.Updater(self, self.checker)
        try:
            self.reload()
        except Exception as e:
            log(f"workspace list failed: {e}")
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self))
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]

    def origin(self):
        return f"http://127.0.0.1:{self.port}"

    def reload(self):
        with self.lock:
            list_mtime, entries = workspaces.mtime(), workspaces.list_all()
            added = [w for w in entries if w["id"] not in self.runtimes]
            self.runtimes = {w["id"]: runtime.Workspace(self, w) for w in entries}
            self.list_mtime = list_mtime
        self.stop_legacy_servers(added)

    def stop_legacy_servers(self, entries):
        for w in entries:
            try:
                stop_legacy(Path(w["path"]) / ".factory")
            except Exception as e:
                log(f"legacy server check failed for {w['id']}: {e}")

    def reload_if_changed(self):
        if workspaces.mtime() != self.list_mtime or any(w.error for w in self.snapshot()):
            return self.reload()
        with self.lock:
            for wid, ws in self.runtimes.items():
                if ws.stale():
                    self.runtimes[wid] = ws.rebuilt()

    def runtime(self, wid):
        with self.lock:
            return self.runtimes.get(wid)

    def snapshot(self):
        with self.lock:
            return list(self.runtimes.values())

    def fresh(self, wid):
        if self.runtime(wid) is None and workspaces.mtime() != self.list_mtime:
            self.reload()
        with self.lock:
            ws = self.runtimes.get(wid)
            if ws and ws.stale():
                ws = self.runtimes[wid] = ws.rebuilt()
            return ws

    def run(self):
        fsio.write_json(info_path(), {"port": self.port, "token": self.token, "pid": os.getpid()})
        os.chmod(info_path(), SERVER_INFO_MODE)
        self.checker.start()
        threading.Thread(target=self.watch_idle, daemon=True).start()
        threading.Thread(target=self.poll_loop, daemon=True).start()
        try:
            self.httpd.serve_forever()
        finally:
            from .pty_sessions import REGISTRY
            REGISTRY.close_all()
            info = read_info()
            if info and info.get("pid") == os.getpid():
                info_path().unlink(missing_ok=True)

    def stop(self):
        threading.Thread(target=self.httpd.shutdown, daemon=True).start()

    def replaced(self):
        return (read_info() or {}).get("pid") != os.getpid()

    def waiting(self):
        from . import engine
        self.reload_if_changed()
        return any(engine.waiting_checks(ws.ctx) for ws in self.snapshot() if not ws.error)

    def should_stop(self):
        if self.updater.ended() or (self.replaced() and not self.updater.holds()):
            return True
        return time.time() - self.last > IDLE_SECONDS and not self.waiting()

    def watch_idle(self):
        while True:
            time.sleep(min(30, IDLE_SECONDS))
            try:
                done = self.should_stop()
            except Exception as e:
                log(f"idle check failed: {e}")
                continue
            if done:
                self.stop()
                return

    def poll_loop(self):
        while True:
            interval = poll_interval()
            self.next_poll = time.time() + interval
            if self.wake.wait(interval):
                self.wake.clear()
                continue
            if self.updating:
                continue
            try:
                self.poll_all()
            except UpdateRunning:
                pass

    def reschedule(self):
        if not self.updating:
            self.wake.set()

    @contextmanager
    def activity(self):
        with self.idle:
            if self.updating:
                raise UpdateRunning()
            self.active += 1
        try:
            yield
        finally:
            with self.idle:
                self.active -= 1
                self.idle.notify_all()

    def pause_for_update(self, timeout=None):
        with self.idle:
            self.updating = True
            self.idle.wait_for(lambda: self.active == 0, timeout)

    def resume_after_update(self):
        with self.idle:
            self.updating = False
        self.wake.set()

    def poll_all(self):
        with self.activity():
            try:
                self.reload()
            except Exception as e:
                log(f"workspace list failed: {e}")
            for ws in self.snapshot():
                self.poll_one(ws)

    def poll_one(self, ws):
        from . import engine, rename
        if ws.error:
            log(f"poll failed for {ws.id}: {ws.error}")
            return
        try:
            engine.poll(ws.ctx)
            rename.apply_all_pending(ws.ctx)
        except Exception as e:
            log(f"poll failed for {ws.id}: {e}")

    def start_job(self, fn):
        job_id = secrets.token_hex(6)
        self.jobs[job_id] = {"status": "running"}

        def work():
            try:
                self.jobs[job_id] = {"status": "done", "result": fn()}
            except Exception as e:
                self.jobs[job_id] = {"status": "error", "error": str(e)}

        threading.Thread(target=work, daemon=True).start()
        return job_id


def make_handler(server):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def reply(self, code, body, content_type="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(data)

        def stream(self, lines):
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            try:
                for chunk in lines:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    server.last = time.time()
            except OSError:
                pass
            finally:
                lines.close()

        def token_ok(self):
            supplied = self.headers.get("X-Factory-Token", "")
            try:
                return secrets.compare_digest(supplied.encode("utf-8"), server.token.encode("utf-8"))
            except (UnicodeError, TypeError):
                return False

        def read_body(self):
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise FactoryError("Invalid Content-Length.")
            if length < 0 or length > MAX_BODY_BYTES:
                raise FactoryError("The request body is too large or has a bad length.")
            if length == 0:
                return {}
            try:
                body = json.loads(self.rfile.read(length))
            except ValueError:
                raise FactoryError("Invalid JSON body.")
            if not isinstance(body, dict):
                raise FactoryError("The JSON body must be an object.")
            return body

        def refusal(self):
            if self.headers.get("Host") != f"127.0.0.1:{server.port}":
                return "The Host header must be 127.0.0.1 and the server port."
            origin = self.headers.get("Origin")
            if origin is not None and origin != server.origin():
                return "The Origin header is not this server."
            return None

        def handle_request(self, method):
            why = self.refusal()
            if why:
                return self.reply(403, {"error": why})
            url = urlparse(self.path)
            if method == "GET" and url.path in PAGES:
                server.last = time.time()
                return self.reply(200, (WEB_DIR / PAGES[url.path]).read_bytes(), "text/html; charset=utf-8")
            if method == "GET" and url.path in STATIC:
                path, content_type = STATIC[url.path]
                return self.reply(200, (WEB_DIR / path).read_bytes(), content_type)
            if not url.path.startswith("/api/"):
                return self.reply(404, {"error": "Not found."})
            if not self.token_ok():
                return self.reply(401, {"error": "Missing or wrong token."})
            server.last = time.time()
            if method == "POST" and server.updating and url.path not in UPDATE_ALLOWED:
                return self.reply(409, {"error": UPDATE_RUNNING})
            try:
                body = self.read_body() if method == "POST" else {}
                result = api.dispatch(server, method, url.path, parse_qs(url.query), body)
                if isinstance(result, api.Stream):
                    return self.stream(result.lines)
                self.reply(200, result)
            except api.NotFound:
                self.reply(404, {"error": "Not found."})
            except KeyError as e:
                self.reply(400, {"error": f"Missing field: {e.args[0]}."})
            except (ExistsError, UpdateRunning) as e:
                self.reply(409, {"error": str(e)})
            except FactoryError as e:
                self.reply(400, {"error": str(e), **getattr(e, "details", {})})
            except Exception as e:
                self.reply(500, {"error": f"Internal error: {e}"})

        def do_GET(self):
            self.handle_request("GET")

        def do_POST(self):
            self.handle_request("POST")

    return Handler


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, TypeError):
        return False


def ping(info):
    req = urllib.request.Request(f"http://127.0.0.1:{info['port']}/api/ping", headers={"X-Factory-Token": info["token"]})
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def running():
    info = read_info()
    return info if info and pid_alive(info.get("pid")) and ping(info) else None


def ensure_server():
    with fsio.locked(info_path()):
        return running() or spawn_server([sys.executable, str(repo.PLUGIN_ROOT / "bin" / "factory"), "serve"])


def spawn_server(argv):
    old_pid = (read_info() or {}).get("pid")
    env = {k: v for k, v in os.environ.items() if k != "FACTORY_DOCK_APP"}
    home = workspaces.home()
    home.mkdir(parents=True, exist_ok=True)
    with open(log_path(), "a") as out:
        child = subprocess.Popen(
            argv, cwd=home, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
            start_new_session=True, close_fds=True, env=env,
        )
    deadline = time.time() + START_TIMEOUT
    while time.time() < deadline and child.poll() is None:
        info = read_info()
        if info and info.get("pid") != old_pid and ping(info):
            return info
        time.sleep(0.2)
    stop_child(child)
    raise FactoryError(f"The local server did not start. See {log_path()}.")


def keep_polling(ctx):
    try:
        workspaces.register(ctx.main)
    except Exception as e:
        print(f"Warning: {e}", file=sys.stderr)
    try:
        ensure_server()
    except Exception:
        print(start_warning(), file=sys.stderr)


def stop_child(child):
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    if (read_info() or {}).get("pid") == child.pid:
        info_path().unlink(missing_ok=True)


def page_url(info, page, **params):
    return f"http://127.0.0.1:{info['port']}/{page}?" + urlencode({"token": info["token"], **params})


def open_page(url):
    if os.environ.get("FACTORY_NO_OPEN"):
        return
    subprocess.run(["open", url], check=False)


def post_shutdown(info):
    req = urllib.request.Request(
        f"http://127.0.0.1:{info['port']}/api/shutdown", data=b"{}", method="POST",
        headers={"X-Factory-Token": info["token"], "Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except (urllib.error.URLError, OSError):
        pass


def stop_server():
    info = running()
    if not info:
        info_path().unlink(missing_ok=True)
        return False
    post_shutdown(info)
    deadline = time.time() + 10
    while time.time() < deadline and pid_alive(info["pid"]):
        time.sleep(0.2)
    return True


def stop_legacy(fdir):
    path = Path(fdir) / "server.json"
    try:
        info = fsio.read_json(path)
    except (OSError, ValueError):
        info = None
    try:
        live = isinstance(info, dict) and pid_alive(info.get("pid")) and ping(info)
    except KeyError:
        live = False
    if live:
        post_shutdown(info)
    path.unlink(missing_ok=True)
    return bool(live)


def waiting_checks():
    from . import engine
    ids = []
    for w in workspaces.list_all():
        try:
            ctx = runtime.load(w["path"])
        except Exception:
            continue
        ids += engine.waiting_checks(ctx)
    return ids
