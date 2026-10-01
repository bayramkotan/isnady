<h1 align="center">📜 isnady &nbsp;<sub>إسناد</sub></h1>

<p align="center">
  <strong>Hadith search built around the isnad, the chain of transmission</strong><br>
  <sub>The JavaScript and TypeScript package</sub>
</p>

<p align="center">
  <a href="https://www.npmjs.com/package/isnady">
    <img src="https://img.shields.io/npm/v/isnady?style=for-the-badge&color=14304F&logo=npm&label=npm" alt="npm">
  </a>
  <a href="https://pypi.org/project/isnady/">
    <img src="https://img.shields.io/pypi/v/isnady?style=for-the-badge&color=1D4777&logo=pypi&logoColor=white&label=app%20on%20PyPI" alt="PyPI">
  </a>
  <img src="https://img.shields.io/badge/License-MIT-D6B25E?style=for-the-badge" alt="License">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/bayramkotan/isnady/main/assets/screenshots/chain.png" alt="The isnady app — the chain of Sahih al-Bukhari 1 from the book to the Prophet" width="780">
</p>

---

## 🧭 Where things stand

**isnady** is a hadith search application whose centre is the *isnad*: it reads each
chain of transmission from the Arabic text, narrator by narrator, and explains what each
link means. The application runs today on Windows, Linux and macOS:

```bash
pip install isnady
iy
```

**This npm package is the JavaScript side, and it is not functional yet.** It will be the
client of the isnady.net web service, which runs the same engine as the application, so a
chain read on the web and in the app always gives the same answer. Until that service
exists, the package only reports its version:

```js
import { info, version } from "isnady";

console.log(version); // "0.0.9"
console.log(info());  // { name: "isnady", version: "0.0.9", dataLoaded: false, homepage: "…" }
```

TypeScript declarations are included.

## 🗺️ Planned

```js
import { searchHadith, getChain, getNarrator } from "isnady";

const results = await searchHadith("النيات", { book: "bukhari" });
const chain   = await getChain("bukhari", 1);      // narrators and the words linking them
const person  = await getNarrator(chain.links[0]); // biography, teachers, students, verdicts
```

Search with Arabic diacritics ignored, chains read narrator by narrator, and grades shown
exactly as each scholar gave them — the same results as the application.

## 🔗 Links

- **Application and source:** [github.com/bayramkotan/isnady](https://github.com/bayramkotan/isnady)
- **Python package:** [pypi.org/project/isnady](https://pypi.org/project/isnady/)
- **Issues:** [github.com/bayramkotan/isnady/issues](https://github.com/bayramkotan/isnady/issues)

## 📝 License

MIT. Hadith data comes from separate sources, each under its own licence.
