"""Common shape of every importer.

An importer turns one data format into rows of the isnady database. Every row
it writes is tied to a source record, so the application can always say where
a piece of information came from.

Sources have an origin: "builtin" for data shipped with isnady, "user" for
anything the user adds themselves (User Resources).
"""

import re
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable

from isnady.data.fetch import NO_AUTH, Auth

ProgressCallback = Callable[[str], None]


@dataclass
class SourceInfo:
    location: str
    name: str | None = None
    license: str | None = None
    origin: str = "user"          # builtin | user
    auth: Auth = field(default_factory=lambda: NO_AUTH)


@dataclass
class ImportReport:
    source_key: str
    editions: list[str] = field(default_factory=list)
    hadiths: int = 0
    grades: int = 0
    warnings: list[str] = field(default_factory=list)


class Importer(ABC):
    format_id: str = ""
    title: str = ""
    description: str = ""

    @abstractmethod
    def run(
        self,
        conn: sqlite3.Connection,
        source: SourceInfo,
        options: dict,
        progress: ProgressCallback | None = None,
    ) -> ImportReport:
        """Import the resource and return what was written."""


_REGISTRY: dict[str, Importer] = {}


def register(importer: Importer) -> Importer:
    _REGISTRY[importer.format_id] = importer
    return importer


def get_importer(format_id: str) -> Importer:
    try:
        return _REGISTRY[format_id]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "none"
        raise KeyError(f"Unknown format '{format_id}'. Known formats: {known}") from None


def list_importers() -> list[Importer]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:80] or "source"
