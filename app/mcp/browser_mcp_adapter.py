from app.mcp.base_mcp_adapter import BaseMCPAdapter
from app.tools.browser_tool import BrowserTool


class BrowserMCPAdapter(BaseMCPAdapter):
    """Exposes BrowserTool actions as MCP tools."""

    def __init__(self, headless: bool = False, executable_path: str = "") -> None:
        super().__init__(BrowserTool(headless=headless, executable_path=executable_path))

    def _register_tools(self) -> None:
        @self._mcp.tool(description="Open a URL in the browser.")
        def open_url(url: str) -> str:
            return self._call("open_url", url=url)

        @self._mcp.tool(description="Open a new browser tab, optionally loading a URL.")
        def new_tab(url: str = "") -> str:
            return self._call("new_tab", url=url)

        @self._mcp.tool(description="Switch to a tab by title substring or index.")
        def switch_tab(title: str = "", index: int = 0) -> str:
            return self._call("switch_tab", title=title, index=index)

        @self._mcp.tool(description="Click an element matching a CSS selector.")
        def click(selector: str) -> str:
            return self._call("click", selector=selector)

        @self._mcp.tool(description="Fill a form field with a value.")
        def fill_form(selector: str, value: str) -> str:
            return self._call("fill_form", selector=selector, value=value)

        @self._mcp.tool(description="Get the title of the current page.")
        def get_title() -> str:
            return self._call("get_title")

        @self._mcp.tool(description="Get visible text content of a CSS selector (default: body).")
        def get_text(selector: str = "body") -> str:
            return self._call("get_text", selector=selector)

        @self._mcp.tool(description="Navigate back in browser history.")
        def go_back() -> str:
            return self._call("go_back")

        @self._mcp.tool(description="Close the current browser tab.")
        def close_tab() -> str:
            return self._call("close_tab")

        @self._mcp.tool(description="Close the browser entirely.")
        def close_browser() -> str:
            return self._call("close_browser")


if __name__ == "__main__":
    BrowserMCPAdapter().run()
