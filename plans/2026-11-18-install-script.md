# Standalone Install Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install the `factory` CLI with `curl -fsSL https://raw.githubusercontent.com/Bwaim/SoftwareFactory/main/install.sh | sh`, with no Claude marketplace, no git clone and no skills.

**Architecture:** A `v*` tag starts a GitHub Actions workflow. The workflow runs `scripts/build-release.sh`, which writes `software-factory.tar.gz` (only the runtime folders and a `VERSION` file) and `software-factory.tar.gz.sha256`, and attaches both to a GitHub release. `install.sh` downloads both files from `releases/latest/download/`, checks the SHA-256, swaps the archive into `~/.local/share/software-factory` and links `~/.local/bin/factory`. `ensure_link` keeps a link that points into a standalone install, so the plugin skill and `factory init` do not move it back to the plugin cache.

**Tech Stack:** POSIX `sh`, `curl`, `tar`, GitHub Actions, pytest.

**Spec:** No spec file. The decisions come from the conversation of 2026-11-18 and two reviews of the same day. They are listed in Global Constraints.

## Global Constraints

- Work on branch `install_script`. Do not change `main`.
- New files at the repository root: `install.sh`, `scripts/build-release.sh`, `.github/workflows/release.yml`. All other changes stay in `software-factory/`.
- Do not install, copy or link the skills. Do not change `skills/`, `.claude-plugin/` or `software-factory/.claude-plugin/`.
- Repository: `Bwaim/SoftwareFactory`, public. No token. No GitHub API call. No JSON parsing.
- Release assets, fixed names: `software-factory.tar.gz` and `software-factory.tar.gz.sha256`.
  - The archive has the top folder `software-factory/` with `VERSION`, `bin/`, `lib/`, `builtin/`, `catalog/`, `migrations/`, and no `__pycache__/`. `VERSION` holds the version and a newline.
  - The `.sha256` file is one line: `<64 lowercase hex>  software-factory.tar.gz`.
- The tag is `v<version>`. `<version>` must equal `VERSION` in `software-factory/lib/factory/cli.py` (today `0.1.0`).
- Download base: `$FACTORY_INSTALL_DOWNLOAD_BASE`, default `https://github.com/Bwaim/SoftwareFactory/releases/latest/download`. The script downloads `<base>/software-factory.tar.gz` and `<base>/software-factory.tar.gz.sha256`.
- curl options for every request: `-fsSL --proto "$FACTORY_INSTALL_PROTO" --proto-redir "$FACTORY_INSTALL_PROTO"`. `FACTORY_INSTALL_PROTO` default: `=https`.
- If a new release appears between the two downloads, the digest check fails and the install stops. Add no retry code.
- Install folder: `$FACTORY_INSTALL_DIR`, default `$HOME/.local/share/software-factory`. Marker file inside it: `.installed-by-script`. Link folder: `$FACTORY_LINK_DIR`, default `$HOME/.local/bin` (same variable as `lib/factory/init.py:21`).
- `install.sh` shape: all code is in a function `main`. The first line of `main` is `set -eu`. The last line of the file is `main "$@"`. Each command that can read stdin gets its own stdin: a heredoc or `</dev/null`. Call `mv` only as `mv <src> <dst>`, with no options.
- Extract with `tar -xzf <archive> -C <stage> --strip-components=1`. The staging folder then holds `VERSION`, `bin/` and the other folders directly, with no `software-factory/` level.
- Glob loops over leftover folders use `for b in "$dir".backup.*; do [ -d "$b" ] || continue; ...; done`. Never parse `ls` output.
- The script touches only the leftover folders it makes: `<dir>.backup.<digits>` and `<dir>.stage.<digits>`. In the loop, skip other names with `case "$b" in *.backup.*[!0-9]*) continue;; esac` (same for `.stage.`).
- Platforms: macOS and Linux. Use `shasum -a 256` on macOS and `sha256sum` on Linux.
- Required on `PATH`: `curl`, `tar`, `uv`, `git`, `claude`. Missing one: stop. `herdr` missing: warn and continue.
- Every error line starts with `factory install: ` and goes to stderr. Exit code 1.
- Exact texts:
  - Missing tool: `factory install: <tool> is required.`
  - Herdr warning: `factory install: herdr is not on PATH. Tasks need it to start. Install it from https://herdr.dev`
  - Bad digest file: `factory install: The latest release has no valid software-factory.tar.gz.sha256.`
  - Digest mismatch: `factory install: The downloaded archive SHA-256 differs from the release digest. The existing install is unchanged.`
  - Unmanaged folder: `factory install: <dir> exists and was not made by this script. Move it away, then run again.`
  - Link is a file: `factory install: <link> exists and is not a link. Move it away, then run again.`
  - Link replaced: `Replaced the link <link>, it pointed to <old target>.`
  - Backup restored: `Restored the previous install from <backup>.`
  - Success: `Installed factory <version> in <dir>.`
  - PATH warning: `Add <link dir> to your PATH.`
  - `lib/factory/migrate.py:44`: `The data is newer than this factory. Run the install script again to update it.`
  - `lib/factory/version.py:27`, `:32` and `:41`, as Python strings (the backticks are part of the messages):

```python
"The factory is not initialized in this repository. Run `factory init --library <path>`."
"Run `factory migrate`, or run the install script again to update the factory."
```

    The second string replaces `"Start the orchestrator to migrate, or update the factory."` at `:32` and `:41`. The first sentence of those two messages does not change.
- No code comments. Commit messages: short, plain. Never add a `Co-Authored-By` line.
- Run tests from `software-factory/` with `uv run --with pytest --with pyyaml pytest -q <paths>`.

## Review Focus

1. The swap fails after the old folder moved away: the old folder comes back. Test in Task 3 with an `mv` stub.
2. A run stopped between the two `mv` commands: the next run restores the backup before anything else. Test in Task 3.
3. The script runs through a pipe (`cat install.sh | sh`), like `curl | sh`. Test in Task 2.
4. `~/.local/bin/factory` points into a standalone install, then the plugin runs `factory link` or `factory init`: the link stays. Test in Task 4.
5. `$HOME` path with a space: every path in `install.sh` is quoted. Tests in Task 2 use a `HOME` with a space.

---

### Task 1: Release archive and workflow

**Files:**
- Create: `scripts/build-release.sh`
- Create: `.github/workflows/release.yml`
- Test: `software-factory/tests/test_release_build.py`

**Interfaces:**
- Produces: `sh scripts/build-release.sh <version> <out dir>`. It writes `<out dir>/software-factory.tar.gz` and `<out dir>/software-factory.tar.gz.sha256`. It exits 1 with `build-release: version <version> differs from cli.VERSION <cli version>.` when they differ.

- [ ] **Step 1: Write the failing tests**

```python
def test_archive_has_only_runtime_files(work):
    out = run_build("0.1.0", work)
    names = tar_names(out)
    tops = {n.split("/")[1] for n in names if n.count("/") >= 1 and n.split("/")[1]}
    assert tops == {"VERSION", "bin", "lib", "builtin", "catalog", "migrations"}
    assert all(n.startswith("software-factory/") or n == "software-factory" for n in names)
    assert not any("__pycache__" in n for n in names)

def test_digest_file_matches(work):
    out = run_build("0.1.0", work)
    line = (work / "software-factory.tar.gz.sha256").read_text()
    assert line == f"{hashlib.sha256(out.read_bytes()).hexdigest()}  software-factory.tar.gz\n"

def test_archive_version_and_cli(work):
    out = run_build("0.1.0", work)
    extract(out, work)
    assert (work / "software-factory/VERSION").read_text() == "0.1.0\n"
    r = subprocess.run(["uv", "run", "--script", str(work / "software-factory/bin/factory"), "--version"], capture_output=True, text=True)
    assert "factory 0.1.0" in r.stdout

def test_version_mismatch_fails(work):
    r = subprocess.run(["sh", str(PROJECT_ROOT / "scripts/build-release.sh"), "9.9.9", str(work)], capture_output=True, text=True)
    assert r.returncode == 1
    assert "build-release: version 9.9.9 differs from cli.VERSION 0.1.0." in r.stderr
    assert not list(work.glob("software-factory.tar.gz*"))
```

`run_build` (returns the archive path), `tar_names` and `extract` are small helpers in the test file.

- [ ] **Step 2: Run the tests and make sure they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_release_build.py`
Expected: FAIL, the script does not exist.

- [ ] **Step 3: Write `scripts/build-release.sh`**

Read `VERSION` from `software-factory/lib/factory/cli.py` with `sed`. Copy the five folders into a temporary folder named `software-factory`, write `VERSION`, remove `__pycache__`, then `tar -czf`. Write the `.sha256` file from inside `<out dir>`, so that the file name has no path. Paths are relative to the script location, so it works from any folder.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_release_build.py`
Expected: 4 passed.

- [ ] **Step 5: Write `.github/workflows/release.yml`**

Trigger: `push` of tags `v*`. Permissions: `contents: write`. Steps: `actions/checkout@v4`, then `sh scripts/build-release.sh "${GITHUB_REF_NAME#v}" dist`, then `gh release create "$GITHUB_REF_NAME" dist/software-factory.tar.gz dist/software-factory.tar.gz.sha256 --title "$GITHUB_REF_NAME" --notes ""` with `GH_TOKEN: ${{ github.token }}`. The version check of Step 3 makes the job fail before `gh release create`.

- [ ] **Step 6: Commit**

```bash
git add scripts/build-release.sh .github/workflows/release.yml software-factory/tests/test_release_build.py
git commit -m "Add the release archive build and workflow"
```

### Task 2: install.sh, first install

**Files:**
- Create: `install.sh`
- Test: `software-factory/tests/test_install_script.py`

**Interfaces:**
- Consumes: `scripts/build-release.sh` from Task 1, to make the test files.
- Produces: `install.sh`, run with `sh install.sh`, configured only by the environment variables in Global Constraints. The fixtures `release`, `env`, the helper `run_install(env)` and the `fake bin` folder, used again in Task 3.

Test setup:

- Fixture `release(work)`: runs Task 1 into `work / "dl"` and serves that folder with `http.server` on a free port in a thread. Methods: `write_digest(text)` replaces the `.sha256` file, `remove_digest()` deletes it.
- Fixture `env`:
  - Reads the real `uv cache dir` and `uv python dir` first and passes them as `UV_CACHE_DIR` and `UV_PYTHON_INSTALL_DIR`.
  - Sets `HOME` to `work / "home dir"` (with a space), `FACTORY_INSTALL_DOWNLOAD_BASE=http://127.0.0.1:<port>` and `FACTORY_INSTALL_PROTO==http`.
  - Makes `work / "tools"` with symlinks to the real `uv`, `git`, `curl`, `tar`, `gzip` and `shasum` or `sha256sum` (found with `shutil.which`).
  - Makes `work / "fake bin"` with an executable `claude` stub.
  - Sets `PATH` to `fake bin`, `tools`, `/usr/bin` and `/bin`, in this order. `/bin` holds `sh`, `mv`, `rm`, `mkdir`, `ln` and `cat` on macOS.
- `run_install(env)`: `subprocess.run(["/bin/sh", str(PROJECT_ROOT / "install.sh")], env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_fresh_install(release, env):
    r = run_install(env)
    home = Path(env["HOME"])
    target = home / ".local/share/software-factory"
    assert r.returncode == 0, r.stderr
    assert (target / ".installed-by-script").exists()
    assert os.readlink(home / ".local/bin/factory") == str(target / "bin/factory")
    assert f"Installed factory 0.1.0 in {target}." in r.stdout
    v = subprocess.run([str(home / ".local/bin/factory"), "--version"], capture_output=True, text=True, env=env)
    assert "factory 0.1.0" in v.stdout

def test_install_through_pipe(release, env):
    script = (PROJECT_ROOT / "install.sh").read_text()
    r = subprocess.run(["/bin/sh"], input=script, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (Path(env["HOME"]) / ".local/share/software-factory/.installed-by-script").exists()
    assert "Installed factory 0.1.0" in r.stdout

def test_missing_claude_stops(release, env, work):
    (work / "fake bin/claude").unlink()
    r = run_install(env)
    assert r.returncode == 1
    assert "factory install: claude is required." in r.stderr
    assert not (Path(env["HOME"]) / ".local/share/software-factory").exists()

def test_missing_herdr_warns(release, env):
    r = run_install(env)
    assert r.returncode == 0
    assert "factory install: herdr is not on PATH. Tasks need it to start. Install it from https://herdr.dev" in r.stderr

def test_path_warning(release, env):
    r = run_install(env)
    assert f"Add {Path(env['HOME']) / '.local/bin'} to your PATH." in r.stdout

def test_digest_mismatch_installs_nothing(release, env):
    release.write_digest("0" * 64 + "  software-factory.tar.gz\n")
    r = run_install(env)
    assert r.returncode == 1
    assert "factory install: The downloaded archive SHA-256 differs from the release digest. The existing install is unchanged." in r.stderr
    assert not (Path(env["HOME"]) / ".local/share/software-factory").exists()

@pytest.mark.parametrize("digest", [None, "", "abc  software-factory.tar.gz\n", "z" * 64 + "\n"])
def test_bad_digest_file_refused(release, env, digest):
    release.remove_digest() if digest is None else release.write_digest(digest)
    r = run_install(env)
    assert r.returncode == 1
    assert "factory install: The latest release has no valid software-factory.tar.gz.sha256." in r.stderr
    assert not (Path(env["HOME"]) / ".local/share/software-factory").exists()
```

- [ ] **Step 2: Run the tests and make sure they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_install_script.py`
Expected: FAIL, `install.sh` does not exist.

- [ ] **Step 3: Write `install.sh`**

Order inside `main`: `set -eu`, `umask 022`. Check the tools. Warn about Herdr. Make a work folder with `mktemp -d` and a `trap` that removes it. Download the `.sha256` file. Take its first field and accept it only if it is 64 hex characters (`case` or `grep -Eq '^[0-9a-f]{64}$'`). Download the archive. Compare the SHA-256. Make `<dir>.stage.$$` next to the install folder and extract into it with `--strip-components=1`. Read `<dir>.stage.$$/VERSION`. Write the marker in the staging folder, move the staging folder to the install folder, and make the link. Print the success line, then the PATH warning if the link folder is not in `PATH`.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_install_script.py`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add install.sh software-factory/tests/test_install_script.py
git commit -m "Add the standalone install script"
```

### Task 3: install.sh, update and existing files

**Files:**
- Modify: `install.sh`
- Test: `software-factory/tests/test_install_script.py`

**Interfaces:**
- Consumes: the fixtures and `run_install` of Task 2.

- [ ] **Step 1: Write the failing tests**

```python
def test_second_run_updates(release, env):
    assert run_install(env).returncode == 0
    target = Path(env["HOME"]) / ".local/share/software-factory"
    (target / "old-file").write_text("x")
    r = run_install(env)
    assert r.returncode == 0, r.stderr
    assert not (target / "old-file").exists()
    assert not list(target.parent.glob("software-factory.*"))

def test_failed_swap_restores_old_install(release, env, work):
    assert run_install(env).returncode == 0
    target = Path(env["HOME"]) / ".local/share/software-factory"
    (target / "old-file").write_text("x")
    log = work / "mv.log"
    write_stub(work / "fake bin/mv", f'''printf '%s|%s\\n' "$1" "$2" >> '{log}'
case "$1" in *.stage.*) [ "$2" = '{target}' ] && exit 1;; esac
exec /bin/mv "$@"''')
    assert run_install(env).returncode == 1
    assert (target / "old-file").exists()
    assert not list(target.parent.glob("software-factory.*"))
    calls = log.read_text().splitlines()
    to_backup = next(i for i, c in enumerate(calls) if c.startswith(f"{target}|") and ".backup." in c)
    failed = next(i for i, c in enumerate(calls) if ".stage." in c.split("|")[0] and c.endswith(f"|{target}"))
    assert to_backup < failed

def test_interrupted_run_restores_backup(release, env):
    share = Path(env["HOME"]) / ".local/share"
    backup = share / "software-factory.backup.111"
    backup.mkdir(parents=True)
    (backup / ".installed-by-script").write_text("")
    (backup / "old-file").write_text("x")
    (share / "software-factory.stage.222").mkdir()
    r = run_install(env)
    assert r.returncode == 0, r.stderr
    assert f"Restored the previous install from {backup}." in r.stdout
    assert not list(share.glob("software-factory.*"))

def test_leftovers_removed_when_install_exists(release, env):
    assert run_install(env).returncode == 0
    share = Path(env["HOME"]) / ".local/share"
    (share / "software-factory.backup.111").mkdir()
    (share / "software-factory.stage.222").mkdir()
    assert run_install(env).returncode == 0
    assert not list(share.glob("software-factory.*"))

def test_user_folder_with_similar_name_kept(release, env):
    share = Path(env["HOME"]) / ".local/share"
    user = share / "software-factory.backup.old"
    user.mkdir(parents=True)
    (user / ".installed-by-script").write_text("")
    r = run_install(env)
    assert r.returncode == 0, r.stderr
    assert user.exists()
    assert "Restored the previous install" not in r.stdout

def test_unmanaged_folder_refused(release, env):
    target = Path(env["HOME"]) / ".local/share/software-factory"
    target.mkdir(parents=True)
    r = run_install(env)
    assert r.returncode == 1
    assert f"factory install: {target} exists and was not made by this script. Move it away, then run again." in r.stderr

def test_link_file_refused(release, env):
    link = Path(env["HOME"]) / ".local/bin/factory"
    link.parent.mkdir(parents=True)
    link.write_text("x")
    r = run_install(env)
    assert r.returncode == 1
    assert f"factory install: {link} exists and is not a link. Move it away, then run again." in r.stderr

def test_link_to_other_target_replaced(release, env, work):
    link = Path(env["HOME"]) / ".local/bin/factory"
    link.parent.mkdir(parents=True)
    link.symlink_to(work / "plugin-cache/bin/factory")
    r = run_install(env)
    assert r.returncode == 0
    assert f"Replaced the link {link}, it pointed to {work / 'plugin-cache/bin/factory'}." in r.stdout
    assert os.readlink(link).endswith("software-factory/bin/factory")
```

`write_stub(path, body)` writes `#!/bin/sh` plus the body and makes the file executable.

- [ ] **Step 2: Run the tests and make sure they fail**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_install_script.py`
Expected: the 8 new tests FAIL.

- [ ] **Step 3: Change `install.sh`**

At start, before any download:

1. If `<dir>` does not exist, loop over `<dir>.backup.<digits>` (glob loop of Global Constraints). Move the first folder that has the `.installed-by-script` marker to `<dir>` and print the "Backup restored" line.
2. Remove the other `<dir>.backup.<digits>` and all `<dir>.stage.<digits>` folders, with the same loop.
3. Run the folder and link checks.

Set `backup=""` before the swap. On update, set `backup="$dir.backup.$$"` and move the old folder there. Then write the swap so that it works under `set -eu`, on a first install too:

```sh
if ! mv "$stage" "$dir"; then
  [ -z "$backup" ] || mv "$backup" "$dir"
  exit 1
fi
```

Then remove the backup. The `trap` removes the `.stage.$$` folder in all cases.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_install_script.py`
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git add install.sh software-factory/tests/test_install_script.py
git commit -m "Install script: safe update and link checks"
```

### Task 4: Keep the standalone link

This task implements the user decision F2: the plugin must not move the link of a standalone install. The rule lives in `ensure_link`, not in the skill. Plugin-only users still need the skill to create the link when it is missing, and `factory init` (`init.py:200`) also calls `ensure_link`. `skills/` does not change.

**Files:**
- Modify: `software-factory/lib/factory/init.py:28-44` (`ensure_link`)
- Test: `software-factory/tests/test_init_menu.py`

**Interfaces:**
- Produces: `ensure_link() -> dict` with the keys `path`, `target`, `changed`, `on_path`. `target` is now the real target of the link, not always `cli_path()`.

Rule: if the link exists and `Path(os.path.realpath(link)).parents[1] / ".installed-by-script"` exists, keep the link (`changed` false). Otherwise do what the function does today.

- [ ] **Step 1: Write the failing test**

```python
def test_link_keeps_standalone_install(factory, work):
    install = work / "standalone"
    (install / "bin").mkdir(parents=True)
    (install / "bin/factory").write_text("x")
    (install / ".installed-by-script").write_text("")
    link = work / "bin" / "factory"
    link.unlink()
    link.symlink_to(install / "bin/factory")
    out = factory.json("link")
    assert out["changed"] is False
    assert os.path.realpath(link) == str((install / "bin/factory").resolve())
    assert out["target"] == str((install / "bin/factory").resolve())
```

The existing `test_link_fixes_wrong_target` must still pass.

- [ ] **Step 2: Run the tests and make sure the new one fails**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_init_menu.py`

- [ ] **Step 3: Change `ensure_link`.**

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run --with pytest --with pyyaml pytest -q tests/test_init_menu.py tests/test_hook_settings.py`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add software-factory/lib/factory/init.py software-factory/tests/test_init_menu.py
git commit -m "Keep the link of a standalone install"
```

### Task 5: Messages and README

**Files:**
- Modify: `software-factory/lib/factory/migrate.py:44`
- Modify: `software-factory/lib/factory/version.py:27`, `:32`, `:41`
- Modify: `software-factory/README.md:27-52`
- Test: `software-factory/tests/test_migrate.py:79`, and every test that asserts on the old texts (`grep -rn "orchestrator\|update the factory" software-factory/tests`).

- [ ] **Step 1: In `tests/test_migrate.py:79`, assert `"Run the install script again to update it." in r.stderr`. Change the other tests found by the grep to the new texts of Global Constraints. Do not change `tests/test_docs.py:69`: it tests the docs checker, not a factory message.**

- [ ] **Step 2: Run those tests and make sure they fail.**

- [ ] **Step 3: Change the four messages to the exact texts of Global Constraints.**

- [ ] **Step 4: Rewrite the README section "Install and prerequisites"**

Keep the prerequisites list. Give the install command `curl -fsSL https://raw.githubusercontent.com/Bwaim/SoftwareFactory/main/install.sh | sh`, the install folder, the update command (run it again) and the PATH note. Replace "Start the orchestrator" with: run `factory init --library <path>` in the main repository, then `factory dashboard`. List the actions that exist only in the CLI: `factory init`, `factory migrate`, `factory catalog install`, `factory library commit`, `factory pipeline edit`, `factory step edit`.

Add a note for users who switch from the plugin: uninstall it with `/plugin uninstall software-factory@software-factory`. Give the reason: hooks run the standalone copy through `~/.local/bin/factory`, the plugin skill runs its own copy, and two code versions on the same `.factory` data are not supported. Older plugin copies also move the link back.

- [ ] **Step 5: Run the full test suite**

Run: `uv run --with pytest --with pyyaml pytest -q tests`
Expected: all pass. `tests/test_docs.py` checks that each `factory ...` command in the README exists.

- [ ] **Step 6: Commit**

```bash
git add software-factory/lib/factory/migrate.py software-factory/lib/factory/version.py software-factory/README.md software-factory/tests
git commit -m "Point users to the install script and the CLI"
```

### Task 6: First release and real install check

Run this task only after the branch is merged into `main`. Step 1 pushes a tag and publishes a public release. Ask the user for approval before Step 1. Until a release exists, `releases/latest/download` returns 404, and the script prints the "Bad digest file" error.

- [ ] **Step 1 (needs user approval): Push the tag**

```bash
git fetch origin
git cat-file -e origin/main:install.sh
git cat-file -e origin/main:.github/workflows/release.yml
git tag v0.1.0 origin/main
git push origin v0.1.0
```

If a `git cat-file` command fails, stop: `origin/main` does not have the merge yet.

- [ ] **Step 2: Wait for the workflow**

```bash
run_id=""
for i in $(seq 1 12); do
  run_id=$(gh run list --workflow release.yml --branch v0.1.0 --limit 1 --json databaseId --jq '.[0].databaseId // empty')
  [ -n "$run_id" ] && break
  sleep 5
done
[ -n "$run_id" ] && gh run watch "$run_id" --exit-status
```

Expected: a run id appears within 60 seconds, and the run succeeds. `gh release view v0.1.0 --json assets --jq '.assets[].name'` lists `software-factory.tar.gz` and `software-factory.tar.gz.sha256`.

- [ ] **Step 3: Install from the real GitHub into a temporary HOME**

```bash
tmp_home=$(mktemp -d)
curl -fsSL https://raw.githubusercontent.com/Bwaim/SoftwareFactory/main/install.sh | HOME="$tmp_home" sh
HOME="$tmp_home" "$tmp_home/.local/bin/factory" --version
rm -rf "$tmp_home"
```

Expected: the install prints `Installed factory 0.1.0 in <tmp_home>/.local/share/software-factory.`, and the last command prints `factory 0.1.0`.
