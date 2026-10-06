# Changelog

Every release of isnady carries one version number on GitHub, PyPI and npm. The text of each GitHub Release
is taken from its section here.

## [Unreleased]

- **Portable applications**: Windows gets one portable `.exe` instead of an installer, macOS a zipped `isnady.app`
  instead of a disk image; the Linux AppImage was portable already. Nothing is installed; a folder named
  `isnady-data` beside the application keeps all its data there (isnady on a USB stick).
- **Version badges that cannot go stale**: the PyPI and npm badges carry the version in their address, so GitHub's
  and npm's image caches can no longer show an older one (0.1.3 showed v0.1.2 there for a while).
- **One command for a new version** (`tools/bump_version.py 0.1.4`): code, npm files, the README's status line and
  badges, the CHANGELOG heading and the npm README, together. The release check now also checks the README, and
  `tools/release_status.py` shows what PyPI, npm, GitHub and the Release page publish after a release.

## [0.1.3] — 2026-10-05

**Deep statistics begin, a glossary to learn from, and two fixes everyone sees.**

- **Learn**: 81 terms of hadith and its sciences, written for isnady with their classical sources — grades, kinds of
  hadith by their chain, chain and text, ways of receiving, judging narrators, generations, Arabic names, Imami
  rijal, books, and isnady's own measures. Each with its Arabic, a one-line and a longer definition in English or
  Turkish, related terms, and its source; searchable in both languages. Pointing at a grade on a search result,
  or at a narrator's rank, shows what it means. `iy term`.
- **Statistics → Graders**, the first deep statistics tab: for a book graded by several scholars, the agreement of
  every pair (same grade, Cohen's kappa, ordinal kappa) with 95% bootstrap intervals; Krippendorff's ordinal alpha;
  a Dawid–Skene model of each hadith's true grade with each grader's confusion matrix and the model's certainty;
  strictness by order only (P below the true grade − P above it) with intervals; pair-by-pair who grades higher;
  the disputed hadith, opening in their book. A pair agreeing far too often to be independent (al-Albani and Muhyi
  al-Din, 98.1%) is one voice in the model. Computed once in the background and kept in a file; `iy stats graders`.
- The Hadith Scholars page measures strictness by order only (how often his grade is lower or higher than the
  others' on the same hadith), no longer by averaging grades as numbers.
- **No more empty space below the results**: the Search page (and the Books reader) ended in thousands of empty
  pixels — up to half the page after widening the window — because each text measured its least height at the
  width it was made with. The page now ends where the last result does, at any window size.
- **Clearer filters on the Narrators and Shia Rijal pages**: each filter sits under its own title (Generation,
  Rank, Book; Assessment), the boxes are plain to see, a chosen filter is coloured, and *Clear filters* appears
  when one is on.

## [0.1.2] — 2026-10-04

**Names that can be read, and a desktop shortcut.**

- **Names, redesigned**: every narrator and scholar is shown by the name he is **known by** — al-A'mash,
  Ibn 'Umar, Abu Hurayra, al-Zuhri, al-Bukhari, Ibn Hajar — large, in Arabic and in Latin letters, with his
  full name and *how* he is known (by-name, kunya, nisba, an ancestor's name) beneath. Below, each part of the
  name on its own line: name (ism), lineage (nasab), kunya, by-name (laqab), nisbas (places marked), client
  of (wala'), other names — the part he is known by marked ★, with a one-line explanation of what the parts
  are. The same card on the Narrators, Shia Rijal and Hadith Scholars pages; the lists, the chains and the
  books use the same known-as names. The entry as the critic wrote it is folded into the critics' card.
- Which name a person is known by is taken only from what the sources say: Ibn Hajar's cross-references, an
  entry that opens with the kunya, or "known as …" in the entry. A name shared by several narrators names only
  the one the chains cite far more often ("Ibn 'Umar" is the Companion); a by-name inside someone else's name
  ("… bint Abi Bakr al-Siddiq") is not taken as hers. Checked on blind samples of the most-cited narrators.
  Readings are in English for now; Turkish and other languages come with the interface language.
- **Create Desktop Shortcut** (Tools menu, `iy shortcut`): isnady on the desktop and in the applications menu,
  with its own icon, starting isnady the way it is installed (AppImage, application, or `isnady-gui`). The
  Desktop folder is the system's own (e.g. "Masaüstü"); on Windows the shortcut and the taskbar show isnady's
  icon, not Python's.

## [0.1.1] — 2026-10-04

**Desktop applications, one release for every place, and two new sections.**

- **Desktop applications** on every GitHub Release: a Windows installer (`.exe`), a Linux `AppImage`, and
  macOS apps (`.dmg`, Apple silicon and Intel) — isnady with everything it needs, including the AI features.
  The application has its own icon.
- **One release, everywhere at once**: a version tag builds the Python package and the three applications
  first; only when every build succeeds is anything published — PyPI, then the GitHub Release with all files
  and their checksums. A check stops the release if the version differs anywhere. The npm README is now made
  from this README, so GitHub, PyPI and npm say the same.
- **Books**: open every imported work and read it in its own order — a hadith collection chapter by chapter,
  each hadith with its card; Ibn Hajar's *Taqrib* letter by letter. Previous / next, find in a chapter,
  languages, isnady remembers where you were. *In its book* on every search result opens the hadith in its
  chapter. Works are general (any depth, any kind of book), the shape of isnady's own exchange format.
- **Shia Rijal**: al-Najashi's *Rijal* — 1,266 narrators — read on the Imami scale: reliability (thiqa,
  praised, weak) and creed (Imami, Waqifi, Fathi, Zaydi, 'ammi …), giving the classical four (thiqa, mamduh,
  muwaththaq, da'if); the critic's words always shown; checked on four blind samples. Shia narrators are never
  matched to the (Sunni) chains. *Open his entry in the book* on both Narrators pages.
- Command line: `iy book`, `iy import najashi`.
- Database schema 7, upgraded in place. Re-import the Taqrib (Data Sources → Update) to read it as a book.

## [0.1.0] — 2026-10-04

- **Narrators** page: every narrator of the Taqrib, searchable in Arabic or Latin letters, filtered by tabaqa,
  rank and book; Ibn Hajar's verdict, tabaqa, death year, teachers and students in the chains.
- **Hadith Scholars** page: compilers, graders and critics measured from the data — agreement between graders,
  Cohen's kappa, a strictness index (the classical mutashaddid / mutasahil), with plain explanations.
- **Takhrij**: the other narrations of each hadith across the imported books ("Also narrated in").
- Names in Latin letters, Turkish and English. The Taqrib reader identifies 52.1% of the names in the chains.
- Pages follow the window's width; Qt's harmless font messages are silenced.

## [0.0.9] — 2026-10-01

- **Search by meaning (AI)**: cross-lingual latent semantic analysis learnt from the imported texts — a Turkish
  query finds its Arabic original (92.8% in the first ten for hadith never seen while learning).
  `pip install "isnady[ai]"`, `iy ai build`, `iy search --mode meaning`.

## [0.0.8] — 2026-10-01

- `iy update` updates every copy of isnady **where it is installed** (system, user, virtual environment, pipx,
  clone); nothing is ever removed or moved. The one-line installers follow the same rule.

## [0.0.7] — 2026-09-30

- `iy doctor`, one-line installers (`install.sh`, `install.ps1`), a quiet installation check at start.

## [0.0.6] — 2026-09-30

- Narrators identified in the chains from Ibn Hajar's *Taqrib al-Tahdhib*; data sources inside the application
  with *Import all*; a movable data folder.

## [0.0.5] — 2026-09-29

- Appearance settings (fonts, sizes, colours per script); one command under several names (`isnady`, `iy`).

## [0.0.4] — 2026-09-29

- Search no longer freezes the window: results are drawn in steps, Arabic text is shaped once.

## [0.0.3] — 2026-09-29

- A database that cannot be opened is explained on the page, with the way to repair it.

## [0.0.1] – [0.0.2] — 2026-09

- First releases: search across hadith collections in Arabic and translations; chains of transmission.
