from pathlib import Path

import pytest

from open_search.fetch import HttpFetcher, _validate_url

FIXTURE = Path(__file__).parent / "fixtures" / "sample.html"


def test_extract_html_fixture():
    html = FIXTURE.read_text()
    text = HttpFetcher.extract_html(html)
    assert "Hello from the extraction fixture" in text


def test_blocked_schemes():
    with pytest.raises(ValueError, match="scheme"):
        _validate_url("file:///etc/passwd")


def test_blocked_metadata_ip():
    with pytest.raises(ValueError, match="blocked"):
        _validate_url("http://169.254.169.254/latest/meta-data/")


@pytest.mark.parametrize(
    "url", ["http://localhost:8765/mcp", "http://127.1/", "http://2130706433/", "http://[::ffff:127.0.0.1]/"]
)
def test_blocked_loopback_forms(url):
    with pytest.raises(ValueError, match="blocked"):
        _validate_url(url)


def _public_dns(monkeypatch):
    import socket

    real = socket.getaddrinfo

    def fake(host, *a, **kw):
        if host == "public.test":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
        return real(host, *a, **kw)

    monkeypatch.setattr(socket, "getaddrinfo", fake)


def test_redirect_to_private_is_blocked(monkeypatch, tmp_path):
    import httpx

    _public_dns(monkeypatch)
    hit_private = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "public.test":
            return httpx.Response(302, headers={"location": "http://127.0.0.1:8765/mcp"})
        hit_private.append(req.url)
        return httpx.Response(200, text="secret")

    f = HttpFetcher(str(tmp_path / "c.db"), client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ValueError, match="blocked"):
        f.fetch("http://public.test/")
    assert not hit_private


def test_response_size_cap(monkeypatch, tmp_path):
    import httpx

    from open_search import fetch as fetch_mod

    _public_dns(monkeypatch)
    monkeypatch.setattr(fetch_mod, "_MAX_BYTES", 10)
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text="x" * 100)))
    f = HttpFetcher(str(tmp_path / "c.db"), client=client)
    with pytest.raises(ValueError, match="larger than"):
        f.fetch("http://public.test/")
