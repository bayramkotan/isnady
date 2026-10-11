<!-- generated from README.md by tools/sync_readme.py — edit README.md, not this file -->
<h1 align="center">📜 isnady &nbsp;<sub>إسناد</sub></h1>

<p align="center">
  <strong>Hadith search built around the isnad, the chain of transmission</strong><br>
  <sub>Search the Sunni and Shia collections, read every chain narrator by narrator, and see how the scholars of each tradition read it</sub>
</p>

<p align="center">
  <a href="https://pypi.org/project/isnady/">
    <img src="https://img.shields.io/badge/PyPI-v0.2.2-1D4777?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI">
  </a>
  <img src="https://img.shields.io/pypi/pyversions/isnady?style=for-the-badge&color=A47E24&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-5B6878?style=for-the-badge" alt="Platform">
  <a href="https://www.npmjs.com/package/isnady">
    <img src="https://img.shields.io/badge/npm-v0.2.2-14304F?style=for-the-badge&logo=npm" alt="npm">
  </a>
  <a href="https://github.com/bayramkotan/isnady-data">
    <img src="https://img.shields.io/badge/data-isnady--data-2E6B4F?style=for-the-badge&logo=github" alt="isnady-data">
  </a>
  <img src="https://img.shields.io/badge/License-MIT-D6B25E?style=for-the-badge" alt="License">
</p>

<p align="center">
  <a href="#-two-repositories-one-project">Repositories</a> •
  <a href="#-why-isnady">Why</a> •
  <a href="#-install">Install</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-isnady-data--the-data">isnady-data</a> •
  <a href="#-search">Search</a> •
  <a href="#-chains-of-transmission">Chains</a> •
  <a href="#-sunni-and-shia-two-roads">Sunni and Shia</a> •
  <a href="#-narrators">Narrators</a> •
  <a href="#-books">Books</a> •
  <a href="#-hadith-scholars">Scholars</a> •
  <a href="#-statistics">Statistics</a> •
  <a href="#-learn">Learn</a> •
  <a href="#-search-by-meaning-ai">Meaning (AI)</a> •
  <a href="#-appearance-and-settings">Appearance</a> •
  <a href="#%EF%B8%8F-cli">CLI</a> •
  <a href="#%EF%B8%8F-roadmap">Roadmap</a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/search-arabic.png" alt="Searching النيات finds بالنيات in Sahih al-Bukhari 1, with the chain above the text" width="850">
</p>

> **Pre-alpha (0.2.2).** Search, chains of transmission, narrators, books, scholars, statistics and
> the glossary work today, Sunni and Shia, on data you import in one click. Everything is built in
> the open, one piece at a time.

---


> **About this npm package.** `npm install isnady` installs a small JavaScript library that will grow into
> isnady's API for the web (isnady.net); it does **not** install the isnady application. The application is
> installed with Python (`pip install isnady`, or the one-line installers below) or downloaded as a desktop
> app from the [GitHub Releases](https://github.com/bayramkotan/isnady/releases/latest) page. The npm package
> always carries the same version number as the application.
>
> ```js
> import { info, version } from "isnady";
> console.log(version);      // the isnady version, the same as on PyPI and GitHub
> console.log(info());       // { name, version, dataLoaded, homepage }
> ```

## 🧭 Two repositories, one project

isnady is two repositories that work as one:

| | [**bayramkotan/isnady**](https://github.com/bayramkotan/isnady) — the application | [**bayramkotan/isnady-data**](https://github.com/bayramkotan/isnady-data) — the data |
|---|---|---|
| **What it is** | The program: a desktop window and a command line on one engine | Every hadith collection and rijal work isnady reads, in one format |
| **What is in it** | Search, the chain reader (Sunni and Shia), narrator identification, books, scholars, statistics, the glossary, meaning search | **17 Sunni and 16 Shia hadith collections — 99,746 hadith** — in Arabic and up to eight translations, with their grades; **Ibn Hajar's *Taqrib*** (8,824 narrators) and **al-Najashi's *Rijal*** (1,266) |
| **How you get it** | [PyPI](https://pypi.org/project/isnady/) (`pip install isnady`), the desktop applications of the [Releases](https://github.com/bayramkotan/isnady/releases/latest), or the one-line installers | Nothing to download by hand: isnady lists its books in **Data sources** and imports them in one click — or clone it and read it offline, or take a whole [ready database](https://github.com/bayramkotan/isnady-data/releases) |
| **Licence** | MIT | each book its own, recorded with it (Help → Licences) |

```
   bayramkotan/isnady-data                         bayramkotan/isnady
   ───────────────────────                         ──────────────────
   catalog.json ─────────────── Data sources ───▶  import ─▶ isnady.db ─▶ search · chains · narrators
   sunni/<book>/  shia/<book>/                       (your data folder)      books · scholars · statistics
   rijal/sunni/   rijal/shia/                                                 window  and  command line
   Releases: isnady-db-<date>.zip ── Use a ready database… ──▶ isnady.db
```

The application ships without hadith data, so it stays small and the data can grow on its own:
a new book in isnady-data reaches every isnady at once, without a new version of the program.

---

## 🎯 Why isnady

A hadith is two things: the text (*matn*) and the chain of people who passed it on (*isnad*).
Most hadith sites let you search the text and show a grade. isnady is built the other way round:
the chain comes first, because that is where the scholars of hadith did their work.

- **The chain is read, not typed in.** isnady reads the chain from the Arabic text itself: who
  narrated to whom, with which words, and whom it reaches.
- **Each tradition by its own road.** A Sunni book's chains are read the Sunni way and judged by
  the Sunni critics; a Shia book's chains are read the Shia way and judged by the Imami critics.
  The two meet on the same pages and are never measured by each other's scale.
- **Nothing is guessed.** Where the wording cannot be read with confidence, the chain is kept
  whole and marked, never split wrongly. A narrator is named only when the evidence leaves one
  person; otherwise isnady says how many it could be.
- **Every fact has a source.** Every hadith, text and grade records where it came from, under
  which licence.
- **Grades are shown as the scholars gave them.** Each grade keeps its scholar's name and wording;
  grades are ordered categories, never averaged, and isnady never invents its own.
- **Computed once, kept.** Every statistic and model is saved as JSON beside your data and read
  back, never computed again for the same data.
- **Window and command line, same engine.** Everything the window does, the command line does
  too, with the same results.

---

## 📦 Install

### Desktop application

Download isnady for your system from the **[latest release](https://github.com/bayramkotan/isnady/releases/latest)** —
everything included, the AI features too:

| System | File |
|---|---|
| Windows 10/11 | `isnady-<version>-windows-portable.exe` — Windows may say the publisher is unknown (the app is not signed): *More info → Run anyway* |
| Linux | `isnady-<version>-linux-x86_64.AppImage` — make it executable (`chmod +x`) and run it |
| macOS, Apple silicon / Intel | `isnady-<version>-macos-arm64.zip` / `…-macos-x86_64.zip` — unzip and run `isnady.app`; the first time, right-click it and choose *Open* (it is not notarized) |

All three are **portable**: nothing is installed, each runs from wherever it is. Put a folder named
`isnady-data` beside the file and isnady keeps its databases and settings there — isnady on a USB stick.

Put isnady on the desktop and in the applications menu with **Tools → Create Desktop Shortcut** (or
`iy shortcut`): the shortcut starts isnady the way it is installed — the AppImage, the application, or the
`isnady-gui` command of a Python install.

### With Python

One line, on any system. Install isnady wherever you like — for all users, for yourself, in a
virtual environment, with pipx: the same line installs it, and later updates every copy where it
is, asking for administrator rights only when a copy needs them. Nothing is ever removed.

```bash
# Linux and macOS
curl -fsSL https://raw.githubusercontent.com/bayramkotan/isnady/main/install.sh | bash
```

```powershell
# Windows (PowerShell)
irm https://raw.githubusercontent.com/bayramkotan/isnady/main/install.ps1 | iex
```

Or with pip:

```bash
pip install isnady
isnady            # or the short name:  iy
```

Run inside a clone of this repository, the installer makes an editable (developer) install of
that clone instead.

The same program answers to several names: **`iy`** to type, **`isnady`** to read, and
`isnady-cli` kept from the first releases. Without arguments it opens the window; with
arguments it is the command line. On Windows, **`isnady-gui`** opens the window without a
console.

<details>
<summary><b>🐧 On Linux, pip may refuse to install</b></summary>
<br>

Most current distributions mark the system Python as *externally managed* (PEP 668), so a
plain `pip install` stops with `error: externally-managed-environment`. Two ways around it:

```bash
# Isolated — recommended, no system packages touched
pipx install isnady

# Into your user site — needs the override flag
pip install isnady --break-system-packages --no-cache-dir -U
```

</details>

### Upgrading, and when something is not right

```bash
iy update
```

`iy update` updates every copy of isnady where it is installed. Your data stays where it is; a
newer isnady upgrades the database in place the first time it opens it, and reads the chains again
when its chain reader has changed (a minute or two, once).

`iy doctor` lists every copy and which one each command really starts — an older copy in the user
folder can start before a newer one elsewhere, so every copy is kept at the same version. The same
report is under **Help → Check Installation** (and the ⚠ button in the sidebar when something is behind), with an
**Update** button that does what `iy update` does: every copy updated where it is, the output shown as it comes; a
copy installed for all users asks for the administrator password in the system's own window (pkexec on Linux, the
administrator prompt on Windows). If an old copy starts even for `iy update`, run `python3 -s -m isnady update`
(Windows: `py -s -m isnady update`).

---

## 🚀 Quick Start

1. **Open isnady** — `iy`, or the desktop application.
2. **File → Data Sources.** The repository is already chosen: **isnady-data**. Tick the books and
   the languages you want and press **Import** — or **Import all**.
3. **Import the narrators too** — Ibn Hajar's *Taqrib* for the Sunni books, al-Najashi's *Rijal*
   for the Shia books — and every name in every chain is matched to its narrator.
4. **Search**, open a chain, open a narrator, read a book.

The same from the command line:

```bash
iy catalog list                                           # the books of isnady-data
iy catalog import sahih_al_bukhari --language ara --language tur
iy catalog import musnad_ahmad_ibn_hanbal
iy catalog import al_kafi_al_kulayni                      # with al-Majlisi's and al-Behbudi's grades
iy catalog import taqrib_al_tahdhib_ibn_hajar_al_asqalani # the narrators of the Sunni chains
iy catalog import rijal_al_najashi_ahmad_ibn_ali_al_najashi  # the narrators of the Shia chains
iy catalog import --all                                   # everything

iy search النيات              # Arabic, with or without diacritics
iy search "niyetlere göre"     # Turkish, English, any imported language
iy chain bukhari 1             # one chain, narrator by narrator
iy chain kafi 5:1740           # a Shia chain, read the Shia way
iy narrator الزهري             # who a narrator is
```

Importing takes a minute or two a book; the search index, the chains and the narrators are built as
part of it. No network? See [Without the network](#without-the-network) below.

---

## 📚 isnady-data — the data

**[bayramkotan/isnady-data](https://github.com/bayramkotan/isnady-data)** is isnady's own data
repository and its default: every source isnady reads, converted once into isnady's own format.

| | Sunni | Shia |
|---|---|---|
| **Hadith collections** | **17 books, 76,132 hadith.** Sahih al-Bukhari, Sahih Muslim, Sunan Abi Dawud, Jami' al-Tirmidhi, Sunan al-Nasa'i, Sunan Ibn Majah, the Muwatta — Arabic and up to eight translations (English, Turkish, Urdu, Indonesian, Bengali, French, Russian, Tamil), graded by al-Albani, Shu'ayb al-Arna'ut, Zubair 'Ali Za'i and others · the Forty of al-Nawawi, Forty Hadith Qudsi, the Forty of Shah Waliullah · Musnad Ahmad ibn Hanbal (26,363) and Sunan al-Darimi, fully voweled · Riyad al-Salihin, al-Shama'il al-Muhammadiyya, Bulugh al-Maram, al-Adab al-Mufrad, Mishkat al-Masabih, Arabic and English | **16 books, 23,614 hadith.** al-Kulayni's **al-Kafi** (8 volumes, 14,241 hadith, al-Majlisi's grade on nearly every one, al-Behbudi's selection) · al-Saduq's 'Uyun Akhbar al-Rida, al-Amali, al-Khisal, al-Tawhid, Ma'ani al-Akhbar, Thawab al-A'mal, Sifat al-Shi'a, Fada'il al-Shi'a · al-Mufid's al-Amali · Ibn Qulawayh's Kamil al-Ziyarat · al-Nu'mani's and al-Tusi's Kitab al-Ghayba · al-Ahwazi's al-Mu'min and al-Zuhd · al-Muhsini's Mu'jam al-Ahadith al-Mu'tabara — Arabic and English |
| **Narrators** | Ibn Hajar, *Taqrib al-Tahdhib* — 8,824 narrators: verdict, rank of twelve, tabaqa, death year, book marks | al-Najashi, *Rijal* — 1,266 authors and narrators: reliability and creed in the Imami terms |

### How it is laid out

```
isnady-data/
├── catalog.json                    the list isnady reads (isnady-catalog/1)
├── sunni/sahih_al_bukhari/         book.json (numbers, chapters, references, grades) + ara.json, eng.json, tur.json …
├── sunni/musnad_ahmad_ibn_hanbal/
├── shia/al_kafi_al_kulayni/
├── rijal/sunni/taqrib_al_tahdhib_ibn_hajar_al_asqalani.md
├── rijal/shia/rijal_al_najashi_ahmad_ibn_ali_al_najashi.md
├── derived/                        statistics and models already computed, as JSON
└── database.json                   the ready database of the latest Release
```

- **Full names, never a bare one.** Every folder and every id is the book's full title with its
  compiler's name — `musnad_ahmad_ibn_hanbal`, `al_kafi_al_kulayni`,
  `taqrib_al_tahdhib_ibn_hajar_al_asqalani`. isnady imports by these ids, and names its exports and
  saved computations after them.
- **One format for every book** (`isnady-book/1`): a `book.json` with each hadith's number, place,
  chapter, other numberings and every grade as `[scholar, grade]`, exactly as written; and one file
  per language with the chapter titles and the texts. The formats are described in the
  [isnady-data README](https://github.com/bayramkotan/isnady-data#-the-formats).
- **Sunni and Shia apart.** Every book says its tradition, and isnady keeps them on their own roads
  (below).
- **Your own data stays yours.** What you import from your own files is never written into a
  ready database for isnady-data: it does not leave your computer.

### Without the network

isnady-data works the same from a folder on your computer — a `git clone`, a USB stick, a shared
folder:

```bash
git clone https://github.com/bayramkotan/isnady-data ~/isnady-data
iy repo add ~/isnady-data       # in the window: Data sources → A folder on this computer…
iy catalog import --all
```

Or take **a whole ready database** — every book imported, every chain read, every narrator
identified — from the [isnady-data Releases](https://github.com/bayramkotan/isnady-data/releases):

```bash
iy database use ~/Downloads/isnady-db-<date>.zip   # in the window: Data folder → Use a ready database…
```

isnady checks the file (the zip must hold `isnady.db`, the schema must be one it reads, the sha256
must match the `database.json` beside it), puts it in place at the next start and keeps your
previous database beside it (`isnady.<date-time>.bak.db`). Nothing is deleted.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/data-sources.png" alt="Settings → Data sources — isnady-data by default, a folder on this computer, or another repository; its books, Sunni and Shia apart" width="760">
</p>

### Other repositories

isnady-data is all you need. isnady can also read a few datasets that others publish, as they
publish them, under their own keys (e.g. `bukhari-lk`) so that editions with other numbering never
mix with isnady-data's. Choose one in **Settings → Data sources** (`iy repo use ID`) or add any
repository with an isnady catalog, a Hugging Face dataset, a URL or a folder (`iy repo add …`):

| Repository | Holds | Licence |
|---|---|---|
| [fawazahmed0/hadith-api](https://github.com/fawazahmed0/hadith-api) | 10 collections, Arabic + 8 languages, grades | Unlicense |
| [Thaqalayn](https://github.com/MohammedArab1/ThaqalaynAPI) | 16 Shia collections, Arabic + English | not stated |
| [Open Hadith Data](https://github.com/mhashim6/Open-Hadith-Data) | the nine books, voweled Arabic | ODbL |
| [hadith-json](https://github.com/AhmedBaset/hadith-json) | 17 books, Arabic + English | not stated |
| [LK Hadith Corpus](https://github.com/ShathaTm/LK-Hadith-Corpus) | the six books, isnad and matn marked apart | not stated |
| [meeAtif/hadith_datasets](https://huggingface.co/datasets/meeAtif/hadith_datasets) (Hugging Face) | the six books, Arabic + English | MIT (as declared) |
| [Hadith-Data-Sets](https://github.com/abdelrahmaan/Hadith-Data-Sets) | the nine books, Arabic | not stated |
| [OpenITI](https://github.com/OpenITI) | the Taqrib, al-Najashi's Rijal | not stated |

Every source records a licence **tier** — **A** may be redistributed, **B** under its conditions,
**C** may not — and **Help → Licences** lists them all. Any CSV or JSON table of hadith can be read
through a catalog that names its columns (format `table`); files and links of your own, with or
without authentication (credentials are never stored), are read as well.

---

## 🔎 Search

| | |
|:--|:--|
| **Arabic without diacritics** | `الاعمال` finds `الأَعْمَالُ`. Alef forms, alef maqsura, hamza seats and ta marbuta are treated alike, so you type the way you normally write |
| **Attached prefixes** | `النيات` finds `بالنيات`, because Arabic joins bi-, wa-, fa- and al- to the word. *Whole words only* turns this off |
| **Latin-script text** | Case and accents are ignored: `NIYET`, `niyet` and `nîyet` are one word; `Muʿādh`, `Mu'adh` and `Muadh` too |
| **Match** | All words, any word, the exact phrase — or by meaning (AI, below) |
| **Books** | All books, all Sunni, all Shia, or any few ticked one by one |
| **Order** | Book by book in the order of the book lists — Sahih al-Bukhari, Sahih Muslim, Sunan Abi Dawud … then the Shia books — and within a book by its numbering |
| **Language** | One language to search in; the languages you do not read are folded behind an arrow on each hadith, a click opens them. The list holds the languages imported; the languages the same books have in isnady-data (Urdu, Indonesian, Bengali, French, Russian, Tamil) are named at its end — choosing them opens **File → Data Sources** to import them |
| **Active books** | A book can be switched off in **Settings → Books and languages**: it stays imported but is left out of searches, book lists and statistics until switched on |
| **Grades** | Shown under each hadith with the scholar's name, exactly as given, and explained when you point at them |
| **Highlighting** | On the original, diacritised text, diacritics included |
| **Narrators and scholars** | The same box finds narrators — Sunni and Shia, each marked — and scholars, by Arabic or Latin name |

Results appear at once and fill in as you read; the window never waits for them.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/search-folded.png" alt="Search in two books with Arabic chosen: the English and Turkish texts folded behind ▸ Other languages, opened with a click" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/book-picker.png" alt="Books — tick all books, all Sunni, all Shia, or any few one by one" width="420">
</p>

---

## 🔗 Chains of transmission

Every Arabic text is read for its chain:

```
Sahih al-Bukhari 1
   1. حدثنا (narrated to us)  الْحُمَيْدِيُّ عَبْدُ اللَّهِ بْنُ الزُّبَيْرِ
   2. حدثنا (narrated to us)  سُفْيَانُ
   3. حدثنا (narrated to us)  يَحْيَى بْنُ سَعِيدٍ الْأَنْصَارِيُّ
   4. أخبرني (informed me)    مُحَمَّدُ بْنُ إِبْرَاهِيمَ التَّيْمِيُّ
   5. سمع (heard)            عَلْقَمَةَ بْنَ وَقَّاصٍ اللَّيْثِيَّ
   6. سمعت (I heard)          عُمَرَ بْنَ الْخَطَّابِ
      -> the Prophet ﷺ
```

In the window, each result shows its chain as a row of names ending at whom it reaches, and
**View chain** opens it as a timeline from the book to the Prophet ﷺ — or, in a Shia book, to the
Imam — with the Arabic text below: the chain in lighter ink, the text of the hadith in full ink.
Every link says who the narrator is and what his critic says of him; a click opens him.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/chain.png" alt="Isnad Chains — the chain of Sahih al-Bukhari 1 as a timeline from the book to the Prophet" width="850">
</p>

### 👤 Who each narrator is

Every name in a chain is matched to a narrator of its own tradition's rijal work — the *Taqrib*
for a Sunni book, al-Najashi for a Shia book. A name is linked only when the evidence leaves one
person: the words of the name, the book marks (a narrator in al-Bukhari must be one Ibn Hajar marks
خ), the order of generations along the chain, the last link before the Prophet being a Companion,
and — in al-Kafi — al-Kulayni's own teachers at the head of his chains. When several narrators
remain — "Sufyan" can be al-Thawri or Ibn 'Uyayna — the chain says so and names how many, rather
than choosing one. In blind, hand-checked samples of the identified names, the last fifty were all
correct. Names are kept exactly as written, with the clarifications the compilers added
(*"— yaʿnī Ibn Muḥammad —"*).

<details>
<summary><b>📊 How well it reads today</b></summary>
<br>

| | Chains | Split into narrators | Reaching the Prophet / a Ma'sum | Names identified |
|:--|--:|--:|--:|--:|
| Sahih al-Bukhari | 7,580 | 85.5% | | 51.5% |
| Sunan Abi Dawud | 5,272 | 71.9% | | 53.0% |
| al-Kafi (read the Shia way) | 14,239 | 96.8% | 92% | 48.5% |

In a blind, hand-checked sample of 30 Sunni chains: **no wrong narrator**, 27 complete. The rest are
kept whole, each with its reason: *tahwil* (ح, a second chain joining), two teachers at one link
(*qiran*), a chain that refers to an earlier one (*bi-isnadihi*), or wording that could not be read
with confidence. `iy isnads` gives the figures for every book you imported.

</details>

### 🎓 The words of transmission explain themselves

| Term | Reads | What the critics took it to mean |
|:--:|:--|:--|
| حدثنا | narrated to us | The teacher recited it to a group: heard directly |
| حدثني | narrated to me | Recited to the narrator alone: heard directly |
| أخبرنا | informed us | Often a text read back to the teacher (*ʿarḍ*) |
| أنبأنا | told us | Later often transmission by permission (*ijāza*) |
| سمعت | I heard | Direct hearing, stated explicitly |
| قرأت على | I read to | The narrator read the text back to the teacher |
| عن | from | Does not say how it was received (*ʿanʿana*); connected when the two could have met and the narrator is not known for *tadlīs* |
| أن | that | Treated by most critics like ʿan (*muʾannan*) |
| — | (his teacher) | The compiler names his teacher without a term, as al-Kulayni does: his own transmission from that teacher |

---

## 🕌 Sunni and Shia: two roads

Sunni and Shia meet on the same pages — one search, one Narrators page, one shelf of books — and
every Shia narrator and book carries a gold **Shia** tag. They meet without being mixed: every value
isnady derives is reached along the road of the book's own tradition.

| | Road A — Sunni books | Road B — Shia books |
|---|---|---|
| How a chain opens | a transmission term on every link (حدثنا، أخبرنا، عن …) | al-Kulayni names his teacher without a term (علي بن إبراهيم عن أبيه …) |
| Groups and joined roads | two narrators at one link (qiran) | "عدة من أصحابنا" — al-Kulayni's groups, shown with the teachers he said they stand for; "… جميعاً عن …", two roads joined; "رفعه"; "عن رجل"; "عنه" |
| Where it ends | the Prophet ﷺ | one of the Fourteen Ma'sumun: the Prophet ﷺ or an Imam, most often by his kunya — أبو عبد الله is Ja'far al-Sadiq, أبو جعفر al-Baqir, أبو الحسن al-Kazim or al-Rida; "سألته" is *mudmar* |
| Who identifies its narrators | Ibn Hajar's *Taqrib al-Tahdhib* | only the Shia rijal works: al-Najashi's *Rijal* (al-Tusi's next) |
| How a narrator is judged | Ibn Hajar's twelve ranks | the Imami critics' own terms — **reliability** (*thiqa*; praised — *jalil*, *wajh*, *'ayn*; weak) and **creed** (Imami, or Waqifi, Fathi, Zaydi, *'ammi* …): an Imami *thiqa*, a praised narrator (*mamduh*), a *thiqa* of another school (*muwaththaq*), a weak one |
| Whose grades | al-Albani, Shu'ayb al-Arna'ut, Zubair 'Ali Za'i … | al-Majlisi (*Mir'at al-'Uqul*), al-Behbudi (*Sahih al-Kafi*) … |

Nothing is mapped onto the other tradition's measure, and a narrator of one tradition is never a
candidate for a link of the other's chains. Read this way, **96.8%** of al-Kafi's 14,239 chains
split into their narrators (9 did when they were read the Sunni way), **92%** reach a Ma'sum, and
half of their 61,160 names are identified in al-Najashi's *Rijal* (3 were before).

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/chain-shia.png" alt="A chain of al-Kafi read the Shia way: al-Kulayni's group of teachers, the narrators judged by al-Najashi, ending at Imam Ja'far al-Sadiq" width="850">
</p>

```bash
iy chain kafi 5:1740                                 # al-Kulayni's group, al-Najashi's verdicts, the Imam it reaches
iy search "زرارة" --in narrators --tradition shia
iy isnads                                            # per book: chains split, and whom they reach
```

---

## 👥 Narrators

The **Narrators** page lists every narrator of the imported rijal works — **All**, **Sunni** or
**Shia** at the top of the list — searchable in Arabic or in Latin letters (`Abu Hurayra`, `Zuhri`,
`Ibn Umar`, `زرارة`). For each narrator:

- the name he is **known by** (al-A'mash, Ibn 'Umar, Zurara), with his full name and every part of
  it laid out — name, lineage, kunya, by-name, nisbas, client of — the part he is known by marked ★;
- what his critic says, in the critic's own words: Ibn Hajar's verdict and its rank for a Sunni
  narrator; al-Najashi's words, reliability and creed for a Shia narrator — the entry as written one
  click away;
- tabaqa and death year, the books his hadith appear in (Ibn Hajar's marks);
- **whom he narrates from and who narrates from him** in the imported chains, and the compilers who
  narrate from him directly;
- every hadith whose chain includes him, each a click from its chain.

Sunni narrators filter by tabaqa, rank and book; Shia narrators by the Imami assessment.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/narrators.png" alt="Narrators — 'Abdullah b. 'Umar: Ibn Hajar's verdict, tabaqa, death year, teachers and students in the chains" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/narrators-shia.png" alt="Narrators — Zurara b. A'yan, a Shia narrator: al-Najashi's words and their reading in the Imami terms" width="850">
</p>

---

## 📖 Books

isnady is not only for searching: the **Books** section opens every imported work and reads it in
its own order. A hadith collection reads chapter by chapter, each hadith with its card (chain,
narrators, other narrations, grades) and the languages you choose; Ibn Hajar's *Taqrib* and
al-Najashi's *Rijal* read entry by entry, each narrator a click away. Find within a chapter, go to
the previous or next one, and isnady remembers where you were. From any search result, **In its
book** opens the hadith where it stands, among the hadith of its chapter.

Book and chapter titles follow the interface language: the sources give chapter titles in English only, so
isnady carries its own — all 642 chapter titles of the 33 books in Turkish and in Arabic ("Vahyin Başlangıcı",
"كتاب بدء الوحي" for "Revelation"), and the Arabic titles a source gives itself where it has them (al-Adab
al-Mufrad, Bulugh al-Maram, Mishkat, Riyad al-Salihin, al-Shama'il). The book titles too: *Sahîh-i Buhârî*,
*صحيح البخاري*.

The shelf holds the Sunni and the Shia books together, each under its own heading — *All*, *Sunni*
or *Shia* at the top shows one of them alone — and every Shia book carries a gold *Shia* tag. Books
are not tied to hadith collections: a work is a tree of any depth (volume, book, chapter, section)
whose leaves are hadith, narrators' entries or paragraphs — so commentaries, manuals of fiqh and the
other works of the scholars can be read the same way as they are added.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/books.png" alt="Books — the Sunni and Shia shelves; reading Sahih al-Bukhari chapter by chapter, Arabic, English and Turkish, each hadith with its chain" width="850">
</p>

```bash
iy book                      # the books
iy book bukhari              # its chapters
iy book bukhari 2 --language Turkish
iy book taqrib 1
```

---

## 🎓 Hadith Scholars

The scholars whose work is in the imported data, and what the data measures of it: **compilers**
(their collection, the teachers their chains begin with, the Companions they end with), **graders**
(how they grade, and how far they agree with each other on the same hadith — agreement, Cohen's
kappa, and a strictness index: the classical *mutashaddid* / *mutasahil*, measured), and **critics**
of narrators — Sunni and Shia on one page (*All / Sunni / Shia*), each by his own road: al-Kulayni,
al-Saduq, al-Mufid and al-Tusi with their chains counted to a Ma'sum; al-Majlisi and al-Behbudi compared
only with each other on the four Imami grades (sahih, hasan, muwaththaq, da'if); al-Najashi's verdicts in
the Imami terms. On Sunan Abi Dawud, for example, Zubair 'Ali Za'i grades most strictly (−0.21) and
agrees with al-Albani on 70% of the hadith; the page also flags a pair of graders whose 98%
agreement suggests the source did not keep them independent.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/scholars.png" alt="Hadith Scholars — al-Albani: his grades on Sunan Abi Dawud and his agreement with the other graders" width="850">
</p>

---

## 📊 Statistics

Measured in depth, each figure with what it means in plain words and how sure it is — on two roads:
*All Sunni books* (Ibn Hajar's ranks, chains to the Prophet ﷺ) and *All Shia books* (al-Najashi's Imami
categories, chains to a Ma'sum; al-Majlisi's and al-Behbudi's grades in the four Imami categories —
sahih, hasan, muwaththaq, da'if), never mixed. Every section is measured on both roads. Grades are
ordered categories, so they are never turned into numbers or averaged, and no figure is read
against the science of hadith: the statistics measure what the scholars did, they do not overrule
it. Every result is computed once and saved as JSON in your data folder (`derived/`).

| Section | What it shows |
|---|---|
| **Overview** | the corpus at a glance: books, hadith, chains, narrators, grades |
| **Narrators** | reliability, concentration (the busiest 10% carry 75% of the transmission — the Lorenz curve) and the pillars of transmission |
| **Chains** | length, the weakest link, and the time between narrators (who could not have met) |
| **Grades and chains** | the weakest narrator and the length of a chain against its grade |
| **Books** | the books side by side |
| **Graders** | agreement of every pair (same grade, Cohen's and the ordinal kappa, 95% intervals, Krippendorff's alpha); a **Dawid–Skene model** of each hadith's true grade and each grader's confusion matrix; **strictness**; the **disputed hadith** |
| **The hadith model** | what each scholar's grade follows — ordinal regression with odds ratios and 95% intervals, and the hadith graded higher or lower than their chain |
| **Correlations and tests** | every measure against every other (Spearman's ρ with Benjamini–Hochberg q-values, the partial ρ with the others held equal) and what differs: graders pair by pair (Stuart–Maxwell), books (Kruskal–Wallis, Mann–Whitney with Cliff's δ), whether the model's shape holds (Brant) |

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/statistics.png" alt="Statistics — Narrators: the busiest 10% of narrators carry 75% of the transmission; the Lorenz curve and the pillars" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/statistics-model.png" alt="The hadith model — for al-Albani, a weak or unknown weakest narrator multiplies the odds of a weaker grade by 14; odds ratios with 95% intervals" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/statistics-lab.png" alt="Correlations and tests — each factor against each scholar's grade with the others held equal (partial Spearman's rho), Sunan Abi Dawud" width="850">
</p>

```bash
iy stats                     # what the database holds, per book
iy stats graders --book abudawud
iy stats model --grader albani
iy stats lab --csv ./lab     # every table behind the figures, as CSV
```

---

## 🎓 Learn

The terms of hadith and its sciences, written for isnady with their classical sources: 81 terms —
the grades (sahih, hasan, da'if, mawdu', shadhdh, munkar, mu'allal), the kinds of hadith by their
chain (mutawatir, mursal, munqati', mu'allaq, mudallas …), chain and text (mutaba'a, shahid,
takhrij, madar), the ways of receiving (sama', ijaza, haddathana, 'an), judging narrators (the
twelve ranks of Ibn Hajar, thiqa, saduq, majhul, matruk, mudallis), generations, the parts of an
Arabic name, the Imami grades (sahih, hasan, muwaththaq, da'if), the books, and isnady's own
measures. Each with its Arabic, a one-line and a longer definition in **English, Turkish or Arabic** — in the interface language when the glossary
has it — related terms one click away, and its source. The grades on every result explain themselves
when you point at them. `iy term mursal --lang tr`, `iy term mursal --lang ar`.

Each of the ten categories has its own colour and sign — on the chips above the list (a click shows that
category alone), the dot before each term, the band of the term's card, its "In short" box and the chips of its
related terms; the card reads from the top: the term large with its Arabic, its names in the other languages,
*In short*, *In detail*, the source, the related terms, and more of the same category to read on.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/learn.png" alt="Learn — the term mursal in its category's colour: Arabic, In short, In detail, source, related terms" width="850">
</p>

---

## 🌳 Genealogies

Four trees, drawn so they can be zoomed, moved and clicked (**Genealogies** in the sidebar, `iy tree`):

| Tree | What it shows |
|---|---|
| **The prophets** | From Adam to Muhammad ﷺ as the Qur'an, al-Bukhari and the classical historians give it — Ibn Hisham, Ibn Sa'd, al-Tabari, Ibn Kathir: Nuh, Ibrahim and his sons, the prophets of the Children of Israel, the line of Isma'il to 'Adnan and on to the Prophet ﷺ. A link whose generations are not known is drawn dashed; a report the sources differ on has a dashed box and says so |
| **Quraysh and the Prophet's family** | From Ka'b b. Lu'ayy: the Prophet's family ﷺ, the lineages of the four caliphs joining his, the Umayyads, and the Imams of the Shia |
| **A narrator's family** | Read from the narrators' own names: "X b. Y b. Z" is the son of "Y b. Z" when exactly one narrator of that name, of the same tradition and of an earlier or the same generation, is found — over a thousand such links in the Taqrib and al-Najashi (Ibn 'Umar's sons and grandsons, the family of al-Zubayr …). A reading of the names, said so on the page |
| **A narrator's line of learning** | His teachers above him and theirs, his students below him and theirs, the most frequent at each step, counted from the imported chains |

**Where the written trees come from.** Sunni sources, each link marked with how strong its source is: the Qur'an
where it names a relation (Ibrahim's sons Isma'il and Ishaq, Ya'qub …); al-Bukhari's *Sahih* (Manaqib al-Ansar,
the Prophet's lineage ﷺ up to 'Adnan, on which the scholars agree); the sira and history works (Ibn Hisham, Ibn
Sa'd, al-Tabari, Ibn Kathir); the genealogists of Quraysh (Mus'ab al-Zubayri, Ibn Hazm). The names between Adam
and Ibrahim and between Isma'il and 'Adnan are the historians' only — they took them partly from the People of the
Book, and neither the Qur'an nor an authentic hadith gives them; the page says so on those names. The Imams of the
Shia are shown as the line of the Prophet's family ﷺ that the Sunni genealogists record too; that they are Imams
is the Shia's belief, shown as theirs (where the Sunni historians differ — a son of al-Hasan al-'Askari — the box
is dashed and both are given).

Click a name for what the sources say about it; a narrator opens on the Narrators page, which has the links to
his family and his line of learning too. `iy tree prophets`, `iy tree prophets Musa`, `iy tree family "Ibn
Umar"`, `iy tree learning al-Zuhri --depth 2 --width 4`.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/genealogy.png" alt="Genealogies — the prophets: Ibrahim, his sons Isma'il and Ishaq, Ya'qub and the tribes" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/genealogy-family.png" alt="Genealogies — a narrator's family read from the narrators' names: 'Umar b. al-Khattab, Ibn 'Umar, Salim and their sons" width="850">
</p>

---

## ⭐ Bookmarks

Every hadith card, narrator, scholar, term of Learn and chapter of Books has a ☆: one click keeps it among
your **Bookmarks**. There they live in folders of your own — nested as deep as you like, one bookmark in as
many folders as you want, dragged onto a folder to file it — each with a note of your own, found by words or by
kind, opened with a click where it belongs. They are kept in `bookmarks.json` in isnady's data folder (yours
alone, never published) and can be exported and imported as a file; a hadith is kept by its book and number, so a
bookmark survives a new import. `iy bookmark add hadith bukhari:1 --folder "Intention/Deeds" --note "…"`,
`iy bookmark list`, `iy bookmark folders`, `iy bookmark export file.json`.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/bookmarks.png" alt="Bookmarks — folders on the left, a hadith, a narrator, a scholar and a term with their folders and a note" width="850">
</p>

---

## 🧠 Search by meaning (AI)

Choose **Match → By meaning (AI)** to find hadith that say the same thing in other words or in
another language: `komşu hakları` finds the hadith on the neighbour's rights, a Turkish sentence
finds its Arabic original, and `إنما الأعمال بالنيات` gathers the narrations of the hadith on
intentions from every imported book. Each result shows how close it is in meaning (0–1), which says
nothing about authenticity.

The model is learnt on your computer from the texts you imported — Arabic beside its translations
is a parallel corpus, and cross-lingual latent semantic analysis learns the concepts the languages
share. Nothing is downloaded and no outside model is used. Measured on al-Bukhari and Abu Dawud: for
hadith the model never saw while learning, a Turkish translation finds its Arabic original first 68%
of the time and among the first ten 93% of the time (chance: 0.8%). For an exact quotation the
ordinary word search stays the better tool.

The same step finds the **other narrations of each hadith** across the imported books (takhrij):
every result card says where else it is narrated — *Also narrated in: Sahih al-Bukhari 5070 · 6689 ·
6953 | Sunan Abi Dawud 2201* — and each number opens that hadith. Only the texts are compared, never
the chains. In blind, hand-checked samples 34 of 35 pairs of the first kind and 18 of 20 of the
second were right.

```bash
pip install "isnady[ai]"        # numpy and scipy
iy ai build                     # a few seconds; or Tools → Build AI Indexes
iy search --mode meaning "komşu hakları"
iy tahric bukhari 1             # the other narrations of a hadith
```

---

## 🎨 Appearance and settings

Seven themes, chosen in **Edit → Preferences → Themes** — each shown as a small live isnady window —
or in **View → Theme**: *Lapis* (lapis and gold of illuminated manuscripts) and *Lapis Night*, which
"Follow system" switches between; *Paper* (warm cream and ink, for long reading); *Slate*;
*Emerald*; *Midnight*; and *High Contrast* (black, white and yellow, for low vision).

Every script has its own reading font, size, colour and line spacing — Arabic, Latin, Cyrillic,
Bengali and Tamil today. The light and the dark theme each keep their own colours, and the interface
font can be changed too. **Edit → Preferences** (Ctrl + ,) applies every change at once; each row
has its own Default button.

**Interface language** (sidebar, or **View → Interface Language**): menus, pages, buttons, messages and the
statistics are in **English, Türkçe and العربية** — Arabic right to left, the whole window mirrored. The list
already names 24 languages, each in its own name with how much of it is translated (Deutsch, Français,
Español, Português, Русский, Bahasa Indonesia, Bahasa Melayu, हिन्दी, اردو, বাংলা, 中文, 日本語, 한국어,
فارسی, دری, پښتو, Azərbaycanca, Oʻzbekcha, Bosanski, Kiswahili, Hausa); a text not translated yet is shown in
English, and the translations follow release by release. The window is rebuilt in the new language at once,
nothing to restart. `iy config set view.ui_language tr`. The hadith texts keep their own languages
(**Content languages**), the command line stays in English.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/preferences.png" alt="Preferences — font, size, line spacing and colour for each script" width="760">
</p>

**Settings → Books and languages** switches imported books on and off (Sunni and Shia apart) and
chooses the languages the texts are shown in; the others are folded behind an arrow on each hadith.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/books-languages.png" alt="Settings → Books and languages — books on and off, Sunni and Shia apart; the languages shown, the others folded behind an arrow" width="760">
</p>

```bash
iy config list --prefix text.arabic       # what is set, and what is changed
iy config set text.arabic.size 22
iy config set view.theme paper
iy config reset text.arabic               # back to the defaults
```

### Your data folder

Everything isnady keeps is in one folder — `iy datadir` shows it, `iy datadir /elsewhere` moves it,
and a folder named `isnady-data` beside a portable application is used instead:

| | |
|---|---|
| `isnady.db` | the database: books, texts, grades, chains, narrators (SQLite) |
| `derived/*.json` | statistics and models, computed once and kept |
| `settings.json` | appearance and other settings, shared by the window and the command line |
| `repos/`, `user_repositories.json` | the catalogs read from the repositories, and the repositories you added |
| `isnady.<date-time>.bak.db` | a database replaced by a ready one, kept |

---

## ⌨️ CLI

Everything the window does also works without it — on a server, over SSH, or in a script. The
command line never loads Qt. Every command that takes a book accepts its full name
(`musnad_ahmad_ibn_hanbal`) or its short key (`ahmad`).

| Short | Example | What it does |
|:------|:-----|:-------------|
| `iy` | `isnady` | Open the window |
| `iy search WORDS` | `iy search niyet --book abudawud` | Search; `--mode all\|any\|phrase\|meaning`, `--whole-words`, `--book`, `--language`, `--limit`; `--in narrators\|scholars`, `--tradition sunni\|shia` |
| `iy chain BOOK NUMBER` | `iy chain kafi 5:1740` | One chain, narrator by narrator, with who each one is and whom it reaches; `--raw` adds the wording |
| `iy isnads` | `iy isnads --rebuild` | Read every chain and report per book: split, reaching the Prophet or a Ma'sum, identified |
| `iy narrator NAME` | `iy narrator "Ibn Umar"` | A narrator: his critic's verdict (Ibn Hajar's rank, or the Imami terms), tabaqa, death year, books; `--limit 1` adds teachers, students and hadith |
| `iy book [KEY [CHAPTER]]` | `iy book bukhari 2` | The books; a book's chapters; a chapter read in order |
| `iy scholar [NAME]` | `iy scholar albani` | The scholars in the data, or one of them with his measured statistics |
| `iy tahric BOOK NUMBER` | `iy tahric bukhari 1` | Other narrations of a hadith in the imported books (takhrij) |
| `iy stats [SECTION]` | `iy stats graders --book abudawud` | `corpus`, `narrators`, `chains`, `grades`, `books`, `graders`, `model`, `lab`; `--csv DIR`, `--recompute` |
| `iy term [NAME]` | `iy term --search tadlis` | The glossary, English, Turkish or Arabic (`--lang tr`, `--lang ar`) |
| `iy tree WHICH [NAME]` | `iy tree family "Ibn Umar"` | Genealogies: `prophets`, `quraysh`, a narrator's `family`, his line of `learning` (`--depth`, `--width`) |
| `iy bookmark ACTION` | `iy bookmark add hadith bukhari:1 --folder Prayer` | Bookmarks: `list`, `folders`, `add`, `remove`, `export`, `import` |
| `iy ai build` | `iy ai status` | Learn the meaning index from the imported texts |
| `iy catalog list` | `iy catalog list --repo lk-hadith-corpus` | The books of the repository in use, and your own, with what is imported |
| `iy catalog import ID` | `iy catalog import sahih_muslim --language tur` | Import a book; `--all` imports every one; `remove`, `add`, `delete` manage the list |
| `iy repo [list\|use\|show\|add\|remove]` | `iy repo add ~/isnady-data` | The data repositories: isnady-data (default), the optional ones, yours — a GitHub or Hugging Face address, a URL, or a folder |
| `iy database [use FILE]` | `iy database use isnady-db-<date>.zip` | A ready database from a file; your own is kept beside it |
| `iy import FORMAT FILE-OR-URL` | `iy import isnady ~/my_book/book.json` | Import a file of your own; `--book`, `--language`, `--license`, `--user`, `--token-env`, `--api-key-env` |
| `iy sources` | | Imported sources, their licence and tier |
| `iy remove KEY` | | Remove a source and everything imported from it |
| `iy formats` | | The formats that can be imported |
| `iy datadir [FOLDER]` | `iy datadir /data/isnady` | Show or move the data folder; `--as-is`, `--default` |
| `iy config list\|get\|set\|reset` | | Settings — the same as Edit → Preferences |
| `iy shortcut` | `iy shortcut --no-desktop` | A desktop and applications-menu shortcut |
| `iy update` | | Update every copy of isnady where it is installed |
| `iy doctor` | | Every copy of isnady on this computer and which one each command starts |
| `iy -V` / `iy -h` | | Version / help |

```console
$ iy search niyet --book abudawud --limit 1
43 hadith found in 8 ms

Sunan Abu Dawud #472
  grades: Al-Albani: Hasan; Muhammad Muhyi Al-Din Abdul Hamid: Hasan; Shuaib Al Arnaut: Daif; Zubair Ali Zai: Daif
  [Turkish] Ebu Hureyre (r.a.); Resulullah (Sallallahu aleyhi ve Sellem)'in şöyle buyurduğunu rivayet etmiştir: "Bir kimse mescid'e hangi [niyet]le gelirse nasibi ondan ibarettir"
```

---

## 📸 More screenshots

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/search-grades.png" alt="Search — Sunan Abi Dawud with each scholar's grade and the chain above the text" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/chain-dark.png" alt="Dark theme — a seven-narrator chain from Sunan Abi Dawud" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/chains-overview.png" alt="Chains overview — per-book statistics and what was kept whole" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/books-taqrib.png" alt="Books — Ibn Hajar's Taqrib read letter by letter, each entry a click from its narrator" width="850">
</p>

---

## 🗺️ Roadmap

- **Shia narrators, further** — al-Tusi's *Rijal* and *Fihrist* and al-Kashshi's reports; names
  resolved by teacher and student; a Sunni–Shia comparison.
- **More in isnady-data** — al-Tusi's *Tahdhib al-Ahkam* and *al-Istibsar*, al-Saduq's *Man la
  yahduruhu al-faqih*; al-Hakim's *Mustadrak*, al-Bayhaqi's *Sunan*, the *Mu'jam*s.
- **Narrators** — the other half of the names identified through teachers and students (al-Mizzi's
  *Tahdhib al-Kamal*), the verdicts of other critics beside Ibn Hajar's, and whether each link could
  have met the next; fuller, richer lives of narrators and scholars.
- **Statistics in plain words** — every finding said simply first, the method after.
- **Settings and export** — every setting in one place, export in every common format (named by the
  books' full names), reset and remove from inside the window.
- **Every interface language in full** — the 21 listed after English, Türkçe and العربية; the command line
  and the glossary in them too.
- **isnady.net** — the same engine on the web.

---

## 🔁 Versions and releases

One version number on GitHub, PyPI and npm, always. A release builds the Python package and the
Windows, Linux and macOS applications first; only when every build succeeds is anything published —
PyPI, then the [GitHub Release](https://github.com/bayramkotan/isnady/releases) with every file and
its checksum. What each version brought is in the
[CHANGELOG](https://github.com/bayramkotan/isnady/blob/main/CHANGELOG.md). The README on npm is made
from this one. The data has its own rhythm: a book added to
[isnady-data](https://github.com/bayramkotan/isnady-data) needs no new version of isnady.

## 🏗️ Build from Source

```bash
git clone https://github.com/bayramkotan/isnady.git
cd isnady
pip install -e .
iy
```

Python 3.10 or newer and PySide6. The command line alone needs no PySide6. The desktop application
of your own system: `pip install ".[ai]" pyinstaller`, then
`python packaging/build_app.py linux|windows|macos VERSION`.

The data repository is built by two tools in this one: `tools/build_data_repo.py --mirror DIR`
converts every source into isnady-data, and `tools/publish_database.py DIR` prepares a ready
database for its Releases.

## 📝 License

MIT for the application code. Hadith data comes from separate sources, each under its own licence,
recorded with the data and listed under **Help → Licences**.

The Arabic and reading typeface is [Amiri](https://github.com/aliftype/amiri) by Khaled Hosny,
bundled under the SIL Open Font License 1.1 (`src/isnady/assets/fonts/OFL.txt`).
