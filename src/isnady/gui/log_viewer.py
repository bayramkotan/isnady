"""Help → Log (LOG1): isnady's log in a window of its own, as VenvStudio has it — the file (isnady.log, its older
parts, the crash reports), followed live, only errors or a text, larger or smaller, copied, its folder opened,
what is older than a day removed.

Bayram (2026-10-25): "isnady icin bir log sistemi ---> venvstudio daki gibi!!!!"
"""

from __future__ import annotations

import time

from PySide6.QtCore import QDate, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QGuiApplication, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from isnady.core import log
from isnady.core.i18n import tr


class LogViewer(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("isnady log"))
        self.setWindowFlags(Qt.WindowType.Window)      # its own window: minimised and moved on its own
        self.resize(1100, 720)
        self._size = 10
        self._shown_size = -1

        box = QVBoxLayout(self)
        box.setSpacing(8)
        top = QHBoxLayout()
        self.file = QComboBox()
        self.file.setMinimumWidth(320)
        self.file.currentIndexChanged.connect(lambda _i: self._load(force=True))
        self.level = QComboBox()
        for key, text in (("", tr("Everything")), ("warning", tr("Warnings and errors")), ("error", tr("Errors only"))):
            self.level.addItem(text, key)
        self.level.currentIndexChanged.connect(lambda _i: self._load(force=True))
        self.find = QLineEdit()
        self.find.setPlaceholderText(tr("Only lines holding…"))
        self.find.setClearButtonEnabled(True)
        self.find.textChanged.connect(lambda _t: self._load(force=True))
        self.follow = QCheckBox(tr("Follow"))
        self.follow.setChecked(True)
        self.follow.setToolTip(tr("Read the log again every two seconds and keep the newest line in view"))
        smaller, larger = QPushButton("A−"), QPushButton("A+")
        for b in (smaller, larger):
            b.setObjectName("Quiet")
            b.setMinimumWidth(52)
        smaller.clicked.connect(lambda: self._zoom(-1))
        larger.clicked.connect(lambda: self._zoom(+1))
        top.addWidget(QLabel(tr("File")))
        top.addWidget(self.file, 1)
        top.addWidget(self.level)
        top.addWidget(self.find, 1)
        top.addWidget(self.follow)
        top.addWidget(smaller)
        top.addWidget(larger)
        box.addLayout(top)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(self._size)
        self.text.setFont(mono)
        box.addWidget(self.text, 1)

        self.info = QLabel("")
        self.info.setObjectName("Caption")
        box.addWidget(self.info)
        bottom = QHBoxLayout()
        copy = QPushButton(tr("Copy all"))
        folder = QPushButton(tr("Open the folder"))
        self.before = QDateEdit(QDate.currentDate().addDays(-7))
        self.before.setCalendarPopup(True)
        self.before.setDisplayFormat("yyyy-MM-dd")
        older = QPushButton(tr("Delete what is older"))
        clear = QPushButton(tr("Clear the log"))
        close = QPushButton(tr("Close"))
        for b in (copy, folder, older, clear, close):
            b.setObjectName("Quiet")
        copy.clicked.connect(self._copy)
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(log.open_folder_path())))
        older.clicked.connect(self._delete_older)
        clear.clicked.connect(self._clear)
        close.clicked.connect(self.close)
        bottom.addWidget(copy)
        bottom.addWidget(folder)
        bottom.addStretch(1)
        bottom.addWidget(QLabel(tr("Before")))
        bottom.addWidget(self.before)
        bottom.addWidget(older)
        bottom.addWidget(clear)
        bottom.addWidget(close)
        box.addLayout(bottom)

        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(lambda: self.follow.isChecked() and self._load())
        self._timer.start()
        self._fill_files()

    # ------------------------------------------------------------------ the files
    def _fill_files(self) -> None:
        current = self.file.currentData()
        self.file.blockSignals(True)
        self.file.clear()
        for f in log.files() or [log.path()]:
            if f.exists():
                stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))
                size = f"{f.stat().st_size / 1024:,.0f} KB"
            else:
                stamp, size = "", ""
            kind = tr("crash report") if f.name.startswith("crash_") else tr("log")
            self.file.addItem(f"{f.name}  ·  {kind}  ·  {stamp}  ·  {size}", str(f))
        if current:
            i = self.file.findData(current)
            if i >= 0:
                self.file.setCurrentIndex(i)
        self.file.blockSignals(False)
        self._load(force=True)

    def _load(self, force: bool = False) -> None:
        from pathlib import Path

        target = Path(self.file.currentData() or log.path())
        try:
            size = target.stat().st_size
        except OSError:
            size = 0
        if not force and size == self._shown_size:
            return
        self._shown_size = size
        bar = self.text.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        body = log.read(target, 0, self.level.currentData() or "", self.find.text().strip())
        self.text.setPlainText(body)
        if self.follow.isChecked() or at_end or force:
            self.text.moveCursor(QTextCursor.MoveOperation.End)
            self.text.moveCursor(QTextCursor.MoveOperation.StartOfLine)    # the newest line in view, from its start
            self.text.horizontalScrollBar().setValue(0)
        lines = body.count("\n") + 1 if body else 0
        self.info.setText(tr("{lines} lines · {path}", lines=f"{lines:,}", path=str(target)))

    def _zoom(self, step: int) -> None:
        self._size = max(7, min(24, self._size + step))
        font = QFont(self.text.font())
        font.setPointSize(self._size)
        self.text.setFont(font)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(log.environment_line() + "\n" + self.text.toPlainText())
        self.info.setText(tr("Copied, with the version and the system at its head."))

    def _delete_older(self) -> None:
        day = self.before.date().toString("yyyy-MM-dd")
        if QMessageBox.question(self, tr("isnady log"), tr("Remove what was logged before {day}?", day=day)) \
                != QMessageBox.StandardButton.Yes:
            return
        n = log.delete_before(day)
        self._fill_files()
        self.info.setText(tr("{n} line(s) before {day} removed.", n=f"{n:,}", day=day))

    def _clear(self) -> None:
        if QMessageBox.question(self, tr("isnady log"), tr("Empty the log and remove the crash reports?")) \
                != QMessageBox.StandardButton.Yes:
            return
        log.clear()
        self._fill_files()
