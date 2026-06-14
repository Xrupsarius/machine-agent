import pytest
from unittest.mock import MagicMock, patch
from app.tools.accessibility_tool import AccessibilityTool


def _make_node(name="", role="", children=None, action_names=None, text=None):
    """Build a mock AT-SPI accessible node."""
    node = MagicMock()
    node.get_name.return_value = name
    node.get_role_name.return_value = role

    kids = children or []
    node.get_child_count.return_value = len(kids)
    node.get_child_at_index.side_effect = lambda i: kids[i] if i < len(kids) else None

    # Action interface
    if action_names:
        action_iface = MagicMock()
        action_iface.get_n_actions.return_value = len(action_names)
        action_iface.get_action_name.side_effect = lambda i: action_names[i]
        action_iface.do_action.return_value = True
        node.get_action_iface.return_value = action_iface
    else:
        node.get_action_iface.return_value = None

    # Component interface
    comp = MagicMock()
    comp.grab_focus.return_value = True
    node.get_component_iface.return_value = comp

    # Text interface
    if text is not None:
        text_iface = MagicMock()
        text_iface.get_character_count.return_value = len(text)
        text_iface.get_text.return_value = text
        node.get_text_iface.return_value = text_iface
    else:
        node.get_text_iface.return_value = None

    # EditableText interface
    et = MagicMock()
    et.insert_text.return_value = True
    node.get_editable_text_iface.return_value = et

    return node


@pytest.fixture
def tool():
    return AccessibilityTool()


def _desktop_with(*apps):
    desktop = MagicMock()
    desktop.get_child_count.return_value = len(apps)
    desktop.get_child_at_index.side_effect = lambda i: apps[i] if i < len(apps) else None
    return desktop


# ------------------------------------------------------------------
# find_element
# ------------------------------------------------------------------

def test_find_element_by_name(tool):
    btn = _make_node(name="OK", role="push button")
    desktop = _desktop_with(_make_node(name="App", children=[btn]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("find_element", {"name": "OK"})
    assert result.success
    assert "OK" in result.output


def test_find_element_by_role(tool):
    btn = _make_node(name="Submit", role="push button")
    desktop = _desktop_with(_make_node(name="App", children=[btn]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("find_element", {"role": "push button"})
    assert result.success
    assert "push button" in result.output


def test_find_element_not_found(tool):
    desktop = _desktop_with(_make_node(name="App", children=[]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("find_element", {"name": "NonExistent"})
    assert not result.success
    assert "not found" in result.error.lower()


def test_find_element_no_criteria_fails(tool):
    result = tool.execute("find_element", {})
    assert not result.success


def test_find_element_shows_count(tool):
    kids = [_make_node(name="OK", role="push button"),
            _make_node(name="OK", role="push button")]
    desktop = _desktop_with(_make_node(name="App", children=kids))
    tool._get_desktop = lambda: desktop

    result = tool.execute("find_element", {"name": "OK"})
    assert result.success
    assert "2" in result.output


# ------------------------------------------------------------------
# click_element
# ------------------------------------------------------------------

def test_click_element_via_action(tool):
    btn = _make_node(name="Submit", role="push button", action_names=["click"])
    desktop = _desktop_with(_make_node(name="App", children=[btn]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("click_element", {"name": "Submit"})
    assert result.success
    assert "Submit" in result.output


def test_click_element_activate_action(tool):
    btn = _make_node(name="OK", role="push button", action_names=["activate"])
    desktop = _desktop_with(_make_node(name="App", children=[btn]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("click_element", {"name": "OK"})
    assert result.success


def test_click_element_fallback_to_focus(tool):
    node = _make_node(name="Item", role="menu item", action_names=[])
    desktop = _desktop_with(_make_node(name="App", children=[node]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("click_element", {"name": "Item"})
    assert result.success
    assert "Focused" in result.output or "Item" in result.output


def test_click_element_not_found(tool):
    desktop = _desktop_with(_make_node(name="App", children=[]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("click_element", {"name": "Ghost"})
    assert not result.success


def test_click_element_no_name_fails(tool):
    result = tool.execute("click_element", {})
    assert not result.success
    assert "No element name" in result.error


# ------------------------------------------------------------------
# type_text
# ------------------------------------------------------------------

def test_type_text_into_named_element(tool):
    field = _make_node(name="Search", role="text")
    desktop = _desktop_with(_make_node(name="App", children=[field]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("type_text", {"text": "hello", "element_name": "Search"})
    assert result.success
    assert "hello" in result.output


def test_type_text_no_text_fails(tool):
    result = tool.execute("type_text", {"text": "", "element_name": "field"})
    assert not result.success
    assert "No text" in result.error


def test_type_text_element_not_found(tool):
    desktop = _desktop_with(_make_node(name="App", children=[]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("type_text", {"text": "hello", "element_name": "Missing"})
    assert not result.success


def test_type_text_xdotool_fallback(tool):
    with patch("app.tools.accessibility_tool.shutil.which", return_value="/usr/bin/xdotool"):
        with patch("app.tools.accessibility_tool.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = tool.execute("type_text", {"text": "world"})
            assert result.success
            assert "world" in result.output


def test_type_text_no_element_no_xdotool_fails(tool):
    with patch("app.tools.accessibility_tool.shutil.which", return_value=None):
        result = tool.execute("type_text", {"text": "hi"})
        assert not result.success


# ------------------------------------------------------------------
# get_text
# ------------------------------------------------------------------

def test_get_text_from_element(tool):
    node = _make_node(name="Label", text="Hello World")
    desktop = _desktop_with(_make_node(name="App", children=[node]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("get_text", {"name": "Label"})
    assert result.success
    assert "Hello World" in result.output


def test_get_text_no_name_fails(tool):
    result = tool.execute("get_text", {})
    assert not result.success


def test_get_text_not_found(tool):
    desktop = _desktop_with(_make_node(name="App", children=[]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("get_text", {"name": "Ghost"})
    assert not result.success


def test_get_text_fallback_to_name(tool):
    node = _make_node(name="Menu Item Text")
    node.get_text_iface.return_value = None
    desktop = _desktop_with(_make_node(name="App", children=[node]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("get_text", {"name": "Menu Item Text"})
    assert result.success
    assert "Menu Item Text" in result.output


# ------------------------------------------------------------------
# list_elements
# ------------------------------------------------------------------

def test_list_elements_shows_apps(tool):
    app1 = _make_node(name="Firefox", children=[_make_node(name="Main Window", role="frame")])
    desktop = _desktop_with(app1)
    tool._get_desktop = lambda: desktop

    result = tool.execute("list_elements", {})
    assert result.success
    assert "Firefox" in result.output


def test_list_elements_filters_by_app(tool):
    app1 = _make_node(name="Firefox")
    app2 = _make_node(name="Gedit")
    desktop = _desktop_with(app1, app2)
    tool._get_desktop = lambda: desktop

    result = tool.execute("list_elements", {"app": "Firefox"})
    assert result.success
    assert "Firefox" in result.output
    assert "Gedit" not in result.output


def test_list_elements_empty_desktop(tool):
    desktop = _desktop_with()
    tool._get_desktop = lambda: desktop

    result = tool.execute("list_elements", {})
    assert result.success
    assert "no accessible" in result.output.lower()


# ------------------------------------------------------------------
# focus_element
# ------------------------------------------------------------------

def test_focus_element_success(tool):
    node = _make_node(name="Username", role="text")
    desktop = _desktop_with(_make_node(name="App", children=[node]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("focus_element", {"name": "Username"})
    assert result.success
    assert "Username" in result.output


def test_focus_element_no_name_fails(tool):
    result = tool.execute("focus_element", {})
    assert not result.success
    assert "No element name" in result.error


def test_focus_element_not_found(tool):
    desktop = _desktop_with(_make_node(name="App", children=[]))
    tool._get_desktop = lambda: desktop

    result = tool.execute("focus_element", {"name": "Ghost"})
    assert not result.success


# ------------------------------------------------------------------
# unknown action
# ------------------------------------------------------------------

def test_unknown_action_fails(tool):
    result = tool.execute("fly", {})
    assert not result.success
    assert "fly" in result.error


# ------------------------------------------------------------------
# AT-SPI unavailable
# ------------------------------------------------------------------

def test_atspi_unavailable_returns_error():
    with patch("app.tools.accessibility_tool._ATSPI_OK", False):
        t = AccessibilityTool()
        result = t.execute("find_element", {"name": "btn"})
        assert not result.success
        assert "AT-SPI" in result.error


# ------------------------------------------------------------------
# tool properties
# ------------------------------------------------------------------

def test_name():
    assert AccessibilityTool().name == "accessibility"


def test_description():
    assert len(AccessibilityTool().description) > 5


def test_execute_sets_tool_name(tool):
    result = tool.execute("find_element", {})
    assert result.tool_name == "accessibility"


def test_execute_sets_action(tool):
    result = tool.execute("find_element", {})
    assert result.action == "find_element"
