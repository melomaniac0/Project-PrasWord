"""
prasword.gui.main_window
========================
Top-level application window.

Composes:
* Tabbed document area.
* FormattingToolbar (second toolbar row, syncs with cursor).
* Sidebar dock  — File tree / TOC / References.
* Metrics dock  — Live word count / character count panel.
* Enhanced StatusBarWidget with debounced live metrics.
* Menu bar: File / Edit / View / Insert / Format / Tools / Help.
* Distraction-free mode via DistractionFreeMode.toggle().
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QAction, QCloseEvent, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QTabWidget,
    QToolBar,
    QWidget,
)

from prasword.core.document import Document, DocumentState
from prasword.core.document_manager import DocumentManager
from prasword.gui.editor_widget import EditorWidget
from prasword.gui.widgets.formatting_toolbar import FormattingToolbar
from prasword.gui.widgets.status_bar_widget import StatusBarWidget
from prasword.gui.widgets.distraction_free_overlay import DistractionFreeMode
from prasword.utils.config import AppConfig
from prasword.utils.logger import get_logger
from prasword.utils.theme_manager import ThemeManager

log = get_logger(__name__)


class MainWindow(QMainWindow):
    """
    PrasWord main application window.

    Parameters
    ----------
    config : AppConfig
    parent : QWidget | None
    """

    def __init__(
        self,
        config: AppConfig,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._doc_manager = DocumentManager(parent=self)

        # document.id → EditorWidget
        self._editors: dict[str, EditorWidget] = {}

        self._setup_window()
        self._create_menu_bar()
        self._create_main_toolbar()
        self._create_formatting_toolbar()
        self._create_tab_area()
        self._create_sidebar_dock()
        self._create_metrics_dock()
        self._create_status_bar()
        self._connect_manager_signals()

        # Auto-save timer.
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.timeout.connect(self._auto_save_all)
        self._restart_auto_save_timer()

        # Start with a blank document.
        self._doc_manager.new_document()
        log.info("MainWindow initialised.")

    # ------------------------------------------------------------------ #
    # Window setup                                                        #
    # ------------------------------------------------------------------ #

    def _setup_window(self) -> None:
        self.setWindowTitle("PrasWord")
        self.setMinimumSize(960, 680)
        self.resize(1360, 860)
        self.setDockOptions(
            QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks
        )

    # ------------------------------------------------------------------ #
    # Menu bar                                                            #
    # ------------------------------------------------------------------ #

    def _create_menu_bar(self) -> None:
        mb = self.menuBar()

        # ── File ──────────────────────────────────────────────────────
        fm = mb.addMenu("&File")
        self.action_new      = self._action("&New",             QKeySequence.New,   self._on_new)
        self.action_open     = self._action("&Open…",           QKeySequence.Open,  self._on_open)
        self.action_save     = self._action("&Save",            QKeySequence.Save,  self._on_save)
        self.action_save_as  = self._action("Save &As…",        QKeySequence.SaveAs,self._on_save_as)
        self.action_export_pdf = self._action("Export as &PDF…", None,              self._on_export_pdf)
        self.action_close_tab= self._action("&Close Tab",       "Ctrl+W",           self._on_close_tab)
        self.action_quit     = self._action("&Quit",            QKeySequence.Quit,  self.close)

        for a in (self.action_new, self.action_open):
            fm.addAction(a)
        self._recent_menu = fm.addMenu("Open &Recent")
        self._populate_recent_menu()
        fm.addSeparator()
        for a in (self.action_save, self.action_save_as, self.action_export_pdf):
            fm.addAction(a)
        fm.addSeparator()
        fm.addAction(self.action_close_tab)
        fm.addAction(self.action_quit)

        # ── Edit ──────────────────────────────────────────────────────
        em = mb.addMenu("&Edit")
        self.action_undo  = self._action("&Undo",  QKeySequence.Undo,  self._relay("undo"))
        self.action_redo  = self._action("&Redo",  QKeySequence.Redo,  self._relay("redo"))
        self.action_cut   = self._action("Cu&t",   QKeySequence.Cut,   self._relay("cut"))
        self.action_copy  = self._action("&Copy",  QKeySequence.Copy,  self._relay("copy"))
        self.action_paste = self._action("&Paste", QKeySequence.Paste, self._relay("paste"))
        self.action_select_all = self._action("Select &All", QKeySequence.SelectAll, self._relay("selectAll"))
        self.action_find  = self._action("&Find / Replace…", "Ctrl+H", self._on_find_replace)

        for a in (self.action_undo, self.action_redo):
            em.addAction(a)
        em.addSeparator()
        for a in (self.action_cut, self.action_copy, self.action_paste, self.action_select_all):
            em.addAction(a)
        em.addSeparator()
        em.addAction(self.action_find)

        # ── View ──────────────────────────────────────────────────────
        vm = mb.addMenu("&View")
        self.action_toggle_theme = self._action(
            "Toggle &Dark/Light Mode", "Ctrl+Shift+T", self._on_toggle_theme)
        self.action_distraction_free = self._action(
            "&Distraction-Free Mode", "F11", self._on_distraction_free, checkable=True)
        self.action_show_sidebar = self._action(
            "&Sidebar", "Ctrl+\\", self._on_toggle_sidebar, checkable=True)
        self.action_show_sidebar.setChecked(True)
        self.action_show_metrics = self._action(
            "&Metrics Panel", "Ctrl+M", self._on_toggle_metrics, checkable=True)
        self.action_show_metrics.setChecked(True)
        self.action_zoom_in  = self._action("Zoom &In",  "Ctrl+=", self._on_zoom_in)
        self.action_zoom_out = self._action("Zoom &Out", "Ctrl+-", self._on_zoom_out)
        self.action_zoom_reset = self._action("&Reset Zoom", "Ctrl+0", self._on_zoom_reset)

        for a in (self.action_toggle_theme, self.action_distraction_free):
            vm.addAction(a)
        vm.addSeparator()
        vm.addAction(self.action_show_sidebar)
        vm.addAction(self.action_show_metrics)
        vm.addSeparator()
        for a in (self.action_zoom_in, self.action_zoom_out, self.action_zoom_reset):
            vm.addAction(a)

        # ── Insert ────────────────────────────────────────────────────
        im = mb.addMenu("&Insert")
        self.action_insert_table    = self._action("&Table…",           None,        self._on_insert_table)
        self.action_insert_image    = self._action("&Image…",           None,        self._on_insert_image)
        self.action_insert_code     = self._action("&Code Block",       "Ctrl+Shift+K", self._on_insert_code)
        self.action_insert_math     = self._action("&Math (LaTeX)…",    "Ctrl+Shift+M", self._on_insert_math)
        self.action_insert_citation = self._action("C&itation…",        "Ctrl+Shift+C", self._on_insert_citation)
        self.action_insert_toc      = self._action("Table of &Contents",None,        self._on_insert_toc)
        self.action_page_break      = self._action("&Page Break",       "Ctrl+Return",  self._on_page_break)

        for a in (
            self.action_insert_table, self.action_insert_image,
            self.action_insert_code, self.action_insert_math,
        ):
            im.addAction(a)
        im.addSeparator()
        im.addAction(self.action_insert_citation)
        im.addAction(self.action_insert_toc)
        im.addSeparator()
        im.addAction(self.action_page_break)

        # ── Format ────────────────────────────────────────────────────
        fmm = mb.addMenu("F&ormat")
        self.action_bold          = self._action("&Bold",         QKeySequence.Bold,      self._on_bold, checkable=True)
        self.action_italic        = self._action("&Italic",       QKeySequence.Italic,    self._on_italic, checkable=True)
        self.action_underline     = self._action("&Underline",    QKeySequence.Underline, self._on_underline, checkable=True)
        self.action_strikethrough = self._action("Strike&through",None,                  self._on_strikethrough, checkable=True)
        self.action_subscript     = self._action("S&ubscript",    None,                   self._on_subscript, checkable=True)
        self.action_superscript   = self._action("Su&perscript",  None,                   self._on_superscript, checkable=True)

        for a in (self.action_bold, self.action_italic,
                  self.action_underline, self.action_strikethrough,
                  self.action_subscript, self.action_superscript):
            fmm.addAction(a)
        fmm.addSeparator()

        self._heading_actions: list[QAction] = []
        for level in range(1, 7):
            a = self._action(
                f"Heading &{level}", f"Ctrl+{level}",
                lambda _=False, lv=level: self._on_heading(lv)
            )
            setattr(self, f"action_h{level}", a)
            self._heading_actions.append(a)
            fmm.addAction(a)

        fmm.addSeparator()
        self.action_clear_fmt = self._action(
            "Clear &Formatting", "Ctrl+Space", self._on_clear_fmt)
        fmm.addAction(self.action_clear_fmt)

        # ── Tools ─────────────────────────────────────────────────────
        tm = mb.addMenu("&Tools")
        self.action_word_count  = self._action("&Word Count…",    None,       self._on_word_count_dialog)
        self.action_import_bib  = self._action("Import &BibTeX…", None,       self._on_import_bibtex)
        self.action_gen_bib     = self._action("&Generate Bibliography", None,self._on_generate_bib)
        self.action_git_commit  = self._action("Git &Commit…",    None,       self._on_git_commit)
        self.action_page_num    = self._action("&Page Numbers…",  None,       self._on_page_numbers)
        self.action_preferences = self._action("&Preferences…",   "Ctrl+,",   self._on_preferences)

        for a in (self.action_word_count, self.action_import_bib,
                  self.action_gen_bib, self.action_git_commit,
                  self.action_page_num):
            tm.addAction(a)
        tm.addSeparator()
        tm.addAction(self.action_preferences)

        # ── Help ──────────────────────────────────────────────────────
        hm = mb.addMenu("&Help")
        self.action_about = self._action("&About PrasWord", None, self._on_about)
        hm.addAction(self.action_about)

    def _action(
        self,
        text: str,
        shortcut,
        slot,
        checkable: bool = False,
    ) -> QAction:
        """Helper to create a connected QAction."""
        a = QAction(text, self)
        if shortcut:
            if isinstance(shortcut, str):
                a.setShortcut(QKeySequence(shortcut))
            else:
                a.setShortcut(shortcut)
        if checkable:
            a.setCheckable(True)
            a.toggled.connect(slot)
        else:
            a.triggered.connect(slot)
        return a

    # ------------------------------------------------------------------ #
    # Toolbars                                                            #
    # ------------------------------------------------------------------ #

    def _create_main_toolbar(self) -> None:
        """File / navigation toolbar (top row)."""
        tb = QToolBar("Main", self)
        tb.setObjectName("MainToolbar")
        tb.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, tb)
        self._main_toolbar = tb

        for a in (self.action_new, self.action_open, self.action_save):
            tb.addAction(a)
        tb.addSeparator()
        for a in (self.action_undo, self.action_redo):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.action_find)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        tb.addAction(self.action_toggle_theme)
        tb.addAction(self.action_distraction_free)

    def _create_formatting_toolbar(self) -> None:
        """Second toolbar row: rich formatting controls."""
        self._fmt_toolbar = FormattingToolbar(self)
        self.addToolBar(Qt.TopToolBarArea, self._fmt_toolbar)

    # ------------------------------------------------------------------ #
    # Tab area                                                            #
    # ------------------------------------------------------------------ #

    def _create_tab_area(self) -> None:
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tabs)

    # ------------------------------------------------------------------ #
    # Sidebar dock                                                        #
    # ------------------------------------------------------------------ #

    def _create_sidebar_dock(self) -> None:
        self._sidebar_dock = QDockWidget("Sidebar", self)
        self._sidebar_dock.setObjectName("SidebarDock")
        self._sidebar_dock.setFeatures(
            QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable
        )
        try:
            from prasword.gui.panels.sidebar_panel import SidebarPanel
            panel = SidebarPanel(doc_manager=self._doc_manager, parent=self._sidebar_dock)
            # Forward file-tree double-click to open the document.
            panel._file_panel.file_activated.connect(
                lambda p: self._open_path(Path(p))
            )
            self._sidebar_dock.setWidget(panel)
        except Exception:
            self._sidebar_dock.setWidget(QLabel("Sidebar unavailable"))

        self._sidebar_dock.setMinimumWidth(210)
        self._sidebar_dock.setMaximumWidth(380)
        self.addDockWidget(Qt.LeftDockWidgetArea, self._sidebar_dock)

    # ------------------------------------------------------------------ #
    # Metrics dock                                                        #
    # ------------------------------------------------------------------ #

    def _create_metrics_dock(self) -> None:
        self._metrics_dock = QDockWidget("Metrics", self)
        self._metrics_dock.setObjectName("MetricsDock")
        self._metrics_dock.setFeatures(
            QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable
        )
        from prasword.gui.widgets.word_count_widget import WordCountWidget
        self._metrics_widget = WordCountWidget(self._metrics_dock)
        self._metrics_dock.setWidget(self._metrics_widget)
        self._metrics_dock.setMinimumWidth(180)
        self._metrics_dock.setMaximumWidth(260)
        self.addDockWidget(Qt.RightDockWidgetArea, self._metrics_dock)

    # ------------------------------------------------------------------ #
    # Status bar                                                          #
    # ------------------------------------------------------------------ #

    def _create_status_bar(self) -> None:
        self._status_bar = StatusBarWidget(self)
        self.setStatusBar(self._status_bar)

    # ------------------------------------------------------------------ #
    # DocumentManager signals                                             #
    # ------------------------------------------------------------------ #

    def _connect_manager_signals(self) -> None:
        dm = self._doc_manager
        dm.document_opened.connect(self._on_document_opened)
        dm.document_closed.connect(self._on_document_closed)
        dm.active_document_changed.connect(self._on_active_document_changed)
        dm.unsaved_changes_detected.connect(self._on_unsaved_changes)
        dm.document_saved.connect(self._on_document_saved)

    # ------------------------------------------------------------------ #
    # DocumentManager slots                                               #
    # ------------------------------------------------------------------ #

    @Slot(object)
    def _on_document_opened(self, doc: Document) -> None:
        editor = EditorWidget(document=doc, parent=self._tabs)
        # Wire up status bar + toolbar sync.
        editor.cursor_position_changed.connect(self._status_bar.on_cursor_moved)
        editor.document().contentsChanged.connect(self._status_bar.schedule_refresh)
        # Wire formatting toolbar to this editor.
        editor.cursorPositionChanged.connect(
            lambda: self._fmt_toolbar.set_editor(editor)
            if self._doc_manager.active_document
            and self._editors.get(self._doc_manager.active_document.id) is editor
            else None
        )

        self._editors[doc.id] = editor
        idx = self._tabs.addTab(editor, doc.title)
        self._tabs.setTabToolTip(idx, str(doc.file_path or "New document"))
        self._tabs.setCurrentIndex(idx)

        doc.title_changed.connect(lambda _: self._refresh_tab_title(doc))
        doc.state_changed.connect(lambda _: self._refresh_tab_title(doc))
        log.debug("Tab added: %s", doc.id)

    @Slot(str)
    def _on_document_closed(self, doc_id: str) -> None:
        editor = self._editors.pop(doc_id, None)
        if editor:
            idx = self._tabs.indexOf(editor)
            if idx != -1:
                self._tabs.removeTab(idx)

    @Slot(object)
    def _on_active_document_changed(self, doc: Optional[Document]) -> None:
        if doc is None:
            self._fmt_toolbar.set_editor(None)
            self._status_bar.bind_document(None)
            return
        editor = self._editors.get(doc.id)
        if editor:
            self._tabs.setCurrentWidget(editor)
            self._fmt_toolbar.set_editor(editor)
        self._status_bar.bind_document(doc)
        # Refresh metrics dock.
        self._metrics_widget.bind_editor(editor, doc)

    @Slot(object)
    def _on_unsaved_changes(self, doc: Document) -> None:
        reply = QMessageBox.question(
            self, "Unsaved Changes",
            f"'{doc.title}' has unsaved changes.\n\nSave before closing?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Save:
            if self._save_document(doc):
                self._doc_manager.force_close(doc)
        elif reply == QMessageBox.Discard:
            self._doc_manager.force_close(doc)

    @Slot(object)
    def _on_document_saved(self, doc: Document) -> None:
        self._config.add_recent_file(str(doc.file_path))
        self._populate_recent_menu()

    # ------------------------------------------------------------------ #
    # Tab widget slots                                                    #
    # ------------------------------------------------------------------ #

    @Slot(int)
    def _on_tab_close_requested(self, idx: int) -> None:
        editor = self._tabs.widget(idx)
        for doc in self._doc_manager.documents:
            if self._editors.get(doc.id) is editor:
                self._doc_manager.close_document(doc)
                return

    @Slot(int)
    def _on_tab_changed(self, idx: int) -> None:
        editor = self._tabs.widget(idx)
        for doc in self._doc_manager.documents:
            if self._editors.get(doc.id) is editor:
                self._doc_manager.set_active(doc)
                return

    # ------------------------------------------------------------------ #
    # File menu slots                                                     #
    # ------------------------------------------------------------------ #

    @Slot()
    def _on_new(self) -> None:
        self._doc_manager.new_document()

    @Slot()
    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Document", "",
            "All Supported (*.docx *.md *.txt);;"
            "Word (*.docx);;Markdown (*.md);;Text (*.txt);;All (*)"
        )
        if path:
            self._open_path(Path(path))

    def _open_path(self, path: Path) -> None:
        try:
            self._doc_manager.open_document(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open Failed", str(exc))

    @Slot()
    def _on_save(self) -> None:
        doc = self._doc_manager.active_document
        if doc:
            self._save_document(doc)

    @Slot()
    def _on_save_as(self) -> None:
        doc = self._doc_manager.active_document
        if doc:
            self._save_document_as(doc)

    @Slot()
    def _on_export_pdf(self) -> None:
        doc = self._doc_manager.active_document
        if not doc:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", f"{doc.title}.pdf", "PDF (*.pdf)"
        )
        if path:
            try:
                from prasword.features.filemanagement.file_io import FileIO
                FileIO.export_pdf(doc, Path(path), self)
                QMessageBox.information(self, "Exported", f"PDF saved:\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "Export Failed", str(exc))

    @Slot()
    def _on_close_tab(self) -> None:
        doc = self._doc_manager.active_document
        if doc:
            self._doc_manager.close_document(doc)

    # ------------------------------------------------------------------ #
    # Edit menu slots                                                     #
    # ------------------------------------------------------------------ #

    def _relay(self, method: str):
        def _slot():
            e = self._active_editor()
            if e:
                getattr(e, method)()
        return _slot

    @Slot()
    def _on_find_replace(self) -> None:
        editor = self._active_editor()
        if editor:
            from prasword.gui.dialogs.find_replace_dialog import FindReplaceDialog
            dlg = FindReplaceDialog(editor=editor, parent=self)
            dlg.show()

    # ------------------------------------------------------------------ #
    # View menu slots                                                     #
    # ------------------------------------------------------------------ #

    @Slot()
    def _on_toggle_theme(self) -> None:
        new = ThemeManager.toggle(QApplication.instance())
        self._config.set("appearance/theme", new)

    @Slot(bool)
    def _on_distraction_free(self, enabled: bool) -> None:
        DistractionFreeMode.toggle(self)

    @Slot(bool)
    def _on_toggle_sidebar(self, visible: bool) -> None:
        if hasattr(self, "_sidebar_dock"):
            self._sidebar_dock.setVisible(visible)

    @Slot(bool)
    def _on_toggle_metrics(self, visible: bool) -> None:
        if hasattr(self, "_metrics_dock"):
            self._metrics_dock.setVisible(visible)

    @Slot()
    def _on_zoom_in(self) -> None:
        e = self._active_editor()
        if e:
            e.zoomIn(2)

    @Slot()
    def _on_zoom_out(self) -> None:
        e = self._active_editor()
        if e:
            e.zoomOut(2)

    @Slot()
    def _on_zoom_reset(self) -> None:
        e = self._active_editor()
        if e:
            # Reset font to config default.
            family = self._config.get("appearance/font_family", "Georgia")
            size   = int(self._config.get("appearance/font_size", 11))
            e.setFont(QFont(family, size))

    # ------------------------------------------------------------------ #
    # Insert menu slots                                                   #
    # ------------------------------------------------------------------ #

    @Slot()
    def _on_insert_table(self) -> None:
        from prasword.gui.dialogs.insert_table_dialog import InsertTableDialog
        e = self._active_editor()
        if e:
            InsertTableDialog(editor=e, parent=self).exec()

    @Slot()
    def _on_insert_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Insert Image", "",
            "Images (*.png *.jpg *.jpeg *.gif *.bmp *.svg)"
        )
        if path:
            e = self._active_editor()
            if e:
                e.textCursor().insertImage(path)

    @Slot()
    def _on_insert_code(self) -> None:
        from prasword.features.datascience.code_highlighter import CodeHighlighter
        e = self._active_editor()
        if e:
            CodeHighlighter.insert_code_block(e)

    @Slot()
    def _on_insert_math(self) -> None:
        from prasword.gui.dialogs.math_dialog import MathDialog
        e = self._active_editor()
        if e:
            dlg = MathDialog(parent=self)
            if dlg.exec():
                latex = dlg.latex_text()
                if latex:
                    from prasword.features.datascience.math_renderer import MathRenderer
                    MathRenderer.insert_rendered(e, latex)

    @Slot()
    def _on_insert_citation(self) -> None:
        doc = self._doc_manager.active_document
        e   = self._active_editor()
        if doc and e:
            from prasword.gui.dialogs.citation_dialog import CitationDialog
            CitationDialog(document=doc, editor=e, parent=self).exec()

    @Slot()
    def _on_insert_toc(self) -> None:
        doc = self._doc_manager.active_document
        e   = self._active_editor()
        if doc and e:
            from prasword.features.layout.toc_generator import TocGenerator
            TocGenerator.insert(e, doc)

    @Slot()
    def _on_page_break(self) -> None:
        e = self._active_editor()
        if e:
            e.textCursor().insertText("\u000C")

    # ------------------------------------------------------------------ #
    # Format menu slots                                                   #
    # ------------------------------------------------------------------ #

    def _fmt_action(self, method: str):
        """Return a slot that calls FormattingEngine.<method>(editor)."""
        def _slot(checked: bool = False):
            e = self._active_editor()
            if e:
                from prasword.features.formatting.formatting_engine import FormattingEngine
                getattr(FormattingEngine, method)(e)
        return _slot

    @Slot(bool)
    def _on_bold(self, checked: bool) -> None:
        e = self._active_editor()
        if e:
            from prasword.features.formatting.formatting_engine import FormattingEngine
            FormattingEngine.toggle_bold(e)

    @Slot(bool)
    def _on_italic(self, checked: bool) -> None:
        e = self._active_editor()
        if e:
            from prasword.features.formatting.formatting_engine import FormattingEngine
            FormattingEngine.toggle_italic(e)

    @Slot(bool)
    def _on_underline(self, checked: bool) -> None:
        e = self._active_editor()
        if e:
            from prasword.features.formatting.formatting_engine import FormattingEngine
            FormattingEngine.toggle_underline(e)

    @Slot(bool)
    def _on_strikethrough(self, checked: bool) -> None:
        e = self._active_editor()
        if e:
            from prasword.features.formatting.formatting_engine import FormattingEngine
            FormattingEngine.toggle_strikethrough(e)

    @Slot(bool)
    def _on_subscript(self, checked: bool) -> None:
        e = self._active_editor()
        if e:
            from prasword.features.formatting.formatting_engine import FormattingEngine
            FormattingEngine.toggle_subscript(e)

    @Slot(bool)
    def _on_superscript(self, checked: bool) -> None:
        e = self._active_editor()
        if e:
            from prasword.features.formatting.formatting_engine import FormattingEngine
            FormattingEngine.toggle_superscript(e)

    def _on_heading(self, level: int) -> None:
        e = self._active_editor()
        if e:
            from prasword.features.formatting.formatting_engine import FormattingEngine
            FormattingEngine.apply_heading(e, level)

    @Slot()
    def _on_clear_fmt(self) -> None:
        e = self._active_editor()
        if e:
            from prasword.features.formatting.formatting_engine import FormattingEngine
            FormattingEngine.clear_character_formatting(e)

    # ------------------------------------------------------------------ #
    # Tools menu slots                                                    #
    # ------------------------------------------------------------------ #

    @Slot()
    def _on_word_count_dialog(self) -> None:
        doc = self._doc_manager.active_document
        if not doc:
            return
        from prasword.features.metrics.metrics_engine import MetricsEngine
        m = MetricsEngine.compute(doc)
        QMessageBox.information(self, "Document Metrics", m.to_detail_text())

    @Slot()
    def _on_import_bibtex(self) -> None:
        doc = self._doc_manager.active_document
        if not doc:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import BibTeX", "", "BibTeX (*.bib)"
        )
        if path:
            try:
                from prasword.features.academic.bibtex_manager import BibTeXManager
                n = BibTeXManager.import_file(doc, Path(path))
                QMessageBox.information(
                    self, "BibTeX Import",
                    f"Imported {n} entr{'y' if n == 1 else 'ies'}."
                )
            except Exception as exc:
                QMessageBox.critical(self, "Import Failed", str(exc))

    @Slot()
    def _on_generate_bib(self) -> None:
        doc = self._doc_manager.active_document
        e   = self._active_editor()
        if doc and e:
            from prasword.features.academic.citation_engine import CitationEngine
            CitationEngine.insert_bibliography(e, doc)

    @Slot()
    def _on_git_commit(self) -> None:
        doc = self._doc_manager.active_document
        if doc:
            from prasword.gui.dialogs.git_dialog import GitCommitDialog
            GitCommitDialog(document=doc, parent=self).exec()

    @Slot()
    def _on_page_numbers(self) -> None:
        """Show a simple page-number configuration dialog."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QComboBox, QCheckBox, QPushButton
        dlg = QDialog(self)
        dlg.setWindowTitle("Page Numbers")
        dlg.setMinimumWidth(320)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Style:"))
        combo = QComboBox()
        combo.addItems(["arabic", "roman_lower", "roman_upper", "alpha_lower", "alpha_upper"])
        lay.addWidget(combo)
        chk_total = QCheckBox("Show total (Page N of M)")
        lay.addWidget(chk_total)
        btn = QPushButton("Install Overlay")
        def _install():
            from prasword.features.layout.page_numbering import PageOverlay, NumberingConfig
            e = self._active_editor()
            if e:
                cfg = NumberingConfig(style=combo.currentText(), show_total=chk_total.isChecked())
                overlay = PageOverlay(e, cfg)
                overlay.install()
            dlg.accept()
        btn.clicked.connect(_install)
        lay.addWidget(btn)
        dlg.exec()

    @Slot()
    def _on_preferences(self) -> None:
        from prasword.gui.dialogs.preferences_dialog import PreferencesDialog
        PreferencesDialog(config=self._config, parent=self).exec()

    @Slot()
    def _on_about(self) -> None:
        QMessageBox.about(
            self, "About PrasWord",
            "<h2>PrasWord</h2>"
            "<p>Professional word processor for academic and data science workflows.</p>"
            "<p><b>Version:</b> 0.1.0 &nbsp;|&nbsp; "
            "<b>Framework:</b> PySide6 (Qt 6) &nbsp;|&nbsp; "
            "<b>License:</b> MIT</p>"
        )

    # ------------------------------------------------------------------ #
    # Close event                                                         #
    # ------------------------------------------------------------------ #

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._doc_manager.request_quit():
            event.ignore()
        else:
            self._auto_save_timer.stop()
            event.accept()

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _active_editor(self) -> Optional[EditorWidget]:
        doc = self._doc_manager.active_document
        return self._editors.get(doc.id) if doc else None

    def _save_document(self, doc: Document) -> bool:
        if doc.file_path is None:
            return self._save_document_as(doc)
        return self._doc_manager.save_document(doc)

    def _save_document_as(self, doc: Document) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Document As", doc.title,
            "Word (*.docx);;Markdown (*.md);;Text (*.txt);;All (*)"
        )
        return bool(path and self._doc_manager.save_document(doc, Path(path)))

    def _refresh_tab_title(self, doc: Document) -> None:
        editor = self._editors.get(doc.id)
        if not editor:
            return
        idx = self._tabs.indexOf(editor)
        if idx == -1:
            return
        title = doc.title + (" ●" if doc.is_modified else "")
        self._tabs.setTabText(idx, title)

    def _populate_recent_menu(self) -> None:
        self._recent_menu.clear()
        recent = self._config.get_recent_files()
        if not recent:
            a = QAction("(No recent files)", self)
            a.setEnabled(False)
            self._recent_menu.addAction(a)
            return
        for p in recent:
            a = QAction(p, self)
            a.triggered.connect(lambda _, path=p: self._open_path(Path(path)))
            self._recent_menu.addAction(a)

    def _auto_save_all(self) -> None:
        if not self._config.get("editor/auto_save", True):
            return
        for doc in self._doc_manager.documents:
            if doc.is_modified and doc.file_path:
                self._doc_manager.save_document(doc)

    def _restart_auto_save_timer(self) -> None:
        secs = int(self._config.get("editor/auto_save_interval_seconds", 60))
        self._auto_save_timer.start(secs * 1_000)
