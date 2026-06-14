# Machine Agent

Local voice operating agent for Linux.

- Fully local: no cloud APIs, no external services
- Voice commands in Russian
- Controls the computer: terminal, files, desktop, browser
- Remembers all actions

## Stack

| Component | Technology |
|-----------|-----------|
| Language  | Python 3.12+ |
| UI        | PySide6 |
| STT       | Faster-Whisper |
| Wake Word | OpenWakeWord |
| LLM       | Ollama + qwen3:8b |
| Vision    | Moondream |
| Database  | SQLite |

## Run

```bash
python main.py
```
