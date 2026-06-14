import pytest
from app.tools.base_tool import BaseTool, ToolResult


# --- concrete stub for testing ---
class EchoTool(BaseTool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes the action"

    def _run(self, action: str, parameters: dict) -> ToolResult:
        if action == "fail":
            return ToolResult(success=False, error="forced failure")
        return ToolResult(success=True, output=f"echo:{action}")


class ExplodingTool(BaseTool):
    @property
    def name(self) -> str:
        return "exploding"

    @property
    def description(self) -> str:
        return "Always raises"

    def _run(self, action: str, parameters: dict) -> ToolResult:
        raise RuntimeError("boom")


# --- ToolResult ---

def test_tool_result_defaults():
    r = ToolResult(success=True)
    assert r.output == ""
    assert r.error == ""
    assert r.tool_name == ""
    assert r.action == ""


def test_tool_result_to_dict():
    r = ToolResult(success=True, output="ok", error="", tool_name="t", action="a")
    d = r.to_dict()
    assert d["success"] is True
    assert d["output"] == "ok"
    assert d["tool_name"] == "t"
    assert d["action"] == "a"


def test_tool_result_failure():
    r = ToolResult(success=False, error="something went wrong")
    assert not r.success
    assert r.error == "something went wrong"


# --- BaseTool (via EchoTool) ---

def test_execute_calls_run():
    t = EchoTool()
    r = t.execute("hello")
    assert r.success
    assert r.output == "echo:hello"


def test_execute_sets_tool_name():
    t = EchoTool()
    r = t.execute("x")
    assert r.tool_name == "echo"


def test_execute_sets_action():
    t = EchoTool()
    r = t.execute("my_action")
    assert r.action == "my_action"


def test_execute_failure_result():
    t = EchoTool()
    r = t.execute("fail")
    assert not r.success
    assert r.error == "forced failure"


def test_execute_none_parameters_defaults_to_empty_dict():
    t = EchoTool()
    r = t.execute("x", None)
    assert r.success


def test_execute_catches_exception():
    t = ExplodingTool()
    r = t.execute("anything")
    assert not r.success
    assert "boom" in r.error


def test_cannot_instantiate_base_tool_directly():
    with pytest.raises(TypeError):
        BaseTool()


def test_name_property():
    assert EchoTool().name == "echo"


def test_description_property():
    assert "Echo" in EchoTool().description
