import json
import os
import re
import sys
import threading
import time
import urllib.request
from pathlib import Path

from . import cli, fsio, repo, workspaces

API_URL = "https://api.github.com/repos/Bwaim/SoftwareFactory/releases/latest"
RELEASES = "https://github.com/Bwaim/SoftwareFactory/releases/download"
CHECK_SECONDS = 24 * 3600
HOLD_SECONDS = 60
VERSION_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


def root():
    return Path(os.environ.get("FACTORY_UPDATE_ROOT") or repo.PLUGIN_ROOT)


def script_install():
    return (root() / ".installed-by-script").exists()


def parse(text):
    m = VERSION_RE.fullmatch(text) if isinstance(text, str) else None
    return tuple(int(n) for n in m.groups()) if m else None


def newer(latest, installed):
    a, b = parse(latest), parse(installed)
    return a is not None and b is not None and a > b


def log(text):
    print(text, file=sys.stderr, flush=True)


def fetch_latest(url=None, timeout=10):
    url = url or os.environ.get("FACTORY_UPDATE_URL") or API_URL
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "captn-factory"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            tag = json.load(response)["tag_name"]
    except Exception as e:
        log(f"Update check failed: {e}")
        return None
    if parse(tag) is None:
        log(f"Update check failed: unexpected tag {tag!r}")
        return None
    return tag.removeprefix("v")


def dismissed_path():
    return workspaces.home() / "update-dismissed"


def dismissed():
    return fsio.read_text(dismissed_path()).strip() or None


def dismiss(version):
    fsio.atomic_write_text(dismissed_path(), version + "\n")


class Checker:
    def __init__(self):
        self.latest = None
        self.checked_at = None

    def check_once(self):
        found = fetch_latest()
        self.checked_at = time.time()
        if found and newer(found, cli.VERSION):
            self.latest = found

    def run(self):
        while True:
            self.check_once()
            time.sleep(CHECK_SECONDS)

    def start(self):
        if os.environ.get("FACTORY_NO_UPDATE_CHECK") or not script_install():
            return
        threading.Thread(target=self.run, daemon=True).start()
