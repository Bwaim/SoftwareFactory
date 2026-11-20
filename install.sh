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

has_herdr() {
  command -v herdr >/dev/null 2>&1
}

platform_init() {
  os_name=${FACTORY_INSTALL_OS:-$(uname -s </dev/null)}
  [ "$os_name" = Darwin ] || os_name=Linux
  intel_mac=0
  if [ "$os_name" = Darwin ]; then
    arm=${FACTORY_INSTALL_ARM64:-$(sysctl -n hw.optional.arm64 2>/dev/null </dev/null || true)}
    [ "$arm" = 1 ] || intel_mac=1
  fi
}

on_macos() {
  [ "$os_name" = Darwin ]
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

brew_path() {
  if command -v brew >/dev/null 2>&1; then
    command -v brew
    return 0
  fi
  for b in ${FACTORY_INSTALL_BREW_PATHS:-/opt/homebrew/bin/brew /usr/local/bin/brew /home/linuxbrew/.linuxbrew/bin/brew}; do
    if [ -x "$b" ]; then
      printf '%s\n' "$b"
      return 0
    fi
  done
}

item_name() {
  case "$1" in
    clt) echo "Xcode Command Line Tools" ;;
    brew) echo "Homebrew" ;;
    claude) echo "Claude Code" ;;
    herdr) echo "Herdr" ;;
    warp) echo "Warp" ;;
    *) echo "$1" ;;
  esac
}

install_command() {
  case "$1" in
    clt) echo "xcode-select --install" ;;
    brew) echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"' ;;
    uv)
      if [ "$intel_mac" = 1 ]; then echo "curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh"
      else echo "brew install uv"; fi
      ;;
    claude)
      if [ "$os_name" = Linux ] || [ "$intel_mac" = 1 ]; then echo "curl -fsSL https://claude.ai/install.sh | bash"
      else echo "brew install --cask claude-code"; fi
      ;;
    herdr)
      if [ "$intel_mac" = 1 ]; then echo "curl -fsSL https://herdr.dev/install.sh | sh"
      else echo "brew install herdr"; fi
      ;;
    warp) echo "brew install --cask warp" ;;
    tmux | gh | glab) echo "brew install $1" ;;
  esac
}

item_use() {
  case "$1" in
    clt) use="git, and swiftc for Warp notifications" ;;
    brew) use="installs the other tools" ;;
    git) use="task worktrees" ;;
    uv) use="runs the factory (Python)" ;;
    claude) use="runs each task" ;;
    herdr | warp) use="shows each task in a tab" ;;
    tmux) use="keeps each task session running" ;;
    gh) use="GitHub steps of the catalog" ;;
    glab) use="GitLab steps of the catalog" ;;
  esac
  if [ "$intel_mac" = 1 ]; then
    case "$(install_command "$1")" in
      "brew install --cask"*) ;;
      "brew install"*) use="$use (brew builds it from source)" ;;
    esac
  fi
  printf '%s\n' "$use"
}

item_found() {
  case "$1" in
    clt) xcode-select -p >/dev/null 2>&1 </dev/null ;;
    brew) [ -n "$(brew_path)" ] ;;
    warp) has_warp ;;
    *) command -v "$1" >/dev/null 2>&1 ;;
  esac
}

item_blocked() {
  case "$1" in
    git) item_found git || echo "install it with your package manager" ;;
    brew)
      if [ "$os_name" = Linux ] && ! command -v git >/dev/null 2>&1; then
        echo "needs git"
      fi
      ;;
  esac
}

item_fixed() {
  item_found "$1" || [ -n "$(item_blocked "$1")" ]
}

is_selected() {
  eval "[ \"\$sel_$1\" = 1 ]"
}

build_list() {
  if [ "$terminal" = warp ]; then terminal_items="warp tmux"; else terminal_items=herdr; fi
  if [ "$os_name" = Linux ]; then
    mandatory_items="git brew uv claude herdr"
    optional_items="gh glab"
  elif [ "$intel_mac" = 1 ] && [ "$terminal" != warp ]; then
    mandatory_items="clt uv claude herdr"
    optional_items="brew gh glab"
  else
    mandatory_items="clt brew uv claude $terminal_items"
    optional_items="gh glab"
  fi
  for key in $mandatory_items; do
    if item_fixed "$key"; then eval "sel_$key=0"; else eval "sel_$key=1"; fi
  done
  for key in $optional_items; do
    eval "sel_$key=0"
  done
}

show_item() {
  box="[ ]"
  if is_selected "$2"; then box="[x]"; fi
  reason=$(item_blocked "$2")
  if item_found "$2"; then
    tag=" (found)"
  elif [ -n "$reason" ]; then
    tag=" ($reason)"
  else
    tag=""
  fi
  printf '  %s) %s %s%s: %s\n' "$1" "$box" "$(item_name "$2")" "$tag" "$(item_use "$2")"
}

show_list() {
  printf '\nCAPTN needs these tools. [x] means that the script installs it.\n'
  number=0
  printf 'Mandatory\n'
  for key in $mandatory_items; do
    number=$((number + 1))
    show_item "$number" "$key"
  done
  printf 'Optional\n'
  for key in $optional_items; do
    number=$((number + 1))
    show_item "$number" "$key"
  done
}

item_at() {
  position=0
  for key in $mandatory_items $optional_items; do
    position=$((position + 1))
    if [ "$position" = "$1" ]; then
      printf '%s\n' "$key"
      return 0
    fi
  done
}

toggle_item() {
  key=""
  case "$1" in
    *[!0-9]*) ;;
    *) key=$(item_at "$1") ;;
  esac
  if [ -z "$key" ] || item_fixed "$key"; then
    printf 'Item %s cannot be changed.\n' "$1"
  elif is_selected "$key"; then
    eval "sel_$key=0"
  else
    eval "sel_$key=1"
  fi
}

choose_items() {
  while :; do
    show_list
    ask "Type numbers to change, Enter to install: " ""
    [ -n "$answer" ] || return 0
    set -f
    for x in $answer; do
      toggle_item "$x"
    done
    set +f
  done
}

use_brew() {
  brew_bin=$(brew_path)
  [ -n "$brew_bin" ] || return 0
  eval "$("$brew_bin" shellenv </dev/null)"
}

run_install() {
  if [ "$1" = brew ]; then
    sh -c "$2" <&3
  else
    sh -c "$2" </dev/null
  fi
}

install_items() {
  for key in $mandatory_items $optional_items; do
    is_selected "$key" || continue
    name=$(item_name "$key")
    command=$(install_command "$key")
    case "$command" in
      "brew "*)
        if ! command -v brew >/dev/null 2>&1; then
          printf 'Install %s later: %s\n' "$name" "$command"
          continue
        fi
        ;;
    esac
    if ! run_install "$key" "$command" || { [ "$key" != clt ] && ! item_found "$key"; }; then
      printf 'factory install: The %s install failed. Install it later: %s\n' "$name" "$command" >&2
      continue
    fi
    case "$key" in
      clt) ask "Finish the Command Line Tools install in its window, then press Enter. " "" ;;
      brew) use_brew ;;
    esac
  done
}

brew_path_hint() {
  brew_bin=$(brew_path)
  [ -n "$brew_bin" ] || return 0
  case ":$user_path:" in
    *":$(dirname "$brew_bin"):"*) ;;
    *)
      if on_macos; then shell_file="~/.zprofile"; else shell_file="~/.bashrc"; fi
      printf 'Add this line to %s: eval "$(%s shellenv)"\n' "$shell_file" "$brew_bin"
      ;;
  esac
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
    "") if [ "$interactive" = 1 ]; then ask_terminal; fi ;;
    *) fail "FACTORY_INSTALL_TERMINAL must be herdr or warp." ;;
  esac
}

finish_terminal() {
  if [ -z "$terminal" ]; then
    if has_herdr; then
      return 0
    elif has_warp; then
      terminal=warp
    else
      printf 'factory install: No terminal tool found. Tasks need Herdr (https://herdr.dev) or, on macOS, Warp with tmux (https://www.warp.dev). Run the install script in a terminal to choose one.\n' >&2
      return 0
    fi
  fi
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

  user_path=$PATH
  platform_init
  export PATH="$HOME/.local/bin:$PATH"
  use_brew
  if open_answers; then interactive=1; else interactive=0; fi
  choose_terminal
  if [ "$interactive" = 1 ]; then
    build_list
    choose_items
    install_items
    use_brew
  fi

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
  finish_terminal
  case ":$user_path:" in
    *":$link_dir:"*) ;;
    *) printf 'Add %s to your PATH.\n' "$link_dir" ;;
  esac
  brew_path_hint
}

main "$@"
