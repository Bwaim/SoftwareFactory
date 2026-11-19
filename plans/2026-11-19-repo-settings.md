# Workspace Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A settings popup in the dashboard edits the repository settings (`factory.yaml`), the `create-worktree` settings (`config.yaml`) and the server poll interval (`$FACTORY_HOME/server.yaml`), with checks before each save.

**Architecture:** A new `server_settings.py` owns `server.yaml` and gives the poll interval. The server poll loop waits on an event, so a save applies at once. A new `settings.py` reads, checks and saves the workspace settings. It finds column users and moves tasks. `api.py` gets two workspace routes and two global routes. `dashboard.html` gets a "Settings" menu item and the popup.

**Tech Stack:** Python 3 (stdlib + pyyaml), pytest, plain HTML/CSS/JS.

**Spec:** `specs/2026-11-19-repo-settings-design.md`. Read it first. Every task implements the spec sections it names.

## Global Constraints

- All code changes stay in `software-factory/`. Work on branch `settings`. `main` must not change.
- No code comments. No docstrings. Match the style of the surrounding code (short functions).
- Commit messages: short, plain. Never add a `Co-Authored-By` line.
- Run tests from `software-factory/` with `uv run --with pytest --with pyyaml pytest -q <paths>`.
- In Tasks 1 to 5, run only the test files that the task adds or changes. Do not run the full suite. Task 6 runs the full suite.
- Tests never write to the real `~/.config`. The autouse fixture `factory_home` in `tests/conftest.py` already sets `FACTORY_HOME`.
- No browser `alert`, `confirm`, or `prompt` in pages.
- Exact texts (copy them as written):
  - Poll range: `The poll interval must be a whole number from 10 to 86400 seconds.`
  - Unknown key: ``Unknown setting `<key>`.``
  - Library not absolute: `Give the full path of the library folder.`
  - Library missing: `LIBRARY_MISSING`, moved from `api.py` to `init.py` (`The library folder does not exist. Create it, or leave the field blank.`). `api.py` and `settings.py` import it from `init.py`.
  - Library warning: `Tasks not finished: <n>. Steps and pipelines from the old library can disappear.`
  - Unknown terminal: ``Unknown terminal `<name>`.``
  - Terminal blocked: `Finish or cancel the open tasks (<n>) before you change the terminal.`
  - Wrong type: ``The setting `<key>` has a wrong type.`` (`<key>` is the dotted path, for example `steps.create-worktree.base_ref`)
  - Unknown step setting: ``Unknown setting `steps.<id>`.`` and ``Unknown setting `steps.<id>.<key>`.``
  - Worktree empty: `The worktree folder cannot be empty.`
  - Worktree not absolute: `Give the full path of the worktree folder.`
  - Bad config file: the `FactoryError` text of `fsio.read_yaml` or `fsio.require_map` on `config.yaml`.
  - No column: `Add at least one column.`
  - Empty column: `A column name cannot be empty.`
  - Reserved: ``The column `Done` is reserved.``
  - Duplicate: ``The column `<name>` is two times in the list.``
  - Too long: ``The column name `<name>` is longer than 40 characters.``
  - Column user: ``The column `<name>` is used in <path>. Change that file first.``
  - Bad move: ``Move the tasks of `<name>` to a column of the new list.``
  - Ticket scheme: `The ticket URL must start with http:// or https://.`
  - Ticket key: `The ticket URL must contain {key}.`
  - Not hidden: ``The step `<id>` is not hidden.``
  - Failed save: `Settings not saved.` (with `errors`)
  - Missing moves: `Choose a column for the tasks in removed columns.` (with `code: "moves_needed"` and `moves_needed`)
  - Step hint: ``Used by the built-in step `create-worktree` only.``
  - Server hint: `Applies to all workspaces.`
  - Env lock: `Set by FACTORY_POLL_SECONDS (<n> seconds).`
  - Save note: `Save rewrites .factory/factory.yaml and .factory/config.yaml. Comments in these files are lost.`
  - No hidden steps: `No hidden steps.`
  - Checkbox: `Create the folder if it is missing`
  - Ticket default: `https://nextory.atlassian.net/browse/{key}` (`init.TICKET_DEFAULT`)
- Import direction: `settings.py` imports `init.py`. `init.py` never imports `settings.py`.

## Review Focus

1. The user removes a column and the library changes in the same save. Expected: `check` finds column users in the new library, not the old one. Test in Task 2 (`test_check_uses_new_library`).
2. A step file or a pipeline file in a level root has invalid YAML. Expected: the column check skips it and the save still works. Test in Task 2 (`test_column_users_skip_broken_files`).
3. A finished task has a removed column. Expected: no `moves_needed` for it, and it is not moved. Test in Task 2 (`test_finished_tasks_are_not_moved`).
4. One field is valid and another field fails, or `config.yaml` is not valid YAML. Expected: no file changes. Test in Task 3 (`test_failed_check_writes_nothing`) and Task 2 (`test_bad_config_file`).
5. `FACTORY_POLL_SECONDS` is not a number, or `server.yaml` is not valid YAML. Expected: the server goes to the next value, and the poll loop keeps running. Tests in Task 1 (`test_invalid_env_falls_back`, `test_bad_file_falls_back`).

---

### Task 1: Server settings file and poll wake

Spec: "Section Server", "API" 2.

**Files:**
- Create: `lib/factory/server_settings.py`
- Modify: `lib/factory/server.py` (`poll_interval`, `Server.__init__`, `Server.poll_loop`, new `Server.reschedule`)
- Modify: `lib/factory/api.py` (two global routes)
- Modify: `tests/serverutil.py` (`GLOBAL` gets `"/api/server-settings"`)
- Test: `tests/test_server_settings.py`

**Interfaces:**
- Produces (in `factory.server_settings`):
  - `POLL_MIN = 10`, `POLL_MAX = 86400`, `POLL_DEFAULT = 300`
  - `path() -> Path`: `workspaces.home() / "server.yaml"`
  - `env_poll() -> int | None`: `FACTORY_POLL_SECONDS` as an int, None if missing or not a number.
  - `saved_poll() -> int | None`: `poll_seconds` from the file if it is an int in range, else None. It returns None if the file cannot be read or parsed (catch `FactoryError` and `OSError`).
  - `poll_seconds() -> int`: `env_poll()`, then `saved_poll()`, then `POLL_DEFAULT`.
  - `read() -> dict`: `{"poll_seconds", "saved_poll_seconds", "env_poll_seconds", "default_poll_seconds"}`.
  - `save(body: dict) -> dict`: `poll_seconds` None or `""` removes the key. A bool, a non-int, or a value out of range raises `FactoryError` (poll range text). Writes with `fsio.update_yaml`. Returns `read()`.
- Produces (in `factory.server`): `poll_interval()` returns `server_settings.poll_seconds()`. `Server.wake` is a `threading.Event`. `Server.reschedule()` sets it.
- Produces routes: `GET /api/server-settings` returns `read()`. `POST /api/server-settings/save` calls `save(body)`, then `server.reschedule()`, and returns the result.

- [ ] **Step 1: Write the failing tests**

```python
def test_poll_order(monkeypatch):
    monkeypatch.delenv("FACTORY_POLL_SECONDS", raising=False)
    assert server_settings.poll_seconds() == 300
    server_settings.save({"poll_seconds": 60})
    assert server_settings.poll_seconds() == 60
    monkeypatch.setenv("FACTORY_POLL_SECONDS", "5")
    assert server_settings.poll_seconds() == 5
    assert server_settings.read() == {"poll_seconds": 5, "saved_poll_seconds": 60, "env_poll_seconds": 5, "default_poll_seconds": 300}

def test_invalid_env_falls_back(monkeypatch):
    server_settings.save({"poll_seconds": 45})
    monkeypatch.setenv("FACTORY_POLL_SECONDS", "abc")
    assert server_settings.poll_seconds() == 45

def test_bad_file_falls_back(monkeypatch):
    monkeypatch.delenv("FACTORY_POLL_SECONDS", raising=False)
    server_settings.path().parent.mkdir(parents=True, exist_ok=True)
    server_settings.path().write_text("poll_seconds: [")
    assert server_settings.poll_seconds() == 300

@pytest.mark.parametrize("value", [9, 86401, "60", 1.5, True])
def test_save_rejects(value):
    with pytest.raises(FactoryError, match="whole number from 10 to 86400"):
        server_settings.save({"poll_seconds": value})

def test_empty_removes_key():
    server_settings.save({"poll_seconds": 60})
    server_settings.save({"poll_seconds": None})
    assert "poll_seconds" not in (yaml.safe_load(server_settings.path().read_text()) or {})

def test_reschedule_wakes_loop_without_poll(monkeypatch):
    monkeypatch.delenv("FACTORY_POLL_SECONDS", raising=False)
    s = server.Server()
    polls = []
    monkeypatch.setattr(s, "poll_all", lambda: polls.append(1))
    threading.Thread(target=s.poll_loop, daemon=True).start()
    wait_until(lambda: s.next_poll is not None)
    first = s.next_poll
    server_settings.save({"poll_seconds": 10})
    s.reschedule()
    wait_until(lambda: s.next_poll != first)
    assert s.next_poll - time.time() <= 11 and polls == []
    s.httpd.server_close()

def test_routes(inited):
    inited.factory("dashboard")
    i = info()
    assert request(i, "POST", "/api/server-settings/save", {"poll_seconds": 120})[1]["saved_poll_seconds"] == 120
    assert request(i, "GET", "/api/server-settings")[1]["saved_poll_seconds"] == 120
    status, body = request(i, "POST", "/api/server-settings/save", {"poll_seconds": 5})
    assert status == 400 and "whole number" in body["error"]
```

`wait_until(fn, seconds=5)` is a small loop helper in the test file.

- [ ] **Step 2: Run the tests and make sure that they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_server_settings.py`
Expected: FAIL (`server_settings` does not exist).

- [ ] **Step 3: Implement `server_settings.py`, the server changes and the routes**

`poll_loop` waits with `self.wake.wait(interval)`. If the wait returns True, clear the event and start the loop again without `poll_all`. Remove `POLL_SECONDS` from `server.py`.

- [ ] **Step 4: Run the tests and make sure that they pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_server_settings.py tests/test_global_server.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/factory/server_settings.py lib/factory/server.py lib/factory/api.py tests/serverutil.py tests/test_server_settings.py
git commit -m "Server settings file with a poll interval that applies at once"
```

### Task 2: Workspace settings read and check

Spec: "Section Repository", "Section Built-in step settings", "Save" 2.

**Files:**
- Modify: `lib/factory/errors.py` (move `DetailedError` here from `api.py`. `api.py` imports it.)
- Modify: `lib/factory/init.py` (new `TICKET_DEFAULT`, `LIBRARY_MISSING` moved here from `api.py`)
- Modify: `lib/factory/api.py` (imports `DetailedError` and `LIBRARY_MISSING`)
- Create: `lib/factory/settings.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces (in `factory.errors`): `DetailedError(message, **details)`, same as the current class in `api.py`.
- Produces (in `factory.init`): `TICKET_DEFAULT = "https://nextory.atlassian.net/browse/{key}"`, `LIBRARY_MISSING`.
- Produces (in `factory.settings`):
  - `TERMINALS = ("herdr",)`, `WORKTREE_STEP = "create-worktree"`, `STEP_KEYS = ("worktree_root", "base_ref")`, `MAX_COLUMN = 40`, `KEYS = ("library", "create_library", "terminal", "columns", "moves", "ticket_url", "unhide", "steps")`
  - Types: `library`, `terminal`, `ticket_url` and step values are `str`. `create_library` is `bool`. `columns` and `unhide` are lists of `str`. `moves` and `steps` are maps of `str`. A wrong type gives the wrong type error and skips the other rules of that key.
  - `read(ctx) -> dict`: `{"library": str, "terminal": str, "terminals": list[str], "columns": list[str], "ticket_url": str, "ticket_default": str, "hidden_steps": list[str], "steps": {"create-worktree": {"worktree_root": str, "base_ref": str}}, "open_tasks": int}`. A missing value is `""`. `terminals` is `TERMINALS` plus the saved terminal if it is not in `TERMINALS`.
  - `column_users(ctx, library: Path | None, columns: set[str]) -> dict[str, list[str]]`: for each column in `columns`, the sorted paths of the files that name it. It reads `steps/*.md` and `pipelines/*.yaml` in the builtin root, `library` (if not None), and `ctx.fdir`. It skips files that it cannot read or parse (`registry.parse_step_text` for steps).
  - `tasks_in(ctx, columns: set[str]) -> dict[str, list[str]]`: for each column in `columns`, the sorted ids of open tasks whose `column` is that column, or whose `steps` has an entry with that `column`. Columns without such a task are left out.
  - `check(ctx, changes: dict) -> dict`: `{"errors": list[str], "warnings": list[str], "moves_needed": dict[str, list[str]], "library": Path | None}`. `library` is the resolved library of this save. Rules and texts: spec "Section Repository", "Section Built-in step settings", "Save" 2, and the Global Constraints. `moves_needed` holds only the columns without a valid entry in `changes["moves"]`. If `steps` is in `changes`, `check` reads `config.yaml` with `fsio.read_yaml` and `fsio.require_map` and adds the `FactoryError` text to `errors`.

- [ ] **Step 1: Write the failing tests**

One test for each rule. Names and assertions:

```python
def test_read_defaults(inited):
    s = settings.read(ctx(inited))
    assert s["columns"] == repo.DEFAULT_COLUMNS and s["terminal"] == "fake"
    assert s["terminals"] == ["herdr", "fake"] and s["ticket_default"] == "https://nextory.atlassian.net/browse/{key}"
    assert s["steps"]["create-worktree"]["worktree_root"] == str(inited.work / "worktrees") and s["steps"]["create-worktree"]["base_ref"] == ""

def test_unknown_key(inited): assert errors(inited, {"nope": 1}) == ["Unknown setting `nope`."]

@pytest.mark.parametrize("columns, text", [
    ([], "Add at least one column."),
    (["A", " "], "A column name cannot be empty."),
    (["A", "Done"], "The column `Done` is reserved."),
    (["A", "A "], "The column `A` is two times in the list."),
    (["x" * 41], f"The column name `{'x' * 41}` is longer than 40 characters."),
])
def test_column_rules(inited, columns, text): assert text in errors(inited, {"columns": columns})

def test_removed_column_with_user(inited):
    p = write_pipeline(inited.fdir, {"id": "p", "start_column": "Plan", "steps": ["user-validation"]})
    cols = [c for c in repo.DEFAULT_COLUMNS if c != "Plan"]
    assert errors(inited, {"columns": cols}) == [f"The column `Plan` is used in {p}. Change that file first."]

def test_check_uses_new_library(inited, tmp_path):
    cols = repo.DEFAULT_COLUMNS[:-1]
    old_user = write_step(inited.library, "s1", {"column": "QA"})
    new_lib = tmp_path / "lib2"
    (new_lib / "steps").mkdir(parents=True)
    assert errors(inited, {"columns": cols, "library": str(new_lib)}) == []
    old_user.unlink()
    new_user = write_step(new_lib, "s2", {"column": "QA"})
    assert errors(inited, {"columns": cols}) == []
    assert errors(inited, {"columns": cols, "library": str(new_lib)}) == [f"The column `QA` is used in {new_user}. Change that file first."]

def test_task_snapshot_needs_move(inited):
    step = {"id": "s", "path": ["s"], "with": {}, "column": "QA", "model": None, "effort": None}
    make_task(ctx(inited), tid="t1", column="Plan", steps=[step])
    result = settings.check(ctx(inited), {"columns": repo.DEFAULT_COLUMNS[:-1]})
    assert result["errors"] == [] and result["moves_needed"] == {"QA": ["t1"]}

def test_column_users_skip_broken_files(inited):
    (inited.fdir / "pipelines" / "bad.yaml").write_text("a: [")
    assert settings.column_users(ctx(inited), None, {"QA"}) == {}

def test_moves_needed(inited):
    make_task(ctx(inited), tid="t1", column="QA")
    cols = repo.DEFAULT_COLUMNS[:-1]
    assert settings.check(ctx(inited), {"columns": cols})["moves_needed"] == {"QA": ["t1"]}
    assert settings.check(ctx(inited), {"columns": cols, "moves": {"QA": "Review"}})["moves_needed"] == {}
    assert "Move the tasks of `QA` to a column of the new list." in errors(inited, {"columns": cols, "moves": {"QA": "QA"}})

def test_finished_tasks_are_not_moved(inited):
    make_task(ctx(inited), tid="t1", column="QA", status="finished")
    assert settings.check(ctx(inited), {"columns": repo.DEFAULT_COLUMNS[:-1]})["moves_needed"] == {}

def test_library_rules(inited, tmp_path):
    assert errors(inited, {"library": "rel/path"}) == ["Give the full path of the library folder."]
    assert errors(inited, {"library": str(tmp_path / "none")}) == ["The library folder does not exist. Create it, or leave the field blank."]
    assert errors(inited, {"library": str(tmp_path / "none"), "create_library": True}) == []
    assert errors(inited, {"library": ""}) == []

def test_library_warning_with_open_tasks(inited):
    make_task(ctx(inited))
    assert settings.check(ctx(inited), {"library": ""})["warnings"] == ["Tasks not finished: 1. Steps and pipelines from the old library can disappear."]

def test_terminal_rules(inited):
    assert errors(inited, {"terminal": "nope"}) == ["Unknown terminal `nope`."]
    make_task(ctx(inited))
    assert errors(inited, {"terminal": "herdr"}) == ["Finish or cancel the open tasks (1) before you change the terminal."]
    assert errors(inited, {"terminal": "fake"}) == []

@pytest.mark.parametrize("url, text", [
    ("ftp://x/{key}", "The ticket URL must start with http:// or https://."),
    ("https://x/browse", "The ticket URL must contain {key}."),
])
def test_ticket_rules(inited, url, text): assert errors(inited, {"ticket_url": url}) == [text]

def test_only_unhide(inited): assert errors(inited, {"unhide": ["create-task"]}) == ["The step `create-task` is not hidden."]

@pytest.mark.parametrize("changes, text", [
    ({"columns": "A"}, "The setting `columns` has a wrong type."),
    ({"columns": ["A", 1]}, "The setting `columns` has a wrong type."),
    ({"create_library": "yes"}, "The setting `create_library` has a wrong type."),
    ({"steps": {"create-worktree": {"base_ref": 3}}}, "The setting `steps.create-worktree.base_ref` has a wrong type."),
    ({"steps": {"rebase": {}}}, "Unknown setting `steps.rebase`."),
    ({"steps": {"create-worktree": {"nope": "x"}}}, "Unknown setting `steps.create-worktree.nope`."),
])
def test_type_and_step_rules(inited, changes, text): assert errors(inited, changes) == [text]

@pytest.mark.parametrize("value, text", [
    ("", "The worktree folder cannot be empty."),
    ("rel/wt", "Give the full path of the worktree folder."),
])
def test_worktree_rules(inited, value, text):
    assert errors(inited, {"steps": {"create-worktree": {"worktree_root": value}}}) == [text]

def test_bad_config_file(inited):
    (inited.fdir / "config.yaml").write_text("a: [")
    assert len(errors(inited, {"steps": {"create-worktree": {"base_ref": "b"}}})) == 1
```

`ctx(inited)` returns `repo.load_ctx(cwd=inited.repo)`. `errors(inited, changes)` returns `settings.check(ctx(inited), changes)["errors"]`.

- [ ] **Step 2: Run the tests and make sure that they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_settings.py`
Expected: FAIL (`settings` does not exist).

- [ ] **Step 3: Move `DetailedError` and `LIBRARY_MISSING`, add `TICKET_DEFAULT`, and implement `read`, `column_users`, `tasks_in` and `check`**

A library change is a change only if the resolved path differs from `ctx.library()`. A terminal change is a change only if the value differs from the saved value. The removed columns are `set(ctx.columns()) - set(new columns)`.

- [ ] **Step 4: Run the tests and make sure that they pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_settings.py tests/test_global_server.py`
Expected: PASS. (`test_global_server.py` covers the `DetailedError` move through the add route.)

- [ ] **Step 5: Commit**

```bash
git add lib/factory/errors.py lib/factory/init.py lib/factory/api.py lib/factory/settings.py tests/test_settings.py
git commit -m "Read and check workspace settings"
```

### Task 3: Workspace settings save, routes and init default

Spec: "Save", "API" 1, "Section Repository" 4 (init default).

**Files:**
- Modify: `lib/factory/settings.py` (new `save`)
- Modify: `lib/factory/api.py` (two workspace routes)
- Modify: `lib/factory/init.py` (`ticket_url` default is `TICKET_DEFAULT`)
- Test: `tests/test_settings.py`, `tests/test_settings_api.py`

**Interfaces:**
- Consumes: `settings.check`, `settings.read`, `errors.DetailedError`, `init.create_library_folder`.
- Produces: `settings.save(ctx, changes: dict) -> dict` returns `{"settings": read(ctx), "warnings": list[str]}`.
  - If `check` has errors: raise `DetailedError("Settings not saved.", errors=[...])`.
  - If `check` has `moves_needed`: raise `DetailedError("Choose a column for the tasks in removed columns.", code="moves_needed", moves_needed={...})`.
  - Else: create the library folder if `create_library` is true and the folder is missing.
  - Write the changed `factory.yaml` keys in one `fsio.update_yaml` call: `library` as the resolved path string or `""`, and `unhide` removes its ids from `hidden_steps` inside the update function (pop the key when the list is empty). Skip the call if no `factory.yaml` key changed.
  - Write the `create-worktree` keys in one `fsio.update_yaml` call on `config.yaml`: an empty `base_ref` pops the key, an empty section is popped. Skip the call if `steps` is not in `changes`.
  - Update each task of `tasks_in` with one `state.update` call. Inside the update function, change `column` only if it is still a removed column, and replace each removed column in the `column` of the `steps` entries with its target. Skip a task that no longer exists (catch the `FactoryError` of `state.update`). Log `events.log(ctx, tid, "column_changed", None, **{"from": old, "to": new})` only when `column` changed.
- Produces routes: `GET /api/settings` returns `settings.read(server.ctx)`. `POST /api/settings/save` returns `settings.save(server.ctx, body)`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_settings.py`:

```python
def test_save_writes_only_changed_keys(inited):
    before = yaml.safe_load((inited.fdir / "factory.yaml").read_text())
    settings.save(ctx(inited), {"ticket_url": "https://x/{key}"})
    after = yaml.safe_load((inited.fdir / "factory.yaml").read_text())
    assert after == {**before, "ticket_url": "https://x/{key}"}

def test_save_moves_tasks_and_logs(inited):
    make_task(ctx(inited), tid="t1", column="QA")
    settings.save(ctx(inited), {"columns": repo.DEFAULT_COLUMNS[:-1], "moves": {"QA": "Review"}})
    assert task_json(inited.fdir, "t1")["column"] == "Review"
    ev = events(inited.fdir, "t1")[-1]
    assert (ev["type"], ev["from"], ev["to"]) == ("column_changed", "QA", "Review")

def test_save_step_keys(inited, tmp_path):
    settings.save(ctx(inited), {"steps": {"create-worktree": {"base_ref": "develop", "worktree_root": str(tmp_path / "wt")}}})
    assert config.get_value(ctx(inited), "create-worktree", "base_ref") == "develop"
    assert config.get_value(ctx(inited), "create-worktree", "worktree_root") == str(tmp_path / "wt")
    settings.save(ctx(inited), {"steps": {"create-worktree": {"base_ref": ""}}})
    assert config.get_value(ctx(inited), "create-worktree", "base_ref") is None

def test_save_replaces_snapshot_column(inited):
    step = {"id": "s", "path": ["s"], "with": {}, "column": "QA", "model": None, "effort": None}
    make_task(ctx(inited), tid="t1", column="Plan", steps=[step])
    settings.save(ctx(inited), {"columns": repo.DEFAULT_COLUMNS[:-1], "moves": {"QA": "Review"}})
    task = task_json(inited.fdir, "t1")
    assert task["column"] == "Plan" and task["steps"][0]["column"] == "Review"

def test_save_unhide_keeps_other_hidden(inited):
    hidden.hide(ctx(inited), "create-task")
    hidden.hide(ctx(inited), "delete-task")
    settings.save(ctx(inited), {"unhide": ["create-task"]})
    assert hidden.ids(ctx(inited)) == ["delete-task"]
    settings.save(ctx(inited), {"unhide": ["delete-task"]})
    assert "hidden_steps" not in yaml.safe_load((inited.fdir / "factory.yaml").read_text())

def test_save_skips_unchanged_file(inited):
    path = inited.fdir / "factory.yaml"
    path.write_text("# keep\n" + path.read_text())
    settings.save(ctx(inited), {"steps": {"create-worktree": {"base_ref": "develop"}}})
    assert path.read_text().startswith("# keep")

def test_save_creates_library(inited, tmp_path):
    settings.save(ctx(inited), {"library": str(tmp_path / "new"), "create_library": True})
    assert (tmp_path / "new" / "factory.yaml").exists() and ctx(inited).library() == (tmp_path / "new").resolve()

def test_failed_check_writes_nothing(inited):
    paths = [inited.fdir / "factory.yaml", inited.fdir / "config.yaml"]
    before = [p.read_text() for p in paths]
    with pytest.raises(DetailedError) as e:
        settings.save(ctx(inited), {"ticket_url": "https://x/{key}", "steps": {"create-worktree": {"base_ref": "b"}}, "columns": []})
    assert e.value.details["errors"] == ["Add at least one column."]
    assert [p.read_text() for p in paths] == before

def test_save_moves_needed(inited):
    make_task(ctx(inited), tid="t1", column="QA")
    with pytest.raises(DetailedError) as e:
        settings.save(ctx(inited), {"columns": repo.DEFAULT_COLUMNS[:-1]})
    assert e.value.details == {"code": "moves_needed", "moves_needed": {"QA": ["t1"]}}
```

In `tests/test_settings_api.py`, write a `dash` fixture: `inited.factory("dashboard")`, yield `inited, serverutil.info(inited.fdir)`, then `inited.factory("server", "stop", check=False)`. Do not copy the `dash` fixture of `tests/test_dashboard_api.py`: it writes a step with `column: Plan`, and the save of `["A", "B"]` then fails with a column user error.

```python
def test_get_and_save(dash):
    inited, i = dash
    assert request(i, "GET", "/api/settings")[1]["columns"] == repo.DEFAULT_COLUMNS
    status, body = request(i, "POST", "/api/settings/save", {"columns": ["A", "B"]})
    assert status == 200 and body["settings"]["columns"] == ["A", "B"]
    assert request(i, "GET", "/api/info")[1]["columns"] == ["A", "B"]

def test_save_errors_are_400(dash):
    inited, i = dash
    status, body = request(i, "POST", "/api/settings/save", {"columns": []})
    assert status == 400 and body["error"] == "Settings not saved." and body["errors"] == ["Add at least one column."]
```

In the existing init test file that reads `factory.yaml` after `factory init` (`tests/test_init_menu.py`), add an assertion: `ticket_url == "https://nextory.atlassian.net/browse/{key}"`.

- [ ] **Step 2: Run the tests and make sure that they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_settings.py tests/test_settings_api.py tests/test_init_menu.py`
Expected: FAIL (no `save`, no routes, old init default).

- [ ] **Step 3: Implement `save`, the routes and the init default**

`init.py` uses its own `TICKET_DEFAULT` for `ticket_url`. It does not import `settings.py`.

- [ ] **Step 4: Run the tests and make sure that they pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_settings.py tests/test_settings_api.py tests/test_init_menu.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/factory/settings.py lib/factory/api.py lib/factory/init.py tests/test_settings.py tests/test_settings_api.py tests/test_init_menu.py
git commit -m "Save workspace settings from the API"
```

### Task 4: Settings popup in the dashboard

Spec: "Goals" 1 and 2, all three sections, "Save" 1, 4, 5 and 6.

**Files:**
- Modify: `lib/factory/web/dashboard.html`
- Test: `tests/test_dashboard_page.py`

**Interfaces:**
- Consumes: `GET /api/settings`, `POST /api/settings/save`, `GET /api/server-settings`, `POST /api/server-settings/save`, `GET /api/host`, `POST /api/workspaces/pick-folder`.
- Produces (page functions): `openSettings(ws)`, `settingsForm(data, server)`, `columnsEditor(columns)`, `movesBlock(movesNeeded, columns)`, `saveSettings(form)`.

- [ ] **Step 1: Write the failing test**

```python
def test_settings_popup():
    for text in ['button("Settings"', "openSettings", "/api/settings", "/api/settings/save", "/api/server-settings",
                 "Repository", "Built-in step settings", "Server", "Add column", "moves_needed", "Unhide",
                 "Create the folder if it is missing", "No hidden steps.", "Used by the built-in step `create-worktree` only.",
                 "Applies to all workspaces.", "Set by FACTORY_POLL_SECONDS (", "https://nextory.atlassian.net/browse/{key}",
                 "Save rewrites .factory/factory.yaml and .factory/config.yaml. Comments in these files are lost."]:
        assert text in PAGE
    assert "server-settings" in PAGE[PAGE.index("const GLOBAL_API"):PAGE.index("\n", PAGE.index("const GLOBAL_API"))]
```

- [ ] **Step 2: Run the test and make sure that it fails**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_dashboard_page.py`
Expected: FAIL on `test_settings_popup`.

- [ ] **Step 3: Build the popup**

- `workspaceMenu` gets "Settings" as the first item. It calls `selectWorkspace(ws.id)`, then `openSettings(ws)`.
- `GLOBAL_API` gets `server-settings`.
- The popup uses `showModal` with `dismissable: false`. Reuse `field`, `button`, `failureBox` and the folder picker code of `openAddWorkspace`. Extract the picker row into one function that both use.
- `saveSettings` sends only the changed keys. Hidden steps go as `unhide` (the marked ids). If no repository value changed, it skips the repository save.
- If the repository save returns `code: "moves_needed"`, it shows `movesBlock` in the popup, and the next Save adds `moves`. If the response has `errors`, it shows each one.
- After a successful repository save, it saves the server settings if they changed. If that save fails, the popup stays open and shows the error. Else it closes the popup and calls `refresh(true)`.
- `worktree_root` has no empty option in the form. The server check rejects an empty value.
- When the library field differs from the saved value and `open_tasks > 0`, show the library warning text under the field.

- [ ] **Step 4: Run the test and make sure that it passes**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_dashboard_page.py`
Expected: PASS.

- [ ] **Step 5: Check the page by hand**

Run `factory dashboard` in a test repository. Open Settings from the "⋯" menu. Remove a column that holds a task, choose a target column, and save. Make sure that the board shows the new columns and the task in the target column.

- [ ] **Step 6: Commit**

```bash
git add lib/factory/web/dashboard.html tests/test_dashboard_page.py
git commit -m "Settings popup in the dashboard"
```

### Task 5: README

Spec: "Docs".

**Files:**
- Modify: `README.md` (the dashboard part, the `$FACTORY_HOME` files list, the `.factory/factory.yaml` fields section)
- Test: `tests/test_docs.py`

- [ ] **Step 1: Write the docs**

- Add a "Settings" section under the dashboard part. It lists the three popup sections, the column rules, the move of tasks, and the note about lost comments.
- Add `server.yaml` to the `$FACTORY_HOME` files list.
- Change the poll sentence to: `The poll interval is FACTORY_POLL_SECONDS, else poll_seconds in $FACTORY_HOME/server.yaml, else 5 minutes.` Use code spans for the names.
- Say that `factory init` writes the Nextory ticket URL as the default `ticket_url`.

- [ ] **Step 2: Run the docs test**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_docs.py`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document the settings popup"
```

### Task 6: Full test run

- [ ] **Step 1: Run all tests**

Run: `uv run --with pytest --with pyyaml pytest -q tests`
Expected: all tests pass. If a test fails, fix the cause in the task that owns the code, run that test file again, and commit the fix.
