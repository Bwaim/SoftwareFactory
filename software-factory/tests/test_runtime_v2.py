import pytest

from conftest import task_from_pipeline, write_pipeline, write_step


def run(inited, *args, check=True):
    return inited.factory(*args, "--task", "t1", check=check)


@pytest.fixture
def ai(inited):
    write_step(inited.fdir, "plan", {
        "config": {"style": {"description": "Style", "default": "small"}},
        "outputs": {"plan": {"type": "file", "description": "The plan"},
                    "note": {"type": "long-text", "description": "Notes", "optional": True}},
        "done_when": "The plan is written.",
    }, body="Plan {{spec}} for {{task_id}} ({{description}}), style {{config.style}}. Ticket: {{ticket}}.\n")
    write_pipeline(inited.fdir, {"id": "p", "steps": ["plan"]})
    task_from_pipeline(inited, "p", description="Add login", state={"spec": "/tmp/spec.md"})
    return inited


def test_next_prints_exact_prompt_then_footer(ai):
    out = run(ai, "next").stdout
    prompt, footer = out.split("\n---\n", 1)
    assert prompt.rstrip("\n") == "Plan /tmp/spec.md for t1 (Add login), style small. Ticket: (not set)."
    assert footer.splitlines()[0] == "Step 2 of 2: plan"
    assert "- `plan` (file): The plan. Set it with `factory state set plan <path>`. Get a path in the artifacts folder with `factory artifact path <name>`." in footer
    assert "- `note` (long-text, optional): Notes. Set it with `factory state set note <value>`." in footer
    assert "Done when: The plan is written." in footer
    assert footer.rstrip().endswith("When the step is done, run `factory done`.")
    assert "--task" not in out


def test_subagent_prompt_is_the_same_text_with_a_report_line(inited):
    write_step(inited.fdir, "sub", {"run_in": "subagent", "model": "haiku", "effort": "low",
                                    "outputs": {"review": {"type": "file", "description": "Review"}}}, body="Review {{ticket}}.\n")
    write_pipeline(inited.fdir, {"id": "s", "steps": [{"id": "sub", "model": "opus"}]})
    task_from_pipeline(inited, "s", state={"ticket": "ABC-1"})
    out = run(inited, "next").stdout
    inner = out.split("<<<\n", 1)[1].split("\n>>>", 1)[0]
    assert inner.startswith("Review ABC-1.\n\n---\nStep 2 of 2: sub\n")
    assert "- `review` (file): Review." in inner
    assert inner.endswith("End with a short report. If you need an answer from the user, say so in the report and stop.")
    assert "factory done" not in inner
    assert "- model: opus" in out and "- effort: low" in out
    assert out.rstrip().endswith("Otherwise run `factory done`.")


def test_wait_external_ends_with_factory_wait(inited):
    write_step(inited.fdir, "w", {"wait_external": True}, body="Wait.\n")
    write_pipeline(inited.fdir, {"id": "wp", "steps": ["w"]})
    task_from_pipeline(inited, "wp")
    assert run(inited, "next").stdout.rstrip().endswith("The factory tells you when the external event happens.")


def test_group_step_shows_full_path(inited):
    write_step(inited.fdir, "a", {})
    write_step(inited.fdir, "b", {})
    write_step(inited.fdir, "ab", {"type": "group", "steps": ["a", "b"]}, body="")
    write_pipeline(inited.fdir, {"id": "g", "steps": ["ab"]})
    task_from_pipeline(inited, "g")
    run(inited, "next"); run(inited, "done")
    assert "Step 3 of 3: ab > b" in run(inited, "next").stdout


def test_first_prompt_never_adds_task_flag():
    from factory import session
    text = session.first_prompt({"id": "t1", "worktree": "/w"})
    assert "`factory next`" in text and "`factory done`" in text and "--task" not in text
