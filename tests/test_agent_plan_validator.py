import pytest
from app.agent.plan_validator import PlanValidator, PlanValidationError, VALID_TOOLS


@pytest.fixture
def v():
    return PlanValidator()


def _step(tool="desktop", action="open_terminal", **extra):
    return {"tool": tool, "action": action, **extra}


# --- validate: happy path ---

def test_empty_steps_is_valid(v):
    v.validate({"intent": "x", "steps": []})


def test_single_step_is_valid(v):
    v.validate({"intent": "open_terminal", "steps": [_step()]})


def test_multiple_steps_valid(v):
    v.validate({"steps": [_step("terminal", "execute"), _step("filesystem", "read")]})


def test_all_valid_tools_accepted(v):
    for tool in VALID_TOOLS:
        v.validate({"steps": [_step(tool=tool)]})


def test_extra_fields_in_step_are_allowed(v):
    v.validate({"steps": [_step(parameters={"cmd": "ls"})]})


# --- validate: structure errors ---

def test_non_dict_plan_raises(v):
    with pytest.raises(PlanValidationError, match="JSON object"):
        v.validate(["not", "a", "dict"])


def test_missing_steps_raises(v):
    with pytest.raises(PlanValidationError, match="steps"):
        v.validate({"intent": "x"})


def test_steps_not_list_raises(v):
    with pytest.raises(PlanValidationError, match="list"):
        v.validate({"steps": "not a list"})


def test_step_not_dict_raises(v):
    with pytest.raises(PlanValidationError, match="Step 0"):
        v.validate({"steps": ["string_step"]})


def test_step_missing_tool_raises(v):
    with pytest.raises(PlanValidationError, match="tool"):
        v.validate({"steps": [{"action": "do_something"}]})


def test_step_missing_action_raises(v):
    with pytest.raises(PlanValidationError, match="action"):
        v.validate({"steps": [{"tool": "desktop"}]})


def test_unknown_tool_raises(v):
    with pytest.raises(PlanValidationError, match="unknown tool"):
        v.validate({"steps": [_step(tool="nonexistent_tool")]})


def test_empty_action_raises(v):
    with pytest.raises(PlanValidationError, match="action"):
        v.validate({"steps": [{"tool": "desktop", "action": ""}]})


def test_whitespace_only_action_raises(v):
    with pytest.raises(PlanValidationError, match="action"):
        v.validate({"steps": [{"tool": "desktop", "action": "   "}]})


# --- is_valid ---

def test_is_valid_returns_true_for_valid(v):
    ok, err = v.is_valid({"steps": [_step()]})
    assert ok is True
    assert err is None


def test_is_valid_returns_false_for_invalid(v):
    ok, err = v.is_valid({"steps": [{"tool": "bad_tool", "action": "x"}]})
    assert ok is False
    assert isinstance(err, str) and len(err) > 0


def test_valid_tools_set_has_expected_members():
    expected = {"terminal", "filesystem", "desktop", "browser", "accessibility", "vision", "memory"}
    assert VALID_TOOLS == expected
