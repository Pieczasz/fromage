import json
from pathlib import Path

import pytest

from fromage.searxng import SearXNGSearch

FIXTURE = Path(__file__).parent / "fixtures" / "searx_results.json"


def test_parse_fixture():
    data = json.loads(FIXTURE.read_text())
    hits = SearXNGSearch.parse_results(data, limit=10)
    assert len(hits) == 2
    assert hits[0].url.startswith("https://www.python.org")


def test_unknown_mode_raises():
    s = SearXNGSearch("http://127.0.0.1:8888")
    with pytest.raises(ValueError, match="unknown mode"):
        s.search("test", mode="not-a-mode")
