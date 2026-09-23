# isnady (JavaScript)

Hadith search built around the **isnad** — the chain of transmission.

This is the JavaScript/TypeScript package of [isnady](https://github.com/bayramkotan/isnady).
The desktop application is published on PyPI as `isnady`; both packages will read the
same SQLite database of hadith, chains, narrators and verdicts.

> **Status: pre-alpha (0.0.1).** This release only reserves the name and exposes version
> information. No hadith data is included yet.

## Install

```
npm install isnady
```

```js
import { info, version } from "isnady";
console.log(version);   // "0.0.1"
console.log(info());
```

## Planned

- `searchHadith(query, options)` — by text, book, narrator and grade
- `getNarrator(id)` — biography, teachers, students, verdicts, reliability score
- `getChain(hadithId)` — the isnad, link by link

## License

MIT for the code. Hadith and narrator data will come from separate sources, each under
its own license, listed in the main repository as they are added.
