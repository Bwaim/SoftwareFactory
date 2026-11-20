import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .. import appbuild, fsio, repo, workspaces
from ..errors import FactoryError

NAME = "CAPTN Dashboard"
APP_NAME = NAME + ".app"
BUNDLE_ID = "com.captn.factory.dashboard"
EXECUTABLE = "captn-dashboard"
SOURCE = Path(__file__).resolve().parent / "main.swift"


def app_path():
    return Path(os.environ.get("FACTORY_DASHBOARD_APP") or Path.home() / "Applications" / APP_NAME)


def uv_path():
    found = shutil.which("uv") or os.environ.get("UV")
    return os.path.abspath(found) if found else None


def factory_path():
    return repo.PLUGIN_ROOT / "bin" / "factory"


def stamp(uv):
    digest = hashlib.sha256()
    for source in (SOURCE, appbuild.ICON):
        digest.update(source.read_bytes())
    for text in (BUNDLE_ID, uv, str(factory_path())):
        digest.update(text.encode())
    return digest.hexdigest()


def info_plist(uv):
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
        "CAPTNUv": uv,
        "CAPTNFactory": str(factory_path()),
        appbuild.STAMP_KEY: stamp(uv),
    }


def installed():
    return sys.platform == "darwin" and (app_path() / "Contents" / "MacOS" / EXECUTABLE).exists()


def current(uv):
    return appbuild.is_current(app_path(), EXECUTABLE, stamp(uv))


def install():
    if sys.platform != "darwin":
        raise FactoryError("The dashboard app needs macOS.")
    if not appbuild.can_build():
        raise FactoryError("The dashboard app needs `swiftc` and `codesign`. Install the Xcode command line tools.")
    uv = uv_path()
    if not uv:
        raise FactoryError("Cannot find uv.")
    app = app_path()
    if not current(uv):
        with fsio.locked(workspaces.home() / "dockapp"):
            if not current(uv):
                try:
                    appbuild.build(app, SOURCE, EXECUTABLE, info_plist(uv))
                except (OSError, subprocess.SubprocessError):
                    raise FactoryError("The dashboard app did not build. See the error above.")
    return app


def refresh():
    uv = uv_path()
    if installed() and not (uv and current(uv)):
        try:
            install()
        except FactoryError:
            pass


def open_url(url):
    subprocess.run(["open", "-a", str(app_path()), url], check=False)
