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
    r = subprocess.run(["sh", str(BUILD), "0.2.0", str(folder)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    handler = functools.partial(QuietHandler, directory=str(folder))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield Release(folder, server.server_address[1])
    server.shutdown()
    server.server_close()


FAKE_SWIFTC = '''while [ "$1" != "-o" ]; do shift; done
printf '#!/bin/sh\\n' > "$2"
chmod +x "$2"'''


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
    write_stub(fake / "xcode-select", "exit 0")
    write_stub(fake / "swiftc", FAKE_SWIFTC)
    write_stub(fake / "codesign", "exit 0")
    write_stub(fake / "curl", f'''url=""
for a in "$@"; do case "$a" in http*) url=$a;; esac; done
case "$url" in http://127.0.0.1*) exec "{tools}/curl" "$@";; esac
echo "$url" >> "{work}/curl.log"
echo "${{CURL_STUB_SCRIPT:-echo installer}}"''')
    home = work / "home dir"
    home.mkdir()
    return {
        "HOME": str(home),
        "PATH": os.pathsep.join([str(fake), str(tools), "/usr/bin", "/bin"]),
        "UV_CACHE_DIR": uv_dir("cache", "dir"),
        "UV_PYTHON_INSTALL_DIR": uv_dir("python", "dir"),
        "FACTORY_INSTALL_DOWNLOAD_BASE": f"http://127.0.0.1:{release.port}",
        "FACTORY_INSTALL_PROTO": "=http",
        "FACTORY_INSTALL_OS": "Darwin",
        "FACTORY_INSTALL_ARM64": "1",
        "FACTORY_INSTALL_BREW_PATHS": "/nonexistent/brew",
        "FACTORY_INSTALL_WARP_APP": "/nonexistent/Warp.app",
        "FACTORY_LSREGISTER": "",
        "FACTORY_DASHBOARD_APP": str(work / "CAPTN Dashboard.app"),
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


def test_fresh_install(release, env, work):
    r = run_install(env)
    home = Path(env["HOME"])
    target = home / ".local/share/software-factory"
    assert r.returncode == 0, r.stderr
    assert (target / ".installed-by-script").exists()
    assert os.readlink(home / ".local/bin/factory") == str(target / "bin/factory")
    assert f"Installed factory 0.2.0 in {target}." in r.stdout
    v = subprocess.run([str(home / ".local/bin/factory"), "--version"], capture_output=True, text=True, env=env)
    assert "factory 0.2.0" in v.stdout
    if sys.platform == "darwin":
        assert f"Dashboard app: {work / 'CAPTN Dashboard.app'}" in r.stdout
        assert (work / "CAPTN Dashboard.app").is_dir()


def test_dashboard_app_build_failure_warns(release, env, work):
    write_stub(work / "fake bin/swiftc", "exit 1")
    r = run_install(env)
    assert r.returncode == 0, r.stderr
    assert "factory install: The dashboard app did not build. Run factory app install to see why." in r.stderr
    assert "Dashboard app: " not in r.stdout


def test_linux_install_skips_dashboard_app(release, env):
    r = run_install({**env, "FACTORY_INSTALL_OS": "Linux"})
    assert r.returncode == 0, r.stderr
    assert "Dashboard app:" not in r.stdout + r.stderr


def test_install_through_pipe(release, env):
    script = INSTALL.read_text()
    r = subprocess.run(["/bin/sh"], input=script, env=env, capture_output=True, text=True, start_new_session=True)
    assert r.returncode == 0, r.stderr
    assert (Path(env["HOME"]) / ".local/share/software-factory/.installed-by-script").exists()
    assert "Installed factory 0.2.0" in r.stdout


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


def test_asks_and_keeps_the_herdr_already_installed(release, env, work):
    write_stub(work / "fake bin/herdr", "exit 0")
    r = run_with_answers(env, work, "", "")
    assert r.returncode == 0, r.stderr
    assert "1) Herdr (found)" in r.stdout and "Choice [1]: " in r.stdout
    assert saved_terminal(env) == "herdr" and "Install Herdr" not in r.stdout


def test_asks_and_keeps_the_warp_already_installed(release, env, work):
    (work / "Warp.app").mkdir()
    write_stub(work / "fake bin/tmux", "exit 0")
    r = run_with_answers({**env, "FACTORY_INSTALL_WARP_APP": str(work / "Warp.app")}, work, "2", "")
    assert r.returncode == 0, r.stderr
    assert "2) Warp (found), with tmux" in r.stdout and "Choice [2]: " in r.stdout
    assert saved_terminal(env) == "warp" and "needed for tasks" not in r.stderr


def test_none_installed_asks_which_to_install(release, env, work):
    r = run_with_answers(env, work, "3", "2", "")
    assert r.returncode == 0, r.stderr
    assert "Which one would you like to install to use with CAPTN?" in r.stdout
    assert saved_terminal(env) == "warp"


def test_list_apple_silicon_herdr(release, env, work):
    r = run_with_answers(env, work, "1", "")
    assert "CAPTN needs these tools. [x] means that the script installs it." in r.stdout
    assert ("Mandatory\n"
            "  1) [ ] Xcode Command Line Tools (found): git, and swiftc for Warp notifications\n"
            "  2) [x] Homebrew: installs the other tools\n"
            "  3) [ ] uv (found): runs the factory (Python)\n"
            "  4) [ ] Claude Code (found): runs each task\n"
            "  5) [x] Herdr: shows each task in a tab\n"
            "Optional\n"
            "  6) [ ] gh: GitHub steps of the catalog\n"
            "  7) [ ] glab: GitLab steps of the catalog\n") in r.stdout


def test_list_warp_has_warp_and_tmux(release, env, work):
    r = run_with_answers(env, work, "2", "")
    assert "  5) [x] Warp: shows each task in a tab\n  6) [x] tmux: keeps each task session running\n" in r.stdout


def test_list_intel_herdr_moves_homebrew_to_optional(release, env, work):
    r = run_with_answers({**env, "FACTORY_INSTALL_ARM64": "0"}, work, "1", "")
    assert "  4) [x] Herdr: shows each task in a tab\nOptional\n  5) [ ] Homebrew: installs the other tools\n" in r.stdout
    assert "  6) [ ] gh: GitHub steps of the catalog (brew builds it from source)\n" in r.stdout


def test_list_linux_without_git(release, env, work):
    (work / "tools/git").unlink()
    usr = work / "usr bin"
    usr.mkdir()
    for tool in Path("/usr/bin").iterdir():
        if tool.name != "git":
            (usr / tool.name).symlink_to(tool)
    r = run_with_answers({**env, "FACTORY_INSTALL_OS": "Linux", "PATH": env["PATH"].replace("/usr/bin", str(usr))}, work, "")
    assert "Which one do you already have?" not in r.stdout
    assert "  1) [ ] git (install it with your package manager): task worktrees\n" in r.stdout
    assert "  2) [ ] Homebrew (needs git): installs the other tools\n" in r.stdout
    assert "Warp" not in r.stdout and "Xcode" not in r.stdout


def test_toggle_numbers(release, env, work):
    r = run_with_answers(env, work, "1", "6 2", "")
    assert "  2) [ ] Homebrew: installs the other tools\n" in r.stdout
    assert "  6) [x] gh: GitHub steps of the catalog\n" in r.stdout


def test_same_number_twice_keeps_the_state(release, env, work):
    r = run_with_answers(env, work, "1", "6 6", "")
    assert r.stdout.count("  6) [ ] gh: GitHub steps of the catalog\n") == 2


@pytest.mark.parametrize("bad", ["abc", "0", "99", "1"])
def test_bad_or_found_number_refused(release, env, work, bad):
    r = run_with_answers(env, work, "1", bad, "")
    assert f"Item {bad} cannot be changed." in r.stdout


def test_end_of_answers_confirms_the_list(release, env, work):
    r = run_with_answers(env, work, "1")
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("Type numbers to change, Enter to install: ") == 1


def test_terminal_from_the_environment_still_shows_the_list(release, env, work):
    r = run_with_answers({**env, "FACTORY_INSTALL_TERMINAL": "herdr"}, work, "")
    assert "Which one do you already have?" not in r.stdout and "  5) [x] Herdr" in r.stdout


def brew_stub(work):
    brew = work / "brew/bin/brew"
    brew.parent.mkdir(parents=True)
    write_stub(brew, f'''echo "$@" >> "{work}/brew.log"
[ "$1" = shellenv ] && echo 'export PATH="{brew.parent}:$PATH"'
exit 0''')
    return brew


def brew_log(work):
    log = work / "brew.log"
    return [line for line in log.read_text().splitlines() if line != "shellenv"] if log.exists() else []


def hide_command(work, name):
    for folder in ("fake bin", "tools"):
        path = work / folder / name
        if path.exists() or path.is_symlink():
            path.unlink()


def test_selected_brew_items_install_in_order(release, env, work):
    brew = brew_stub(work)
    r = run_with_answers({**env, "FACTORY_INSTALL_BREW_PATHS": str(brew)}, work, "2", "7", "")
    assert r.returncode == 0, r.stderr
    assert brew_log(work) == ["install --cask warp", "install tmux", "install gh"]


def test_homebrew_install_runs_the_official_script(release, env, work):
    run_with_answers(env, work, "1", "")
    assert "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh" in (work / "curl.log").read_text()


def test_brew_items_without_homebrew_print_install_later(release, env, work):
    r = run_with_answers(env, work, "1", "2", "")
    assert "Install Herdr later: brew install herdr" in r.stdout
    assert saved_terminal(env) == "herdr"


def test_failed_homebrew_install_continues(release, env, work):
    r = run_with_answers({**env, "CURL_STUB_SCRIPT": "exit 1"}, work, "1", "")
    assert r.returncode == 0, r.stderr
    assert "factory install: The Homebrew install failed." in r.stderr
    assert "Install Herdr later: brew install herdr" in r.stdout


def test_intel_mac_uses_the_official_scripts(release, env, work):
    for name in ("uv", "claude"):
        hide_command(work, name)
    run_with_answers({**env, "FACTORY_INSTALL_ARM64": "0"}, work, "1", "")
    urls = (work / "curl.log").read_text()
    assert "https://astral.sh/uv/install.sh" in urls
    assert "https://claude.ai/install.sh" in urls and "https://herdr.dev/install.sh" in urls


def test_uv_script_does_not_edit_shell_files(release, env, work):
    hide_command(work, "uv")
    write_stub(work / "fake bin/env", f'echo "$@" >> "{work}/env.log"')
    run_with_answers({**env, "FACTORY_INSTALL_ARM64": "0"}, work, "1", "")
    assert "UV_NO_MODIFY_PATH=1 sh" in (work / "env.log").read_text()


def test_command_line_tools_install_waits_for_enter(release, env, work):
    write_stub(work / "fake bin/xcode-select", f'[ "$1" = -p ] && exit 2; echo "$@" >> "{work}/xcode.log"')
    r = run_with_answers(env, work, "1", "", "")
    assert (work / "xcode.log").read_text().strip() == "--install"
    assert "Finish the Command Line Tools install in its window, then press Enter. " in r.stdout


def test_unselected_uv_stops_before_the_factory(release, env, work):
    hide_command(work, "uv")
    r = run_with_answers(env, work, "1", "3", "")
    assert r.returncode == 1 and "factory install: uv is required." in r.stderr


def test_everything_found_installs_nothing(release, env, work):
    brew = brew_stub(work)
    for name in ("herdr", "gh", "glab"):
        write_stub(work / f"fake bin/{name}", "exit 0")
    r = run_with_answers({**env, "FACTORY_INSTALL_BREW_PATHS": str(brew)}, work, "1", "")
    assert ") [x]" not in r.stdout and brew_log(work) == []
    assert not (work / "curl.log").exists()


def test_brew_path_line_when_brew_is_not_on_path(release, env, work):
    brew = brew_stub(work)
    r = run_with_answers({**env, "FACTORY_INSTALL_BREW_PATHS": str(brew)}, work, "1", "")
    assert f'Add this line to ~/.zprofile: eval "$({brew} shellenv)"' in r.stdout


def test_second_run_finds_tools_off_the_user_path(release, env, work):
    brew = brew_stub(work)
    hide_command(work, "uv")
    (brew.parent / "uv").symlink_to(shutil.which("uv"))
    write_stub(brew.parent / "herdr", "exit 0")
    hide_command(work, "claude")
    local_bin = Path(env["HOME"]) / ".local/bin"
    local_bin.mkdir(parents=True)
    write_stub(local_bin / "claude", "exit 0")
    r = run_with_answers({**env, "FACTORY_INSTALL_BREW_PATHS": str(brew)}, work, "", "")
    assert r.returncode == 0, r.stderr
    assert "1) Herdr (found)" in r.stdout
    assert "  3) [ ] uv (found)" in r.stdout and "  4) [ ] Claude Code (found)" in r.stdout
    assert brew_log(work) == []


def test_installer_that_installs_nothing_is_reported(release, env, work):
    r = run_with_answers({**env, "CURL_STUB_SCRIPT": ""}, work, "1", "")
    assert "factory install: The Homebrew install failed." in r.stderr


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
