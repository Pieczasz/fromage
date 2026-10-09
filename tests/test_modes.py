import pytest

from fromage.modes import get_mode, load_modes


def test_default_modes():
    modes = load_modes(config_path=__import__("pathlib").Path("/nonexistent/modes.json"))
    assert "general" in modes
    assert get_mode("code", modes)["categories"] == "general"


def test_unknown_mode():
    with pytest.raises(ValueError, match="unknown mode"):
        get_mode("nope", {"general": {"categories": "general"}})
