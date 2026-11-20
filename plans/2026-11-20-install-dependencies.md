# Dependency Checklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `install.sh` shows a checklist of the dependencies, installs the ones that the user selects, and then installs the factory.

**Architecture:** The terminal question stays first. Then the script builds the list for the OS, the CPU and the terminal choice, shows it, and reads numbers until an empty line. It installs the selected items in list order, puts Homebrew and `~/.local/bin` on its own PATH, runs the existing required-tool checks, and installs the factory. Without a terminal, the current flow does not change.

**Tech Stack:** POSIX `sh`, pytest.

**Spec:** `specs/2026-11-20-install-dependencies-design.md`

## Global Constraints

- Branch `install`. Change only `install.sh`, `software-factory/tests/test_install_script.py` and `software-factory/README.md`.
- Commit messages have no `Co-Authored-By` line.
- Each task runs only the tests that it adds or changes. The full test suite runs once, in Task 4.
- No comments in code.
- The script stays POSIX `sh`. All answers come from fd 3 (`open_answers`, `ask`). Every command that does not need the terminal gets `</dev/null`.
- Test hooks, with their defaults:
  - `FACTORY_INSTALL_OS`: default `$(uname -s)`. `Darwin` is macOS. Any other value is Linux.
  - `FACTORY_INSTALL_ARM64`: default `$(sysctl -n hw.optional.arm64 2>/dev/null)`. On macOS, `1` is Apple Silicon. Any other value is Intel. Never use `uname -m`.
  - `FACTORY_INSTALL_BREW_PATHS`: default `/opt/homebrew/bin/brew /usr/local/bin/brew /home/linuxbrew/.linuxbrew/bin/brew`.
  - `FACTORY_INSTALL_WARP_APP`: as today.
- The script never edits shell files. The uv script runs with `UV_NO_MODIFY_PATH=1`.

### Items

Each item has a key, a name, a use and an install command.

| Key | Name | Use | Install command |
|---|---|---|---|
| `clt` | Xcode Command Line Tools | git, and swiftc for Warp notifications | `xcode-select --install` |
| `brew` | Homebrew | installs the other tools | `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` |
| `git` | git | task worktrees | none (cannot be selected) |
| `uv` | uv | runs the factory (Python) | `brew install uv`. Intel Mac: `curl -LsSf https://astral.sh/uv/install.sh \| env UV_NO_MODIFY_PATH=1 sh` |
| `claude` | Claude Code | runs each task | `brew install --cask claude-code`. Linux and Intel Mac: `curl -fsSL https://claude.ai/install.sh \| bash` |
| `herdr` | Herdr | shows each task in a tab | `brew install herdr`. Intel Mac: `curl -fsSL https://herdr.dev/install.sh \| sh` |
| `warp` | Warp | shows each task in a tab | `brew install --cask warp` |
| `tmux` | tmux | keeps each task session running | `brew install tmux` |
| `gh` | gh | GitHub steps of the catalog | `brew install gh` |
| `glab` | glab | GitLab steps of the catalog | `brew install glab` |

A brew item is an item whose command starts with `brew `.

### Lists

- macOS, Apple Silicon: Mandatory `clt brew uv claude <terminal items>`. Optional `gh glab`.
- macOS, Intel, Warp: Mandatory `clt brew uv claude warp tmux`. Optional `gh glab`.
- macOS, Intel, Herdr: Mandatory `clt uv claude herdr`. Optional `brew gh glab`.
- Linux: Mandatory `git brew uv claude herdr`. Optional `gh glab`.
- Terminal items: `herdr`, or `warp tmux`.
- Numbers go from 1 in this order, across both groups.

### Found

- `clt`: `xcode-select -p` succeeds.
- `brew`: `command -v brew` succeeds, or a path in `FACTORY_INSTALL_BREW_PATHS` is executable.
- `git`: `command -v git`. `uv`, `claude`, `herdr`, `tmux`, `gh`, `glab`: `command -v <cmd>`. `warp`: `has_warp`.

### Exact text

- Before the list: `\nCAPTN needs these tools. [x] means that the script installs it.\n`
- Group headers: `Mandatory` and `Optional`, each on its own line.
- Item line: `  <n>) [x] <name>: <use>` or `  <n>) [ ] <name>: <use>`.
  - Found: `  <n>) [ ] <name> (found): <use>`.
  - Linux `git` missing: `  <n>) [ ] git (install it with your package manager): task worktrees`.
  - Linux `brew` when git is missing: `  <n>) [ ] Homebrew (needs git): installs the other tools`.
  - Intel Mac brew items: `<use>` ends with ` (brew builds it from source)`.
- Prompt: `Type numbers to change, Enter to install: `
- A number that is not a list number, or a found or blocked item: `Item <x> cannot be changed.`
- CLT wait, after `xcode-select --install`: `Finish the Command Line Tools install in its window, then press Enter. `
- Brew item without brew: `Install <name> later: <command>`.
- Failed install: `factory install: The <name> install failed. Install it later: <command>` on stderr.
- End, when brew was not on the PATH at start: `Add this line to <file>: eval "$(<brew path> shellenv)"`. `<file>` is `~/.zprofile` on macOS and `~/.bashrc` on Linux.

## Review Focus

1. The same number twice in one answer (`5 5`): the item goes back to its first state. Test in Task 1.
2. The answer file ends before the empty line: `ask` returns the default `""`, so the list confirms and the script does not hang. Test in Task 1.
3. Not a number (`abc`, `0`, `99`): `Item <x> cannot be changed.`, and the list shows again. Test in Task 1.
4. The Homebrew install fails: each selected brew item prints `Install <name> later`, and `set -eu` does not stop the script. Test in Task 2.
5. Second run with all items found: the list shows `(found)` on each line, and Enter installs nothing. Test in Task 2.

---

### Task 1: Build, show and change the list

**Files:**
- Modify: `install.sh` (replace `install_herdr`, `brew_install` and `install_warp`; `ask_terminal` and `choose_terminal` only ask and do not install)
- Test: `software-factory/tests/test_install_script.py`

**Interfaces:**
- Produces, in `install.sh`:
  - `platform_init`: sets `os_name` (`Darwin` or `Linux`) and `intel_mac` (`1` or `0`).
  - `brew_path`: prints the brew path, or nothing.
  - `item_name <key>`, `item_use <key>`, `install_command <key>`: print the values of the Items table, for this platform.
  - `item_found <key>`: returns 0 when found.
  - `item_blocked <key>`: prints the reason in the parentheses of the Exact text, or nothing.
  - `build_list`: sets `mandatory_items` and `optional_items`, space-separated keys. Missing, not blocked mandatory items are selected. Selection state: one variable per key, `sel_<key>` (`1` or `0`).
  - `show_list`, and `choose_items`, which loops on `show_list` and the prompt until an empty answer.
  - `choose_terminal` sets `terminal` (or leaves it empty without a terminal), as today, but installs nothing.

- [ ] **Step 1: Update the fixture and write the failing tests**

In the `env` fixture, add `FACTORY_INSTALL_OS: "Darwin"`, `FACTORY_INSTALL_ARM64: "1"`, `FACTORY_INSTALL_BREW_PATHS: "/nonexistent/brew"`, `FACTORY_INSTALL_WARP_APP: "/nonexistent/Warp.app"`. Add stubs in `fake bin`: `xcode-select` (`exit 0`), and `curl`. The `curl` stub finds the URL argument. For `http://127.0.0.1` it runs `exec "<tools>/curl" "$@"`. For other URLs it appends the URL to `<work>/curl.log` and prints `${CURL_STUB_SCRIPT:-echo installer}`. Remove `macos_only`, because `FACTORY_INSTALL_OS` replaces it.

Remove `test_declined_herdr_install_is_not_run` and `test_accepted_brew_installs_run_brew`. Update `test_none_installed_asks_which_to_install`: answers `"3", "2", ""`, and keep only the asserts on the question and on `saved_terminal`. Add `""` as the last answer of the other `run_with_answers` tests.

```python
def test_list_apple_silicon_herdr(release, env, work):
    r = run_with_answers(env, work, "1", "")
    assert "CAPTN needs these tools. [x] means that the script installs it." in r.stdout
    assert ("Mandatory\n"
            "  1) [ ] Xcode Command Line Tools (found): git, and swiftc for Warp notifications\n"
            "  2) [x] Homebrew: installs the other tools\n"
            "  3) [ ] uv (found): runs the factory (Python)\n"
            "  4) [ ] Claude Code (found): runs each task\n"
            "  5) [x] Herdr: shows each task in a tab\n"
            "Optional\n"
            "  6) [ ] gh: GitHub steps of the catalog\n"
            "  7) [ ] glab: GitLab steps of the catalog\n") in r.stdout

def test_list_warp_has_warp_and_tmux(release, env, work):
    r = run_with_answers(env, work, "2", "")
    assert "  5) [x] Warp: shows each task in a tab\n  6) [x] tmux: keeps each task session running\n" in r.stdout

def test_list_intel_herdr_moves_homebrew_to_optional(release, env, work):
    r = run_with_answers({**env, "FACTORY_INSTALL_ARM64": "0"}, work, "1", "")
    assert "  4) [x] Herdr: shows each task in a tab\nOptional\n  5) [ ] Homebrew: installs the other tools\n" in r.stdout
    assert "  6) [ ] gh: GitHub steps of the catalog (brew builds it from source)\n" in r.stdout

def test_list_linux_without_git(release, env, work):
    (work / "tools/git").unlink()
    usr = work / "usr bin"
    usr.mkdir()
    for tool in Path("/usr/bin").iterdir():
        if tool.name != "git":
            (usr / tool.name).symlink_to(tool)
    r = run_with_answers({**env, "FACTORY_INSTALL_OS": "Linux", "PATH": env["PATH"].replace("/usr/bin", str(usr))}, work, "")
    assert "Which one do you already have?" not in r.stdout
    assert "  1) [ ] git (install it with your package manager): task worktrees\n" in r.stdout
    assert "  2) [ ] Homebrew (needs git): installs the other tools\n" in r.stdout
    assert "Warp" not in r.stdout and "Xcode" not in r.stdout

def test_toggle_numbers(release, env, work):
    r = run_with_answers(env, work, "1", "6 2", "")
    assert "  2) [ ] Homebrew: installs the other tools\n" in r.stdout
    assert "  6) [x] gh: GitHub steps of the catalog\n" in r.stdout

def test_same_number_twice_keeps_the_state(release, env, work):
    r = run_with_answers(env, work, "1", "6 6", "")
    assert r.stdout.count("  6) [ ] gh: GitHub steps of the catalog\n") == 2

@pytest.mark.parametrize("bad", ["abc", "0", "99", "1"])
def test_bad_or_found_number_refused(release, env, work, bad):
    r = run_with_answers(env, work, "1", bad, "")
    assert f"Item {bad} cannot be changed." in r.stdout

def test_end_of_answers_confirms_the_list(release, env, work):
    r = run_with_answers(env, work, "1")
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("Type numbers to change, Enter to install: ") == 1

def test_terminal_from_the_environment_still_shows_the_list(release, env, work):
    r = run_with_answers({**env, "FACTORY_INSTALL_TERMINAL": "herdr"}, work, "")
    assert "Which one do you already have?" not in r.stdout and "  5) [x] Herdr" in r.stdout
```

- [ ] **Step 2: Run the added and changed tests and make sure that the new tests fail**

Run: `cd software-factory && uv run pytest tests/test_install_script.py -q -k "list_ or toggle or number or end_of_answers or still_shows or none_installed or asks_and_keeps"`
Expected: the new `test_list_*`, `test_toggle_*` and `test_*_number*` tests FAIL.

- [ ] **Step 3: Implement the Task 1 interfaces in `install.sh`**

`main` calls `open_answers` once and keeps the result. `choose_terminal` and `choose_items` use that result, so the list also shows when `FACTORY_INSTALL_TERMINAL` is set. `choose_items` runs only when `open_answers` succeeded. `on_macos` reads `os_name` from `platform_init`, not `uname -s`, so `has_warp` and `ask_terminal` follow `FACTORY_INSTALL_OS`. In this task, the script does not install the selected items. `main` calls `platform_init`, `choose_terminal`, `build_list` and `choose_items` before the existing required-tool checks. `choose_terminal` only sets `terminal`. The save of the choice and the terminal warnings stay after the factory install, as today.

- [ ] **Step 4: Run the added and changed tests and make sure that they pass**

Run: `cd software-factory && uv run pytest tests/test_install_script.py -q -k "list_ or toggle or number or end_of_answers or still_shows or none_installed or asks_and_keeps"`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add install.sh software-factory/tests/test_install_script.py
git commit -m "install.sh: show the dependency list and let the user change it"
```

### Task 2: Install the selected items, then the factory

**Files:**
- Modify: `install.sh` (`main` and new functions)
- Test: `software-factory/tests/test_install_script.py`

**Interfaces:**
- Consumes: all Task 1 interfaces.
- Produces: `install_items`, which installs the selected items in list order. It runs each command with `sh -c "$(install_command <key>)"`. `use_brew` runs `eval "$("$(brew_path)" shellenv)"` when `brew_path` prints a path.

New order in `main`: `open_answers` (keep the result), `platform_init`, `choose_terminal`, `build_list`, `choose_items`, `use_brew`, `install_items`, then `export PATH="$HOME/.local/bin:$PATH"` and `use_brew`. Then come the existing required-tool checks, the download, the swap and the link. Save the `terminal` choice and print the warnings, as today. Keep the original PATH in a variable before any change. The `Add <link_dir> to your PATH.` message and the brew line use the original PATH.

`install_items` rules:
- `clt`: run the command, then `ask` the CLT wait text.
- `brew`: run the command with stdin from fd 3, then `use_brew`.
- All other commands: `</dev/null`.
- A brew item when `command -v brew` fails: print the `Install <name> later` line and run nothing.
- A command that fails: print the failed-install line and continue.

- [ ] **Step 1: Write the failing tests**

Add a helper that writes a `brew` stub at `<work>/brew/bin/brew`. The stub logs `"$@"` to `<work>/brew.log`, and on `shellenv` it prints `export PATH="<work>/brew/bin:$PATH"`. Tests that need brew set `FACTORY_INSTALL_BREW_PATHS` to that path. `brew_log(work)` returns the logged lines without the `shellenv` lines, or `[]` when there is no log.

```python
def test_selected_brew_items_install_in_order(release, env, work):
    brew = brew_stub(work)
    r = run_with_answers({**env, "FACTORY_INSTALL_BREW_PATHS": str(brew)}, work, "2", "7", "")
    assert r.returncode == 0, r.stderr
    assert brew_log(work) == ["install --cask warp", "install tmux", "install gh"]

def test_homebrew_install_runs_the_official_script(release, env, work):
    r = run_with_answers(env, work, "1", "")
    assert "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh" in (work / "curl.log").read_text()

def test_brew_items_without_homebrew_print_install_later(release, env, work):
    r = run_with_answers(env, work, "1", "2", "")
    assert "Install Herdr later: brew install herdr" in r.stdout
    assert saved_terminal(env) == "herdr"

def test_failed_homebrew_install_continues(release, env, work):
    r = run_with_answers({**env, "CURL_STUB_SCRIPT": "exit 1"}, work, "1", "")
    assert r.returncode == 0, r.stderr
    assert "factory install: The Homebrew install failed." in r.stderr
    assert "Install Herdr later: brew install herdr" in r.stdout

def test_intel_mac_uses_the_official_scripts(release, env, work):
    for name in ("uv", "claude"):
        hide_command(work, env, name)
    run_with_answers({**env, "FACTORY_INSTALL_ARM64": "0"}, work, "1", "")
    urls = (work / "curl.log").read_text()
    assert "https://astral.sh/uv/install.sh" in urls
    assert "https://claude.ai/install.sh" in urls and "https://herdr.dev/install.sh" in urls

def test_uv_script_does_not_edit_shell_files(release, env, work):
    hide_command(work, env, "uv")
    write_stub(work / "fake bin/env", f'echo "$@" >> "{work}/env.log"')
    run_with_answers({**env, "FACTORY_INSTALL_ARM64": "0"}, work, "1", "")
    assert "UV_NO_MODIFY_PATH=1 sh" in (work / "env.log").read_text()

def test_command_line_tools_install_waits_for_enter(release, env, work):
    write_stub(work / "fake bin/xcode-select", f'[ "$1" = -p ] && exit 2; echo "$@" >> "{work}/xcode.log"')
    r = run_with_answers(env, work, "1", "", "")
    assert (work / "xcode.log").read_text().strip() == "--install"
    assert "Finish the Command Line Tools install in its window, then press Enter. " in r.stdout

def test_unselected_uv_stops_before_the_factory(release, env, work):
    hide_command(work, env, "uv")
    r = run_with_answers(env, work, "1", "3", "")
    assert r.returncode == 1 and "factory install: uv is required." in r.stderr

def test_everything_found_installs_nothing(release, env, work):
    brew = brew_stub(work)
    write_stub(work / "fake bin/herdr", "exit 0")
    for name in ("gh", "glab"):
        write_stub(work / f"fake bin/{name}", "exit 0")
    r = run_with_answers({**env, "FACTORY_INSTALL_BREW_PATHS": str(brew)}, work, "1", "")
    assert ") [x]" not in r.stdout and brew_log(work) == []
    assert not (work / "curl.log").exists()

def test_brew_path_line_when_brew_is_not_on_path(release, env, work):
    brew = brew_stub(work)
    r = run_with_answers({**env, "FACTORY_INSTALL_BREW_PATHS": str(brew)}, work, "1", "")
    assert f'Add this line to ~/.zprofile: eval "$({brew} shellenv)"' in r.stdout
```

`hide_command(work, env, name)` removes `name` from `fake bin` and `tools`. When `name` is `uv`, the test still needs uv for the factory, so these tests check only the output before the factory install.

- [ ] **Step 2: Run the added tests and make sure that they fail**

Run: `cd software-factory && uv run pytest tests/test_install_script.py -q -k "selected_brew or homebrew_install or without_homebrew or intel_mac_uses or uv_script or command_line_tools or unselected_uv or everything_found or brew_path_line"`
Expected: the new tests FAIL.

- [ ] **Step 3: Implement `install_items`, `use_brew` and the new `main` order in `install.sh`**

- [ ] **Step 4: Run the added tests and make sure that they pass**

Run: `cd software-factory && uv run pytest tests/test_install_script.py -q -k "selected_brew or homebrew_install or without_homebrew or intel_mac_uses or uv_script or command_line_tools or unselected_uv or everything_found or brew_path_line"`
Expected: all PASS. Also run `sh -n install.sh` and, if `shellcheck` is installed, `shellcheck install.sh`, with no new warning.

- [ ] **Step 5: Commit**

```bash
git add install.sh software-factory/tests/test_install_script.py
git commit -m "install.sh: install the selected dependencies before the factory"
```

### Task 3: README

**Files:**
- Modify: `software-factory/README.md` (section "Install and prerequisites", lines 28-52)

- [ ] **Step 1: Rewrite the section**

- Replace the "You need:" list with the two groups of the spec, with the use of each item.
- Replace lines 46-48: the script asks for the terminal tool, then shows the list. Missing mandatory items are selected. Type numbers to change, and Enter to install. Then the factory installs.
- Add: on Intel Macs, uv, Claude Code and Herdr install with their official scripts. The script never edits shell files, but `claude install` can add `~/.local/bin` to one.
- Add: at the end, the script prints the PATH lines to add for `~/.local/bin` and Homebrew.
- Keep line 50 (no terminal, `FACTORY_INSTALL_TERMINAL`). Add: the list is still shown with `FACTORY_INSTALL_TERMINAL`.

- [ ] **Step 2: Make sure that each command in the section is the same as in `install.sh`**

Run: `grep -n "install.sh\|brew install\|UV_NO_MODIFY_PATH" software-factory/README.md install.sh`
Expected: the same commands in both files.

- [ ] **Step 3: Commit**

```bash
git add software-factory/README.md
git commit -m "README: describe the dependency list of the install script"
```

### Task 4: Full test suite

- [ ] **Step 1: Run the full test suite once**

Run: `cd software-factory && uv run pytest -q`
Expected: all PASS. If a test outside the changed ones fails, fix the cause in the task that it belongs to, then run the full suite again.
