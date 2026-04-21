#!/usr/bin/env python3
"""
run.py — zero-install launcher for PrasWord.

Run this from the project root if you have NOT done `pip install -e .`:

    python run.py

It adds the project root to sys.path so the `prasword` package is found
without any installation step.
"""
import sys
import os

# Add the project root (directory containing this script) to sys.path.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from prasword.main import main
sys.exit(main())
