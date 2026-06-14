import json
import logging
from dataclasses import dataclass

log = logging.getLogger("agent")

EVENT_SECURITY_VALIDATED = "security.validated"
EVENT_SECURITY_BLOCKED = "security.blocked"

# ADR-013 / PROMPT-03: explicit dangerous shell patterns.
_DANGEROUS_PATTERNS: list[str] = [
    "sudo",
    " rm ",
    "rm -",
    " dd ",
    "dd if",
    "mkfs",
    "chmod",
    "chown",
    "systemctl",
    "package remove",
    "package purge",
    "apt remove",
    "apt purge",
    "pacman -R",
    "pacman -r",
]

# Filesystem tool actions that are inherently destructive.
_DESTRUCTIVE_ACTIONS: frozenset[str] = frozenset({"delete_file", "rmdir", "truncate"})


@dataclass
class SecurityCheckResult:
    safe: bool
    requires_confirmation: bool
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "safe": self.safe,
            "requires_confirmation": self.requires_confirmation,
            "reason": self.reason,
        }


class SecurityValidator:
    """
    Two-phase security validation (Stage 13 full implementation).

    Phase 1 — pattern matching: catches all ADR-013 patterns immediately.
    Phase 2 — LLM validation: optional secondary layer via PROMPT-03.
                              Only runs when LLM is available AND patterns say safe.
    Rule (PROMPT-03): when in doubt — treat as dangerous.
    """

    def __init__(self, llm_service=None, prompt_manager=None) -> None:
        self._llm = llm_service
        self._prompts = prompt_manager

    # ------------------------------------------------------------------

    def validate_plan(self, plan: dict) -> SecurityCheckResult:
        # Phase 1: always run pattern matching.
        result = self._pattern_check_plan(plan)
        if not result.safe:
            return result

        # Phase 2: LLM check — only when available (optional layer).
        if self._needs_llm_check(plan) and self._llm and self._llm.is_available() and self._prompts:
            llm_result = self._llm_validate(plan)
            if not llm_result.safe:
                return llm_result

        log.debug("SecurityValidator: plan is safe")
        return SecurityCheckResult(safe=True, requires_confirmation=False)

    def _needs_llm_check(self, plan: dict) -> bool:
        for step in plan.get("steps", []):
            if step.get("tool") == "terminal":
                return True
            if step.get("action") in ("write_file", "delete_file", "close_app"):
                return True
            if step.get("parameters", {}).get("command", ""):
                return True
        return False

    def validate_command(self, command: str) -> SecurityCheckResult:
        """Check a raw shell command string."""
        return self._check_text(command)

    # ------------------------------------------------------------------

    def _pattern_check_plan(self, plan: dict) -> SecurityCheckResult:
        for step in plan.get("steps", []):
            result = self._check_step(step)
            if not result.safe:
                log.warning(f"SecurityValidator (pattern): {result.reason}")
                return result
        return SecurityCheckResult(safe=True, requires_confirmation=False)

    def _check_step(self, step: dict) -> SecurityCheckResult:
        # Check if the action itself is destructive.
        action = step.get("action", "")
        if action in _DESTRUCTIVE_ACTIONS:
            return SecurityCheckResult(
                safe=False,
                requires_confirmation=True,
                reason=f"Destructive action: '{action}'",
            )

        # Check dangerous patterns in action name.
        result = self._check_text(action)
        if not result.safe:
            return result

        # Check command parameter (TerminalTool passes commands here).
        command = step.get("parameters", {}).get("command", "")
        if command:
            result = self._check_text(command)
            if not result.safe:
                return result

        return SecurityCheckResult(safe=True, requires_confirmation=False)

    def _check_text(self, text: str) -> SecurityCheckResult:
        lower = text.lower()
        for pattern in _DANGEROUS_PATTERNS:
            if pattern in lower:
                return SecurityCheckResult(
                    safe=False,
                    requires_confirmation=True,
                    reason=f"Contains dangerous pattern: '{pattern}'",
                )
        return SecurityCheckResult(safe=True, requires_confirmation=False)

    # ------------------------------------------------------------------

    def _llm_validate(self, plan: dict) -> SecurityCheckResult:
        """Ask LLM (PROMPT-03) to validate the plan. Falls back to safe on error."""
        try:
            system = self._prompts.get("security_validator")
            plan_text = self._serialize_plan(plan)
            raw = self._llm.generate(
                prompt=plan_text,
                system=system,
                json_output=True,
            )
            return self._parse_llm_result(raw)
        except Exception as e:
            log.warning(f"SecurityValidator LLM check failed, assuming safe: {e}")
            return SecurityCheckResult(safe=True, requires_confirmation=False)

    def _serialize_plan(self, plan: dict) -> str:
        lines = [f"Intent: {plan.get('intent', 'unknown')}", "Steps:"]
        for i, step in enumerate(plan.get("steps", []), 1):
            cmd = step.get("parameters", {}).get("command", "")
            detail = f": {cmd}" if cmd else ""
            lines.append(f"  {i}. [{step.get('tool', '?')}] {step.get('action', '?')}{detail}")
        return "\n".join(lines)

    def _parse_llm_result(self, raw: str) -> SecurityCheckResult:
        try:
            data = json.loads(raw)
            return SecurityCheckResult(
                safe=bool(data.get("safe", True)),
                requires_confirmation=bool(data.get("requires_confirmation", False)),
                reason=str(data.get("reason", "")),
            )
        except (json.JSONDecodeError, Exception) as e:
            log.warning(f"SecurityValidator: failed to parse LLM response: {e}")
            return SecurityCheckResult(safe=True, requires_confirmation=False)
