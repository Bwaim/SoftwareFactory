import functools
import http.server
import os
import shutil
import subprocess
import sys
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
    # A new session has no controlling terminal, so the script cannot read /dev/tty and asks nothing.
    return subprocess.run(
        ["/bin/sh", str(INSTALL)], env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, start_new_session=True,
    )


def run_with_answers(env, work, *answers):
    path = work / "answers"
    path.write_text("".join(a + "\n" for a in answers))
    return run_install({**env, "FACTORY_INSTALL_TTY": str(path)})


def saved_terminal(env):
    path = Path(env["HOME"]) / ".config/software-factory/terminal"
    return path.read_text().strip() if path.exists() else None


macos_only = pytest.mark.skipif(sys.platform != "darwin", reason="Warp is offered on macOS only")


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
    r = subprocess.run(["/bin/sh"], input=script, env=env, capture_output=True, text=True, start_new_session=True)
    assert r.returncode == 0, r.stderr
    assert (Path(env["HOME"]) / ".local/share/software-factory/.installed-by-script").exists()
    assert "Installed factory 0.1.0" in r.stdout


def test_missing_claude_stops(release, env, work):
    (work / "fake bin/claude").unlink()
    r = run_install(env)
    assert r.returncode == 1
    assert "factory install: claude is required." in r.stderr
    assert not (Path(env["HOME"]) / ".local/share/software-factory").exists()


def test_no_terminal_tool_warns_without_a_terminal_to_ask(release, env):
    r = run_install({**env, "FACTORY_INSTALL_WARP_APP": "/nonexistent/Warp.app"})
    assert r.returncode == 0
    assert "factory install: No terminal tool found. Tasks need Herdr (https://herdr.dev)" in r.stderr
    assert saved_terminal(env) is None


def test_herdr_found_without_a_terminal_saves_nothing(release, env, work):
    write_stub(work / "fake bin/herdr", "exit 0")
    r = run_install(env)
    assert r.returncode == 0 and "terminal tool" not in r.stderr and saved_terminal(env) is None


def test_terminal_from_the_environment(release, env):
    r = run_install({**env, "FACTORY_INSTALL_TERMINAL": "herdr"})
    assert saved_terminal(env) == "herdr"
    assert "factory install: herdr is not on PATH. Tasks need it to start. Install it from https://herdr.dev" in r.stderr


def test_missing_git_warns(release, env, work):
    usr = work / "usr bin"
    usr.mkdir()
    for tool in Path("/usr/bin").iterdir():
        if tool.name != "git":
            (usr / tool.name).symlink_to(tool)
    (work / "tools/git").unlink()
    r = run_install({**env, "PATH": env["PATH"].replace("/usr/bin", str(usr))})
    assert r.returncode == 0, r.stderr
    assert "factory install: git is not installed. Only pipelines with `worktree: false` can run." in r.stderr


def test_bad_terminal_from_the_environment_stops(release, env):
    r = run_install({**env, "FACTORY_INSTALL_TERMINAL": "kitty"})
    assert r.returncode == 1 and "factory install: FACTORY_INSTALL_TERMINAL must be herdr or warp." in r.stderr


@macos_only
def test_asks_and_keeps_the_herdr_already_installed(release, env, work):
    write_stub(work / "fake bin/herdr", "exit 0")
    r = run_with_answers({**env, "FACTORY_INSTALL_WARP_APP": "/nonexistent/Warp.app"}, work, "")
    assert r.returncode == 0, r.stderr
    assert "1) Herdr (found)" in r.stdout and "Choice [1]: " in r.stdout
    assert saved_terminal(env) == "herdr" and "Install Herdr" not in r.stdout


@macos_only
def test_asks_and_keeps_the_warp_already_installed(release, env, work):
    (work / "Warp.app").mkdir()
    write_stub(work / "fake bin/tmux", "exit 0")
    r = run_with_answers({**env, "FACTORY_INSTALL_WARP_APP": str(work / "Warp.app")}, work, "2")
    assert r.returncode == 0, r.stderr
    assert "2) Warp (found), with tmux" in r.stdout and "Choice [2]: " in r.stdout
    assert saved_terminal(env) == "warp" and "needed for tasks" not in r.stderr


@macos_only
def test_none_installed_asks_which_to_install(release, env, work):
    r = run_with_answers({**env, "FACTORY_INSTALL_WARP_APP": "/nonexistent/Warp.app"}, work, "3", "2")
    assert r.returncode == 0, r.stderr
    assert "Which one would you like to install to use with CAPTN?" in r.stdout
    assert "Install Warp later: https://www.warp.dev" in r.stdout and "Install tmux later: brew install tmux" in r.stdout
    assert saved_terminal(env) == "warp"
    assert "factory install: Warp and tmux are needed for tasks." in r.stderr


@macos_only
def test_declined_herdr_install_is_not_run(release, env, work):
    r = run_with_answers({**env, "FACTORY_INSTALL_WARP_APP": "/nonexistent/Warp.app"}, work, "3", "1", "n")
    assert r.returncode == 0, r.stderr
    assert "Install Herdr now with its install script" in r.stdout and "Install Herdr later from https://herdr.dev" in r.stdout
    assert saved_terminal(env) == "herdr"


@macos_only
def test_accepted_brew_installs_run_brew(release, env, work):
    log = work / "brew.log"
    write_stub(work / "fake bin/brew", f'echo "$@" >> "{log}"')
    r = run_with_answers({**env, "FACTORY_INSTALL_WARP_APP": "/nonexistent/Warp.app"}, work, "3", "2", "y", "")
    assert r.returncode == 0, r.stderr
    assert log.read_text().splitlines() == ["install --cask warp", "install tmux"]


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


def test_second_run_updates(release, env):
    assert run_install(env).returncode == 0
    target = Path(env["HOME"]) / ".local/share/software-factory"
    (target / "old-file").write_text("x")
    r = run_install(env)
    assert r.returncode == 0, r.stderr
    assert not (target / "old-file").exists()
    assert not list(target.parent.glob("software-factory.*"))


def test_failed_swap_restores_old_install(release, env, work):
    assert run_install(env).returncode == 0
    target = Path(env["HOME"]) / ".local/share/software-factory"
    (target / "old-file").write_text("x")
    log = work / "mv.log"
    write_stub(work / "fake bin/mv", f'''printf '%s|%s\\n' "$1" "$2" >> '{log}'
case "$1" in *.stage.*) [ "$2" = '{target}' ] && exit 1;; esac
exec /bin/mv "$@"''')
    assert run_install(env).returncode == 1
    assert (target / "old-file").exists()
    assert not list(target.parent.glob("software-factory.*"))
    calls = log.read_text().splitlines()
    to_backup = next(i for i, c in enumerate(calls) if c.startswith(f"{target}|") and ".backup." in c)
    failed = next(i for i, c in enumerate(calls) if ".stage." in c.split("|")[0] and c.endswith(f"|{target}"))
    assert to_backup < failed


def test_interrupted_run_restores_backup(release, env):
    share = Path(env["HOME"]) / ".local/share"
    backup = share / "software-factory.backup.111"
    backup.mkdir(parents=True)
    (backup / ".installed-by-script").write_text("")
    (backup / "old-file").write_text("x")
    (share / "software-factory.stage.222").mkdir()
    r = run_install(env)
    assert r.returncode == 0, r.stderr
    assert f"Restored the previous install from {backup}." in r.stdout
    assert not list(share.glob("software-factory.*"))


def test_leftovers_removed_when_install_exists(release, env):
    assert run_install(env).returncode == 0
    share = Path(env["HOME"]) / ".local/share"
    (share / "software-factory.backup.111").mkdir()
    (share / "software-factory.stage.222").mkdir()
    assert run_install(env).returncode == 0
    assert not list(share.glob("software-factory.*"))


def test_user_folder_with_similar_name_kept(release, env):
    share = Path(env["HOME"]) / ".local/share"
    user = share / "software-factory.backup.old"
    user.mkdir(parents=True)
    (user / ".installed-by-script").write_text("")
    r = run_install(env)
    assert r.returncode == 0, r.stderr
    assert user.exists()
    assert "Restored the previous install" not in r.stdout


def test_unmanaged_folder_refused(release, env):
    target = Path(env["HOME"]) / ".local/share/software-factory"
    target.mkdir(parents=True)
    r = run_install(env)
    assert r.returncode == 1
    assert (f"factory install: {target} exists and was not made by this script. "
            "Move it away, then run again.") in r.stderr


def test_link_file_refused(release, env):
    link = Path(env["HOME"]) / ".local/bin/factory"
    link.parent.mkdir(parents=True)
    link.write_text("x")
    r = run_install(env)
    assert r.returncode == 1
    assert f"factory install: {link} exists and is not a link. Move it away, then run again." in r.stderr


def test_link_to_other_target_replaced(release, env, work):
    link = Path(env["HOME"]) / ".local/bin/factory"
    link.parent.mkdir(parents=True)
    link.symlink_to(work / "plugin-cache/bin/factory")
    r = run_install(env)
    assert r.returncode == 0
    assert f"Replaced the link {link}, it pointed to {work / 'plugin-cache/bin/factory'}." in r.stdout
    assert os.readlink(link).endswith("software-factory/bin/factory")
