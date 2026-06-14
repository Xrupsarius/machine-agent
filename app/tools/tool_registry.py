import logging
from app.tools.base_tool import BaseTool

log = logging.getLogger(__name__)


class ToolNotFoundError(Exception):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            log.warning(f"Tool '{tool.name}' overwritten in registry")
        self._tools[tool.name] = tool
        log.debug(f"Tool '{tool.name}' registered ({type(tool).__name__})")

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool '{name}' not registered")
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def all_names(self) -> list[str]:
        return list(self._tools.keys())
