import json
import logging
import re

from app.agent.llm_service import LLMService, OllamaConnectionError
from app.agent.prompt_manager import PromptManager

log = logging.getLogger("agent")

EVENT_INTENT_PARSED = "intent.parsed"

_FALLBACK = {"intent": "unknown", "parameters": {}}

_TYPE_TEXT_RULE = re.compile(
    r"^(?:напиши(?:сь)?[\s,]+(?:здесь|тут)|напечатай|набери|введи)"
    r"[\s.,:—-]*(?:следующее)?[\s.,:—-]*(.+)$",
    re.IGNORECASE | re.DOTALL,
)


class IntentParser:
    def __init__(self, llm: LLMService, prompts: PromptManager) -> None:
        self._llm = llm
        self._system = prompts.get("intent_parser")

    def parse(self, user_text: str) -> dict:
        """
        Returns {"intent": str, "parameters": dict}.
        Raises OllamaConnectionError if LLM is unreachable.
        Falls back to {"intent": "unknown", ...} on JSON parse error.
        """
        log.debug(f"Parsing intent for: '{user_text}'")

        match = _TYPE_TEXT_RULE.match(user_text.strip())
        if match and match.group(1).strip():
            result = {"intent": "type_text", "parameters": {"text": match.group(1).strip()}}
            log.info(f"Intent parsed (rule): {result}")
            return result

        raw = self._llm.generate(
            prompt=user_text,
            system=self._system,
            json_output=True,
            think=False,
        )

        try:
            data = json.loads(raw)
            result = self._validate(data)
            log.info(f"Intent parsed: {result}")
            return result
        except (json.JSONDecodeError, ValueError) as e:
            log.warning(f"IntentParser: bad LLM response ({e}). Raw: '{raw[:200]}'")
            return dict(_FALLBACK)

    def _validate(self, data: dict) -> dict:
        if not isinstance(data, dict):
            raise ValueError("Response is not a JSON object")
        if "intent" not in data:
            raise ValueError("Missing 'intent' field")
        if not isinstance(data["intent"], str) or not data["intent"].strip():
            raise ValueError("'intent' must be a non-empty string")
        return {
            "intent": data["intent"].strip(),
            "parameters": data.get("parameters", {}),
        }
