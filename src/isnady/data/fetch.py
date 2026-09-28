"""Read a resource from a local path or a URL, with optional authentication.

Supported authentication: none, HTTP Basic (username + password), bearer token,
and API key (sent as a header or as a query parameter).

Credentials are used for the request only. They are never written to the
database or to disk; the database records the authentication TYPE alone.
"""

import base64
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from isnady import __version__

USER_AGENT = f"isnady/{__version__} (+https://github.com/bayramkotan/isnady)"
TIMEOUT_SECONDS = 60


class ResourceError(Exception):
    """A resource could not be read. The message is meant for the user."""


@dataclass
class Auth:
    kind: str = "none"            # none | basic | bearer | apikey
    username: str | None = None
    password: str | None = None
    token: str | None = None
    key_name: str | None = None   # header or query parameter name for an API key
    key_in: str = "header"        # header | query

    def describe(self) -> str:
        if self.kind == "apikey":
            return f"apikey ({self.key_in}: {self.key_name})"
        return self.kind


NO_AUTH = Auth()


def is_url(location: str) -> bool:
    return urllib.parse.urlparse(location).scheme in ("http", "https")


def _build_request(url: str, auth: Auth) -> urllib.request.Request:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, */*"}
    if auth.kind == "basic":
        if auth.username is None or auth.password is None:
            raise ResourceError("Basic authentication needs both a username and a password.")
        pair = f"{auth.username}:{auth.password}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(pair).decode("ascii")
    elif auth.kind == "bearer":
        if not auth.token:
            raise ResourceError("Bearer authentication needs a token.")
        headers["Authorization"] = f"Bearer {auth.token}"
    elif auth.kind == "apikey":
        if not auth.token or not auth.key_name:
            raise ResourceError("API key authentication needs a key and the header/parameter name to send it in.")
        if auth.key_in == "query":
            parts = urllib.parse.urlparse(url)
            query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
            query.append((auth.key_name, auth.token))
            url = urllib.parse.urlunparse(parts._replace(query=urllib.parse.urlencode(query)))
        else:
            headers[auth.key_name] = auth.token
    elif auth.kind != "none":
        raise ResourceError(f"Unknown authentication type: {auth.kind}")
    return urllib.request.Request(url, headers=headers)


def read_bytes(location: str, auth: Auth = NO_AUTH) -> bytes:
    """Return the raw bytes of a local file or a URL."""
    if is_url(location):
        request = _build_request(location, auth)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise ResourceError(
                    f"Access denied ({exc.code}) for {location}. "
                    "The resource may need authentication, or the credentials were rejected."
                ) from exc
            if exc.code == 404:
                raise ResourceError(f"Not found (404): {location}") from exc
            raise ResourceError(f"HTTP {exc.code} while reading {location}") from exc
        except urllib.error.URLError as exc:
            raise ResourceError(f"Could not reach {location}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ResourceError(f"Timed out after {TIMEOUT_SECONDS}s: {location}") from exc

    path = Path(location).expanduser()
    if location.startswith("file://"):
        path = Path(urllib.request.url2pathname(urllib.parse.urlparse(location).path))
    if not path.exists():
        raise ResourceError(f"File not found: {path}")
    if path.is_dir():
        raise ResourceError(f"Expected a file but got a folder: {path}")
    return path.read_bytes()


def resolve(base: str, relative: str) -> str:
    """Resolve a link found inside a resource against the resource's own location."""
    if is_url(relative) or Path(relative).is_absolute():
        return relative
    if is_url(base):
        return urllib.parse.urljoin(base, relative)
    return str(Path(base).expanduser().parent / relative)
