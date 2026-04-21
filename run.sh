#!/usr/bin/env bash
# run.sh — Shell launcher for PrasWord (Linux / macOS)
# Works whether or not the package is installed via pip.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHONPATH="$DIR:${PYTHONPATH:-}" exec python3 -m prasword "$@"
