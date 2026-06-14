import logging
import shutil
import subprocess
from collections import deque

from app.tools.base_tool import BaseTool, ToolResult

log = logging.getLogger(__name__)

try:
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi
    _ATSPI_OK = True
except Exception as _atspi_err:
    _ATSPI_OK = False
    log.warning(f"AT-SPI2 not available: {_atspi_err}")

_MAX_NODES = 500   # BFS node limit to prevent hanging on huge trees
_MAX_DEPTH = 15    # depth limit


class AccessibilityTool(BaseTool):
    """
    UI interaction via AT-SPI2 accessibility tree.
    ADR-004: Accessibility API is priority #1 for GUI control.
    ADR-007: every execution logged via BaseTool.execute().
    """

    @property
    def name(self) -> str:
        return "accessibility"

    @property
    def description(self) -> str:
        return (
            "AT-SPI2 UI interaction: find_element, click_element, "
            "type_text, get_text, list_elements, focus_element"
        )

    def _run(self, action: str, parameters: dict) -> ToolResult:
        if not _ATSPI_OK:
            return ToolResult(
                success=False,
                error="AT-SPI2 unavailable. Install: pacman -S python-gobject at-spi2-core",
            )
        match action:
            case "find_element":
                return self._find_element(
                    parameters.get("name", ""),
                    parameters.get("role", ""),
                )
            case "click_element":
                return self._click_element(
                    parameters.get("name", ""),
                    parameters.get("role", ""),
                )
            case "type_text":
                return self._type_text(
                    parameters.get("text", ""),
                    parameters.get("element_name", ""),
                )
            case "get_text":
                return self._get_text(parameters.get("name", ""))
            case "list_elements":
                return self._list_elements(parameters.get("app", ""))
            case "focus_element":
                return self._focus_element(parameters.get("name", ""))
            case _:
                return ToolResult(
                    success=False,
                    error=(
                        f"Unknown action '{action}'. Supported: find_element, "
                        "click_element, type_text, get_text, list_elements, focus_element"
                    ),
                )

    # ------------------------------------------------------------------
    # Overridable entry point — mock this in tests

    def _get_desktop(self):
        return Atspi.get_desktop(0)

    # ------------------------------------------------------------------

    def _search(self, name: str = "", role: str = "", root=None) -> list:
        """BFS search across the accessibility tree."""
        if root is None:
            root = self._get_desktop()

        results: list = []
        queue: deque = deque([(root, 0)])
        visited = 0

        while queue and visited < _MAX_NODES:
            node, depth = queue.popleft()
            visited += 1
            try:
                node_name = node.get_name() or ""
                node_role = node.get_role_name() or ""

                name_ok = not name or name.lower() in node_name.lower()
                role_ok = not role or role.lower() in node_role.lower()

                if (name or role) and name_ok and role_ok:
                    results.append(node)

                if depth < _MAX_DEPTH:
                    count = node.get_child_count()
                    for i in range(min(count, 50)):
                        child = node.get_child_at_index(i)
                        if child:
                            queue.append((child, depth + 1))
            except Exception:
                continue

        return results

    # ------------------------------------------------------------------

    def _find_element(self, name: str, role: str) -> ToolResult:
        if not name and not role:
            return ToolResult(success=False, error="Provide name or role to search")
        try:
            elements = self._search(name=name, role=role)
            if not elements:
                criteria = f"name={name!r}" if name else ""
                if role:
                    criteria += (f" role={role!r}" if criteria else f"role={role!r}")
                return ToolResult(success=False, error=f"Element not found: {criteria}")
            lines = [
                f"  {e.get_name()!r} [{e.get_role_name()}]"
                for e in elements[:10]
            ]
            return ToolResult(
                success=True,
                output=f"Found {len(elements)} element(s):\n" + "\n".join(lines),
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _click_element(self, name: str, role: str) -> ToolResult:
        if not name:
            return ToolResult(success=False, error="No element name provided")
        try:
            elements = self._search(name=name, role=role)
            if not elements:
                return ToolResult(success=False, error=f"Element not found: {name!r}")

            element = elements[0]

            # Try Action interface (click / press / activate).
            try:
                action_iface = element.get_action_iface()
                if action_iface:
                    for i in range(action_iface.get_n_actions()):
                        aname = (action_iface.get_action_name(i) or "").lower()
                        if aname in ("click", "press", "activate"):
                            if action_iface.do_action(i):
                                return ToolResult(success=True, output=f"Clicked: {name!r}")
            except Exception:
                pass

            # Fallback: grab focus via Component interface.
            try:
                comp = element.get_component_iface()
                if comp and comp.grab_focus():
                    return ToolResult(success=True, output=f"Focused: {name!r}")
            except Exception:
                pass

            return ToolResult(
                success=False, error=f"No clickable interface on element: {name!r}"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _type_text(self, text: str, element_name: str) -> ToolResult:
        if not text:
            return ToolResult(success=False, error="No text provided")
        try:
            if element_name:
                elements = self._search(name=element_name)
                if not elements:
                    return ToolResult(
                        success=False, error=f"Element not found: {element_name!r}"
                    )
                element = elements[0]
                try:
                    comp = element.get_component_iface()
                    if comp:
                        comp.grab_focus()
                except Exception:
                    pass
                try:
                    et = element.get_editable_text_iface()
                    if et and et.insert_text(0, text, len(text)):
                        return ToolResult(
                            success=True,
                            output=f"Typed into {element_name!r}: {text!r}",
                        )
                except Exception:
                    pass

            # Fallback: xdotool type.
            if shutil.which("xdotool"):
                proc = subprocess.run(
                    ["xdotool", "type", "--clearmodifiers", text],
                    capture_output=True, text=True,
                )
                if proc.returncode == 0:
                    return ToolResult(success=True, output=f"Typed: {text!r}")
                return ToolResult(success=False, error=proc.stderr.strip())

            return ToolResult(
                success=False,
                error="type_text requires a target element with EditableText or xdotool",
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _get_text(self, name: str) -> ToolResult:
        if not name:
            return ToolResult(success=False, error="No element name provided")
        try:
            elements = self._search(name=name)
            if not elements:
                return ToolResult(success=False, error=f"Element not found: {name!r}")

            element = elements[0]
            try:
                text_iface = element.get_text_iface()
                if text_iface:
                    count = text_iface.get_character_count()
                    return ToolResult(
                        success=True, output=text_iface.get_text(0, count)
                    )
            except Exception:
                pass

            elem_name = element.get_name() or ""
            if elem_name:
                return ToolResult(success=True, output=elem_name)

            return ToolResult(
                success=False, error=f"No text interface on element: {name!r}"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _list_elements(self, app: str) -> ToolResult:
        try:
            desktop = self._get_desktop()
            lines: list[str] = []

            for i in range(desktop.get_child_count()):
                app_node = desktop.get_child_at_index(i)
                if not app_node:
                    continue
                app_name = app_node.get_name() or ""
                if app and app.lower() not in app_name.lower():
                    continue

                lines.append(f"[App] {app_name}")
                for j in range(min(app_node.get_child_count(), 5)):
                    win = app_node.get_child_at_index(j)
                    if not win:
                        continue
                    win_name = win.get_name() or ""
                    lines.append(f"  [Window] {win_name}")
                    for k in range(min(win.get_child_count(), 30)):
                        child = win.get_child_at_index(k)
                        if not child:
                            continue
                        c_name = child.get_name() or ""
                        c_role = child.get_role_name() or ""
                        if c_name or c_role:
                            lines.append(f"    [{c_role}] {c_name}")

            if not lines:
                return ToolResult(success=True, output="(no accessible applications found)")
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _focus_element(self, name: str) -> ToolResult:
        if not name:
            return ToolResult(success=False, error="No element name provided")
        try:
            elements = self._search(name=name)
            if not elements:
                return ToolResult(success=False, error=f"Element not found: {name!r}")

            element = elements[0]
            try:
                comp = element.get_component_iface()
                if comp and comp.grab_focus():
                    return ToolResult(success=True, output=f"Focused: {name!r}")
            except Exception:
                pass

            return ToolResult(success=False, error=f"Cannot focus element: {name!r}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
