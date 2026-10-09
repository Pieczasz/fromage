from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TypedDict


class ModeConfig(TypedDict, total=False):
    categories: str
    engines: str
    time_range: str


DEFAULT_MODES: dict[str, ModeConfig] = {
    "general": {"categories": "general", "engines": "yep,duckduckgo,brave,wikipedia,mojeek"},
    "academic": {
        "categories": "science",
        "engines": "arxiv,yep,wikipedia,crossref,pubmed,google scholar",
    },
    "code": {
        "categories": "general",
        "engines": "yep,duckduckgo,brave,github,stackoverflow",
    },
    "news": {
        "categories": "news",
        "engines": "yep,duckduckgo,brave,bing news,reuters,google news",
    },
}


def load_modes(config_path: Path | None = None) -> dict[str, ModeConfig]:
    modes = {k: dict(v) for k, v in DEFAULT_MODES.items()}
    if config_path is None:
        env_path = os.environ.get("OPEN_SEARCH_MODES_PATH")
        config_path = Path(env_path) if env_path else Path("modes.json")
    path = config_path
    if path.is_file():
        overlay = json.loads(path.read_text(encoding="utf-8"))
        for name, cfg in overlay.items():
            if not isinstance(cfg, dict):
                raise ValueError(f"modes.json entry {name!r} must be an object")
            modes[name] = cfg  # type: ignore[assignment]
    return modes


def get_mode(mode: str, modes: dict[str, ModeConfig] | None = None) -> ModeConfig:
    table = modes if modes is not None else load_modes()
    if mode not in table:
        known = ", ".join(sorted(table))
        raise ValueError(f"unknown mode {mode!r}; known: {known}")
    return table[mode]
