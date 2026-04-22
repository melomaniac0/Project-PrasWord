"""
prasword.gui.dialogs.git_dialog
================================
Git integration dialog: status, diff, stage, commit, push.

Requires: pip install gitpython

Tabs
----
  Commit   — Stage selected files, write a message, commit.
  Log      — Last 20 commits with hash, author, date, message.
  Diff     — Unified diff of the current document file (if tracked).

The dialog is document-aware: it opens the repo containing the document's
file path. If the file has never been saved it uses the current working dir.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from prasword.core.document import Document

from prasword.utils.logger import get_logger

log = get_logger(__name__)


class GitCommitDialog(QDialog):
    """
    Full Git workflow dialog: commit, log, diff.

    Parameters
    ----------
    document : Document
    parent : QWidget | None
    """

    def __init__(
        self,
        document: "Document",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._repo = None
        self.setWindowTitle("Git Integration")
        self.setMinimumSize(620, 480)
        self.resize(700, 540)
        self._build_ui()
        self._load_repo()

    # ------------------------------------------------------------------ #
    # UI                                                                   #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # ── Repo path banner ──────────────────────────────────────────
        self._repo_label = QLabel("Detecting repository…")
        self._repo_label.setStyleSheet(
            "background: #313244; padding: 6px 10px; border-radius: 4px;"
            "color: #a6adc8; font-size: 9pt;"
        )
        root.addWidget(self._repo_label)

        # ── Tabs ──────────────────────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_commit_tab(), "📝 Commit")
        self._tabs.addTab(self._build_log_tab(),    "📋 Log")
        self._tabs.addTab(self._build_diff_tab(),   "🔀 Diff")
        root.addWidget(self._tabs, 1)

        # ── Bottom buttons ────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("↻ Refresh")
        btn_refresh.clicked.connect(self._load_repo)
        btn_row.addWidget(btn_refresh)
        btn_row.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)
        root.addLayout(btn_row)

    def _build_commit_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(6)

        # Branch / last-commit info
        self._branch_label = QLabel("")
        self._branch_label.setStyleSheet("color: #89b4fa; font-size: 9pt;")
        layout.addWidget(self._branch_label)

        layout.addWidget(QLabel("Changed files  (check to stage):"))
        self._file_list = QListWidget()
        self._file_list.setSelectionMode(QListWidget.NoSelection)
        layout.addWidget(self._file_list, 1)

        layout.addWidget(QLabel("Commit message:"))
        self._msg_edit = QTextEdit()
        self._msg_edit.setPlaceholderText(
            "Short summary (≤ 72 chars)\n\n"
            "Optional longer description…"
        )
        self._msg_edit.setMaximumHeight(100)
        self._msg_edit.setFont(QFont("Courier New", 10))
        layout.addWidget(self._msg_edit)

        # Amend checkbox + push after commit
        opt_row = QHBoxLayout()
        self._chk_amend = QCheckBox("Amend last commit")
        self._chk_push  = QCheckBox("Push after commit")
        opt_row.addWidget(self._chk_amend)
        opt_row.addWidget(self._chk_push)
        opt_row.addStretch()
        layout.addLayout(opt_row)

        self._btn_commit = QPushButton("Commit Staged Files")
        self._btn_commit.setEnabled(False)
        self._btn_commit.clicked.connect(self._commit)
        layout.addWidget(self._btn_commit)

        return w

    def _build_log_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QFont("Courier New", 9))
        self._log_view.setStyleSheet(
            "background: #11111b; color: #cdd6f4; border: none;"
        )
        layout.addWidget(self._log_view)
        return w

    def _build_diff_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Diff of current document file vs HEAD:"))
        self._diff_view = QTextEdit()
        self._diff_view.setReadOnly(True)
        self._diff_view.setFont(QFont("Courier New", 9))
        self._diff_view.setStyleSheet(
            "background: #11111b; color: #cdd6f4; border: none;"
        )
        layout.addWidget(self._diff_view)
        return w

    # ------------------------------------------------------------------ #
    # Repo loading                                                         #
    # ------------------------------------------------------------------ #

    def _load_repo(self) -> None:
        try:
            import git as gitmodule
        except ImportError:
            self._repo_label.setText(
                "⚠  gitpython not installed.  Run:  pip install gitpython"
            )
            self._btn_commit.setEnabled(False)
            return

        start = (
            self._document.file_path.parent
            if self._document.file_path and self._document.file_path.exists()
            else Path.cwd()
        )

        try:
            self._repo = gitmodule.Repo(start, search_parent_directories=True)
        except gitmodule.InvalidGitRepositoryError:
            self._repo_label.setText(
                f"⚠  No git repository found from:  {start}\n"
                "   Run  git init  in your project folder."
            )
            self._btn_commit.setEnabled(False)
            return
        except Exception as exc:
            self._repo_label.setText(f"⚠  Git error: {exc}")
            self._btn_commit.setEnabled(False)
            return

        self._btn_commit.setEnabled(True)
        self._refresh_all()

    def _refresh_all(self) -> None:
        self._refresh_status()
        self._refresh_log()
        self._refresh_diff()

    def _refresh_status(self) -> None:
        if not self._repo:
            return

        try:
            branch = self._repo.active_branch.name
        except TypeError:
            branch = "(detached HEAD)"

        try:
            last_msg = self._repo.head.commit.message.strip().splitlines()[0][:70]
            last_hash = self._repo.head.commit.hexsha[:8]
            self._branch_label.setText(
                f"Branch: {branch}   |   HEAD: {last_hash}  {last_msg}"
            )
        except Exception:
            self._branch_label.setText(f"Branch: {branch}")

        self._repo_label.setText(f"Repository: {self._repo.working_dir}")

        self._file_list.clear()

        # Staged (index vs HEAD)
        try:
            staged = [d.a_path for d in self._repo.index.diff("HEAD")]
        except Exception:
            staged = [d.a_path for d in self._repo.index.diff(None)]

        # Unstaged (working tree vs index)
        unstaged = [d.a_path for d in self._repo.index.diff(None)]
        untracked = list(self._repo.untracked_files)

        def _add_item(label: str, path: str, checked: bool, colour: str) -> None:
            item = QListWidgetItem()
            chk = QCheckBox(f"{label}  {path}")
            chk.setChecked(checked)
            chk.setStyleSheet(f"color: {colour};")
            item.setData(Qt.UserRole, (path, chk))
            item.setSizeHint(chk.sizeHint())
            self._file_list.addItem(item)
            self._file_list.setItemWidget(item, chk)

        for p in staged:
            _add_item("[staged]   ", p, True,  "#a6e3a1")
        for p in unstaged:
            if p not in staged:
                _add_item("[modified] ", p, False, "#f9e2af")
        for p in untracked:
            _add_item("[untracked]", p, False, "#cba6f7")

        if not (staged or unstaged or untracked):
            item = QListWidgetItem("✓  Working tree is clean.")
            item.setForeground(QColor("#a6adc8"))
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self._file_list.addItem(item)

    def _refresh_log(self) -> None:
        if not self._repo:
            return
        try:
            lines = []
            for commit in self._repo.iter_commits(max_count=25):
                dt = commit.authored_datetime.strftime("%Y-%m-%d %H:%M")
                msg = commit.message.strip().splitlines()[0][:65]
                lines.append(
                    f"<span style='color:#89b4fa'>{commit.hexsha[:8]}</span>  "
                    f"<span style='color:#f9e2af'>{dt}</span>  "
                    f"<span style='color:#a6adc8'>{commit.author.name}</span><br/>"
                    f"<span style='color:#cdd6f4;margin-left:20px'>&nbsp;&nbsp;{msg}</span>"
                    f"<br/><br/>"
                )
            self._log_view.setHtml("".join(lines) if lines else "<i>No commits yet.</i>")
        except Exception as exc:
            self._log_view.setPlainText(f"Could not read log: {exc}")

    def _refresh_diff(self) -> None:
        if not self._repo or not self._document.file_path:
            self._diff_view.setPlainText("(save the document first to see its diff)")
            return
        try:
            rel = Path(self._document.file_path).relative_to(self._repo.working_dir)
            diff = self._repo.git.diff("HEAD", "--", str(rel))
            if not diff:
                diff = self._repo.git.diff("--", str(rel))
            if not diff:
                self._diff_view.setPlainText("No changes relative to HEAD.")
                return
            # Colour the diff
            html_lines = []
            for line in diff.splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    html_lines.append(f"<span style='color:#a6e3a1'>{line}</span>")
                elif line.startswith("-") and not line.startswith("---"):
                    html_lines.append(f"<span style='color:#f38ba8'>{line}</span>")
                elif line.startswith("@@"):
                    html_lines.append(f"<span style='color:#89b4fa'>{line}</span>")
                else:
                    html_lines.append(f"<span style='color:#a6adc8'>{line}</span>")
            self._diff_view.setHtml("<br/>".join(html_lines))
        except Exception as exc:
            self._diff_view.setPlainText(f"Diff unavailable: {exc}")

    # ------------------------------------------------------------------ #
    # Commit                                                               #
    # ------------------------------------------------------------------ #

    @Slot()
    def _commit(self) -> None:
        if not self._repo:
            return
        msg = self._msg_edit.toPlainText().strip()
        if not msg:
            QMessageBox.warning(self, "No Message", "Please enter a commit message.")
            return

        # Collect checked paths to stage
        paths_to_stage: list[str] = []
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            data = item.data(Qt.UserRole)
            if data:
                path_str, chk_widget = data
                w = self._file_list.itemWidget(item)
                if w and w.isChecked():
                    paths_to_stage.append(path_str)

        if not paths_to_stage and not self._chk_amend.isChecked():
            QMessageBox.warning(
                self, "Nothing Staged",
                "Check at least one file to stage before committing."
            )
            return

        try:
            if paths_to_stage:
                self._repo.index.add(paths_to_stage)

            amend = self._chk_amend.isChecked()
            if amend:
                self._repo.git.commit("--amend", "-m", msg)
            else:
                self._repo.index.commit(msg)

            if self._chk_push.isChecked():
                origin = self._repo.remotes.origin
                origin.push()

            short = msg.splitlines()[0][:50]
            QMessageBox.information(
                self, "Committed",
                f"Successfully committed:\n{short}"
                + ("\n\nPushed to origin." if self._chk_push.isChecked() else "")
            )
            self._msg_edit.clear()
            self._chk_amend.setChecked(False)
            self._refresh_all()
            log.info("Git commit: %s", short)
        except Exception as exc:
            QMessageBox.critical(self, "Commit Failed", str(exc))
            log.exception("Git commit failed.")
