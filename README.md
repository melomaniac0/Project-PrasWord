# PrasWord

> A professional-grade, desktop word processor built for **academic** and **data science** workflows.

**Stack:** Python 3.10+ · PySide6 (Qt 6) · python-docx · Pygments · bibtexparser · GitPython

---

## Quick Start (3 commands)

```bash
git clone https://github.com/your-org/prasword.git
cd prasword
bash install.sh          # creates .venv, installs core deps
source .venv/bin/activate
python -m prasword
```

**No pip install needed?** Use the zero-install launcher:
```bash
python run.py            # adds project root to sys.path automatically
```

**Windows:**
```bat
run.bat
```

---

## Installation Options

| Command | What it installs |
|---|---|
| `bash install.sh` | Core only (PySide6, python-docx, Pygments) |
| `bash install.sh --all` | Core + BibTeX + LaTeX math + CSV/pandas + Git |
| `pip install -e .` | Core (editable, from project root) |
| `pip install -e ".[all]"` | All extras |
| `pip install -e ".[dev]"` | All + ruff + mypy + pytest |

### Environment variables

| Variable | Default | Effect |
|---|---|---|
| `PRASWORD_LOG_LEVEL` | `INFO` | Set to `DEBUG` for verbose output |
| `QT_QPA_PLATFORM` | *(auto)* | Set to `offscreen` for headless/CI |

---

## Project Structure

```
PrasWord/                        ← project root (cd here to run)
│
├── prasword/                    ← Python package
│   ├── __init__.py              (version metadata)
│   ├── __main__.py              (python -m prasword entry-point)
│   ├── main.py                  (QApplication bootstrap, exception hook)
│   │
│   ├── core/                    ── Document Engine (GUI-free) ──
│   │   ├── document.py          Document data model (QTextDocument + signals)
│   │   └── document_manager.py  Controller: open/save/close/active tracking
│   │
│   ├── gui/                     ── PySide6 GUI Layer ──
│   │   ├── main_window.py       QMainWindow: menus, toolbars, tabs, docks
│   │   ├── editor_widget.py     QTextEdit: line numbers, DF mode, insert helpers
│   │   │
│   │   ├── widgets/
│   │   │   ├── formatting_toolbar.py      Rich char/para formatting toolbar
│   │   │   ├── word_count_widget.py       Live 9-metric right-dock panel
│   │   │   ├── status_bar_widget.py       Debounced status bar (words/chars/state)
│   │   │   └── distraction_free_overlay.py  Zen-mode manager (banner + badge)
│   │   │
│   │   ├── panels/
│   │   │   └── sidebar_panel.py   Left dock: Files / TOC / References tabs
│   │   │
│   │   └── dialogs/
│   │       ├── find_replace_dialog.py   Regex search, replace, replace-all
│   │       ├── math_dialog.py           LaTeX input + snippet picker + preview
│   │       ├── citation_dialog.py       BibTeX browser + cite-key inserter
│   │       ├── insert_table_dialog.py   Blank table or CSV import
│   │       ├── git_dialog.py            Git status, stage, commit
│   │       └── preferences_dialog.py    Theme, font, editor, metrics settings
│   │
│   ├── features/                ── Feature Modules ──
│   │   ├── formatting/
│   │   │   └── formatting_engine.py       Bold/Italic/Underline/Strike/Sub/Sup,
│   │   │                                  Font, Size, Colour, Highlight,
│   │   │                                  Alignment, Spacing, Indent, Headings H1–H6
│   │   │
│   │   ├── layout/
│   │   │   ├── toc_generator.py           Auto Table of Contents (scan + insert)
│   │   │   ├── page_layout.py             Page size (A4/Letter/…), margins
│   │   │   ├── header_footer.py           Header/footer templates with placeholders
│   │   │   └── page_numbering.py          arabic/roman/alpha, PDF painter, live overlay
│   │   │
│   │   ├── academic/
│   │   │   ├── bibtex_manager.py          .bib import, APA/MLA/Chicago/IEEE format,
│   │   │   │                              bibliography HTML generation, search
│   │   │   ├── citation_engine.py         In-text citation insertion
│   │   │   └── cross_reference.py         Label anchors + clickable xref links
│   │   │
│   │   ├── datascience/
│   │   │   ├── code_highlighter.py   (not yet)     Pygments syntax highlighting (Python/R/SQL/…)
│   │   │   ├── math_renderer.py      (not yet)     LaTeX → PNG via matplotlib; sympy validation
│   │   │   ├── csv_table.py          (not yet)     CSV/TSV → styled QTextTable with zebra rows
│   │   │   └── jupyter_cell.py       (not yet)     Executable cells (Python/R/Bash) in subprocess
│   │   │
│   │   ├── filemanagement/
│   │   │   └── file_io.py                 Load/save .docx .md .txt; PDF export via QPrinter
│   │   │
│   │   └── metrics/
│   │       └── metrics_engine.py          Words, chars, paragraphs, sentences,
│   │                                      unique words, avg word/sentence length,
│   │                                      reading time — fast path + full analysis
│   │
│   ├── utils/
│   │   ├── config.py            QSettings-backed typed preferences store
│   │   ├── logger.py            Rotating file + console logger (PRASWORD_LOG_LEVEL)
│   │   └── theme_manager.py     Dark/light QSS theme (Catppuccin palette)
│   │
│   └── resources/
│       ├── fonts/               Drop .ttf files here — auto-loaded at startup
│       ├── icons/               Reserved for icon theme
│       └── themes/              Reserved for custom QSS overrides
│
├── tests/
│   ├── conftest.py              Shared fixtures: qapp, blank_document, editor, …
│   ├── test_document.py    (not yet)     Document model: state, metrics, bibliography
│   ├── test_document_manager.py   (not yet)DocumentManager lifecycle
│   ├── test_formatting.py   (not yet)    FormattingEngine: bold/italic/heading/spacing
│   ├── test_metrics.py      (not yet)    MetricsEngine: counts, reading time, frozen dataclass
│   ├── test_fileio.py       (not yet)    FileIO: load/save/round-trip txt/md/docx
│   ├── test_academic.py     (not yet)    BibTeXManager: import, search, format, generate
│   ├── test_layout.py           PageLayout, margins, header/footer, page numbering
│   └── test_integration.py      End-to-end: open→edit→save→reload, widgets, signals
│
├── main.py          → prasword/main.py (symlink-style re-export, optional)
├── run.py           Zero-install launcher (adds project root to sys.path)
├── run.sh           Shell launcher (sets PYTHONPATH, works without pip install)
├── run.bat          Windows launcher
├── install.sh       One-shot venv + pip install setup script
├── Makefile         make run / test / lint / typecheck / clean
├── pyproject.toml   PEP 517 build spec, dependency groups
├── setup.py    (not yet)     Legacy setuptools shim
└── README.md        This file
```

---

## Features

### ✅ Text Formatting
Bold · Italic · Underline · Strikethrough · Subscript · Superscript · Font family · Font size · Text colour · Background highlight · Clear formatting

### ✅ Paragraph & Layout
Left / Centre / Right / Justify alignment · Line spacing (1× – 3×) · Indent increase/decrease · First-line indent · Left/right paragraph margins · Page breaks · Page size (A4, A3, Letter, Legal, landscape) · Margins (mm)

### ✅ Document Structure
H1–H6 headings (styled, colour-coded) · Auto Table of Contents (scan + insert + refresh) · Page numbering (arabic / roman / alpha, PDF painter + live overlay) · Headers & footers (template with `{page}`, `{pages}`, `{title}`, `{author}`, `{date}`)

### ✅ Academic Tools
BibTeX `.bib` file import · In-text citation insertion (APA / MLA / Chicago / IEEE) · Auto-generated bibliography (cited-only or full) · Cross-reference anchors + clickable links · Bibliography browser panel (search, filter, format preview)

### ✅ Data Science Integration
Syntax-highlighted code blocks via Pygments (Python, R, SQL, Bash, Julia, …) · LaTeX math rendering (matplotlib → PNG; sympy validation) · CSV / TSV → styled QTextTable with zebra striping · Jupyter-style execution cells (Python / R / Bash via subprocess)

### ✅ File Management
Open/save `.docx` (python-docx) · `.md` · `.txt` · Export `.pdf` (Qt QPrinter) · Tabbed document navigation · Recent files · Find & Replace (plain text + regex, case/whole-word, replace-all)

### ✅ Metrics
Live word count · Character count (with/without spaces) · Paragraph count · Sentence count · Unique word count · Avg word length · Avg sentence length · Estimated reading time · Status bar + right-dock Metrics panel

### ✅ UX / UI
Dark mode (Catppuccin Mocha) · Light mode (Catppuccin Latte) · Runtime theme toggle (Ctrl+Shift+T) · Distraction-free mode (F11) with hover exit banner + floating word-count badge · Sidebar dock (File tree / TOC / References) · Metrics dock · Zoom in/out/reset · Preferences dialog · Git commit dialog

---

## Development

```bash
# Run tests (headless)
make test
# or
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -v

# Lint
make lint

# Type check
make typecheck

# Clean build artefacts
make clean
```

### Adding a feature module

Every feature lives in `prasword/features/<category>/`. The pattern:

```python
# prasword/features/formatting/my_feature.py
from PySide6.QtGui import QTextCharFormat
from prasword.gui.editor_widget import EditorWidget

class MyFeature:
    @staticmethod
    def apply(editor: EditorWidget) -> None:
        fmt = QTextCharFormat()
        # ... modify fmt ...
        editor.mergeCurrentCharFormat(fmt)
```

Wire it to a menu action in `MainWindow` — no other changes needed. The engine/GUI separation guarantees zero breakage to existing features.

### Adding a file format

In `prasword/features/filemanagement/file_io.py`, add your handler class and one dict entry:

```python
class _MyFormatHandler:
    @staticmethod
    def load(doc, path): ...
    @staticmethod
    def save(doc, path): ...

_LOADERS[".xyz"] = _MyFormatHandler
_WRITERS[".xyz"] = _MyFormatHandler
```

That's it. The dispatcher does the rest.

---

## Architecture Principles

| Principle | How it's enforced |
|---|---|
| **GUI ↔ Engine separation** | `core/` and `features/` never import `gui/` widgets. All communication via Qt signals. |
| **No circular imports** | Feature modules use lazy imports inside methods. |
| **Pluggable formats** | `FileIO` is a registry dict — one dict entry per new format. |
| **Observable documents** | `Document` emits `state_changed`, `title_changed`, `metadata_changed` — GUI stays in sync without polling. |
| **Safe multi-doc** | `DocumentManager` enforces unsaved-change prompts via signals before any close/quit. |
| **Debounced metrics** | All live-metric updates are rate-limited (300–500 ms) to avoid CPU spikes on every keystroke. |

---

## Troubleshooting

**`No module named 'prasword'`**
→ You are running `python -m prasword` from inside the `prasword/` package directory instead of the project root. Fix:
```bash
cd PrasWord           # the directory containing pyproject.toml
python -m prasword    # now it finds the package
# or use the zero-install launcher:
python run.py
```

**`Could not load Qt platform plugin "xcb"`** (Linux)
→ You are on a headless server. Install `libxcb-cursor0` or run with the offscreen platform:
```bash
QT_QPA_PLATFORM=offscreen python -m prasword   # headless mode
# For a real desktop, install: sudo apt install libxcb-cursor0
```

**BibTeX import says `bibtexparser not installed`**
```bash
pip install bibtexparser
```

**LaTeX math shows raw text instead of rendered image**
```bash
pip install matplotlib
```

**Git panel shows `gitpython not installed`**
```bash
pip install gitpython
```

---

## License

MIT © PrasWord Contributors
