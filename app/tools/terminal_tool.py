import logging
import subprocess
from app.tools.base_tool import BaseTool, ToolResult

log = logging.getLogger(__name__)

_TERMINAL_EMULATORS = [
    "xterm",
    "gnome-terminal",
    "konsole",
    "xfce4-terminal",
    "alacritty",
    "kitty",
]


class TerminalTool(BaseTool):
    """
    Executes shell commands.
    Security check happens BEFORE this tool is called (SecurityValidator).
    ADR-007: every execution is logged via BaseTool.execute().
    """

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "terminal"

    @property
    def description(self) -> str:
        return "Run shell commands: execute, execute_background, execute_interactive"

    def _run(self, action: str, parameters: dict) -> ToolResult:
        match action:
            case "execute":
                return self._execute(parameters.get("command", ""))
            case "execute_background":
                return self._execute_background(parameters.get("command", ""))
            case "execute_interactive":
                return self._execute_interactive(parameters.get("command", ""))
            case "open":
                return self._execute_interactive()
            case _:
                return ToolResult(
                    success=False,
                    error=f"Unknown action '{action}'. "
                          "Supported: execute, execute_background, execute_interactive, open",
                )

    # ------------------------------------------------------------------

    def _execute(self, command: str) -> ToolResult:
        if not command.strip():
            return ToolResult(success=False, error="No command provided")
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            output = proc.stdout.strip()
            stderr = proc.stderr.strip()
            if proc.returncode == 0:
                return ToolResult(success=True, output=output)
            return ToolResult(
                success=False,
                output=output,
                error=stderr or f"Exit code {proc.returncode}",
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error=f"Command timed out after {self._timeout}s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _execute_background(self, command: str) -> ToolResult:
        if not command.strip():
            return ToolResult(success=False, error="No command provided")
        try:
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return ToolResult(success=True, output=f"Started in background (PID {proc.pid})")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _execute_interactive(self, command: str = "") -> ToolResult:
        for emulator in _TERMINAL_EMULATORS:
            try:
                args = [emulator]
                if command.strip():
                    args += ["-e", command]
                subprocess.Popen(args)
                return ToolResult(success=True, output=f"Opened terminal: {emulator}")
            except FileNotFoundError:
                continue
            except Exception as e:
                return ToolResult(success=False, error=str(e))
        return ToolResult(
            success=False,
            error=f"No terminal emulator found. Tried: {_TERMINAL_EMULATORS}",
        )
