#!/usr/bin/env bash
# install.sh — One-shot setup script for PrasWord
# Usage: bash install.sh [--all]
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXTRAS="${1:-}"

echo "=============================================="
echo "  PrasWord Installer"
echo "=============================================="
echo ""

# Check Python version
PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python $PYVER detected"

# Create venv if not already in one
if [ -z "${VIRTUAL_ENV:-}" ]; then
    echo "→ Creating virtual environment at $DIR/.venv ..."
    python3 -m venv "$DIR/.venv"
    source "$DIR/.venv/bin/activate"
    echo "✓ Virtual environment created"
else
    echo "✓ Using existing virtual environment: $VIRTUAL_ENV"
fi

# Upgrade pip
pip install --upgrade pip --quiet

# Install the package
if [ "$EXTRAS" = "--all" ]; then
    echo "→ Installing PrasWord with all optional extras ..."
    pip install -e "$DIR[all]" --quiet
else
    echo "→ Installing PrasWord (core) ..."
    pip install -e "$DIR" --quiet
    echo ""
    echo "  Tip: run  bash install.sh --all  to also install:"
    echo "       bibtexparser (BibTeX), sympy (LaTeX math),"
    echo "       pandas (CSV tables), gitpython (Git integration)"
fi

echo ""
echo "=============================================="
echo "  Installation complete!"
echo ""
echo "  To run PrasWord:"
echo "    source .venv/bin/activate   # if not already active"
echo "    python -m prasword"
echo "    # OR"
echo "    bash run.sh"
echo "=============================================="
