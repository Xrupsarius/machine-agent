# Machine Agent

Local voice operating agent for Linux. Fully local — no cloud APIs, no external services.

- Voice commands in **Russian or English** (chosen on first run)
- Controls the computer: terminal, files, desktop, browser
- **Live dictation** — speak and have your words typed into any window, with voice editing commands
- **Chat mode** — anything that isn't a command is answered conversationally
- Scans your installed apps so "open X" just works
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
  wl-clipboard ydotool \      # Wayland: type/paste text (works in Electron apps)
  chromium \                  # browser automation
  kitty                       # any terminal emulator works
```

`ydotool` needs its daemon running and access to `/dev/uinput`:

```bash
sudo ydotoold &     # or enable a ydotoold service; keep it running
```

Optional / fallbacks:
- `wtype` — typing fallback when `ydotool` isn't running. Works in most apps but produces garbled text in some Electron apps (e.g. Obsidian) — that's why `ydotool` is recommended.
- `xdotool` — typing fallback on X11.
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
| `language` | Working language `ru` / `en` (default; overridden by the first-run choice) | `ru` |
| `wakeword_threshold` | Wake-word sensitivity (lower = more sensitive) | `0.3` |
| `wakeword_models_dir` | Directory with `.onnx` wake-word models | `config/wakeword_models` |
| `mic_device` | `auto` probes all sources and picks the live one; or a device name | `auto` |
| `confirmation_required` | Ask before dangerous commands | `true` |
| `ollama_host` | Ollama server URL | `http://localhost:11434` |

**Wake words:** the project ships a custom model `Hey OMNIS` (`config/wakeword_models/`). If the directory is empty, the app falls back to built-in `Hey Jarvis` / `Hey Mycroft` / `Hey Marvin`.

**Language:** on the very first run the app asks for the working language (Русский / English) and stores the choice in `data/settings.json`. Change it there later, or set `language:` in `config.yaml`. The language controls both speech recognition and the dictation command words (defined in `config/commands.yaml`).

**Dictation tuning** (optional, in `config.yaml`): `dictation_silence_seconds`, `dictation_max_segment_seconds`, `dictation_noise_factor` — leave the defaults unless dictation feels too eager or too slow to commit text.

### GPU acceleration (NVIDIA)

Speech recognition runs much faster and more accurately on an NVIDIA GPU. With a CUDA card you can run `medium` or `large-v3` with lower latency than `small` on CPU. Set in `config.yaml`:

```yaml
stt_model: medium          # or large-v3 / large-v3-turbo
stt_device: cuda           # cpu to disable GPU
stt_compute_type: float16  # int8 on CPU
stt_beam_size: 5           # higher = more accurate; GPU can afford it
stt_cuda_lib_dir: ""       # blank = auto-detect cuBLAS
```

CTranslate2 (the Whisper backend) needs CUDA's `libcublas.so.12`. You don't need a full CUDA toolkit — if **Ollama** is installed it already ships the library, and the app auto-loads it from `/usr/local/lib/ollama/cuda_v12`. If your cuBLAS lives elsewhere, point `stt_cuda_lib_dir` at that folder (or add it to `LD_LIBRARY_PATH`). On CPU-only machines keep `stt_device: cpu` and `stt_compute_type: int8`.

## 4. Run

```bash
source .venv/bin/activate
python main.py
```

A window and a tray icon appear. Say the wake word (`Hey OMNIS`), wait for the beep, then speak a command in your chosen language.

Example commands:
- "Открой терминал." → opens a terminal
- "Открой браузер." → opens the browser
- "Открой Obsidian." → opens an installed app by name (resolved from the app catalog)
- "Выведи список приложений." → lists your installed apps
- "Что мы делали?" → answers from memory
- "Посмотри на экран." → analyzes the screen with vision

If what you say isn't a command, the assistant answers conversationally — the reply appears in the **Chat** panel (it remembers the last few turns within the session).

### Dictation (speak → type into any window)

Click **Старт** in the Dictation panel (bottom-right), then focus the window you want to type into (editor, browser, chat box). Speak naturally — recognized text is typed into the focused window at the cursor.

While dictating you can give commands with the marker word **`омнис`** (English: **`omnis`**):

| Say | Effect |
|-----|--------|
| `омнис отправь` | press **Enter** (send) |
| `омнис новая строка` | line break |
| `омнис сотри` | delete the last word |
| `омнис стоп` | stop dictation |
| `омнис открой браузер` (or any command) | run it through the agent without leaving dictation |

Marker matching is fuzzy, so small mishearings (`омни с`, `омнись`) still work. Click **Стоп** (or say `омнис стоп`) to finish.

### Window layout

- **Status** (top) — current state: `Ожидание`, `🎙 Слушаю…`, `Думаю…`, etc.
- **Chat | Dictation** (middle) — conversational replies on the left, live dictation on the right.
- **Activity log** (bottom) — full technical play-by-play.

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
- **Typing produces garbage in Obsidian / other Electron apps** — start the `ydotool` daemon (`sudo ydotoold &`); the `wtype` fallback mis-types in Electron.
- **Typing does nothing** — install `wl-clipboard` + `ydotool` and make sure `ydotoold` is running; or install `wtype` (most apps) / `xdotool` (X11).
- **Dictation never commits text / lags** — on a noisy mic raise `dictation_noise_factor` or `dictation_silence_seconds` in `config.yaml`.
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
  wl-clipboard ydotool \      # Wayland: ввод/вставка текста (работает в Electron-приложениях)
  chromium \                  # автоматизация браузера
  kitty                       # подойдёт любой терминал
```

Для `ydotool` нужен запущенный демон и доступ к `/dev/uinput`:

```bash
sudo ydotoold &     # или включите сервис ydotoold; должен работать в фоне
```

Опционально / запасные варианты:
- `wtype` — запасной ввод, если `ydotool` не запущен. Работает в большинстве приложений, но в некоторых Electron-приложениях (например, Obsidian) выдаёт мусор — поэтому рекомендуется `ydotool`.
- `xdotool` — запасной ввод для X11.
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
| `language` | Рабочий язык `ru` / `en` (по умолчанию; перекрывается выбором при первом запуске) | `ru` |
| `wakeword_threshold` | Чувствительность wake word (меньше = чувствительнее) | `0.3` |
| `wakeword_models_dir` | Папка с моделями `.onnx` | `config/wakeword_models` |
| `mic_device` | `auto` — сам найдёт активный источник; или имя устройства | `auto` |
| `confirmation_required` | Спрашивать перед опасными командами | `true` |
| `ollama_host` | Адрес сервера Ollama | `http://localhost:11434` |

**Слова активации:** в проекте есть своя модель `Hey OMNIS` (`config/wakeword_models/`). Если папка пуста, используются встроенные `Hey Jarvis` / `Hey Mycroft` / `Hey Marvin`.

**Язык:** при самом первом запуске приложение спрашивает рабочий язык (Русский / English) и сохраняет выбор в `data/settings.json`. Поменять можно там же или в `config.yaml` (`language:`). Язык задаёт и распознавание речи, и слова команд диктовки (заданы в `config/commands.yaml`).

**Тонкая настройка диктовки** (необязательно, в `config.yaml`): `dictation_silence_seconds`, `dictation_max_segment_seconds`, `dictation_noise_factor` — меняйте только если диктовка коммитит текст слишком рано или слишком поздно.

### Ускорение на GPU (NVIDIA)

На GPU распознавание речи работает гораздо быстрее и точнее. С CUDA-картой можно гонять `medium` или `large-v3` с задержкой меньше, чем `small` на CPU. В `config.yaml`:

```yaml
stt_model: medium          # или large-v3 / large-v3-turbo
stt_device: cuda           # cpu — отключить GPU
stt_compute_type: float16  # int8 для CPU
stt_beam_size: 5           # больше = точнее; на GPU не жалко
stt_cuda_lib_dir: ""       # пусто = авто-поиск cuBLAS
```

CTranslate2 (движок Whisper) требует `libcublas.so.12` из CUDA. Полный CUDA-тулкит ставить не нужно — если установлен **Ollama**, он уже несёт эту библиотеку, и приложение само подхватит её из `/usr/local/lib/ollama/cuda_v12`. Если cuBLAS лежит в другом месте — укажите папку в `stt_cuda_lib_dir` (или добавьте её в `LD_LIBRARY_PATH`). На машинах без GPU оставьте `stt_device: cpu` и `stt_compute_type: int8`.

## 4. Запуск

```bash
source .venv/bin/activate
python main.py
```

Появятся окно и иконка в трее. Скажите слово активации (`Hey OMNIS`), дождитесь сигнала и произнесите команду на выбранном языке.

Примеры команд:
- «Открой терминал.» → откроется терминал
- «Открой браузер.» → откроется браузер
- «Открой Obsidian.» → откроет установленное приложение по имени (из каталога приложений)
- «Выведи список приложений.» → покажет установленные приложения
- «Что мы делали?» → ответит из памяти
- «Посмотри на экран.» → проанализирует экран через зрение

Если сказанное — не команда, ассистент ответит как собеседник; ответ появится в панели **Чат** (он помнит несколько последних реплик в пределах сессии).

### Диктовка (говори → печатается в любое окно)

Нажмите **Старт** в панели диктовки (справа внизу), затем сделайте активным окно, куда хотите печатать (редактор, браузер, поле чата). Говорите обычным текстом — распознанное печатается в активное окно под курсор.

Во время диктовки можно давать команды словом-маркером **`омнис`** (по-английски: **`omnis`**):

| Скажите | Действие |
|---------|----------|
| `омнис отправь` | нажать **Enter** (отправить) |
| `омнис новая строка` | перенос строки |
| `омнис сотри` | удалить последнее слово |
| `омнис стоп` | остановить диктовку |
| `омнис открой браузер` (или любая команда) | выполнить её через агента, не выходя из диктовки |

Маркер ловится нечётко, поэтому мелкие огрехи распознавания (`омни с`, `омнись`) тоже срабатывают. Завершить — кнопкой **Стоп** или фразой `омнис стоп`.

### Раскладка окна

- **Статус** (сверху) — текущее состояние: `Ожидание`, `🎙 Слушаю…`, `Думаю…` и т.д.
- **Чат | Диктовка** (середина) — слева ответы собеседника, справа живая диктовка.
- **История действий** (снизу) — полный технический лог.

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
- **Мусор при вводе в Obsidian / других Electron-приложениях** — запустите демон `ydotool` (`sudo ydotoold &`); запасной `wtype` в Electron печатает неверно.
- **Текст вообще не вводится** — поставьте `wl-clipboard` + `ydotool` и убедитесь, что `ydotoold` запущен; либо `wtype` (большинство приложений) / `xdotool` (X11).
- **Диктовка не коммитит текст / отстаёт** — на шумном микрофоне поднимите `dictation_noise_factor` или `dictation_silence_seconds` в `config.yaml`.
- **Не запускается браузер** — установите `chromium` или выполните `playwright install chromium`.
