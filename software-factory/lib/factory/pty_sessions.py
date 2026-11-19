import base64
import fcntl
import json
import os
import pty
import signal
import struct
import subprocess
import sys
import termios
import threading
import time

from .errors import FactoryError

BUFFER_BYTES = 256 * 1024
READ_BYTES = 64 * 1024
INPUT_MAX = 16 * 1024
HEARTBEAT_SECONDS = 15
IDLE_CLOSE_SECONDS = 30
STOP_WAIT_SECONDS = 2
REAP_SECONDS = 5
MAX_SESSIONS = 8
COLS = (20, 500)
ROWS = (5, 300)
# Runs in the new child, before the real program: it makes the pty the controlling terminal, which subprocess cannot do.
# Without a controlling terminal the program never gets SIGWINCH, so a resize in the browser is not redrawn.
# os.forkpty would do it too, but it runs Python code between fork and exec in this threaded server, which can deadlock.
LAUNCHER = (
    "import fcntl, os, sys, termios\n"
    "os.setsid()\n"
    "fcntl.ioctl(0, termios.TIOCSCTTY, 0)\n"
    "try:\n"
    "    os.execvp(sys.argv[1], sys.argv[1:])\n"
    "except OSError as e:\n"
    "    sys.stderr.write(f'Could not start {sys.argv[1]}: {e}\\n')\n"
    "    sys.exit(127)\n"
)


def check_size(cols, rows):
    if not (isinstance(cols, int) and isinstance(rows, int) and COLS[0] <= cols <= COLS[1] and ROWS[0] <= rows <= ROWS[1]):
        raise FactoryError(f"The terminal size must be {COLS[0]} to {COLS[1]} columns and {ROWS[0]} to {ROWS[1]} rows.")


def set_size(fd, cols, rows):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def line(**fields):
    return (json.dumps(fields) + "\n").encode()


class Session:
    """One program running in a pseudo-terminal. Many viewers can stream its output; the last BUFFER_BYTES are replayed to a new viewer."""

    def __init__(self, argv, cols, rows):
        master, slave = pty.openpty()
        set_size(master, cols, rows)
        try:
            self.proc = subprocess.Popen(
                [sys.executable, "-I", "-c", LAUNCHER, *argv], stdin=slave, stdout=slave, stderr=slave, close_fds=True,
                env={**os.environ, "TERM": "xterm-256color"},
            )
        except OSError as e:
            os.close(master)
            raise FactoryError(f"Could not start the terminal: {e}")
        finally:
            os.close(slave)
        self.master = master
        self.cond = threading.Condition()
        self.buffer = bytearray()
        self.end = 0
        self.closed = False
        self.watchers = 0
        self.idle_since = time.time()
        threading.Thread(target=self.pump, daemon=True).start()

    def pump(self):
        while True:
            try:
                data = os.read(self.master, READ_BYTES)
            except OSError:
                data = b""
            with self.cond:
                if not data:
                    self.closed = True
                    self.poll()
                    self.cond.notify_all()
                    return
                self.buffer += data
                self.end += len(data)
                del self.buffer[:max(0, len(self.buffer) - BUFFER_BYTES)]
                self.cond.notify_all()

    def stream(self):
        """Output as JSON lines: {"d": base64} for bytes, {"h": 1} as a heartbeat, {"closed": true} at the end."""
        with self.cond:
            self.watchers += 1
            pos = self.end - len(self.buffer)
        try:
            while True:
                with self.cond:
                    if pos >= self.end and not self.closed:
                        self.cond.wait(HEARTBEAT_SECONDS)
                    start = self.end - len(self.buffer)
                    chunk = bytes(self.buffer[max(pos, start) - start:])
                    pos = self.end
                    closed = self.closed
                if chunk:
                    yield line(d=base64.b64encode(chunk).decode())
                elif closed:
                    yield line(closed=True, code=self.poll())
                    return
                else:
                    yield line(h=1)
        finally:
            with self.cond:
                self.watchers -= 1
                self.idle_since = time.time()

    def write(self, data):
        if not isinstance(data, str) or not data or len(data) > INPUT_MAX:
            raise FactoryError(f"Send `data` as a text of 1 to {INPUT_MAX} characters.")
        if self.closed:
            raise FactoryError("The terminal has ended. Open it again.")
        os.write(self.master, data.encode())

    def resize(self, cols, rows):
        check_size(cols, rows)
        if not self.closed:
            set_size(self.master, cols, rows)

    def idle(self, now):
        with self.cond:
            return self.closed or (self.watchers == 0 and now - self.idle_since > IDLE_CLOSE_SECONDS)

    def poll(self):
        """The exit code of the program, or None while it runs."""
        return self.proc.poll()

    def signal(self, sig):
        try:
            os.killpg(self.proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass

    def stop(self):
        if self.poll() is None:
            self.signal(signal.SIGTERM)
            try:
                self.proc.wait(STOP_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                self.signal(signal.SIGKILL)
                self.proc.wait()
        try:
            os.close(self.master)
        except OSError:
            pass


class Registry:
    def __init__(self):
        self.lock = threading.Lock()
        self.sessions = {}
        self.reaper = None

    def open(self, key, argv, cols, rows):
        """The live session for key, started with argv when there is none. Returns (session, started)."""
        check_size(cols, rows)
        with self.lock:
            current = self.sessions.get(key)
            if current and not current.closed:
                current.resize(cols, rows)
                return current, False
            if len([s for s in self.sessions.values() if not s.closed]) >= MAX_SESSIONS:
                raise FactoryError(f"Too many open terminals (at most {MAX_SESSIONS}). Close one first.")
            session = self.sessions[key] = Session(argv, cols, rows)
            if self.reaper is None:
                self.reaper = threading.Thread(target=self.reap_loop, daemon=True)
                self.reaper.start()
            return session, True

    def get(self, key):
        with self.lock:
            session = self.sessions.get(key)
        if session is None:
            raise FactoryError("The terminal is not open. Open it again.")
        return session

    def close(self, key):
        with self.lock:
            session = self.sessions.pop(key, None)
        if session:
            session.stop()

    def reap(self, now=None):
        now = now or time.time()
        with self.lock:
            done = [k for k, s in self.sessions.items() if s.idle(now)]
            stopped = [self.sessions.pop(k) for k in done]
        for session in stopped:
            session.stop()

    def reap_loop(self):
        while True:
            time.sleep(REAP_SECONDS)
            self.reap()

    def close_all(self):
        with self.lock:
            stopped, self.sessions = list(self.sessions.values()), {}
        for session in stopped:
            session.stop()


REGISTRY = Registry()
