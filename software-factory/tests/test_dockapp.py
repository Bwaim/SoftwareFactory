import os
import plistlib
import subprocess
import sys

import pytest

from factory import dockapp
from factory.errors import FactoryError

real_refresh = dockapp.refresh


@pytest.fixture
def mac(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")


def info(app):
    with open(app / "Contents" / "Info.plist", "rb") as f:
        return plistlib.load(f)


def test_install_builds_the_app(tools, mac, monkeypatch):
    compiles, _ = tools
    monkeypatch.setenv("UV", "/opt/uv/bin/uv")

    app = dockapp.install()

    assert app == dockapp.app_path()
    assert app.name == "CAPTN Dashboard.app"
    assert info(app)["CFBundleIdentifier"] == "com.captn.factory.dashboard"
    assert info(app)["CFBundleName"] == "CAPTN Dashboard"
    assert info(app)["CFBundleExecutable"] == "captn-dashboard"
    assert info(app)["CAPTNUv"] == "/opt/uv/bin/uv"
    assert info(app)["CAPTNFactory"] == str(dockapp.factory_path())
    assert info(app)["NSHighResolutionCapable"] is True
    assert compiles() == 1


def test_install_reuses_a_current_app(tools, mac, monkeypatch):
    compiles, _ = tools
    monkeypatch.setenv("UV", "/opt/uv/bin/uv")

    dockapp.install()
    dockapp.install()

    assert compiles() == 1


def test_new_uv_path_rebuilds(tools, mac, monkeypatch):
    compiles, _ = tools
    monkeypatch.setenv("UV", "/opt/uv/bin/uv")
    dockapp.install()

    monkeypatch.setenv("UV", "/other/uv")
    dockapp.install()

    assert compiles() == 2
    assert info(dockapp.app_path())["CAPTNUv"] == "/other/uv"


def test_symlinked_uv_keeps_link_path(tools, mac, monkeypatch, tmp_path):
    target = tmp_path / "cellar" / "uv"
    target.parent.mkdir()
    target.write_text("#!/bin/sh\n")
    target.chmod(0o755)
    link_dir = tmp_path / "linkbin"
    link_dir.mkdir()
    (link_dir / "uv").symlink_to(target)
    monkeypatch.setenv("PATH", f"{link_dir}:{os.environ['PATH']}")
    monkeypatch.delenv("UV", raising=False)

    dockapp.install()

    assert info(dockapp.app_path())["CAPTNUv"] == str(link_dir / "uv")


def test_install_without_uv_fails(tools, mac, monkeypatch):
    monkeypatch.delenv("UV", raising=False)

    with pytest.raises(FactoryError, match="^Cannot find uv.$"):
        dockapp.install()

    assert not dockapp.app_path().exists()


def test_install_without_swiftc_fails(mac, monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("UV", "/opt/uv/bin/uv")

    with pytest.raises(FactoryError, match="swiftc` and `codesign"):
        dockapp.install()


def test_install_needs_macos(tools, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")

    with pytest.raises(FactoryError, match="^The dashboard app needs macOS.$"):
        dockapp.install()


def test_failed_build_shows_the_compiler_output(tools, mac, monkeypatch, capsys):
    monkeypatch.setenv("UV", "/opt/uv/bin/uv")
    monkeypatch.setenv("FAKE_SWIFTC_EXIT", "1")
    monkeypatch.setenv("FAKE_SWIFTC_STDERR", "boom")

    with pytest.raises(FactoryError, match="did not build"):
        dockapp.install()

    assert "boom" in capsys.readouterr().err


def test_refresh_does_nothing_when_not_installed(tools, mac, monkeypatch):
    compiles, _ = tools
    monkeypatch.setenv("UV", "/opt/uv/bin/uv")

    dockapp.refresh()

    assert compiles() == 0


def test_refresh_rebuilds_a_stale_app(tools, mac, monkeypatch):
    compiles, _ = tools
    monkeypatch.setenv("UV", "/opt/uv/bin/uv")
    dockapp.install()

    monkeypatch.setenv("UV", "/other/uv")
    dockapp.refresh()

    assert compiles() == 2


def test_refresh_rebuilds_a_stale_stamp(tools, mac, monkeypatch):
    compiles, _ = tools
    monkeypatch.setenv("UV", "/opt/uv/bin/uv")
    app = dockapp.install()
    plist = app / "Contents" / "Info.plist"
    data = info(app)
    data["CAPTNBuildStamp"] = "old"
    with open(plist, "wb") as f:
        plistlib.dump(data, f)

    dockapp.refresh()

    assert compiles() == 2
    assert info(app)["CAPTNFactory"] == str(dockapp.factory_path())


def test_refresh_leaves_an_app_of_another_factory(tools, mac, monkeypatch, tmp_path):
    compiles, _ = tools
    monkeypatch.setenv("UV", "/opt/uv/bin/uv")
    app = dockapp.install()
    monkeypatch.setattr(dockapp, "factory_path", lambda: tmp_path / "other" / "bin" / "factory")

    dockapp.refresh()

    assert compiles() == 1
    assert info(app)["CAPTNFactory"] != str(tmp_path / "other" / "bin" / "factory")


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_app_install_command_prints_path(factory, tools):
    fake = {k: os.environ[k] for k in ("PATH", "FAKE_PYTHON", "FAKE_TOOLS_LOG", "FAKE_APP_LOG")}

    r = factory("app", "install", env={"UV": "/opt/uv/bin/uv", **fake})

    assert f"Dashboard app: {dockapp.app_path()}" in r.stdout
    assert "Drag it to the Dock to keep it there." in r.stdout


@pytest.fixture
def dash(monkeypatch):
    from factory import commands, server
    calls = []
    monkeypatch.delenv("FACTORY_NO_OPEN", raising=False)
    monkeypatch.delenv("FACTORY_DOCK_APP", raising=False)
    monkeypatch.setattr(commands, "current_workspace", lambda: {})
    monkeypatch.setattr(server, "ensure_server", lambda: {"port": 1})
    monkeypatch.setattr(server, "page_url", lambda info, page, **ws: "http://127.0.0.1:1/dashboard")
    monkeypatch.setattr(server, "open_page", lambda url: calls.append(("page", url)))
    monkeypatch.setattr(dockapp, "refresh", lambda: calls.append(("refresh",)))
    monkeypatch.setattr(dockapp, "installed", lambda: True)
    monkeypatch.setattr(dockapp, "open_url", lambda url: calls.append(("app", url)))
    return commands.dashboard_cmd, calls


def test_dashboard_opens_the_app_when_installed(dash, capsys):
    run, calls = dash

    run(None)

    assert calls == [("refresh",), ("app", "http://127.0.0.1:1/dashboard")]
    assert "Dashboard: http://127.0.0.1:1/dashboard" in capsys.readouterr().out


def test_dashboard_opens_the_browser_without_the_app(dash, monkeypatch):
    run, calls = dash
    monkeypatch.setattr(dockapp, "installed", lambda: False)

    run(None)

    assert calls == [("refresh",), ("page", "http://127.0.0.1:1/dashboard")]


@pytest.mark.parametrize("name", ["FACTORY_NO_OPEN", "FACTORY_DOCK_APP"])
def test_dashboard_quiet_skips_rebuild_and_open(dash, monkeypatch, capsys, name):
    run, calls = dash
    monkeypatch.setenv(name, "1")

    run(None)

    assert calls == []
    assert "Dashboard: " in capsys.readouterr().out


def test_dashboard_opens_app_when_rebuild_fails(dash, monkeypatch):
    run, calls = dash
    monkeypatch.setattr(dockapp, "refresh", real_refresh)

    def fail():
        calls.append(("install",))
        raise FactoryError("no")

    monkeypatch.setattr(dockapp, "uv_path", lambda: "/opt/uv/bin/uv")
    monkeypatch.setattr(dockapp, "current", lambda uv: False)
    monkeypatch.setattr(dockapp, "ours", lambda: True)
    monkeypatch.setattr(dockapp, "install", fail)

    run(None)

    assert calls.count(("install",)) == 1
    assert calls == [("install",), ("app", "http://127.0.0.1:1/dashboard")]


def test_server_does_not_inherit_the_dock_app_flag(factory_home, monkeypatch):
    from factory import server
    factory_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FACTORY_DOCK_APP", "1")
    envs = []

    class Exited:
        pid = -1

        def poll(self):
            return 1

    def popen(argv, **kwargs):
        envs.append(kwargs.get("env"))
        return Exited()

    monkeypatch.setattr(server.subprocess, "Popen", popen)

    with pytest.raises(FactoryError, match="did not start"):
        server.ensure_server()

    assert envs and envs[0] is not None
    assert "FACTORY_DOCK_APP" not in envs[0]
    assert envs[0]["FACTORY_HOME"] == str(factory_home)


def swiftc_found():
    try:
        return subprocess.run(["xcrun", "--find", "swiftc"], capture_output=True).returncode == 0
    except OSError:
        return False


@pytest.mark.skipif(not swiftc_found(), reason="needs swiftc")
def test_swift_source_compiles():
    r = subprocess.run(["xcrun", "swiftc", "-typecheck", str(dockapp.SOURCE)], capture_output=True, text=True)

    assert r.returncode == 0, r.stderr


APP_TEXTS = [
    "Starting the factory…",
    '"Server stopped"',
    '"Start"',
    '"Try again"',
    '"Quitting CAPTN Dashboard stops the factory server."',
    '"Quit"',
    '"Cancel"',
    '"Don\'t show again"',
    '"Tasks wait on a done check: \\(ids). Quitting stops their done checks."',
    'joined(separator: ", ")',
    '"Cannot list the waiting tasks."',
    '"Stop"',
    '"Keep server running"',
    '"captn"',
    '"unreachable"',
    '"skipQuitWarning"',
    '"FACTORY_DOCK_APP"',
    '"Dashboard: "',
    '"X-Factory-Token"',
    '"CAPTNUv"',
    '"CAPTNFactory"',
    '["-l", "-c", "env -0"]',
    'split(separator: "\\0")',
    '"/opt/homebrew/bin", "/usr/local/bin", NSHomeDirectory() + "/.local/bin"',
    "var environment = LoginEnvironment.values",
    "isElementFullscreenEnabled = true",
]


@pytest.mark.parametrize("text", APP_TEXTS)
def test_swift_texts(text):
    assert text in dockapp.SOURCE.read_text()


def test_swift_callbacks_avoid_the_main_dispatch_queue():
    source = dockapp.SOURCE.read_text()

    assert "DispatchQueue.main" not in source
    assert "RunLoop.main.perform(inModes: [.common, .modalPanel]" in source
