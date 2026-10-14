import json
import os
import shutil
from pathlib import Path


def claude_home():
    return Path(os.environ.get("FACTORY_CLAUDE_HOME", "~/.claude")).expanduser()


def skill_present(name, main):
    plugin, _, skill = name.lstrip("/").rpartition(":")
    if not plugin:
        for root in (claude_home() / "skills", Path(main) / ".claude" / "skills"):
            if (root / skill / "SKILL.md").exists():
                return True
    cache = claude_home() / "plugins" / "cache"
    if not plugin:
        return next(cache.glob(f"*/*/*/skills/{skill}/SKILL.md"), None) is not None
    for version in cache.glob(f"*/{plugin}/*"):
        if (version / "skills" / skill / "SKILL.md").exists():
            return True
        if any(Path(folder).name == skill and (version / folder / "SKILL.md").exists()
               for folder in manifest_skills(version, plugin)):
            return True
    return False


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def manifest_skills(version, plugin):
    manifests = version / ".claude-plugin"
    entries = [read_json(manifests / "plugin.json")]
    marketplace = read_json(manifests / "marketplace.json")
    if isinstance(marketplace, dict) and isinstance(marketplace.get("plugins"), list):
        entries += [p for p in marketplace["plugins"] if isinstance(p, dict) and p.get("name") == plugin]
    folders = []
    for entry in entries:
        skills = entry.get("skills") if isinstance(entry, dict) else None
        if isinstance(skills, list):
            folders += [s for s in skills if isinstance(s, str)]
    return folders


def missing(items, main):
    out = []
    for item in items:
        present = skill_present(item, main) if item.startswith("/") else shutil.which(item) is not None
        if not present:
            out.append(item)
    return out
