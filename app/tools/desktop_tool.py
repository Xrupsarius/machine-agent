import glob
import json
import logging
import os
import re
import shutil
import subprocess
import time

from app.tools.base_tool import BaseTool, ToolResult

log = logging.getLogger(__name__)

_TERMINAL_EMULATORS = [
    "xterm", "gnome-terminal", "konsole",
    "xfce4-terminal", "alacritty", "kitty",
]

_APP_ALIASES: dict[str, tuple[str, ...]] = {
    "браузер": ("chromium", "google-chrome", "chrome", "firefox"),
    "browser": ("chromium", "google-chrome", "chrome", "firefox"),
    "хром": ("chromium", "google-chrome", "chrome"),
    "chrome": ("google-chrome", "chromium"),
    "фаерфокс": ("firefox",),
    "терминал": ("kitty", "alacritty", "konsole", "gnome-terminal", "xterm"),
    "terminal": ("kitty", "alacritty", "konsole", "gnome-terminal", "xterm"),
    "редактор": ("gedit", "kate", "mousepad"),
    "калькулятор": ("gnome-calculator", "kcalc", "galculator"),
    "стим": ("steam",),
    "обсидиан": ("obsidian",),
    "общедиан": ("obsidian",),
    "общеден": ("obsidian",),
    "обседиан": ("obsidian",),
    "дискорд": ("discord", "vesktop"),
    "телеграм": ("telegram-desktop", "Telegram"),
    "телеграмм": ("telegram-desktop", "Telegram"),
    "проводник": ("nautilus", "dolphin", "thunar", "nemo", "pcmanfm"),
    "файлы": ("nautilus", "dolphin", "thunar", "nemo", "pcmanfm"),
    "код": ("code", "codium"),
}

_DESKTOP_DIRS = (
    "/usr/share/applications",
    os.path.expanduser("~/.local/share/applications"),
)


def _resolve_app(name: str) -> list[str]:
    return list(_APP_ALIASES.get(name.strip().lower(), (name.strip(),)))


def _find_desktop_app(name: str) -> str | None:
    needle = name.strip().lower()
    if not needle:
        return None
    for d in _DESKTOP_DIRS:
        for path in glob.glob(os.path.join(d, "*.desktop")):
            try:
                content = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            m_name = re.search(r"^Name=(.+)$", content, re.MULTILINE)
            if not m_name or needle not in m_name.group(1).lower():
                continue
            m_exec = re.search(r"^Exec=(\S+)", content, re.MULTILINE)
            if m_exec:
                binary = os.path.basename(m_exec.group(1))
                log.info(f"App '{name}' matched desktop entry: {path} -> {binary}")
                return binary
    return None


def _has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


class DesktopTool(BaseTool):
    """
    Desktop and window management.
    Uses wmctrl / xdotool when installed; falls back to xdg-open, pkill, xprop.
    ADR-007: every execution logged via BaseTool.execute().
    """

    @property
    def name(self) -> str:
        return "desktop"

    @property
    def description(self) -> str:
        return (
            "Window management: open_app, close_app, "
            "list_windows, switch_window, open_terminal, type_text"
        )

    def _run(self, action: str, parameters: dict) -> ToolResult:
        match action:
            case "open_app":
                return self._open_app(
                    parameters.get("app") or parameters.get("name", ""),
                    parameters.get("args", []),
                )
            case "close_app":
                return self._close_app(parameters.get("app") or parameters.get("name", ""))
            case "list_windows":
                return self._list_windows()
            case "switch_window":
                return self._switch_window(parameters.get("title") or parameters.get("name", ""))
            case "open_terminal":
                return self._open_terminal()
            case "type_text":
                return self._type_text(parameters.get("text", ""))
            case "close_active_window":
                return self._close_active_window()
            case _:
                return ToolResult(
                    success=False,
                    error=(
                        f"Unknown action '{action}'. Supported: "
                        "open_app, close_app, list_windows, switch_window, "
                        "open_terminal, type_text, close_active_window"
                    ),
                )

    # ------------------------------------------------------------------

    def _open_app(self, name: str, args: list) -> ToolResult:
        if not name.strip():
            return ToolResult(success=False, error="No app name provided")
        args = args if isinstance(args, list) else []
        candidates = _resolve_app(name)
        desktop_binary = _find_desktop_app(name)
        if desktop_binary and desktop_binary not in candidates:
            candidates.append(desktop_binary)
        for candidate in candidates:
            try:
                subprocess.Popen(
                    [candidate] + args,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return ToolResult(success=True, output=f"Launched: {candidate}")
            except FileNotFoundError:
                continue
            except Exception as e:
                return ToolResult(success=False, error=str(e))
        if ("/" in name or "." in name) and _has("xdg-open"):
            try:
                subprocess.Popen(
                    ["xdg-open", name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return ToolResult(success=True, output=f"Opened via xdg-open: {name}")
            except Exception as e:
                return ToolResult(success=False, error=str(e))
        return ToolResult(success=False, error=f"App not found: {name}")

    def _close_app(self, name: str) -> ToolResult:
        if not name.strip():
            return ToolResult(success=False, error="No app name provided")
        if _has("pkill"):
            for candidate in _resolve_app(name):
                proc = subprocess.run(
                    ["pkill", "-f", candidate],
                    capture_output=True, text=True,
                )
                if proc.returncode == 0:
                    return ToolResult(success=True, output=f"Closed: {candidate}")
                if proc.returncode > 1:
                    return ToolResult(success=False, error=proc.stderr.strip() or f"pkill error (code {proc.returncode})")
            return ToolResult(success=False, error=f"No process found: {name}")
        if _has("killall"):
            for candidate in _resolve_app(name):
                proc = subprocess.run(
                    ["killall", candidate],
                    capture_output=True, text=True,
                )
                if proc.returncode == 0:
                    return ToolResult(success=True, output=f"Closed: {candidate}")
            return ToolResult(success=False, error=f"No process: {name}")
        return ToolResult(success=False, error="close_app requires pkill or killall")

    def _list_windows(self) -> ToolResult:
        if _has("wmctrl"):
            proc = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True)
            if proc.returncode == 0:
                return ToolResult(
                    success=True,
                    output=proc.stdout.strip() or "(no windows)",
                )
            return ToolResult(success=False, error=proc.stderr.strip())

        if _has("xdotool"):
            return self._list_windows_xdotool()

        if _has("xprop"):
            return self._list_windows_xprop()

        return ToolResult(
            success=False,
            error="list_windows requires wmctrl, xdotool, or xprop. Install: pacman -S wmctrl",
        )

    def _list_windows_xdotool(self) -> ToolResult:
        proc = subprocess.run(
            ["xdotool", "search", "--name", ""],
            capture_output=True, text=True,
        )
        wids = proc.stdout.strip().split() if proc.returncode == 0 else []
        lines = []
        for wid in wids[:30]:
            n = subprocess.run(
                ["xdotool", "getwindowname", wid],
                capture_output=True, text=True,
            )
            if n.returncode == 0 and n.stdout.strip():
                lines.append(f"{wid}  {n.stdout.strip()}")
        return ToolResult(
            success=True,
            output="\n".join(lines) if lines else "(no windows)",
        )

    def _list_windows_xprop(self) -> ToolResult:
        proc = subprocess.run(
            ["xprop", "-root", "_NET_CLIENT_LIST"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            return ToolResult(success=False, error=proc.stderr.strip())
        # parse "# Window id: 0x... 0x..." format
        raw = proc.stdout.strip()
        ids = [x.strip().rstrip(",") for x in raw.split()
               if x.startswith("0x")]
        if not ids:
            return ToolResult(success=True, output="(no windows)")
        lines = []
        for wid in ids[:30]:
            n = subprocess.run(
                ["xprop", "-id", wid, "_NET_WM_NAME", "WM_NAME"],
                capture_output=True, text=True,
            )
            title = ""
            for line in n.stdout.splitlines():
                if "=" in line:
                    title = line.split("=", 1)[1].strip().strip('"')
                    break
            lines.append(f"{wid}  {title}" if title else wid)
        return ToolResult(success=True, output="\n".join(lines))

    def _switch_window(self, name: str) -> ToolResult:
        if not name.strip():
            return ToolResult(success=False, error="No window name provided")
        if _has("wmctrl"):
            proc = subprocess.run(
                ["wmctrl", "-a", name],
                capture_output=True, text=True,
            )
            if proc.returncode == 0:
                return ToolResult(success=True, output=f"Switched to: {name}")
            return ToolResult(success=False, error=f"Window not found: {name}")
        if _has("xdotool"):
            proc = subprocess.run(
                ["xdotool", "search", "--name", name, "windowfocus", "--sync"],
                capture_output=True, text=True,
            )
            if proc.returncode == 0:
                return ToolResult(success=True, output=f"Switched to: {name}")
            return ToolResult(success=False, error=f"Window not found: {name}")
        return ToolResult(
            success=False,
            error="switch_window requires wmctrl or xdotool. Install: pacman -S wmctrl",
        )

    def _close_active_window(self) -> ToolResult:
        if _has("hyprctl"):
            proc = subprocess.run(
                ["hyprctl", "dispatch", "killactive"],
                capture_output=True, text=True,
            )
            if proc.returncode == 0:
                return ToolResult(success=True, output="Active window closed")
            return ToolResult(success=False, error=proc.stderr.strip() or "hyprctl failed")
        if _has("xdotool"):
            proc = subprocess.run(
                ["xdotool", "getactivewindow", "windowclose"],
                capture_output=True, text=True,
            )
            if proc.returncode == 0:
                return ToolResult(success=True, output="Active window closed")
            return ToolResult(success=False, error=proc.stderr.strip() or "xdotool failed")
        return ToolResult(
            success=False,
            error="close_active_window requires hyprctl or xdotool",
        )

    def _active_window_is_terminal(self) -> bool:
        if not _has("hyprctl"):
            return False
        try:
            proc = subprocess.run(
                ["hyprctl", "activewindow", "-j"],
                capture_output=True, text=True, timeout=3,
            )
            cls = json.loads(proc.stdout).get("class", "").lower()
        except Exception:
            return False
        return any(t in cls for t in ("kitty", "alacritty", "konsole", "terminal", "xterm", "foot"))

    def _paste_text(self, text: str) -> ToolResult | None:
        if not (_has("wl-copy") and _has("wtype")):
            return None
        copy = subprocess.run(
            ["wl-copy", "--", text],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
        )
        if copy.returncode != 0:
            return None
        time.sleep(0.2)
        if self._active_window_is_terminal():
            keys = ["-M", "ctrl", "-M", "shift", "-P", "v", "-p", "v", "-m", "shift", "-m", "ctrl"]
        else:
            keys = ["-M", "ctrl", "-P", "v", "-p", "v", "-m", "ctrl"]
        proc = subprocess.run(["wtype"] + keys, capture_output=True, text=True)
        if proc.returncode == 0:
            return ToolResult(success=True, output=f"Typed: {text}")
        return None

    def _type_text(self, text: str) -> ToolResult:
        if not text.strip():
            return ToolResult(success=False, error="No text provided")

        pasted = self._paste_text(text)
        if pasted is not None:
            return pasted

        if _has("wtype"):
            proc = subprocess.run(
                ["wtype", "-s", "200", "-d", "12", text],
                capture_output=True, text=True,
            )
            if proc.returncode == 0:
                return ToolResult(success=True, output=f"Typed: {text}")
            return ToolResult(success=False, error=proc.stderr.strip() or "wtype failed")
        if _has("ydotool"):
            proc = subprocess.run(
                ["ydotool", "type", "--key-delay", "12", "--", text],
                capture_output=True, text=True,
            )
            if proc.returncode == 0:
                return ToolResult(success=True, output=f"Typed: {text}")
            return ToolResult(success=False, error=proc.stderr.strip() or "ydotool failed")
        if _has("xdotool"):
            proc = subprocess.run(
                ["xdotool", "type", "--delay", "12", "--", text],
                capture_output=True, text=True,
            )
            if proc.returncode == 0:
                return ToolResult(success=True, output=f"Typed: {text}")
            return ToolResult(success=False, error=proc.stderr.strip() or "xdotool failed")

        return ToolResult(
            success=False,
            error="type_text requires wtype, ydotool, or xdotool. Install: sudo pacman -S wtype",
        )

    def _open_terminal(self) -> ToolResult:
        for emulator in _TERMINAL_EMULATORS:
            if not _has(emulator):
                continue
            try:
                subprocess.Popen(
                    [emulator],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return ToolResult(success=True, output=f"Opened terminal: {emulator}")
            except Exception:
                continue
        return ToolResult(
            success=False,
            error=f"No terminal emulator found. Tried: {_TERMINAL_EMULATORS}",
        )
