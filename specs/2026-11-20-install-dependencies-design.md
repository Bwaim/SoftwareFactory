# Dependency checklist in the install script

Source: user request in the session of 2026-11-20.

## Intent

On a fresh Mac, `install.sh` stops with `uv is required.` The user must find and install each dependency by hand. The install script must list all dependencies, say what each one is for, install the ones that the user selects, and then install the factory.

## Terms

- Dependency list: the numbered checklist that the script shows before the factory install.
- Found: the dependency is already on the machine. A found item shows `(found)` and cannot be selected.
- Brew item: a dependency that the script installs with Homebrew.

## Goals

1. The script asks for the terminal tool first (Herdr or Warp), as today. On Linux, the terminal tool is Herdr, and the script does not ask.
2. The script shows the dependency list in two groups, "Mandatory" and "Optional". Each line has a number, a box (`[x]` or `[ ]`), a name, `(found)` when found, and the use.
3. Missing mandatory items are selected by default. Optional items are not selected by default.
4. The user types one or more numbers, separated by spaces, to change the selection. The script shows the list again. An empty line confirms the list.
5. The script installs the selected items, in list order. Then it installs the factory and saves the terminal choice.

## The list

macOS with Herdr:

| # | Group | Item | Use | Install command |
|---|---|---|---|---|
| 1 | Mandatory | Xcode Command Line Tools | git, and swiftc for Warp notifications | `xcode-select --install` |
| 2 | Mandatory | Homebrew | installs the other tools | official script from brew.sh |
| 3 | Mandatory | uv | runs the factory (Python) | `brew install uv` |
| 4 | Mandatory | Claude Code | runs each task | `brew install --cask claude-code` |
| 5 | Mandatory | Herdr | shows each task in a tab | `brew install herdr` |
| 6 | Optional | gh | GitHub steps of the catalog | `brew install gh` |
| 7 | Optional | glab | GitLab steps of the catalog | `brew install glab` |

macOS with Warp: line 5 becomes two lines. Warp (`brew install --cask warp`) shows each task in a tab. tmux (`brew install tmux`) keeps each task session running.

Intel Mac: the formulas `uv`, `herdr`, `gh`, `glab` and `tmux` have no Intel macOS bottle. Their bottles are only for arm64 macOS and Linux (`bottle.stable.files` in `https://formulae.brew.sh/api/formula/<name>.json`). So on an Intel Mac, brew builds them from source with Rust or other tools. That build is slow and can fail. On an Intel Mac, the mandatory items use their official scripts, without Homebrew:

- uv: `curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh`. Without `UV_NO_MODIFY_PATH=1`, the uv script adds `~/.local/bin` to `.zshrc`, `.zshenv`, `.profile` and `.bashrc`.
- Claude Code: `curl -fsSL https://claude.ai/install.sh | bash`
- Herdr: `curl -fsSL https://herdr.dev/install.sh | sh`

All three install to `~/.local/bin`. gh, glab and tmux stay brew items. On an Intel Mac, their lines say "brew builds it from source". Homebrew is mandatory on an Intel Mac only with Warp, because tmux needs it. With Herdr, Homebrew moves to the "Optional" group, as its first line. Items install in list order, so Homebrew must install before gh and glab.

Intel detection: `sysctl -n hw.optional.arm64` prints `1` on Apple Silicon. Any other result, or an error, means Intel. The script does not use `uname -m`, because under Rosetta an Apple Silicon Mac reports `x86_64`.

Linux: no Command Line Tools, Warp or tmux. A "git" line replaces the Command Line Tools line, with the use "task worktrees". The git line cannot be selected. When git is missing, the line says to install git with the system package manager (for example `sudo apt install git`). The Homebrew installer stops without git ("You must install Git before installing Homebrew."), so `brew install git` cannot work on a machine without git. For the same reason, when git is missing on Linux, the Homebrew line cannot be selected and shows "needs git". Then each selected brew item prints `Install <item> later: <command>`. Claude Code uses `curl -fsSL https://claude.ai/install.sh | bash`, because Homebrew casks do not work on Linux.

## Behavior

- Command Line Tools: `xcode-select --install` opens a macOS window and returns at once. The script then asks the user to finish the install in that window and press Enter. Found means `xcode-select -p` succeeds. The script does not use `command -v git`, because macOS has a `/usr/bin/git` stub without the tools.
- Homebrew found: `command -v brew` succeeds, or `brew` is at `/opt/homebrew/bin/brew`, `/usr/local/bin/brew` or `/home/linuxbrew/.linuxbrew/bin/brew`. This prevents a second Homebrew install when brew is not on PATH.
- Homebrew install: the script runs the official installer and gives it the terminal for the password.
- PATH of the script: a new install is not on PATH while the script runs, so the checks after the installs (`command -v uv`, `command -v claude`, `has_herdr`) fail. When Homebrew is found or installed, the script runs `eval "$(<brew path> shellenv)"`. Before the checks, the script also adds `~/.local/bin` to its own PATH. The Claude Code script on Linux and on Intel Macs, and the uv and Herdr scripts on Intel Macs, install there.
- Homebrew on PATH: the script does not edit shell files. At the end, it prints the line to add to `~/.zprofile` (macOS) or `~/.bashrc` (Linux), next to the existing `~/.local/bin` PATH message.
- Brew items without Homebrew: if Homebrew is not found and not selected, the script installs no brew item. For each selected brew item, it prints `Install <item> later: <command>`.
- A failed install prints a warning, and the script continues.
- After the installs, the existing checks run: `curl`, `tar`, `uv` and `claude` are required. If one is missing, the script stops before the factory install, as today.
- Without a terminal (CI, no `/dev/tty`), the script shows no list and installs nothing. It keeps the current behavior.
- `FACTORY_INSTALL_TERMINAL` skips the terminal question. The list is still shown.
- Herdr changes from `releases.herdr.dev/app/install.sh` to `brew install herdr`, and to `herdr.dev/install.sh` on Intel Macs. This fixes a bug. The script that `install.sh` runs today installs the Herdr desktop app (`herdr-app`) and `herdr-core` (`hc`), not the `herdr` command. The factory runs `herdr` (`software-factory/lib/factory/adapters/herdr.py:19`), so after today's Herdr install, `has_herdr` still fails.

## Non-goals

- Arrow-key checkboxes.
- Edits of the user's shell files. One exception: the Claude Code script (Linux and Intel Macs) runs `claude install`, which sets up the "launcher and shell integration". It can add `~/.local/bin` to a shell file. The script has no switch to turn this off. The install script accepts this edit.
- Install of dependencies with other package managers (apt, dnf).
- Updates of dependencies that are found.

## Anti-goals

- The script installs an item that the user did not select.
- The script installs the factory when `uv` or `claude` is missing.
- The script hangs without a terminal.

## Approaches

### Checklist

- O1, chosen: a numbered list that the user changes by number, then confirms with Enter. It is one screen, plain `sh`, and easy to test with an answer file.
- O2: one Y/n question per item. It uses the existing `yes_to` function, but it is long and it is not a checklist.
- O3: arrow-key checkboxes. They need raw terminal mode in `sh`, they are hard to test, and they can break with `curl ... | sh`.

### Claude Code on Intel Mac

- O4, chosen: Claude Code installs with its official script. Homebrew stays optional with Herdr. The shell file edit of `claude install` exists on Linux in all cases.
- O5: Claude Code installs with `brew install --cask claude-code`. Homebrew becomes mandatory on Intel Macs again, and the Linux exception stays.

## Left to the builder

- Test hooks for detection of Command Line Tools, Homebrew paths and the OS, in the style of `FACTORY_INSTALL_WARP_APP`.
- Messages for an unknown number in the answer.
- Changes to `software-factory/tests/test_install_script.py` and to the "Install and prerequisites" section of `software-factory/README.md`.
