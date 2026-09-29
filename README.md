# isnady

Hadith search built around the **isnad** — the chain of transmission.

isnady is a desktop application (PySide6, Windows and Linux) for searching hadith
across the major collections and seeing *why* each report has the grade it has:
every narrator in the chain, what the scholars of jarh wa ta'dil said about them,
and how the chain holds together.

> **Status: pre-alpha (0.0.3).** Search and chains of transmission work today on data you
> import; narrators, scholars and the rest are being built.

## Works now

- **Search** across every imported edition. Arabic ignores diacritics and letter forms and
  finds words with attached prefixes; Turkish and other Latin-script text ignores case and
  accents. All words, any word or exact phrase; book and language filters.
- **Chains of transmission** read from the Arabic text: each narrator, the words that link
  them (haddathana, akhbarana, 'an ...) with what each means, and whether the chain reaches
  the Prophet. Where the wording cannot be read with confidence the chain is kept whole,
  never guessed.
- **Desktop app and command line** with the same engine: `isnady` and `isnady-cli`.

```
isnady-cli import fawazahmed0 https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions.json \
    --book bukhari --language ara --language tur --license Unlicense
isnady-cli search النيات
isnady-cli chain bukhari 1
isnady
```

## Planned

- **Search** — by text, book, chapter, narrator and grade: mutawatir, sahih, hasan,
  da'if, mawdu' and the intermediate grades.
- **Narrators** — biography, dates, teachers and students, number of narrations,
  and every recorded verdict with its source.
- **Narrators identified** — every name in a chain linked to its narrator, with each
  narrator's standing and whether each link could have met the next.
- **Reliability scores** — derived transparently from classical rankings (for example
  Ibn Hajar's twelve grades in *Taqrib al-Tahdhib*), always shown with the verdicts
  they come from. A score is a conversion of the scholars' judgement, never a new one.
- **Shia rijal** — the primary grading follows the Sunni tradition; narrator verdicts
  from Shia rijal works (al-Najashi, al-Tusi, al-Kashshi, al-Hilli, al-Khoei) are listed
  per narrator beside the Sunni view.
- **Statistics** — narrators, books and grades counted and compared.
- **Learn** — the hadith sciences explained: terminology, grading, jarh wa ta'dil,
  and the classical works.

## Install

```
pip install isnady
isnady
```

## License

MIT for the application code. Hadith and narrator data will come from separate
sources, each under its own license, listed here as they are added.

The Arabic and reading typeface is [Amiri](https://github.com/aliftype/amiri) by
Khaled Hosny, bundled under the SIL Open Font License 1.1
(`src/isnady/assets/fonts/OFL.txt`).
