import logging
import os
import threading
from typing import Optional

from app.tools.base_tool import BaseTool, ToolResult

log = logging.getLogger(__name__)

_CHROMIUM_PATHS = [
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
]

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
    _PW_OK = True
except ImportError:
    _PW_OK = False
    log.warning("Playwright not installed. Run: pip install playwright")


def _find_chromium() -> str:
    for path in _CHROMIUM_PATHS:
        if os.path.exists(path):
            return path
    return ""


class BrowserTool(BaseTool):
    """
    Browser automation via Playwright (Chromium).
    Maintains a persistent session across calls.
    ADR-007: every execution logged via BaseTool.execute().
    Thread-safe: all Playwright calls serialised with a lock.
    """

    def __init__(self, headless: bool = False, executable_path: str = "") -> None:
        self._headless = headless
        self._exe = executable_path or _find_chromium()
        self._lock = threading.Lock()
        self._pw = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._pages: list = []
        self._current: int = 0

    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return (
            "Browser automation: open_url, new_tab, switch_tab, "
            "click, fill_form, get_title, get_text, go_back, close_tab, close_browser"
        )

    def _run(self, action: str, parameters: dict) -> ToolResult:
        if not _PW_OK:
            return ToolResult(
                success=False,
                error="Playwright not installed. Run: pip install playwright",
            )
        with self._lock:
            match action:
                case "open_url":
                    return self._open_url(parameters.get("url", ""))
                case "new_tab":
                    return self._new_tab(parameters.get("url", ""))
                case "switch_tab":
                    return self._switch_tab(
                        parameters.get("title", ""),
                        int(parameters.get("index", 0)),
                    )
                case "click":
                    return self._click(parameters.get("selector", ""))
                case "fill_form":
                    return self._fill_form(
                        parameters.get("selector", ""),
                        parameters.get("value", ""),
                    )
                case "get_title":
                    return self._get_title()
                case "get_text":
                    return self._get_text(parameters.get("selector", "body"))
                case "go_back":
                    return self._go_back()
                case "close_tab":
                    return self._close_tab()
                case "close_browser":
                    return self._close_browser()
                case _:
                    return ToolResult(
                        success=False,
                        error=(
                            f"Unknown action '{action}'. Supported: open_url, new_tab, "
                            "switch_tab, click, fill_form, get_title, get_text, "
                            "go_back, close_tab, close_browser"
                        ),
                    )

    # ------------------------------------------------------------------
    # Session management (called with _lock held)

    def _ensure_session(self) -> None:
        if self._pw is None:
            self._pw = sync_playwright().start()

        if self._browser is None or not self._browser.is_connected():
            kwargs: dict = {"headless": self._headless}
            if self._exe:
                kwargs["executable_path"] = self._exe
            self._browser = self._pw.chromium.launch(**kwargs)
            self._context = self._browser.new_context()
            self._pages = []
            self._current = 0

        if not self._pages:
            page = self._context.new_page()
            self._pages.append(page)
            self._current = 0

    def _active_page(self) -> "Page":
        self._ensure_session()
        return self._pages[self._current]

    # ------------------------------------------------------------------
    # Actions

    def _open_url(self, url: str) -> ToolResult:
        if not url.strip():
            return ToolResult(success=False, error="No URL provided")
        try:
            page = self._active_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            title = page.title()
            return ToolResult(success=True, output=f"Opened: {url}  (title: {title!r})")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _new_tab(self, url: str) -> ToolResult:
        try:
            self._ensure_session()
            page = self._context.new_page()
            self._pages.append(page)
            self._current = len(self._pages) - 1
            if url.strip():
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                return ToolResult(
                    success=True,
                    output=f"New tab #{self._current}: {url}  (title: {page.title()!r})",
                )
            return ToolResult(success=True, output=f"New blank tab #{self._current}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _switch_tab(self, title: str, index: int) -> ToolResult:
        try:
            self._ensure_session()
            if title:
                for i, p in enumerate(self._pages):
                    if not p.is_closed() and title.lower() in p.title().lower():
                        self._current = i
                        p.bring_to_front()
                        return ToolResult(
                            success=True, output=f"Switched to tab {i}: {p.title()!r}"
                        )
                return ToolResult(success=False, error=f"No tab with title: {title!r}")
            if 0 <= index < len(self._pages):
                self._current = index
                self._pages[index].bring_to_front()
                return ToolResult(
                    success=True,
                    output=f"Switched to tab {index}: {self._pages[index].title()!r}",
                )
            return ToolResult(
                success=False, error=f"Tab index {index} out of range (0–{len(self._pages)-1})"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _click(self, selector: str) -> ToolResult:
        if not selector.strip():
            return ToolResult(success=False, error="No selector provided")
        try:
            page = self._active_page()
            page.click(selector, timeout=10_000)
            return ToolResult(success=True, output=f"Clicked: {selector!r}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _fill_form(self, selector: str, value: str) -> ToolResult:
        if not selector.strip():
            return ToolResult(success=False, error="No selector provided")
        try:
            page = self._active_page()
            page.fill(selector, value, timeout=10_000)
            return ToolResult(success=True, output=f"Filled {selector!r} with {value!r}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _get_title(self) -> ToolResult:
        try:
            title = self._active_page().title()
            return ToolResult(success=True, output=title)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _get_text(self, selector: str) -> ToolResult:
        try:
            page = self._active_page()
            text = page.inner_text(selector, timeout=10_000)
            return ToolResult(success=True, output=text[:2000])
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _go_back(self) -> ToolResult:
        try:
            self._active_page().go_back(wait_until="domcontentloaded", timeout=10_000)
            return ToolResult(success=True, output="Navigated back")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _close_tab(self) -> ToolResult:
        try:
            if not self._pages:
                return ToolResult(success=False, error="No tabs open")
            page = self._pages.pop(self._current)
            page.close()
            if self._pages:
                self._current = max(0, self._current - 1)
            return ToolResult(success=True, output=f"Closed tab. Open tabs: {len(self._pages)}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _close_browser(self) -> ToolResult:
        try:
            if self._browser:
                self._browser.close()
                self._browser = None
                self._context = None
                self._pages = []
                self._current = 0
            if self._pw:
                self._pw.stop()
                self._pw = None
            return ToolResult(success=True, output="Browser closed")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def __del__(self) -> None:
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
