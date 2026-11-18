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
  mv "$stage" "$dir"

  mkdir -p "$link_dir"
  ln -s "$dir/bin/factory" "$link"

  printf 'Installed factory %s in %s.\n' "$version" "$dir"
  case ":$PATH:" in
    *":$link_dir:"*) ;;
    *) printf 'Add %s to your PATH.\n' "$link_dir" ;;
  esac
}

main "$@"
