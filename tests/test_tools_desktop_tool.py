import pytest
from unittest.mock import patch, MagicMock
from app.tools.desktop_tool import DesktopTool


@pytest.fixture
def tool():
    return DesktopTool()


# --- open_app ---

def test_open_app_launches_process(tool):
    with patch("app.tools.desktop_tool.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        result = tool.execute("open_app", {"name": "firefox"})
        assert result.success
        assert "firefox" in result.output
        mock_popen.assert_called_once()


def test_open_app_no_name_fails(tool):
    result = tool.execute("open_app", {"name": ""})
    assert not result.success
    assert "No app name" in result.error


def test_open_app_whitespace_name_fails(tool):
    result = tool.execute("open_app", {"name": "   "})
    assert not result.success


def test_open_app_not_found_falls_back_to_xdg_open(tool):
    with patch("app.tools.desktop_tool.subprocess.Popen") as mock_popen:
        mock_popen.side_effect = [FileNotFoundError, MagicMock()]
        with patch("app.tools.desktop_tool._has", return_value=True):
            result = tool.execute("open_app", {"name": "example.com"})
            assert result.success


def test_open_app_unknown_name_fails_honestly(tool):
    with patch("app.tools.desktop_tool.subprocess.Popen") as mock_popen:
        mock_popen.side_effect = FileNotFoundError
        with patch("app.tools.desktop_tool._has", return_value=True):
            result = tool.execute("open_app", {"name": "unknown_app"})
            assert not result.success
            assert "not found" in result.error.lower()


def test_open_app_not_found_no_xdg_open_fails(tool):
    with patch("app.tools.desktop_tool.subprocess.Popen", side_effect=FileNotFoundError):
        with patch("app.tools.desktop_tool._has", return_value=False):
            result = tool.execute("open_app", {"name": "unknown_app"})
            assert not result.success
            assert "not found" in result.error


def test_open_app_uses_catalog_argv():
    catalog = MagicMock()
    catalog.resolve.return_value = ["flatpak", "run", "com.x.App"]
    tool = DesktopTool(app_catalog=catalog)
    with patch("app.tools.desktop_tool.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        result = tool.execute("open_app", {"name": "иксрей"})
        assert result.success
        catalog.resolve.assert_called_once_with("иксрей")
        assert mock_popen.call_args[0][0] == ["flatpak", "run", "com.x.App"]


def test_open_app_catalog_miss_falls_back_to_alias():
    catalog = MagicMock()
    catalog.resolve.return_value = None
    tool = DesktopTool(app_catalog=catalog)
    with patch("app.tools.desktop_tool.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        result = tool.execute("open_app", {"name": "браузер"})
        assert result.success
        assert mock_popen.call_args[0][0][0] in ("chromium", "google-chrome", "chrome", "firefox")


def test_open_app_passes_args(tool):
    with patch("app.tools.desktop_tool.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        result = tool.execute("open_app", {"name": "gedit", "args": ["/tmp/f.txt"]})
        assert result.success
        call_args = mock_popen.call_args[0][0]
        assert "gedit" in call_args
        assert "/tmp/f.txt" in call_args


# --- close_app ---

def test_close_app_pkill_success(tool):
    with patch("app.tools.desktop_tool._has", return_value=True):
        with patch("app.tools.desktop_tool.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = tool.execute("close_app", {"name": "firefox"})
            assert result.success
            assert "firefox" in result.output


def test_close_app_pkill_not_found(tool):
    with patch("app.tools.desktop_tool._has", return_value=True):
        with patch("app.tools.desktop_tool.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="")
            result = tool.execute("close_app", {"name": "firefox"})
            assert not result.success
            assert "No process found" in result.error


def test_close_app_no_name_fails(tool):
    result = tool.execute("close_app", {"name": ""})
    assert not result.success
    assert "No app name" in result.error


def test_close_app_no_pkill_no_killall_fails(tool):
    with patch("app.tools.desktop_tool._has", return_value=False):
        result = tool.execute("close_app", {"name": "app"})
        assert not result.success
        assert "requires" in result.error


# --- list_windows ---

def test_list_windows_wmctrl(tool):
    def has_wmctrl(cmd):
        return cmd == "wmctrl"
    with patch("app.tools.desktop_tool._has", side_effect=has_wmctrl):
        with patch("app.tools.desktop_tool.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="0x001 -1 host  Desktop\n0x002  0 host  Firefox\n",
                stderr="",
            )
            result = tool.execute("list_windows", {})
            assert result.success
            assert "Firefox" in result.output


def test_list_windows_wmctrl_empty(tool):
    def has_wmctrl(cmd):
        return cmd == "wmctrl"
    with patch("app.tools.desktop_tool._has", side_effect=has_wmctrl):
        with patch("app.tools.desktop_tool.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = tool.execute("list_windows", {})
            assert result.success
            assert "(no windows)" in result.output


def test_list_windows_no_tools_fails(tool):
    with patch("app.tools.desktop_tool._has", return_value=False):
        result = tool.execute("list_windows", {})
        assert not result.success
        assert "requires" in result.error


def test_list_windows_xprop_fallback(tool):
    def has_check(cmd):
        return cmd == "xprop"
    with patch("app.tools.desktop_tool._has", side_effect=has_check):
        with patch("app.tools.desktop_tool.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="_NET_CLIENT_LIST(WINDOW): window id # 0x1234567, 0x7654321\n",
                stderr="",
            )
            result = tool.execute("list_windows", {})
            assert result.success


# --- switch_window ---

def test_switch_window_wmctrl_success(tool):
    def has_wmctrl(cmd):
        return cmd == "wmctrl"
    with patch("app.tools.desktop_tool._has", side_effect=has_wmctrl):
        with patch("app.tools.desktop_tool.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = tool.execute("switch_window", {"name": "Firefox"})
            assert result.success
            assert "Firefox" in result.output


def test_switch_window_wmctrl_not_found(tool):
    def has_wmctrl(cmd):
        return cmd == "wmctrl"
    with patch("app.tools.desktop_tool._has", side_effect=has_wmctrl):
        with patch("app.tools.desktop_tool.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="")
            result = tool.execute("switch_window", {"name": "Firefox"})
            assert not result.success
            assert "not found" in result.error


def test_switch_window_no_name_fails(tool):
    result = tool.execute("switch_window", {"name": ""})
    assert not result.success
    assert "No window name" in result.error


def test_switch_window_no_tools_fails(tool):
    with patch("app.tools.desktop_tool._has", return_value=False):
        result = tool.execute("switch_window", {"name": "app"})
        assert not result.success
        assert "requires" in result.error


# --- open_terminal ---

def test_open_terminal_finds_emulator(tool):
    with patch("app.tools.desktop_tool._has", return_value=True):
        with patch("app.tools.desktop_tool.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock()
            result = tool.execute("open_terminal", {})
            assert result.success
            assert "Opened terminal" in result.output


def test_open_terminal_no_emulator_fails(tool):
    with patch("app.tools.desktop_tool._has", return_value=False):
        result = tool.execute("open_terminal", {})
        assert not result.success
        assert "No terminal emulator" in result.error


def test_open_terminal_tries_next_on_exception(tool):
    call_count = [0]

    def has_always(cmd):
        return True

    def popen_fail_first(args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("failed")
        return MagicMock()

    with patch("app.tools.desktop_tool._has", side_effect=has_always):
        with patch("app.tools.desktop_tool.subprocess.Popen", side_effect=popen_fail_first):
            result = tool.execute("open_terminal", {})
            assert result.success
            assert call_count[0] == 2


# --- unknown action ---

def test_unknown_action_fails(tool):
    result = tool.execute("fly", {})
    assert not result.success
    assert "fly" in result.error


# --- properties ---

def test_name():
    assert DesktopTool().name == "desktop"


def test_description():
    assert len(DesktopTool().description) > 5


def test_execute_sets_tool_name(tool):
    with patch("app.tools.desktop_tool.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        result = tool.execute("open_app", {"name": "xterm"})
        assert result.tool_name == "desktop"


def test_execute_sets_action(tool):
    with patch("app.tools.desktop_tool.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        result = tool.execute("open_terminal", {})
        assert result.action == "open_terminal"


# --- type_text ---

def _run_ok():
    m = MagicMock()
    m.returncode = 0
    m.stderr = ""
    return m


def test_type_text_empty_fails(tool):
    result = tool.execute("type_text", {"text": "   "})
    assert not result.success
    assert "No text" in result.error


def test_type_text_uses_clipboard_paste(tool):
    with patch("app.tools.desktop_tool._has", side_effect=lambda n: n in ("wl-copy", "ydotool")):
        with patch("app.tools.desktop_tool.subprocess.run", return_value=_run_ok()) as run:
            result = tool.execute("type_text", {"text": "привет мир"})
            assert result.success
            copy_cmd = run.call_args_list[0][0][0]
            paste_cmd = run.call_args_list[1][0][0]
            assert copy_cmd[0] == "wl-copy"
            assert "привет мир" in copy_cmd
            assert paste_cmd[0] == "ydotool"
            assert paste_cmd[1] == "key"
            assert "29:1" in paste_cmd and "47:1" in paste_cmd


def test_type_text_terminal_uses_ctrl_shift_v(tool):
    with patch("app.tools.desktop_tool._has", side_effect=lambda n: n in ("wl-copy", "ydotool", "hyprctl")):
        active = MagicMock(returncode=0, stdout='{"class": "kitty"}')
        with patch("app.tools.desktop_tool.subprocess.run",
                   side_effect=[_run_ok(), active, _run_ok()]) as run:
            result = tool.execute("type_text", {"text": "ls"})
            assert result.success
            paste_cmd = run.call_args_list[-1][0][0]
            assert "42:1" in paste_cmd


def test_type_text_falls_back_to_wtype_when_paste_fails(tool):
    fail = MagicMock(returncode=1, stderr="no socket")
    with patch("app.tools.desktop_tool._has", side_effect=lambda n: n in ("wl-copy", "ydotool", "wtype")):
        with patch("app.tools.desktop_tool.subprocess.run", side_effect=[_run_ok(), fail, _run_ok()]) as run:
            result = tool.execute("type_text", {"text": "test"})
            assert result.success
            assert run.call_args_list[-1][0][0][0] == "wtype"


def test_type_text_uses_wtype_when_no_ydotool(tool):
    with patch("app.tools.desktop_tool._has", side_effect=lambda n: n == "wtype"):
        with patch("app.tools.desktop_tool.subprocess.run", return_value=_run_ok()) as run:
            result = tool.execute("type_text", {"text": "test"})
            assert result.success
            assert run.call_args[0][0][0] == "wtype"


def test_type_text_no_tools_fails(tool):
    with patch("app.tools.desktop_tool._has", return_value=False):
        result = tool.execute("type_text", {"text": "hi"})
        assert not result.success
        assert "ydotool" in result.error


def test_press_key_enter_uses_ydotool(tool):
    with patch("app.tools.desktop_tool._has", side_effect=lambda n: n == "ydotool"):
        with patch("app.tools.desktop_tool.subprocess.run", return_value=_run_ok()) as run:
            result = tool.execute("press_key", {"key": "enter"})
            assert result.success
            cmd = run.call_args[0][0]
            assert cmd[0] == "ydotool" and "28:1" in cmd and "28:0" in cmd


def test_press_key_newline_sends_shift_enter(tool):
    with patch("app.tools.desktop_tool._has", side_effect=lambda n: n == "ydotool"):
        with patch("app.tools.desktop_tool.subprocess.run", return_value=_run_ok()) as run:
            result = tool.execute("press_key", {"key": "newline"})
            assert result.success
            cmd = run.call_args[0][0]
            assert "42:1" in cmd and "28:1" in cmd


def test_press_key_delete_word_sends_ctrl_backspace(tool):
    with patch("app.tools.desktop_tool._has", side_effect=lambda n: n == "ydotool"):
        with patch("app.tools.desktop_tool.subprocess.run", return_value=_run_ok()) as run:
            result = tool.execute("press_key", {"key": "delete_word"})
            assert result.success
            cmd = run.call_args[0][0]
            assert "29:1" in cmd and "14:1" in cmd


def test_press_key_unknown_fails(tool):
    with patch("app.tools.desktop_tool._has", side_effect=lambda n: n == "ydotool"):
        result = tool.execute("press_key", {"key": "bogus"})
        assert not result.success
        assert "Unknown key" in result.error


def test_press_key_falls_back_to_wtype(tool):
    fail = MagicMock(returncode=1, stderr="no socket")
    with patch("app.tools.desktop_tool._has", side_effect=lambda n: n in ("ydotool", "wtype")):
        with patch("app.tools.desktop_tool.subprocess.run", side_effect=[fail, _run_ok()]) as run:
            result = tool.execute("press_key", {"key": "enter"})
            assert result.success
            assert run.call_args_list[-1][0][0][:2] == ["wtype", "-k"]
