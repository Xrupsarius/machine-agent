import logging
import re
from difflib import SequenceMatcher

import yaml

log = logging.getLogger(__name__)

_MARKER_THRESHOLD = 0.7
_COMMAND_THRESHOLD = 0.72
_LOCAL_NAMES = ("submit", "newline", "delete_word", "stop")

_FALLBACK = {
    "ru": {
        "marker": ["омнис", "омнес", "амнис", "онис", "омнус", "omnis", "omni", "omnes"],
        "submit": ["отправь", "отправить", "отправляй", "энтер"],
        "newline": ["новая строка", "с новой строки", "перенос", "новую строку"],
        "delete_word": ["сотри", "сатри", "удали", "стереть", "удалить"],
        "stop": ["стоп", "стой", "хватит", "закончи", "останови", "заверши", "отключи", "выключи", "выйди", "stop"],
        "dictation": ["начни диктов", "включи диктов", "режим диктов", "диктовку", "диктовка", "диктуй", "надиктую"],
    },
    "en": {
        "marker": ["omnis", "omni", "omnes", "omniss"],
        "submit": ["send", "submit", "enter", "post"],
        "newline": ["new line", "newline", "line break", "next line"],
        "delete_word": ["delete", "erase", "backspace", "remove"],
        "stop": ["stop", "halt", "finish", "end"],
        "dictation": ["start dictation", "dictation mode", "begin dictation", "dictate"],
    },
}


def _norm(s: str) -> str:
    return re.sub(r"[^\w]+", "", s.lower())


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


class CommandSet:
    """Language-specific dictation command vocabulary with fuzzy matching.

    Phrases come from config/commands.yaml (or a built-in fallback). Matching
    tolerates STT mistakes so «омни с»/«омнись»/«обнес» still hit the marker.
    """

    def __init__(
        self,
        markers: list[str],
        commands: dict[str, list[str]],
        language: str = "ru",
        dictation: list[str] | None = None,
    ) -> None:
        self.language = language
        self._markers = [_norm(m) for m in markers if m.strip()]
        self._commands = {
            name: [s.lower().strip() for s in commands.get(name, []) if s.strip()]
            for name in _LOCAL_NAMES
        }
        self._dictation = [s.lower().strip() for s in (dictation or []) if s.strip()]

    @classmethod
    def from_config(cls, language: str, path: str = "config/commands.yaml") -> "CommandSet":
        lang = {}
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            lang = data.get(language) or {}
        except Exception as e:
            log.warning(f"CommandSet: config load failed ({e}) — using built-in")
        if not lang:
            lang = _FALLBACK.get(language, _FALLBACK["ru"])
        commands = {name: lang.get(name, []) for name in _LOCAL_NAMES}
        return cls(lang.get("marker", []), commands, language, lang.get("dictation", []))

    def is_dictation_start(self, text: str) -> bool:
        """True if a wake-word command asks to switch into dictation mode."""
        t = text.lower()
        return any(phrase in t for phrase in self._dictation)

    def parse(self, text: str) -> tuple[str, str | None, str | None]:
        """Split a finalized segment into (text_to_type, local_command, agent_command)."""
        words = text.split()
        if not words:
            return text, None, None
        idx, consumed = self._find_marker(words)
        if idx is None:
            return text, None, None
        body = " ".join(words[:idx]).strip(" ,.!?;:—-")
        rest_words = words[idx + consumed:]
        local = self._match_local(rest_words)
        if local:
            return body, local, None
        rest = " ".join(rest_words).strip(" ,.!?;:—-")
        if rest:
            return body, None, rest
        return body, None, None

    def _find_marker(self, words: list[str]) -> tuple[int | None, int]:
        for i, word in enumerate(words):
            r1 = self._best_ratio(_norm(word))
            if r1 < _MARKER_THRESHOLD:
                continue
            consumed = 1
            if i + 1 < len(words):
                r2 = self._best_ratio(_norm(word) + _norm(words[i + 1]))
                r_next = self._best_ratio(_norm(words[i + 1]))
                if r2 > r1 and r2 >= r_next:
                    consumed = 2
            return i, consumed
        return None, 0

    def _best_ratio(self, candidate: str) -> float:
        if not candidate:
            return 0.0
        return max((_ratio(candidate, m) for m in self._markers), default=0.0)

    def _match_local(self, rest_words: list[str]) -> str | None:
        if not rest_words:
            return None
        norm_words = [_norm(w) for w in rest_words]
        best_name, best_score = None, 0.0
        for name, synonyms in self._commands.items():
            for syn in synonyms:
                span = len(syn.split())
                candidate = "".join(norm_words[:span])
                score = _ratio(candidate, _norm(syn))
                if score > best_score:
                    best_name, best_score = name, score
        return best_name if best_score >= _COMMAND_THRESHOLD else None
