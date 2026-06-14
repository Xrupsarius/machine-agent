import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class ToolResult:
    success: bool
    output: str = ""
    error: str = ""
    tool_name: str = ""
    action: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "tool_name": self.tool_name,
            "action": self.action,
        }


class BaseTool(ABC):
    """
    Abstract base for all tools. ADR-009: every action goes through a Tool.
    Every execute() call must be logged — ADR-007.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def _run(self, action: str, parameters: dict) -> ToolResult:
        """Override in subclasses. Do NOT call directly — use execute()."""

    def execute(self, action: str, parameters: dict | None = None) -> ToolResult:
        params = parameters or {}
        log.info(f"[{self.name}] execute: action='{action}' params={params}")
        try:
            result = self._run(action, params)
        except Exception as e:
            log.error(f"[{self.name}] unhandled exception in '{action}': {e}")
            result = ToolResult(success=False, error=str(e))

        result.tool_name = self.name
        result.action = action

        if result.success:
            log.info(f"[{self.name}] '{action}' OK — {result.output[:120]}")
        else:
            log.warning(f"[{self.name}] '{action}' FAILED — {result.error}")
        return result
