import yaml

from conftest import SF
from factory import requires, step_format
from factory.registry import parse_step_text

FORBIDDEN = ["nextory", "android", "kotlin", "gradlew", "crashlytics", "jira", "herdr", "fabien"]


def by_id(items):
    return {i["id"]: i for i in items}


def test_list_and_install_pipeline_with_missing_steps(inited):
    items = by_id(inited.factory.json("catalog", "list"))
    assert items["quick-task"]["status"] == "not installed"
    dry = inited.factory.json("catalog", "install", "quick-task", "--local", "--dry-run")
    assert sorted(dry["missing_steps"]) == ["commit", "implement"]
    inited.factory("catalog", "install", "quick-task", "--local", "--with-steps")
    assert (inited.fdir / "pipelines" / "quick-task.yaml").exists()
    assert (inited.fdir / "steps" / "commit.md").exists()
    items = by_id(inited.factory.json("catalog", "list"))
    assert items["quick-task"]["status"] == "installed" and items["quick-task"]["location"] == "local"
    (inited.fdir / "steps" / "commit.md").write_text((inited.fdir / "steps" / "commit.md").read_text() + "\nMore.\n")
    assert by_id(inited.factory.json("catalog", "list"))["commit"]["status"] == "changed"


def test_replace_needs_flag_and_shows_diff(inited):
    inited.factory("catalog", "install", "push", "--generic")
    assert (inited.library / "steps" / "push.sh").exists()
    push_md = inited.library / "steps" / "push.md"
    push_md.write_text(push_md.read_text() + "\nchanged\n")
    dry = inited.factory.json("catalog", "install", "push", "--generic", "--dry-run")
    assert dry["conflicts"] and "changed" in dry["conflicts"][0]["diff"]
    r = inited.factory("catalog", "install", "push", "--generic", check=False)
    assert r.returncode == 1 and "--replace" in r.stderr
    out = inited.factory.json("catalog", "install", "push", "--generic", "--replace")
    assert out["library_commit"]["message"] == "Factory library: add step push"


def test_missing_requires(inited, work):
    items = by_id(inited.factory.json("catalog", "list"))
    assert "/superpowers:brainstorming" in items["brainstorm"]["missing_requires"]
    skill = work / "claude-home" / "plugins" / "cache" / "m" / "superpowers" / "1.0" / "skills" / "brainstorming"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("x")
    items = by_id(inited.factory.json("catalog", "list"))
    assert items["brainstorm"]["missing_requires"] == []
    marketplace = work / "claude-home" / "plugins" / "marketplaces" / "m" / "superpowers" / "1.0" / "skills" / "debugging"
    marketplace.mkdir(parents=True)
    (marketplace / "SKILL.md").write_text("x")
    assert requires.missing(["/superpowers:debugging"], inited.repo) == ["/superpowers:debugging"]
    assert requires.missing(["definitely-not-a-tool-xyz", "git"], inited.repo) == ["definitely-not-a-tool-xyz"]


def test_catalog_is_generic():
    for path in (SF / "catalog").rglob("*"):
        if path.is_file():
            text = path.read_text().lower()
            assert not [w for w in FORBIDDEN if w in text], path
    for path in (SF / "catalog" / "steps").glob("*.md"):
        manifest = yaml.safe_load(path.read_text().split("---")[1])
        for item in manifest.get("requires") or []:
            assert not item.startswith("/") or item.startswith("/superpowers:"), path


def test_catalog_steps_parse_with_registry():
    paths = sorted((SF / "catalog" / "steps").glob("*.md"))
    assert len(paths) == 13
    for path in paths:
        manifest, body = parse_step_text(path.read_text(), path)
        assert manifest["id"] == path.stem
        assert manifest["description"] and manifest.get("category")
        assert body.strip()
    wait_review, _ = parse_step_text((SF / "catalog" / "steps" / "wait-review.md").read_text(), "wait-review")
    assert wait_review["done_check"].startswith('if [ "$FACTORY_CONFIG_FORGE" = github ]; then gh pr view')
    assert wait_review["done_check"].endswith('json.load(sys.stdin).get(\\"approved\\") else 1)"; else exit 1; fi')


TYPED_OUTPUTS = {"brainstorm": {"spec": ("file", False)}, "write-plan": {"plan": ("file", False)},
                 "review": {"review": ("file", False)}, "create-pr": {"mr_url": ("text", False)},
                 "commit": {"branch": ("text", True)}}


def test_catalog_steps_are_version_2():
    for path in sorted((SF / "catalog" / "steps").glob("*.md")):
        manifest, body = parse_step_text(path.read_text(), path)
        assert step_format.validate(manifest, body)[0] == [], path.name
        assert manifest["type"] in ("ai", "command")
        assert "factory state get" not in str(manifest.get("done_check") or ""), path.name
        for key, (ktype, optional) in TYPED_OUTPUTS.get(manifest["id"], {}).items():
            out = manifest["outputs"][key]
            assert out["type"] == ktype and bool(out.get("optional")) is optional and out["description"]
    for sid, script in (("push", "push.sh"), ("run-tests", "run-tests.sh")):
        manifest, body = parse_step_text((SF / "catalog" / "steps" / f"{sid}.md").read_text(), sid)
        assert manifest["type"] == "command" and body.strip() == f'bash "$FACTORY_STEP_DIR/{script}"'


def test_catalog_prompts_use_placeholders():
    expected = {"brainstorm": ["{{description}}", "{{summary}}"], "write-plan": ["{{spec}}", "{{config.plan_style}}"],
                "execute-plan": ["{{plan}}"], "create-pr": ["{{branch}}", "{{config.forge}}"],
                "implement": ["{{description}}", "{{summary}}"], "address-review-comments": ["{{mr_url}}"],
                "wait-review": ["{{mr_url}}"]}
    for sid, needles in expected.items():
        text = (SF / "catalog" / "steps" / f"{sid}.md").read_text()
        for needle in needles:
            assert needle in text, (sid, needle)
