import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import fsio
from .errors import FactoryError
from .repo import PLUGIN_ROOT
from .step_format import STEP_ID_RE, is_valid_id, validate

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
CREATE_WORKTREE = "create-worktree"


def parse_step_text(text, path):
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise FactoryError(f"{path}: the step file has no YAML frontmatter.")
    try:
        manifest = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise FactoryError(f"{path}: invalid YAML frontmatter: {e}")
    return manifest, m.group(2).lstrip("\n")


def normalize_entry(e):
    return {"id": e} if isinstance(e, str) else dict(e or {})


@dataclass
class Step:
    id: str
    level: str
    path: Path
    manifest: dict
    body: str

    def get(self, key, default=None):
        return self.manifest.get(key, default)

    @property
    def type(self):
        return self.get("type")

    @property
    def run_in(self):
        return self.get("run_in", "session")

    @property
    def required(self):
        return bool(self.get("required", False))

    @property
    def children(self):
        return list(self.get("steps") or [])

    @property
    def column(self):
        return self.get("column")

    @property
    def model(self):
        return self.get("model")

    @property
    def effort(self):
        return self.get("effort")

    @property
    def done_check(self):
        return self.get("done_check")

    @property
    def done_when(self):
        return self.get("done_when", "")

    @property
    def wait_external(self):
        return bool(self.get("wait_external", False))

    @property
    def requires(self):
        return list(self.get("requires") or [])

    @property
    def category(self):
        return self.get("category", "")

    @property
    def description(self):
        return self.get("description", "")

    @property
    def config_spec(self):
        return {k: (v or {}) for k, v in (self.get("config") or {}).items()}


@dataclass
class Pipeline:
    id: str
    level: str
    path: Path
    data: dict

    @property
    def entries(self):
        return [normalize_entry(e) for e in self.data.get("steps") or []]

    @property
    def inputs(self):
        return dict(self.data.get("inputs") or {})

    @property
    def claude(self):
        return dict(self.data.get("claude") or {})

    @property
    def start_column(self):
        return self.data.get("start_column")


def level_roots(ctx):
    roots = [("builtin", PLUGIN_ROOT / "builtin")]
    lib = ctx.library()
    if lib:
        roots.append(("generic", lib))
    roots.append(("local", ctx.fdir))
    return roots


def all_pipeline_files(ctx):
    out = []
    for level, root in level_roots(ctx):
        for p in sorted((root / "pipelines").glob("*.yaml")):
            data = fsio.read_yaml(p, {}) or {}
            out.append((level, data.get("id") or p.stem, data))
    return out


class Registry:
    def __init__(self, steps, pipelines, variants=None):
        self.steps = steps
        self.pipelines = pipelines
        self.variants = variants if variants is not None else {sid: [s] for sid, s in steps.items()}

    @classmethod
    def load(cls, ctx):
        steps, pipelines, variants = {}, {}, {}
        for level, root in level_roots(ctx):
            for p in sorted((root / "steps").glob("*.md")):
                manifest, body = parse_step_text(p.read_text(), p)
                errors, _ = validate(manifest, body)
                if errors:
                    raise FactoryError(f"{p}: " + " ".join(errors))
                sid = manifest.get("id") or p.stem
                steps[sid] = Step(sid, level, p, manifest, body)
                variants.setdefault(sid, []).append(steps[sid])
            for p in sorted((root / "pipelines").glob("*.yaml")):
                data = fsio.read_yaml(p, {}) or {}
                pid = data.get("id") or p.stem
                pipelines[pid] = Pipeline(pid, level, p, data)
        reg = cls(steps, pipelines, variants)
        reg.check_loops()
        return reg

    def step(self, sid):
        if not isinstance(sid, str) or sid not in self.steps:
            raise FactoryError(f"The step `{sid}` does not exist.")
        return self.steps[sid]

    def pipeline(self, pid):
        if not isinstance(pid, str) or pid not in self.pipelines:
            raise FactoryError(f"The pipeline `{pid}` does not exist.")
        return self.pipelines[pid]

    def check_loops(self):
        def visit(sid, chain):
            if sid in chain:
                raise FactoryError("Group step loop: " + " > ".join(chain + [sid]))
            step = self.steps.get(sid)
            if step and step.type == "group":
                for child in step.children:
                    visit(child, chain + [sid])

        for sid in self.steps:
            visit(sid, [])

    def leaves(self, sid, prefix=None):
        prefix = prefix or []
        step = self.step(sid)
        if step.type != "group":
            return [prefix + [sid]]
        out = []
        for child in step.children:
            out += self.leaves(child, prefix + [sid])
        return out

    def expand(self, pipeline):
        entries = pipeline.entries
        if not entries or entries[0].get("id") != CREATE_WORKTREE:
            entries = [{"id": CREATE_WORKTREE}] + entries
        snapshot = []
        for entry in entries:
            for i, path in enumerate(self.leaves(entry["id"])):
                snapshot.append({
                    "id": path[-1],
                    "path": path,
                    "with": dict(entry.get("with") or {}),
                    "column": entry.get("column") if i == 0 else None,
                    "model": entry.get("model"),
                    "effort": entry.get("effort"),
                })
        return snapshot

    def categories(self):
        return sorted({s.category for s in self.steps.values() if s.category})
