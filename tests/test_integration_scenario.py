"""
Stage 20 — Release Candidate: full scenario integration test.

Validates the complete event pipeline end-to-end:
  speech → intent → plan → security → execute → memory

External services (Ollama, PyAudio, Whisper, Playwright) are mocked.
Real logic runs: IntentParser, Planner, SecurityValidator, ToolExecutor,
MemoryService, MemorySearch, VisionTrigger.
"""
import json
import pytest
from unittest.mock import MagicMock

from app.core.event_bus import EventBus
from app.core.state_manager import StateManager, AppState
from app.agent.intent_parser import IntentParser, EVENT_INTENT_PARSED
from app.agent.planner import Planner, EVENT_PLAN_CREATED
from app.agent.security_validator import SecurityValidator, EVENT_SECURITY_VALIDATED
from app.agent.prompt_manager import PromptManager
from app.agent.memory_search import MemorySearch
from app.tools.base_tool import BaseTool, ToolResult
from app.tools.tool_registry import ToolRegistry
from app.tools.tool_executor import ToolExecutor, EVENT_EXECUTION_COMPLETED
from app.memory.session_memory import SessionMemory
from app.memory.long_term_memory import LongTermMemory
from app.memory.memory_service import MemoryService
from app.stt.speech_pipeline import EVENT_SPEECH_RECOGNIZED
from app.vision.vision_trigger import VisionTrigger


# ------------------------------------------------------------------
# Stub tools — no real windows, no browser, no filesystem access

class _TerminalTool(BaseTool):
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    @property
    def name(self): return "terminal"

    @property
    def description(self): return "stub terminal"

    def _run(self, action: str, params: dict) -> ToolResult:
        self.calls.append((action, params))
        return ToolResult(success=True, output=f"terminal:{action}")


class _DesktopTool(BaseTool):
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    @property
    def name(self): return "desktop"

    @property
    def description(self): return "stub desktop"

    def _run(self, action: str, params: dict) -> ToolResult:
        self.calls.append((action, params))
        return ToolResult(success=True, output=f"desktop:{action}")


class _BrowserTool(BaseTool):
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    @property
    def name(self): return "browser"

    @property
    def description(self): return "stub browser"

    def _run(self, action: str, params: dict) -> ToolResult:
        self.calls.append((action, params))
        return ToolResult(success=True, output=f"browser:{action}:{params.get('url', '')}")


class _FilesystemTool(BaseTool):
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    @property
    def name(self): return "filesystem"

    @property
    def description(self): return "stub filesystem"

    def _run(self, action: str, params: dict) -> ToolResult:
        self.calls.append((action, params))
        return ToolResult(success=True, output=f"filesystem:{action}")


class _VisionTool(BaseTool):
    @property
    def name(self): return "vision"

    @property
    def description(self): return "stub vision"

    def _run(self, action: str, params: dict) -> ToolResult:
        return ToolResult(success=True, output="экран содержит браузер")


# ------------------------------------------------------------------
# Scenario harness — mirrors the event wiring in main.py

class ScenarioHarness:
    """
    Full component stack wired end-to-end.
    Inject speech via .speak(); results accumulate in .completed / .activity.
    """

    def __init__(self, llm_responses: list[str], db_path: str = ":memory:"):
        self.bus = EventBus()
        self.sm = StateManager(self.bus)

        # Mock LLM — returns responses from the provided list in order.
        # is_available=False so SecurityValidator skips the LLM phase.
        llm = MagicMock()
        llm.is_available.return_value = False
        response_iter = iter(llm_responses)
        llm.generate.side_effect = lambda *a, **kw: next(response_iter)

        prompts = PromptManager()
        self.intent_parser = IntentParser(llm, prompts)
        self.planner = Planner(llm, prompts)
        self.security_validator = SecurityValidator()  # pattern-only, no LLM

        self.terminal = _TerminalTool()
        self.desktop = _DesktopTool()
        self.browser = _BrowserTool()
        self.filesystem = _FilesystemTool()
        self.vision = _VisionTool()

        self.tool_reg = ToolRegistry()
        for t in [self.terminal, self.desktop, self.browser, self.filesystem, self.vision]:
            self.tool_reg.register(t)

        self.executor = ToolExecutor(self.tool_reg, self.bus, self.sm)

        session_mem = SessionMemory(limit=200)
        ltm = LongTermMemory(db_path)
        self.mem_service = MemoryService(session_mem, ltm, self.bus)
        self.mem_search = MemorySearch(self.mem_service)
        self.vision_trigger = VisionTrigger()

        # Collected results
        self.completed: list[dict] = []
        self.activity: list[str] = []

        self._ctx: dict = {"user_text": "", "plan": {}}
        self._wire()

    def _wire(self) -> None:
        bus = self.bus
        ctx = self._ctx

        def _on_speech(data: dict) -> None:
            text = data["text"]
            ctx["user_text"] = text
            ctx["plan"] = {}
            self.activity.append(f"speech:{text}")

            if self.mem_search.is_history_query(text):
                answer = self.mem_search.answer(text)
                self.activity.append(f"memory_answer:{answer}")
                return

            if self.vision_trigger.is_vision_query(text):
                vt = self.tool_reg.get("vision")
                r = vt.execute("describe_screen", {})
                self.activity.append(f"vision:{r.output}")
                return

            if self.vision_trigger.is_find_query(text):
                elem = self.vision_trigger.extract_element(text)
                vt = self.tool_reg.get("vision")
                r = vt.execute("find_element", {"element": elem})
                self.activity.append(f"vision_find:{r.output}")
                return

            self.sm.set_state(AppState.THINKING)
            intent = self.intent_parser.parse(text)
            bus.publish(EVENT_INTENT_PARSED, intent)

        def _on_intent(data: dict) -> None:
            self.sm.set_state(AppState.PLANNING)
            plan = self.planner.plan(data)
            bus.publish(EVENT_PLAN_CREATED, plan)

        def _on_plan(plan: dict) -> None:
            ctx["plan"] = plan
            check = self.security_validator.validate_plan(plan)
            if check.requires_confirmation:
                self.activity.append(f"blocked:{check.reason}")
                self.sm.set_state(AppState.IDLE)
                return
            bus.publish(EVENT_SECURITY_VALIDATED, plan)

        def _on_validated(plan: dict) -> None:
            self.executor.execute_plan(plan)

        def _on_completed(data: dict) -> None:
            self.completed.append(data)
            self.mem_service.save(
                user_command=ctx.get("user_text", ""),
                intent=data.get("intent", ""),
                plan=ctx.get("plan", {}),
                results=data.get("results", []),
                success=data.get("success", False),
            )

        bus.subscribe(EVENT_SPEECH_RECOGNIZED, _on_speech)
        bus.subscribe(EVENT_INTENT_PARSED, _on_intent)
        bus.subscribe(EVENT_PLAN_CREATED, _on_plan)
        bus.subscribe(EVENT_SECURITY_VALIDATED, _on_validated)
        bus.subscribe(EVENT_EXECUTION_COMPLETED, _on_completed)

    def speak(self, text: str) -> None:
        self.bus.publish(EVENT_SPEECH_RECOGNIZED, {"text": text})


# ------------------------------------------------------------------
# Helpers

def _intent(intent: str, **params) -> str:
    return json.dumps({"intent": intent, "parameters": params}, ensure_ascii=False)


def _plan(intent: str, *steps) -> str:
    return json.dumps({"intent": intent, "steps": list(steps)}, ensure_ascii=False)


def _step(tool: str, action: str, **params) -> dict:
    s: dict = {"tool": tool, "action": action}
    if params:
        s["parameters"] = params
    return s


# ------------------------------------------------------------------
# Stage 20 scenario: individual step tests

def test_step1_open_terminal(tmp_path):
    """'Брат, открой терминал.' → terminal tool вызван, память сохранена."""
    h = ScenarioHarness([
        _intent("open_terminal"),
        _plan("open_terminal", _step("terminal", "open_terminal")),
    ], db_path=str(tmp_path / "mem.db"))

    h.speak("открой терминал")

    assert len(h.completed) == 1
    assert h.completed[0]["success"] is True
    assert h.completed[0]["intent"] == "open_terminal"
    assert h.mem_service.session_count() == 1


def test_step2_type_command(tmp_path):
    """'Напиши echo Привет мир.' → команда набрана в терминале."""
    h = ScenarioHarness([
        _intent("run_command", command="echo Привет мир"),
        _plan("run_command", _step("terminal", "run_command", command="echo Привет мир")),
    ], db_path=str(tmp_path / "mem.db"))

    h.speak("напиши echo Привет мир")

    assert h.completed[0]["success"] is True
    assert h.terminal.calls[0][0] == "run_command"


def test_step3_run_command(tmp_path):
    """'Выполни.' → команда выполнена в терминале."""
    h = ScenarioHarness([
        _intent("run_command"),
        _plan("run_command", _step("terminal", "run_command")),
    ], db_path=str(tmp_path / "mem.db"))

    h.speak("выполни")

    assert h.completed[0]["success"] is True


def test_step4_memory_query(tmp_path):
    """'Что мы делали?' → ответ из памяти, LLM не вызывался."""
    h = ScenarioHarness([], db_path=str(tmp_path / "mem.db"))
    h.mem_service.save(
        user_command="открой терминал",
        intent="open_terminal",
        plan={},
        results=[],
        success=True,
    )

    h.speak("что мы делали?")

    assert any("memory_answer:" in a for a in h.activity)
    assert len(h.completed) == 0  # memory query → no tool execution


def test_step5_open_browser(tmp_path):
    """'Открой браузер и перейди на сайт.' → browser tool вызван."""
    h = ScenarioHarness([
        _intent("open_url", url="https://example.com"),
        _plan("open_url", _step("browser", "open_url", url="https://example.com")),
    ], db_path=str(tmp_path / "mem.db"))

    h.speak("открой браузер и перейди на сайт")

    assert h.completed[0]["success"] is True
    assert h.browser.calls[0][0] == "open_url"


def test_step6_vision_screen(tmp_path):
    """'Посмотри на экран.' → vision анализ, LLM не вызывался."""
    h = ScenarioHarness([], db_path=str(tmp_path / "mem.db"))

    h.speak("посмотри на экран")

    assert any("vision:" in a for a in h.activity)
    assert len(h.completed) == 0  # vision → no tool execution via chain


# ------------------------------------------------------------------
# Stage 20 acceptance: full scenario in one run

def test_full_scenario(tmp_path):
    """
    Полный сценарий Stage 20:
      открой терминал → напиши команду → выполни →
      что мы делали? → открой браузер → посмотри на экран
    """
    h = ScenarioHarness([
        # Step 1: открой терминал
        _intent("open_terminal"),
        _plan("open_terminal", _step("terminal", "open_terminal")),
        # Step 2: напиши echo Привет мир
        _intent("run_command", command="echo Привет мир"),
        _plan("run_command", _step("terminal", "run_command", command="echo Привет мир")),
        # Step 3: выполни
        _intent("run_command"),
        _plan("run_command", _step("terminal", "run_command")),
        # Step 5: открой браузер (step 4 is memory — no LLM)
        _intent("open_url", url="https://example.com"),
        _plan("open_url", _step("browser", "open_url", url="https://example.com")),
        # Step 6: посмотри на экран — no LLM
    ], db_path=str(tmp_path / "mem.db"))

    h.speak("открой терминал")           # step 1
    h.speak("напиши echo Привет мир")    # step 2
    h.speak("выполни")                   # step 3
    h.speak("что мы делали?")            # step 4 — memory query
    h.speak("открой браузер и перейди на сайт")  # step 5
    h.speak("посмотри на экран")         # step 6 — vision

    # 4 tool executions (terminal×3 + browser×1)
    assert len(h.completed) == 4
    assert all(c["success"] for c in h.completed)

    # Memory query answered without tool execution
    assert any("memory_answer:" in a for a in h.activity)

    # Vision triggered without tool execution chain
    assert any("vision:" in a for a in h.activity)

    # All 4 executions saved to memory
    assert h.mem_service.session_count() == 4

    # Memory query returns the actual history
    h.mem_service.save(
        user_command="тест",
        intent="open_terminal",
        plan={},
        results=[],
        success=True,
    )
    recent = h.mem_service.recent(10)
    assert len(recent) >= 4


# ------------------------------------------------------------------
# Security tests (acceptance criteria: dangerous commands blocked)

def test_dangerous_command_blocked(tmp_path):
    """Команда с 'rm -' блокируется до выполнения."""
    h = ScenarioHarness([
        _intent("run_command", command="rm -rf /tmp/test"),
        _plan("run_command", _step("terminal", "run_command", command="rm -rf /tmp/test")),
    ], db_path=str(tmp_path / "mem.db"))

    h.speak("удали все файлы")

    assert len(h.completed) == 0
    assert any("blocked:" in a for a in h.activity)


def test_destructive_filesystem_action_blocked(tmp_path):
    """delete_file план требует подтверждения."""
    h = ScenarioHarness([
        _intent("delete_file", path="/tmp/important.txt"),
        _plan("delete_file", _step("filesystem", "delete_file", path="/tmp/important.txt")),
    ], db_path=str(tmp_path / "mem.db"))

    h.speak("удали файл")

    assert len(h.completed) == 0
    assert any("blocked:" in a for a in h.activity)


# ------------------------------------------------------------------
# MVP acceptance criteria (AGENTS.md Section 12)

def test_mvp_open_terminal(tmp_path):
    h = ScenarioHarness([
        _intent("open_terminal"),
        _plan("open_terminal", _step("terminal", "open_terminal")),
    ], db_path=str(tmp_path / "mem.db"))
    h.speak("открой терминал")
    assert h.completed[0]["success"] is True


def test_mvp_execute_command(tmp_path):
    h = ScenarioHarness([
        _intent("run_command", command="echo test"),
        _plan("run_command", _step("terminal", "run_command", command="echo test")),
    ], db_path=str(tmp_path / "mem.db"))
    h.speak("выполни echo test")
    assert h.completed[0]["success"] is True


def test_mvp_open_browser(tmp_path):
    h = ScenarioHarness([
        _intent("open_browser"),
        _plan("open_browser", _step("desktop", "open_app", app="chromium")),
    ], db_path=str(tmp_path / "mem.db"))
    h.speak("открой браузер")
    assert h.completed[0]["success"] is True


def test_mvp_create_file(tmp_path):
    h = ScenarioHarness([
        _intent("create_file", path="/tmp/test.txt", content="привет"),
        _plan("create_file", _step("filesystem", "create_file", path="/tmp/test.txt", content="привет")),
    ], db_path=str(tmp_path / "mem.db"))
    h.speak("создай файл test.txt с текстом привет")
    assert h.completed[0]["success"] is True


def test_mvp_ask_history(tmp_path):
    h = ScenarioHarness([], db_path=str(tmp_path / "mem.db"))
    h.mem_service.save(user_command="echo test", intent="run_command",
                       plan={}, results=[], success=True)
    h.speak("что мы делали?")
    assert any("memory_answer:" in a for a in h.activity)


def test_mvp_confirmation_for_dangerous(tmp_path):
    h = ScenarioHarness([
        _intent("run_command", command="sudo reboot"),
        _plan("run_command", _step("terminal", "run_command", command="sudo reboot")),
    ], db_path=str(tmp_path / "mem.db"))
    h.speak("перезагрузи компьютер")
    assert len(h.completed) == 0
    assert any("blocked:" in a for a in h.activity)


def test_mvp_vision_analyze_screen(tmp_path):
    h = ScenarioHarness([], db_path=str(tmp_path / "mem.db"))
    h.speak("посмотри на экран")
    assert any("vision:" in a for a in h.activity)
