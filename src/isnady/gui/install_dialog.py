"""Help → Check Installation: the same report as `iy doctor`, in the window — and the same update as
`iy update`, one click away: every copy updated where it is, the administrator prompt of the system when a copy
needs it (pkexec on Linux, the Windows prompt), the output shown as it comes."""

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from isnady import doctor
from isnady.core.i18n import tr

_LIVE: set = set()      # keep the thread until Qt says it finished (see sources_page._LIVE_WORKERS)


class _Check(QThread):
    done = Signal(object)

    def run(self) -> None:
        self.done.emit(doctor.diagnose(check_pypi=True))


class _Update(QThread):
    line = Signal(str)
    done = Signal(object, object)          # results, the report after updating

    def __init__(self, plan: list[list[str]]) -> None:
        super().__init__()
        self.plan = plan

    def run(self) -> None:
        results = doctor.run_plan(self.plan, self.line.emit, window=True)
        self.done.emit(results, doctor.diagnose(check_pypi=True))


class InstallDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Check Installation"))
        self.resize(820, 560)
        self.report = None
        self.summary = QLabel(tr("Looking for every copy of isnady on this computer…"))
        self.summary.setObjectName("Lead")
        self.summary.setWordWrap(True)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        mono = QFont("monospace")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(mono)
        self.note = QLabel(tr("Update updates every copy where it is installed; nothing is removed. A copy installed for "
                              "all users asks for the administrator password. The same in a terminal: iy update  "
                              "— if an old copy starts even for that: {rescue}", rescue=doctor.RESCUE))
        self.note.setObjectName("Caption")
        self.note.setWordWrap(True)
        copy = QPushButton(tr("Copy report"))
        copy.setObjectName("Quiet")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.text.toPlainText()))
        self.update_button = QPushButton(tr("Update"))
        self.update_button.setObjectName("Primary")
        self.update_button.setToolTip(tr("Run the update commands shown in the report, one after the other"))
        self.update_button.clicked.connect(self._update)
        self.update_button.hide()
        self.close_button = QPushButton(tr("Close"))
        self.close_button.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(copy)
        row.addWidget(self.update_button)
        row.addWidget(self.close_button)
        box = QVBoxLayout(self)
        box.setContentsMargins(22, 18, 22, 16)
        box.addWidget(self.summary)
        box.addWidget(self.text, 1)
        box.addWidget(self.note)
        box.addLayout(row)
        worker = _Check()
        self._start(worker)
        worker.done.connect(self._show)

    def _start(self, worker: QThread) -> None:
        _LIVE.add(worker)
        worker.finished.connect(lambda w=worker: (_LIVE.discard(w), w.deleteLater()))
        worker.start()

    def _show(self, report) -> None:
        self.report = report
        self.text.setPlainText(doctor.as_text(report))
        self.update_button.setVisible(bool(report.fixes and report.problems))
        self.update_button.setEnabled(True)
        if report.problems:
            self.summary.setText(tr("{problems} thing(s) to update; see below. Update brings every copy up to date where "
                                    "it is installed.", problems=len(report.problems)))
        else:
            latest = " " + tr("The latest on PyPI is {latest}.", latest=report.latest) if report.latest else ""
            commands = (tr("every isnady command on PATH starts it.") if report.commands else
                        tr("no isnady command was found on PATH (started from a virtual environment or a shortcut?)."))
            self.summary.setText(tr("One installation, isnady {version}; {commands}", version=report.running_version,
                                    commands=commands) + latest)

    def _update(self) -> None:
        if not self.report or not self.report.fixes:
            return
        self.update_button.setEnabled(False)
        self.close_button.setEnabled(False)
        self.summary.setText(tr("Updating every copy of isnady where it is installed…"))
        self.text.setPlainText("")
        worker = _Update(self.report.fixes)
        worker.line.connect(self.text.appendPlainText)
        worker.done.connect(self._updated)
        self._start(worker)

    def _updated(self, results, after) -> None:
        self.close_button.setEnabled(True)
        log = self.text.toPlainText()
        self.report = after
        failed = [argv for argv, code in results if code != 0]
        self.text.setPlainText(log + "\n\n" + "—" * 40 + "\n" + doctor.as_text(after))
        self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())
        self.update_button.setVisible(bool(after.fixes and after.problems))
        self.update_button.setEnabled(True)
        note = doctor.lag_note(after)
        if note:
            self.text.appendPlainText("\n" + note)
        if failed:
            self.summary.setText(tr("{failed} of {total} update command(s) did not succeed; the output is below.",
                                    failed=len(failed), total=len(results)))
        elif note:
            self.summary.setText(note)
        elif after.problems:
            self.summary.setText(tr("Updated; {problems} thing(s) still to look at, see below.",
                                    problems=len(after.problems)))
        else:
            self.summary.setText(tr("Every copy is up to date. Close isnady and open it again to use the new version."))
