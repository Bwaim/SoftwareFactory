import re

from conftest import SF
from factory import cli, commands


def command_names():
    parser, sub, common = cli.build_parser()
    commands.register(sub, common)
    names = set()
    for name, p in sub.choices.items():
        names.add(name)
        for action in p._actions:
            if getattr(action, "choices", None) and isinstance(action.choices, dict):
                for child in action.choices:
                    names.add(f"{name} {child}")
    return names


FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)


def code_spans(text):
    fenced = FENCE.findall(text)
    inline = re.findall(r"`([^`\n]+)`", FENCE.sub("", text))
    return "\n".join(fenced + inline)


def used_commands(text):
    found = set()
    for m in re.finditer(r"\bfactory ([a-z][a-z-]*)(?: ([a-z][a-z-]*))?", code_spans(text)):
        found.add((m.group(1), m.group(2)))
    return found


def check(text, names):
    missing = []
    for first, second in used_commands(text):
        if first not in names:
            missing.append(first)
        elif second and any(n.startswith(first + " ") for n in names) and f"{first} {second}" not in names:
            missing.append(f"{first} {second}")
    return missing


def test_readme_commands_exist():
    assert check((SF / "README.md").read_text(), command_names()) == []


def test_skill_and_builtin_commands_exist():
    names = command_names()
    texts = [(SF / "skills" / "software-factory" / "SKILL.md").read_text()]
    texts += [p.read_text() for p in (SF / "builtin" / "steps").glob("*.md")]
    texts += [p.read_text() for p in (SF / "catalog" / "steps").glob("*.md")]
    for text in texts:
        assert check(text, names) == []


def test_readme_sections():
    text = (SF / "README.md").read_text()
    for heading in ("Concepts", "Install", "Tutorial", "Reference", "Troubleshooting"):
        assert heading in text


def test_checker_scans_fenced_blocks_and_inline_spans_but_not_prose():
    names = command_names()
    assert check("```\nfactory bogus\n```", names) == ["bogus"]
    assert check("run `factory nope` now", names) == ["nope"]
    assert check("```\nfactory tasks\n```\nupdate the factory plugin", names) == []


def test_readme_describes_step_editor():
    text = (SF / "README.md").read_text()
    for needle in ("`text`", "`long-text`", "`file`", "`task_id`", "`summary`", "`ai`", "`command`", "`group`",
                   "{{<key>}}", "{{config.<key>}}", "(not set)", "`outputs`", "FACTORY_KEY_", "FACTORY_STEP_DIR",
                   "factory pipeline keys", "factory step edit", "factory run-command", "step form"):
        assert needle in text, needle
    assert "run-script" not in text and "new-step-assistant" not in text and "Answer the questions of the assistant" not in text
