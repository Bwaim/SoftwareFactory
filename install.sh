#!/bin/sh

fail() {
  printf 'factory install: %s\n' "$1" >&2
  exit 1
}

fetch() {
  curl -fsSL --proto "$proto" --proto-redir "$proto" "$1" -o "$2" </dev/null
}

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" </dev/null
  else
    shasum -a 256 "$1" </dev/null
  fi
}

# The questions read the terminal, not stdin: with `curl ... | sh`, stdin is the script itself.
# FACTORY_INSTALL_TTY replaces /dev/tty (tests give a file of answers). Without a terminal, nothing is asked.
open_answers() {
  answers=${FACTORY_INSTALL_TTY:-/dev/tty}
  if (: <"$answers") 2>/dev/null; then
    exec 3<"$answers"
    return 0
  fi
  return 1
}

ask() {
  printf '%s' "$1"
  answer=""
  read -r answer <&3 || answer=""
  [ -n "$answer" ] || answer=$2
}

yes_to() {
  ask "$1 [Y/n] " y
  case "$answer" in [Nn]*) return 1 ;; *) return 0 ;; esac
}

has_herdr() {
  command -v herdr >/dev/null 2>&1
}

on_macos() {
  [ "$(uname -s </dev/null)" = Darwin ]
}

has_warp() {
  on_macos || return 1
  if [ -n "${FACTORY_INSTALL_WARP_APP:-}" ]; then
    [ -d "$FACTORY_INSTALL_WARP_APP" ]
  else
    [ -d /Applications/Warp.app ] || [ -d "$HOME/Applications/Warp.app" ]
  fi
}

has_tmux() {
  command -v tmux >/dev/null 2>&1
}

found() {
  if "$1"; then printf ' (found)'; fi
}

install_herdr() {
  has_herdr && return 0
  if yes_to "Install Herdr now with its install script (curl -fsSL https://releases.herdr.dev/app/install.sh | sh)?"; then
    curl -fsSL --proto "=https" --proto-redir "=https" https://releases.herdr.dev/app/install.sh </dev/null | sh \
      || printf 'factory install: The Herdr install failed. Install it from https://herdr.dev\n' >&2
  else
    printf 'Install Herdr later from https://herdr.dev\n'
  fi
}

brew_install() {
  if ! command -v brew >/dev/null 2>&1; then
    printf 'Install %s later: %s\n' "$1" "$3"
    return 0
  fi
  if yes_to "Install $1 now with Homebrew (brew install $2)?"; then
    # shellcheck disable=SC2086
    brew install $2 </dev/null || printf 'factory install: The %s install failed. Install it later: %s\n' "$1" "$3" >&2
  else
    printf 'Install %s later: %s\n' "$1" "$3"
  fi
}

install_warp() {
  has_warp || brew_install Warp "--cask warp" https://www.warp.dev
  has_tmux || brew_install tmux tmux "brew install tmux"
}

ask_terminal() {
  if has_herdr; then default=1; elif has_warp; then default=2; else default=3; fi
  printf '\nCAPTN runs each task in a multi-terminal tool.\n'
  if on_macos; then
    printf 'Which one do you already have?\n  1) Herdr%s\n  2) Warp%s, with tmux\n  3) None of them\n' "$(found has_herdr)" "$(found has_warp)"
    ask "Choice [$default]: " "$default"
  else
    printf 'Herdr is the one that works on Linux.\n'
    if has_herdr; then answer=1; else answer=3; fi
  fi
  case "$answer" in
    1) terminal=herdr ;;
    2) terminal=warp ;;
    *)
      terminal=herdr
      if on_macos; then
        printf 'Which one would you like to install to use with CAPTN?\n  1) Herdr: https://herdr.dev\n  2) Warp with tmux: https://www.warp.dev\n'
        ask "Choice [1]: " 1
        if [ "$answer" = 2 ]; then terminal=warp; fi
      fi
      ;;
  esac
  if [ "$terminal" = warp ]; then install_warp; else install_herdr; fi
}

save_terminal() {
  config_dir=${FACTORY_HOME:-$HOME/.config/software-factory}
  mkdir -p "$config_dir"
  printf '%s\n' "$terminal" > "$config_dir/terminal"
  printf 'CAPTN will use %s in new repositories. A repository keeps its own choice in .factory/factory.yaml (terminal:).\n' "$terminal"
}

choose_terminal() {
  terminal=${FACTORY_INSTALL_TERMINAL:-}
  case "$terminal" in
    herdr | warp) ;;
    "")
      if open_answers; then
        ask_terminal
      elif has_herdr; then
        return 0
      elif has_warp; then
        terminal=warp
      else
        printf 'factory install: No terminal tool found. Tasks need Herdr (https://herdr.dev) or, on macOS, Warp with tmux (https://www.warp.dev). Run the install script in a terminal to choose one.\n' >&2
        return 0
      fi
      ;;
    *) fail "FACTORY_INSTALL_TERMINAL must be herdr or warp." ;;
  esac
  save_terminal
  if [ "$terminal" = warp ] && { ! has_warp || ! has_tmux; }; then
    printf 'factory install: Warp and tmux are needed for tasks. Install them from https://www.warp.dev and with brew install tmux.\n' >&2
  elif [ "$terminal" = herdr ] && ! has_herdr; then
    printf 'factory install: herdr is not on PATH. Tasks need it to start. Install it from https://herdr.dev\n' >&2
  fi
}

main() {
  set -eu
  umask 022

  base=${FACTORY_INSTALL_DOWNLOAD_BASE:-https://github.com/Bwaim/SoftwareFactory/releases/latest/download}
  proto=${FACTORY_INSTALL_PROTO:-=https}
  dir=${FACTORY_INSTALL_DIR:-$HOME/.local/share/software-factory}
  link_dir=${FACTORY_LINK_DIR:-$HOME/.local/bin}
  link="$link_dir/factory"

  for tool in curl tar uv claude; do
    command -v "$tool" >/dev/null 2>&1 || fail "$tool is required."
  done
  command -v git >/dev/null 2>&1 \
    || printf 'factory install: git is not installed. Only pipelines with `worktree: false` can run.\n' >&2

  if [ ! -e "$dir" ]; then
    for b in "$dir".backup.*; do
      [ -d "$b" ] || continue
      case "$b" in "$dir".backup.*[!0-9]*) continue ;; esac
      [ -f "$b/.installed-by-script" ] || continue
      mv "$b" "$dir"
      printf 'Restored the previous install from %s.\n' "$b"
      break
    done
  fi
  for b in "$dir".backup.* "$dir".stage.*; do
    [ -d "$b" ] || continue
    case "$b" in "$dir".backup.*[!0-9]* | "$dir".stage.*[!0-9]*) continue ;; esac
    rm -rf "$b"
  done

  if [ -e "$dir" ] && [ ! -f "$dir/.installed-by-script" ]; then
    fail "$dir exists and was not made by this script. Move it away, then run again."
  fi
  if [ -e "$link" ] && [ ! -L "$link" ]; then
    fail "$link exists and is not a link. Move it away, then run again."
  fi

  work=$(mktemp -d)
  stage="$dir.stage.$$"
  trap 'rm -rf "$work" "$stage"' EXIT

  fetch "$base/software-factory.tar.gz.sha256" "$work/digest" 2>/dev/null \
    || fail "The latest release has no valid software-factory.tar.gz.sha256."
  expected=$(sed -n '1s/[[:space:]].*//p' "$work/digest")
  printf '%s\n' "$expected" | grep -Eq '^[0-9a-f]{64}$' \
    || fail "The latest release has no valid software-factory.tar.gz.sha256."

  fetch "$base/software-factory.tar.gz" "$work/archive.tar.gz"
  actual=$(sha256 "$work/archive.tar.gz" | sed 's/[[:space:]].*//')
  [ "$actual" = "$expected" ] \
    || fail "The downloaded archive SHA-256 differs from the release digest. The existing install is unchanged."

  mkdir -p "$(dirname "$dir")" "$stage"
  tar -xzf "$work/archive.tar.gz" -C "$stage" --strip-components=1 </dev/null
  version=$(cat "$stage/VERSION")
  : > "$stage/.installed-by-script"

  backup=""
  if [ -e "$dir" ]; then
    backup="$dir.backup.$$"
    mv "$dir" "$backup"
  fi
  if ! mv "$stage" "$dir"; then
    [ -z "$backup" ] || mv "$backup" "$dir"
    exit 1
  fi
  [ -z "$backup" ] || rm -rf "$backup"

  mkdir -p "$link_dir"
  if [ -L "$link" ]; then
    old_target=$(readlink "$link")
    if [ "$old_target" != "$dir/bin/factory" ]; then
      rm "$link"
      ln -s "$dir/bin/factory" "$link"
      printf 'Replaced the link %s, it pointed to %s.\n' "$link" "$old_target"
    fi
  else
    ln -s "$dir/bin/factory" "$link"
  fi

  printf 'Installed factory %s in %s.\n' "$version" "$dir"
  choose_terminal
  case ":$PATH:" in
    *":$link_dir:"*) ;;
    *) printf 'Add %s to your PATH.\n' "$link_dir" ;;
  esac
}

main "$@"
