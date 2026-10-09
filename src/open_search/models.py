from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Hit:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class Page:
    url: str
    text: str


@dataclass(frozen=True)
class Chunk:
    id: str
    url: str
    text: str
    embed_model: str | None = None
