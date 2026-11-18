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

main() {
  set -eu
  umask 022

  base=${FACTORY_INSTALL_DOWNLOAD_BASE:-https://github.com/Bwaim/SoftwareFactory/releases/latest/download}
  proto=${FACTORY_INSTALL_PROTO:-=https}
  dir=${FACTORY_INSTALL_DIR:-$HOME/.local/share/software-factory}
  link_dir=${FACTORY_LINK_DIR:-$HOME/.local/bin}
  link="$link_dir/factory"

  for tool in curl tar uv git claude; do
    command -v "$tool" >/dev/null 2>&1 || fail "$tool is required."
  done
  command -v herdr >/dev/null 2>&1 \
    || printf 'factory install: herdr is not on PATH. Tasks need it to start. Install it from https://herdr.dev\n' >&2

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
  case ":$PATH:" in
    *":$link_dir:"*) ;;
    *) printf 'Add %s to your PATH.\n' "$link_dir" ;;
  esac
}

main "$@"
