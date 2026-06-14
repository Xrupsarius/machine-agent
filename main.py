import json
import logging
import os
import queue
import signal
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from app.core.logger import setup_logging
from app.core.config_manager import ConfigManager
from app.core.event_bus import EventBus
from app.core.state_manager import StateManager, AppState
from app.core.service_registry import ServiceRegistry
from app.ui.main_window import MainWindow
from app.ui.activity_log_widget import EVENT_ACTIVITY_LOG
from app.ui.tray_icon import TrayIcon
from app.ui.confirmation_dialog import ConfirmationDialog
from app.stt.microphone_service import MicrophoneService
from app.stt.whisper_service import WhisperService
from app.stt.wakeword_service import WakeWordService, EVENT_WAKE_WORD_DETECTED
from app.stt.speech_pipeline import (
    SpeechPipeline, EVENT_SPEECH_RECOGNIZED, EVENT_STT_ERROR, EVENT_STT_EMPTY,
)
from app.stt.dictation_controller import DictationController
from app.ui.dictation_widget import EVENT_DICTATION_TOGGLE
from app.ui.chat_widget import EVENT_CHAT_MESSAGE
from app.agent.llm_service import LLMService, OllamaConnectionError
from app.agent.prompt_manager import PromptManager
from app.agent.intent_parser import IntentParser, EVENT_INTENT_PARSED
from app.agent.planner import Planner, EVENT_PLAN_CREATED
from app.agent.security_validator import SecurityValidator, EVENT_SECURITY_VALIDATED, EVENT_SECURITY_BLOCKED
from app.tools.tool_registry import ToolRegistry
from app.tools.tool_executor import ToolExecutor, EVENT_EXECUTION_COMPLETED
from app.tools.terminal_tool import TerminalTool
from app.tools.filesystem_tool import FilesystemTool
from app.tools.desktop_tool import DesktopTool
from app.tools.app_catalog import AppCatalog, is_app_list_query
from app.stt.command_set import CommandSet
from app.ui.language_dialog import LanguageDialog
from app.tools.accessibility_tool import AccessibilityTool
from app.tools.browser_tool import BrowserTool
from app.tools.vision_tool import VisionTool
from app.vision.vision_service import VisionService
from app.vision.vision_trigger import VisionTrigger
from app.memory.session_memory import SessionMemory
from app.memory.long_term_memory import LongTermMemory
from app.memory.memory_service import MemoryService, EVENT_MEMORY_SAVED
from app.agent.memory_search import MemorySearch


def _log(event_bus: EventBus, text: str, level: str = "info") -> None:
    event_bus.publish(EVENT_ACTIVITY_LOG, {"text": text, "level": level})


class _MainThreadDispatcher(QObject):
    dispatch = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.dispatch.connect(lambda fn: fn())


def _reset_to_idle_after(state_manager: StateManager, delay: float = 3.0) -> None:
    """Reset ERROR state to IDLE after *delay* seconds (called from any thread)."""
    def _reset():
        if state_manager.is_state(AppState.ERROR):
            state_manager.set_state(AppState.IDLE)
    threading.Timer(delay, _reset).start()


def _resolve_language(default: str = "ru", path: str = "data/settings.json") -> str:
    """Return the chosen language, asking once on first run and persisting it."""
    log = logging.getLogger(__name__)
    try:
        if os.path.exists(path):
            return json.load(open(path, encoding="utf-8")).get("language", default)
    except Exception as e:
        log.warning(f"settings load failed: {e}")
    language = LanguageDialog.choose()
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"language": language}, f)
    except Exception as e:
        log.warning(f"settings save failed: {e}")
    return language


def main() -> None:
    config = ConfigManager("config.yaml")
    setup_logging(config.get("log_level", "INFO"))

    log = logging.getLogger(__name__)
    log.info("Machine Agent starting...")

    event_bus = EventBus()
    state_manager = StateManager(event_bus)
    registry = ServiceRegistry()
    registry.register("config", config)
    registry.register("event_bus", event_bus)
    registry.register("state_manager", state_manager)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # ADR-019

    language = _resolve_language(default=config.get("language", "ru"))
    command_set = CommandSet.from_config(language)
    log.info(f"Language: {language}")

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    sigint_timer = QTimer()
    sigint_timer.timeout.connect(lambda: None)
    sigint_timer.start(200)

    ui_dispatcher = _MainThreadDispatcher()

    window = MainWindow(state_manager, event_bus)
    tray = TrayIcon(window, event_bus)
    tray.show()
    window.show()
    registry.register("window", window)
    registry.register("tray", tray)

    # STT stack
    mic = MicrophoneService(device_name=config.get("mic_device", ""))
    whisper = WhisperService(model_name=config.get("stt_model", "small"))
    wakeword = WakeWordService(
        model_dir=config.get("wakeword_models_dir", "config/wakeword_models"),
        threshold=config.get("wakeword_threshold", 0.5),
    )
    pipeline = SpeechPipeline(
        mic, whisper, state_manager, event_bus,
        silence_threshold=config.get("stt_silence_threshold", 500),
        wakeword=wakeword,
        language=language,
    )
    registry.register("mic", mic)
    registry.register("whisper", whisper)
    registry.register("wakeword", wakeword)
    registry.register("pipeline", pipeline)

    app_catalog = AppCatalog(cache_path=config.get("app_catalog_path", "data/app_catalog.json"))
    threading.Thread(target=app_catalog.load_or_scan, daemon=True, name="AppCatalogScan").start()
    registry.register("app_catalog", app_catalog)
    desktop_tool = DesktopTool(app_catalog=app_catalog)
    _command_queue: queue.Queue = queue.Queue()
    dictation = DictationController(
        mic, whisper, state_manager, event_bus,
        pause_listening=pipeline.stop,
        resume_listening=pipeline.start,
        inject_text=lambda t: desktop_tool.execute("type_text", {"text": t}),
        run_key=lambda k: desktop_tool.execute("press_key", {"key": k}),
        run_command=lambda t: _command_queue.put(t),
        command_set=command_set,
        silence_threshold=config.get("stt_silence_threshold", 500),
        chunk_seconds=config.get("dictation_chunk_seconds", 0.7),
        silence_seconds=config.get("dictation_silence_seconds", 1.0),
        max_segment_seconds=config.get("dictation_max_segment_seconds", 15.0),
        noise_factor=config.get("dictation_noise_factor", 1.4),
    )
    registry.register("dictation", dictation)

    # Agent stack
    prompts = PromptManager()
    llm = LLMService(
        model=config.get("llm_model", "qwen3:8b"),
        host=config.get("ollama_host", "http://localhost:11434"),
    )
    intent_parser = IntentParser(llm, prompts)
    planner = Planner(llm, prompts)
    security_validator = SecurityValidator(llm_service=llm, prompt_manager=prompts)
    registry.register("prompts", prompts)
    registry.register("llm", llm)
    registry.register("intent_parser", intent_parser)
    registry.register("planner", planner)
    registry.register("security_validator", security_validator)

    # Tool stack
    vision_service = VisionService(
        model=config.get("vision_model", "moondream"),
        host=config.get("ollama_host", "http://localhost:11434"),
    )
    vision_trigger = VisionTrigger()
    registry.register("vision_service", vision_service)
    registry.register("vision_trigger", vision_trigger)

    tool_registry = ToolRegistry()
    tool_registry.register(TerminalTool(timeout=config.get("terminal_timeout", 30)))
    tool_registry.register(FilesystemTool())
    tool_registry.register(desktop_tool)
    tool_registry.register(AccessibilityTool())
    tool_registry.register(BrowserTool(
        headless=config.get("browser_headless", False),
        executable_path=config.get("browser_executable", ""),
    ))
    tool_registry.register(VisionTool(vision_service))
    tool_executor = ToolExecutor(tool_registry, event_bus, state_manager)
    registry.register("tool_registry", tool_registry)
    registry.register("tool_executor", tool_executor)

    # Memory stack
    session_memory = SessionMemory(limit=config.get("memory_limit", 200))
    long_term_memory = LongTermMemory(db_path=config.get("memory_db_path", "data/memory.db"))
    memory_service = MemoryService(session_memory, long_term_memory, event_bus)
    registry.register("session_memory", session_memory)
    registry.register("long_term_memory", long_term_memory)
    registry.register("memory_service", memory_service)

    memory_search = MemorySearch(memory_service)
    registry.register("memory_search", memory_search)

    if not llm.is_available():
        log.warning("Ollama is not reachable — LLM features unavailable")
        _log(event_bus, "Предупреждение: Ollama недоступен", "warning")

    # ---- Event routing ------------------------------------------------
    # Full chain: speech → intent → plan → security → execute → memory
    # ADR-008: User Input → Intent Parser → Planner → Validator → Executor → Memory

    # Shared context carried through the async event chain.
    _ctx: dict = {"user_text": "", "plan": {}}

    _chat_history: list[dict] = []

    # Intents whose output is information the user reads (mirrored to the chat
    # panel); action intents (open/close/type…) stay in the activity log only.
    _INFORMATIONAL_INTENTS = {
        "run_command", "read_file", "list_dir", "search_files",
        "describe_screen", "find_screen_element",
    }

    def _chat(role: str, text: str) -> None:
        if text:
            event_bus.publish(EVENT_CHAT_MESSAGE, {"role": role, "text": text})

    def _chat_reply(user_text: str) -> None:
        try:
            event_bus.publish(EVENT_CHAT_MESSAGE, {"role": "user", "text": user_text})
            _chat_history.append({"role": "user", "content": user_text})
            messages = [{"role": "system", "content": prompts.get("chat")}] + _chat_history[-10:]
            answer = llm.chat(messages, think=False).strip()
            _chat_history.append({"role": "assistant", "content": answer})
            event_bus.publish(EVENT_CHAT_MESSAGE, {"role": "assistant", "text": answer})
            _log(event_bus, f"🤖 {answer}", "success")
            memory_service.save(
                user_command=user_text,
                intent="chat",
                plan={},
                results=[{"output": answer}],
                success=True,
                error="",
            )
        except OllamaConnectionError as e:
            log.error(f"LLM unavailable during chat: {e}")
            _log(event_bus, f"LLM недоступен: {e}", "error")
        finally:
            state_manager.set_state(AppState.IDLE)

    _wake_sound = "/usr/share/sounds/freedesktop/stereo/message.oga"

    def _on_wakeword(_) -> None:
        try:
            _log(event_bus, "🎤 Проснулся по wake word — говорите команду…", "success")
            if os.path.exists(_wake_sound):
                subprocess.Popen(
                    ["paplay", _wake_sound],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
        except Exception as e:
            log.error(f"_on_wakeword error: {e}", exc_info=True)

    def _on_stt_empty(_) -> None:
        _log(event_bus, "Не расслышал команду — скажите wake word и повторите", "warning")

    def _command_worker() -> None:
        while True:
            text = _command_queue.get()
            try:
                _process_command(text)
            except Exception as e:
                log.error(f"Command worker error: {e}", exc_info=True)
                _log(event_bus, f"Внутренняя ошибка: {e}", "error")
                state_manager.set_state(AppState.IDLE)
            finally:
                _command_queue.task_done()

    def _on_speech(data: dict) -> None:
        _log(event_bus, f"Вы: {data['text']}")
        _command_queue.put(data["text"])

    def _process_command(text: str) -> None:
        try:
            _ctx["user_text"] = text
            _ctx["plan"] = {}

            # "What apps do I have?" — answered from the catalog, no LLM needed.
            if is_app_list_query(text):
                names = app_catalog.app_names()
                listing = (
                    "Установленные приложения:\n" + "\n".join(f"• {n}" for n in names)
                    if names else "Каталог приложений пуст."
                )
                _log(event_bus, listing)
                _chat("user", text)
                _chat("assistant", listing)
                return

            # History queries are answered directly from memory — no LLM needed.
            if memory_search.is_history_query(text):
                answer = memory_search.answer(text)
                _log(event_bus, answer)
                _chat("user", text)
                _chat("assistant", answer)
                return

            # Vision queries: capture screen and analyze — no LLM needed. ADR-005.
            if vision_trigger.is_vision_query(text):
                _log(event_bus, "Делаю скриншот и анализирую экран...")
                vision_tool = tool_registry.get("vision")
                result = vision_tool.execute("describe_screen", {})
                if result.success:
                    _log(event_bus, f"Экран: {result.output}")
                    _chat("user", text)
                    _chat("assistant", result.output)
                else:
                    _log(event_bus, f"Ошибка анализа экрана: {result.error}", "error")
                return

            if vision_trigger.is_find_query(text):
                element = vision_trigger.extract_element(text)
                _log(event_bus, f"Ищу на экране: {element!r}...")
                vision_tool = tool_registry.get("vision")
                result = vision_tool.execute("find_element", {"element": element})
                if result.success:
                    _log(event_bus, f"Найдено: {result.output}")
                    _chat("user", text)
                    _chat("assistant", result.output)
                else:
                    _log(event_bus, f"Ошибка поиска элемента: {result.error}", "error")
                return

            state_manager.set_state(AppState.THINKING)
            try:
                intent = intent_parser.parse(text)
                event_bus.publish(EVENT_INTENT_PARSED, intent)
            except OllamaConnectionError as e:
                log.error(f"LLM unavailable during intent parsing: {e}")
                _log(event_bus, f"LLM недоступен: {e}", "error")
                state_manager.set_state(AppState.ERROR)
                _reset_to_idle_after(state_manager)
        except Exception as e:
            log.error(f"_process_command unhandled error: {e}", exc_info=True)
            _log(event_bus, f"Внутренняя ошибка: {e}", "error")
            state_manager.set_state(AppState.IDLE)

    def _on_intent(data: dict) -> None:
        try:
            intent_name = data.get("intent", "unknown")

            if intent_name in ("chat", "unknown"):
                _log(event_bus, "Это не команда — отвечаю как собеседник…")
                _chat_reply(_ctx.get("user_text", ""))
                return

            _log(event_bus, f"Намерение: {intent_name}")
            state_manager.set_state(AppState.PLANNING)
            try:
                plan = planner.plan(data)
                event_bus.publish(EVENT_PLAN_CREATED, plan)
            except OllamaConnectionError as e:
                log.error(f"LLM unavailable during planning: {e}")
                _log(event_bus, f"LLM недоступен при планировании: {e}", "error")
                state_manager.set_state(AppState.ERROR)
                _reset_to_idle_after(state_manager)
        except Exception as e:
            log.error(f"_on_intent unhandled error: {e}", exc_info=True)
            _log(event_bus, f"Внутренняя ошибка: {e}", "error")
            state_manager.set_state(AppState.IDLE)

    def _on_plan(plan: dict) -> None:
        try:
            _ctx["plan"] = plan
            steps = plan.get("steps", [])
            intent_name = plan.get("intent", "?")
            _log(event_bus, f"План [{intent_name}]: {len(steps)} шаг(ов)", "success")
            for i, step in enumerate(steps, 1):
                _log(event_bus, f"  Шаг {i}: [{step['tool']}] {step['action']}")

            # ADR-008: Validator sits between Planner and Executor
            check = security_validator.validate_plan(plan)
            if check.requires_confirmation:
                log.warning(f"Security: {check.reason}")
                _log(event_bus, f"⚠ Требуется подтверждение: {check.reason}", "warning")
                state_manager.set_state(AppState.WAITING_CONFIRMATION)
                event_bus.publish(EVENT_SECURITY_BLOCKED, {"plan": plan, "reason": check.reason})
                return

            event_bus.publish(EVENT_SECURITY_VALIDATED, plan)
        except Exception as e:
            log.error(f"_on_plan unhandled error: {e}", exc_info=True)
            _log(event_bus, f"Внутренняя ошибка при планировании: {e}", "error")
            state_manager.set_state(AppState.IDLE)

    def _on_security_validated(plan: dict) -> None:
        try:
            tool_executor.execute_plan(plan)
        except Exception as e:
            log.error(f"_on_security_validated unhandled error: {e}", exc_info=True)
            _log(event_bus, f"Ошибка выполнения: {e}", "error")
            state_manager.set_state(AppState.IDLE)

    def _on_execution_completed(data: dict) -> None:
        try:
            ok = data.get("success", False)
            intent = data.get("intent", "?")
            results = data.get("results", [])
            level = "success" if ok else "error"
            _log(event_bus, f"Выполнение '{intent}': {'OK' if ok else 'ОШИБКА'} ({len(results)} шаг(ов))", level)
            outputs = [r["output"] for r in results if r.get("output")]
            for output in outputs:
                _log(event_bus, f"  → {output[:200]}")

            if ok and intent in _INFORMATIONAL_INTENTS and outputs:
                _chat("user", _ctx.get("user_text", ""))
                _chat("assistant", "\n".join(outputs)[:3000])

            # ADR-008: Memory is the final step in the chain
            memory_service.save(
                user_command=_ctx.get("user_text", ""),
                intent=intent,
                plan=_ctx.get("plan", {}),
                results=results,
                success=ok,
                error=data.get("error", ""),
            )
        except Exception as e:
            log.error(f"_on_execution_completed unhandled error: {e}", exc_info=True)

    def _on_security_blocked(data: dict) -> None:
        plan = data.get("plan", {})
        reason = data.get("reason", "Неизвестная причина")

        def _show_dialog() -> None:
            try:
                dialog = ConfirmationDialog(reason=reason, plan=plan, parent=window)
                if dialog.exec() == ConfirmationDialog.DialogCode.Accepted:
                    _log(event_bus, "Пользователь подтвердил выполнение", "warning")
                    event_bus.publish(EVENT_SECURITY_VALIDATED, plan)
                else:
                    _log(event_bus, "Выполнение отменено пользователем", "warning")
                    state_manager.set_state(AppState.IDLE)
            except Exception as e:
                log.error(f"Confirmation dialog error: {e}", exc_info=True)
                state_manager.set_state(AppState.IDLE)

        ui_dispatcher.dispatch.emit(_show_dialog)

    def _on_stt_error(data: dict) -> None:
        error_text = data.get("error", "")
        _log(event_bus, f"STT ошибка: {error_text}", "error")
        if "Microphone unavailable" in error_text or "mic" in error_text.lower():
            _log(event_bus, "Микрофон недоступен — проверьте подключение и перезапустите", "warning")
            state_manager.set_state(AppState.IDLE)

    def _on_mute(data: dict) -> None:
        if data["muted"]:
            pipeline.stop()
        else:
            pipeline.start()

    def _on_dictation_toggle(_) -> None:
        threading.Thread(target=dictation.toggle, daemon=True, name="DictationToggle").start()

    event_bus.subscribe(EVENT_WAKE_WORD_DETECTED, _on_wakeword)
    event_bus.subscribe(EVENT_SPEECH_RECOGNIZED, _on_speech)
    event_bus.subscribe(EVENT_INTENT_PARSED, _on_intent)
    event_bus.subscribe(EVENT_PLAN_CREATED, _on_plan)
    event_bus.subscribe(EVENT_SECURITY_VALIDATED, _on_security_validated)
    event_bus.subscribe(EVENT_SECURITY_BLOCKED, _on_security_blocked)
    event_bus.subscribe(EVENT_EXECUTION_COMPLETED, _on_execution_completed)
    event_bus.subscribe(EVENT_STT_ERROR, _on_stt_error)
    event_bus.subscribe(EVENT_STT_EMPTY, _on_stt_empty)
    event_bus.subscribe("tray.mute", _on_mute)
    event_bus.subscribe(EVENT_DICTATION_TOGGLE, _on_dictation_toggle)

    def _on_app_quit() -> None:
        log.info("Shutting down gracefully...")
        if dictation.is_active:
            dictation.stop()
        pipeline.stop()
        if tool_registry.has("browser"):
            try:
                tool_registry.get("browser").execute("close_browser", {})
            except Exception as e:
                log.warning(f"Browser close error on quit: {e}")
        log.info("Shutdown complete.")

    app.aboutToQuit.connect(_on_app_quit)

    threading.Thread(target=_command_worker, daemon=True, name="CommandWorker").start()

    pipeline.start()

    log.info(f"Services: {registry.all_names()}")
    log.info("Machine Agent ready.")
    if pipeline.is_active:
        words = ", ".join(wakeword.active_models) or "нет моделей!"
        _log(event_bus, f"✅ Агент запущен. Активация по слову: {words}", "success")
    else:
        _log(event_bus, "Агент запущен, но микрофон недоступен", "warning")

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Unhandled crash: {e}", exc_info=True)
        sys.exit(1)
