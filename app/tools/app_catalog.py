import glob
import json
import logging
import os
import re
import shlex
import time
from difflib import SequenceMatcher

log = logging.getLogger(__name__)

_DESKTOP_DIRS = (
    "/usr/share/applications",
    "/usr/local/share/applications",
    os.path.expanduser("~/.local/share/applications"),
    "/var/lib/flatpak/exports/share/applications",
    os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
)

_FUZZY_THRESHOLD = 0.8


def _clean_argv(exec_line: str) -> list[str]:
    try:
        tokens = shlex.split(exec_line)
    except ValueError:
        tokens = exec_line.split()
    return [t for t in tokens if not (len(t) == 2 and t.startswith("%"))]


def _parse_desktop(path: str) -> dict | None:
    try:
        content = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return None
    if re.search(r"^NoDisplay\s*=\s*true", content, re.MULTILINE | re.IGNORECASE):
        return None
    m_type = re.search(r"^Type=(.+)$", content, re.MULTILINE)
    if m_type and m_type.group(1).strip() != "Application":
        return None
    m_name = re.search(r"^Name=(.+)$", content, re.MULTILINE)
    m_exec = re.search(r"^Exec=(.+)$", content, re.MULTILINE)
    if not m_name or not m_exec:
        return None
    argv = _clean_argv(m_exec.group(1))
    if not argv:
        return None
    keywords: list[str] = []
    m_kw = re.search(r"^Keywords=(.+)$", content, re.MULTILINE)
    if m_kw:
        keywords += [k.strip() for k in re.split(r"[;,]", m_kw.group(1)) if k.strip()]
    m_gen = re.search(r"^GenericName=(.+)$", content, re.MULTILINE)
    if m_gen:
        keywords.append(m_gen.group(1).strip())
    return {
        "name": m_name.group(1).strip(),
        "binary": os.path.basename(argv[0]),
        "argv": argv,
        "keywords": keywords,
    }


def _normalize(s: str) -> str:
    return re.sub(r"[\s\-_.]", "", s.lower())


_APP_LIST_PATTERNS = [
    r"как[иео]\w*\s+(?:у меня\s+)?(?:есть\s+)?(?:приложени|программ)",
    r"список\s+(?:приложени|программ)",
    r"(?:приложени\w*|программ\w*)\s+(?:на|в)\s+компьютер",
    r"что\s+(?:у меня\s+)?(?:есть\s+)?установлен",
    r"вывед\w*\s+(?:список\s+)?(?:приложени|программ)",
    r"list\s+(?:my\s+)?(?:apps|applications|programs)",
    r"what\s+(?:apps|applications|programs)",
    r"installed\s+(?:apps|applications|programs)",
]


def is_app_list_query(text: str) -> bool:
    """True if the user is asking which apps/programs are installed."""
    t = text.lower()
    return any(re.search(p, t) for p in _APP_LIST_PATTERNS)


def _scan_path_binaries() -> list[str]:
    bins: set[str] = set()
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d or not os.path.isdir(d):
            continue
        try:
            for name in os.listdir(d):
                full = os.path.join(d, name)
                if not os.path.isdir(full) and os.access(full, os.X_OK):
                    bins.add(name)
        except OSError:
            continue
    return sorted(bins)


class AppCatalog:
    """Scans installed desktop applications once and resolves spoken app names.

    Built at startup (from cache when fresh), so 'открой X' matches against a
    known list instead of re-scanning the disk on every command.
    """

    def __init__(self, cache_path: str = "data/app_catalog.json", max_age_hours: float = 24.0) -> None:
        self._cache_path = cache_path
        self._max_age = max_age_hours * 3600
        self._apps: list[dict] = []
        self._binaries: list[str] = []

    @property
    def apps(self) -> list[dict]:
        return list(self._apps)

    def app_names(self) -> list[str]:
        """Friendly, de-duplicated display names of installed desktop apps."""
        return sorted({a["name"] for a in self._apps if a.get("name")}, key=str.lower)

    def load_or_scan(self) -> None:
        if self._load_cache():
            log.info(f"AppCatalog: loaded {len(self._apps)} apps / {len(self._binaries)} binaries from cache")
            return
        self.refresh()

    def refresh(self) -> None:
        self._apps = self._scan()
        self._binaries = _scan_path_binaries()
        self._save_cache()
        log.info(f"AppCatalog: scanned {len(self._apps)} apps / {len(self._binaries)} binaries")

    def _scan(self) -> list[dict]:
        seen: set[str] = set()
        apps: list[dict] = []
        for d in _DESKTOP_DIRS:
            for path in sorted(glob.glob(os.path.join(d, "*.desktop"))):
                entry = _parse_desktop(path)
                if not entry or entry["binary"] in seen:
                    continue
                seen.add(entry["binary"])
                apps.append(entry)
        return apps

    def _load_cache(self) -> bool:
        try:
            if not os.path.exists(self._cache_path):
                return False
            if time.time() - os.path.getmtime(self._cache_path) > self._max_age:
                return False
            with open(self._cache_path, encoding="utf-8") as f:
                data = json.load(f)
            self._apps = data.get("apps", [])
            self._binaries = data.get("binaries", [])
            return bool(self._apps or self._binaries)
        except Exception as e:
            log.warning(f"AppCatalog: cache load failed: {e}")
            return False

    def _save_cache(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._cache_path) or ".", exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(
                    {"scanned_at": time.time(), "apps": self._apps, "binaries": self._binaries},
                    f, ensure_ascii=False, indent=2,
                )
        except Exception as e:
            log.warning(f"AppCatalog: cache save failed: {e}")

    def resolve(self, query: str) -> list[str] | None:
        """Return the launch argv for the best-matching installed app, or None."""
        q = query.strip().lower()
        if not q:
            return None
        for a in self._apps:
            if q == a["binary"].lower() or q == a["name"].lower():
                return list(a["argv"])
        for b in self._binaries:
            if q == b.lower():
                return [b]
        for a in self._apps:
            haystack = (a["name"] + " " + " ".join(a.get("keywords", []))).lower()
            if q in haystack:
                return list(a["argv"])
        qn = _normalize(q)
        best, best_score = None, 0.0
        for a in self._apps:
            score = SequenceMatcher(None, qn, _normalize(a["name"])).ratio()
            if score > best_score:
                best, best_score = a, score
        if best and best_score >= _FUZZY_THRESHOLD:
            log.info(f"AppCatalog: fuzzy '{query}' -> {best['name']} ({best_score:.2f})")
            return list(best["argv"])
        return None
