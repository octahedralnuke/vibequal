#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
  echo "Usage: bash scripts/publish_github.sh [repository-name] [--private|--public]"
  echo "Requires GitHub CLI (gh), prior gh auth login, and a clean local commit."
  exit 0
fi
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
repository_name="${1:-vibequal}"
visibility="${2:---private}"
if [[ "$visibility" != "--private" && "$visibility" != "--public" ]]; then
  echo "Visibility must be --private or --public" >&2
  exit 2
fi
command -v gh >/dev/null || { echo "Install GitHub CLI from https://cli.github.com/ first." >&2; exit 2; }
gh auth status
git rev-parse --verify HEAD >/dev/null
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Commit or review local changes before publishing." >&2
  exit 2
fi
if git remote get-url origin >/dev/null 2>&1; then
  echo "An origin remote already exists. Inspect it; this script will not replace it." >&2
  exit 2
fi
gh repo create "$repository_name" "$visibility" --source . --remote origin --push \
  --description "CAD-to-modal vibration screening with Python, Gmsh and CalculiX; educational FEA and verification."
