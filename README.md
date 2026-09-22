# isnady

Hadith search built around the **isnad** — the chain of transmission.

isnady is a desktop application (PySide6, Windows and Linux) for searching hadith
across the major collections and seeing *why* each report has the grade it has:
every narrator in the chain, what the scholars of jarh wa ta'dil said about them,
and how the chain holds together.

> **Status: pre-alpha (0.0.1).** This release is the application skeleton. No hadith
> data is included yet.

## Planned

- **Search** — by text, book, chapter, narrator and grade: mutawatir, sahih, hasan,
  da'if, mawdu' and the intermediate grades.
- **Narrators** — biography, dates, teachers and students, number of narrations,
  and every recorded verdict with its source.
- **Isnad chains** — each chain drawn link by link, with each narrator's standing.
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
