#!/bin/sh
set -eu

version=$1
out=$2
root=$(cd "$(dirname "$0")/.." && pwd)
sf="$root/software-factory"
cli_version=$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' "$sf/lib/factory/cli.py")

if [ "$version" != "$cli_version" ]; then
  printf 'build-release: version %s differs from cli.VERSION %s.\n' "$version" "$cli_version" >&2
  exit 1
fi

plugin_version=$(sed -n 's/^  "version": "\(.*\)",$/\1/p' "$sf/.claude-plugin/plugin.json")
if [ "$version" != "$plugin_version" ]; then
  printf 'build-release: version %s differs from plugin.json version %s.\n' "$version" "$plugin_version" >&2
  exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir "$work/software-factory"
for folder in bin lib builtin catalog migrations; do
  cp -R "$sf/$folder" "$work/software-factory/$folder"
done
find "$work/software-factory" -name __pycache__ -type d -prune -exec rm -rf {} +
printf '%s\n' "$version" > "$work/software-factory/VERSION"

mkdir -p "$out"
COPYFILE_DISABLE=1 tar -czf "$out/software-factory.tar.gz" -C "$work" software-factory
cd "$out"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum software-factory.tar.gz > software-factory.tar.gz.sha256
else
  shasum -a 256 software-factory.tar.gz > software-factory.tar.gz.sha256
fi
printf '%s\n' "$out/software-factory.tar.gz"
