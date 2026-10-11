"""The two languages of isnady (L1): the interface, and the content.

  interface  the language of the window (menus, pages, explanations — core.i18n, I1), the Latin reading of every
             Arabic name (Musaddad b. Musarhad in English and the other languages, Müsedded b. Müserhed in
             Turkish) and the language of the glossary (Learn: English or Turkish so far).
  content    the languages the hadith texts are shown in — Arabic, Turkish, English, … as imported. Empty: every
             language imported. A text that matches a search is shown whatever its language.

Qt-free, like all of isnady.core: the window and the command line read the same two settings.
"""

from isnady import config
from isnady.core.i18n import LANGUAGES

UI_LANGUAGES = {code: own for code, (own, _english, _rtl) in LANGUAGES.items()}


def ui_language() -> str:
    value = config.get("view.ui_language")
    return value if value in UI_LANGUAGES else "en"


def set_ui_language(code: str) -> None:
    config.set("view.ui_language", code)


def content_languages() -> list[str]:
    """The languages chosen for the texts; [] means all."""
    return [part for part in str(config.get("view.content_languages") or "").split(",") if part]


def set_content_languages(languages: list[str]) -> None:
    config.set("view.content_languages", ",".join(languages))
    config.state_forget("reader.languages.")      # every book follows the new choice


def shows(language: str) -> bool:
    chosen = content_languages()
    return not chosen or language in chosen


def folds() -> bool:
    """Texts in languages not chosen: folded behind an arrow on each hadith (True), or left out (False)."""
    return config.get("view.other_languages") != "omit"


def set_folds(on: bool) -> None:
    config.set("view.other_languages", "fold" if on else "omit")
