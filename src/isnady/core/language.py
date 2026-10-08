"""The two languages of isnady (L1): the interface, and the content.

  interface  how the reader reads: the Latin reading of every Arabic name (Musaddad b. Musarhad or Müsedded b.
             Müserhed) and the language of the glossary (Learn). Menus and page texts are in English for now
             (TODO I1: the whole interface in Turkish).
  content    the languages the hadith texts are shown in — Arabic, Turkish, English, … as imported. Empty: every
             language imported. A text that matches a search is shown whatever its language.

Qt-free, like all of isnady.core: the window and the command line read the same two settings.
"""

from isnady import config

UI_LANGUAGES = {"en": "English", "tr": "Türkçe"}


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
