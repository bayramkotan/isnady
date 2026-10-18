"""Help → Check for Updates (UPD4): isnady on PyPI and on npm, whichever are installed here; both offered together
when both are behind, each with its own tick. What is new is read from the CHANGELOG. The update itself is
isnady.doctor's (every copy where it is installed; the system's administrator prompt when one needs it)."""

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout)

from isnady import doctor
from isnady.core import updates
from isnady.core.i18n import tr

_LIVE: set = set()


class _Check(QThread):
    done = Signal(object)

    def run(self) -> None:
        try:
            self.done.emit(updates.check())
        except Exception as exc:         # the dialog never waits for ever
            self.done.emit({"error": str(exc)})


class _Update(QThread):
    line = Signal(str)
    done = Signal(object)

    def __init__(self, pypi: bool, npm: bool) -> None:
        super().__init__()
        self.pypi, self.npm = pypi, npm

    def run(self) -> None:
        try:
            plan = updates.plan(self.pypi, self.npm)
            results = doctor.run_plan(plan, self.line.emit, window=True) if plan else []
        except Exception as exc:
            self.line.emit(str(exc))
            results = [([], -1)]
        self.done.emit(results)


class UpdateDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Check for Updates"))
        self.resize(760, 520)
        self.summary = QLabel(tr("Asking PyPI and npm for the latest isnady…"))
        self.summary.setObjectName("Lead")
        self.summary.setWordWrap(True)
        self.pypi = QCheckBox()
        self.npm = QCheckBox()
        for box in (self.pypi, self.npm):
            box.hide()
            box.toggled.connect(self._enable)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.update_button = QPushButton(tr("Update"))
        self.update_button.setObjectName("Primary")
        self.update_button.clicked.connect(self._update)
        self.update_button.hide()
        self.close_button = QPushButton(tr("Close"))
        self.close_button.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.update_button)
        row.addWidget(self.close_button)
        box = QVBoxLayout(self)
        box.setContentsMargins(22, 18, 22, 16)
        box.addWidget(self.summary)
        box.addWidget(self.pypi)
        box.addWidget(self.npm)
        box.addWidget(self.text, 1)
        note = QLabel(tr("The same in a terminal: iy update --check, iy update (add --npm for the npm package)."))
        note.setObjectName("Caption")
        box.addWidget(note)
        box.addLayout(row)
        self._start(_Check(), self._show)

    def _start(self, worker: QThread, slot) -> None:
        _LIVE.add(worker)
        worker.finished.connect(lambda w=worker: (_LIVE.discard(w), w.deleteLater()))
        worker.done.connect(slot)
        worker.start()

    def _enable(self, *_a) -> None:
        self.update_button.setEnabled(self.pypi.isChecked() or self.npm.isChecked())

    def _show(self, found: dict) -> None:
        if "error" in found:
            self.summary.setText(found["error"])
            return
        p, n = found["pypi"], found["npm"]
        lines = []
        if p["latest"] is None:
            lines.append(tr("PyPI could not be reached (no internet?). Installed: isnady {v}.", v=p["installed"]))
        self.pypi.setText(tr("Python package (PyPI): {have} → {latest}", have=p["installed"], latest=p["latest"] or "?"))
        self.pypi.setVisible(p["behind"])
        self.pypi.setChecked(p["behind"])
        if n["installed"]:
            self.npm.setText(tr("npm package: {have} → {latest}", have=n["installed"], latest=n["latest"] or "?"))
            self.npm.setVisible(n["behind"])
            self.npm.setChecked(n["behind"])
        behind = p["behind"] or n["behind"]
        if behind:
            names = [x for x, b in ((tr("PyPI"), p["behind"]), (tr("npm"), n["behind"])) if b]
            self.summary.setText(tr("A newer isnady is out ({where}). Tick what to update:", where=", ".join(names)))
        elif p["latest"]:
            installed = tr("isnady {v} is up to date", v=p["installed"])
            if n["installed"]:
                installed += " " + tr("(PyPI and npm).")
            else:
                installed += ". " + tr("isnady is not installed with npm here.")
            self.summary.setText(installed)
        for version, text in found["news"]:
            lines.append(tr("What is new in {version}:", version=version) + "\n" + text + "\n")
        self.text.setPlainText("\n".join(lines))
        self.update_button.setVisible(behind)
        self._enable()

    def _update(self) -> None:
        self.update_button.setEnabled(False)
        self.close_button.setEnabled(False)
        self.text.setPlainText("")
        self.summary.setText(tr("Updating…"))
        worker = _Update(self.pypi.isChecked(), self.npm.isChecked())
        worker.line.connect(self.text.appendPlainText)
        self._start(worker, self._updated)

    def _updated(self, results) -> None:
        self.close_button.setEnabled(True)
        failed = [argv for argv, code in results if code != 0]
        self.summary.setText(tr("{failed} of {total} update command(s) did not succeed; the output is below.",
                                failed=len(failed), total=len(results)) if failed else
                             tr("Updated. Close isnady and open it again to use the new version."))
