"""Visual identity of isnady.

Drawn from illuminated hadith manuscripts: lapis blue for structure, gold for
the one thing that matters on a result page — the matched words, which are
"gilded". Arabic and translations are set in Amiri (bundled, SIL OFL), a naskh
in the Bulaq press tradition; interface chrome keeps the system font.

Both a light and a dark theme are defined; the system colour scheme decides,
and a change of scheme while the app runs is followed.
"""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FONT_DIR = ASSETS / "fonts"
ICON_DIR = ASSETS / "icons"
READING_FAMILY = "Amiri"


@dataclass(frozen=True)
class Tokens:
    dark: bool
    window: str        # app background
    surface: str       # cards, inputs
    border: str
    ink: str           # main text
    muted: str         # secondary text
    lapis: str         # primary
    lapis_soft: str    # hover / selected backgrounds
    gold: str          # accent
    gilt: str          # matched-word background
    sidebar: str
    sidebar_ink: str
    sidebar_muted: str
    sidebar_selected: str
    pill: str


LIGHT = Tokens(
    dark=False, window="#EEF1F5", surface="#FFFFFF", border="#D9DFE7", ink="#18212C", muted="#5B6878",
    lapis="#1D4777", lapis_soft="#E3EBF5", gold="#A47E24", gilt="#F2E2B3",
    sidebar="#14304F", sidebar_ink="#F1F4F8", sidebar_muted="#9DB0C6", sidebar_selected="#22466F",
    pill="#EDF1F6",
)
DARK = Tokens(
    dark=True, window="#10151C", surface="#18202A", border="#2A3542", ink="#E4E9EF", muted="#8E9BAA",
    lapis="#7FAEE0", lapis_soft="#1F2C3B", gold="#D6B25E", gilt="#4B3C17",
    sidebar="#0B1522", sidebar_ink="#E4E9EF", sidebar_muted="#7D8FA5", sidebar_selected="#1A2D45",
    pill="#222C38",
)

_current: Tokens = LIGHT

THEME_MODES = ("system", "light", "dark")
TEXT_SCALE_MIN, TEXT_SCALE_MAX, TEXT_SCALE_STEP = 0.8, 1.6, 0.1


def settings() -> QSettings:
    return QSettings("isnady", "isnady")


def theme_mode() -> str:
    mode = str(settings().value("view/theme", "system"))
    return mode if mode in THEME_MODES else "system"


def set_theme_mode(mode: str) -> None:
    settings().setValue("view/theme", mode if mode in THEME_MODES else "system")


def text_scale() -> float:
    try:
        value = float(settings().value("view/text_scale", 1.0))
    except (TypeError, ValueError):
        value = 1.0
    return min(max(value, TEXT_SCALE_MIN), TEXT_SCALE_MAX)


def set_text_scale(value: float) -> float:
    value = round(min(max(value, TEXT_SCALE_MIN), TEXT_SCALE_MAX), 2)
    settings().setValue("view/text_scale", value)
    return value


def current() -> Tokens:
    return _current


def load_fonts() -> bool:
    ok = False
    for name in ("Amiri-Regular.ttf", "Amiri-Bold.ttf"):
        path = FONT_DIR / name
        if path.exists() and QFontDatabase.addApplicationFont(str(path)) != -1:
            ok = True
    return ok


def reading_font(point_size: float, bold: bool = False, scaled: bool = False) -> QFont:
    """Amiri at the given size; scaled=True applies the reader's text size (View menu)."""
    font = QFont(READING_FAMILY)
    font.setPointSizeF(point_size * (text_scale() if scaled else 1.0))
    font.setBold(bold)
    return font


def _is_dark_scheme() -> bool:
    hints = QGuiApplication.styleHints()
    scheme = getattr(hints, "colorScheme", None)
    if scheme is not None:
        return hints.colorScheme() == Qt.ColorScheme.Dark
    return QGuiApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128


def _palette(t: Tokens) -> QPalette:
    p = QPalette()
    role = QPalette.ColorRole
    p.setColor(role.Window, QColor(t.window))
    p.setColor(role.WindowText, QColor(t.ink))
    p.setColor(role.Base, QColor(t.surface))
    p.setColor(role.AlternateBase, QColor(t.window))
    p.setColor(role.Text, QColor(t.ink))
    p.setColor(role.Button, QColor(t.surface))
    p.setColor(role.ButtonText, QColor(t.ink))
    p.setColor(role.Highlight, QColor(t.lapis))
    p.setColor(role.HighlightedText, QColor(t.surface if not t.dark else t.window))
    p.setColor(role.ToolTipBase, QColor(t.surface))
    p.setColor(role.ToolTipText, QColor(t.ink))
    p.setColor(role.PlaceholderText, QColor(t.muted))
    p.setColor(role.Link, QColor(t.lapis))
    for group in (QPalette.ColorGroup.Disabled,):
        p.setColor(group, role.Text, QColor(t.muted))
        p.setColor(group, role.WindowText, QColor(t.muted))
        p.setColor(group, role.ButtonText, QColor(t.muted))
    return p


def _icon(name: str, t: Tokens) -> str:
    return (ICON_DIR / f"{name}-{'dark' if t.dark else 'light'}.svg").as_posix()


def stylesheet(t: Tokens) -> str:
    chevron, check = _icon("chevron", t), _icon("check", t)
    return f"""
    QMainWindow, QWidget#Page {{ background: {t.window}; }}
    QMenuBar {{ background: {t.window}; color: {t.ink}; border-bottom: 1px solid {t.border}; padding: 2px 6px; }}
    QMenuBar::item {{ background: transparent; padding: 5px 10px; border-radius: 5px; }}
    QMenuBar::item:selected {{ background: {t.lapis_soft}; }}
    QMenu {{ background: {t.surface}; color: {t.ink}; border: 1px solid {t.border}; padding: 6px 0; }}
    QMenu::item {{ padding: 6px 28px 6px 26px; }}
    QMenu::item:selected {{ background: {t.lapis_soft}; color: {t.ink}; }}
    QMenu::item:disabled {{ color: {t.muted}; }}
    QMenu::separator {{ height: 1px; background: {t.border}; margin: 5px 12px; }}
    QMenu::indicator {{ width: 14px; height: 14px; left: 7px; }}
    QDialog {{ background: {t.window}; }}
    QToolTip {{ background: {t.surface}; color: {t.ink}; border: 1px solid {t.border}; padding: 4px 6px; }}

    /* sidebar */
    QFrame#Sidebar {{ background: {t.sidebar}; border: none; }}
    QLabel#Wordmark {{ color: {t.sidebar_ink}; }}
    QLabel#WordmarkArabic {{ color: {t.gold}; }}
    QLabel#SidebarFooter {{ color: {t.sidebar_muted}; font-size: 8.5pt; }}
    QListWidget#Nav {{ background: transparent; border: none; outline: none; color: {t.sidebar_ink}; }}
    QListWidget#Nav::item {{ padding-left: 14px; margin: 1px 10px; border-radius: 6px; color: {t.sidebar_muted}; }}
    QListWidget#Nav::item:hover {{ background: {t.sidebar_selected}; color: {t.sidebar_ink}; }}
    QListWidget#Nav::item:selected {{ background: {t.sidebar_selected}; color: {t.sidebar_ink};
                                      border-left: 3px solid {t.gold}; }}

    /* inputs */
    QLineEdit#SearchField {{ background: {t.surface}; color: {t.ink}; border: 1px solid {t.border};
                             border-radius: 10px; padding: 10px 14px; font-size: 12.5pt; }}
    QLineEdit#SearchField:focus {{ border: 2px solid {t.lapis}; padding: 9px 13px; }}
    QPushButton#Primary {{ background: {t.lapis}; color: {t.surface if not t.dark else t.window}; border: none;
                           border-radius: 10px; padding: 10px 22px; font-weight: 600; font-size: 11pt; }}
    QPushButton#Primary:hover {{ background: {t.gold}; }}
    QPushButton#Quiet {{ background: {t.surface}; color: {t.lapis}; border: 1px solid {t.border};
                         border-radius: 8px; padding: 7px 16px; }}
    QPushButton#Quiet:hover {{ border-color: {t.lapis}; }}
    QPushButton#Example {{ background: {t.surface}; color: {t.ink}; border: 1px solid {t.border};
                           border-radius: 17px; padding: 0 16px; min-height: 34px; }}
    QPushButton#Example:hover {{ border-color: {t.gold}; color: {t.gold}; }}
    QComboBox {{ background: {t.surface}; color: {t.ink}; border: 1px solid {t.border}; border-radius: 7px;
                 padding: 5px 10px; min-height: 18px; }}
    QComboBox:hover {{ border-color: {t.lapis}; }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QComboBox::down-arrow {{ image: url("{chevron}"); width: 12px; height: 12px; }}
    QComboBox QAbstractItemView {{ background: {t.surface}; color: {t.ink}; border: 1px solid {t.border};
                                   selection-background-color: {t.lapis_soft}; selection-color: {t.ink}; }}
    QCheckBox {{ color: {t.ink}; spacing: 7px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {t.border}; border-radius: 4px;
                            background: {t.surface}; }}
    QCheckBox::indicator:hover {{ border-color: {t.lapis}; }}
    QCheckBox::indicator:checked {{ background: {t.lapis}; border-color: {t.lapis}; image: url("{check}"); }}
    QLabel#FilterLabel {{ color: {t.muted}; }}
    QLabel#Summary {{ color: {t.muted}; }}

    /* results */
    QScrollArea#Results, QWidget#ResultsBody {{ background: {t.window}; border: none; }}
    QFrame#Card {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 12px; }}
    QLabel#CardTitle {{ color: {t.ink}; }}
    QLabel#CardNumber {{ color: {t.muted}; }}
    QLabel#Pill {{ background: {t.pill}; color: {t.ink}; border: 1px solid {t.pill}; border-radius: 7px;
                   padding: 2px 10px; font-size: 8.5pt; }}
    QLabel#ArabicText {{ color: {t.ink}; }}
    QFrame#Translation {{ border: none; border-left: 3px solid {t.gold}; background: transparent; }}
    QLabel#TranslationText {{ color: {t.ink}; }}
    QLabel#Caption {{ color: {t.muted}; font-size: 8.5pt; }}

    /* start and placeholder pages */
    QLabel#Hero {{ color: {t.ink}; }}
    QLabel#HeroArabic {{ color: {t.gold}; }}
    QLabel#Lead {{ color: {t.muted}; font-size: 11pt; }}
    QLabel#PageTitle {{ color: {t.ink}; }}

    QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 4px; min-height: 36px; }}
    QScrollBar::handle:vertical:hover {{ background: {t.muted}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QStatusBar {{ background: {t.window}; color: {t.muted}; }}
    """


def apply(app: QApplication, mode: str | None = None) -> Tokens:
    """Apply the chosen theme (system, light or dark; default: the saved choice)."""
    global _current
    if "Fusion" in QStyleFactory.keys():
        app.setStyle("Fusion")
    mode = mode or theme_mode()
    if mode == "light":
        _current = LIGHT
    elif mode == "dark":
        _current = DARK
    else:
        _current = DARK if _is_dark_scheme() else LIGHT
    app.setPalette(_palette(_current))
    app.setStyleSheet(stylesheet(_current))
    return _current
