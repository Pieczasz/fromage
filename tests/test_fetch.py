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
