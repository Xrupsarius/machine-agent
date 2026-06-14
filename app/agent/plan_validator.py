VALID_TOOLS = frozenset({
    "terminal", "filesystem", "desktop",
    "browser", "accessibility", "vision", "memory",
})


class PlanValidationError(Exception):
    pass


class PlanValidator:
    """Validates plan structure (not security — that is Stage 13 SecurityValidator)."""

    def validate(self, plan: dict) -> None:
        """Raise PlanValidationError if plan structure is invalid."""
        if not isinstance(plan, dict):
            raise PlanValidationError("Plan must be a JSON object")
        if "steps" not in plan:
            raise PlanValidationError("Plan missing required field 'steps'")
        if not isinstance(plan["steps"], list):
            raise PlanValidationError("'steps' must be a list")
        for i, step in enumerate(plan["steps"]):
            self._validate_step(step, i)

    def _validate_step(self, step: dict, index: int) -> None:
        if not isinstance(step, dict):
            raise PlanValidationError(f"Step {index} must be a JSON object")
        if "tool" not in step:
            raise PlanValidationError(f"Step {index}: missing 'tool'")
        if "action" not in step:
            raise PlanValidationError(f"Step {index}: missing 'action'")
        if step["tool"] not in VALID_TOOLS:
            raise PlanValidationError(
                f"Step {index}: unknown tool '{step['tool']}'. "
                f"Valid tools: {sorted(VALID_TOOLS)}"
            )
        if not isinstance(step["action"], str) or not step["action"].strip():
            raise PlanValidationError(f"Step {index}: 'action' must be a non-empty string")

    def is_valid(self, plan: dict) -> tuple[bool, str | None]:
        """Return (True, None) or (False, error_message)."""
        try:
            self.validate(plan)
            return True, None
        except PlanValidationError as e:
            return False, str(e)
