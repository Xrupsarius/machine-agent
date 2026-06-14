import logging

from app.core.event_bus import EventBus
from app.core.state_manager import StateManager, AppState
from app.tools.base_tool import ToolResult
from app.tools.tool_registry import ToolRegistry

log = logging.getLogger(__name__)

EVENT_TOOL_EXECUTED = "tool.executed"
EVENT_TOOL_ERROR = "tool.error"
EVENT_EXECUTION_COMPLETED = "execution.completed"

_MAX_RETRIES = 3


class ToolExecutor:
    """
    Executes plan steps through the ToolRegistry.
    ADR-008: the only allowed chain is Plan → Validator → Executor.
    ADR-009: actions execute only through registered Tools.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        event_bus: EventBus,
        state_manager: StateManager,
    ) -> None:
        self._registry = registry
        self._event_bus = event_bus
        self._state_manager = state_manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_plan(self, plan: dict) -> list[ToolResult]:
        """
        Execute all steps of a validated plan sequentially.
        Stops on the first failed step (ADR-017: Simplicity > Complexity).
        """
        intent = plan.get("intent", "?")
        steps = plan.get("steps", [])

        if not steps:
            log.info(f"Plan '{intent}' has no steps — nothing to execute")
            self._state_manager.set_state(AppState.IDLE)
            self._event_bus.publish(
                EVENT_EXECUTION_COMPLETED,
                {"intent": intent, "results": [], "success": True},
            )
            return []

        self._state_manager.set_state(AppState.EXECUTING)
        results: list[ToolResult] = []

        for step in steps:
            result = self.execute_step(step)
            results.append(result)
            if not result.success:
                self._state_manager.set_state(AppState.ERROR)
                self._event_bus.publish(
                    EVENT_EXECUTION_COMPLETED,
                    {
                        "intent": intent,
                        "results": [r.to_dict() for r in results],
                        "success": False,
                    },
                )
                return results

        self._state_manager.set_state(AppState.IDLE)
        self._event_bus.publish(
            EVENT_EXECUTION_COMPLETED,
            {
                "intent": intent,
                "results": [r.to_dict() for r in results],
                "success": True,
            },
        )
        return results

    def execute_step(self, step: dict) -> ToolResult:
        """Execute a single plan step with up to _MAX_RETRIES attempts. Never raises."""
        tool_name = step.get("tool", "")
        action = step.get("action", "")
        parameters = step.get("parameters", {})

        if not self._registry.has(tool_name):
            error = f"Tool '{tool_name}' is not registered"
            log.error(error)
            self._event_bus.publish(
                EVENT_TOOL_ERROR, {"tool": tool_name, "action": action, "error": error}
            )
            return ToolResult(success=False, error=error, tool_name=tool_name, action=action)

        tool = self._registry.get(tool_name)

        result = ToolResult(success=False, error="", tool_name=tool_name, action=action)
        for attempt in range(1, _MAX_RETRIES + 1):
            result = tool.execute(action, parameters)
            if result.success:
                break
            if attempt < _MAX_RETRIES:
                log.warning(
                    f"[{tool_name}:{action}] attempt {attempt}/{_MAX_RETRIES} failed"
                    f" — {result.error!r}. Retrying..."
                )
            else:
                log.error(
                    f"[{tool_name}:{action}] all {_MAX_RETRIES} attempts failed: {result.error!r}"
                )

        self._event_bus.publish(
            EVENT_TOOL_EXECUTED,
            {
                "tool": tool_name,
                "action": action,
                "success": result.success,
                "output": result.output,
            },
        )
        if not result.success:
            self._event_bus.publish(
                EVENT_TOOL_ERROR,
                {"tool": tool_name, "action": action, "error": result.error},
            )

        return result
