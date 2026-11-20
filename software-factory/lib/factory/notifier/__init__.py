"""macOS notifications with the CAPTN icon.

`osascript` notifications always show the Script Editor icon. A notification shows the icon of the app that sends it, so the
factory builds a small app, "CAPTN Dashboard Notifier.app", from main.swift next to this file and appicon/AppIcon.icns, and sends through it.
The release has no compiled app (it is built on any OS), so the app is compiled here, with swiftc, the first time it is
needed, and again when its sources change. Without swiftc, or until the user allows the app's notifications, `send`
returns False and the caller falls back to osascript.
"""
import hashlib
import os
import subprocess
from pathlib import Path

from .. import appbuild, fsio, workspaces

TITLE = "CAPTN Factory"
SOUND = "Glass"
NAME = "CAPTN Dashboard Notifier"
APP_NAME = NAME + ".app"
OLD_APP = Path.home() / "Applications" / "CAPTN Factory.app"
BUNDLE_ID = "com.captn.factory.notifications"
EXECUTABLE = "captn-notify"
SOURCES = Path(__file__).resolve().parent
SWIFT_SOURCE = SOURCES / "main.swift"
# Above the app's own 10 second limit, so a hang cannot hold the factory longer than this.
SEND_TIMEOUT_SECONDS = 15
SENT = 0


def app_path():
    # ~/Applications, not the install folder: an app run from a temporary or hidden folder got no permission prompt.
    return Path(os.environ.get("FACTORY_NOTIFIER_APP") or Path.home() / "Applications" / APP_NAME)


def lock_path():
    return workspaces.home() / "notifier"


def executable(app):
    return app / "Contents" / "MacOS" / EXECUTABLE


def stamp():
    digest = hashlib.sha256()
    for source in (SWIFT_SOURCE, appbuild.ICON):
        digest.update(source.read_bytes())
    digest.update(BUNDLE_ID.encode())
    return digest.hexdigest()


def info_plist():
    return {
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleName": NAME,
        "CFBundleDisplayName": NAME,
        "CFBundleExecutable": EXECUTABLE,
        "CFBundleIconFile": "AppIcon",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "13.0",
        "NSPrincipalClass": "NSApplication",
        appbuild.STAMP_KEY: stamp(),
    }


def ensure_app():
    """The path of an up-to-date app, building it when needed. None when it cannot be built."""
    app = app_path()
    if appbuild.is_current(app, EXECUTABLE, stamp()):
        return app
    if not appbuild.can_build():
        return None
    with fsio.locked(lock_path()):
        if not appbuild.is_current(app, EXECUTABLE, stamp()):
            try:
                appbuild.build(app, SWIFT_SOURCE, EXECUTABLE, info_plist())
            except (OSError, subprocess.SubprocessError):
                return None
            if not os.environ.get("FACTORY_NOTIFIER_APP"):
                appbuild.remove_old_bundle(OLD_APP, BUNDLE_ID)
    return app


def send(text, title=TITLE, sound=SOUND):
    """Show `text` through the app. False when the app is missing, not allowed yet, or failed: the caller falls back."""
    app = ensure_app()
    if app is None:
        return False
    try:
        r = subprocess.run([str(executable(app)), title, text, sound], capture_output=True, timeout=SEND_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == SENT
