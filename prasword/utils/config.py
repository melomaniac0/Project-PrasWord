"""
prasword.utils.config
=====================
Persistent application configuration backed by ``QSettings``.

``AppConfig`` provides a typed, dict-like interface over Qt's INI-format
settings file.  All preferences (theme, default font, recent files, …) are
stored and retrieved through this class.

The settings file is written to the platform-appropriate user config
directory (e.g. ``~/.config/PrasWord/PrasWord.ini`` on Linux,
``HKCU\\Software\\PrasWord`` on Windows).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSettings

from prasword.utils.logger import get_logger

log = get_logger(__name__)

# Default values for every known preference key.
_DEFAULTS: dict[str, Any] = {
    "appearance/theme": "dark",
    "appearance/font_family": "Segoe UI",
    "appearance/font_size": 11,
    "appearance/distraction_free": False,
    "editor/line_spacing": 1.5,
    "editor/tab_width": 4,
    "editor/show_line_numbers": True,
    "editor/auto_save": True,
    "editor/auto_save_interval_seconds": 60,
    "files/recent_files": [],
    "files/max_recent": 10,
    "metrics/show_word_count": True,
    "metrics/show_char_count": True,
    "metrics/show_reading_time": True,
    "git/auto_commit": False,
    "git/commit_on_save": False,
}


class AppConfig:
    """
    Typed wrapper around ``QSettings``.

    Usage
    -----
    >>> cfg = AppConfig()
    >>> cfg.get("appearance/theme")
    'dark'
    >>> cfg.set("appearance/theme", "light")
    """

    def __init__(self) -> None:
        self._settings = QSettings()
        log.debug("AppConfig backed by: %s", self._settings.fileName())

    # ------------------------------------------------------------------
    # Core get / set
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a configuration value.

        Falls back to the built-in defaults table, then to *default*.
        """
        fallback = _DEFAULTS.get(key, default)
        return self._settings.value(key, fallback)

    def set(self, key: str, value: Any) -> None:
        """Persist a configuration value immediately."""
        self._settings.setValue(key, value)
        self._settings.sync()
        log.debug("Config set: %s = %r", key, value)

    def reset(self, key: str) -> None:
        """Reset a single key to its default value."""
        default = _DEFAULTS.get(key)
        if default is not None:
            self.set(key, default)
        else:
            self._settings.remove(key)

    def reset_all(self) -> None:
        """Wipe all user preferences and restore factory defaults."""
        self._settings.clear()
        for key, value in _DEFAULTS.items():
            self._settings.setValue(key, value)
        self._settings.sync()
        log.info("All preferences reset to defaults.")

    # ------------------------------------------------------------------
    # Recent files helpers
    # ------------------------------------------------------------------

    def add_recent_file(self, path: str) -> None:
        """Prepend *path* to the recent-files list, trimming to max_recent."""
        recent: list[str] = self.get("files/recent_files", []) or []
        if isinstance(recent, str):
            recent = [recent]
        # Remove duplicates.
        recent = [p for p in recent if p != path]
        recent.insert(0, path)
        max_recent = int(self.get("files/max_recent", 10))
        recent = recent[:max_recent]
        self.set("files/recent_files", recent)

    def get_recent_files(self) -> list[str]:
        """Return the list of recently opened file paths (most recent first)."""
        recent = self.get("files/recent_files", [])
        if isinstance(recent, str):
            return [recent] if recent else []
        return recent or []

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<AppConfig file={self._settings.fileName()!r}>"
