"""Going through a book by its hadith numbers (NAV3): the number field, the last number beside it, the first /
previous / next / last buttons and where the hadith stands among all of the book's. One widget, on Isnad Chains and
on Books.

Bayram (2026-10-24): "kitaplari rahat dolasmak lazim! Max hadis nerede???? max sayfa numarasi????? Isnad Chain de de
ayni durum var!!!"
"""

from __future__ import annotations

from PySide6.QtCore import QStringListModel, Qt, Signal
from PySide6.QtWidgets import QCompleter, QLabel, QLineEdit, QPushButton, QWidget

from isnady.core import isnad as core_isnad
from isnady.core.i18n import tr
from isnady.gui.widgets import FlowLayout


class NumberField(QLineEdit):
    """The hadith number (CH2): typed freely ("12a", "5:1740"), stepped with the arrow keys and the mouse wheel
    to the book's next or previous number."""

    def __init__(self, step) -> None:
        super().__init__()
        self._step = step

    def keyPressEvent(self, e) -> None:  # noqa: N802 (Qt name)
        popup = self.completer().popup() if self.completer() else None
        if e.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down) and not (popup and popup.isVisible()):
            self._step(1 if e.key() == Qt.Key.Key_Up else -1)
            return
        super().keyPressEvent(e)

    def wheelEvent(self, e) -> None:  # noqa: N802
        self._step(1 if e.angleDelta().y() > 0 else -1)
        e.accept()


def _button(text: str, tip: str, name: str = "Quiet") -> QPushButton:
    b = QPushButton(text)
    b.setObjectName(name)
    b.setToolTip(tip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


class HadithNavigator(QWidget):
    """[Hadith no] [ 93 ] / 7563  [Show]  ⏮ ‹ › ⏭  the 93rd of 7,583 hadith. Wraps onto a second line when narrow.
    `activated` is sent when a number is to be shown (Enter, Show, a step); the page reads `number()`."""

    activated = Signal()

    def __init__(self, connection_getter, go_text: str, parent=None) -> None:
        super().__init__(parent)
        self._conn_of = connection_getter
        self._book: str | None = None
        self._range: dict | None = None

        self.field = NumberField(self.step)
        self.field.setObjectName("NumberField")
        self.field.setPlaceholderText(tr("Hadith number"))
        self.field.setFixedWidth(130)
        self.field.returnPressed.connect(self._go)
        self._numbers = QStringListModel(self)               # the numbers that begin with what is typed (CH2)
        completer = QCompleter(self._numbers, self)
        completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        completer.activated.connect(lambda text: (self.field.setText(text), self._go()))
        self.field.setCompleter(completer)
        self.field.textEdited.connect(self._typed)

        self.last_label = QLabel("")                         # "/ 7563": the last number, always in view
        self.last_label.setObjectName("FilterLabel")
        self.go_button = _button(go_text, "", "Primary")
        self.go_button.clicked.connect(self._go)
        self.first_button = _button("⏮", tr("The first hadith of the book"))
        self.prev_button = _button("‹  " + tr("Previous"), tr("The hadith before (↓ or the mouse wheel in the number)"))
        self.next_button = _button(tr("Next") + "  ›", tr("The hadith after (↑ or the mouse wheel in the number)"))
        self.last_button = _button("⏭", tr("The last hadith of the book"))
        self.first_button.clicked.connect(lambda: self._jump("first"))
        self.last_button.clicked.connect(lambda: self._jump("last"))
        self.prev_button.clicked.connect(lambda: self.step(-1))
        self.next_button.clicked.connect(lambda: self.step(+1))
        self.place = QLabel("")                              # "the 93rd of 7,583 hadith"
        self.place.setObjectName("Caption")

        caption = QLabel(tr("Hadith no"))
        caption.setObjectName("FilterLabel")
        flow = FlowLayout(self, spacing=8)
        for w in (caption, self.field, self.last_label, self.go_button, self.first_button, self.prev_button,
                  self.next_button, self.last_button, self.place):
            flow.addWidget(w)

    @property
    def conn(self):
        return self._conn_of()

    # ------------------------------------------------------------------ the book
    def set_book(self, book: str | None) -> None:
        self._book = book
        conn = self.conn
        self._range = core_isnad.number_range(conn, book) if book and conn is not None else None
        rng = self._range
        for b in (self.first_button, self.prev_button, self.next_button, self.last_button, self.go_button):
            b.setEnabled(rng is not None)
        if rng is None:
            self.field.setPlaceholderText(tr("Hadith number"))
            self.field.setToolTip("")
            self.last_label.setText("")
            self.place.setText("")
            return
        self.field.setPlaceholderText(f"{rng['first']} – {rng['last']}")
        self.last_label.setText("/ " + str(rng["last"]))
        why = tr("The numbers are the book's own, as its edition gives them, not a count: some numbers are missing, some "
                 "are split (402.2) and some books begin at 0, so the last number and the number of hadith "
                 "differ.")
        self.last_label.setToolTip(tr("The last number of this book") + "\n" + why)
        self.field.setToolTip(tr("This book's numbers run from {first} to {last} ({n} hadith). The arrow keys and "
                                 "the mouse wheel go to the next or the previous one; typing shows the numbers "
                                 "that begin so.", first=rng["first"], last=rng["last"], n=f"{rng['count']:,}")
                              + "\n" + why)
        self.place.setToolTip(why)
        self._show_place()

    def book(self) -> str | None:
        return self._book

    def number(self) -> str:
        return self.field.text().strip()

    def set_number(self, number: str) -> None:
        """Show a number without going to it (the page shows that hadith already)."""
        self.field.setText(number or "")
        self._show_place()

    # ------------------------------------------------------------------ moving
    def step(self, delta: int) -> None:
        if not self._book or self.conn is None:
            return
        number = core_isnad.step_number(self.conn, self._book, self.number(), delta)
        if number:
            self.field.setText(number)
            self._go()

    def _jump(self, end: str) -> None:
        if self._range:
            self.field.setText(self._range[end])
            self._go()

    def _go(self) -> None:
        self._show_place()
        if self.number():
            self.activated.emit()

    def _typed(self, text: str) -> None:
        if self._book and self.conn is not None:
            self._numbers.setStringList(core_isnad.numbers_starting(self.conn, self._book, text))

    def _show_place(self) -> None:
        rng = self._range
        if rng is None:
            self.place.setText("")
            return
        at = core_isnad.position(self.conn, self._book, self.number()) if self.number() and self.conn is not None else None
        if at is None:
            self.place.setText(tr("{n} hadith · numbers {first} – {last}", n=f"{rng['count']:,}",
                                  first=rng["first"], last=rng["last"]))
            self.prev_button.setEnabled(True)
            self.next_button.setEnabled(True)
            return
        place, count = at
        self.place.setText(tr("hadith {place} of {count} in this book", place=f"{place:,}", count=f"{count:,}"))
        self.first_button.setEnabled(place > 1)
        self.prev_button.setEnabled(place > 1)
        self.next_button.setEnabled(place < count)
        self.last_button.setEnabled(place < count)
