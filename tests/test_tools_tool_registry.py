import pytest
from app.tools.base_tool import BaseTool, ToolResult
from app.tools.tool_registry import ToolRegistry, ToolNotFoundError


class FakeTool(BaseTool):
    def __init__(self, tool_name: str) -> None:
        self._name = tool_name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Fake tool: {self._name}"

    def _run(self, action: str, parameters: dict) -> ToolResult:
        return ToolResult(success=True, output="ok")


@pytest.fixture
def registry():
    return ToolRegistry()


def test_register_and_has(registry):
    registry.register(FakeTool("terminal"))
    assert registry.has("terminal")


def test_has_returns_false_if_missing(registry):
    assert not registry.has("nonexistent")


def test_get_returns_registered_tool(registry):
    tool = FakeTool("filesystem")
    registry.register(tool)
    assert registry.get("filesystem") is tool


def test_get_raises_if_not_found(registry):
    with pytest.raises(ToolNotFoundError, match="not registered"):
        registry.get("ghost")


def test_all_names_empty_initially(registry):
    assert registry.all_names() == []


def test_all_names_after_register(registry):
    registry.register(FakeTool("a"))
    registry.register(FakeTool("b"))
    names = registry.all_names()
    assert "a" in names
    assert "b" in names
    assert len(names) == 2


def test_overwrite_replaces_tool(registry):
    t1 = FakeTool("terminal")
    t2 = FakeTool("terminal")
    registry.register(t1)
    registry.register(t2)
    assert registry.get("terminal") is t2


def test_multiple_tools_independent(registry):
    ta = FakeTool("desktop")
    tb = FakeTool("browser")
    registry.register(ta)
    registry.register(tb)
    assert registry.get("desktop") is ta
    assert registry.get("browser") is tb
