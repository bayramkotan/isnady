<h1 align="center">📜 isnady &nbsp;<sub>إسناد</sub></h1>

<p align="center">
  <strong>Hadith search built around the isnad, the chain of transmission</strong><br>
  <sub>Search the collections, read every chain narrator by narrator, and see how the scholars read it</sub>
</p>

<p align="center">
  <a href="https://pypi.org/project/isnady/">
    <img src="https://img.shields.io/badge/PyPI-v0.1.8-1D4777?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI">
  </a>
  <img src="https://img.shields.io/pypi/pyversions/isnady?style=for-the-badge&color=A47E24&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-5B6878?style=for-the-badge" alt="Platform">
  <a href="https://www.npmjs.com/package/isnady">
    <img src="https://img.shields.io/badge/npm-v0.1.8-14304F?style=for-the-badge&logo=npm" alt="npm">
  </a>
  <img src="https://img.shields.io/badge/License-MIT-D6B25E?style=for-the-badge" alt="License">
</p>

<p align="center">
  <a href="#-why-isnady">Why</a> •
  <a href="#-install">Install</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-search">Search</a> •
  <a href="#-narrators">Narrators</a> •
  <a href="#-hadith-scholars">Scholars</a> •
  <a href="#-books">Books</a> •
  <a href="#-sunni-and-shia-two-roads">Sunni and Shia</a> •
  <a href="#-statistics">Statistics</a> •
  <a href="#-learn">Learn</a> •
  <a href="#-search-by-meaning-ai">Meaning (AI)</a> •
  <a href="#-chains-of-transmission">Chains</a> •
  <a href="#-educational-by-design">Educational</a> •
  <a href="#-appearance">Appearance</a> •
  <a href="#-data-and-licences">Data</a> •
  <a href="#%EF%B8%8F-cli">CLI</a> •
  <a href="#-screenshots">Screenshots</a> •
  <a href="#%EF%B8%8F-roadmap">Roadmap</a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/search-arabic.png" alt="Searching النيات finds بالنيات in Sahih al-Bukhari 1, with the chain above the text" width="850">
</p>

> **Pre-alpha (0.1.8).** Search and chains of transmission work today, on data you import
> in one command. Narrators, scholars, gradings and the rest are being built, in the open.

---

## 🎯 Why isnady

A hadith is two things: the text (*matn*) and the chain of people who passed it on
(*isnad*). Most hadith sites let you search the text and show a grade. isnady is built
the other way round: the chain comes first, because that is where the scholars of hadith
did their work.

- **The chain is read, not typed in.** isnady reads the chain from the Arabic text itself:
  who narrated to whom, with which words, and whether it reaches the Prophet.
- **Nothing is guessed.** Where the wording cannot be read with confidence, the chain is
  kept whole and marked, never split wrongly. A missing link is shown as missing.
- **Every fact has a source.** Every hadith, text and grade records where it came from,
  under which licence.
- **Grades are shown as the scholars gave them.** Each grade keeps its scholar's name and
  wording; isnady does not merge them or invent its own.
- **Window and command line, same engine.** Everything the window does, the command line
  does too, with the same results.

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

### Something not right?

`iy update` updates every copy of isnady where it is installed. `iy doctor` lists every copy and
which one each command really starts — an older copy in the user folder can start before a newer
one elsewhere, so every copy is kept at the same version. The same report is under
**Help → Check Installation**. If an old copy starts even for `iy update`, run
`python3 -s -m isnady update` (Windows: `py -s -m isnady update`).

### Upgrading

```bash
iy update
```

Your data stays where it is; a newer isnady upgrades the database in place the first time
it opens it.

---

## 🚀 Quick Start

isnady ships without hadith data; it reads it from a **data repository**. The default is
isnady's own, [**bayramkotan/isnady-data**](https://github.com/bayramkotan/isnady-data), which
holds every Sunni and Shia collection and rijal work isnady can read — 35 sources, from Sahih
al-Bukhari to al-Kafi (see [Data sources](#-data-sources) below). Open the window with `iy`,
choose **File → Data Sources**, and import any of them with one click — or **Import all** — in
the languages you tick. The same from the command line:

```bash
iy catalog list                         # the sources of the repository in use
iy catalog import sahih_al_bukhari --language ara --language tur
iy catalog import musnad_ahmad_ibn_hanbal
iy catalog import al_kafi_al_kulayni    # with al-Majlisi's and al-Behbudi's grades
iy catalog import taqrib_al_tahdhib_ibn_hajar_al_asqalani   # identifies the narrators in the chains
iy catalog import --all                 # everything
```

Other repositories can be chosen instead — the datasets others publish on GitHub and Hugging
Face are in the list — and any repository with an isnady catalog can be added
(`iy repo add https://github.com/owner/name`). Your own files and links can be added too, and
the data folder can be moved anywhere you like.

On the command line:

```bash
iy search النيات            # Arabic, with or without diacritics
iy search "niyetlere göre"   # Turkish, English, any imported language
iy chain bukhari 1           # one chain, narrator by narrator
```

Importing takes a minute or two; the search index and the chains are built as part of it.

With Ibn Hajar's *Taqrib al-Tahdhib* imported (8,824 narrators, his verdict on each), every
chain is read narrator by narrator: `iy narrator الزهري`.

No network? Read the books from a copy of isnady-data on this computer (`iy repo add ~/Github/isnady-data`), or take a whole ready database from a file (`iy database use isnady-db-2026-10-10.zip`).

---

## 🔎 Search

| | |
|:--|:--|
| **Arabic without diacritics** | `الاعمال` finds `الأَعْمَالُ`. Alef forms, alef maqsura, hamza seats and ta marbuta are treated alike, so you type the way you normally write |
| **Attached prefixes** | `النيات` finds `بالنيات`, because Arabic joins bi-, wa-, fa- and al- to the word. *Whole words only* turns this off |
| **Latin-script text** | Case and accents are ignored: `NIYET`, `niyet` and `nîyet` are one word; `Muʿādh`, `Mu'adh` and `Muadh` too |
| **Match** | All words, any word, or the exact phrase |
| **Books** | All books, all Sunni, all Shia, or any few ticked one by one — Sunni collections listed first, Shia after them |
| **Language** | One language to search in; the languages you do not read are folded behind an arrow on each hadith (**Settings → Books and languages**), a click opens them |
| **Active books** | A book can be switched off in **Settings → Books and languages**: it stays imported but is left out of searches, book lists and statistics until switched on |
| **Grades** | Shown under each hadith with the scholar's name, exactly as given |
| **Highlighting** | On the original, diacritised text, diacritics included |

Results appear at once and fill in as you read; the window never waits for them.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/search-folded.png" alt="Search in two books with Arabic chosen: the English and Turkish texts folded behind ▸ Other languages, opened with a click" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/book-picker.png" alt="Books — tick all books, all Sunni, all Shia, or any few one by one" width="420">
</p>

### 👥 Narrators

The **Narrators** page lists every narrator of the imported rijal work — 8,824 from Ibn
Hajar's *Taqrib* — searchable in Arabic or in Latin letters (`Abu Hurayra`, `Zuhri`, `Ibn Umar`),
and filtered by tabaqa, rank and book. For each narrator: Ibn Hajar's verdict and its rank, the
tabaqa and death year, the books his hadith appear in, **whom he narrates from and who
narrates from him** in the imported chains, the compilers who narrate from him directly, and
every hadith whose chain includes him. On the Isnad Chains page a click on a narrator's name
opens him here.

Each narrator — and each scholar — is shown by the name he is **known by** (al-A'mash, Ibn 'Umar,
Abu Hurayra), with his full name and every part of it laid out: name, lineage, kunya, by-name,
nisbas, client of; the part he is known by is marked ★.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/narrators.png" alt="Narrators — 'Abdullah b. 'Umar: Ibn Hajar's verdict, tabaqa, death year, teachers and students in the chains" width="850">
</p>

### 🎓 Hadith Scholars

The scholars whose work is in the imported data, and what the data measures of it:
**compilers** (their collection, the teachers their chains begin with, the Companions they end
with), **graders** (how they grade, and how far they agree with each other on the same hadith —
agreement, Cohen's kappa, and a strictness index: the classical *mutashaddid* / *mutasahil*,
measured), and **critics** of narrators (Ibn Hajar's twelve ranks). On Sunan Abi Dawud, for
example, Zubair 'Ali Za'i grades most strictly (−0.21) and agrees with al-Albani on 70% of the
hadith; the page also flags a pair of graders whose 98% agreement suggests the source did not keep
them independent.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/scholars.png" alt="Hadith Scholars — al-Albani: his grades on Sunan Abi Dawud and his agreement with the other graders" width="850">
</p>

### 📚 Books

isnady is not only for searching: the **Books** section opens every imported work and reads it in
its own order. A hadith collection reads chapter by chapter, each hadith with its card (chain,
narrators, other narrations, grades) and the languages you choose; Ibn Hajar's *Taqrib* reads
letter by letter and name by name, each entry with its narrator a click away. Find within a
chapter, go to the previous or next one, and isnady remembers where you were. From any search
result, **In its book** opens the hadith where it stands, among the hadith of its chapter.

Books are not tied to hadith collections: a work is a tree of any depth (volume, book, chapter,
section) whose leaves are hadith, narrators' entries or paragraphs — so the commentaries, manuals
of fiqh and other works of the scholars can be read the same way as they are added.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/books.png" alt="Books — reading Sahih al-Bukhari chapter by chapter, Arabic and Turkish, each hadith with its chain" width="850">
</p>

```bash
iy book                      # the books
iy book bukhari              # its chapters
iy book bukhari 2 --language Turkish
iy book taqrib 1
```

### 🕌 Sunni and Shia: two roads

Sunni and Shia narrators meet on one **Narrators** page — *All*, *Sunni* or *Shia* at the top of the
list — and every Shia narrator carries a gold **Shia** tag. They meet without being mixed: each value
isnady derives is reached along the road of the book's own tradition.

| | Road A — Sunni books | Road B — Shia books |
|---|---|---|
| How a chain opens | a transmission term on every link (حدثنا، أخبرنا، عن …) | al-Kulayni names his teacher without a term (علي بن إبراهيم عن أبيه …) |
| Groups and joined roads | two narrators at one link (qiran) | "عدة من أصحابنا" — al-Kulayni's groups, with the teachers he said they stand for; "… جميعاً عن …", two roads joined; "رفعه"; "عن رجل" |
| Where it ends | the Prophet ﷺ | one of the Fourteen Ma'sumun: the Prophet ﷺ or an Imam, most often by his kunya — أبو عبد الله is Ja'far al-Sadiq, أبو جعفر al-Baqir, أبو الحسن al-Kazim or al-Rida; "سألته" is *mudmar* |
| Who identifies its narrators | Ibn Hajar's *Taqrib al-Tahdhib* | only the Shia rijal works: al-Najashi's *Rijal* (al-Tusi's next) |
| How a narrator is judged | Ibn Hajar's twelve ranks | the Imami critics' own terms — **reliability** (*thiqa*; praised — *jalil*, *wajh*, *'ayn*; weak) and **creed** (Imami, or Waqifi, Fathi, Zaydi, *'ammi* …): an Imami *thiqa*, a praised narrator (*mamduh*), a *thiqa* of another school (*muwaththaq*), a weak one |

Nothing is mapped onto the other tradition's measure, and a narrator of one tradition is never a
candidate for a link of the other's chains. Read this way, **96.8%** of al-Kafi's 14,239 chains split
into their narrators (it was 9 chains when they were read the Sunni way), **92%** reach a
Ma'sum, and half of their 61,160 names are already identified in al-Najashi's *Rijal* (from 3).

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/chain-shia.png" alt="A chain of al-Kafi read the Shia way: al-Kulayni's group of teachers, the narrators judged by al-Najashi, ending at Imam Ja'far al-Sadiq" width="850">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/narrators-shia.png" alt="Narrators — Zurara b. A'yan, a Shia narrator: al-Najashi's words and their reading in the Imami terms" width="850">
</p>

```bash
iy search "زرارة" --in narrators --tradition shia
iy isnads                    # per book: chains split, and whom they reach — the Prophet, or a Ma'sum on road B
iy chain kafi 5:1740
```

Next: al-Tusi's *Rijal* and *Fihrist* (and al-Kashshi's reports), names resolved by teacher and
student, and statistics of the Shia books by the Imami scholars' grades (al-Majlisi, al-Behbudi).

### 📊 Statistics

Measured in depth, each figure with what it means and how sure it is. Grades are ordered
categories, so they are never turned into numbers or averaged. The first tab, **Graders**, takes
the scholars who graded a book (al-Albani, Shu'ayb al-Arna'ut, Zubair 'Ali Za'i, Muhammad Muhyi
al-Din 'Abd al-Hamid on Sunan Abi Dawud) and shows:

- agreement of every pair — same grade, Cohen's kappa and the ordinal kappa — with 95% intervals,
  and Krippendorff's alpha for all of them together;
- a **Dawid–Skene model** of each hadith's true grade: each grader's confusion matrix (how he grades
  a hadith of each true grade) and, for every hadith, how sure the model is;
- **strictness** — the classical *mutashaddid* and *mutasahil*, measured by order only, with intervals;
- the **disputed hadith**, where the scholars are furthest apart — a double-click opens one in its book.

Two graders who agree far too often to be independent (98.1%) count as one voice in the model,
and the page says so. Results are computed once and kept in a file. `iy stats graders`.
Narrators, books, hadith, chains, correlations and the models follow, tab by tab. **Correlations
and tests** sets every measure against every other — Spearman's ρ with Benjamini–Hochberg q-values,
and the partial ρ with all the others held equal (what each factor of the chain says of each
scholar's grade on its own) — and tests what differs: the scholars' grades pair by pair
(Stuart–Maxwell), the books (Kruskal–Wallis, Mann–Whitney with Cliff's δ), and whether the hadith
model's shape holds (Brant's test). `iy stats lab`.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/statistics.png" alt="Statistics — Narrators: the busiest 10% of narrators carry 75% of the transmission; the Lorenz curve and the pillars" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/statistics-model.png" alt="The hadith model — for al-Albani, a weak or unknown weakest narrator multiplies the odds of a weaker grade by 14; odds ratios with 95% intervals" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/statistics-lab.png" alt="Correlations and tests — each factor against each scholar's grade with the others held equal (partial Spearman's rho), Sunan Abi Dawud" width="850">
</p>

### 🎓 Learn

The terms of hadith and its sciences, written for isnady with their classical sources: 81 terms —
the grades (sahih, hasan, da'if, mawdu', shadhdh, munkar, mu'allal), the kinds of hadith by their
chain (mutawatir, mursal, munqati', mu'allaq, mudallas …), chain and text (mutaba'a, shahid,
takhrij, madar), the ways of receiving (sama', ijaza, haddathana, 'an), judging narrators (the
twelve ranks of Ibn Hajar, thiqa, saduq, majhul, matruk, mudallis), generations, the parts of an
Arabic name, Imami rijal, the books, and isnady's own measures. Each with its Arabic, a one-line
and a longer definition in **English or Turkish**, related terms one click away, and its source.
The grades on every result explain themselves when you point at them. `iy term mursal --lang tr`.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/learn.png" alt="Learn — the term mursal: Arabic, definition, related terms and source" width="850">
</p>

### 🧠 Search by meaning (AI)

Choose **Match → By meaning (AI)** to find hadith that say the same thing in other words or in
another language: `komşu hakları` finds the hadith on the neighbour's rights, a Turkish sentence
finds its Arabic original, and `إنما الأعمال بالنيات` gathers the narrations of the hadith on
intentions from every imported book. Each result shows how close it is in meaning (0–1), which
says nothing about authenticity.

The model is learnt on your computer from the texts you imported — Arabic beside its
translations is a parallel corpus, and cross-lingual latent semantic analysis learns the
concepts the languages share. Nothing is downloaded and no outside model is used. Measured on
al-Bukhari and Abu Dawud: for hadith the model never saw while learning, a Turkish translation
finds its Arabic original first 68% of the time and among the first ten 93% of the time (chance:
0.8%). For an exact quotation the ordinary word search stays the better tool.

The same step finds the **other narrations of each hadith** across the imported books
(takhrij): every result card says where else it is narrated — *Also narrated in: Sahih
al-Bukhari 5070 · 6689 · 6953 | Sunan Abi Dawud 2201* — and each number opens that hadith.
Only the texts are compared, never the chains; upright numbers share the text, italic ones
probably report the same event from the same Companion. In blind, hand-checked samples 34 of
35 pairs of the first kind and 18 of 20 of the second were right.

```bash
pip install "isnady[ai]"        # numpy and scipy
iy ai build                     # a few seconds; or Tools → Build AI Indexes
iy search --mode meaning "komşu hakları"
iy tahric bukhari 1             # the other narrations of a hadith
```

---

## 🔗 Chains of transmission

Every Arabic text is read for its chain:

```
Sahih al Bukhari 1
   1. حدثنا (narrated to us)  الْحُمَيْدِيُّ عَبْدُ اللَّهِ بْنُ الزُّبَيْرِ
   2. حدثنا (narrated to us)  سُفْيَانُ
   3. حدثنا (narrated to us)  يَحْيَى بْنُ سَعِيدٍ الْأَنْصَارِيُّ
   4. أخبرني (informed me)    مُحَمَّدُ بْنُ إِبْرَاهِيمَ التَّيْمِيُّ
   5. سمع (heard)            عَلْقَمَةَ بْنَ وَقَّاصٍ اللَّيْثِيَّ
   6. سمعت (I heard)          عُمَرَ بْنَ الْخَطَّابِ
      -> the Prophet
```

In the window, each result shows its chain as a row of names ending at the Prophet, and
**View chain** opens it as a timeline from the book to the Prophet, with the Arabic text
below: the chain in lighter ink, the text of the hadith in full ink.

### 👤 Who each narrator is

With Ibn Hajar's *Taqrib al-Tahdhib* imported, every name in a chain is matched to a
narrator, and the chain shows what Ibn Hajar says of him: his verdict in his own words, its
rank on Ibn Hajar's twelve-step scale, the narrator's *tabaqa* (generation) and his death
year.

A name is linked only when the evidence leaves one person: the words of the name, the book
marks (a narrator in al-Bukhari must be one Ibn Hajar marks خ), the order of generations
along the chain, and the last link before the Prophet being a Companion. When several
narrators remain — "Sufyan" can be al-Thawri or Ibn 'Uyayna — the chain says so and names
how many, rather than choosing one. Today about half of all names are identified; in blind,
hand-checked samples of the identified ones, the last fifty were all correct.

Names are kept exactly as written, with the clarifications the compilers added
(*"— yaʿnī Ibn Muḥammad —"*, *"mawlā Ibn ʿAbbās"*), because identifying each narrator is
a separate step that comes next.

<details>
<summary><b>📊 How well it reads today</b></summary>
<br>

Measured on Sahih al-Bukhari and Sunan Abi Dawud (12,852 chains):

| | Bukhari | Abu Dawud | Both |
|:--|:--:|:--:|:--:|
| Split into narrators | 85.5% | 71.9% | 79.9% |
| Of those, reaching the Prophet | | | 78.3% |
| Narrators per chain | | | 5.0 |

In a blind, hand-checked sample of 30 chains: **no wrong narrator**, 27 complete.

The rest are kept whole, each with its reason: *tahwil* (ح, a second chain joining), two
teachers at one link (*qiran*), a second chain after the first, or wording that could not be
read with confidence. Abu Dawud uses *qiran* and *tahwil* far more often than Bukhari, which
is why its share is lower. One known limit: a last narrator introduced only by *qāla*
("قال قال عبد الله") is not added, because the same words also begin stories.

</details>

---

## 🎓 Educational by Design

isnady teaches the science it uses. Every transmission term in a chain explains itself:

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

The Learn section — hadith terminology, grading, *jarḥ wa taʿdīl* and the classical works,
each shown on real hadith and real chains — is on the roadmap.

---

## 🎨 Appearance

Seven themes, chosen in **Edit → Preferences → Themes** — each shown as a small live isnady window —
or in **View → Theme**: *Lapis* (lapis and gold of illuminated manuscripts) and *Lapis Night*, which
"Follow system" switches between; *Paper* (warm cream and ink, for long reading); *Slate* (quiet and
modern, with a light sidebar); *Emerald*; *Midnight* (deep dark with teal); and *High Contrast*
(black, white and yellow, for low vision). `iy config set view.theme paper`.

Every script has its own reading font, size, colour and line spacing — Arabic, Latin,
Cyrillic, Bengali and Tamil today, more as sources in other scripts arrive. The light and
the dark theme each keep their own colours, and the interface font can be changed too.
**Edit → Preferences** (Ctrl + ,) applies every change at once; each row has its own
Default button.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/preferences.png" alt="Preferences — font, size, line spacing and colour for each script" width="760">
</p>

**Settings → Books and languages** switches imported books on and off (Sunni and Shia apart) and
chooses the languages the texts are shown in; the others are folded behind an arrow on each hadith.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/books-languages.png" alt="Settings → Books and languages — books on and off, Sunni and Shia apart; the languages shown, the others folded behind an arrow" width="760">
</p>

The same settings from the command line:

```bash
iy config list --prefix text.arabic       # what is set, and what is changed
iy config set text.arabic.size 22
iy config set text.latin.family "Noto Serif"
iy config set colors.dark.gilt "#5A4A1E"  # matched words in the dark theme
iy config reset text.arabic               # back to the defaults
```

Settings live in `settings.json` in the isnady data folder, shared by the window and the
command line.

---

## 📚 Data sources

isnady reads its sources from a **repository**: a `catalog.json` listing books and rijal works,
where each file is, its format, its licence and its tradition. Choose one in **Settings → Data
sources** (or `iy repo use ID`); add your own with **Add a repository…** (`iy repo add URL`: a
GitHub repository, a Hugging Face dataset, a catalog URL or a folder).

**The default — [isnady-data](https://github.com/bayramkotan/isnady-data)** holds every source
below in one place and in isnady's own format, each book in a folder named by its full title and
its compiler — `sunni/sahih_al_bukhari/`, `sunni/musnad_ahmad_ibn_hanbal/`, `shia/al_kafi_al_kulayni/`
(a `book.json` and one file per language) — and the works on the narrators in `rijal/sunni/`,
`rijal/shia/`.

| | Sunni | Shia |
|---|---|---|
| **Hadith** | Sahih al-Bukhari, Sahih Muslim, Sunan Abi Dawud, Jami' al-Tirmidhi, Sunan al-Nasa'i, Sunan Ibn Maja, the Muwatta, the Forty of al-Nawawi, Forty Hadith Qudsi, the Forty of Shah Waliullah — Arabic and up to eight translations, with grades · Musnad Ahmad, Sunan al-Darimi · Riyad al-Salihin, al-Shama'il al-Muhammadiyya, Bulugh al-Maram, al-Adab al-Mufrad, Mishkat al-Masabih | al-Kulayni's al-Kafi (8 volumes, with al-Majlisi's and al-Behbudi's grades) · al-Saduq's 'Uyun Akhbar al-Rida, al-Amali, al-Khisal, al-Tawhid, Ma'ani al-Akhbar, Thawab al-A'mal, Sifat al-Shi'a, Fada'il al-Shi'a · al-Mufid's al-Amali · Ibn Qulawayh's Kamil al-Ziyarat · al-Nu'mani's and al-Tusi's Kitab al-Ghayba · al-Ahwazi's al-Mu'min and al-Zuhd · al-Muhsini's Mu'jam al-Ahadith al-Mu'tabara — Arabic and English |
| **Narrators** | Ibn Hajar, *Taqrib al-Tahdhib* | al-Najashi, *Rijal* |

The credits for where each text was first published are in the repository's README.

**On this computer, without the network:** a copy of isnady-data (a `git clone`, a USB stick,
a shared folder) is a repository too — **A folder on this computer…** in Settings → Data sources,
or `iy repo add ~/Github/isnady-data` — and every book is then read from that folder. A whole
ready database can be taken from a file as well — the `isnady-db-<date>.zip` of the
[isnady-data Releases](https://github.com/bayramkotan/isnady-data/releases), or an `isnady.db` —
with **Use a ready database…** (Data folder) or `iy database use FILE`: it is checked (and its
sha256 against the `database.json` beside it), takes the place of your database at the next start,
and your database is kept beside it.

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/data-sources.png" alt="Settings → Data sources — the repository (isnady-data by default, a folder on this computer, or one you add) and its books, Sunni and Shia apart" width="760">
</p>

**Optional repositories**, each the dataset as its authors publish it (their books under their
own keys, e.g. `bukhari-lk`, so editions with other numbering never mix):

| Repository | What it holds | Licence |
|---|---|---|
| [fawazahmed0/hadith-api](https://github.com/fawazahmed0/hadith-api) | 10 collections, Arabic + 8 languages, grades | Unlicense |
| [Thaqalayn](https://github.com/MohammedArab1/ThaqalaynAPI) | 16 Shia collections, Arabic + English, grades of al-Kafi | not stated (from thaqalayn.net) |
| [Open Hadith Data](https://github.com/mhashim6/Open-Hadith-Data) | the nine books in Arabic with diacritics, seven with a commentary of every hadith | ODbL |
| [hadith-json](https://github.com/AhmedBaset/hadith-json) | 17 books, Arabic + English (50,884 hadith, from sunnah.com) | not stated |
| [LK Hadith Corpus](https://github.com/ShathaTm/LK-Hadith-Corpus) | the six books, Arabic + English, isnad and matn marked apart, grades | not stated (cite the authors' paper) |
| [Hugging Face — meeAtif/hadith_datasets](https://huggingface.co/datasets/meeAtif/hadith_datasets) | the six books, Arabic + English, chapter titles, grades | MIT (as declared; text from sunnah.com) |
| [Hadith-Data-Sets](https://github.com/abdelrahmaan/Hadith-Data-Sets) | the nine books in Arabic (62,169 hadith) | not stated |
| [OpenITI](https://github.com/OpenITI) | the Taqrib and al-Najashi's Rijal | not stated in the repository |

Every source records a licence **tier**: **A** may be redistributed, **B** may be redistributed
under its conditions, **C** may not. Sources you add yourself stay on your computer. **Help →
Licences** lists every source in your database with its licence. Any CSV or JSON table of hadith
can be read through a catalog that names its columns (format `table`); the fawazahmed0 JSON
format, OpenITI mARkdown (the Taqrib, al-Najashi) and files of your own with or without
authentication (credentials are never stored) are read as well.

---

## ⌨️ CLI

Everything the window does also works without it — on a server, over SSH, or in a
script. The command line never loads Qt.

| Short | Full | What it does |
|:------|:-----|:-------------|
| `iy` | `isnady` | Open the window |
| `iy search WORDS` | `isnady search WORDS` | Search; `--mode all\|any\|phrase`, `--whole-words`, `--book`, `--language`, `--limit` |
| `iy chain BOOK NUMBER` | `isnady chain bukhari 1` | One chain, narrator by narrator, with who each one is; `--raw` adds the wording |
| `iy isnads` | `isnady isnads` | Read every chain and report per book; `--rebuild` reads them again |
| `iy ai build` | `isnady ai build` | Learn the meaning index from the imported texts (`iy ai status` to check) |
| `iy import najashi FILE` | `isnady catalog import najashi` | al-Najashi's Rijal: Shia narrators read on the Imami scale, and the book |
| `iy shortcut` | `isnady shortcut --no-desktop` | A desktop and applications-menu shortcut, with isnady's icon |
| `iy term [NAME]` | `isnady term --search tadlis` | The glossary: a term's meaning, English or Turkish (`--lang tr`) |
| `iy stats graders` | `isnady stats graders --book abudawud` | The graders of a book in depth: agreement, model, strictness |
| `iy stats model` | `isnady stats model --grader albani` | What each scholar's grade follows: ordinal regression, odds ratios, surprises |
| `iy stats lab` | `isnady stats lab --csv ./lab` | Correlations (Spearman, partial, BH q) and tests (Stuart–Maxwell, Kruskal–Wallis, Mann–Whitney, Brant) |
| `iy book [KEY [CHAPTER]]` | `isnady book bukhari 2` | The books; a book's chapters; a chapter read in order |
| `iy scholar [NAME]` | `isnady scholar albani` | The scholars in the data, or one of them with his measured statistics |
| `iy tahric BOOK NUMBER` | `isnady tahric bukhari 1` | Other narrations of a hadith in the imported books (takhrij) |
| `iy search --mode meaning WORDS` | `isnady search --mode meaning "komşu hakları"` | Search by meaning and across languages |
| `iy narrator NAME` | `isnady narrator "Ibn Umar"` | A narrator: Ibn Hajar's verdict and rank, tabaqa, death year, books, other names; with `--limit 1` also teachers, students and hadith |
| `iy import FORMAT FILE-OR-URL` | `isnady import …` | Import a source; `--book`, `--language`, `--license`, `--user`, `--token-env`, `--api-key-env` |
| `iy repo [list\|use\|show\|add\|remove]` | `isnady repo add ~/Github/isnady-data` | The data repositories: isnady's own (default), the optional ones, yours — a GitHub or Hugging Face address, a URL, or a folder on this computer |
| `iy database [use FILE]` | `isnady database use isnady-db-2026-10-10.zip` | A ready database from a file on this computer (`isnady.db` or the zip of the isnady-data Releases); your own is kept beside it |
| `iy catalog list` | `isnady catalog list --repo lk-hadith-corpus` | The sources of the repository in use, and your own, with what is imported — the same as File → Data Sources |
| `iy catalog import ID` | `isnady catalog import sahih_muslim --language tur` | Import a listed source; `remove`, `add`, `delete` manage the list |
| `iy catalog import --all` | `isnady catalog import --all --language ara` | Every source of the repository at once |
| `iy datadir [FOLDER]` | `isnady datadir /data/isnady` | Show or change where the database and settings live; `--as-is`, `--default` |
| `iy formats` | `isnady formats` | Formats that can be imported |
| `iy sources` | `isnady sources` | Imported sources, their licence and tier |
| `iy stats` | `isnady stats` | Hadith, texts, grades and chains per book |
| `iy remove KEY` | `isnady remove KEY` | Remove a source and everything imported from it |
| `iy config list\|get\|set\|reset` | `isnady config …` | Appearance and other settings — the same as Edit → Preferences |
| `iy update` | `isnady update` | Update every copy of isnady where it is installed (system, user, venv, pipx, clone) |
| `iy doctor` | `isnady doctor` | Every copy of isnady on this computer and which one each command starts |
| `iy -V` | `isnady -V` | Show the version (also `-v`, `--version`, `version`) |
| `iy -h` | `isnady -h` | Show help |

```console
$ iy search niyet --book abudawud --limit 1
43 hadith found in 8 ms

Sunan Abu Dawud #472
  grades: Al-Albani: Hasan; Muhammad Muhyi Al-Din Abdul Hamid: Hasan; Shuaib Al Arnaut: Daif; Zubair Ali Zai: Daif
  [Turkish] Ebu Hureyre (r.a.); Resulullah (Sallallahu aleyhi ve Sellem)'in şöyle buyurduğunu rivayet etmiştir: "Bir kimse mescid'e hangi [niyet]le gelirse nasibi ondan ibarettir"
```

---

## 📸 Screenshots

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/chain.png" alt="Isnad Chains — the chain of Sahih al-Bukhari 1 as a timeline from the book to the Prophet" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/search-grades.png" alt="Search — Sunan Abi Dawud with each scholar's grade and the chain above the text" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/chain-dark.png" alt="Dark theme — a seven-narrator chain from Sunan Abi Dawud" width="850">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/chains-overview.png" alt="Chains overview — per-book statistics and what was kept whole" width="850">
</p>

---

## 🗺️ Roadmap

- **Narrators** — the other half of the names identified through teachers and students
  (al-Mizzi's *Tahdhib al-Kamal*), the verdicts of other critics beside Ibn Hajar's, and
  whether each link could have met the next.
- **Hadith scholars** — their lives in full, and more scholars as more collections and grades
  are imported.
- **Shia rijal** — narrator verdicts from the Shia rijal works, beside the Sunni view.
- **Learn** — the sciences of hadith, shown on real hadith and real chains.
- **More sources and formats** — and adding your own from inside the window.
- **Glossary** — every Arabic term of hadith and the Islamic sciences explained where it
  appears: hover or click a term, read its meaning in the interface language.
- **isnady.net** — the same engine on the web.

---

## 🔁 Versions and releases

One version number on GitHub, PyPI and npm, always. A release builds the Python package and the Windows,
Linux and macOS applications first; only when every build succeeds is anything published — PyPI, then the
[GitHub Release](https://github.com/bayramkotan/isnady/releases) with every file and its checksum. What each
version brought is in the [CHANGELOG](https://github.com/bayramkotan/isnady/blob/main/CHANGELOG.md). The
README on npm is made from this one.

## 🏗️ Build from Source

```bash
git clone https://github.com/bayramkotan/isnady.git
cd isnady
pip install -e .
iy
```

Python 3.10 or newer and PySide6. The command line alone needs no PySide6.

---


The desktop application of your own system: `pip install ".[ai]" pyinstaller`, then
`python packaging/build_app.py linux|windows|macos VERSION`.

## 📝 License

MIT for the application code. Hadith data comes from separate sources, each under its own
licence, recorded with the data and listed under **Help → Licences**.

The Arabic and reading typeface is [Amiri](https://github.com/aliftype/amiri) by Khaled
Hosny, bundled under the SIL Open Font License 1.1 (`src/isnady/assets/fonts/OFL.txt`).
