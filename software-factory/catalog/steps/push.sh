#!/usr/bin/env bash
set -euo pipefail
branch=$(git symbolic-ref --short -q HEAD) || { echo "HEAD is detached. Create a branch first."; exit 1; }
git push -u origin "$branch"
factory state set branch "$branch"
