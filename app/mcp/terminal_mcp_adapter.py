from app.mcp.base_mcp_adapter import BaseMCPAdapter
from app.tools.terminal_tool import TerminalTool


class TerminalMCPAdapter(BaseMCPAdapter):
    """Exposes TerminalTool actions as MCP tools."""

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout
        super().__init__(TerminalTool(timeout=timeout))

    def _register_tools(self) -> None:
        @self._mcp.tool(description="Execute a shell command and return stdout/stderr.")
        def execute(command: str) -> str:
            return self._call("execute", command=command)

        @self._mcp.tool(description="Start a command in the background; returns PID.")
        def execute_background(command: str) -> str:
            return self._call("execute_background", command=command)

        @self._mcp.tool(
            description="Open an interactive terminal emulator, optionally running a command."
        )
        def execute_interactive(command: str = "") -> str:
            return self._call("execute_interactive", command=command)

        @self._mcp.tool(description="Open a new terminal window.")
        def open_terminal() -> str:
            return self._call("open")


if __name__ == "__main__":
    TerminalMCPAdapter().run()
