from app.mcp.base_mcp_adapter import BaseMCPAdapter
from app.tools.desktop_tool import DesktopTool


class DesktopMCPAdapter(BaseMCPAdapter):
    """Exposes DesktopTool actions as MCP tools."""

    def __init__(self) -> None:
        super().__init__(DesktopTool())

    def _register_tools(self) -> None:
        @self._mcp.tool(description="Launch an application by name.")
        def open_app(name: str, args: list[str] | None = None) -> str:
            return self._call("open_app", name=name, args=args or [])

        @self._mcp.tool(description="Close (kill) a running application by name.")
        def close_app(name: str) -> str:
            return self._call("close_app", name=name)

        @self._mcp.tool(description="List open windows (requires wmctrl or xdotool).")
        def list_windows() -> str:
            return self._call("list_windows")

        @self._mcp.tool(
            description="Switch focus to a window whose title contains the given name."
        )
        def switch_window(name: str) -> str:
            return self._call("switch_window", name=name)

        @self._mcp.tool(description="Open a new terminal emulator window.")
        def open_terminal() -> str:
            return self._call("open_terminal")


if __name__ == "__main__":
    DesktopMCPAdapter().run()
