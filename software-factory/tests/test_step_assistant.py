from conftest import fake_calls
from factory import launch, repo
from factory.registry import Registry


def test_builtin_assistant_runs_in_main_repo(inited):
    ctx = repo.load_ctx(cwd=inited.repo)
    reg = Registry.load(ctx)
    assert reg.pipeline("new-step-assistant").level == "builtin"
    assert [e["id"] for e in reg.expand(reg.pipeline("new-step-assistant"))] == ["new-step"]
    task = launch.launch(ctx, "new-step-assistant", "Create merge request step", {})
    assert task["worktree"] is None
    call = fake_calls(inited.fdir)[-1]
    assert call["in_worktree"] is False
    assert call["args"].count("--add-dir") == 2 and str(inited.library) in call["args"]
    out = inited.factory("next", "--task", task["id"]).stdout
    assert "`factory step list --task" in out
