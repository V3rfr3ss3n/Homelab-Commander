#!/usr/bin/env bash
set -euo pipefail

status=0

if rg -n --hidden \
  -g '!.git/**' \
  -g '!.venv/**' \
  -g '!scripts/check-public-data.sh' \
  -g '!uv.lock' \
  '(^|[^0-9])(10\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|192\.168\.[0-9]{1,3}\.[0-9]{1,3}|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]{1,3}\.[0-9]{1,3})([^0-9]|$)' .; then
  echo "Private IPv4 address found in public project files."
  status=1
fi

if rg -n --hidden \
  -g '!.git/**' \
  -g '!.venv/**' \
  -g '!scripts/check-public-data.sh' \
  '(/home/[^/[:space:]]+|/Users/[^/[:space:]]+|[A-Za-z]:\\Users\\[^\\[:space:]]+)' .; then
  echo "User-specific absolute path found in public project files."
  status=1
fi

exit "$status"
