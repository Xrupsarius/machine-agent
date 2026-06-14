"""
Tests for MCP adapters (Stage 15).
Verifies that each adapter:
  1. Instantiates correctly.
  2. Exposes the right MCP tool names.
  3. Delegates to the underlying BaseTool correctly.
  4. Returns text output on success and an "Error:" prefix on failure.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.mcp.base_mcp_adapter import BaseMCPAdapter
from app.mcp.filesystem_mcp_adapter import FilesystemMCPAdapter
from app.mcp.terminal_mcp_adapter import TerminalMCPAdapter
from app.mcp.desktop_mcp_adapter import DesktopMCPAdapter
from app.mcp.browser_mcp_adapter import BrowserMCPAdapter
from app.tools.base_tool import ToolResult


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _tool_names(adapter: BaseMCPAdapter) -> set[str]:
    """Return the set of MCP tool names registered on the adapter."""
    return {t.name for t in adapter.mcp._tool_manager.list_tools()}


def _make_ok(output: str = "ok") -> ToolResult:
    return ToolResult(success=True, output=output, tool_name="t", action="a")


def _make_err(error: str = "oops") -> ToolResult:
    return ToolResult(success=False, error=error, tool_name="t", action="a")


# ------------------------------------------------------------------
# BaseMCPAdapter interface
# ------------------------------------------------------------------

def test_base_adapter_has_mcp_property():
    from mcp.server.fastmcp import FastMCP
    adapter = FilesystemMCPAdapter()
    assert isinstance(adapter.mcp, FastMCP)


def test_base_adapter_has_tool_property():
    from app.tools.filesystem_tool import FilesystemTool
    adapter = FilesystemMCPAdapter()
    assert isinstance(adapter.tool, FilesystemTool)


def test_base_adapter_call_returns_output_on_success():
    adapter = FilesystemMCPAdapter()
    adapter._tool = MagicMock()
    adapter._tool.execute.return_value = _make_ok("Created: /tmp/x.txt")
    result = adapter._call("create_file", path="/tmp/x.txt")
    assert result == "Created: /tmp/x.txt"


def test_base_adapter_call_returns_error_prefix_on_failure():
    adapter = FilesystemMCPAdapter()
    adapter._tool = MagicMock()
    adapter._tool.execute.return_value = _make_err("File not found")
    result = adapter._call("read_file", path="/tmp/missing.txt")
    assert result.startswith("Error:")
    assert "File not found" in result


def test_base_adapter_call_ok_no_output_returns_ok():
    adapter = FilesystemMCPAdapter()
    adapter._tool = MagicMock()
    adapter._tool.execute.return_value = ToolResult(success=True, output="")
    result = adapter._call("some_action")
    assert result == "(ok)"


# ------------------------------------------------------------------
# FilesystemMCPAdapter
# ------------------------------------------------------------------

def test_filesystem_adapter_instantiates():
    assert FilesystemMCPAdapter() is not None


def test_filesystem_adapter_tool_names():
    names = _tool_names(FilesystemMCPAdapter())
    assert "create_file" in names
    assert "read_file" in names
    assert "write_file" in names
    assert "append_file" in names
    assert "delete_file" in names
    assert "list_dir" in names
    assert "search_files" in names


def test_filesystem_adapter_create_file_delegates(tmp_path):
    adapter = FilesystemMCPAdapter()
    path = str(tmp_path / "hello.txt")
    mock_tool = MagicMock()
    mock_tool.execute.return_value = _make_ok(f"Created: {path}")
    adapter._tool = mock_tool

    result = adapter._call("create_file", path=path, content="hi")
    mock_tool.execute.assert_called_once_with("create_file", {"path": path, "content": "hi"})
    assert "Created" in result


def test_filesystem_adapter_read_file_delegates(tmp_path):
    adapter = FilesystemMCPAdapter()
    mock_tool = MagicMock()
    mock_tool.execute.return_value = _make_ok("file contents")
    adapter._tool = mock_tool

    result = adapter._call("read_file", path="/tmp/x.txt")
    mock_tool.execute.assert_called_once_with("read_file", {"path": "/tmp/x.txt"})
    assert result == "file contents"


def test_filesystem_adapter_real_create_read(tmp_path):
    """Integration: real FilesystemTool through the adapter."""
    adapter = FilesystemMCPAdapter()
    path = str(tmp_path / "test.txt")

    out = adapter._call("create_file", path=path, content="hello")
    assert "Created" in out or "Error" not in out

    out2 = adapter._call("read_file", path=path)
    assert out2 == "hello"


# ------------------------------------------------------------------
# TerminalMCPAdapter
# ------------------------------------------------------------------

def test_terminal_adapter_instantiates():
    assert TerminalMCPAdapter() is not None


def test_terminal_adapter_tool_names():
    names = _tool_names(TerminalMCPAdapter())
    assert "execute" in names
    assert "execute_background" in names
    assert "execute_interactive" in names
    assert "open_terminal" in names


def test_terminal_adapter_execute_delegates():
    adapter = TerminalMCPAdapter()
    mock_tool = MagicMock()
    mock_tool.execute.return_value = _make_ok("hello")
    adapter._tool = mock_tool

    result = adapter._call("execute", command="echo hello")
    mock_tool.execute.assert_called_once_with("execute", {"command": "echo hello"})
    assert result == "hello"


def test_terminal_adapter_real_echo():
    adapter = TerminalMCPAdapter()
    result = adapter._call("execute", command="echo mcp_test")
    assert "mcp_test" in result


def test_terminal_adapter_timeout():
    adapter = TerminalMCPAdapter(timeout=1)
    result = adapter._call("execute", command="sleep 5")
    assert "Error" in result


# ------------------------------------------------------------------
# DesktopMCPAdapter
# ------------------------------------------------------------------

def test_desktop_adapter_instantiates():
    assert DesktopMCPAdapter() is not None


def test_desktop_adapter_tool_names():
    names = _tool_names(DesktopMCPAdapter())
    assert "open_app" in names
    assert "close_app" in names
    assert "list_windows" in names
    assert "switch_window" in names
    assert "open_terminal" in names


def test_desktop_adapter_open_app_delegates():
    adapter = DesktopMCPAdapter()
    mock_tool = MagicMock()
    mock_tool.execute.return_value = _make_ok("Launched: firefox")
    adapter._tool = mock_tool

    result = adapter._call("open_app", name="firefox", args=[])
    mock_tool.execute.assert_called_once_with("open_app", {"name": "firefox", "args": []})
    assert "Launched" in result


def test_desktop_adapter_list_windows_delegates():
    adapter = DesktopMCPAdapter()
    mock_tool = MagicMock()
    mock_tool.execute.return_value = _make_ok("0x001  Firefox\n0x002  Terminal")
    adapter._tool = mock_tool

    result = adapter._call("list_windows")
    mock_tool.execute.assert_called_once_with("list_windows", {})
    assert "Firefox" in result


# ------------------------------------------------------------------
# BrowserMCPAdapter (stub)
# ------------------------------------------------------------------

def test_browser_adapter_instantiates():
    assert BrowserMCPAdapter() is not None


def test_browser_adapter_tool_names():
    names = _tool_names(BrowserMCPAdapter())
    assert "open_url" in names
    assert "switch_tab" in names
    assert "fill_form" in names
    assert "click" in names
    assert "get_title" in names


def test_browser_adapter_delegates_to_browser_tool():
    from unittest.mock import MagicMock, patch
    from app.tools.base_tool import ToolResult
    adapter = BrowserMCPAdapter(headless=True)
    mock_result = ToolResult(success=True, output="Opened: https://example.com  (title: 'Test')")
    with patch.object(adapter.tool, "execute", return_value=mock_result):
        result = adapter._call("open_url", url="https://example.com")
    assert "Opened" in result


# ------------------------------------------------------------------
# Cross-adapter: all expose mcp property and tool property
# ------------------------------------------------------------------

@pytest.mark.parametrize("AdapterClass", [
    FilesystemMCPAdapter,
    TerminalMCPAdapter,
    DesktopMCPAdapter,
    BrowserMCPAdapter,
])
def test_all_adapters_have_mcp_and_tool(AdapterClass):
    from mcp.server.fastmcp import FastMCP
    from app.tools.base_tool import BaseTool
    adapter = AdapterClass()
    assert isinstance(adapter.mcp, FastMCP)
    assert isinstance(adapter.tool, BaseTool)


@pytest.mark.parametrize("AdapterClass", [
    FilesystemMCPAdapter,
    TerminalMCPAdapter,
    DesktopMCPAdapter,
    BrowserMCPAdapter,
])
def test_all_adapters_register_at_least_one_tool(AdapterClass):
    adapter = AdapterClass()
    assert len(_tool_names(adapter)) >= 1
