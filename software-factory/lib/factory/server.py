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
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from . import adapters, api, fsio, repo
from .errors import FactoryError

IDLE_SECONDS = int(os.environ.get("FACTORY_SERVER_IDLE_SECONDS", "1800"))
START_TIMEOUT = 30
FALLBACK_POLL_SECONDS = 300
MAX_BODY_BYTES = 1024 * 1024
SERVER_INFO_MODE = 0o600
WEB_DIR = Path(__file__).resolve().parent / "web"
PAGES = {"/editor": "editor.html", "/dashboard": "dashboard.html"}


def info_path(ctx):
    return ctx.fdir / "server.json"


def read_info(ctx):
    return fsio.read_json(info_path(ctx))


class Server:
    def __init__(self, ctx):
        self.ctx = ctx
        self.token = secrets.token_urlsafe(24)
        self.last = time.time()
        self.jobs = {}
        try:
            adapter = adapters.get_adapter(ctx)
            ok, message = adapter.check()
            self.capabilities = sorted(adapter.capabilities()) if ok else []
        except Exception as e:
            ok, message, self.capabilities = False, str(e), []
        self.adapter = {"ok": ok, "message": message}
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self))
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]

    def origin(self):
        return f"http://127.0.0.1:{self.port}"

    def run(self):
        fsio.write_json(info_path(self.ctx), {"port": self.port, "token": self.token, "pid": os.getpid()})
        os.chmod(info_path(self.ctx), SERVER_INFO_MODE)
        threading.Thread(target=self.watch_idle, daemon=True).start()
        threading.Thread(target=self.poll_loop, daemon=True).start()
        try:
            self.httpd.serve_forever()
        finally:
            info = read_info(self.ctx)
            if info and info.get("pid") == os.getpid():
                info_path(self.ctx).unlink(missing_ok=True)

    def stop(self):
        threading.Thread(target=self.httpd.shutdown, daemon=True).start()

    def watch_idle(self):
        while True:
            time.sleep(min(30, IDLE_SECONDS))
            if time.time() - self.last > IDLE_SECONDS:
                self.stop()
                return

    def poll_seconds(self):
        override = os.environ.get("FACTORY_POLL_SECONDS")
        return int(override) if override else int(self.ctx.factory_yaml().get("poll_minutes", 5)) * 60

    def poll_interval(self):
        try:
            return self.poll_seconds()
        except Exception as e:
            print(f"poll interval fallback: {e}", file=sys.stderr, flush=True)
            return FALLBACK_POLL_SECONDS

    def poll_loop(self):
        from . import engine
        while True:
            time.sleep(self.poll_interval())
            try:
                engine.poll(self.ctx)
            except Exception as e:
                print(f"poll failed: {e}", file=sys.stderr, flush=True)

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
            if not url.path.startswith("/api/"):
                return self.reply(404, {"error": "Not found."})
            if not self.token_ok():
                return self.reply(401, {"error": "Missing or wrong token."})
            server.last = time.time()
            try:
                body = self.read_body() if method == "POST" else {}
                self.reply(200, api.dispatch(server, method, url.path, parse_qs(url.query), body))
            except api.NotFound:
                self.reply(404, {"error": "Not found."})
            except FactoryError as e:
                self.reply(400, {"error": str(e)})
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


def running(ctx):
    info = read_info(ctx)
    return info if info and pid_alive(info.get("pid")) and ping(info) else None


def ensure_server(ctx):
    info = running(ctx)
    if info:
        return info
    old_pid = (read_info(ctx) or {}).get("pid")
    with open(ctx.fdir / "server.log", "a") as log:
        child = subprocess.Popen(
            [sys.executable, str(repo.PLUGIN_ROOT / "bin" / "factory"), "serve"],
            cwd=ctx.main, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            start_new_session=True, close_fds=True,
        )
    deadline = time.time() + START_TIMEOUT
    while time.time() < deadline and child.poll() is None:
        info = read_info(ctx)
        if info and info.get("pid") != old_pid and ping(info):
            return info
        time.sleep(0.2)
    stop_child(ctx, child)
    raise FactoryError("The local server did not start. See .factory/server.log.")


def stop_child(ctx, child):
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
    if (read_info(ctx) or {}).get("pid") == child.pid:
        info_path(ctx).unlink(missing_ok=True)


def page_url(info, page, **params):
    return f"http://127.0.0.1:{info['port']}/{page}?" + urlencode({"token": info["token"], **params})


def open_page(url):
    if os.environ.get("FACTORY_NO_OPEN"):
        return
    subprocess.run(["open", url], check=False)


def stop_server(ctx):
    info = running(ctx)
    if not info:
        info_path(ctx).unlink(missing_ok=True)
        return False
    req = urllib.request.Request(
        f"http://127.0.0.1:{info['port']}/api/shutdown", data=b"{}", method="POST",
        headers={"X-Factory-Token": info["token"], "Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except (urllib.error.URLError, OSError):
        pass
    deadline = time.time() + 10
    while time.time() < deadline and pid_alive(info["pid"]):
        time.sleep(0.2)
    return True
