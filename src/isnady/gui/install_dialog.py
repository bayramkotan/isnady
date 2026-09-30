"""Help → Check Installation: the same report as `iy doctor`, in the window."""

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from isnady import doctor

_LIVE: set = set()      # keep the thread until Qt says it finished (see sources_page._LIVE_WORKERS)


class _Check(QThread):
    done = Signal(object)

    def run(self) -> None:
        self.done.emit(doctor.diagnose(check_pypi=True))


class InstallDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Check Installation")
        self.resize(820, 560)
        self.summary = QLabel("Looking for every copy of isnady on this computer…")
        self.summary.setObjectName("Lead")
        self.summary.setWordWrap(True)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        mono = QFont("monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(mono)
        note = QLabel("To repair, run in a terminal:  iy doctor --fix      If an old copy starts instead of this "
                      f"one:  {doctor.RESCUE}")
        note.setObjectName("Caption")
        note.setWordWrap(True)
        copy = QPushButton("Copy report")
        copy.setObjectName("Quiet")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.text.toPlainText()))
        close = QPushButton("Close")
        close.setObjectName("Primary")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(copy)
        row.addWidget(close)
        box = QVBoxLayout(self)
        box.setContentsMargins(22, 18, 22, 16)
        box.addWidget(self.summary)
        box.addWidget(self.text, 1)
        box.addWidget(note)
        box.addLayout(row)
        worker = _Check()
        _LIVE.add(worker)
        worker.finished.connect(lambda w=worker: (_LIVE.discard(w), w.deleteLater()))
        worker.done.connect(self._show)
        worker.start()

    def _show(self, report) -> None:
        self.text.setPlainText(doctor.as_text(report))
        if report.problems:
            self.summary.setText(f"{len(report.problems)} problem(s) found; see below. The fix commands are listed "
                                 "at the end of the report.")
        else:
            latest = f" The latest on PyPI is {report.latest}." if report.latest else ""
            commands = ("every isnady command on PATH starts it." if report.commands else
                        "no isnady command was found on PATH (started from a virtual environment or a shortcut?).")
            self.summary.setText(f"One installation, isnady {report.running_version}; {commands}" + latest)
