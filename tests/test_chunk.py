from open_search.embed_ollama import chunk_text, make_chunk_id


def test_chunk_overlap():
    text = "a" * 2500
    parts = chunk_text(text, size=1000, overlap=100)
    assert len(parts) >= 2


def test_make_chunk_id():
    assert make_chunk_id("https://x", 2) == "https://x#2"
