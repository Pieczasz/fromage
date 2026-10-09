from fromage.bench import WebCase, filter_split


def test_filter_split():
    cases = [
        WebCase("q1", "code", [], [], id="a", split="train"),
        WebCase("q2", "code", [], [], id="b", split="test"),
        WebCase("q3", "code", [], [], id="c", split="train"),
    ]
    assert len(filter_split(cases, "train")) == 2
    assert len(filter_split(cases, "test")) == 1
    assert len(filter_split(cases, "all")) == 3
