"""Tools → Narrator Identification (0.8.0): every way isnady identifies a narrator, what it reads, how many links it
decided, its parameters — each can be changed, and the narrators are identified again (core/narrator_rules.py).

Bayram (2026-11-15): "râviyi nasıl tanımlıyoruz, ona ait settingsler … hangi teknikler ve parametreleri neler ve
bunları nasıl değiştirebiliyoruz". The rijal work's own words and isnady's guesses are two tabs, never mixed.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from isnady.core import narrator_rules as nr
from isnady.core.i18n import t, tr


def _number(value) -> str:
    return f"{value:g}" if isinstance(value, float) else f"{value:,}"


class NarratorRulesDialog(QDialog):
    """The ways of identifying, in three tabs; Save keeps them and identifies the narrators again."""

    def __init__(self, parent, rules: dict, guess: bool, counts: dict) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Narrator Identification"))
        self.resize(760, 640)
        self._boxes: dict[str, QGroupBox] = {}
        self._fields: dict[tuple[str, str], QSpinBox | QDoubleSpinBox] = {}
        layout = QVBoxLayout(self)
        intro = QLabel(tr("How isnady links a name of a chain to a narrator. The rijal work's own words are used "
                          "unless turned off here; isnady's guesses only with the box below, and every narrator they "
                          "find is marked \"≟ isnady's guess\" in the chain. Saving identifies every chain's "
                          "narrators again."))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self._guess = QCheckBox(tr("Use isnady's guesses (its own inference, marked in the chain)"))
        self._guess.setChecked(guess)
        self._guess.toggled.connect(self._guess_changed)
        layout.addWidget(self._guess)
        tabs = QTabWidget()
        self._guess_page = None
        for group in ("source", "guess", "common"):
            page = self._page(group, rules, counts)
            if group == "guess":
                self._guess_page = page
            tabs.addTab(page, t(nr.GROUPS[group]))
        layout.addWidget(tabs, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        save = QPushButton(tr("Save and Identify Again"))
        save.setDefault(True)
        buttons.addButton(save, QDialogButtonBox.ButtonRole.AcceptRole)
        reset = QPushButton(tr("Defaults"))
        reset.setToolTip(tr("Every way on, every parameter as isnady ships it"))
        reset.clicked.connect(self._defaults)
        buttons.addButton(reset, QDialogButtonBox.ButtonRole.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._guess_changed(guess)

    def _page(self, group: str, rules: dict, counts: dict) -> QWidget:
        inner = QWidget()
        column = QVBoxLayout(inner)
        if group == "guess":
            note = QLabel(tr("isnady's own inference, not the scholars' words: used only when the box above is on."))
            note.setWordWrap(True)
            column.addWidget(note)
        for key, g, switch, params in nr.RULES:
            if g != group:
                continue
            box = QGroupBox(t(nr.TITLES[key]))
            if switch:
                box.setCheckable(True)
                box.setChecked(rules[key]["on"])
            self._boxes[key] = box
            form = QFormLayout(box)
            text = QLabel(t(nr.EXPLAINED[key]))
            text.setWordWrap(True)
            form.addRow(text)
            decided = [f"{label} {_number(counts.get(road, {}).get(key, 0))}"
                       for road, label in (("sunni", tr("Sunni")), ("shia", tr("Shia")))
                       if counts.get(road, {}).get(key)]
            if decided:
                head = tr("Removed:") if key == "impossible" else tr("Decided at the last identification:")
                form.addRow(QLabel(head + " " + " · ".join(decided)))
            for name, default, lo, hi, step in params:
                if isinstance(default, int):
                    field = QSpinBox()
                    field.setRange(int(lo), int(hi))
                    field.setSingleStep(int(step))
                else:
                    field = QDoubleSpinBox()
                    field.setDecimals(2)
                    field.setRange(lo, hi)
                    field.setSingleStep(step)
                field.setValue(rules[key][name])
                field.setToolTip(tr("Default: {value}", value=_number(default)))
                self._fields[(key, name)] = field
                form.addRow(t(nr.PARAMETERS[name]), field)
            column.addWidget(box)
        column.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        return scroll

    def _guess_changed(self, on: bool) -> None:
        if self._guess_page is not None:
            self._guess_page.widget().setEnabled(on)

    def _defaults(self) -> None:
        base = nr.defaults()
        for key, box in self._boxes.items():
            if box.isCheckable():
                box.setChecked(True)
        for (key, name), field in self._fields.items():
            field.setValue(base[key][name])

    def rules(self) -> dict:
        """The ways and parameters as the dialog shows them."""
        out = nr.defaults()
        for key, box in self._boxes.items():
            if box.isCheckable():
                out[key]["on"] = box.isChecked()
        for (key, name), field in self._fields.items():
            value = field.value()
            out[key][name] = int(value) if isinstance(field, QSpinBox) else round(float(value), 2)
        return out

    def guess(self) -> bool:
        return self._guess.isChecked()


def open_dialog(window) -> None:
    """Tools → Narrator Identification…: the dialog, and the narrators identified again when it is saved."""
    from PySide6.QtGui import QGuiApplication

    from isnady.core import narrators as core_narrators

    search = window.search_page
    conn = search._conn
    if conn is None:
        return
    dialog = NarratorRulesDialog(window, nr.load(conn), core_narrators.guesses_on(conn), nr.counts(conn))
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS core_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("INSERT OR REPLACE INTO core_meta (key, value) VALUES ('narrator_guess', ?)",
                     ("on" if dialog.guess() else "off",))
        core_narrators.set_rules(conn, dialog.rules(), progress=search._status)
    finally:
        QGuiApplication.restoreOverrideCursor()
    search.__dict__.pop("_person_cache", None)
    search.data_changed.emit()
    search.retheme()
