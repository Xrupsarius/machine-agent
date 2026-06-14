import pytest
from unittest.mock import patch, MagicMock
from app.tools.terminal_tool import TerminalTool


@pytest.fixture
def tool():
    return TerminalTool(timeout=5)


# --- execute ---

def test_execute_echo():
    result = TerminalTool().execute("execute", {"command": "echo hello"})
    assert result.success
    assert "hello" in result.output


def test_execute_captures_stdout():
    result = TerminalTool().execute("execute", {"command": "echo test_output"})
    assert result.success
    assert "test_output" in result.output


def test_execute_nonzero_exit_is_failure(tool):
    result = tool.execute("execute", {"command": "exit 1"})
    assert not result.success


def test_execute_empty_command_is_failure(tool):
    result = tool.execute("execute", {"command": ""})
    assert not result.success
    assert "No command" in result.error


def test_execute_whitespace_command_is_failure(tool):
    result = tool.execute("execute", {"command": "   "})
    assert not result.success


def test_execute_invalid_command_is_failure(tool):
    result = tool.execute("execute", {"command": "nonexistent_command_xyz_123"})
    assert not result.success


def test_execute_timeout(tool):
    t = TerminalTool(timeout=1)
    result = t.execute("execute", {"command": "sleep 5"})
    assert not result.success
    assert "timed out" in result.error.lower()


def test_execute_sets_tool_name(tool):
    result = tool.execute("execute", {"command": "echo x"})
    assert result.tool_name == "terminal"


def test_execute_sets_action(tool):
    result = tool.execute("execute", {"command": "echo x"})
    assert result.action == "execute"


# --- execute_background ---

def test_execute_background_starts_process(tool):
    result = tool.execute("execute_background", {"command": "sleep 1"})
    assert result.success
    assert "PID" in result.output


def test_execute_background_empty_command_fails(tool):
    result = tool.execute("execute_background", {"command": ""})
    assert not result.success


# --- execute_interactive ---

def test_execute_interactive_finds_emulator():
    with patch("app.tools.terminal_tool.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        t = TerminalTool()
        result = t.execute("execute_interactive", {})
        assert result.success
        assert "Opened terminal" in result.output


def test_execute_interactive_no_emulator_fails():
    with patch("app.tools.terminal_tool.subprocess.Popen") as mock_popen:
        mock_popen.side_effect = FileNotFoundError
        t = TerminalTool()
        result = t.execute("execute_interactive", {})
        assert not result.success
        assert "No terminal emulator" in result.error


def test_execute_interactive_with_command():
    with patch("app.tools.terminal_tool.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        t = TerminalTool()
        result = t.execute("execute_interactive", {"command": "bash"})
        assert result.success
        call_args = mock_popen.call_args[0][0]
        assert "bash" in call_args


# --- open ---

def test_open_action_opens_terminal():
    with patch("app.tools.terminal_tool.subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        t = TerminalTool()
        result = t.execute("open", {})
        assert result.success


# --- unknown action ---

def test_unknown_action_is_failure(tool):
    result = tool.execute("fly_to_moon", {})
    assert not result.success
    assert "fly_to_moon" in result.error


# --- tool properties ---

def test_name():
    assert TerminalTool().name == "terminal"


def test_description():
    assert len(TerminalTool().description) > 5
