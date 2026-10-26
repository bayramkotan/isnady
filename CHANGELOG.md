# Changelog

Every release of isnady carries one version number on GitHub, PyPI and npm. The text of each GitHub Release
is taken from its section here.

## [0.5.6] — 2026-10-27

- **Search by grade (GR-FLT, Bayram 2026-10-27: "sadece sahih ya da hasen arayabilirim, ya da her ikisi, ya da daha
  fazlasi").** A **Grade** choice beside Books on the Search page, and `--grade` for `iy search`: only sahih, only
  hasan, both, or any grades ticked. Each tradition keeps its own scale and is never matched to the other: the Sunni
  books by sahih, hasan, da'if, very weak, fabricated and not graded; the Shia books by the Imami categories sahih,
  hasan, muwaththaq and da'if (al-Majlisi's and al-Behbudi's grades). A hadith is found when one of its graders gave
  a grade ticked; with *Every grader agrees* (`--every-grader`) only when every grade it was given is among those
  ticked. The grades are the graders' own words, grouped as the statistics group them; a grade given to the chain
  alone ("Isnaad Hasan") counts in its group and is shown as written. Al-Bukhari's and Muslim's own hadith carry no
  grader's grade: they count as sahih by their compiler's condition and the community's acceptance of the two books —
  the rule of hadith science, not a grader's grade, said so on each of their hadith ("In the Sahihayn: sahih by its
  compiler's condition"), and left out with one tick (`--no-sahihayn`). The search says how many of the hadith its
  words found are of the grades chosen, and when none is, how many the words found. Word search and search by meaning
  alike.

## [0.5.5] — 2026-10-26

- **isnady opens at once again (PERF-START, Bayram 2026-10-26: "isnady son zamanlarda cok cok gec aciliyor").**
  Before the window showed, every start looked for texts not yet indexed, hadith without a chain and links not yet
  looked up — and each of those looks read a whole table: about 320 MB of the 740 MB database, at every start, and
  half a minute and more on a disk not yet warm (after a restart). Each is now known from a few small index reads,
  kept as a stamp of what was done last (the number and the last row of the texts, the hadith and the chains; a
  partial index of the links not yet looked up): about 8 MB. A book added, removed or imported again changes the
  stamp, and the full look is made then. What the window reads in all at a start fell from about 670 MB to 170 MB:
  the Chains page's share of narrators identified in each book is kept with the other figures (it was counted again,
  book by book, at every start), and the Narrators page no longer draws the first narrator twice.
- **A new version no longer keeps the window from opening.** When a new version reads the chains again or identifies
  the narrators again (once), that work used to come before the window: the window did not show at all for a minute
  or more. It now runs in a thread of its own after the window has opened, says so in the status bar, and every page
  is drawn again with the new results when it ends. With a new matcher: the window in about 1.5 s, the narrators
  identified behind it in about 45 s, with the same results as before.

## [0.5.4] — 2026-10-26

- **Abu Mu'awiya is al-Darir again, and seven famous kunyas are read as the six books mean them (NR-ID5, 2026-10-26).**
  "أبو معاوية" bare in the six books is Muhammad b. Khazim al-Darir, al-A'mash's student; Hushaym b. Bashir shares
  the kunya, but the chains call him "هشيم" — and his name had been given to 190 of al-Darir's links, the neighbours
  outvoting a man the chains hardly ever name in full. Each is now told apart by the teachers only he narrates from
  (al-A'mash, Hisham b. 'Urwa, 'Asim al-Ahwal … for al-Darir; Husayn, Mughira, Abu Bishr, Yunus b. 'Ubayd … for
  Hushaym), and al-Darir is the reading of the bare kunya when nothing else decides: 1,420 links (56). In the same
  way "أبو عوانة" (al-Waddah al-Yashkuri, 873), "أبو نعيم" (al-Fadl b. Dukayn, 646), "أبو أسامة" (Hammad b. Usama),
  "أبو الزناد" ('Abd Allah b. Dhakwan), "أبو عاصم" (al-Dahhak b. Makhlad), "أبو قلابة" ('Abd Allah b. Zayd al-Jarmi)
  are no longer left among their namesakes. A neighbour known only as the famous bearer of such a bare name does not
  count as evidence for the next link (so "شعيب عن أبي الزناد" is still Shu'ayb b. Abi Hamza by his student). The
  matcher is isnady-narrators-17: 5,026 more links identified (366,314 → 371,319), 192 corrected; al-Bukhari 81.6%,
  Muslim 82.8%, Abu Dawud 79.2%. The narrators are identified again once, on the first start.
- **The recent searches no longer cut their second row in half** (Bayram, 2026-10-26, screenshot): a row of buttons
  that wraps (the recent searches, and every other such row) now makes its box as tall as its lines.

## [0.5.3] — 2026-10-25

- **Where you left off, and markers of your own (BM3, 2026-10-25: "Kitaplarda nerede kaldım?").** Each book
  remembers by itself the chapter and the hadith you had come to (the hadith at the top of the page when the scrolling
  stops) and opens there again; the shelf says "You left off at hadith 59" under it. The 🔖 Markers menu of the Books
  page puts a marker of your own where you are reading, named as you like, in any book and as many as you want, goes
  to any of them or to where you left each book, renames and removes them. Kept with the profile (state.json, in a
  profile file too) by book, chapter label and hadith number, so they survive a new import. The command line does the
  same: `iy book bukhari --resume`, `iy book bukhari 3 --mark NAME`, `iy book --marks`, `--go NAME`, `--unmark NAME`.
- **Statistics in plain words (ST-EXP1: "istatistik bilmeyenlerde anlayacak sekilde gosterilsin!").** Every finding
  of the Statistics page has under its headline an open box, *In plain words*, that says what came out here, with
  the figure in words ("τb 0.35 — a moderate relation, too clear to be chance", "Gini 0.88: very uneven: a few carry
  most of it — the pivots (madar) the critics speak of", "an odds ratio of 17.8 for a weak weakest narrator"); its
  words open on a click with what they measure, how to read them, what they mean for the science of hadith and an
  example. A new last section, *Terms explained*, holds all 31 of them; `iy stats --explain [TERM]` prints them, and
  `iy stats` adds a plain line under concentration, the grades, the model's fit, the graders' agreement and
  strictness. Turkish and Arabic complete.
- **The roads of a tahwil meet where the narrators attest it (ISN-TAH).** 0.5.2 stopped joining two roads whose
  meeting the text does not name; now a stopped road goes on as the other road does only (1) where the text names the
  meeting after it ("كلهم عن الزهري", "جميعا عن هشام") and the pair is attested, or (2) where its last narrator is
  found narrating from a narrator of the other road in at least three OTHER hadith, in chains read whole — never the
  other way round more often, never a teacher of a later generation, never one dead too long before to have taught
  him; the most attested meeting wins. 330 roads joined this way, 99 of them where the text names the meeting; Sahih Muslim reaches the
  Prophet ﷺ in 70.6% of its roads (69.5%); the chain page and `iy chain` say at the joining link why the roads meet there and how many hadith
  attest it. A road that ends with "بهذا الإسناد" is never joined so: the book's own pointer is drawn beside it.
- **More narrators identified, by their teachers and students (NR-ID3).** The matcher (isnady-narrators-16):
  - a bare name ("سفيان", "يحيى", "عبيد الله", "أبي سلمة") whose neighbour on ONE side only is known is the
    candidate that neighbour is seen with in at least six chains read whole, five times as often as any other (the
    critics' tamyiz al-muhmal);
  - "عن أبيه" is the father as the son's own nasab in the rijal work names him, found as an entry of his own —
    "سهيل بن أبي صالح ذكوان" → Dhakwan Abu Salih, "عبد الله بن أبي قتادة" → Abu Qatada, "عمر بن حفص بن غياث" →
    Hafs b. Ghiyath — when the entry carries his name and one more thing of the nasab (the grandfather, the kunya, a
    nisba) and is of the son's generation or before.
  21,507 more links identified (344,822 → 366,314); al-Bukhari 74.7% → 79.8%, Muslim 77.6% → 81.3%, Abu Dawud
  74.3% → 78.3%, al-Kafi 63.5% → 65.2%. The new identifications break the order of generations or the years of death
  far less often than the ones before (18 in 21,507 against 156 in as many). The narrators are identified again once,
  on the first start.

## [0.5.2] — 2026-10-25

- **Only what the text says is drawn, as the science of hadith reads it (2026-10-25: "Hadis ilmi cercevesinde
  yap demistim!").** 0.5.0 and 0.5.1 joined chains on their own suppositions; they are taken back (isnady-isnad-15):
  - "بهذا الإسناد" (Muslim's way): the road stays as it is written, and the chain of the hadith before it is drawn
    beside it, marked "from the hadith before" and kept out of the statistics. "مثله", "نحوه", "بمعناه" speak of
    the wording of the text, not of its chain, and complete nothing. Sahih Muslim reaches the Prophet ﷺ in 69.5%
    of the roads as written (0.5.0 said 81.9%, counting the completed ones);
  - a chain is borrowed from the hadith before only where the book says so: "وعنه" (from him), "وبهذا الإسناد",
    "وبإسناده". A text that merely goes on from the one before ("ونهى عن …", "قالت: …", the Musnad's pieces) is
    said to have no chain of its own, and none is drawn (589 hadith);
  - the books that cite without chains (Bulugh, Riyad, Mishkat): the Companion is shown only where the text names
    him; "وفي رواية لمسلم" no longer takes the Companion of the hadith before;
  - two roads whose meeting the text does not name (a tahwil, al-Kulayni's second road without "جميعاً") are no
    longer joined "at one depth": each is drawn as far as it is written;
  - a text is called "the compiler's own words" only where he says so ("قال أبو عيسى", "قال مصنف هذا الكتاب",
    "قلنا", "فإن قيل"); otherwise "the book gives the text without a chain".
  The chain page and the CLI say so on every borrowed chain ("taken from the hadith before it … not counted in the
  statistics"), and the card of a search result marks it "بهذا الإسناد".
  Hadith with no chain drawn: 1,314 (589 going on from the hadith before, 484 given without a chain, 216 drawn
  compiler → … → the Prophet ﷺ / the Imam, 25 the compilers' own words) — more than 0.5.1's 385, because the chains
  it supposed are no longer drawn as their own. The chains are read again once, on the first start.

## [0.5.1] — 2026-10-25

- **No chain is left unread (2026-10-25: "arkadasim hepsini coz demistim!").** The reader of the chains
  (isnady-isnad-14) reads the last 276 problem chains of 0.5.0 to the end:
  - a story after the chain ("قال قلت لأنس: حدثنا …", "سمع المسلمون ببدر") ends it where it was read, and names read
    on after a story are kept only while they are names: they are checked against the first words of the names of
    every chain read whole (a new list shipped with isnady, `assets/sources/name_words.txt`);
  - two narrators at one link with nothing named after them ("وراشد بن سعد وغيرهما قالوا …"), a "ح" that closes the
    text (the other road is the next hadith) and a full stop before a sentence keep the road as read;
  - "قالت زينب فدخلت …", "قال أبو حازم …" take the chain of the hadith before, to the narrator who goes on speaking;
    "قال أبو عيسى قال محمد بن بشار سألت يحيى …" and "باب … حدثني عن مالك أنه بلغه" are read from their first narrator;
  - the Shia books: an Alid's nasab that ends "بن علي بن أبي طالب عليهم السلام" goes on to the next narrator; the
    editor's brackets ("[عن أبيه]") are read through; "رجال الكشي:", "التهذيب: بإسناده عن …", "قال الشيخ … مصنف هذا
    الكتاب: حدثنا", "قال أبي رحمه الله قال سعد", "أحمد بن مهران رحمه الله رفعه"; a second road from the compiler
    meets the first where it names the first one's narrator (two roads left unread 27 → 0); the numbers of the
    edition ("2-120", "[8/42]") are no longer read as a narrator (about 1,000 such links gone).
  Chains left unread: Sunni 247 → 0, Shia 29 → 0; hadith with no chain drawn 483 → 385 (216 drawn compiler → … →
  the Prophet ﷺ / the Imam, 169 the compilers' own words). Sunni identified 287,199 → 287,487. The chains are read
  again once, on the first start.

## [0.5.0] — 2026-10-25

- **Every hadith with a chain is drawn with it (2026-10-25: "tamamda senedsiz kalmasin … Hepsini hic eksik
  kalmayacak sekilde coz").** The reader of the chains (isnady-isnad-13) no longer stops where a chain goes on:
  - after words not understood, a pair of teachers it could not split, or a full stop, it reads on from the next
    term of hearing ("قال قلت لأبي أسامة: حدثكم …", "قالا سمعنا قيسًا", "عن مسعر وغيره"); after a Companion the
    words are his story and the chain ends with him;
  - a road that stops at a narrator and says "بهذا الإسناد", "بمثله", "نحوه" (Muslim's way) goes on as the chain of the
    hadith before it does, from that narrator: Sahih Muslim reaches the Prophet ﷺ in 81.9% of its chains (70.4%);
  - every tahwil is drawn, each road its own chain, a road that names a narrator of another going on as that one;
  - the man not named: "حدثني من شهد النبي ﷺ", "عمّن صلى مع رسول الله ﷺ", "عن رجل من القوم الذين سألوا عمر";
    "فأخبرني", "قلت لعائشة: أخبريني", "أن رجلاً سأل ابن عمر"; the Musnad's pieces without a chain ("ثم قالت …",
    "قال: وقال رسول الله ﷺ") take the chain of the hadith before;
  - the books that cite without chains name their Companion ("ولأبي داود من حديث أبي هريرة", "وعن جابر نحوه") or
    take the Companion of the hadith before ("وفي رواية لمسلم"); al-Dehlawi's Forty and al-Mu'min, which give the
    words of the Prophet ﷺ or the Imam alone, are drawn as the compiler → … → him;
  - the Shia books: a second road from the compiler without "جميعاً" is read whole and both roads drawn
    (232 → 27); "بإسناده عن …", "بإسناده رفعه", "أبي رحمه الله قال سعد بن عبد الله عن …"; "وبهذا الإسناد عن X" whose X
    is not in the chain before draws its own narrators (bi-isnadihi left unread 397 → 2); "قال سعد: …" (al-Tusi) is a
    link; what is the compiler's own word (a date, a note on a narrator) is said to be so.
  Hadith with no chain drawn: 1,950 → 483 (of them 213 now drawn compiler → … → the Prophet ﷺ / the Imam, 184 the
  compilers' own words); chains left unread: Sunni 2,001 → 247, Shia 1,058 → 29. Links 513,880 → 527,724; Sunni
  identified 279,943 → 287,199. The chains are read again once, on the first start.

## [0.4.9] — 2026-10-25

- **Ten thousand chains that stopped halfway are read to the end (2026-10-25: "10bin senet az mı????!!!! Bunları da
  düzelt").** The reader of the chains (isnady-isnad-12) now reads what kept a chain of the Sunni books "kept
  whole":
  - the Musnad of Ahmad, written without commas: a name ends where the story begins ("عن عائشة أنها كانت تقول",
    "عن أبي بكر أنه سمعه حين …", "وكان عاملاً على توج", "في بيت قتادة"); two teachers at one link with no comma
    ("حدثنا سفيان وشعبة عن منصور", "قتادة وثابت"); "قال قال إسرائيل قال أبو إسحاق عن زيد"; "قال لي ابن أبي نجيح";
    "قال كان محمد بن جبير يحدث عن معاوية"; "قرأت على عبد الرحمن: مالك عن …"; "وجدت في كتاب أبي بخط يده";
  - which teacher said which word, in every form of Muslim's and Abu Dawud's: "قال إسحاق أخبرنا وقال الآخران
    حدثنا جرير", "- قال ابن أيوب حدثنا إسماعيل -", "قال عفان عن ابن بريدة", "- المعنى - قالا", "- واللفظ لحرملة -";
  - three or four teachers before "قالوا"/"كلهم", "عبد الرحمن ومجمع ابنا يزيد", "انهما أخبراه", "سمعا";
  - al-Bukhari's asides between "ـ … ـ" ("عن أبي عبيد ـ اسمه سعد بن عبيد ـ"), a blessing between them is no aside;
  - a narrator's doubt: "عن أبي هريرة أو عن أبي سعيد - شك الأعمش -" (both, as two roads), "أو أخيه سليمان",
    "حدثني أو أخبرني"; "عن رجل لم يسمه"; "عن مسعر وغيره"; "غير مرة"; "ثقة حدثنا";
  - new terms with their meaning: "كتب إليّ" (wrote to me), "وجدت في كتاب" (found in writing, wijada), "بلغه عن"
    / "بلغني عن" (it reached him), "سأل" (he asked); also "حدثتني", "أخبرتني", "حدثكم", "سمعه من", "قلت لأبي
    أسامة: حدثكم عبيد الله …", "أن رجلاً سأل ابن عمر" (Ibn Umar the one asked);
  - al-Bukhari's citations without a chain of hearing ("وقال الليث حدثني جعفر", "وقال لنا أحمد بن حنبل"): the man
    cited is the first link (qala);
  - a tahwil whose meeting nothing names: the two roads are of one depth to there; road A's second teacher at a
    link is a road of its own; "عائشة" and "عائشة بنت طلحة" are two women;
  - the books that cite their hadith without a chain (Bulugh al-Maram, Riyad al-Salihin, Mishkat, the Forty of
    al-Dehlawi, al-Mu'min) say so — "no chain: the book cites the text without one" — instead of "does not start
    with a transmission term"; the Musnad's "وقال رسول الله ﷺ …" and "وبإسناده" take the chain of the hadith before,
    and al-Kafi's or Thawab al-A'mal's "وبهذا الإسناد عن أحمد بن أبي عبد الله …" that chain to the man named, then
    its own narrators.
  In the Sunni books, chains (first roads) kept whole fell from 10,214 to 2,001 — "words not understood" 6,596 →
  1,515, tahwil 788 → 90, two at one link 923 → 99 — and 513 more are books that give no chain. Links read
  448,822 → 513,880; Sunni links identified 232,106 → 279,943 (68.2% → 69.2%). Sahih Muslim is read whole in 96.7%
  of its chains (74.9% before), al-Bukhari 97.0% (89.9%), Abu Dawud 95.9% (85.0%). The Shia books are read as
  before (their own terms). The chains are read again once, on the first start.

## [0.4.8] — 2026-10-25

- **More chains read to the end: Muslim's way of writing them (2026-10-25, the big problem of this release).** The
  reader of the chains (isnady-isnad-11) now understands what stopped it in a thousand chains of the Sunni books:
  - a narrator made plain in dashes — "حدثنا عمارة، - وهو ابن القعقاع - عن أبي زرعة" (with "وهو" as with "يعني");
  - the compiler's note on whose wording it is — "- قال ابن نمير حدثنا سفيان -", "- واللفظ له -",
    "- وهذا حديثه -" — no link;
  - which of two teachers said which word — "حدثنا عثمان وإسحاق، قال إسحاق أخبرنا جرير، وقال عثمان حدثنا
    جرير، عن منصور": Jarir once, then Mansur;
  - a narrator quoted before he goes on — "حدثنا حجاج، قال قال ابن جريج أخبرني محمد";
  - the one asked — "قال سألت عائشة عن …", "قال سئل أنس": the last link, with its own term ("I asked", "was
    asked");
  - a long nasab of eleven to thirteen words ("عبد الله بن أبي بكر بن محمد بن عمرو بن حزم");
  - where the two roads of a tahwil (ح) meet: "ليث" and "الليث", "أبو حيان" and "أبي حيان", "أنسا" and "أنس",
    "ابن عمر" and "عبد الله بن عمر", "ابن وهب" and "عبد الله بن وهب", a name and its nisba, and "حدثنا محمد بن
    فليح، حدثني أبي" meeting a road that ended with Fulayh. Muslim 93 now shows its two chains.
  In the Sunni books: 6,775 more links read (337,712), 1,221 more chains reaching the Prophet ﷺ or their end,
  326 more roads; chains kept whole fell from 12,042 to 10,967 — "words not understood" from 7,385 to 6,596,
  unsplit tahwil from 1,039 to 788. The chains are read again once, on the first start.
- **"حدثني أبي" is the father of the narrator before.** The matcher (isnady-narrators-15) read a lone "أبي" as the
  kunya "Abu" (698 candidates), and the neighbours then picked a stranger: in Muslim 93 'Ubayd Allah b. Mu'adh's
  father was al-Mu'tamir. It is now the father, read from the son's full name — Mu'adh b. Mu'adh al-'Anbari — and
  said as "his father" with whose. 1,034 more links identified. Turkish no longer doubles the apostrophe after a
  name ending in 'ayn: "Nâfi'den", not "Nâfi''den".
- **Random hadith always shows a chain (2026-10-25: "rasgele hadis dediginde bazen hicbirsey cikmiyor").** It picks
  among the hadith whose chain was read; Riyad al-Salihin, Mishkat, the Forty of al-Dehlawi and other books give
  many hadith without one, and such a pick showed an empty page. A hadith without a chain now says so — the book
  gives it without one, or why none could be read — above its text.
- **isnady's log, as VenvStudio has it (2026-10-25: "isnady icin bir log sistemi ---> venvstudio daki gibi").**
  `logs/isnady.log` in the data folder: every start with a banner (version, Python, PySide6, system, data folder,
  profile, database, books), then a line for what isnady did — a page drawn, a search and its time, an import, an
  export, the chains read, the narrators identified, the statistics computed, a cache cleared, a reset — and every
  error with its traceback; 2 MB, five older files kept. A hard crash writes `logs/crash_<time>.log` with every
  thread's stack. **Help → Log…** (Ctrl+Shift+L) follows it live, filters errors or a text, makes it larger or
  smaller, copies it with the version at its head, opens its folder, removes what is older than a day or clears it;
  `iy log` (`-n`, `--level error`, `--grep`, `--follow`, `--crash`, `--files`, `--before`, `--clear`) does the same
  on the command line, and every `iy` command is logged. `log.level` debug says more.
- **Statistics out of isnady, piece by piece or whole (2026-10-25: "Istatistik kismindaki detaylari veya grafikleri
  ayri ayri ya da tam disari aktarabilmemiz lazim").** Every finding on the Statistics page has a ⤓: its chart as a
  picture (PNG, SVG), a PDF or on the clipboard, its figures as CSV, Excel, JSON or Markdown. The page's **Export**
  writes this section or every section as one PDF or one web page (charts and their tables), every table as one
  Excel workbook with a sheet each or as CSV files in a folder, and the computed results as JSON. File → Export…
  and `iy export statistics [BOOK] --tradition shia` write the results as JSON too.
- **Export: every language with one click (2026-10-25: "tum diller sec diye birsey de yok").** The languages of an
  export are ticked in a list with All and None, like the books.

## [0.4.7] — 2026-10-25

- **Exporting hadith works again.** In 0.4.5 and 0.4.6 every export of hadith — a book, several books, numbered
  hadith or search results, in any format — stopped at once with "TypeError: argument of type 'module' is not
  iterable": the name kept for the chapters' titles was taken over by the module that gives the books' names in
  the interface language. Each now has its own name; every format was written again and read back (JSON, JSON
  Lines, CSV, TSV, Excel, Markdown, HTML, text, EPUB, Word, SQLite, PDF).
- **The README and its screenshots are up to date on GitHub, PyPI and npm (2026-10-25: "readme ve screenshotlari
  guncellemedin. 3 ayri yerdeki readme").** Every screenshot was taken again: Books and Isnad Chains with the
  number, the last number, the place in the book and ⏮ ‹ › ⏭; Settings → Books and languages with the languages in
  their order; and three new ones — Settings → Reset with its three cards, the Export dialog writing every book as
  one EPUB with its progress bar, and the same export going on in the bar at the bottom of the window. The text
  says what 0.4.3–0.4.6 brought (going through a book, the language order, several books at once, big exports
  beside the window, statistics kept across versions), and the roadmap no longer lists what is done.
  `tools/make_screenshots.py` takes the three new ones too.

## [0.4.6] — 2026-10-25

- **Statistics are not computed again for nothing (2026-10-25: "neden surekli istatistik kismini hesapliyor … eger
  cok buyuk bir degisiklik yoksa neden surekli bunu yapiyor?").** Every new version of isnady deleted the saved
  statistics with the rest of what it had computed, so Statistics worked everything out again after each update. Now
  the saved statistics are kept across versions: each carries the fingerprint of what it was computed from (the
  hadith, the narrators identified in the chains, the verdicts, the grades, the books switched off) and the method
  of its analysis, and is computed again only when one of these changed — after an update that identifies
  narrators differently, for example, but not after one that only changes the window. The other kept files
  (`cache/`) are still made new on a new version.

## [0.4.5] — 2026-10-24

- **Big exports beside the window, with a progress bar (2026-10-24: "epub olarak hepsini tum dilleri ile export
  etmesini istedim. cok cok uzuyor ama en azindan ayri bir threat olabilir, bunun disinda progress bar da
  olabilir").** Every export, PDF too, runs in a thread of its own. The dialog and the bar at the bottom of the window
  show how far it has come (a bar with the percentage, "36,912 / 99,567", the book being written, the time gone and
  about how long is left) and a Stop button; the dialog is no longer modal and can be closed — the export goes on,
  and the bottom bar says where the file was written ("Show in folder"). Stopped, the unfinished file is removed;
  closing isnady during an export asks first. `iy export` shows the same bar on the terminal, and Ctrl+C stops it.
- **Faster, and in little memory.** The hadith are read and written one after another: an EPUB, Word, HTML,
  Markdown, text, JSON, JSON Lines, CSV or TSV file grows while the hadith are read, instead of every book being
  gathered in memory first. Every book in every language with the chains as one EPUB (99,567 hadith, 51 MB): 55
  seconds and 295 MB instead of 96 seconds and 1.2 GB on the same computer. Each name of a chain is read once
  (not again in every chain it stands in), each chapter title is asked once, and telling Arabic from other text
  costs a fraction of what it did.

## [0.4.4] — 2026-10-24

- **Going through a book with ease (2026-10-24: "kitaplari rahat dolasmak lazim! Max hadis nerede???? max sayfa
  numarasi????? Isnad Chain de de ayni durum var!!!").** On Books and on Isnad Chains the hadith number has the
  book's last number beside it ("/ 7563"), where the hadith stands among the book's ("hadith 36 of 7,467 in this
  book") and ⏮ ‹ › ⏭ for the first, previous, next and last hadith. Books also goes to a chapter by its number
  ("34 / 57") with the first and last chapter a click away, and to any hadith by its number, opening its chapter
  where it stands. On Isnad Chains the book list is wide enough to read and nothing is cut off at the right.
- **The languages in your own order (2026-10-24: "Dilleri (Arapca disinda) yerlerini duzenleyebilmemiz lazim").**
  Preferences → Books and languages lists the languages to tick and to drag (or move with the arrows); Arabic always
  stays first, Default puts the others back from A to Z. The texts of every hadith card, the chain said in words, the
  language lists of the sidebar, Books and Export follow. `iy config set view.language_order Turkish,English`.
- **Several at once in Export and Import, or all of them (2026-10-24: "birden fazla kitap/..... secilebilir olsun.
  Hepsi de olsun").** Books are ticked in a list with All, None, Sunni and Shia: together in one file, or each in its
  own file in a folder (isnady books always so); the isnad network from the books ticked; several profiles, each in
  its own file. Import takes several files at once and says how each went. `iy export book bukhari muslim`,
  `iy export book all|sunni|shia --separate -o FOLDER`, `iy export network bukhari muslim`, `iy import-data
  bookmarks a.json b.csv`.

## [0.4.3] — 2026-10-24

- **The chain of more hadiths is read to the end (2026-10-24, Muslim 93: "hala senedlerini neden goremiyoruz bazi
  hadislerin").** When one man is named twice with a comma between — "حدثني أبو خيثمة، زهير بن حرب" (his kunya, then
  his name) — the reader took the second half for a new, nameless link and stopped there with "…". It is now one
  man. 2,111 more links in the chains of the six books are read and given to a narrator; the "words not understood"
  fell from 7,861 to 7,385.
  - Abu Khaythama Zuhayr b. Harb, Muslim's teacher, is found: Ibn Hajar's Taqrib spells his kunya "أبو خثيمة", so
    he was never matched and 11 of his chains were given to Ahmad b. Abi Bakr. A bare "Abu Khaythama" is left open
    when two men carry it.
  - "Ebû Hîsme" → "Ebû Hayseme": a comma stuck to a name no longer stops it from being read from the word list.
  - When the chains are read again (once, on the first start: about a minute and a half), every narrator is found
    again with all the evidence; before, only the new chains were looked at and many narrators were lost.
  - A chain still stops where the book joins a second chain to the first ("ح", tahwil): the first road is shown,
    the second is not yet split (ISN-TAH).
- **Reset is clear (2026-10-24: "hicbirsey anlamadim reset kisminda, sanki birbirinin ayni").** Settings → Reset now
  shows three cards — 1. Only the settings, 2. Only the books, 3. Everything — each listing what is deleted and what
  is kept, with its own coloured button and its own question before anything is deleted. Reset is no longer in the
  Edit menu (2026-10-24: "tools altinda direkt reset olmasin"); `iy reset` is unchanged.
- **The Settings window opens large (2026-10-24: "veri kaynaklari kismina girdigimde pencereyi genisletmemiz
  gerekiyor").** Most of the screen, and its pages never scroll sideways: on Data sources the book titles, tags and
  buttons wrap onto a new line when the window is narrow.

## [0.4.2] — 2026-10-24

- **Export and import of everything, each in many formats (2026-10-24: "herseyin ayri ayri farkli formatlarda
  export/import edilebilirligini istiyorum. Ister bookmarklar ister profiller, ister kitaplar!").** File → Export…
  (Ctrl+E) and File → Import… (Ctrl+Shift+E), with a preview before writing; an **Export** link on every hadith card;
  the Bookmarks page's export and import open the same dialogs.
  - **Hadith** by number (bukhari:1, bukhari:5-10), **search results**, a **book or a chapter**: JSON, JSON Lines,
    CSV, TSV, Excel (XLSX), Markdown, HTML, text, EPUB, Word (DOCX), PDF, SQLite — each hadith with its chapter,
    texts in the languages chosen, grades and chains (Arabic, Turkish, English). A book also as an **isnady book**,
    isnady-data's own format, which comes back in as a book (a source of your own); an export in JSON, JSON Lines,
    CSV or TSV comes back too, each hadith to its own book.
  - **Bookmarks** (JSON with the folders, JSON Lines, CSV, TSV, Excel, Markdown, HTML, text, PDF; imported from
    JSON, JSON Lines, CSV, TSV, into a folder or replacing), **narrators** of a tradition (tables, PDF, SQLite), the
    **isnad network** — who narrated from whom, how often — for Gephi and yEd (GraphML, GEXF, CSV, JSON),
    **settings** (only the ones changed), a **profile** (isnady profile or JSON) and a **backup** of everything of
    yours (settings, place, bookmarks, the list of the books).
  - PDF is drawn by Qt, so Arabic is joined and set right to left; Excel, Word and EPUB are written without any
    extra package (core/formats.py, core/transfer.py).
  - `iy export WHAT … -f FORMAT -o FILE` (`--chapter`, `--language`, `--no-chains`, `--tradition`, `--list`) and
    `iy import-data WHAT FILE` (`--replace`, `--folder`, `--name`).

## [0.4.1] — 2026-10-24

- **The content languages can be chosen again (2026-10-24: "diller secilmiyor").** With "All languages" on, a click
  on one language changed nothing and every click closed the menu. The languages are now ticked in place — "All
  languages" ticks or clears them all — the menu stays open while they are ticked, and the choice is applied when it
  closes (the Content button at the bottom of the sidebar and View → Content Languages).

## [0.4.0] — 2026-10-24

- **The chain's words, closer to the Arabic and with its manners (2026-10-24, Bayram's screens).** "عمه أبي سهيل"
  is "Mâlik b. Enes'in amcası Ebû Süheyl b. Mâlik" (it was "Amh Ebû Süheyl"), and Isnad Chains names each link as
  the chain does — "Nâfi' b. Mâlik'in babası Mâlik b. Ebî Âmir", not "Babası". On road A a Companion carries
  "(r.a.)" / "(RA)" and the Prophet "(s.a.v.)" in Turkish; after "b." and "bint" Turkish writes the kunya in the
  genitive (Ebû Bekr b. Ebî Şeybe, Mâlik b. Ebî Âmir, Hind bint Ebî Ümeyye). On a card the compiler heads the
  chain — he is the "us" of "narrated to us" — and an arrow stays with the name it points to, so that a line never
  ends on an arrow.
- **Language settings on every card.** Beside "Other languages" (or alone), **Language settings** opens Settings →
  Books and languages.
- **Back to zero (2026-10-24: "tum config'i silme olsun. Tum kitaplari silme de olsun. Sifir duruma
  getirebilelim").** Edit → Reset… (Settings → Reset): delete all settings, all books (with the narrators, the
  search index and all that was computed; the database file small again), or everything — books, settings,
  bookmarks and the downloaded data. `iy reset settings|books|all [--yes]` (core/reset.py).
- **A book's numbers said as numbers.** Isnad Chains shows "numbers 1 – 7563 · 7,583 hadith" and says why the last
  number and the count differ (missing and split numbers, a book beginning at 0).
- **"His father" says whose father (2026-10-24: "babasi-kardesi gibi kavramlar bir supheli. Kimin babasi, kimin
  kardesi?").** Under the chain, a relative named only as such — أبيه، جده، أمه، أخيه، عمه، ابنه، مولاه — now says whose
  relative he is and, when isnady has identified him, who he is: "Hişâm b. Urve'nin babası Urve b. ez-Zübeyr'den" /
  "from Hisham b. Urwa's father, Urwa b. al-Zubayr". "عن أبيه عن جده" is the grandfather of the man before the
  father ("Sâlih b. İbrâhim'in dedesi Abdurrahman b. Avf'tan"); "أمه أسماء" is "Hişâm'ın annesi Esmâ …". On the
  cards, in Isnad Chains and in `iy chain --lang`.
- **The books offered at every start until there are some (2026-10-24: "ilk calistirildiginda … otomatik acip icine
  aktarmayi sorsun! Tek bir onaylama ile kitaplarin hepsini yuklesin").** With no book in the database, isnady asks
  at each start — not once only — and **Import all** brings every hadith book and rijal work of isnady-data in the
  background. The command line says the same and names the one command: `iy catalog import --all`.

## [0.3.9] — 2026-10-24

- **The chain's words right under its names (2026-10-24: "tam altinda olsa daha guzel olurdu. Ayni sekilde
  oklarla").** On a hadith card each Arabic name of the chain now has its piece of the chain written right under it,
  in each language the card shows, between the same arrows: "Abdân bize rivayet etti" · "Ebû Hamza'dan" ·
  "el-A'meş'ten" · … · "Hz. Peygamber ﷺ'den" (English: "Abdan narrated to us" · "from Abu Hamza" …), instead of one
  sentence below the chain. Isnad Chains keeps the whole sentence under the Arabic text.

## [0.3.8] — 2026-10-24

- **The chain in your languages, under the Arabic (2026-10-20: "Senedlerin hepsi arapça ---> altina gosterilen
  dillerde de gosterilsin arapcasinin altina!").** On every hadith card (Search, Books) and under the Arabic text of
  Isnad Chains, the chain is said again in the languages the texts are shown in — Turkish and English so far — link
  by link as the Arabic says it: each name read from the chain's own wording, with the term that brings it
  ("Kuteybe b. Saîd bize rivayet etti, Leys bize rivayet etti, Yezîd b. Ebî Habîb'den, … Hz. Peygamber ﷺ'den" /
  "Qutayba b. Sa'id narrated to us, … from the Prophet ﷺ"). Turkish puts the case on the name by vowel harmony
  (Leys'ten, Enes'ten, babasından, Ömer b. el-Hattâb'ı işittim); "his mother Asma' …", "his father" and "رضي الله
  عنها" are read as such; a Shia chain ends at its Ma'sum (İmam Ca'fer b. Muhammed es-Sâdık'tan) or says it is
  raised. `iy chain BOOK NUMBER --lang tr,en`.

## [0.3.7] — 2026-10-24

- **Narrators, Books and Scholars open on the Sunni ones (2026-10-20: "ilk açıldığında default Sunni Raviler gelsin
  — kitaplar ve alimler içinde!").** All and Shia are a click away and the choice holds while isnady runs; a Shia
  narrator, book or scholar opened from another page shows his own road (no longer "All"). The Books page no longer
  carries the last shelf over to the next start. `iy book` and `iy scholar` list the Sunni ones (`--tradition shia`
  or `all`); `iy narrator --famous` the Companions (`--tradition shia`, `all`).

## [0.3.6] — 2026-10-20

- **The famous Companions, however they are written (2026-10-20: "Ebubekir'in diğer isimlerini bilmeyen nasıl
  bulacak? … Omer ibn Hattap ya Umar bin Hattab da yazmış olabilirdim").** ★ Famous Companions on the Narrators page
  and in the Genealogies, and `iy narrator --famous`: the four Caliphs, the ten promised Paradise, the Mothers of the
  Believers, the Prophet's household, those who narrated most and some forty more, group by group, each by the name
  people know him by ("Hz. Ebû Bekir es-Sıddîk (r.a.)", "Abu Bakr al-Siddiq (RA)", أبو بكر الصديق رضي الله عنه); on
  road B, Ashab al-Ijma' from al-Najashi, never in one list with the Companions (core/famous.py). Typed in any
  search of narrators, a famous Companion comes first whichever way he is written — "Ebubekir", "Ebubekr", "Ebû Bekr
  es-Sıddîk", "Abu Bakr", "Hz. Ömer (r.a.)", "Omer ibn Hattap", "Umar bin Hattab", "Osman", "Uthman", "Hz. Ali",
  "Ayşe", "Aisha", "Aysha", "Ümmü Seleme", أبو بكر الصديق; "Hattab" alone is 'Umar.
- **Namesakes told apart.** The names the Genealogies find carry their tabaqa, death year and how often they are in
  the chains: 'Umar b. al-Khattab the Caliph (tabaqa 1, d. 23) is no longer one of three alike.
- **Umm Salama and Abu Umama found in the chains.** "أم سلمة" is the Mother of the Believers (Asma' bt. Yazid, also
  called so, is named Asma' in the chains), "أبو أمامة" al-Bahili, "أبو بكر الصديق" Abu Bakr (his entry begins with
  'Abd Allah b. 'Uthman): 839 links more, none changed; Sunni links identified 67.8% → 68.1% (matcher
  isnady-narrators-13 — the narrators are matched again once, under a minute).
- **"Abi" is Abi again.** Since 0.3.5 every "أبي" not known as part of a name pair was read "Übey" (Ubayy): Hind bt.
  Abi Umayya was "Hind bint Ubayy Umayya" — 971 names read right again. "أبي" before "بن" stays Ubayy (Ubayy b.
  Ka'b, his son 'Abd Allah b. Ubayy b. Ka'b), and so after a kunya's "Abu" (Abu Ubayy b. Umm Haram).

## [0.3.5] — 2026-10-18

- **No one made a teacher he was not (2026-10-18: Abu Hurayra's line of learning).** Read anew, the chains no longer
  put on a narrator's line of learning men who never taught him:
  - the Prophet ﷺ named by his kunya — "سمعت أبا القاسم ﷺ", "حدثني خليلي", "حدثنا الصادق المصدوق", "سمعت محمداً ﷺ" — ends
    the chain (29 links of Abu Hurayra had been given to Muhammad b. Abi Bakr al-Siddiq, also "Abu al-Qasim");
  - the man a Companion tells a story about is not his teacher: "عن أبي هريرة أنّ سعد بن عبادة قال لرسول الله", "عن عائشة
    أن حمزة بن عمرو قال يا رسول الله", "أن فاطمة بنت أبي حبيش سألت", "أن جبريل أتى النبي ﷺ", "سمعت هشام بن حكيم يقرأ" end at
    the Companion who tells it (core/companions.py: the Companions as the chains name them);
  - a second road after a link is its own chain: "… عن عروة، عن عائشة، وعن هشام بن عروة، عن أبيه، عن عائشة" had made
    Hisham a teacher of A'isha; "وحدثنا فلان", "قال وأخبرني فلان", "، وأبي الزناد، عن الأعرج" after a Companion and Muslim's
    "ح وحدثنا … قالا" (which had met the first road at the wrong man) are read the same way; a road begun again without a
    sign is cut where the narrator is named the second time;
  - "عائشة، زوج النبي ﷺ قالت" is A'isha (the title had swallowed her name), "أن ابن عباس أخبره أن النبي ﷺ" keeps
    Ibn 'Abbas, "وابن، عباس" (a comma some editions put in a name) is one name, "سمع من أبي هريرة" is Abu Hurayra.
  Sunni links identified 66.7% → 67.8%, Shia 51.1% → 51.6%; parser isnady-isnad-9, matcher isnady-narrators-12 — the
  chains are read again once (about a minute and a half).
- **Two neighbours that cannot both be right are not left so.** A narrator his own teacher, a teacher four tabaqat
  after his student or six before him, or one who died eighty years after him: the less certain identification is
  left open ("أبو عمران الجوني" had been the later Baghdadi of that name, "حماد عن ثابت" Thabit b. al-Dahhak, "حدثني
  عمي" al-'Ammi). "عن جده عبد الله بن الزبير" is the man the chain names, "عن أبيه، عن جده" the father's father; on road B
  the narrator al-Kulayni's roads meet at after "جميعاً" is no longer named twice.
- **Ubayy b. Ka'b** is read as Ubayy, not "Ka'b b. Qays" known by a kunya "أبي".

## [0.3.4] — 2026-10-18

- **Everything named opens (2026-10-18: "hâlâ tıklanmayan yerler var").** On Isnad Chains a narrator's whole card
  opens him (before, only the small Arabic line did); the book at the top opens the hadith in its book; the Prophet ﷺ
  at the end opens his life in the Genealogies, in the tree of Quraysh, with al-Shama'il and Ibn Hisham's Sira to
  read (on road B, the Imam the chain reaches); a name not identified looks for its narrators on Search. The chains
  on the cards of Search and Books open the same way, chip by chip. The books of the overview open their first
  chain; a narrator's teachers and students open through the window, so Back returns; a mark of one book (خ, م …)
  opens that book; a scholar's own books open from his page; every teacher and student named in a life looks for
  himself among the narrators.
- **One in two of the Shia chains' narrators identified (NR-ID2 on road B).** al-Kulayni's teachers named short
  ("'Ali b. Ibrahim" b. Hashim al-Qummi, "Muhammad b. Yahya" al-'Attar), the nisbas and kunyas the chains use alone
  (al-Sakuni, al-Nawfali, Abu Basir, al-Halabi, Ibn Faddal, Ibn Muskan, Safwan) and the bare names their neighbours
  tell apart ("Muhammad b. Yahya from Ahmad b. Muhammad" is Ibn 'Isa, "Hammad from al-Halabi" Hammad b. 'Uthman,
  "Hammad from Hariz" Hammad b. 'Isa). "From his father" is read from the son's full name once he is known ("'Ali b.
  Ibrahim from his father" is Ibrahim b. Hashim), never from a father named by his kunya or his ism alone, which had
  matched the wrong man. Shia links identified 42.4% → 51.1%, Sunni 66.0% → 66.7%; matcher isnady-narrators-11, the
  chains are read again once.
- **Scholars named in the interface language.** The Hadith Scholars list and the scholar cards of Search show the
  name in the interface language on top ("Buhârî", under it "Buhârî (Muhammed b. İsmâil)"); before, the English name
  stood above the Turkish one.

## [0.3.3] — 2026-10-18

- **Two of every three narrators of the Sunni chains identified (NR-ID2).** The Taqrib's unnamed men ("'Ata' b. Yasar
  from one of the Companions … he is Abu Hurayra") are no longer matched to a name — they had taken Abu Hurayra,
  Malik and others out of thousands of chains. Names the chains use that the Taqrib does not list are added ("Ibn
  Shihab" al-Zuhri, "Ibn Mas'ud", "Ibn Numayr" father and son); the Muwatta's chains begin with Malik himself; a chain
  of one link in Mishkat, Riyad al-Salihin or Bulugh al-Maram is the Companion; the two Sufyans, the two Hammads and
  the three Hishams are told apart by the students and teachers that show each ("al-Humaydi from Sufyan" is Ibn
  'Uyayna, "Abu Nu'aym from Sufyan" al-Thawri, "Hisham from his father" Ibn 'Urwa); "from his father" is read again
  once the narrator before it is known; and last, a bare name still open is the famous man of that name when nothing
  else excludes him ("Anas", "Malik", "Shu'ba", "Ibn 'Umar"; confidence 0.5). 66.0% of the Sunni links are identified
  (52.6% before), about 262,000 in all; pointing at a narrator in a chain says how he was identified, and `iy chain`
  marks the ones read from their neighbours or as the famous one. The chains are read again once (about half a
  minute).
- **Recent searches (S4).** The last twenty searches on the Search page, a click to search again and one to forget
  them; kept with the profile. `iy search --recent`, `iy search --clear-recent`.
- **Home on the Search page (NAV1).** ⌂ (Alt+Home) brings the page back to how it opens; Esc empties the box.
- **Back and forward (NAV2).** ◀ ▶ in the sidebar, Alt+Left / Alt+Right and the mouse's back and forward buttons
  go through what was opened — narrators, chains, books, scholars, terms, trees — each button saying where it goes.
- **The range of a book's numbers (CH2).** On Isnad Chains the number field shows the book's first and last number
  and how many hadith it has; the arrow keys and the mouse wheel step through them, typing lists the numbers that
  begin so, a number the book lacks offers the nearest one, and **Random hadith** picks one. `iy chain kafi` prints
  the range; a missing number names the nearest.
- **What a bookmark is (BM2).** Every bookmark says its kind and a line on what it is (a narrator's road, tabaqa, death
  and verdict; which tree); places in the Genealogies can be bookmarked too ("Genealogy": a box of the tree of the
  prophets or of Quraysh, a narrator's family or line of learning) and open there. The ☆ says what it adds.
  `iy bookmark add tree prophets:musa`, `iy bookmark list tree`.
- **A new version starts clean (CFG1).** What the earlier version computed (`cache/`, `derived/`) is deleted once and
  computed again; settings, bookmarks, profiles, recent searches, the database and the downloaded works are kept. The
  footer (and the command line) says so once.
- **A page that fails does not stop isnady (ROB1).** It shows a plain card with **Check Installation** and **Data
  Sources**; the details go to `isnady.log` in the data folder. An import cut short (the window killed, the computer
  off) is named on the Search page at the next start, and on the command line.
- **Help → Check for Updates (UPD4).** PyPI and npm, whichever isnady is installed from — both offered, ticked, when
  both are behind — with what is new from the CHANGELOG. `iy update --check`, `iy update --npm`.
- **One language for every book (LANG2).** **File → Data Sources → Languages for every book**: a language added to
  every imported book that has it, or taken out of all of them, in one step (Arabic stays). `iy catalog languages`,
  `iy catalog languages add tr en`, `iy catalog languages remove ur`.
- **The first start (FR1).** With no books yet, isnady offers once to import isnady-data, in the background — the
  window usable meanwhile, the progress in the bar at the bottom.
- **Sunan al-Darimi's chapters in Turkish and English (BK2c).** All 1,382, written from the Arabic of the edition.

## [0.3.2] — 2026-10-18

- **More narrators identified in the chains (NR-ID1).** A name in a chain is now read by its neighbours too: whom the
  same teacher and student are in the chains where they are named in full (in three rounds, a reading kept only when
  it is three times as frequent as the next one), a client named as the "mawla" of his patron, and the well-known
  men a bare name means in a given circle — Ibrahim from 'Alqama is al-Nakha'i, Abu Ishaq from al-Bara' al-Sabi'i,
  al-Hasan from Anas al-Basri. A Companion whose generation the Taqrib leaves empty is read as a Companion.
  About 218,000 links are identified (52.6% of the Sunni chains' links, 42.4% of the Shia); Anas b. Malik now in
  1,295 chains, Nafi' in 2,037. The chains are read again once, the first time isnady opens (about half a minute).
- **Search in several languages at once (LANG3).** The language of the search is a list to tick: Arabic and Turkish
  together, say. The languages named in the Preferences are shown in the interface language.
- **All books in the Statistics (BK1).** The book list begins with *All books*: every section measured on both roads
  at once, each road under its own heading, never added together. `iy stats corpus --book @all` (with `--csv`, a
  folder for each road).
- **The Musnad's Companions in Turkish and English (BK2b).** All 1,252 chapters of Musnad Ahmad — the musnad of each
  Companion — are named in Turkish and English as well as Arabic, with the honorific the heading has: "Hz. Ebû Bekir
  es-Sıddîk (r.a.) müsnedi", "Musnad of Abu Bakr al-Siddiq (RA)".
- **Profiles (PRF1).** Several people on one isnady, each with their own settings, place in the books and bookmarks:
  **File → Profiles** — new, switch, rename, delete, export to one `.isnady-profile.zip` file and import it on another
  computer. The books and the database are shared; the first profile is the data folder itself, so nothing moves.
  `iy profile list|new|use|rename|delete|export|import`; `ISNADY_PROFILE` for a single command.
- **The Prophet ﷺ in the Genealogies (GEN1-P).** His name opens his life — birth, prophethood, Hijra, passing, family —
  in English, Turkish and Arabic, from Ibn Hisham, Ibn Sa'd, al-Tabari, Ibn Kathir, with al-Tirmidhi's *al-Shama'il*
  to read in isnady and Ibn Hisham's *Sira* in OpenITI.
- **The hadith about a prophet (GEN1-H).** A prophet of the tree opens the hadith that speak of him — the Sunni and the
  Shia books apart, each a click from its place in its book. `iy tree prophets Musa --hadith`.
- **The classical entry beside the written life (BIO2b) and the lives in the tree (GEN1-L).** For 109 written lives
  the entry of al-Dhahabi's *Siyar A'lam al-Nubala'* in its own words (vol. and number), downloaded once on request
  (about 22 MB, OpenITI) and kept in the data folder. `iy life "Abu Hurayra" --source`. The Companions, caliphs and
  Imams of the tree of Quraysh open their lives there, and the Narrators page links back to their place in the tree.
  The side panel of the Genealogies scrolls instead of squeezing its text.

## [0.3.1] — 2026-10-17

- **Musnad Ahmad and Sunan al-Darimi read by their chapters.** The two books come as numbered texts only, and the
  Books page showed each as one chapter, "Without a chapter in the source" (26,363 and 3,367 hadith). isnady now
  keeps their tables of contents, two levels deep: the Musnad in its 13 parts — the Ten promised Paradise, the
  Companions after the Ten, the Household of the Prophet ﷺ, Banu Hashim, the Companions who narrated most, of Mecca,
  of Medina, of Syria, of Kufa, the Ansar, the Tribes — and under them the musnad of each Companion (1,252: Abu Bakr
  al-Siddiq 1–77, 'Umar 78–375, 'Uthman, 'Ali …, Abu Hurayra from 6,822); al-Darimi in its 24 books and 1,382
  chapters. The headings are those of the Maymaniyya edition of the Musnad and the Dar al-Kitab al-'Arabi edition
  of al-Darimi in OpenITI, placed at their hadith by matching the texts (25,571 of 26,363 and 3,332 of 3,367
  directly, the rest by their neighbours). The parts and books are named in English, Turkish and Arabic; the
  Companions and the chapters keep the Arabic of the book. `iy book ahmad` lists them.
- **The lives written with reverence.** All 152 lives, in English, Turkish and Arabic, now name the Companions
  with "(may Allah be pleased with him/her)" — Hz. … (r.a.), رضي الله عنه — the Mothers of the Believers by their
  title, and the imams and scholars with "Imam" and "(may Allah have mercy on him)" — İmam … (rahimehullah),
  الإمام … رحمه الله; the martyrs are "martyred". On road B the Imami narrators and scholars are named with the
  same respect, and the Imams of the Prophet's family as Imam al-Baqir, Imam al-Sadiq, Imam al-Kazim, Imam al-Rida.
  The account of Imam Muslim's last night is told as the sources tell it.

## [0.3.0] — 2026-10-17

- **The lives of the Companions, the Successors, the narrators and the scholars.** A card *Life* on the Narrators
  and Hadith Scholars pages, in English, Turkish or Arabic. 152 lives written for isnady — the Companions who
  narrated most and the ten promised Paradise, the Mothers of the Believers, the Prophet's family, the great
  Successors and their followers, the imams of law and the great critics, the compilers of every book in isnady,
  the graders, and on road B the companions of the Imams, the narrators of Qum and the Imami scholars — each with
  the facts at a glance (full name, birth, death, family, teachers, students, works) and a life in a few
  paragraphs, summarised from the classical works named under it, each road from its own works. Every other
  narrator gets his life as far as the data says it, in plain sentences. The Hadith Scholars page no longer says
  "his life is planned". `iy life NAME` (`--lang en|tr|ar`).
- **Years of death read right.** Ibn Hajar names the tens once for several years ("died in seven, or eight, or
  nine and fifty" = 57–59): isnady read the first as 7 or 8 — Abu Hurayra showed "d. 8", Zayd b. Thabit "d. 5".
  And his rule for the century (tabaqa 3–8 after 100, 9 on after 200) put Successors who died in the 90s a century
  late ("Urwa d. 194", Sa'id b. Jubayr 195) and Yahya al-Qattan and Ibn Mahdi (198) in 298. 238 years of death
  are corrected, once, at the first start; the lists kept in the cache are counted again.
- **Every compiler on the Hadith Scholars page:** Ahmad b. Hanbal (al-Musnad), al-Darimi, al-Khatib al-Tabrizi
  (Mishkat al-Masabih) added; al-Adab al-Mufrad under al-Bukhari, al-Shama'il under al-Tirmidhi, Riyad al-Salihin
  under al-Nawawi, Bulugh al-Maram under Ibn Hajar.
- **Every narrator found can be reached.** The Search page ranked the closest 400 narrators and then said "add a word
  to find the others"; now "Show more" goes on past them, through every match ("محمد": 1,775). The Narrators page
  stopped at its first 200 ("narrow the search to see others"); now the next 200 are read when the list is scrolled
  to its end. `iy search --in narrators` reaches them with `--offset` and `--limit`.
- **English is back in the interface language menu.** The menu listed all 58 languages and was taller than the
  screen: opened upward from the sidebar it lost its first rows — English first. Now English, Türkçe and العربية
  (the translated ones) are in the menu, the languages not translated yet in a submenu of their own.

## [0.2.9] — 2026-10-14

- **A word with a letter you do not know, or a letter wrong, is found.** `?` stands for one unknown letter and `*` for
  any letters ("ي?من", "مسل*"). A search that finds nothing as typed is tried again with its words one letter away
  (a letter more, less or different), first the words found in no text, then every word — so several words may each
  have their own mistake: "لا يمن احدكم حتى يحب لاخبه" (two mistakes) finds the 14 hadith of "لا يؤمن أحدكم حتى يحب
  لأخيه", and "amelller niyetlere" finds "ameller niyetlere". The result line names the spellings used ("near
  spellings: يمن → يومن; لاخبه → لاخيه"); `iy search` prints the same line. Diacritics never mattered. The words
  of the texts are listed once with the search index (about 7 s on the full isnady-data, at the first start).
  Searches found as typed find what they found before.
- **A passage pasted from another source is found.** Punctuation that clings to a word — "قَالَ:", "«لَا", a comma,
  a question mark — is no longer part of the word looked for, and a phrase is found whatever punctuation or spaces
  stand between its words in the text ("قال: «لا يؤمن" finds "قال \"لا يؤمن"). A passage of the hadith "لا يؤمن
  أحدكم حتى يحب لأخيه" pasted with «» and ":" found nothing; now all words: Sahih Muslim 170, al-Nasa'i 5039, Musnad
  Ahmad 12338 and 13371; the exact phrase: Muslim 170. Searches without punctuation find what they found before.

## [0.2.8] — 2026-10-13

- **Every hadith shows its chain, as far as it can be read — no box instead of it.** v0.2.7 put a box "Chain not split
  into narrators" where a chain could not be split; now the chain is drawn: whole when it is read whole, as far as it
  is read otherwise (ending in "…", its reason in the tooltip), and with the narrators identified on it.
- **Two narrators at one link are two chains** ("حدثنا أيوب، ويونس، عن الحسن", Sahih al-Bukhari 31; "قالا / كلاهما"):
  the same links, that one replaced — as for a tahwil.
- **More chains read:** the Muwatta's "وحدثني عن مالك" (the narrator who says "haddathani" is not named), the
  Musnad's "قال حدثنا …" (Abdullah b. Ahmad's own "qala"), a number or a mark before the first term, "وحدثنيه".
  "وعنه" / "وعنها" (Mishkat, Riyad al-Salihin) and "وبهذا الإسناد" / "وبإسناده" take the chain of the hadith before
  them (the Companion alone for "from him", the whole chain for "with this chain").
- On the full isnady-data: 83,836 hadith with a whole chain (80,497 before), 12,476 more drawn as far as read or with
  the chain before them; 3,255 hadith without any link (19,287 before) — mostly texts that give no chain at all
  ("وقال رسول الله", "وفي رواية"). The statistics still measure whole chains only, so no chain is counted twice.
- A database read with the earlier rules reads only its unsplit chains again, once, at start.

## [0.2.7] — 2026-10-13

- **Chains joined by tahwil (ح) are drawn — each of them.** When a compiler joins a second road to the first with
  "ح" (Sahih al-Bukhari 89: Abu al-Yaman ← Shu'ayb ← al-Zuhri, ح, Ibn Wahb ← Yunus ← Ibn Shihab ← 'Ubayd Allah ←
  Ibn 'Abbas ← 'Umar), the hadith had no chain at all. Now each road is read and completed with the links the roads
  share — where "قالا / كلاهما / جميعاً" stands, or where the same narrator is named in both (al-Zuhri = Ibn
  Shihab) — and every chain is shown: on the search card and in the reader one under the other ("Chain 1", "Chain
  2"), on Isnad Chains each drawn whole, in `iy chain` one after the other. A narrator cited without a term of
  hearing ("وقال ابن وهب", ta'liq) is a link of its own ("said").
- **525 chains were taken for a tahwil that was not there:** the reader cut the text and the first letter of
  "حدثنا" or "حتى" left a lone "ح" at the cut. They are read as the plain chains they are.
- Together, on the full isnady-data: 950 more hadith have a chain (unsplit 20,237 → 19,287), 511 of them with two
  roads or more; every other chain is unchanged (checked chain for chain). A database read by the earlier rules
  reads only those hadith again, in seconds, not every chain.
- **A chain that could not be split is shown so it cannot be missed:** a gold-edged box with what happened ("Chain
  not split into narrators"), why, and the chain as written — instead of a grey line.
- Narrators are matched only for the chains with links not looked up yet when nothing else changed (18 s → 2 s after
  such an update).
- **Book menus scroll.** A list of books (Statistics, Search, the Lab, the Graders) opened as tall as all its books
  around the chosen one, and with 33 books its first entries — "All Sunni books", "All Shia books" — were above the
  screen. Every drop-down list now opens below its box and scrolls (20 rows at a time for the books, with the same
  row height as before).
- **Statistics: a book chosen while another is computed is computed next.** It used to be dropped, and the first
  book's results were then shown under the second book's name. The Graders section likewise.
- **Importing the sources two and a half times faster.** Every book of isnady-data took about 4 minutes (228 s on
  the test machine), now 1.5 minutes (92 s) — and the database is the same, table for table. Most of the time was
  never the download: it was the work after it. Identifying the narrators (80 s → 18 s): a name written in thousands
  of chains is looked up once, and the tabaqa test compares with the smallest and largest tabaqa of the neighbours
  instead of every pair. The search index (89 s → 32 s): the texts to index are found once, a first index is built
  by FTS5 in one pass, and the texts are folded by `str.translate` (twice as fast). The downloads (about 30 s, one
  after the other): the next three books download while one is written.
- **Updating tells what happened, and right after a release it works.** On Windows the update of a copy installed
  for all users runs behind the administrator prompt, in a window of its own that closed with pip's answer in it:
  the report then said "No problems found" although the copy was still the old version (checked without asking
  PyPI again). Now pip's output and its exit code come back to Help → Check Installation and `iy update`; the
  report after updating asks PyPI again, and when a copy is still behind it says so and why. pip is asked for the
  version PyPI reported (`isnady>=X`, never a step back), and always with `--no-cache-dir` — pip keeps PyPI's list
  of versions for 10 minutes, so an update a minute after a release found "already up to date". `pythonw.exe` beside
  `python.exe` is the same installation: it is no longer updated a second time (that run, without administrator
  rights, did nothing). The command lines shown are quoted for pasting (`"isnady>=0.2.6"`).

## [0.2.6] — 2026-10-12

- **Books twice as fast.** Opening a book or a chapter froze the window for about half as long as before and draws the
  whole chapter in about half the time (measured on the full isnady-data database: Sahih Muslim 1.5 s → 0.6 s, al-Kafi
  1.5 s → 0.7 s; the moment after the click 0.27–0.4 s → 0.1–0.2 s). A layout asks a text for its height at many
  widths before it settles; every one of them laid out the whole Arabic text again (1,245 layouts for the 180 texts
  of one chapter of Muslim). Now a text is laid out once, at the width it is shown at; its height at other widths is
  estimated from that, and the page ends exactly as tall as before. A book read without a search no longer folds
  every text for highlighting, and the cards of the chapter left behind are dropped without being taken out one by
  one.
- **Statistics compute without slowing the window.** The first computation of the Statistics page (about 30 s on the
  full database) now runs in a separate Python process (`core.stats_jobs`); the window stays responsive — the
  longest pause while it computes went from 1.2 s to 0.3 s — and the computation itself finished sooner (31 s instead
  of 50 s). Results already saved are read at once, as before; closing isnady ends a computation still running. In
  the packaged applications (exe, AppImage, macOS app) the computation stays in the background thread.
- **Help → Check Installation and `iy doctor` / `iy update` see an old record pip left behind.** When pip updates
  isnady but cannot delete the old version's record (`isnady-0.2.4.dist-info` beside `isnady-0.2.5.dist-info` in
  the same folder — seen on Windows in Program Files), the code is the new version's but pip reads the old record
  (`pip show isnady` said 0.2.4). The report used to show this as two installations, both "running", asked for
  an update that was already done, and updating again did not help. Now the record the code does not match is
  shown as a left-over record, the problem says what it is, and Update (or `iy update`) deletes only that record
  folder — with the administrator prompt or sudo when the folder needs it; the program itself is not touched.
- The Windows administrator command now quotes arguments that contain spaces.

## [0.2.5] — 2026-10-12

- **A cache for everything that costs time to read.** The books and their counts, the shelf of Books, the
  narrators' lists (Sunni and Shia, by tabaqa, rank and book) and their names read in Latin letters, each scholar's
  numbers as compiler, grader and critic, the chains' figures per book, the families read from the narrators' names,
  searches and the hadith they show: counted once and kept until the database changes — in memory and, for what is
  worth keeping across starts, in `cache/*.json` in the data folder (`core.cache`). Whether anything changed is told
  by a stamp of the database (a few counts and highest ids, read only when SQLite reports a write). JSON keeps the
  values' types (number keys, tuples, sets, counters), so a kept value is exactly what was counted.
- **The window opens in a fraction of the time and switching stays instant:** Isnad Chains, Narrators, Hadith
  Scholars and Books are no longer drawn before the window appears but right after it, one at a time while nobody
  waits; the narrators' list shows its first rows at once and the rest right after. Measured on the full
  isnady-data database (33 books, 99,444 hadith): window 2.5 s → 0.4 s, switching to a page 0.05–0.3 s, a search
  0.1–0.2 s, a chain, a narrator or a scholar 0.1–0.2 s.
- **`tools/measure_speed.py`:** measures, on the computer it runs on and with its own database, the start, every
  page, search, a chain, a narrator, a scholar, the books and their chapters, with a profile of where the time goes,
  and which isnady the `iy` command starts (a copy installed from PyPI does not have what was pushed to the source
  folder) — written to `isnady_olcum.txt` in the home folder.
- **Fixed: al-Shama'il al-Muhammadiyya could not be imported** ("invalid literal for int() with base 10: 'None'") —
  a chapter without a number in the source stopped the book; it is now passed over, and the shelf has its 17 Sunni
  books (16 before).
- The settings and the reader's remembered places are read from disk at most once a second; a chapter of Books shows
  its first four hadith at once. **Tools → Clear the Cache**, `iy cache info|clear`.
- **Fixed: the window froze when Books was opened** on a full database. Counting a chapter's sub-chapters and
  hadith read the whole table of chapters for every chapter (no index on the parent alone), so the first book's
  table of contents took seconds to minutes. A new index (`ix_work_nodes_child`, made once at the first start)
  brings it under a second (demo database: 4.5 s → 0.3 s).
- **Fixed: "database is locked" after the window was closed during the first import.** The import went on in the
  background and kept the database's write lock, so the next isnady could not open it. Now closing isnady while
  books are being imported asks first (the book being imported is not kept, those already imported stay) and,
  when the window is gone, the process really ends — SQLite rolls the unfinished book back at the next start. A
  connection waits up to 15 seconds for another one's write instead of 5, and if the database is still locked the
  page says why and how to end the other isnady, with a **Try again** button.

## [0.2.4] — 2026-10-11

- **Fixed: isnady stopped at start on a new computer** ("1st ORDER BY term out of range"). When the database held
  books whose texts were not (yet) imported — an import cut short, say — the book order was empty and the SQL read
  "ORDER BY 0" as a column number. The order now falls back to the book key; isnady opens and Data sources can
  import the books again.
- **The sidebar in a new order, and in your own:** Books comes second, after Search, and Learn last (Search, Books,
  Narrators, Isnad Chains, Hadith Scholars, Genealogies, Statistics, Bookmarks, Learn). **Preferences → Sidebar**
  reorders the sections — drag one to its place, or move it with the arrows; the page in view stays, Ctrl+1 …
  Ctrl+9 and the View menu follow the order, Default puts isnady's back. Setting `view.sidebar`
  (`iy config set view.sidebar books,search,narrators` — the sections not named follow in isnady's order).
- **Isnad Chains: every name in Latin letters beside its Arabic.** Each link of the chain shows the name as it is
  written in the chain, read in Latin letters on the left of the Arabic (it stood empty): Ebû Kâmil, Hammâd (yani
  İbn Seleme), İbn Ebî Atîk; a link that names no one by name is said in words — أبيه "his father", رجل "a man",
  عدة من أصحابنا "a group of our companions". A word not in isnady's list of names is spelled letter by letter and
  marked ≈ (its short vowels a guess). Shown in every left-to-right interface; Turkish readings in Turkish, English
  in the others. `core.isnad.name_reading`.

## [0.2.3] — 2026-10-11

- **Interface languages — 58 in the list:** the language of Azerbaijan is named **Azərbaycan türkcəsi** in its own
  letters and **Azerbaycan Türkçesi** in Turkish (no more "Azərbaycanca"). New: the Turkic languages — Қазақша,
  Кыргызча, Türkmençe, ئۇيغۇرچە (right to left), Татарча, Башҡортса, Qırımtatarca; the languages of Europe —
  Italiano, Nederlands, Polski, Čeština, Slovenčina, Magyar, Română, Български, Ελληνικά, Українська, Српски,
  Hrvatski, Slovenščina, Македонски, Shqip, Svenska, Dansk, Norsk, Suomi, Eesti, Latviešu, Lietuvių; and ไทย,
  Tiếng Việt, தமிழ், Kurdî, Soomaali. Each language is shown by its own name and by its name in the interface
  language (Lehçe, Yunanca, Kırgızca … in Turkish; Arabic names in Arabic) with how much of it is translated;
  the translations follow.

## [0.2.2] — 2026-10-11

- **Genealogies** (new section in the sidebar, `iy tree`): four trees one can zoom, move and click — **the
  prophets** from Adam to Muhammad ﷺ as Ibn Hisham, Ibn Sa'd, al-Tabari and Ibn Kathir give it (unknown generations
  drawn dashed, reports the sources differ on in a dashed box with their note); **Quraysh and the Prophet's family**
  ﷺ — the four caliphs' lineages joining his, the Umayyads, the Imams of the Shia; **a narrator's family**, read from
  the narrators' own names ("X b. Y b. Z" is the son of "Y b. Z" when exactly one narrator of that name, tradition
  and an earlier or the same generation is found — 1,147 links in the Taqrib and al-Najashi); **a narrator's line of
  learning**, his teachers above and his students below, from the imported chains. The Narrators page links to his
  family and his line of learning. The written trees name their Sunni sources by strength — the Qur'an, al-Bukhari
  (the Prophet's lineage ﷺ to 'Adnan), the sira and history works, the genealogists of Quraysh — and say where a
  name rests on the historians alone (between Adam and Ibrahim, between Isma'il and 'Adnan). `core/genealogy.py`,
  `assets/genealogy/trees.json`.
- **README screenshots** all retaken (the ☆ on every page, the two new sections); `tools/make_screenshots.py` makes
  the Genealogies and Bookmarks pictures too, putting back the user's own bookmarks afterwards.
- **Bookmarks** (new section, `iy bookmark`): a ☆ on every hadith card, narrator, scholar, term of Learn and chapter
  of Books; the Bookmarks page keeps them in folders of your own (nested, one bookmark in many folders, dragged onto
  a folder), with notes, found by words or kind, opened with a click, exported and imported as a file
  (`bookmarks.json` in the data folder; a hadith kept by its book and number, so it survives a new import).
- **Learn in colour**: each category with its colour and sign — chips above the list (one category alone with a
  click), dots before the terms, the band of the card, the "In short" box, the related terms; the card reads In
  short, In detail, source, related terms, more of the same category.

## [0.2.1] — 2026-10-11

**Book and chapter titles in Turkish and Arabic, statistics tables that can be read, the other languages one
click away, and Check Installation that updates by itself.**

- **Chapter titles in the interface language.** The sources give their chapter titles in English only (every
  language file of isnady-data carries the same English titles), so the Turkish of Sahih al-Bukhari stood under
  "Revelation", "Belief" … isnady now carries its own: all 642 chapter titles of the 33 books in Turkish and in
  Arabic (`isnady/assets/i18n/titles/tr.json`, `ar.json`), and the Arabic titles a source gives itself where it has
  them (al-Adab al-Mufrad, Bulugh al-Maram, Mishkat, Riyad al-Salihin, al-Shama'il) — in Books, the chapter list,
  the path above the reader. `core.titles`; `python tools/i18n.py titles CODE` lists what a language still lacks.
- **Book titles in the interface language** everywhere a book is named — the shelf, the search cards, "Also
  narrated in", Isnad Chains, Narrators, the book pickers, the statistics: *Sahîh-i Buhârî*, *صحيح البخاري*; the
  name an import gave a book ("Sahih al Bukhari") no longer shows. Saved statistics keep the English title, so
  they are the same in every language; the screen translates them.
- **Graders by their names in the interface language** in the statistics: Elbânî, Arnaût, Zübeyr Ali Zaî,
  Muhyiddin, Meclisî, Behbûdî (الألباني … in Arabic). `scholars.short_name`.
- **Statistics tables that can be read.** A cell with one figure drew it in the upper half only, so in the small
  cells of the confusion matrices and the cross-tables the figures were cut ("12%", "8%", "77%"); the colour of
  the figure is now chosen by contrast (white on dark cells, near-black on light ones), the cells are larger, the
  empty corner says what the rows and the columns are ("true grade ↓ / the grader says →"), and pointing at a
  cell says it in words.
- **More languages one click away in Search**: the language list holds the languages imported; at its end it
  names the languages the same books have in isnady-data and not here (Urdu, Indonesian, Bengali, French,
  Russian, Tamil) — choosing it opens File → Data Sources.
- **Check Installation updates by itself**: an **Update** button runs the update of every copy where it is
  installed (what `iy update` does) and shows the output as it comes; a copy installed for all users asks for
  the administrator password in the system's own window (pkexec on Linux, the Windows administrator prompt); after
  it, the report is made again and the ⚠ in the sidebar goes away when nothing is left. The report is in the
  interface language.
- Fixed: an editable copy (a clone installed with `pip install -e`) was reported with the version of the day it
  was installed ("0.1.9 editable" while it ran 0.2.0); its version is now read from its source.

## [0.2.0] — 2026-10-11

**The interface in Turkish and Arabic, with 24 languages to choose from; every narrator's name in Latin letters;
the glossary in Arabic; the Shia scholars on the Hadith Scholars page and the Statistics on two roads — the Sunni
and the Shia books each measured in its own terms.**

- **Every narrator's name in Latin letters.** A name with a word isnady's list of names did not know was shown
  only in Arabic — 2,863 of 10,090 narrators (Yazid b. Ruman, Isma'il b. Raja', 'Ali b. Ri'ab, Jamil b. Darraj,
  'Ali b. Mahziyar, al-Miswar b. Makhrama …), in the Narrators list, the teachers and students, Hadith Scholars and
  Statistics. The list has 395 more words (Turkish and English, the most frequent first), and a word still unknown
  is spelled letter by letter from the Arabic (`names.spell`): the consonants are the Arabic's, the short vowels a
  guess, and the name card says so ("Latin letters spelled from the Arabic", the reason on hover). Words that end a
  name — "غير منسوب", "وهو", reading notes — stop it instead of being read as names.
- **"In the chains of … hadith" in straight columns**, the book named once above its own hadith ("Sahih al-Bukhari"
  as isnady writes it, whatever the imported source called it — `books.title`), each link "hadith 1390.3".
- **Learn in Arabic**: the 81 terms with their definitions in Arabic too, the categories, the search; the glossary
  opens in the interface language (English, Türkçe, العربية), Arabic right to left. `iy term mursal --lang ar`.
- Fixed: in Turkish, "rank 3 of 12" after the critic's Arabic words was turned around ("12 ● ثقة dereceden 3.");
  "their client" and "(place)" are translated; the dates of the scholars ("d. 279 AH (892 CE)") and the books'
  facts (kind, hadith, chapters, the language boxes) too.

- **The interface in Türkçe and العربية** (sidebar, or View → Interface Language). Choosing Türkçe used to change
  only how names are read; now menus, every page, buttons, messages, explanations, the statistics (findings,
  "How to read", tables and charts' words) and the progress messages are translated — 1,174 texts, all of them
  in Turkish and Arabic. Arabic runs right to left, the whole window mirrored. The window is rebuilt in the new
  language at once, nothing to restart; the place in it is kept.
- **24 interface languages in the list**, each in its own name with how much of it is translated: English,
  Türkçe, العربية, Deutsch, Français, Español, Português, Русский, Bahasa Indonesia, Bahasa Melayu, हिन्दी, اردو,
  বাংলা, 中文, 日本語, 한국어, فارسی, دری, پښتو, Azərbaycanca, Oʻzbekcha, Bosanski, Kiswahili, Hausa (Urdu, Persian,
  Dari and Pashto right to left). A text not translated yet is shown in English; the others follow release by
  release.
- **Translations are files**, one per language (`isnady/assets/i18n/<code>.json`, English text → translation),
  so anyone can add or correct one. `python tools/i18n.py extract` collects every text of the program into
  `en.json`; `check`, `missing CODE`, `merge CODE FILE` and `prune` keep the others in step (a translation that
  drops a `{field}` is reported and English is shown instead).
- Still in English: the command line, the chapter titles and texts of the books, scholars' names and works, the
  glossary outside English and Türkçe.

- **Shia scholars on the Hadith Scholars page**, each by his own road: the compilers al-Kulayni, al-Shaykh al-Saduq,
  al-Shaykh al-Mufid, Ibn Qulawayh, al-Nu'mani, al-Shaykh al-Tusi, al-Husayn b. Sa'id al-Ahwazi and Asif al-Muhsini;
  the graders al-'Allama al-Majlisi, Muhammad Baqir al-Behbudi and al-Muhsini; the critic al-Najashi. *All / Sunni /
  Shia* at the top, a gold *Shia* tag. A Shia compiler's chains are counted to a Ma'sum (whom they reach, Imam by
  Imam) and his narrators identified in al-Najashi; a Shia grader is compared only with the Shia graders, on the
  four Imami categories (sahih, hasan, muwaththaq, da'if — majhul, mursal and marfu' among the da'if;
  `grades.imami_group`), never with the Sunni groups; al-Najashi's verdicts are counted in the Imami terms with the
  creeds he states. The same in `iy scholar`.
- **Isnad Chains**: the overview says which road each book is read on, a Shia book's card in gold with "reach a
  Ma'sum" and "identified in al-Najashi"; a Shia hadith says so beside its title; a chain raised with "رفعه" shows
  the gap instead of "stops before a Ma'sum"; a number that is not in the book says how the book numbers its
  hadith (al-Kafi: volume:hadith, "5:1740"); "إجازة" and other words of how a text was received are no longer read
  as part of a narrator's name (parser isnady-isnad-6).
- **Statistics on two roads**: *All Sunni books* (Ibn Hajar's ranks, chains to the Prophet ﷺ) and *All Shia books*
  (al-Najashi's Imami categories, chains to a Ma'sum) are measured apart — the Shia books were counted with the
  Sunni ones before, with 0% of their names identified; one Shia book is measured on its own road too. Fixed: sections that
  ran off the right edge (the cross-tables now one under the other, the map of shared narrators sized to the page,
  the books table fitted), and the median chain length counted over the chains split into names (Sahih Muslim
  showed "—"). `iy stats … --book @shia`. Saved results are named `corpus-all_sunni_books.json`,
  `corpus-all_shia_books.json`.
- **Statistics: one book for the whole page.** The Graders section had its own book list beside **Books** above,
  so the page could show two different books at once (Books: Fada'il al-Shi'a, Graders: Sunan al-Nasa'i). Now the
  two move together: a book chosen above is the book of Graders; a book chosen in Graders becomes the book above;
  a book with fewer than two graders says so instead of showing another book's graders.
- **Statistics: no empty pages on the Shia road.** *Grades and chains*, *The hadith model* and *Correlations and
  tests* showed only a note for a Shia book. Every measure is now written once and run on each road with its own
  scale (`stats_corpus.Road`): for al-Kafi, al-Majlisi's grades in the four Imami categories against the weakest
  narrator in al-Najashi's categories, the ordinal model of his grades (13,276 hadith; the weakest narrator carries
  77.7% of what the chain explains), the correlations, Brant's test and the narrators' matrix (no generations: al-
  Najashi gives none). al-Behbudi's *Sahih al-Kafi* is a selection — he names only what he holds sahih — so he is
  shown as one: of his 225 hadith that al-Majlisi grades, al-Majlisi calls 35.6% sahih; no kappa, alpha or model is
  made of a grader who never says anything else. Graders now takes Shia books too, on the Imami categories; a grader
  with fewer than 20 grades of a book is named, not measured (al-Muhsini: 1 of al-Kafi). Why a chain whose weakest is
  "praised" is so often sahih is said in the page: al-Najashi praises Zurara, Ibn Abi 'Umayr and Ahmad b. Muhammad
  b. 'Isa without the word thiqa; al-Tusi and the later scholars count them thiqa.
- **Statistics: the disputed-hadith table reads plainly.** Short names in the headers (the full name on hover; the
  header was cut to "nmad Muhyi al-Din 'Abd al-"); *not graded*, muted, instead of "—"; a *Voices weighed* column
  ("sahih 1 · da'if 1") so the many 64% rows explain themselves — one voice against one, the model siding with the
  grader closer to the others; the grader who is one voice with another (Muhyi al-Din ≈ al-Albani) marked and muted.
  The confusion matrices no longer show rows of "too few"; the true grades without data are named under them.
- **Statistics: headlines follow the data.** "for every grader (τ 0.13 to 0.13)" with one grader, "Longer chains are
  graded a little lower" when they are not, and "against 58% by always saying sahih" when the commonest grade was
  da'if are now said from the numbers. The surprises say how many are clear (the model gave that grade 5% or less).
- **al-Najashi: "من أوثق الناس" is thiqa** (Muhammad b. Muslim was read as only "praised"); takes effect when al-
  Najashi's Rijal is imported again. Saved statistics are recomputed once (isnady-corpus-3, isnady-models-2,
  isnady-lab-3, isnady-graders-4).

## [0.1.9] — 2026-10-11

**Sunni and Shia each by its own road — the Shia chains read the Shia way and identified in the Shia rijal works;
isnady-data read from this computer or taken as a whole ready database; results and shelves in the order of the
books; the READMEs of isnady and isnady-data written anew.**

- **Data from this computer**: a copy of isnady-data (a git clone, a USB stick, a shared folder) is a repository
  too — **A folder on this computer…** in Settings → Data sources, or `iy repo add ~/Github/isnady-data` — and
  every book is read from that folder, without the network. A whole ready database can be taken from a file —
  the `isnady-db-<date>.zip` of the isnady-data Releases, or an `isnady.db` — with **Use a ready database…** (Data
  folder) or `iy database use FILE`: it is checked (a zip must hold isnady.db, the schema must be one this version
  reads, the sha256 must match a `database.json` beside it), takes the place of the database at the next start,
  and the database it replaces is kept beside it (`isnady.<date-time>.bak.db`).
- **README written anew** around the two repositories of the project — **isnady** (the application) and
  **isnady-data** (the data: 17 Sunni and 16 Shia collections, 99,746 hadith, the Taqrib and al-Najashi) — with
  what isnady-data holds, its layout and formats, how to use it online, offline or as a ready database; every
  section brought up to date (two roads, narrators of both traditions, books, statistics, the data folder, the
  full CLI); the other datasets isnady can read in one short table. The **isnady-data README** too
  (`tools/build_data_repo.py --readme DIR` writes it from the catalog: what it holds, book by book with import ids,
  the layout, the formats, how it is made, licences and credits).
- **README** on GitHub, PyPI and npm with new screenshots: search narrowed to a few books with the other
  languages folded, the book list, the Narrators, hadith model and correlation sections of Statistics, Data
  sources, Books and languages; the isnady-data README shows how to use it from this computer.
- **Sunni and Shia narrators on one page, each tradition by its own road** (SH1). The Shia Rijal section is gone
  from the menu: **Narrators** shows *All*, *Sunni* or *Shia*, every Shia narrator with a gold *Shia* tag and his
  critic's verdict in the Imami terms (never on Ibn Hajar's scale). Every value derived from a chain is reached
  along the book's own tradition (`core/traditions.py`): road A for the Sunni books, road B for the Shia books.
  - **Shia chains are read the Shia way** (`isnad.parse(text, "shia")`, parser isnady-isnad-5): the teacher named
    without a term (al-Kulayni), "عدة من أصحابنا" with the teachers al-Kulayni said each group stands for, two
    narrators at one link, two roads joined by "جميعاً", "رفعه", unnamed narrators ("عن رجل", "بعض أصحابه"),
    "عنه", "بإسناده" (kept whole), the hadith number and the student's "قال:" at the head, al-Saduq's
    "رضي الله عنه … قال: حدثنا", places and dates after a name. The chain ends at one of the Fourteen
    Ma'sumun — the Prophet ﷺ or an Imam, most often by his kunya (أبو عبد الله = Ja'far al-Sadiq, أبو جعفر =
    al-Baqir, أبو الحسن = al-Kazim or al-Rida); "سألته" is *mudmar*. al-Kafi: 96.8% of 14,239 chains split
    (was 9), 92% reach a Ma'sum; 'Uyun Akhbar al-Rida and al-Mufid's Amali from none to 608 and 333.
  - **Shia chains are identified only in Shia rijal works** (al-Najashi; al-Tusi when imported), Sunni ones only in
    the Taqrib; al-Kulayni's own teachers are recognised at the head of his chains (محمد بن يحيى is al-'Attar) and
    "ابن أبي عمير" by his father's name. al-Kafi: 29,652 of 61,160 names identified (was 3).
  - The chain page draws the Imam the chain reaches, explains al-Kulayni's groups and the unnamed narrators, shows
    al-Najashi's verdicts in their own terms, and says when a second road joins; `iy chain kafi 5:1740` and
    `iy isnads` likewise. Database schema 8: `isnads.ends_with` (whom the chain reaches) and `isnads.raised`.
- **Rebuilding the chains no longer takes hours**: an index on `grades(isnad_id)` — removing the old chains read
  the whole grades table once per chain (the demo database: 235 s → 1 s; a full one: hours, and the window did not
  open). Every database gets it when it is opened.
- **Search results in the order of the books**: Sahih al-Bukhari, Sahih Muslim, Sunan Abi Dawud … then the Shia
  books, as the book lists show them — they came by title, so al-Kafi and 'Uyun Akhbar al-Rida stood before
  Sahih al-Bukhari. The same order for a narrator's hadith, `iy isnads` and `iy stats` (`books.order_sql`).
- **Books: the Shia books on the shelf in plain sight.** The shelf showed every book in one short list, Shia ones
  last, so they sat below the fold. Now the Sunni and the Shia books (hadith collections, then rijal works) stand
  under their own headings, *All / Sunni / Shia* at the top shows one of them alone (remembered), every Shia book
  carries a gold *Shia* tag, and the list is taller. `works.list_works` gives each book its tradition.

## [0.1.8] — 2026-10-10

**isnady's own data repository with every Sunni and Shia source, books in order and in full name, search in a few
books, and the correlation and test laboratory.**

- **Data repositories** (Settings → Data sources; `iy repo`): isnady reads its sources from a repository — a
  `catalog.json` listing books and rijal works with their files, licences and tradition. The default is isnady's
  own, [isnady-data](https://github.com/bayramkotan/isnady-data): every Sunni and Shia source isnady reads (35), in
  one place and in isnady's own format, each book in a folder named by its full title and its compiler —
  `sunni/sahih_al_bukhari/`, `sunni/musnad_ahmad_ibn_hanbal/`, `shia/al_kafi_al_kulayni/`,
  `rijal/sunni/taqrib_al_tahdhib_ibn_hajar_al_asqalani.md`, never a bare name. Sunni: the six books, the Muwatta,
  Musnad Ahmad ibn Hanbal, Sunan al-Darimi, Riyad al-Salihin, al-Shama'il al-Muhammadiyya, Bulugh al-Maram, al-Adab
  al-Mufrad, Mishkat al-Masabih and three forty-hadith books, in Arabic and up to eight translations, with grades.
  Shia: al-Kafi of al-Kulayni in eight volumes with al-Majlisi's and al-Behbudi's grades, the books of al-Shaykh
  al-Saduq, al-Shaykh al-Mufid, al-Shaykh al-Tusi, Ibn Abi Zaynab al-Nu'mani, Ibn Qulawayh, al-Husayn ibn Sa'id
  al-Ahwazi and Asif al-Muhsini, in Arabic and English. Rijal: Ibn Hajar's Taqrib al-Tahdhib and al-Najashi's Rijal.
- Optional repositories in the same list — the datasets others publish (fawazahmed0/hadith-api, Thaqalayn, Open
  Hadith Data, hadith-json, the LK Hadith Corpus, Hugging Face meeAtif/hadith_datasets, Hadith-Data-Sets, OpenITI),
  each book under its own key so editions numbered differently never mix — and any repository with a catalog can
  be added (a GitHub repository, a Hugging Face dataset, a URL or a folder) and chosen. The catalog is kept for a
  day; offline, the copy shipped with isnady is used.
- **isnady's book format** (isnady-book/1): `book.json` (numbers, chapters, references, grades) and one file per
  language, so only the languages chosen are downloaded; a book imported earlier straight from its publisher is
  replaced, not shown twice. A second importer reads any CSV or JSON table of hadith through a column mapping.
  `iy catalog import musnad_ahmad_ibn_hanbal`; the short keys of earlier versions (`ahmad`, `fawaz-bukhari`) are
  still understood, and every command that takes a book takes its full name (`iy chain sunan_abi_dawud 1`).
- **Books in order, Sunni and Shia apart**: every book list (Search, Isnad Chains, Statistics, Books) shows the
  Sunni collections first — the six books, the Muwatta, the Musnad and al-Darimi in their classical order, then the
  others by name, read without a leading 'ayn or article — and the Shia collections after them, al-Kafi first,
  each group under its own heading. The Data sources page lists the repository's sources the same way, with their
  Arabic titles, tradition and licence.
- **Search in a few books**: Books on the Search page opens a list to tick — all books, all Sunni, all Shia, or any
  few one by one; a narrowed search is marked.
- **Settings → Books and languages**: switch any imported book off (it stays in the database, but is left out of
  searches, book lists and statistics until switched on again; statistics keep a saved result for each set of
  active books, so switching back reads it instead of computing again); choose the languages the texts are shown
  in, the others folded behind an arrow on each hadith (▸ Other languages: English) or left out.
- **Correlations and tests** (Statistics → Correlations and tests; `iy stats lab [--book] [--csv DIR]`): every
  measure against every other by rank — Spearman's ρ with Benjamini–Hochberg q-values and the partial ρ with all
  the others held equal (what each factor of the chain says of each scholar's grade on its own); the scholars'
  grades compared pair by pair (Stuart–Maxwell); Brant's test of the hadith model's proportional-odds shape, with
  the odds ratio at each step; the narrators' measures (rank, generation, death, times in the chains, teachers,
  students, PageRank); the books compared (Kruskal–Wallis with ε², Mann–Whitney with Cliff's δ, Holm). Every matrix
  switches between each pair alone and the others held equal; a pair that could be chance is outlined, not
  coloured; every figure on hover and every table as CSV. Checked against SciPy and statsmodels; Brant's test by
  simulation.
- Saved computations are named by the book's full name (`derived/lab-sunan_abi_dawud.json`), and
  `tools/publish_database.py` sends this computer's database (as a Release of isnady-data, without your own
  sources) and every saved computation (`derived/`) to isnady-data.

## [0.1.7] — 2026-10-08

**Statistics in depth: the narrators, the chains and the grades measured, each finding said in a sentence.**

- **A new Statistics page**: one section at a time — Overview, Narrators, Chains, Grades and chains, Books, Graders —
  each a few findings: a sentence that says what the numbers show, the chart that shows it, the figures on hover,
  and, folded until asked for, how to read it and how it was measured. Every finding can be saved as CSV for a
  thesis or a paper. All books or one, chosen at the top; computed once in the background and kept while the data is
  unchanged.
- **Narrators**: Ibn Hajar's ranks of everyone he judged, of the narrators in the chains, and of every name counted
  as often as it appears (what the hadith actually rest on); how concentrated the transmission is (Lorenz curve,
  Gini, the busiest 1% and 10%, how few carry half); the pillars, the weak narrators the most hadith pass through,
  the network (PageRank on who narrates from whom), and reliability generation by generation. Names in the interface
  language; a click opens the narrator.
- **Chains**: length (isnad 'ali and nazil); the weakest link of every chain; teacher–student pairs too far apart in
  time and pairs out of the order of generations — each a sign of a wrongly identified name or a wrong year, listed
  so it can be checked.
- **Grades and chains**: does the weakest narrator foretell the grade? Kendall's tau-b and Goodman–Kruskal's gamma
  with bootstrap intervals for every grader of every book, the cross-tables behind them, and chain length against
  grade. Ranks and grades stay ordered categories: counted, cross-tabulated and rank-correlated, never averaged.
- **The hadith model** (Statistics → The hadith model; `iy stats model`): what each scholar's grade follows, as an
  ordinal (proportional-odds) regression of the grade on the hadith's best chain — its weakest narrator, further weak
  narrators, length, names not identified, chains in the book, narrations elsewhere, stopping short of the Prophet, a
  doubtful link. Odds ratios with 95% intervals, a likelihood-ratio test for every factor (Holm-adjusted), McFadden's
  R², accuracy against the base rate, Somers' D, a calibration chart; the hadith graded higher than their chain
  foretells (candidates for strengthening by other routes) and lower (candidates for a hidden defect), and the
  surprises several scholars share. Fitted in pure Python and checked against statsmodels' OrderedModel (the same
  estimates; standard errors within 0.005).
- **Books** side by side, and the narrators each pair of books shares.
- **Command line**: `iy stats corpus|narrators|chains|grades|books [--book KEY] [--csv DIR]`.
- Charts follow one design: thin marks, a two-sided blue–grey–red scale for ranks and grades (accepted ↔ rejected),
  solid hairline grids, a legend and the figures on hover so colour never carries meaning alone.

## [0.1.6] — 2026-10-08

**Names in your language, the two languages always in sight, close spellings found, and themes that change at once.**

- **Names read in the interface language**: every Arabic name isnady can read is shown in Latin letters where it
  was shown only in Arabic — the teachers and Companions of a compiler (Hadith Scholars), a narrator's teachers and
  students (Narrators) — with the Arabic on hover; a name isnady cannot read yet stays in Arabic.
- **Two languages, always in sight** (sidebar, and View → Interface Language / Content Languages): the
  **interface** language, English or Türkçe, decides how names are read (Musaddad b. Musarhad / Müsedded b.
  Müserhed) and the language of the glossary — menus and pages are in English for now; the **content** languages
  are the languages the hadith texts are shown in (all, or those chosen). A text a search matched is shown whatever
  its language, and each book in Books can still choose its own. `iy config set view.ui_language tr`,
  `iy config set view.content_languages "Arabic,Turkish"`.
- **The npm README is written the same on every system** (LF line endings), so its MD5 is the same on Windows.

- **Close spellings** (Search → Narrators and Scholars, the Narrators page, `iy search --in`): when the letters
  typed find little, isnady looks for names one slip away — a letter typed twice or missing ("zuberyyyr",
  "Buhaari", "Müslümm"), two letters swapped, one wrong, or written as Turkish and English differ (h and kh,
  "Buhari" = al-Bukhari; z and dh, "Muaz bin Cebel" = Mu'adh b. Jabal; a final h, "Abu Hurayrah"). They come after
  every exact match, each card marked "≈ close spelling", and the page says when nothing was written exactly so.
- **Weaker matches apart**: Arabic is written without its short vowels, so names are matched by their consonants
  first — and "Bayram" (b-r-m) has the consonants of al-Barmaki. A Latin query is now compared with the READINGS of
  the parts of the name it matched; where the vowels differ the match is weaker, shown after the others under
  "Weaker matches" with the reason, and each such card names the word it matched (البرمكي). A name isnady cannot
  read yet is marked "same consonants" rather than judged.
- **Turkish and one-word names**: "İbni Abbas", "İbni Ömer", "binti" are read as ibn and bint; "Abdullah",
  "Abdurrahman", "Abdülaziz", عبدالله typed as one word are found as the books write them (عبد الله, عبد الرحمن);
  an Arabic name typed without the article finds it with it (زبير finds الزبير).

- **A new theme in under a second or so, instead of five to seven**: Qt styles every widget of the window again,
  the hidden pages too, and every page was then drawn again — the two narrator lists alone are two thousand
  widgets. Now the pages let go of what they show before the new style is applied, the page in view is drawn at
  once, and every other page is drawn when it is next opened. The style engine is no longer set up again on every
  change. Measured with Sunan Abi Dawud, the Taqrib and al-Najashi imported: 5.5–7.6 s before, 0.7–1.3 s now.
- **Pages draw faster**: the settings file is read again only when it changes (drawing the Narrators list asked
  for it over a thousand times), and the names a narrator is known by are not worked out again while nothing
  in the database has changed. The Narrators and Shia Rijal pages open in about half the time.

## [0.1.5] — 2026-10-08

**Search finds people: the narrators of both traditions and the scholars of hadith.**

- **Search → Narrators / Scholars**: a drop-down before the search field chooses what is searched — Hadith (the
  default at every start), Narrators or Scholars. Each card shows the person in brief: the name he is known by, in
  reading and in Arabic, his full name, his standing in words (the Arabic term and Ibn Hajar's rank, or al-Najashi's
  judgment and the narrator's school, on hover), his generation, year of death and how often he is in the imported
  chains. A click opens him on his own page: Narrators, Shia Rijal or Hadith Scholars.
- **Both traditions in one search**, each card marked Sunni or Shia, with a Tradition filter. The two are never
  matched to each other: each keeps its own terms.
- **The closest first**: the person KNOWN by the words typed (Abu Hurayra, al-Zuhri, Ibn Umar), then those in whose
  name they stand, then those whose entry only mentions them. A scholar known by the name is first among the
  narrators too ("Bukhari" → Muhammad b. Isma'il, "Abu Dawud" → Sulayman b. al-Ash'ath).
- **Turkish and English spellings alike**: "Âişe", "Ebû Hüreyre", "İbn Ömer", "Câbir", "Buhârî", "Elbânî" find
  the same people as "Aisha", "Abu Hurayra", "Ibn Umar", "Jabir", "al-Bukhari", "al-Albani". Names are matched by
  their consonants, and the vowels then put A'isha before al-A'sha and Umar before 'Amir.
- **Narrator search, also on the Narrators page**: "b." is read as ibn ("Hammad b. Zayd" found nothing); a match in
  the person's own entry counts above the same name read from another entry; a two-letter skeleton ("Anas",
  "Aisha") must be a whole word, no longer the beginning of hundreds.

## [0.1.4] — 2026-10-06

**Portable applications, a fix for every new computer, graders compared fairly, and seven themes.**

- **Themes**: seven, each drawn as a small live isnady window in Edit → Preferences → **Themes** (and listed in View →
  Theme): Lapis and Lapis Night (followed by "Follow system"), Paper, Slate (light sidebar), Emerald, Midnight and
  High Contrast. A click applies the theme at once; `iy config set view.theme slate`. Cards are rounder and the
  sidebar rows have more room.
- **First start on a new computer fixed**: since 0.1.0 a fresh database could not be built — an index stood in the
  schema before its table — so the first import on a computer that had never run isnady failed ("no such table:
  isnad_links"). Databases upgraded from earlier versions were never affected, which is why it went unseen. The
  tables are now created in order, and every release first builds a database from nothing (`tools/release_check.py`).
- **Graders compared fairly**: a grade of the chain only ("Isnaad Sahih" — the chain is sound, the text not judged)
  is no longer compared with a grade of the hadith ("Munkar"). It was 25.8% of Zubair 'Ali Za'i's grades of Sunan
  Abi Dawud (4.5% of al-Albani's). Statistics → Graders and the Hadith Scholars page leave such grades out and say
  how many: alpha 0.705 → 0.738; al-Albani–Zubair agreement 70.0% → 74.4%; Zubair's strictness −0.10 → −0.14.
  The alignment of his grades with the hadith numbers was checked and is right (no shift fits better, in any part
  of the book).
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
