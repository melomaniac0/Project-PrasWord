#!/usr/bin/env python3
"""
PrasWord — main.py
==================
Application entry-point.

Responsibilities
----------------
* Bootstrap the Qt application (QApplication, theme, fonts).
* Instantiate and show the MainWindow.
* Set up the global exception handler so unhandled errors surface in a
  dialog instead of silently killing the process.
* Start the Qt event loop.

Usage
-----
    python -m prasword          # run as a package
    python prasword/main.py     # run directly (dev convenience)
"""

import sys
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the repo root is on sys.path when executed directly (dev mode).
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Qt imports — fail early with a helpful message if PySide6 is missing.
# ---------------------------------------------------------------------------
try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import Qt, QSettings
    from PySide6.QtGui import QFont, QFontDatabase
except ImportError as exc:  # pragma: no cover
    print(
        f"[PrasWord] PySide6 is required but not installed.\n"
        f"  pip install PySide6\n\nOriginal error: {exc}",
        file=sys.stderr,
    )
    sys.exit(1)

from prasword.gui.main_window import MainWindow
from prasword.utils.config import AppConfig
from prasword.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Global exception hook
# ---------------------------------------------------------------------------

def _exception_hook(exc_type, exc_value, exc_tb):
    """
    Catch all unhandled exceptions and show them in a Qt dialog so the user
    sees a meaningful message instead of a bare crash.

    The exception is *also* forwarded to the default sys.excepthook so that
    it appears in the terminal / log during development.
    """
    log.critical(
        "Unhandled exception",
        exc_info=(exc_type, exc_value, exc_tb),
    )

    # During headless / CI runs there may be no QApplication yet.
    if QApplication.instance() is not None:
        msg = QMessageBox()
        msg.setWindowTitle("PrasWord — Unexpected Error")
        msg.setIcon(QMessageBox.Critical)
        msg.setText("<b>An unexpected error occurred.</b>")
        formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        msg.setDetailedText(formatted)
        msg.exec()

    # Delegate to the original hook (prints to stderr).
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _exception_hook


# ---------------------------------------------------------------------------
# Application bootstrap
# ---------------------------------------------------------------------------

def _apply_high_dpi_settings() -> None:
    """Enable high-DPI scaling before the QApplication is created."""
    # Qt 6 enables high-DPI scaling by default; these attrs are kept for
    # compatibility with older PySide6 builds.
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


def _load_bundled_fonts(app: QApplication) -> None:  # noqa: ARG001
    """
    Register any fonts bundled under resources/fonts/ with Qt's font database
    so they are available application-wide via QFont("FontName").
    """
    fonts_dir = Path(__file__).parent / "resources" / "fonts"
    if not fonts_dir.exists():
        return
    db = QFontDatabase()
    for font_file in fonts_dir.glob("*.ttf"):
        font_id = db.addApplicationFont(str(font_file))
        if font_id == -1:
            log.warning("Failed to load bundled font: %s", font_file.name)
        else:
            log.debug("Loaded bundled font: %s", font_file.name)


def _apply_initial_theme(app: QApplication, config: AppConfig) -> None:
    """
    Set the application-wide stylesheet based on the persisted theme
    preference (dark / light).  Full theme switching is handled at runtime
    by the ThemeManager; this is just the cold-start application.
    """
    from prasword.utils.theme_manager import ThemeManager  # local import to avoid cycles

    theme = config.get("appearance/theme", "dark")
    ThemeManager.apply(app, theme)


def create_application() -> QApplication:
    """
    Construct and configure the QApplication instance.

    Returns
    -------
    QApplication
        The fully configured application object.
    """
    _apply_high_dpi_settings()

    app = QApplication(sys.argv)
    app.setApplicationName("PrasWord")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("PrasWord")
    app.setOrganizationDomain("prasword.io")

    # QSettings picks up organisation/app names automatically.
    QSettings.setDefaultFormat(QSettings.IniFormat)

    config = AppConfig()
    _load_bundled_fonts(app)
    _apply_initial_theme(app, config)

    # Default application font — can be overridden by the user via preferences.
    app.setFont(QFont("Segoe UI", 10))

    return app


def main() -> int:
    """
    Main entry-point.

    Returns
    -------
    int
        Exit code forwarded to the OS (0 = success).
    """
    log.info("Starting PrasWord v%s", "0.1.0")

    app = create_application()
    config = AppConfig()

    window = MainWindow(config=config)
    window.show()

    log.info("Main window displayed; entering event loop.")
    exit_code = app.exec()

    log.info("PrasWord exiting with code %d", exit_code)
    return exit_code


# ---------------------------------------------------------------------------
# __main__ guard
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
