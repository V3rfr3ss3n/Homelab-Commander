#!/usr/bin/env bash
set -euo pipefail

manifest='custom_components/homelab_updates/manifest.json'
status=0

if rg -n 'example\.invalid' "$manifest"; then
  echo "Replace reserved manifest URLs with the public repository URLs."
  status=1
fi

if rg -n '"codeowners"[[:space:]]*:[[:space:]]*\[\]' "$manifest"; then
  echo "Add at least one real GitHub code owner before release."
  status=1
fi

exit "$status"
