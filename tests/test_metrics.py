from fromage.metrics import hit_at_k, mrr, recall_at_k


def test_hit_at_k():
    ranked = ["a", "b", "c"]
    assert hit_at_k(ranked, {"b"}, 2) is True
    assert hit_at_k(ranked, {"c"}, 2) is False


def test_recall_at_k():
    ranked = ["a", "b", "c"]
    assert recall_at_k(ranked, {"a", "c"}, 2) == 0.5


def test_mrr_first_rank():
    assert mrr(["x", "y"], {"x"}) == 1.0
    assert mrr(["x", "y"], {"y"}) == 0.5
    assert mrr(["x"], {"z"}) == 0.0
