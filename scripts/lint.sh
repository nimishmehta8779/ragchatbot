#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

case "${1:-check}" in
  format)
    uv run black backend/ main.py
    ;;
  check)
    uv run black --check backend/ main.py
    ;;
  *)
    echo "Usage: $0 [check|format]"
    echo "  check   (default) Report files that need formatting"
    echo "  format  Reformat files in-place"
    exit 1
    ;;
esac
