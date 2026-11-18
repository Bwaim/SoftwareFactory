import functools
import http.server
import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from conftest import PROJECT_ROOT

INSTALL = PROJECT_ROOT / "install.sh"
BUILD = PROJECT_ROOT / "scripts" / "build-release.sh"
DIGEST_NAME = "software-factory.tar.gz.sha256"


class Release:
    def __init__(self, folder, port):
        self.folder = folder
        self.port = port

    def write_digest(self, text):
        (self.folder / DIGEST_NAME).write_text(text)

    def remove_digest(self):
        (self.folder / DIGEST_NAME).unlink()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture
def release(work):
    folder = work / "dl"
    r = subprocess.run(["sh", str(BUILD), "0.1.0", str(folder)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    handler = functools.partial(QuietHandler, directory=str(folder))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield Release(folder, server.server_address[1])
    server.shutdown()
    server.server_close()


def write_stub(path, body):
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)


def uv_dir(*args):
    return subprocess.run(["uv", *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def env(work, release):
    tools = work / "tools"
    tools.mkdir()
    sha = "shasum" if shutil.which("shasum") else "sha256sum"
    for name in ("uv", "git", "curl", "tar", "gzip", sha):
        (tools / name).symlink_to(shutil.which(name))
    fake = work / "fake bin"
    fake.mkdir()
    write_stub(fake / "claude", "exit 0")
    home = work / "home dir"
    home.mkdir()
    return {
        "HOME": str(home),
        "PATH": os.pathsep.join([str(fake), str(tools), "/usr/bin", "/bin"]),
        "UV_CACHE_DIR": uv_dir("cache", "dir"),
        "UV_PYTHON_INSTALL_DIR": uv_dir("python", "dir"),
        "FACTORY_INSTALL_DOWNLOAD_BASE": f"http://127.0.0.1:{release.port}",
        "FACTORY_INSTALL_PROTO": "=http",
    }


def run_install(env):
    return subprocess.run(
        ["/bin/sh", str(INSTALL)], env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )


def test_fresh_install(release, env):
    r = run_install(env)
    home = Path(env["HOME"])
    target = home / ".local/share/software-factory"
    assert r.returncode == 0, r.stderr
    assert (target / ".installed-by-script").exists()
    assert os.readlink(home / ".local/bin/factory") == str(target / "bin/factory")
    assert f"Installed factory 0.1.0 in {target}." in r.stdout
    v = subprocess.run([str(home / ".local/bin/factory"), "--version"], capture_output=True, text=True, env=env)
    assert "factory 0.1.0" in v.stdout


def test_install_through_pipe(release, env):
    script = INSTALL.read_text()
    r = subprocess.run(["/bin/sh"], input=script, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (Path(env["HOME"]) / ".local/share/software-factory/.installed-by-script").exists()
    assert "Installed factory 0.1.0" in r.stdout


def test_missing_claude_stops(release, env, work):
    (work / "fake bin/claude").unlink()
    r = run_install(env)
    assert r.returncode == 1
    assert "factory install: claude is required." in r.stderr
    assert not (Path(env["HOME"]) / ".local/share/software-factory").exists()


def test_missing_herdr_warns(release, env):
    r = run_install(env)
    assert r.returncode == 0
    assert "factory install: herdr is not on PATH. Tasks need it to start. Install it from https://herdr.dev" in r.stderr


def test_path_warning(release, env):
    r = run_install(env)
    assert f"Add {Path(env['HOME']) / '.local/bin'} to your PATH." in r.stdout


def test_digest_mismatch_installs_nothing(release, env):
    release.write_digest("0" * 64 + "  software-factory.tar.gz\n")
    r = run_install(env)
    assert r.returncode == 1
    assert ("factory install: The downloaded archive SHA-256 differs from the release digest. "
            "The existing install is unchanged.") in r.stderr
    assert not (Path(env["HOME"]) / ".local/share/software-factory").exists()


@pytest.mark.parametrize("digest", [None, "", "abc  software-factory.tar.gz\n", "z" * 64 + "\n"])
def test_bad_digest_file_refused(release, env, digest):
    release.remove_digest() if digest is None else release.write_digest(digest)
    r = run_install(env)
    assert r.returncode == 1
    assert "factory install: The latest release has no valid software-factory.tar.gz.sha256." in r.stderr
    assert not (Path(env["HOME"]) / ".local/share/software-factory").exists()
