import re
from dataclasses import asdict, dataclass

from . import fsio
from .errors import FactoryError

HEADING_RE = re.compile(r"^## (.+?)\s*$")
ID_LINE_RE = re.compile(r"^<!-- id: ([A-Za-z0-9_-]+) -->\s*$")
PIPELINE_LINE_RE = re.compile(r"^pipeline: ([a-z][a-z0-9_-]*)\s*$")
GENERATED_ID_RE = re.compile(r"^b(\d+)$")
LIST_MARK_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
DEFAULT_PREAMBLE = "# Backlog"


@dataclass
class Entry:
    id: str | None
    title: str
    summary: str
    pipeline: str | None

    def to_dict(self):
        return asdict(self)


def path(ctx):
    return ctx.fdir / "backlog.md"


def read_metadata(entry, line):
    id_match = ID_LINE_RE.match(line)
    if id_match and entry.id is None:
        entry.id = id_match.group(1)
        return True
    pipeline_match = PIPELINE_LINE_RE.match(line)
    if pipeline_match and entry.pipeline is None:
        entry.pipeline = pipeline_match.group(1)
        return True
    return False


def finish_entry(entry, lines):
    rest = [line for line in lines if not read_metadata(entry, line)]
    entry.summary = "\n".join(rest).strip()


def parse(text):
    preamble, entries, current, lines = [], [], None, []
    for line in text.splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            if current:
                finish_entry(current, lines)
            current, lines = Entry(None, heading.group(1), "", None), []
            entries.append(current)
        elif current:
            lines.append(line)
        else:
            preamble.append(line)
    if current:
        finish_entry(current, lines)
    return "\n".join(preamble).strip() or DEFAULT_PREAMBLE, entries


def render_entry(entry):
    block = [f"## {entry.title}", f"<!-- id: {entry.id} -->"]
    if entry.pipeline:
        block.append(f"pipeline: {entry.pipeline}")
    if entry.summary:
        block.append(entry.summary)
    return "\n".join(block)


def render(preamble, entries):
    return "\n\n".join([preamble.strip(), *(render_entry(e) for e in entries)]) + "\n"


def assign_ids(entries):
    numbers = [int(m.group(1)) for e in entries if e.id and (m := GENERATED_ID_RE.match(e.id))]
    n = max(numbers, default=0)
    for e in entries:
        if not e.id:
            n += 1
            e.id = f"b{n}"


def change(ctx, fn):
    box = {}

    def update(text):
        preamble, entries = parse(text)
        assign_ids(entries)
        box["value"] = fn(entries)
        return render(preamble, entries)

    fsio.update_text(path(ctx), update)
    return box["value"]


def find(entries, entry_id):
    for i, e in enumerate(entries):
        if e.id == entry_id:
            return i
    raise FactoryError(f"No backlog entry with id `{entry_id}`.")


def list_entries(ctx):
    return change(ctx, lambda entries: list(entries))


def get(ctx, entry_id):
    entries = list_entries(ctx)
    return entries[find(entries, entry_id)]


def clean_title(title):
    title = " ".join(title.split())
    if not title:
        raise FactoryError("The title is empty.")
    return title


def add(ctx, title, summary="", pipeline=None):
    title = clean_title(title)

    def fn(entries):
        entry = Entry(None, title, (summary or "").strip(), pipeline or None)
        entries.append(entry)
        assign_ids(entries)
        return entry

    return change(ctx, fn)


def remove(ctx, entry_id):
    return change(ctx, lambda entries: entries.pop(find(entries, entry_id)))


def move(ctx, entry_id, to):
    def fn(entries):
        entry = entries.pop(find(entries, entry_id))
        index = max(0, min(int(to) - 1, len(entries)))
        entries.insert(index, entry)
        return list(entries)

    return change(ctx, fn)


def parse_import(text):
    titles = []
    for line in text.splitlines():
        title = " ".join(LIST_MARK_RE.sub("", line).split())
        if title:
            titles.append(title)
    return titles


def import_titles(ctx, titles):
    return [add(ctx, t) for t in titles]
