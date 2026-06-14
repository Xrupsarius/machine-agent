# Machine Agent

Local voice operating agent for Linux. Fully local — no cloud APIs, no external services.

- Voice commands in Russian
- Controls the computer: terminal, files, desktop, browser
- Reads the screen on demand (vision)
- Remembers every action

| Component | Technology |
|-----------|-----------|
| Language  | Python 3.12+ |
| UI        | PySide6 |
| STT       | Faster-Whisper |
| Wake Word | OpenWakeWord |
| LLM       | Ollama + qwen3:8b |
| Vision    | Moondream |
| Database  | SQLite |

📖 **[Русская инструкция ниже / Russian guide below](#запуск-проекта-русский)**

---

# Running the project (English)

## 1. Prerequisites

### Ollama + models

The agent talks to a local [Ollama](https://ollama.com) server. Install it, start it, and pull the models:

```bash
# install Ollama (see https://ollama.com/download), then:
ollama serve            # keep running (or enable the systemd service)
ollama pull qwen3:8b    # main LLM (~5 GB)
ollama pull moondream   # vision model (~1.7 GB)
```

### System packages

These are needed for audio, GUI control, typing and the browser. Commands are for **Arch Linux** — adapt the package names for your distro.

```bash
sudo pacman -S --needed \
  python portaudio \          # PyAudio (microphone)
  python-gobject at-spi2-core \  # accessibility (AT-SPI2 UI control)
  wl-clipboard wtype \        # Wayland: paste / type text
  chromium \                  # browser automation
  kitty                       # any terminal emulator works
```

Optional / fallbacks:
- `ydotool` or `xdotool` — typing fallback if `wtype` is unavailable (X11).
- `libpulse` / `pipewire-pulse` — provide `pactl` and `paplay` (usually already installed). Used for mic selection and the wake-word beep.

> **Note (Wayland/Hyprland):** desktop control uses `hyprctl` on Hyprland. On other compositors, window management falls back to other tools but may be limited.

## 2. Install Python dependencies

```bash
cd machine-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Playwright ships its own Chromium; if the system Chromium isn't found, install the bundled one once:

```bash
playwright install chromium
```

The Whisper STT model is downloaded automatically on first run (cached in `~/.cache/huggingface`).

## 3. Configure

Settings live in `config.yaml` — no hardcoding. Common options:

| Key | Meaning | Default |
|-----|---------|---------|
| `stt_model` | Whisper size: `tiny` / `base` / `small` / `medium` | `small` |
| `llm_model` | Ollama model name | `qwen3:8b` |
| `vision_model` | Vision model | `moondream` |
| `wakeword_threshold` | Wake-word sensitivity (lower = more sensitive) | `0.3` |
| `wakeword_models_dir` | Directory with `.onnx` wake-word models | `config/wakeword_models` |
| `mic_device` | `auto` probes all sources and picks the live one; or a device name | `auto` |
| `confirmation_required` | Ask before dangerous commands | `true` |
| `ollama_host` | Ollama server URL | `http://localhost:11434` |

**Wake words:** the project ships a custom model `Hey OMNIS` (`config/wakeword_models/`). If the directory is empty, the app falls back to built-in `Hey Jarvis` / `Hey Mycroft` / `Hey Marvin`.

## 4. Run

```bash
source .venv/bin/activate
python main.py
```

A window and a tray icon appear. Say the wake word (`Hey OMNIS`), wait for the beep, then speak a command in Russian.

Example session:
- "Открой терминал." → opens a terminal
- "Открой браузер." → opens the browser
- "Что мы делали?" → answers from memory
- "Посмотри на экран." → analyzes the screen with vision

Closing the window hides it to the tray (the process keeps running). Quit fully from the **tray menu → Quit**, or press `Ctrl+C` in the terminal.

## 5. Tests

```bash
source .venv/bin/activate
pytest                 # full suite
pytest -m "not slow"   # skip browser/integration tests
```

## Troubleshooting

- **"Ollama недоступен" / no LLM** — make sure `ollama serve` is running and models are pulled (`ollama list`).
- **No reaction to the wake word** — check the mic in `config.yaml` (`mic_device`), or lower `wakeword_threshold`. The active wake words are printed in the activity log at startup.
- **Mic delivers silence** — set the correct PipeWire/PulseAudio source as default, or set `mic_device` to your device name (e.g. `"USB PnP"`).
- **Typing produces garbage / drops characters** — install `wtype` and `wl-clipboard`; on X11 install `xdotool`.
- **Browser doesn't start** — install `chromium`, or run `playwright install chromium`.

---

# Запуск проекта (Русский)

## 1. Что нужно заранее

### Ollama + модели

Агент работает с локальным сервером [Ollama](https://ollama.com). Установите его, запустите и скачайте модели:

```bash
# установите Ollama (см. https://ollama.com/download), затем:
ollama serve            # должен работать в фоне (или включите systemd-сервис)
ollama pull qwen3:8b    # основная LLM (~5 ГБ)
ollama pull moondream   # модель зрения (~1.7 ГБ)
```

### Системные пакеты

Нужны для звука, управления интерфейсом, ввода текста и браузера. Команды — для **Arch Linux**, под другой дистрибутив поменяйте названия пакетов.

```bash
sudo pacman -S --needed \
  python portaudio \          # PyAudio (микрофон)
  python-gobject at-spi2-core \  # accessibility (управление UI через AT-SPI2)
  wl-clipboard wtype \        # Wayland: вставка / ввод текста
  chromium \                  # автоматизация браузера
  kitty                       # подойдёт любой терминал
```

Опционально / запасные варианты:
- `ydotool` или `xdotool` — запасной ввод текста, если нет `wtype` (для X11).
- `libpulse` / `pipewire-pulse` — дают `pactl` и `paplay` (обычно уже стоят). Нужны для выбора микрофона и звукового сигнала на wake word.

> **Заметка (Wayland/Hyprland):** управление рабочим столом использует `hyprctl` на Hyprland. На других композиторах управление окнами работает через запасные средства, но может быть ограничено.

## 2. Установка Python-зависимостей

```bash
cd machine-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Playwright несёт свой Chromium; если системный Chromium не найден, один раз поставьте встроенный:

```bash
playwright install chromium
```

Модель распознавания речи (Whisper) скачается автоматически при первом запуске (кэш в `~/.cache/huggingface`).

## 3. Настройка

Все настройки в `config.yaml` — без хардкода. Основные параметры:

| Ключ | Значение | По умолчанию |
|------|----------|--------------|
| `stt_model` | Размер Whisper: `tiny` / `base` / `small` / `medium` | `small` |
| `llm_model` | Имя модели Ollama | `qwen3:8b` |
| `vision_model` | Модель зрения | `moondream` |
| `wakeword_threshold` | Чувствительность wake word (меньше = чувствительнее) | `0.3` |
| `wakeword_models_dir` | Папка с моделями `.onnx` | `config/wakeword_models` |
| `mic_device` | `auto` — сам найдёт активный источник; или имя устройства | `auto` |
| `confirmation_required` | Спрашивать перед опасными командами | `true` |
| `ollama_host` | Адрес сервера Ollama | `http://localhost:11434` |

**Слова активации:** в проекте есть своя модель `Hey OMNIS` (`config/wakeword_models/`). Если папка пуста, используются встроенные `Hey Jarvis` / `Hey Mycroft` / `Hey Marvin`.

## 4. Запуск

```bash
source .venv/bin/activate
python main.py
```

Появятся окно и иконка в трее. Скажите слово активации (`Hey OMNIS`), дождитесь сигнала и произнесите команду по-русски.

Пример сессии:
- «Открой терминал.» → откроется терминал
- «Открой браузер.» → откроется браузер
- «Что мы делали?» → ответит из памяти
- «Посмотри на экран.» → проанализирует экран через зрение

Закрытие окна сворачивает его в трей (процесс продолжает работать). Полностью выйти — через **меню в трее → Выход**, либо `Ctrl+C` в терминале.

## 5. Тесты

```bash
source .venv/bin/activate
pytest                 # все тесты
pytest -m "not slow"   # без браузерных/интеграционных тестов
```

## Решение проблем

- **«Ollama недоступен» / нет ответа LLM** — убедитесь, что запущен `ollama serve` и модели скачаны (`ollama list`).
- **Нет реакции на слово активации** — проверьте микрофон в `config.yaml` (`mic_device`) или понизьте `wakeword_threshold`. Активные слова печатаются в логе при запуске.
- **Микрофон отдаёт тишину** — выберите правильный источник PipeWire/PulseAudio по умолчанию или укажите `mic_device` с именем устройства (например, `"USB PnP"`).
- **Текст вводится с мусором / теряются символы** — поставьте `wtype` и `wl-clipboard`; на X11 — `xdotool`.
- **Не запускается браузер** — установите `chromium` или выполните `playwright install chromium`.
