"""Visual identity of isnady.

Drawn from illuminated hadith manuscripts: lapis blue for structure, gold for
the one thing that matters on a result page — the matched words, which are
"gilded". Arabic and translations are set in Amiri (bundled, SIL OFL), a naskh
in the Bulaq press tradition; interface chrome keeps the system font.

Both a light and a dark theme are defined; the system colour scheme decides,
and a change of scheme while the app runs is followed.
"""

from dataclasses import dataclass, replace
from pathlib import Path

from isnady import config

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

# Named themes (UI5). "light" and "dark" keep their keys (saved settings) and are the Lapis pair that "system"
# follows; the others are chosen by name. The user's colour edits (Preferences → Colours) belong to the Lapis pair.
PAPER = Tokens(
    dark=False, window="#F3EEE4", surface="#FFFCF6", border="#E2D8C8", ink="#2B241C", muted="#776A59",
    lapis="#8A3B1F", lapis_soft="#F1E2D4", gold="#A8792A", gilt="#F3DFAE",
    sidebar="#3A2A1E", sidebar_ink="#F6EEE3", sidebar_muted="#BCAA93", sidebar_selected="#55402E",
    pill="#EFE6D8",
)
SLATE = Tokens(
    dark=False, window="#F5F6F8", surface="#FFFFFF", border="#E2E5EA", ink="#111827", muted="#646B78",
    lapis="#4338CA", lapis_soft="#ECEDFE", gold="#C2700A", gilt="#FCE7C2",
    sidebar="#FFFFFF", sidebar_ink="#111827", sidebar_muted="#646B78", sidebar_selected="#ECEDFE",
    pill="#F0F2F5",
)
EMERALD = Tokens(
    dark=False, window="#EFF5F2", surface="#FFFFFF", border="#D3E2DB", ink="#13241D", muted="#58706A",
    lapis="#0F6E66", lapis_soft="#DCF0EA", gold="#B0741C", gilt="#F6E1B2",
    sidebar="#0B3B33", sidebar_ink="#EAF6F2", sidebar_muted="#93BCB1", sidebar_selected="#14544A",
    pill="#E7F1ED",
)
MIDNIGHT = Tokens(
    dark=True, window="#0D1117", surface="#161B22", border="#2A313C", ink="#E6EDF3", muted="#8B949E",
    lapis="#5CC8BC", lapis_soft="#16302E", gold="#E3B341", gilt="#4A3A12",
    sidebar="#090C10", sidebar_ink="#E6EDF3", sidebar_muted="#7D8590", sidebar_selected="#18242C",
    pill="#21262D",
)
CONTRAST = Tokens(
    dark=True, window="#000000", surface="#0B0B0B", border="#BDBDBD", ink="#FFFFFF", muted="#D4D4D4",
    lapis="#FFD400", lapis_soft="#2E2A00", gold="#FFD400", gilt="#5C4D00",
    sidebar="#000000", sidebar_ink="#FFFFFF", sidebar_muted="#D4D4D4", sidebar_selected="#262626",
    pill="#1A1A1A",
)
THEMES = {   # key: (name, description, tokens)
    "light": ("Lapis", "Lapis and gold of illuminated manuscripts", LIGHT),
    "dark": ("Lapis Night", "The same, by night", DARK),
    "paper": ("Paper", "Warm cream and ink, for long reading", PAPER),
    "slate": ("Slate", "Quiet and modern, a light sidebar", SLATE),
    "emerald": ("Emerald", "Green and gold", EMERALD),
    "midnight": ("Midnight", "Deep dark with teal", MIDNIGHT),
    "contrast": ("High Contrast", "Black, white and yellow, for low vision", CONTRAST),
}

_current: Tokens = LIGHT
_SYSTEM_UI_FONT: QFont | None = None     # the platform's own UI font, before any user choice

# Ibn Hajar's twelve ranks, grouped for a small colour mark next to the verdict (the words themselves are
# always shown; the colour only helps the eye): Companions, praised, truthful, acceptable, weak, rejected.
RANK_COLORS = {
    "light": {1: "#A47E24", 2: "#2E7D4F", 3: "#2E7D4F", 4: "#1D4777", 5: "#1D4777", 6: "#8A6D1F", 7: "#8A6D1F",
              8: "#B4552D", 9: "#B4552D", 10: "#A33A3A", 11: "#A33A3A", 12: "#A33A3A"},
    "dark": {1: "#D6B25E", 2: "#6FC08F", 3: "#6FC08F", 4: "#7FAEE0", 5: "#7FAEE0", 6: "#D9B866", 7: "#D9B866",
             8: "#E08A64", 9: "#E08A64", 10: "#E07A7A", 11: "#E07A7A", 12: "#E07A7A"},
}


def rank_color(rank: int | None) -> str:
    return RANK_COLORS["dark" if _current.dark else "light"].get(rank or 0, _current.muted)


def current() -> Tokens:
    return _current


THEME_MODES = ("system",) + tuple(THEMES)
TEXT_SCALE_MIN, TEXT_SCALE_MAX, TEXT_SCALE_STEP = 0.8, 1.6, 0.1


def settings() -> QSettings:
    """Kept only to carry settings over from 0.0.4 and earlier (see migrate_qsettings)."""
    return QSettings("isnady", "isnady")


def migrate_qsettings() -> None:
    """0.0.4 and earlier kept theme and text size in QSettings; move them to settings.json once."""
    old = settings()
    for old_key, new_key in (("view/theme", "view.theme"), ("view/text_scale", "view.text_scale")):
        value = old.value(old_key)
        if value not in (None, "") and config.get(new_key) == config.DEFAULTS[new_key]:
            try:
                config.set(new_key, value)
            except config.ConfigError:
                pass
        old.remove(old_key)


def theme_mode() -> str:
    return config.get("view.theme")


def set_theme_mode(mode: str) -> None:
    config.set("view.theme", mode if mode in THEME_MODES else "system")


def text_scale() -> float:
    return float(config.get("view.text_scale"))


def set_text_scale(value: float) -> float:
    value = round(min(max(value, TEXT_SCALE_MIN), TEXT_SCALE_MAX), 2)
    config.set("view.text_scale", value)
    return value


# ------------------------------------------------------------ reading text by script
def script_font(script: str, bold: bool = False, factor: float = 1.0) -> QFont:
    """The reader's font for one script: family and size from the settings, times the text scale."""
    script = script if script in config.SCRIPTS else "latin"
    family = config.get(f"text.{script}.family")
    font = QFont(family) if family else QFont(QApplication.font())
    font.setPointSizeF(float(config.get(f"text.{script}.size")) * factor * text_scale())
    font.setBold(bold)
    return font


def font_css(font: QFont) -> str:
    """The font as style-sheet text. A widget with its own style sheet ignores setFont(),
    so any widget that also sets a colour through a style sheet must carry its font here."""
    weight = "700" if font.bold() else "400"
    return f"font-family: '{font.family()}'; font-size: {font.pointSizeF():.1f}pt; font-weight: {weight};"


def script_color(script: str) -> str:
    color = config.get(f"text.{script}.color") if script in config.SCRIPTS else ""
    return color or _current.ink


def script_line_height(script: str) -> int:
    return int(config.get(f"text.{script}.line_height")) if script in config.SCRIPTS else 115


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
    chevron, check, up, down = _icon("chevron", t), _icon("check", t), _icon("up", t), _icon("down", t)
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
    QFrame#Sidebar {{ background: {t.sidebar}; border: none; border-right: 1px solid {t.border if not t.dark and t.sidebar.upper() == t.surface.upper() else t.sidebar}; }}
    QLabel#Wordmark {{ color: {t.sidebar_ink}; }}
    QLabel#WordmarkArabic {{ color: {t.gold}; }}
    QLabel#SidebarFooter {{ color: {t.sidebar_muted}; font-size: 8.5pt; }}
    QListWidget#Nav {{ background: transparent; border: none; outline: none; color: {t.sidebar_ink}; }}
    QListWidget#Nav::item {{ padding-left: 16px; margin: 2px 12px; border-radius: 8px; color: {t.sidebar_muted}; }}
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
    QPushButton#Primary:disabled {{ background: {t.border}; color: {t.muted}; }}
    QCheckBox:disabled {{ color: {t.muted}; }}
    QListWidget#NarratorList {{ background: transparent; border: none; outline: none; }}
    QLabel#RowLatin {{ color: {t.lapis}; font-weight: 600; }}
    QPushButton#Chip {{ background: {t.lapis_soft}; color: {t.lapis}; border: none; border-radius: 13px;
                       padding: 5px 12px; font-weight: 600; }}
    QPushButton#Chip:hover {{ background: {t.lapis}; color: {t.surface}; }}
    QPushButton#Segment {{ background: {t.surface}; color: {t.muted}; border: 1.5px solid {t.border};
                          border-radius: 8px; padding: 5px 14px; font-weight: 600; }}
    QPushButton#Segment:checked {{ background: {t.lapis}; color: {t.surface}; border-color: {t.lapis}; }}
    QLabel#FilterTitle {{ color: {t.muted}; font-size: 8.5pt; font-weight: 600; letter-spacing: 0.3px; }}
    QComboBox#FilterCombo {{ background: {t.surface}; color: {t.ink}; border: 1.5px solid {t.muted};
                            border-radius: 9px; padding: 7px 12px; min-height: 22px; font-weight: 600; }}
    QComboBox#FilterCombo:hover {{ border-color: {t.lapis}; }}
    QComboBox#FilterCombo[active="true"] {{ background: {t.lapis_soft}; border: 1.5px solid {t.lapis}; color: {t.lapis}; }}
    QComboBox#FilterCombo::drop-down {{ border: none; width: 28px; }}
    QTreeWidget#Contents {{ background: transparent; border: none; outline: none; color: {t.ink}; }}
    QTreeWidget#Contents::item {{ padding: 4px 2px; }}
    QTreeWidget#Contents::item:selected {{ background: {t.lapis_soft}; color: {t.ink}; }}
    QLabel#RowTitle {{ color: {t.ink}; font-weight: 700; }}
    QFrame#Help {{ background: {t.lapis_soft}; border-radius: 10px; }}
    QListWidget#NarratorList::item {{ border-bottom: 1px solid {t.border}; }}
    QListWidget#NarratorList::item:selected {{ background: {t.lapis_soft}; }}
    QListWidget#NarratorList::item:hover {{ background: {t.lapis_soft}; }}
    QCheckBox::indicator:disabled {{ background: {t.window}; border-color: {t.border}; }}
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
    QFrame#Card {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 14px; }}
    QLabel#CardTitle {{ color: {t.ink}; }}
    QLabel#CardNumber {{ color: {t.muted}; }}
    QLabel#Pill {{ background: {t.pill}; color: {t.ink}; border: 1px solid {t.pill}; border-radius: 7px;
                   padding: 2px 10px; font-size: 8.5pt; }}
    QLabel#ArabicText {{ color: {t.ink}; }}
    QFrame#Translation {{ border: none; border-left: 3px solid {t.gold}; background: transparent; }}
    QLabel#TranslationText {{ color: {t.ink}; }}
    QLabel#Caption {{ color: {t.muted}; font-size: 8.5pt; }}

    /* preferences */
    QTabWidget::pane {{ border: none; }}
    QTabBar::tab {{ background: transparent; color: {t.muted}; padding: 8px 16px; border: none;
                    border-bottom: 2px solid transparent; }}
    QTabBar::tab:selected {{ color: {t.ink}; border-bottom: 2px solid {t.gold}; }}
    QTabBar::tab:hover {{ color: {t.ink}; }}
    QSpinBox, QDoubleSpinBox, QFontComboBox {{ background: {t.surface}; color: {t.ink};
        border: 1px solid {t.border}; border-radius: 7px; padding: 4px 8px; min-height: 20px; }}
    QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {t.lapis}; }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-origin: border; subcontrol-position: top right;
        width: 20px; border: none; background: transparent; }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-origin: border;
        subcontrol-position: bottom right; width: 20px; border: none; background: transparent; }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url("{up}"); width: 10px; height: 10px; }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url("{down}"); width: 10px; height: 10px; }}

    QProgressBar {{ background: {t.lapis_soft}; border: none; border-radius: 3px; }}
    QProgressBar::chunk {{ background: {t.gold}; border-radius: 3px; }}
    QLineEdit {{ background: {t.surface}; color: {t.ink}; border: 1px solid {t.border}; border-radius: 7px;
                 padding: 5px 8px; }}
    QLineEdit:focus {{ border-color: {t.lapis}; }}

    /* chains */
    QLabel#ChainChip {{ background: {t.lapis_soft}; color: {t.ink}; border: 1px solid {t.lapis_soft};
                        border-radius: 8px; padding: 1px 9px; }}
    QLabel#ChainChipProphet {{ background: {t.gilt}; color: {t.ink}; border: 1px solid {t.gold};
                               border-radius: 8px; padding: 1px 9px; }}
    QLabel#ChainArrow {{ color: {t.muted}; padding: 0 1px; }}
    QPushButton#SidebarNotice {{ background: transparent; color: {t.gold}; border: 1px solid {t.gold};
        border-radius: 8px; padding: 6px 10px; margin: 0 18px 8px 18px; text-align: left; font-weight: 600; }}
    QPushButton#SidebarNotice:hover {{ background: {t.sidebar_selected}; }}
    QLabel#ChainChipUnknown {{ background: transparent; color: {t.muted}; border: 1px dashed {t.border};
                               border-radius: 8px; padding: 1px 9px; }}
    QLabel#NodeFacts {{ color: {t.muted}; font-size: 9pt; }}
    QLabel#NodeVerdict {{ color: {t.ink}; }}
    QLabel#NodeUnknown {{ color: {t.muted}; font-size: 9pt; font-style: italic; }}
    QFrame#Node {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: 10px; }}
    QFrame#NodeProphet {{ background: {t.gilt}; border: 1px solid {t.gold}; border-radius: 10px; }}
    QLabel#NodeTerm {{ color: {t.gold}; font-size: 9pt; }}
    QLabel#NodeName {{ color: {t.ink}; }}
    QLabel#StatValue {{ color: {t.lapis}; font-size: 20pt; font-weight: 700; }}
    QPushButton#Link {{ background: transparent; color: {t.lapis}; border: none; padding: 2px 4px;
                        font-weight: 600; }}
    QPushButton#Link:hover {{ color: {t.gold}; }}
    QLineEdit#NumberField {{ background: {t.surface}; color: {t.ink}; border: 1px solid {t.border};
                             border-radius: 7px; padding: 5px 10px; }}
    QLineEdit#NumberField:focus {{ border-color: {t.lapis}; }}
    QPushButton#Quiet:disabled {{ color: {t.muted}; border-color: {t.border}; }}

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
    global _current, _SYSTEM_UI_FONT
    if _SYSTEM_UI_FONT is None:
        _SYSTEM_UI_FONT = QFont(app.font())
    if "Fusion" in QStyleFactory.keys():
        app.setStyle("Fusion")
    mode = mode or theme_mode()
    if mode in THEMES:
        base = THEMES[mode][2]
    else:
        base = DARK if _is_dark_scheme() else LIGHT
    if base in (LIGHT, DARK):           # the user's own colours belong to the Lapis pair
        which = "dark" if base.dark else "light"
        overrides = {token: config.get(f"colors.{which}.{token}") for token in config.COLOR_TOKENS}
        _current = replace(base, **{k: v for k, v in overrides.items() if v})
    else:
        _current = base
    family, size = config.get("ui.family"), float(config.get("ui.size"))
    ui_font = QFont(family) if family else QFont(_SYSTEM_UI_FONT or app.font())
    if size:
        ui_font.setPointSizeF(size)
    app.setFont(ui_font)
    app.setPalette(_palette(_current))
    app.setStyleSheet(stylesheet(_current))
    return _current
