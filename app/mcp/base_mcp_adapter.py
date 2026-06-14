import logging
from abc import ABC, abstractmethod

from mcp.server.fastmcp import FastMCP

from app.tools.base_tool import BaseTool, ToolResult

log = logging.getLogger(__name__)


class BaseMCPAdapter(ABC):
    """
    Wraps a BaseTool and exposes its actions as an MCP server via FastMCP.
    ADR-010: MCP is an additional integration layer — system works without it.

    Usage:
        adapter = FilesystemMCPAdapter()
        adapter.run()          # start stdio MCP server
        adapter.mcp            # FastMCP instance (for testing / embedding)
    """

    def __init__(self, tool: BaseTool) -> None:
        self._tool = tool
        self._mcp = FastMCP(name=tool.name)
        self._register_tools()
        log.debug(f"MCPAdapter ready: {tool.name}")

    # ------------------------------------------------------------------

    @abstractmethod
    def _register_tools(self) -> None:
        """Register tool actions as @mcp.tool() handlers."""

    # ------------------------------------------------------------------

    @property
    def mcp(self) -> FastMCP:
        return self._mcp

    @property
    def tool(self) -> BaseTool:
        return self._tool

    def run(self) -> None:
        """Start as a stdio MCP server (blocking)."""
        self._mcp.run()

    # ------------------------------------------------------------------

    def _call(self, action: str, **params) -> str:
        """Execute an action on the underlying tool and return text output."""
        result: ToolResult = self._tool.execute(action, params)
        if result.success:
            return result.output or "(ok)"
        return f"Error: {result.error}"
