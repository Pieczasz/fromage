import pytest
from mcp.server.mcpserver.exceptions import ToolError


def test_tool_errors_reach_the_agent(monkeypatch, tmp_path):
    monkeypatch.setenv("FROMAGE_SQLITE_PATH", str(tmp_path / "mem.db"))
    monkeypatch.setenv("FROMAGE_PAGE_CACHE", str(tmp_path / "pages.db"))
    from fromage import mcp_server

    monkeypatch.setattr(mcp_server, "_pipeline", None)
    with pytest.raises(ToolError, match="unknown mode 'bogus'; known: academic, code, general, news"):
        mcp_server.search("x", mode="bogus")
    with pytest.raises(ToolError, match="unsupported URL scheme"):
        mcp_server.read("file:///etc/passwd")
