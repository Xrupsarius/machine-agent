from app.mcp.base_mcp_adapter import BaseMCPAdapter
from app.tools.filesystem_tool import FilesystemTool


class FilesystemMCPAdapter(BaseMCPAdapter):
    """Exposes FilesystemTool actions as MCP tools."""

    def __init__(self) -> None:
        super().__init__(FilesystemTool())

    def _register_tools(self) -> None:
        @self._mcp.tool(description="Create a new file with optional text content.")
        def create_file(path: str, content: str = "") -> str:
            return self._call("create_file", path=path, content=content)

        @self._mcp.tool(description="Read the contents of a file.")
        def read_file(path: str) -> str:
            return self._call("read_file", path=path)

        @self._mcp.tool(description="Write (overwrite) a file with new content.")
        def write_file(path: str, content: str) -> str:
            return self._call("write_file", path=path, content=content)

        @self._mcp.tool(description="Append text to an existing or new file.")
        def append_file(path: str, content: str) -> str:
            return self._call("append_file", path=path, content=content)

        @self._mcp.tool(description="Delete a file. Requires security confirmation.")
        def delete_file(path: str) -> str:
            return self._call("delete_file", path=path)

        @self._mcp.tool(description="List files and directories in a path.")
        def list_dir(path: str = ".") -> str:
            return self._call("list_dir", path=path)

        @self._mcp.tool(description="Recursively search for files matching a glob pattern.")
        def search_files(path: str = ".", pattern: str = "*") -> str:
            return self._call("search_files", path=path, pattern=pattern)


if __name__ == "__main__":
    FilesystemMCPAdapter().run()
