import re

from conftest import SF


def test_skill_frontmatter_and_menu_rule():
    text = (SF / "skills" / "software-factory" / "SKILL.md").read_text()
    assert text.startswith("---\nname: software-factory\n")
    assert "Do not use the AskUserQuestion tool for the menu" in text
    assert "FACTORY link --json" in text.split("factory terminal check")[0]
