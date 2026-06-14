import json
import logging

from app.agent.llm_service import LLMService, OllamaConnectionError
from app.agent.plan_validator import PlanValidator, PlanValidationError
from app.agent.prompt_manager import PromptManager

log = logging.getLogger("agent")

EVENT_PLAN_CREATED = "plan.created"

_TEMPLATES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "open_terminal": ("desktop", "open_terminal", ()),
    "run_command": ("terminal", "run_command", ("command",)),
    "create_file": ("filesystem", "create_file", ("path",)),
    "read_file": ("filesystem", "read_file", ("path",)),
    "write_file": ("filesystem", "write_file", ("path",)),
    "delete_file": ("filesystem", "delete_file", ("path",)),
    "list_dir": ("filesystem", "list_dir", ("path",)),
    "search_files": ("filesystem", "search_files", ("path", "pattern")),
    "open_app": ("desktop", "open_app", ("app",)),
    "close_app": ("desktop", "close_app", ("app",)),
    "close_active_window": ("desktop", "close_active_window", ()),
    "switch_window": ("desktop", "switch_window", ("title",)),
    "open_url": ("browser", "open_url", ("url",)),
    "click_element": ("browser", "click", ("selector",)),
    "fill_form": ("browser", "fill_form", ("selector",)),
    "describe_screen": ("vision", "describe_screen", ()),
    "find_screen_element": ("vision", "find_element", ("element",)),
    "type_text": ("desktop", "type_text", ("text",)),
}


class Planner:
    def __init__(self, llm: LLMService, prompts: PromptManager) -> None:
        self._llm = llm
        self._system = prompts.get("planner")
        self._validator = PlanValidator()

    def plan(self, intent: dict) -> dict:
        """
        Takes: {"intent": str, "parameters": dict}
        Returns: {"intent": str, "steps": [{"tool": str, "action": str, ...}]}
        Raises OllamaConnectionError if LLM is unreachable.
        Returns a zero-step plan on JSON / validation error.
        """
        log.debug(f"Planning for intent: {intent}")

        template_plan = self._from_template(intent)
        if template_plan is not None:
            log.info(f"Plan created (template): {template_plan}")
            return template_plan

        raw = self._llm.generate(
            prompt=json.dumps(intent, ensure_ascii=False),
            system=self._system,
            json_output=True,
            think=False,
        )

        try:
            plan = json.loads(raw)
            self._validator.validate(plan)
            # PROMPT-02: 'intent' field is mandatory (required by Memory Writer)
            plan.setdefault("intent", intent.get("intent", "unknown"))
            log.info(f"Plan created: {plan}")
            return plan
        except (json.JSONDecodeError, PlanValidationError, ValueError) as e:
            log.warning(f"Planner: bad LLM response ({e}). Raw: '{raw[:200]}'")
            return {"intent": intent.get("intent", "unknown"), "steps": []}

    def _from_template(self, intent: dict) -> dict | None:
        name = intent.get("intent", "")
        params = intent.get("parameters", {}) or {}

        if name == "open_browser":
            return {
                "intent": "open_browser",
                "steps": [{"tool": "desktop", "action": "open_app",
                           "parameters": {"app": "chromium"}}],
            }

        if name not in _TEMPLATES:
            return None
        tool, action, required = _TEMPLATES[name]
        if any(not str(params.get(key, "")).strip() for key in required):
            return None
        step: dict = {"tool": tool, "action": action}
        if params:
            step["parameters"] = params
        return {"intent": name, "steps": [step]}
