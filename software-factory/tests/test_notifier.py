import json
import plistlib
import stat
import sys

import pytest

from factory import notifier

FAKE_SWIFTC = """#!/bin/sh
echo "swiftc $*" >> "$FAKE_TOOLS_LOG"
[ "${FAKE_SWIFTC_EXIT:-0}" = 0 ] || exit "$FAKE_SWIFTC_EXIT"
while [ "$1" != "-o" ]; do shift; done
cat > "$2" <<'APP'
#!/bin/sh
"$FAKE_PYTHON" -c 'import json,sys,os; open(os.environ["FAKE_APP_LOG"],"a").write(json.dumps(sys.argv[1:])+"\\n")' "$@"
exit "${FAKE_NOTIFY_EXIT:-0}"
APP
chmod +x "$2"
"""

FAKE_CODESIGN = """#!/bin/sh
echo "codesign $*" >> "$FAKE_TOOLS_LOG"
"""


@pytest.fixture
def tools(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, text in (("swiftc", FAKE_SWIFTC), ("codesign", FAKE_CODESIGN)):
        exe = bindir / name
        exe.write_text(text)
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    tools_log, app_log = tmp_path / "tools.log", tmp_path / "app.log"
    # /usr/bin holds the real swiftc and codesign, so PATH leaves it out.
    monkeypatch.setenv("PATH", f"{bindir}:/bin")
    monkeypatch.setenv("FAKE_PYTHON", sys.executable)
    monkeypatch.setenv("FAKE_TOOLS_LOG", str(tools_log))
    monkeypatch.setenv("FAKE_APP_LOG", str(app_log))
    monkeypatch.setattr(notifier, "LSREGISTER", tmp_path / "no-lsregister")

    def compiles():
        return sum(line.startswith("swiftc ") for line in tools_log.read_text().splitlines()) if tools_log.exists() else 0

    def sent():
        return [json.loads(line) for line in app_log.read_text().splitlines()] if app_log.exists() else []

    return compiles, sent


def info(app):
    with open(app / "Contents" / "Info.plist", "rb") as f:
        return plistlib.load(f)


def test_send_builds_the_app_and_shows_the_text_through_it(tools):
    compiles, sent = tools

    assert notifier.send('Task "t1" is blocked') is True

    app = notifier.app_path()
    assert compiles() == 1
    assert sent() == [["CAPTN Factory", 'Task "t1" is blocked', "Glass"]]
    assert info(app)["CFBundleIdentifier"] == "com.captn.factory.notifications"
    assert info(app)["CFBundleIconFile"] == "AppIcon"
    assert (app / "Contents" / "Resources" / "AppIcon.icns").read_bytes() == notifier.ICON.read_bytes()
    assert not [p for p in app.parent.iterdir() if p.name.startswith(".captn-build-")]


def test_send_reuses_an_app_built_from_the_same_sources(tools):
    compiles, sent = tools

    notifier.send("one")
    notifier.send("two")

    assert compiles() == 1
    assert [call[1] for call in sent()] == ["one", "two"]


def test_send_rebuilds_the_app_when_its_sources_changed(tools):
    compiles, _ = tools
    notifier.send("one")
    stale = {**info(notifier.app_path()), notifier.STAMP_KEY: "old"}
    with open(notifier.app_path() / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump(stale, f)

    notifier.send("two")

    assert compiles() == 2
    assert notifier.is_current(notifier.app_path())


def test_send_returns_false_when_the_app_is_not_allowed(tools, monkeypatch):
    monkeypatch.setenv("FAKE_NOTIFY_EXIT", "1")

    assert notifier.send("hi") is False


def test_send_returns_false_and_builds_nothing_without_swiftc(tools, tmp_path, monkeypatch):
    compiles, _ = tools
    (tmp_path / "bin" / "swiftc").unlink()

    assert notifier.send("hi") is False
    assert compiles() == 0 and not notifier.app_path().exists()


def test_send_returns_false_and_keeps_no_app_when_the_build_fails(tools, monkeypatch):
    monkeypatch.setenv("FAKE_SWIFTC_EXIT", "1")
    _, sent = tools

    assert notifier.send("hi") is False
    assert not notifier.app_path().exists() and sent() == []
