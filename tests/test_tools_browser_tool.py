"""
BrowserTool tests.
Unit tests mock Playwright to avoid a real browser launch.
Integration tests (marked slow) use headless Chromium.
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from app.tools.browser_tool import BrowserTool


# ------------------------------------------------------------------
# Mock factory
# ------------------------------------------------------------------

def _make_page(title="Test Page", text="Hello", closed=False):
    page = MagicMock()
    page.title.return_value = title
    page.inner_text.return_value = text
    page.is_closed.return_value = closed
    page.goto.return_value = None
    page.click.return_value = None
    page.fill.return_value = None
    page.go_back.return_value = None
    page.bring_to_front.return_value = None
    page.close.return_value = None
    return page


def _make_context(page):
    ctx = MagicMock()
    ctx.new_page.return_value = page
    return ctx


def _make_browser(context, connected=True):
    browser = MagicMock()
    browser.is_connected.return_value = connected
    browser.new_context.return_value = context
    browser.close.return_value = None
    return browser


def _make_pw(browser):
    pw = MagicMock()
    chromium = MagicMock()
    chromium.launch.return_value = browser
    pw.chromium = chromium
    pw.stop.return_value = None
    return pw


def _patched_tool(title="Test Page", text="Body text"):
    """Create a BrowserTool with a fully mocked Playwright session."""
    page = _make_page(title=title, text=text)
    ctx = _make_context(page)
    browser = _make_browser(ctx)
    pw = _make_pw(browser)

    tool = BrowserTool(headless=True)
    tool._pw = pw
    tool._browser = browser
    tool._context = ctx
    tool._pages = [page]
    tool._current = 0
    return tool, page


# ------------------------------------------------------------------
# Properties
# ------------------------------------------------------------------

def test_name():
    assert BrowserTool().name == "browser"


def test_description():
    assert len(BrowserTool().description) > 5


def test_execute_sets_tool_name():
    tool, _ = _patched_tool()
    result = tool.execute("get_title", {})
    assert result.tool_name == "browser"


def test_execute_sets_action():
    tool, _ = _patched_tool()
    result = tool.execute("get_title", {})
    assert result.action == "get_title"


# ------------------------------------------------------------------
# playwright not installed
# ------------------------------------------------------------------

def test_playwright_unavailable_returns_error():
    with patch("app.tools.browser_tool._PW_OK", False):
        tool = BrowserTool()
        result = tool.execute("open_url", {"url": "https://example.com"})
        assert not result.success
        assert "Playwright" in result.error


# ------------------------------------------------------------------
# open_url
# ------------------------------------------------------------------

def test_open_url_success():
    tool, page = _patched_tool(title="Example Domain")
    result = tool.execute("open_url", {"url": "https://example.com"})
    assert result.success
    page.goto.assert_called_once()
    assert "Example Domain" in result.output


def test_open_url_empty_fails():
    tool, _ = _patched_tool()
    result = tool.execute("open_url", {"url": ""})
    assert not result.success
    assert "No URL" in result.error


def test_open_url_goto_exception():
    tool, page = _patched_tool()
    page.goto.side_effect = Exception("net::ERR_NAME_NOT_RESOLVED")
    result = tool.execute("open_url", {"url": "https://not-a-real-url.invalid"})
    assert not result.success
    assert "ERR_NAME_NOT_RESOLVED" in result.error


# ------------------------------------------------------------------
# new_tab
# ------------------------------------------------------------------

def test_new_tab_creates_tab():
    tool, _ = _patched_tool()
    initial_count = len(tool._pages)
    new_page = _make_page(title="New Tab")
    tool._context.new_page.return_value = new_page

    result = tool.execute("new_tab", {})
    assert result.success
    assert len(tool._pages) == initial_count + 1


def test_new_tab_with_url():
    tool, _ = _patched_tool()
    new_page = _make_page(title="Loaded")
    tool._context.new_page.return_value = new_page

    result = tool.execute("new_tab", {"url": "about:blank"})
    assert result.success
    new_page.goto.assert_called_once()


# ------------------------------------------------------------------
# switch_tab
# ------------------------------------------------------------------

def test_switch_tab_by_index():
    tool, page0 = _patched_tool(title="Tab 0")
    page1 = _make_page(title="Tab 1")
    tool._pages = [page0, page1]
    tool._current = 0

    result = tool.execute("switch_tab", {"index": 1})
    assert result.success
    assert tool._current == 1
    assert "Tab 1" in result.output


def test_switch_tab_by_title():
    tool, page0 = _patched_tool(title="Firefox")
    page1 = _make_page(title="Gedit")
    tool._pages = [page0, page1]
    tool._current = 0

    result = tool.execute("switch_tab", {"title": "Gedit"})
    assert result.success
    assert tool._current == 1


def test_switch_tab_title_not_found():
    tool, _ = _patched_tool(title="Tab")
    result = tool.execute("switch_tab", {"title": "Ghost"})
    assert not result.success


def test_switch_tab_index_out_of_range():
    tool, _ = _patched_tool()
    result = tool.execute("switch_tab", {"index": 99})
    assert not result.success


# ------------------------------------------------------------------
# click
# ------------------------------------------------------------------

def test_click_success():
    tool, page = _patched_tool()
    result = tool.execute("click", {"selector": "button#submit"})
    assert result.success
    page.click.assert_called_once_with("button#submit", timeout=10_000)
    assert "button#submit" in result.output


def test_click_empty_selector_fails():
    tool, _ = _patched_tool()
    result = tool.execute("click", {"selector": ""})
    assert not result.success
    assert "No selector" in result.error


def test_click_exception():
    tool, page = _patched_tool()
    page.click.side_effect = Exception("Element not found")
    result = tool.execute("click", {"selector": "#missing"})
    assert not result.success


# ------------------------------------------------------------------
# fill_form
# ------------------------------------------------------------------

def test_fill_form_success():
    tool, page = _patched_tool()
    result = tool.execute("fill_form", {"selector": "input#username", "value": "admin"})
    assert result.success
    page.fill.assert_called_once_with("input#username", "admin", timeout=10_000)
    assert "admin" in result.output


def test_fill_form_empty_selector_fails():
    tool, _ = _patched_tool()
    result = tool.execute("fill_form", {"selector": "", "value": "x"})
    assert not result.success


def test_fill_form_exception():
    tool, page = _patched_tool()
    page.fill.side_effect = Exception("Timeout")
    result = tool.execute("fill_form", {"selector": "#field", "value": "val"})
    assert not result.success


# ------------------------------------------------------------------
# get_title
# ------------------------------------------------------------------

def test_get_title_returns_title():
    tool, _ = _patched_tool(title="My Page")
    result = tool.execute("get_title", {})
    assert result.success
    assert result.output == "My Page"


# ------------------------------------------------------------------
# get_text
# ------------------------------------------------------------------

def test_get_text_body():
    tool, page = _patched_tool(text="Page content here")
    result = tool.execute("get_text", {"selector": "body"})
    assert result.success
    assert "Page content here" in result.output


def test_get_text_default_selector():
    tool, page = _patched_tool(text="default body text")
    result = tool.execute("get_text", {})
    assert result.success
    page.inner_text.assert_called_with("body", timeout=10_000)


# ------------------------------------------------------------------
# go_back
# ------------------------------------------------------------------

def test_go_back_success():
    tool, page = _patched_tool()
    result = tool.execute("go_back", {})
    assert result.success
    page.go_back.assert_called_once()


def test_go_back_exception():
    tool, page = _patched_tool()
    page.go_back.side_effect = Exception("Cannot go back")
    result = tool.execute("go_back", {})
    assert not result.success


# ------------------------------------------------------------------
# close_tab
# ------------------------------------------------------------------

def test_close_tab_removes_from_list():
    tool, page0 = _patched_tool()
    page1 = _make_page(title="Second")
    tool._pages = [page0, page1]
    tool._current = 0

    result = tool.execute("close_tab", {})
    assert result.success
    assert len(tool._pages) == 1


def test_close_tab_no_tabs_fails():
    tool, _ = _patched_tool()
    tool._pages = []
    result = tool.execute("close_tab", {})
    assert not result.success


# ------------------------------------------------------------------
# close_browser
# ------------------------------------------------------------------

def test_close_browser_clears_session():
    tool, _ = _patched_tool()
    result = tool.execute("close_browser", {})
    assert result.success
    assert tool._browser is None
    assert tool._pw is None
    assert tool._pages == []


# ------------------------------------------------------------------
# unknown action
# ------------------------------------------------------------------

def test_unknown_action_fails():
    tool, _ = _patched_tool()
    result = tool.execute("fly", {})
    assert not result.success
    assert "fly" in result.error


# ------------------------------------------------------------------
# Integration tests (real headless Chromium)
# ------------------------------------------------------------------

@pytest.mark.slow
def test_integration_open_about_blank():
    tool = BrowserTool(headless=True, executable_path="/usr/bin/chromium")
    try:
        result = tool.execute("open_url", {"url": "about:blank"})
        assert result.success
    finally:
        tool.execute("close_browser", {})


@pytest.mark.slow
def test_integration_data_uri():
    html = "data:text/html,<h1>Hello</h1>"
    tool = BrowserTool(headless=True, executable_path="/usr/bin/chromium")
    try:
        r1 = tool.execute("open_url", {"url": html})
        assert r1.success
        r2 = tool.execute("get_text", {"selector": "h1"})
        assert r2.success
        assert "Hello" in r2.output
    finally:
        tool.execute("close_browser", {})


@pytest.mark.slow
def test_integration_fill_and_click():
    html = (
        "data:text/html,"
        "<input id='q' type='text'/>"
        "<button id='btn' onclick=\"document.title='clicked'\">Go</button>"
    )
    tool = BrowserTool(headless=True, executable_path="/usr/bin/chromium")
    try:
        tool.execute("open_url", {"url": html})
        r_fill = tool.execute("fill_form", {"selector": "#q", "value": "hello"})
        assert r_fill.success
        r_click = tool.execute("click", {"selector": "#btn"})
        assert r_click.success
    finally:
        tool.execute("close_browser", {})


@pytest.mark.slow
def test_integration_new_tab_and_switch():
    tool = BrowserTool(headless=True, executable_path="/usr/bin/chromium")
    try:
        tool.execute("open_url", {"url": "about:blank"})
        tool.execute("new_tab", {"url": "about:blank"})
        assert len(tool._pages) == 2
        r = tool.execute("switch_tab", {"index": 0})
        assert r.success
        assert tool._current == 0
    finally:
        tool.execute("close_browser", {})
