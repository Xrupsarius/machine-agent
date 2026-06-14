# AGENTS.md
# Local Voice Computer Assistant
# Master document for Claude Code

---

## DOCUMENT STATUS

This is the single source of truth for Claude Code.

If there is a conflict between this document and any other file in the project — this document takes priority.

All architectural decisions, development rules, system prompts, and roadmap are consolidated here.

---

## SECTION 1. PROJECT GOAL

Build a fully local voice assistant for Linux.

**This is not a chatbot. This is a local voice operating agent.**

The assistant must:
- continuously listen to the user
- understand voice commands in Russian
- control the computer: open programs, manage files, operate the terminal
- type text and click buttons
- read screen content
- store the full history of all actions
- work without cloud services and without external APIs

**All models run locally on the user's machine.**

---

## SECTION 2. TECHNOLOGY STACK

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| UI | PySide6 |
| STT | Faster-Whisper (model: small or medium) |
| Wake Word | OpenWakeWord |
| LLM | Ollama + qwen3:8b |
| Vision | Moondream (on demand only) |
| Database | SQLite |
| Configuration | config.yaml |

**Fallback LLM models:** qwen3:4b, llama3.1:8b, gemma3:4b

---

## SECTION 3. ARCHITECTURAL DECISIONS (ADR)

### ADR-001 — Project is fully local
Forbidden: OpenAI API, Anthropic API, Gemini API, any cloud LLM.
No external APIs without explicit user confirmation.

### ADR-002 — LLM via Ollama
All LLM calls go through `LLMService` only.
Direct Ollama calls from other modules are forbidden.

### ADR-003 — STT via Faster-Whisper
STT is implemented as an isolated service.
Replacing STT must be possible without changing other modules.

### ADR-004 — GUI control via Accessibility
Priority order for GUI interaction:
1. Accessibility API
2. Native API
3. MCP Desktop
4. Vision
5. Mouse coordinates (last resort only)

### ADR-005 — Vision on demand only
Vision is triggered only if:
- user explicitly said "look at the screen"
- element not found by other methods
- image analysis is required

Continuous screen analysis is forbidden.

### ADR-006 — Memory stored locally
- Session Memory: in process memory (200 records)
- Long-Term Memory: SQLite
- External databases for MVP are forbidden

### ADR-007 — Every action is logged
Every action is written to the log.
Skipping logging is considered an implementation error. No silent failures.

### ADR-008 — Commands execute only through a plan
Direct execution of raw LLM output is forbidden.
The only allowed chain:
```
User Input → Intent Parser → Planner → Validator → Executor → Memory
```

### ADR-009 — Tool-Based Architecture
Every action is implemented through a Tool.
Executing system actions directly from Agent is forbidden.

### ADR-010 — MCP is an additional integration layer
The application must work without MCP. MCP is not required for MVP.

### ADR-011 — UI built on PySide6
Migration to Electron is forbidden without a strong reason.

### ADR-012 — SQLite as primary storage
PostgreSQL is forbidden in MVP.

### ADR-013 — Dangerous commands require confirmation
Dangerous patterns: `sudo`, `rm`, `dd`, `mkfs`, `chmod`, `chown`, `systemctl`, `package remove`, `package purge`.
Execution without user confirmation is impossible.

### ADR-014 — All settings stored in config.yaml
Hardcoding is forbidden: models, paths, timeouts, confidence thresholds, wake words.

### ADR-015 — MVP first, improvements later
Before MVP is complete, the following are forbidden:
- vector databases (`vector_memory.py` is marked **post-MVP**)
- distributed systems
- microservices
- multi-user mode
- clustering

### ADR-016 — Modular architecture
All components must have interfaces and be interchangeable.

### ADR-017 — Primary quality criterion is reliability
```
Reliability > Performance
Simplicity > Complexity
Working solution > Perfect solution
```

### ADR-018 — Memory System is mandatory
Removing memory is forbidden. This is not an optional component.

### ADR-019 — Closing the window does not terminate the process
The close button hides the window but does not terminate the process.
Full termination only via system tray menu.

### ADR-020 — Final principle
This is a local voice operating agent, not a chatbot.
All architectural decisions are made from this perspective.

---

## SECTION 4. DEVELOPMENT RULES

### Core principle
Simple solution first. Improvements later.
Never build a complex system in advance for a hypothetical future.

### Forbidden actions
- writing monolithic code
- creating God Objects
- mixing UI and business logic
- mixing memory and tools
- mixing STT and Agent
- creating circular dependencies
- hardcoding paths, models, system commands

### Rule: changing existing code
Before modifying existing code:
1. Read related files
2. Find all usages
3. Check impact of changes
4. Only then modify

Never rewrite large parts of the project without necessity.

### Rule: implementing a new feature
1. Interface
2. Implementation
3. Tests
4. Integration

### Rule: commits
Every stage must be fully complete.

❌ Bad: "Added half of memory"
✅ Good: "Session Memory fully implemented"

### Rule: memory
Every user action is saved. Minimum fields: timestamp, command, intent, plan, result.
Memory cannot be deferred to the final stage.

### Rule: tools
Every tool is independent. Communication only through Coordinator.
- Terminal Tool has no knowledge of Browser Tool
- Browser Tool has no knowledge of Memory
- Memory has no knowledge of UI

### Rule: security
Any potentially dangerous operation requires confirmation.
When in doubt — treat the action as dangerous.

### Rule: terminal
```
LLM → Plan → Validation → Execution
```
Direct execution of LLM response text is forbidden.

### Rule: Vision
Vision is an expensive resource. Trigger only when necessary (see ADR-005).

### Rule: configuration
Every setting lives in config.yaml. No exceptions.

### Rule: dependencies
Before adding a new library, verify:
1. Can the task be solved with existing tools
2. How well the library is maintained
3. Dependency size
4. License

### Rule: tests
Mandatory test coverage: memory, planner, tools, security, command parser.

### Definition of Done
A task is complete only if:
- [ ] Code written
- [ ] Tests written
- [ ] Tests passing
- [ ] Logging implemented
- [ ] Documentation updated

---

## SECTION 5. PROJECT STRUCTURE

```
project/
├── main.py
├── config.yaml
├── requirements.txt
├── pyproject.toml
├── README.md
├── app/
│   ├── core/
│   │   ├── event_bus.py
│   │   ├── state_manager.py
│   │   └── service_registry.py
│   ├── stt/
│   │   ├── microphone_service.py
│   │   ├── wakeword_service.py
│   │   ├── whisper_service.py
│   │   └── speech_pipeline.py
│   ├── agent/
│   │   ├── llm_service.py
│   │   ├── planner.py
│   │   ├── intent_parser.py
│   │   └── execution_coordinator.py
│   ├── tools/
│   │   ├── base_tool.py
│   │   ├── tool_registry.py
│   │   ├── terminal_tool.py
│   │   ├── filesystem_tool.py
│   │   ├── desktop_tool.py
│   │   ├── accessibility_tool.py
│   │   └── browser_tool.py
│   ├── memory/
│   │   ├── memory_service.py
│   │   ├── session_memory.py
│   │   └── long_term_memory.py
│   │   # vector_memory.py — implement AFTER MVP (see ADR-015)
│   ├── mcp/
│   │   ├── base_mcp_adapter.py
│   │   ├── filesystem_mcp_adapter.py
│   │   ├── terminal_mcp_adapter.py
│   │   ├── browser_mcp_adapter.py
│   │   └── desktop_mcp_adapter.py
│   ├── vision/
│   │   ├── screen_capture.py
│   │   ├── vision_service.py
│   │   └── ui_analyzer.py
│   └── ui/
│       ├── main_window.py
│       ├── tray_icon.py
│       ├── status_widget.py
│       └── activity_log_widget.py
├── config/
├── logs/
│   ├── system.log
│   ├── agent.log
│   ├── errors.log
│   └── actions.log
├── database/
└── tests/
```

---

## SECTION 6. EXECUTION FLOW

```
User speaks a phrase
        ↓
WakeWord detected
        ↓
STT transcribes speech → text
        ↓
Intent Parser → { "intent": "...", "parameters": {} }
        ↓
Planner → { "intent": "...", "steps": [...] }
        ↓
Security Validator → { "safe": true/false, "requires_confirmation": true/false }
        ↓
  [if requires_confirmation] → prompt user → wait for response
        ↓
Tool Executor → calls the appropriate Tool
        ↓
Memory Writer → saves to Session Memory + SQLite
        ↓
UI updates → status + activity log
```

**Important:** SecurityValidator must be created as a stub at the Terminal Tool stage (roadmap stage 8), not waiting until stage 13.

---

## SECTION 7. DATABASE SCHEMA

```sql
CREATE TABLE actions (
    id               INTEGER PRIMARY KEY,
    timestamp        TEXT NOT NULL,
    user_command     TEXT NOT NULL,
    intent           TEXT NOT NULL,
    plan             TEXT NOT NULL,
    executed_actions TEXT,
    result           TEXT,
    success          INTEGER NOT NULL DEFAULT 0,
    error            TEXT
);
```

### Session Memory
- Stored in process memory
- Maximum 200 records
- Evict oldest records when limit is exceeded

### Memory Search Algorithm
1. Search Session Memory first
2. If no result — search SQLite
3. Return summary to user

---

## SECTION 8. CONFIGURATION (config.yaml)

```yaml
stt_model: medium
llm_model: qwen3:8b
vision_model: moondream
wake_words:
  - брат
  - ассистент
  - компьютер
memory_limit: 200
confirmation_required: true
ollama_host: http://localhost:11434
log_level: INFO
```

---

## SECTION 9. UI STATUSES

| Status | Description |
|--------|-------------|
| IDLE | Waiting for wake word |
| LISTENING | Recording speech |
| THINKING | LLM processing |
| PLANNING | Planner building plan |
| EXECUTING | Tool executing action |
| WAITING_CONFIRMATION | Awaiting dangerous action confirmation |
| ERROR | Error state |

### System Tray Menu Items
- Open
- Mute / Unmute
- Show Logs
- Quit

---

## SECTION 10. SYSTEM PROMPTS

### PROMPT-01: Intent Parser
```
Role: user intent classification module.
Task: understand intent, extract parameters.
Forbidden: execute actions, build plans.

Input: user text.

Output (JSON only):
{
  "intent": "open_terminal",
  "parameters": {}
}

Rules: no explanations, no extra text, JSON only.
```

### PROMPT-02: Planner
```
Role: action planner.
Task: create a safe step-by-step plan.
Forbidden: execute actions, call tools.

Input:
{
  "intent": "open_terminal",
  "parameters": {}
}

Output (JSON only):
{
  "intent": "open_terminal",
  "steps": [
    {
      "tool": "desktop",
      "action": "open_terminal"
    }
  ]
}

Rules: plan must be minimal, clear, verifiable.
The "intent" field is mandatory in output JSON — required by Memory Writer.
```

### PROMPT-03: Security Validator
```
Role: security check system.
Input: action plan.

Dangerous patterns: sudo, rm, dd, mkfs, chmod, chown,
systemctl, package remove, package purge.

Output (JSON only):
{
  "safe": false,
  "requires_confirmation": true,
  "reason": "Contains sudo command"
}

Rules: when in doubt — treat as dangerous.
```

### PROMPT-04: Tool Selector
```
Role: select the correct tool for a plan step.

Available tools: terminal, filesystem, desktop,
browser, accessibility, vision, memory.

Output (JSON only):
{
  "tool": "filesystem"
}

If multiple tools needed — return a list.
```

### PROMPT-05: Tool Executor
```
Role: tool orchestration.
Task: receive plan, call tools, collect result.

Rules:
- do not modify the plan
- do not invent new steps
- do not execute steps outside the plan
- if plan is invalid — stop execution
```

### PROMPT-06: Memory Writer
```
Role: save action history.

Input: user command + plan + result.

Record format (all fields required):
{
  "timestamp": "ISO8601",
  "user_command": "command text",
  "intent": "classified intent",
  "plan": "serialized plan",
  "result": "execution result",
  "success": true
}

Rules: every action is saved, nothing is skipped.
```

### PROMPT-07: Memory Search
```
Role: search action history.

Example queries (in Russian from user):
- "Что мы делали?" (What did we do?)
- "Что было в терминале?" (What happened in terminal?)
- "Какие команды запускались?" (What commands were run?)
- "Когда открывался браузер?" (When was browser opened?)

Algorithm:
1. Search Session Memory
2. If no result — search SQLite
3. Return brief description of found events
```

### PROMPT-08: Desktop Agent
```
Role: application and window management.
Capabilities: open/close app, switch window, find window.

Priority:
1. Accessibility
2. Native APIs
3. MCP Desktop

Forbidden: use Vision without necessity.
```

### PROMPT-09: Accessibility Agent
```
Role: application interface interaction.
Capabilities: find buttons, input fields, menus, tabs.

Rules:
- use Accessibility Tree
- do not use mouse coordinates without extreme necessity
```

### PROMPT-10: Vision Agent
```
Role: screen analysis.

Trigger only if:
- user said "look at the screen"
- element not found by other methods
- application is unknown

Input: screenshot.
Output: structured interface description.
Forbidden: execute actions — analysis only.
```

### PROMPT-11: Terminal Agent
```
Role: terminal operations.
Capabilities: open terminal, type command, execute, get output.

Rules:
- never execute dangerous commands without confirmation
- always return execution result
```

### PROMPT-12: Browser Agent
```
Role: browser automation.
Capabilities: open URL, switch tab, fill form, click button.

Priority:
1. Accessibility
2. MCP Browser
3. Vision
```

### PROMPT-13: Conversation Agent
```
Role: user communication.
Style: concise, clear, no unnecessary explanations.

Example:
User: "Открой терминал." (Open terminal.)
Response: "Открываю терминал." (Opening terminal.)

User: "Что мы делали?" (What did we do?)
Response: "Last action: terminal opened. Command executed: echo Привет мир"
```

### PROMPT-14: Recovery Agent
```
Role: error recovery.

Algorithm:
1. Identify the cause of failure
2. Attempt a safe fix
3. If failed — notify the user

Maximum attempts: 3.
Forbidden: retry infinitely.
```

### PROMPT-15: Global Assistant Directive
```
You are a local voice operating agent.

Your mission:
- understand the user
- safely control the computer
- remember action history
- explain your actions
- never execute dangerous operations without confirmation

Priority order when instructions conflict:
1. Safety
2. User data integrity
3. Task completion
4. Convenience
5. Execution speed
```

---

## SECTION 11. DEVELOPMENT ROADMAP

**Rule:** every stage is fully complete before moving to the next.
After each stage: update documentation, run tests, verify manual scenario.

---

### Stage 0 — Project Initialization
**Tasks:** create repository, directory structure, requirements.txt, pyproject.toml, README.md, config.yaml, logging system.

**Done when:** `python main.py` runs without errors.

---

### Stage 1 — Core Architecture
**Tasks:** create EventBus, StateManager, ServiceRegistry, ConfigManager.

**Done when:** all services can register and resolve dependencies.

---

### Stage 2 — UI MVP
**Tasks:** MainWindow, StatusWidget, ActivityLogWidget, TrayIcon, all statuses.

**Done when:** window displays, tray works, closing window does not terminate process.

---

### Stage 3 — STT Pipeline
**Tasks:** MicrophoneService, WhisperService, SpeechPipeline, Faster-Whisper.

**Done when:** user speaks — text appears in UI.

---

### Stage 4 — Wake Word
**Tasks:** OpenWakeWord, support for "брат", "ассистент", "компьютер".

**Done when:** commands are processed only after wake word is detected.

---

### Stage 5 — LLM Integration
**Tasks:** LLMService, PromptManager, IntentParser, Ollama + qwen3:8b.

**Done when:** phrase "Открой терминал" is converted to structured intent.

---

### Stage 6 — Planner
**Tasks:** Planner, PlanValidator. Every command becomes a plan.

**Done when:** plans are displayed in UI.

---

### Stage 7 — Tool System
**Tasks:** BaseTool, ToolRegistry, ToolExecutor.

**Done when:** system calls tools through a unified interface.

---

### Stage 8 — Terminal Tool
**Tasks:** TerminalTool (execute, execute_background, execute_interactive).
**⚠️ Critical:** create SecurityValidator as a stub at this stage — it will be used here already. Do not wait for stage 13.

**Done when:** assistant opens terminal and executes safe commands.

---

### Stage 9 — Filesystem Tool
**Tasks:** create, read, write, search files.

**Done when:** assistant creates and modifies a file via voice command.

---

### Stage 10 — Desktop Tool
**Tasks:** open/close apps, switch windows, list windows.

**Done when:** assistant controls windows.

---

### Stage 11 — Memory System
**Tasks:** SessionMemory, LongTermMemory, SQLite.

**Done when:** all actions are saved.

---

### Stage 12 — Dialog History
**Tasks:** MemorySearch, support for queries "Что мы делали?", "Что было в терминале?", "Какие команды выполнялись?".

**Done when:** assistant answers from action log.

---

### Stage 13 — Security (full implementation)
**Tasks:** full SecurityValidator implementation.
Patterns: sudo, rm, dd, mkfs, chmod, chown, systemctl, package remove/purge.

**Done when:** dangerous actions require user confirmation.

---

### Stage 14 — Accessibility Layer
**Tasks:** Linux Accessibility API, buttons, input fields, menus, interface elements.

**Done when:** assistant interacts with UI without Vision.

---

### Stage 15 — MCP Integration
**Tasks:** Filesystem MCP, Terminal MCP, Browser MCP, Desktop MCP, adapters.

**Done when:** tools work through MCP.

---

### Stage 16 — Browser Automation
**Tasks:** open URL, switch tab, fill form, click button.

**Done when:** assistant performs actions in browser.

---

### Stage 17 — Vision Module
**Tasks:** Moondream, screen and screenshot analysis, element detection.

**Done when:** assistant understands screen content.

---

### Stage 18 — Agent Memory Upgrade
**Tasks:** search by history, actions, past conversations.
Also here: implement vector_memory.py if needed (post-MVP, only by user decision).

**Done when:** assistant recalls old events.

---

### Stage 19 — Production Hardening
**Tasks:** error handling, memory leaks, freezes, logging, crash recovery.

**Done when:** application runs stably for several hours.

---

### Stage 20 — Release Candidate

**Final scenario:**
```
User: "Брат, открой терминал."
→ Terminal opened.

User: "Напиши echo Привет мир."
→ Command typed.

User: "Выполни."
→ Command executed.

User: "Что мы делали?"
→ Assistant answers from memory.

User: "Открой браузер и перейди на сайт."
→ Assistant performs action.

User: "Посмотри на экран."
→ Vision analyzes the image.
```

All features work locally. No cloud. No external APIs.

---

## SECTION 12. MVP ACCEPTANCE CRITERIA

The system is considered MVP-ready when the user can by voice:
- open a terminal
- execute a command in the terminal
- open a browser
- create a file
- edit text
- switch windows
- ask about past actions and get an answer
- receive confirmation prompt before dangerous commands

**All components work locally. Zero external APIs.**

---

## SECTION 13. EDGE CASES

The agent must handle the following situations:

| Situation | Behavior |
|-----------|----------|
| Ollama not responding | Log error, notify user, switch to ERROR status |
| Microphone unavailable | Log error, notify user, offer manual input fallback |
| STT returned empty string | Ignore, return to LISTENING status |
| Tool threw exception | Recovery Agent, max 3 attempts, then notify user |
| Disk full | Log, notify user, do not crash |
| SQLite unavailable | Work with Session Memory only, log warning |

---

## SECTION 14. ENVIRONMENT — WHAT IS ALREADY INSTALLED

> **Instructions for the developer:**
> Before starting a Claude Code session, update this section with actual output
> from the commands below. This prevents the agent from reinstalling
> existing components or using wrong versions.

### How to update this section

Run these commands and paste the output below:

```bash
# 1. Check installed Python packages
pip list | grep -E "faster-whisper|pyaudio|PySide6|ollama|openai-whisper|openwakeword"

# 2. Check Ollama models
ollama list

# 3. Verify faster-whisper import
python -c "import faster_whisper; print('faster-whisper version:', faster_whisper.__version__)"

# 4. Check Whisper model cache location
ls ~/.cache/huggingface/hub/ 2>/dev/null || echo "No HuggingFace cache found"

# 5. Check models directory (project-local)
ls ~/voice-assistant/models/ 2>/dev/null || echo "No local models dir yet"
```

### Current environment status

```
# PASTE COMMAND OUTPUT HERE BEFORE EACH SESSION
# Example format:

faster-whisper    1.1.0   ✓ installed
PySide6           6.7.0   ✓ installed
pyaudio           0.2.14  ✓ installed
openwakeword      0.6.0   ✓ installed

Ollama models:
  qwen3:8b        ✓ pulled, ready
  moondream       ✓ pulled, ready

Whisper models cached at:
  ~/.cache/huggingface/hub/models--Systran--faster-whisper-small
  ~/.cache/huggingface/hub/models--Systran--faster-whisper-medium
```

### Agent instructions — READ BEFORE WRITING ANY CODE

- **DO NOT reinstall** any component listed above as installed
- **DO NOT change versions** of installed packages without explicit user request
- **DO NOT download models** that are already listed as ready
- **USE existing model paths** — do not hardcode new paths
- **ASK the user** before adding any new dependency not listed here
- If a package is missing from this list — install it, then ask the user to update this section

---

### Current environment status

```
faster-whisper     1.2.1    ✓ installed
openwakeword       0.4.0    ✓ installed
PySide6            6.11.1   ✓ installed
pyaudio            0.2.14   ✓ installed

Ollama models:
  qwen3:8b        ✓ pulled, ready — 5.2 GB
  moondream       ✓ pulled, ready — 1.7 GB

Whisper models cached at:
  ~/.cache/huggingface/hub/models--Systran--faster-whisper-small
  ~/.cache/huggingface/hub/models--Systran--faster-whisper-medium

```

*Document compiled from: PROJECT_SPEC.md, IMPLEMENTATION_GUIDE.md, AGENT_RULES.md, ROADMAP.md, ARCHITECTURE_DECISIONS.md, PROMPTS.md*
*Version: 2.0 — English translation with ENVIRONMENT section*
