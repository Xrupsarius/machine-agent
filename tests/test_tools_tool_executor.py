import pytest
from unittest.mock import MagicMock
from app.core.event_bus import EventBus
from app.core.state_manager import StateManager, AppState
from app.tools.base_tool import BaseTool, ToolResult
from app.tools.tool_registry import ToolRegistry
from app.tools.tool_executor import (
    ToolExecutor,
    EVENT_TOOL_EXECUTED,
    EVENT_TOOL_ERROR,
    EVENT_EXECUTION_COMPLETED,
    _MAX_RETRIES,
)


class OkTool(BaseTool):
    @property
    def name(self) -> str:
        return "ok_tool"

    @property
    def description(self) -> str:
        return "Always succeeds"

    def _run(self, action: str, parameters: dict) -> ToolResult:
        return ToolResult(success=True, output=f"done:{action}")


class FailTool(BaseTool):
    @property
    def name(self) -> str:
        return "fail_tool"

    @property
    def description(self) -> str:
        return "Always fails"

    def _run(self, action: str, parameters: dict) -> ToolResult:
        return ToolResult(success=False, error="intentional failure")


class FlakyTool(BaseTool):
    """Fails the first *fail_count* calls, then succeeds."""

    def __init__(self, fail_count: int) -> None:
        self._fail_count = fail_count
        self.calls = 0

    @property
    def name(self) -> str:
        return "flaky_tool"

    @property
    def description(self) -> str:
        return "Fails N times then succeeds"

    def _run(self, action: str, parameters: dict) -> ToolResult:
        self.calls += 1
        if self.calls <= self._fail_count:
            return ToolResult(success=False, error=f"transient failure #{self.calls}")
        return ToolResult(success=True, output="recovered")


def _make_executor(tools=None):
    bus = EventBus()
    sm = StateManager(bus)
    reg = ToolRegistry()
    for t in (tools or []):
        reg.register(t)
    exe = ToolExecutor(reg, bus, sm)
    return exe, bus, sm, reg


# --- execute_step ---

def test_execute_step_success():
    exe, _, _, _ = _make_executor([OkTool()])
    result = exe.execute_step({"tool": "ok_tool", "action": "run"})
    assert result.success
    assert "run" in result.output


def test_execute_step_unknown_tool_returns_failure():
    exe, _, _, _ = _make_executor()
    result = exe.execute_step({"tool": "ghost", "action": "x"})
    assert not result.success
    assert "ghost" in result.error


def test_execute_step_tool_failure_propagates():
    exe, _, _, _ = _make_executor([FailTool()])
    result = exe.execute_step({"tool": "fail_tool", "action": "x"})
    assert not result.success
    assert result.error == "intentional failure"


def test_execute_step_publishes_tool_executed_on_success():
    exe, bus, _, _ = _make_executor([OkTool()])
    events = []
    bus.subscribe(EVENT_TOOL_EXECUTED, lambda d: events.append(d))
    exe.execute_step({"tool": "ok_tool", "action": "go"})
    assert len(events) == 1
    assert events[0]["success"] is True
    assert events[0]["tool"] == "ok_tool"


def test_execute_step_publishes_tool_error_on_failure():
    exe, bus, _, _ = _make_executor([FailTool()])
    errors = []
    bus.subscribe(EVENT_TOOL_ERROR, lambda d: errors.append(d))
    exe.execute_step({"tool": "fail_tool", "action": "x"})
    assert len(errors) == 1


def test_execute_step_publishes_tool_error_for_unknown_tool():
    exe, bus, _, _ = _make_executor()
    errors = []
    bus.subscribe(EVENT_TOOL_ERROR, lambda d: errors.append(d))
    exe.execute_step({"tool": "missing", "action": "x"})
    assert len(errors) == 1


def test_execute_step_sets_tool_name_in_result():
    exe, _, _, _ = _make_executor([OkTool()])
    result = exe.execute_step({"tool": "ok_tool", "action": "ping"})
    assert result.tool_name == "ok_tool"


def test_execute_step_sets_action_in_result():
    exe, _, _, _ = _make_executor([OkTool()])
    result = exe.execute_step({"tool": "ok_tool", "action": "my_action"})
    assert result.action == "my_action"


# --- execute_plan ---

def test_execute_plan_empty_steps():
    exe, bus, sm, _ = _make_executor()
    events = []
    bus.subscribe(EVENT_EXECUTION_COMPLETED, lambda d: events.append(d))
    results = exe.execute_plan({"intent": "x", "steps": []})
    assert results == []
    assert events[0]["success"] is True
    assert sm.state == AppState.IDLE


def test_execute_plan_single_step_success():
    exe, _, sm, _ = _make_executor([OkTool()])
    plan = {"intent": "test", "steps": [{"tool": "ok_tool", "action": "run"}]}
    results = exe.execute_plan(plan)
    assert len(results) == 1
    assert results[0].success
    assert sm.state == AppState.IDLE


def test_execute_plan_multi_step_success():
    exe, _, _, _ = _make_executor([OkTool()])
    plan = {
        "intent": "multi",
        "steps": [
            {"tool": "ok_tool", "action": "step1"},
            {"tool": "ok_tool", "action": "step2"},
        ],
    }
    results = exe.execute_plan(plan)
    assert len(results) == 2
    assert all(r.success for r in results)


def test_execute_plan_stops_on_first_failure():
    exe, _, sm, _ = _make_executor([OkTool(), FailTool()])
    plan = {
        "intent": "mixed",
        "steps": [
            {"tool": "fail_tool", "action": "x"},
            {"tool": "ok_tool", "action": "never_reached"},
        ],
    }
    results = exe.execute_plan(plan)
    assert len(results) == 1
    assert not results[0].success
    assert sm.state == AppState.ERROR


def test_execute_plan_sets_executing_state():
    exe, bus, sm, _ = _make_executor([OkTool()])
    states = []
    bus.subscribe("state.changed", lambda d: states.append(d["new"]))
    exe.execute_plan({"intent": "x", "steps": [{"tool": "ok_tool", "action": "go"}]})
    assert AppState.EXECUTING in states


def test_execute_plan_publishes_completed_event():
    exe, bus, _, _ = _make_executor([OkTool()])
    events = []
    bus.subscribe(EVENT_EXECUTION_COMPLETED, lambda d: events.append(d))
    exe.execute_plan({"intent": "done", "steps": [{"tool": "ok_tool", "action": "x"}]})
    assert len(events) == 1
    assert events[0]["success"] is True
    assert events[0]["intent"] == "done"


def test_execute_plan_completed_event_has_results():
    exe, bus, _, _ = _make_executor([OkTool()])
    events = []
    bus.subscribe(EVENT_EXECUTION_COMPLETED, lambda d: events.append(d))
    exe.execute_plan({"intent": "x", "steps": [{"tool": "ok_tool", "action": "run"}]})
    assert len(events[0]["results"]) == 1
    assert events[0]["results"][0]["success"] is True


# --- retry logic ---

def test_retry_succeeds_after_transient_failures():
    flaky = FlakyTool(fail_count=2)
    exe, _, _, _ = _make_executor([flaky])
    result = exe.execute_step({"tool": "flaky_tool", "action": "go"})
    assert result.success
    assert flaky.calls == 3  # 2 failures + 1 success


def test_retry_exhausts_all_attempts_on_persistent_failure():
    flaky = FlakyTool(fail_count=10)
    exe, _, _, _ = _make_executor([flaky])
    result = exe.execute_step({"tool": "flaky_tool", "action": "go"})
    assert not result.success
    assert flaky.calls == _MAX_RETRIES


def test_retry_no_extra_calls_on_first_success():
    flaky = FlakyTool(fail_count=0)
    exe, _, _, _ = _make_executor([flaky])
    result = exe.execute_step({"tool": "flaky_tool", "action": "go"})
    assert result.success
    assert flaky.calls == 1


def test_retry_publishes_single_error_event_after_all_attempts():
    flaky = FlakyTool(fail_count=10)
    exe, bus, _, _ = _make_executor([flaky])
    errors = []
    bus.subscribe(EVENT_TOOL_ERROR, lambda d: errors.append(d))
    exe.execute_step({"tool": "flaky_tool", "action": "go"})
    assert len(errors) == 1  # one error event total, not one per retry


def test_retry_publishes_single_executed_event_on_eventual_success():
    flaky = FlakyTool(fail_count=1)
    exe, bus, _, _ = _make_executor([flaky])
    executed = []
    bus.subscribe(EVENT_TOOL_EXECUTED, lambda d: executed.append(d))
    exe.execute_step({"tool": "flaky_tool", "action": "go"})
    assert len(executed) == 1
    assert executed[0]["success"] is True
