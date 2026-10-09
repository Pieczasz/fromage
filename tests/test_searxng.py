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


def test_one_failed_query_does_not_fail_search():
    import httpx

    def handler(req):
        if "documentation" in req.url.params["q"]:
            return httpx.Response(500)
        return httpx.Response(200, json={"results": [{"title": "t", "url": "https://docs.python.org/3/", "content": "asyncio"}]})

    s = SearXNGSearch("http://searx", client=httpx.Client(transport=httpx.MockTransport(handler)), semantic=False)
    hits = s.search("python asyncio", mode="code")
    assert [h.url for h in hits] == ["https://docs.python.org/3/"]


def test_all_failed_queries_raise():
    import httpx

    s = SearXNGSearch(
        "http://searx", client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))), semantic=False
    )
    with pytest.raises(httpx.HTTPStatusError):
        s.search("python asyncio", mode="code")


def test_empty_results_name_the_failing_engines():
    import httpx

    body = {"results": [], "unresponsive_engines": [["google", "access denied"]]}
    s = SearXNGSearch(
        "http://searx", client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))), semantic=False
    )
    with pytest.raises(RuntimeError, match=r"google \(access denied\)"):
        s.search("anything")
