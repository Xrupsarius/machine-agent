"""
Memory search — detects history queries and answers from action log.
Works entirely without LLM (keyword-based). PROMPT-07 algorithm.
Stage 18: upgraded with time filtering, success/failure filters, count extraction.
"""
import re
from datetime import datetime, timezone

from app.memory.memory_service import MemoryService

EVENT_HISTORY_ANSWERED = "history.answered"

_HISTORY_TRIGGERS = [
    # Generic history
    "что мы делали",
    "что делали",
    "что я делал",
    "что было",
    "что происходило",
    "что делал ассистент",
    "покажи историю",
    "покажи действия",
    "покажи лог",
    "история",
    "журнал",
    "вспомни",
    # Specific tool/action recalls
    "какие команды",
    "какие файлы",
    "какие приложения",
    "какие программы",
    "что запускал",
    "что выполнял",
    "что открывал",
    "что создавал",
    "когда открывался",
    "когда запускался",
    # Time-based
    "что было сегодня",
    "что делали сегодня",
    "что было вчера",
    "что делали вчера",
    "что было час",
    "последний час",
    "последние",
    "за последние",
    "что было за",
    # Success / failure
    "что не получилось",
    "что не вышло",
    "какие ошибки",
    "что завершилось ошибкой",
    "что упало",
    "что прошло успешно",
    "что получилось",
    "успешные команды",
]

_TOOL_KEYWORDS: dict[str, list[str]] = {
    "desktop": ["приложен", "программ", "окн", "запущен"],
    "terminal": ["терминал", "команд", "выполн", "bash", "shell", "скрипт"],
    "filesystem": ["файл", "папк", "директор", "создан", "записан", "удал"],
    "browser": ["браузер", "сайт", "url", "страниц"],
    "vision": ["экран", "скриншот", "посмотр", "опис"],
}

# Time keyword → approximate hours back
_TIME_MAP = [
    (r"(\d+)\s*минут",         lambda m: int(m.group(1)) / 60),
    (r"(\d+)\s*час",           lambda m: float(m.group(1))),
    (r"полчаса",               lambda _: 0.5),
    (r"последний\s+час",       lambda _: 1.0),
    (r"последние\s+два\s+час", lambda _: 2.0),
    (r"сегодня",               None),   # handled separately via date
    (r"вчера",                 lambda _: 24.0),
    (r"за\s+сутки",            lambda _: 24.0),
]

_FAILURE_TRIGGERS = [
    "не получилось",
    "не вышло",
    "ошибки",
    "ошибка",
    "завершилось ошибкой",
    "упало",
    "failed",
    "error",
    "неудачн",
]

_SUCCESS_TRIGGERS = [
    "успешн",
    "прошло успешно",
    "получилось",
    "выполнено",
    "сделано",
]


class MemorySearch:
    """
    Detects history queries and answers directly from the action log.
    Works without LLM — keyword-based detection only.
    Stage 18 upgrade: time filtering, success/failure, count extraction.
    """

    def __init__(self, memory_service: MemoryService) -> None:
        self._memory = memory_service

    # ------------------------------------------------------------------
    # Public API

    def is_history_query(self, text: str) -> bool:
        t = text.lower().strip()
        return any(trigger in t for trigger in _HISTORY_TRIGGERS)

    def answer(self, query: str) -> str:
        q = query.lower()
        limit = self._parse_limit(q) or 10

        # 1. Failure filter
        if self._is_failure_query(q):
            records = self._memory.filter_by_success(success=False, limit=limit)
            if not records:
                return "Ошибок не найдено — все команды выполнены успешно."
            return self._format(records, title=f"Неудачные команды ({len(records)}):")

        # 2. Success filter
        if self._is_success_query(q):
            records = self._memory.filter_by_success(success=True, limit=limit)
            if not records:
                return "Успешных команд не найдено."
            return self._format(records, title=f"Успешные команды ({len(records)}):")

        # 3. "Сегодня"
        if "сегодня" in q:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            records = self._memory.search_by_date(today)
            if not records:
                return "Сегодня действий не выполнялось."
            return self._format(records, title=f"Действия сегодня ({len(records)}):")

        # 4. "Вчера"
        if "вчера" in q:
            from datetime import timedelta
            yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
            records = self._memory.search_by_date(yesterday)
            if not records:
                return "Вчера действий не выполнялось."
            return self._format(records, title=f"Действия вчера ({len(records)}):")

        # 5. Time-based ("час назад", "30 минут", etc.)
        hours = self._parse_time_hours(q)
        if hours is not None:
            records = self._memory.recent_since(hours)
            if not records:
                label = _hours_label(hours)
                return f"За последние {label} действий не выполнялось."
            return self._format(
                records,
                title=f"Действия за последние {_hours_label(hours)} ({len(records)}):",
            )

        # 6. Explicit count: "последние N команд/действий" — must come before tool filter
        #    to avoid "команд" triggering terminal keyword.
        explicit_limit = self._parse_limit(q)
        if explicit_limit is not None:
            records = self._memory.recent(explicit_limit)
            if not records:
                return "История пуста. Ещё не было выполнено ни одной команды."
            return self._format(records, title=f"Последние {explicit_limit} действий:")

        # 7. Tool keyword filter
        tool_kw = self._extract_tool_keyword(q)
        if tool_kw:
            records = self._memory.search(tool_kw)
            if not records:
                return f"Действий с инструментом '{tool_kw}' не найдено."
            return self._format(records, title=f"Действия [{tool_kw}] ({len(records)}):")

        # 8. Generic recent
        records = self._memory.recent(limit)
        if not records:
            return "История пуста. Ещё не было выполнено ни одной команды."
        return self._format(records, title=f"Последние действия ({len(records)}):")

    # ------------------------------------------------------------------
    # Internal helpers

    def _is_failure_query(self, q: str) -> bool:
        return any(t in q for t in _FAILURE_TRIGGERS)

    def _is_success_query(self, q: str) -> bool:
        return any(t in q for t in _SUCCESS_TRIGGERS)

    def _parse_time_hours(self, q: str) -> float | None:
        """Return approximate hours back if a time expression is found."""
        for pattern, calculator in _TIME_MAP:
            if calculator is None:
                continue  # "сегодня" is handled separately
            m = re.search(pattern, q)
            if m:
                return calculator(m)
        if "вчера" in q or "за сутки" in q:
            return 24.0
        return None

    def _parse_limit(self, q: str) -> int | None:
        """Extract N from 'последние N команд/действий'."""
        m = re.search(r"последни[хе]?\s+(\d+)", q)
        if m:
            return max(1, min(int(m.group(1)), 50))
        return None

    def _extract_tool_keyword(self, q: str) -> str:
        for tool, keywords in _TOOL_KEYWORDS.items():
            if any(kw in q for kw in keywords):
                return tool
        return ""

    def _format(self, records: list[dict], title: str = "") -> str:
        display = records[-10:]
        header = title or f"История действий ({len(display)} записей):"
        lines = [header]
        for r in display:
            ts = r.get("timestamp", "")[:19].replace("T", " ")
            cmd = r.get("user_command", "—")
            ok = "✓" if r.get("success") else "✗"
            result = r.get("result", "")
            line = f"  {ok} [{ts}]  {cmd}"
            if result:
                line += f"\n      → {result[:100]}"
            lines.append(line)
        return "\n".join(lines)


def _hours_label(hours: float) -> str:
    if hours < 1:
        mins = int(hours * 60)
        return f"{mins} мин."
    if hours == 1:
        return "1 час"
    if hours < 24:
        return f"{int(hours)} ч."
    return f"{int(hours // 24)} дн."
