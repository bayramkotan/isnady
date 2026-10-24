"""Long work beside the window (EX3): an export of a whole library runs in a thread of its own, with a progress bar,
the time gone and the time left, and a Stop button — in the bar at the bottom of the window, so the window stays
usable and the Export dialog can be closed while it runs.

Bayram (2026-10-24): "export kisminda epub olarak hepsini tum dilleri ile export etmesini istedim. cok cok uzuyor
ama en azindan ayri bir threat olabilir, bunun disinda progress bar da olabilir."
"""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QWidget

from isnady.core import transfer as T
from isnady.core.i18n import tr


def _clock(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds < 60:
        return tr("{s} s", s=seconds)
    if seconds < 3600:
        return tr("{m} min {s} s", m=seconds // 60, s=seconds % 60)
    return tr("{h} h {m} min", h=seconds // 3600, m=seconds % 3600 // 60)


class Job(QThread):
    """work(conn, say, tick) in a thread with a connection of its own. tick(done, total) moves the bar; after Stop the
    next tick raises transfer.Cancelled, and the work removes its half-written file."""

    progress = Signal(str)
    ticked = Signal(int, int)
    done = Signal(bool, str)

    def __init__(self, work, title: str = "") -> None:
        super().__init__()
        self._work = work
        self.title = title
        self._stop = False
        self.started_at = time.monotonic()
        self.cancelled = False

    def stop(self) -> None:
        self._stop = True

    def _tick(self, done: int, total: int) -> None:
        if self._stop:
            raise T.Cancelled(tr("Stopped."))
        self.ticked.emit(done, total)

    def run(self) -> None:
        from isnady.data import db

        self.started_at = time.monotonic()
        conn = db.connect()
        try:
            result = self._work(conn, self.progress.emit, self._tick)
            self.done.emit(True, str(result))
        except T.Cancelled as exc:
            self.cancelled = True
            self.done.emit(False, str(exc))
        except (T.TransferError, OSError, ValueError, KeyError) as exc:
            self.done.emit(False, str(exc))
        except Exception as exc:          # anything else: said, never a crash of the window
            self.done.emit(False, f"{type(exc).__name__}: {exc}")
        finally:
            conn.close()


def describe(job: Job, done: int, total: int) -> tuple[int, str]:
    """(percent, "12,345 / 99,567 · 1 min 20 s gone · about 3 min left")."""
    percent = int(done * 100 / total) if total else 0
    gone = time.monotonic() - job.started_at
    text = f"{done:,} / {total:,} · " + tr("{t} gone", t=_clock(gone))
    if 0 < done < total and gone > 3:
        text += " · " + tr("about {t} left", t=_clock(gone * (total - done) / done))
    return percent, text


class JobRow(QWidget):
    """One job in the bottom bar: what, the bar, the time, Stop; when it ends, where the file is."""

    def __init__(self, job: Job, on_finished) -> None:
        super().__init__()
        self.job = job
        self._on_finished = on_finished
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 2, 8, 2)
        row.setSpacing(10)
        self.title = QLabel(job.title)
        self.title.setObjectName("FilterLabel")
        self.message = QLabel(tr("Starting…"))
        self.message.setObjectName("Caption")
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)                       # busy until the first tick says how many
        self.bar.setMinimumWidth(180)
        self.bar.setMaximumWidth(260)
        self.bar.setFormat("%p%")
        self.stop_button = QPushButton(tr("Stop"))
        self.stop_button.setObjectName("Quiet")
        self.stop_button.clicked.connect(self._stop)
        self.show_button = QPushButton(tr("Show in folder"))
        self.show_button.setObjectName("Quiet")
        self.show_button.hide()
        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("Quiet")
        self.close_button.setToolTip(tr("Close"))
        self.close_button.clicked.connect(lambda: self._on_finished(self))
        self.close_button.hide()
        row.addWidget(self.title)
        row.addWidget(self.bar)
        row.addWidget(self.message, 1)
        row.addWidget(self.stop_button)
        row.addWidget(self.show_button)
        row.addWidget(self.close_button)
        job.progress.connect(self._said)
        job.ticked.connect(self._ticked)
        job.done.connect(self._done)
        self._last = ""

    def _said(self, message: str) -> None:
        self._last = message
        if self.bar.maximum() == 0:
            self.message.setText(message)

    def _ticked(self, done: int, total: int) -> None:
        if total <= 0:
            return
        if self.bar.maximum() != total:
            self.bar.setRange(0, total)
        self.bar.setValue(done)
        _percent, text = describe(self.job, done, total)
        book = self._last.split(" · ")[0] if self._last else ""
        self.message.setText((book + " · " if book else "") + text)

    def _stop(self) -> None:
        self.job.stop()
        self.stop_button.setEnabled(False)
        self.message.setText(tr("Stopping…"))

    def _done(self, ok: bool, message: str) -> None:
        self.stop_button.hide()
        self.bar.hide()
        self.close_button.show()
        gone = _clock(time.monotonic() - self.job.started_at)
        if ok:
            self.message.setText(tr("Written in {t}: {path}", t=gone, path=message))
            where = Path(message)
            self.show_button.show()
            self.show_button.clicked.connect(lambda: QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(where if where.is_dir() else where.parent))))
        elif self.job.cancelled:
            self.message.setText(tr("Stopped; the unfinished file was removed."))
        else:
            self.message.setText(tr("Failed: ") + message)
        QTimer.singleShot(120000, lambda: self._on_finished(self))


class Jobs:
    """The jobs of the window, each a row in the bottom bar (shown while there is one)."""

    def __init__(self, window) -> None:
        self._window = window
        self._rows: list[JobRow] = []

    def start(self, work, title: str) -> Job:
        job = Job(work, title)
        row = JobRow(job, self._remove)
        self._rows.append(row)
        bar = self._window.statusBar()
        bar.addWidget(row, 1)
        row.show()
        bar.show()
        job.start()
        return job

    def running(self) -> list[Job]:
        return [r.job for r in self._rows if r.job.isRunning()]

    def stop_all(self, wait_ms: int = 15000) -> None:
        for job in self.running():
            job.stop()
        for job in self.running():
            job.wait(wait_ms)

    def _remove(self, row: JobRow) -> None:
        if row not in self._rows or row.job.isRunning():
            return
        self._rows.remove(row)
        self._window.statusBar().removeWidget(row)
        row.deleteLater()
        importing = getattr(self._window, "_import_bar", None)
        if not self._rows and not (importing is not None and importing.isVisible()):
            self._window.statusBar().hide()
