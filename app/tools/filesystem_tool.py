import logging
from pathlib import Path

from app.tools.base_tool import BaseTool, ToolResult

log = logging.getLogger(__name__)


class FilesystemTool(BaseTool):
    """
    File and directory operations.
    ADR-007: every execution logged via BaseTool.execute().
    """

    @property
    def name(self) -> str:
        return "filesystem"

    @property
    def description(self) -> str:
        return (
            "File operations: create_file, read_file, write_file, "
            "append_file, delete_file, list_dir, search_files"
        )

    def _run(self, action: str, parameters: dict) -> ToolResult:
        match action:
            case "create_file":
                return self._create_file(
                    parameters.get("path", ""),
                    parameters.get("content", ""),
                )
            case "read_file":
                return self._read_file(parameters.get("path", ""))
            case "write_file":
                return self._write_file(
                    parameters.get("path", ""),
                    parameters.get("content", ""),
                )
            case "append_file":
                return self._append_file(
                    parameters.get("path", ""),
                    parameters.get("content", ""),
                )
            case "delete_file":
                return self._delete_file(parameters.get("path", ""))
            case "list_dir":
                return self._list_dir(parameters.get("path", "."))
            case "search_files":
                return self._search_files(
                    parameters.get("path", "."),
                    parameters.get("pattern", "*"),
                )
            case _:
                return ToolResult(
                    success=False,
                    error=(
                        f"Unknown action '{action}'. Supported: create_file, read_file, "
                        "write_file, append_file, delete_file, list_dir, search_files"
                    ),
                )

    # ------------------------------------------------------------------

    def _create_file(self, path: str, content: str) -> ToolResult:
        if not path.strip():
            return ToolResult(success=False, error="No path provided")
        p = Path(path)
        if p.exists():
            return ToolResult(success=False, error=f"File already exists: {path}")
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return ToolResult(success=True, output=f"Created: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _read_file(self, path: str) -> ToolResult:
        if not path.strip():
            return ToolResult(success=False, error="No path provided")
        p = Path(path)
        if not p.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        if not p.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")
        try:
            return ToolResult(success=True, output=p.read_text(encoding="utf-8"))
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _write_file(self, path: str, content: str) -> ToolResult:
        if not path.strip():
            return ToolResult(success=False, error="No path provided")
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return ToolResult(success=True, output=f"Written: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _append_file(self, path: str, content: str) -> ToolResult:
        if not path.strip():
            return ToolResult(success=False, error="No path provided")
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(success=True, output=f"Appended to: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _delete_file(self, path: str) -> ToolResult:
        if not path.strip():
            return ToolResult(success=False, error="No path provided")
        p = Path(path)
        if not p.exists():
            return ToolResult(success=False, error=f"File not found: {path}")
        if not p.is_file():
            return ToolResult(success=False, error=f"Not a file: {path}")
        try:
            p.unlink()
            return ToolResult(success=True, output=f"Deleted: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _list_dir(self, path: str) -> ToolResult:
        p = Path(path)
        if not p.exists():
            return ToolResult(success=False, error=f"Path not found: {path}")
        if not p.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {path}")
        try:
            entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name))
            if not entries:
                return ToolResult(success=True, output="(empty)")
            lines = [f"{'  ' if e.is_file() else 'D '}{e.name}" for e in entries]
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _search_files(self, path: str, pattern: str) -> ToolResult:
        p = Path(path)
        if not p.exists():
            return ToolResult(success=False, error=f"Path not found: {path}")
        try:
            matches = sorted(str(f) for f in p.rglob(pattern) if f.is_file())
            if not matches:
                return ToolResult(
                    success=True,
                    output=f"No files found matching '{pattern}' in {path}",
                )
            return ToolResult(success=True, output="\n".join(matches))
        except Exception as e:
            return ToolResult(success=False, error=str(e))
