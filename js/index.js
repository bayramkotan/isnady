/**
 * isnady — hadith search built around the isnad.
 *
 * This is a placeholder release: it reserves the package name and exposes
 * version information only. The search API arrives once the shared SQLite
 * database (used by both the Python and JavaScript packages) exists.
 */

export const version = "0.0.5";
export const name = "isnady";

/** Returns basic package information. */
export function info() {
  return {
    name,
    version,
    dataLoaded: false,
    homepage: "https://github.com/bayramkotan/isnady",
  };
}
