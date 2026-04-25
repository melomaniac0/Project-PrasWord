"""
setup.py
========
Legacy setuptools shim for PrasWord.

The authoritative build specification lives in ``pyproject.toml``.
This file exists solely for compatibility with older pip / build tool
versions that do not yet support PEP 517/518 directly.

For all normal use cases, install via:

    pip install -e .                  # editable / development install
    pip install -e ".[all]"           # with all optional extras
    pip install -e ".[all,dev]"       # with test + lint tools
    pip install .                     # production install
"""
from __future__ import annotations

from pathlib import Path

# ── Attempt the modern PEP 517 path first ─────────────────────────────────────
try:
    from setuptools import setup, find_packages
except ImportError as exc:
    raise SystemExit(
        "setuptools is required to install PrasWord.\n"
        "  pip install setuptools\n"
        f"Original error: {exc}"
    ) from exc


# ── Read long description from README ─────────────────────────────────────────
_HERE = Path(__file__).parent
_LONG_DESC = (_HERE / "README.md").read_text(encoding="utf-8")


# ── Core runtime dependencies ─────────────────────────────────────────────────
_INSTALL_REQUIRES = [
    "PySide6>=6.6",
    "python-docx>=1.1",
    "pygments>=2.17",
]

# ── Optional feature groups ────────────────────────────────────────────────────
_EXTRAS_REQUIRE = {
    # Academic writing — BibTeX import/export
    "academic": [
        "bibtexparser>=1.4",
    ],
    # Data science — LaTeX math rendering, CSV/pandas utilities
    "datascience": [
        "matplotlib>=3.7",
        "sympy>=1.12",
        "pandas>=2.0",
    ],
    # Git integration
    "git": [
        "gitpython>=3.1",
    ],
    # Development + test tools
    "dev": [
        "pytest>=7.4",
        "pytest-qt>=4.2",
        "ruff>=0.4",
        "mypy>=1.8",
        "coverage>=7.4",
    ],
}

# Convenience "all" meta-extra that installs every optional feature
_EXTRAS_REQUIRE["all"] = sorted(
    {dep for key, deps in _EXTRAS_REQUIRE.items() if key != "dev" for dep in deps}
)


# ── Entry points ───────────────────────────────────────────────────────────────
_ENTRY_POINTS = {
    "console_scripts": [
        "prasword = prasword.main:main",
    ],
}


# ── Package discovery ──────────────────────────────────────────────────────────
# All Python packages live under prasword/ — find_packages() discovers them
# automatically.  Exclude test and build artefacts.
_PACKAGES = find_packages(
    where=".",
    include=["prasword*"],
    exclude=["tests*", "build*", "dist*", "*.egg-info"],
)


# ── Package data ───────────────────────────────────────────────────────────────
# Include non-Python assets bundled inside the prasword/ tree.
_PACKAGE_DATA = {
    "prasword": [
        "resources/fonts/*.ttf",
        "resources/icons/*.png",
        "resources/icons/*.svg",
        "resources/themes/*.qss",
        "py.typed",                 # PEP 561 type-checking marker
    ],
}


# ── Classifiers ────────────────────────────────────────────────────────────────
_CLASSIFIERS = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Science/Research",
    "Intended Audience :: Education",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Text Editors :: Word Processors",
    "Topic :: Scientific/Engineering",
    "Environment :: X11 Applications :: Qt",
]


# ── setup() call ───────────────────────────────────────────────────────────────
setup(
    # ── Identity ────────────────────────────────────────────────────────────
    name             = "prasword",
    version          = "0.1.0",
    description      = (
        "Professional word processor for academic and data science workflows"
    ),
    long_description          = _LONG_DESC,
    long_description_content_type = "text/markdown",
    author           = "PrasWord Contributors",
    license          = "MIT",
    url              = "https://github.com/your-org/prasword",
    project_urls     = {
        "Bug Tracker":  "https://github.com/your-org/prasword/issues",
        "Source Code":  "https://github.com/your-org/prasword",
        "Changelog":    "https://github.com/your-org/prasword/releases",
    },

    # ── Python compatibility ─────────────────────────────────────────────────
    python_requires  = ">=3.10",

    # ── Packages ────────────────────────────────────────────────────────────
    packages         = _PACKAGES,
    package_data     = _PACKAGE_DATA,
    include_package_data = True,

    # ── Dependencies ─────────────────────────────────────────────────────────
    install_requires  = _INSTALL_REQUIRES,
    extras_require    = _EXTRAS_REQUIRE,

    # ── Entry points ─────────────────────────────────────────────────────────
    entry_points     = _ENTRY_POINTS,

    # ── PyPI metadata ────────────────────────────────────────────────────────
    classifiers      = _CLASSIFIERS,
    keywords         = [
        "word processor", "academic", "data science",
        "bibtex", "latex", "pyside6", "qt",
    ],

    # ── Zip safety ───────────────────────────────────────────────────────────
    # PySide6 ships compiled extensions — must not be run from a zip.
    zip_safe = False,
)
