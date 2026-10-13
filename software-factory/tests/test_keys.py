from types import SimpleNamespace

from factory import keys


def step(stype, body="", manifest=None):
    m = {"type": stype, **(manifest or {})}
    return SimpleNamespace(type=stype, body=body, done_check=m.get("done_check"), get=m.get)


def test_key_rule_and_env_name():
    assert keys.is_key("crash_url") and keys.is_key("a1")
    assert not keys.is_key("Crash") and not keys.is_key("1a") and not keys.is_key("a-b") and not keys.is_key(None)
    assert keys.env_name("crash_url") == "FACTORY_KEY_CRASH_URL"
    assert keys.key_type(None) == "text" and keys.key_type({"type": "file"}) == "file" and keys.key_type({}) == "text"


def test_placeholders():
    found = keys.placeholders("Use {{spec}} and {{config.plan_style}}, {{spec}} again, {{Bad}} and {{config.}}.")
    assert found == (["spec"], ["plan_style"], ["{{Bad}}", "{{config.}}"])
    assert keys.has_placeholder("a {{x}} b") and not keys.has_placeholder("a {x} b")


def test_env_refs():
    text = 'echo "$FACTORY_KEY_MR_URL" ${FACTORY_KEY_BRANCH:-none} $FACTORY_CONFIG_X $FACTORY_KEY_MR_URL'
    assert keys.env_refs(text) == ["mr_url", "branch"]


def test_outputs_and_leaf_uses():
    ai = step("ai", "Read {{spec}} with {{config.style}}.", {"done_check": 'test -n "$FACTORY_KEY_PLAN"',
                                                          "outputs": {"plan": {"type": "file", "description": "Plan"}, "note": None}})
    assert keys.leaf_uses(ai) == ["spec", "plan"]
    assert keys.outputs_of(ai) == {"plan": {"type": "file", "description": "Plan", "optional": False},
                                   "note": {"type": "text", "description": "", "optional": False}}
    cmd = step("command", 'bash x.sh "$FACTORY_KEY_BRANCH"')
    assert keys.leaf_uses(cmd) == ["branch"]
