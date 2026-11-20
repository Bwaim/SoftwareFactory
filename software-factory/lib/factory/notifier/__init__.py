"""macOS notifications with the CAPTN icon.

`osascript` notifications always show the Script Editor icon. A notification shows the icon of the app that sends it, so the
factory builds a small app, "CAPTN Factory.app", from main.swift and AppIcon.icns next to this file, and sends through it.
The release has no compiled app (it is built on any OS), so the app is compiled here, with swiftc, the first time it is
needed, and again when its sources change. Without swiftc, or until the user allows the app's notifications, `send`
returns False and the caller falls back to osascript.
"""
import hashlib
import os
import plistlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from .. import fsio, workspaces

TITLE = "CAPTN Factory"
SOUND = "Glass"
APP_NAME = "CAPTN Factory.app"
BUNDLE_ID = "com.captn.factory.notifications"
EXECUTABLE = "captn-notify"
STAMP_KEY = "CAPTNBuildStamp"
SOURCES = Path(__file__).resolve().parent
SWIFT_SOURCE = SOURCES / "main.swift"
ICON = SOURCES / "AppIcon.icns"
BUILD_TIMEOUT_SECONDS = 300
# Above the app's own 10 second limit, so a hang cannot hold the factory longer than this.
SEND_TIMEOUT_SECONDS = 15
SENT = 0
LSREGISTER = Path(
    "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
)


def app_path():
    # ~/Applications, not the install folder: an app run from a temporary or hidden folder got no permission prompt.
    return Path(os.environ.get("FACTORY_NOTIFIER_APP") or Path.home() / "Applications" / APP_NAME)


def lock_path():
    return workspaces.home() / "notifier"


def executable(app):
    return app / "Contents" / "MacOS" / EXECUTABLE


def stamp():
    digest = hashlib.sha256()
    for source in (SWIFT_SOURCE, ICON):
        digest.update(source.read_bytes())
    digest.update(BUNDLE_ID.encode())
    return digest.hexdigest()


def is_current(app):
    try:
        with open(app / "Contents" / "Info.plist", "rb") as f:
            info = plistlib.load(f)
    except (OSError, plistlib.InvalidFileException):
        return False
    return info.get(STAMP_KEY) == stamp() and executable(app).exists()


def can_build():
    return bool(shutil.which("swiftc") and shutil.which("codesign"))


def info_plist():
    return {
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleName": "CAPTN Factory",
        "CFBundleDisplayName": "CAPTN Factory",
        "CFBundleExecutable": EXECUTABLE,
        "CFBundleIconFile": "AppIcon",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "13.0",
        "NSPrincipalClass": "NSApplication",
        STAMP_KEY: stamp(),
    }


def build(app):
    """Compile the app in a temporary folder next to `app`, sign it ad hoc, then move it in place."""
    app.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=app.parent, prefix=".captn-build-") as work:
        bundle = Path(work) / APP_NAME
        (bundle / "Contents" / "MacOS").mkdir(parents=True)
        (bundle / "Contents" / "Resources").mkdir()
        subprocess.run(["swiftc", "-O", str(SWIFT_SOURCE), "-o", str(executable(bundle))],
                       check=True, capture_output=True, timeout=BUILD_TIMEOUT_SECONDS)
        shutil.copyfile(ICON, bundle / "Contents" / "Resources" / "AppIcon.icns")
        with open(bundle / "Contents" / "Info.plist", "wb") as f:
            plistlib.dump(info_plist(), f)
        subprocess.run(["codesign", "--force", "--sign", "-", str(bundle)], check=True, capture_output=True)
        if app.exists():
            shutil.rmtree(app)
        os.rename(bundle, app)
    if LSREGISTER.exists():
        subprocess.run([str(LSREGISTER), "-f", str(app)], capture_output=True)


def ensure_app():
    """The path of an up-to-date app, building it when needed. None when it cannot be built."""
    app = app_path()
    if is_current(app):
        return app
    if not can_build():
        return None
    with fsio.locked(lock_path()):
        if not is_current(app):
            try:
                build(app)
            except (OSError, subprocess.SubprocessError):
                return None
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
