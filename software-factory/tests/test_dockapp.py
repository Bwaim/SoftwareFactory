import os
import plistlib
import subprocess
import sys

import pytest

from factory import dockapp
from factory.errors import FactoryError


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


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
def test_app_install_command_prints_path(factory, tools):
    fake = {k: os.environ[k] for k in ("PATH", "FAKE_PYTHON", "FAKE_TOOLS_LOG", "FAKE_APP_LOG")}

    r = factory("app", "install", env={"UV": "/opt/uv/bin/uv", **fake})

    assert f"Dashboard app: {dockapp.app_path()}" in r.stdout
    assert "Drag it to the Dock to keep it there." in r.stdout
