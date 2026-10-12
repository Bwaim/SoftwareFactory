from conftest import commit_all, git, write_pipeline, write_step
from factory import launch, repo, state


def finish(ctx, tid):
    state.update(ctx, tid, lambda t: state.set_status(t, "finished"))


def test_clean_detects_merge_cases(inited):
    write_step(inited.fdir, "w", {})
    write_pipeline(inited.fdir, {"id": "b", "inputs": {"branch": {"description": "b"}}, "steps": ["w"]})
    write_pipeline(inited.fdir, {"id": "nb", "steps": ["w"]})
    ctx = repo.load_ctx(cwd=inited.repo)
    merged = launch.launch(ctx, "b", "Merged", {"branch": "feat/merged"})
    gone = launch.launch(ctx, "b", "Gone remote", {"branch": "feat/gone"})
    open_ = launch.launch(ctx, "b", "Open", {"branch": "feat/open"})
    nobranch = launch.launch(ctx, "nb", "No branch", {})
    for task, name in ((merged, "m.txt"), (gone, "g.txt"), (open_, "o.txt")):
        (inited.worktrees / task["id"] / name).write_text("x")
        commit_all(inited.worktrees / task["id"], name)
    git("push", "origin", "feat/merged:main", cwd=inited.repo)
    git("push", "-u", "origin", "feat/gone", cwd=inited.worktrees / gone["id"])
    git("push", "origin", "--delete", "feat/gone", cwd=inited.repo)
    for t in (merged, gone, open_, nobranch):
        finish(ctx, t["id"])
    rows = {r["id"]: r for r in inited.factory.json("clean")}
    assert rows[merged["id"]]["merged"] and rows[merged["id"]]["selected"]
    assert rows[gone["id"]]["merged"]
    assert not rows[open_["id"]]["merged"] and not rows[open_["id"]]["selected"]
    assert rows[nobranch["id"]]["merged"]
