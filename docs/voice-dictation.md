# Voice Dictation — диктовка вместо клавиатуры

Push-to-talk голосовой ввод во **любое** активное поле (Slack, iMessage, Telegram, VS Code, Obsidian, любой текстовое поле в браузере). Работает локально через Whisper, не отправляет ничего наружу.

> 💰 Заменяет **Superwhisper ($8.49/мес)**, **Wispr Flow ($12/мес)**, **Aqua Voice**, **Whispering** — за **$0**.

## Что нужно поставить

```bash
# В venv где уже стоит твой Whisper-бэкенд (mlx / faster / whisperx):
pip install sounddevice soundfile pynput pyperclip pystray Pillow numpy

# Дополнительно на Windows — приглушение музыки и звонков во время записи:
pip install pycaw
```

## Как работает

```
Жмёшь Ctrl+Shift+Space →  🎙 запись
Говоришь...
Отпускаешь          →  ⏳ Whisper
                    →  📋 в clipboard
                    →  ⌨️  Cmd+V в активное поле
```

**Скорость:** на Mac M2 Pro для фразы 5 секунд — транскрибация ~0.3-0.5 сек. Realtime-feel.

## Запуск

```bash
# Создать конфиг (одноразово)
python -m examples.voice_dictation --setup

# Запустить (висит в трее, слушает хоткей)
python -m examples.voice_dictation
```

## Конфиг

Лежит в `~/.config/whisper-skill/voice_dictation.json` (Mac/Linux) или `%APPDATA%\whisper-skill\` (Windows).

```json
{
  "hotkey": "<ctrl>+<shift>+<space>",
  "mode": "ptt",
  "language": "ru",
  "model": "large-v3-turbo",
  "sample_rate": 16000,
  "channels": 1,
  "max_duration_sec": 60,
  "auto_paste": true,
  "play_sound": true,
  "show_tray": true,
  "audio_ducking_enabled": true,
  "audio_ducking_reduction_percent": 70,
  "show_input_device_overlay": true,
  "input_device_overlay_duration_ms": 650,
  "trim_silence_ms": 200,
  "min_duration_ms": 300
}
```

### Параметры

| Поле | Значения | Описание |
|---|---|---|
| `hotkey` | строка | Глобальный хоткей в формате pynput. Примеры: `<ctrl>+<shift>+<space>`, `<f9>`, `<cmd>+<shift>+v`, `<alt>+<space>` |
| `mode` | `ptt` / `toggle` | **ptt** = держи и говори (push-to-talk). **toggle** = жми чтобы начать, жми ещё чтобы остановить |
| `language` | `null` / `ru` / `en` / ... | `null` — auto-detect (медленнее). Лучше указать |
| `model` | имя | `large-v3-turbo` (дефолт), `large-v3`, `medium`, `small`, `tiny` |
| `auto_paste` | bool | После транскрибации эмулировать Cmd+V/Ctrl+V. Если `false` — только в clipboard |
| `play_sound` | bool | Тихие бипы на старт/стоп для обратной связи |
| `show_tray` | bool | Иконка в трее (меняет цвет: серый/красный/оранжевый) |
| `audio_ducking_enabled` | bool | Windows: приглушать звук остальных приложений на время записи. Быстро включается и выключается из трея |
| `audio_ducking_reduction_percent` | 0–90 | Насколько приглушать музыку, браузер, Zoom и другие звонки. Удобный бегунок открывается из трея |
| `show_input_device_overlay` | bool | На старте записи коротко показать по центру активный микрофон |
| `input_device_overlay_duration_ms` | int | Сколько миллисекунд показывать карточку микрофона |
| `min_duration_ms` | int | Игнорировать короткие записи (промахи кнопкой) |

### Популярные пресеты хоткеев

```jsonc
// Mac — родной для системы
"hotkey": "<f5>"           // удобно на Mac, обычно ничем не занято

// Универсальный
"hotkey": "<ctrl>+<shift>+<space>"

// Однокнопочные модификаторы (для миграции с OpenWispr / Wispr Flow / Superwhisper)
"hotkey": "<alt_r>"        // Right Option (OpenWispr default) ⭐ самый популярный
"hotkey": "<alt_l>"        // Left Option
"hotkey": "<cmd_r>"        // Right Command (Wispr Flow стандарт)

// Под клавишу на правой стороне (для leftie)
"hotkey": "<alt_r>+<space>"

// Однокнопочные функциональные клавиши
"hotkey": "<f9>"
"hotkey": "<f13>"          // на Mac часто свободна
```

> 💡 **pynput использует имена `alt_l` / `alt_r` / `cmd_l` / `cmd_r` / `ctrl_l` / `ctrl_r`** —
> с подчёркиванием, не `right_alt` / `left_alt`. Если поставишь невалидное имя
> в конфиге, hotkey просто не сработает (без понятной ошибки).

### Миграция с OpenWispr / Wispr Flow / Superwhisper

Если переходишь с другого инструмента — у них стандартные хоткеи:

| С чего | Хоткей | Конфиг для нашего скилла |
|---|---|---|
| **OpenWispr** | Right Option (без модификаторов) | `"hotkey": "<alt_r>", "mode": "toggle"` |
| **Wispr Flow** | Right Command | `"hotkey": "<cmd_r>", "mode": "toggle"` |
| **Superwhisper** | F-key configurable | `"hotkey": "<f5>", "mode": "ptt"` |
| **Aqua Voice** | Globe/Fn key | `"hotkey": "<f6>", "mode": "ptt"` |

## Permissions

### macOS

Нужны два разрешения:

1. **Microphone**:
   `System Settings → Privacy & Security → Microphone → добавить Terminal/iTerm/тот шелл откуда запускаешь`

2. **Accessibility** (для глобального хоткея и эмуляции вставки):
   `System Settings → Privacy & Security → Accessibility → добавить Terminal/iTerm`

После добавления нужно **перезапустить терминал**. Если не работает — кликни ⊖ Remove → ⊕ Add заново.

### Linux

- **X11** — работает out-of-box.
- **Wayland** — глобальные хоткеи частично сломаны на уровне платформы. Workaround:
  - Использовать `evdev` напрямую (нужен root или добавить юзера в группу `input`):
    ```bash
    sudo usermod -aG input $USER
    # перелогиниться
    ```
  - Или отказаться от Wayland (`/etc/gdm3/custom.conf` → `WaylandEnable=false` → перезагрузка)

### Windows

Обычно работает без настройки. Если хоткей перехватывается другим приложением — поменяй в конфиге.

## Сценарии использования

### 1. Кодеру — диктовать комментарии и docstrings

```jsonc
{
  "hotkey": "<f5>",
  "mode": "ptt",
  "language": "en",
  "model": "large-v3-turbo"
}
```

В VS Code/PyCharm кликаешь куда вставить → жмёшь F5 → говоришь → отпускаешь. Текст вставляется.

### 2. В Slack/Telegram быстро ответить

```jsonc
{
  "hotkey": "<ctrl>+<shift>+<space>",
  "mode": "ptt",
  "language": "ru",
  "model": "large-v3-turbo"
}
```

Кликаешь в поле ввода Slack → жмёшь хоткей → говоришь → отпускаешь → Enter.

### 3. Длинная диктовка статьи (toggle mode)

```jsonc
{
  "hotkey": "<ctrl>+<shift>+d",
  "mode": "toggle",
  "language": "ru",
  "model": "large-v3"
}
```

Жмёшь — начало записи, говоришь сколько надо, жмёшь ещё раз — стоп. Удобно для длинных текстов где не хочется держать кнопку 2 минуты.

### 4. Многоязычка (RU + EN термины)

```jsonc
{
  "hotkey": "<f5>",
  "language": null,
  "model": "large-v3"
}
```

Auto-detect языка. Whisper сам понимает RU/EN. Чуть медленнее (auto-detect добавляет 5-10%).

## Запуск в фоне (автостарт)

### macOS — через launchd

Создай `~/Library/LaunchAgents/com.whisper.dictation.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
        "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.whisper.dictation</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/.venv/bin/python</string>
        <string>-m</string>
        <string>examples.voice_dictation</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/whisper-skill</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <!-- ⭐ ВАЖНО: без PYTHONUNBUFFERED логи копятся в буфер
         и в StandardOutPath ничего не пишется пока не накопится 4-8KB.
         Из-за этого кажется что скрипт не запустился. -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/whisper_dictation.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/whisper_dictation.err</string>
</dict>
</plist>
```

Загрузи:
```bash
launchctl load ~/Library/LaunchAgents/com.whisper.dictation.plist
```

### Linux — через systemd user service

`~/.config/systemd/user/whisper-dictation.service`:

```ini
[Unit]
Description=Whisper Voice Dictation
After=graphical-session.target

[Service]
Type=simple
WorkingDirectory=%h/whisper-skill
ExecStart=%h/whisper-skill/.venv/bin/python -m examples.voice_dictation
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now whisper-dictation
```

### Windows — Task Scheduler

`Win+R` → `taskschd.msc` → Create Task:
- General: запуск при логине пользователя
- Triggers: At log on
- Actions: Start a program → `python.exe`, аргументы `-m examples.voice_dictation`, путь рабочей папки = whisper-skill

## Известные грабли

### Хоткей не срабатывает на Mac

→ Не дано Accessibility-разрешение. Зайди в `System Settings → Privacy & Security → Accessibility` и добавь Terminal (откуда запущено). После — **перезапусти терминал**.

### Запись идёт, текст копируется в буфер, но не вставляется автоматически (macOS)

Это самая частая проблема на маке. Симптомы: бипы есть, в clipboard'е текст лежит, но Cmd+V не «нажимается» автоматически.

**Причина.** macOS защищает синтетические нажатия клавиш — они блокируются если приложение не имеет Accessibility-разрешения. Хитрость в том, что **Accessibility выдаётся конкретному бинарю** — обычно ты даёшь Terminal, но реально работает `.venv/bin/python3` или системный Python, и им нужно отдельное разрешение.

**Что делать (по приоритету):**

1. **Скилл сам уже использует osascript** (через System Events) — это надёжнее чем pynput. Если он не работает — макос блочит и его. Тогда:

2. **Дай Accessibility ВСЕМ троим:**
   - Terminal (или iTerm — что используешь)
   - System Events (после первого запуска оно само спросит, разреши)
   - `python3` бинарь — открой `System Settings → Privacy & Security → Accessibility → +` → Cmd+Shift+G → введи `/path/to/whisper-skill/.venv/bin` → выбери `python3`

3. **После каждого добавления — перезапусти терминал.**

4. **Если ничего не помогает** — используй режим без auto-paste. В конфиге `~/.config/whisper-skill/voice_dictation.json`:
   ```json
   "auto_paste": false
   ```
   Тогда текст только в clipboard, вставляешь руками `Cmd+V`. Это **рабочий вариант** для тех у кого защита упёртая.

5. **Для production / магазинных приложений** macOS требует подписанный .app bundle с прописанной decleration of permissions. В рамках этого скилла мы не подписываем — это домашний тулчейн. Если хочется именно «нативное приложение» — можно обернуть через `py2app` или `Platypus`, но это отдельный проект.

### "Microphone permission denied"

→ `System Settings → Privacy & Security → Microphone` → добавь Terminal.

### macOS: высокий CPU в idle (~70-90%) даже когда ничего не записываю

Это известная проблема комбо `pystray` (NSRunLoop в non-main thread) + `pynput` (CGEventTap) на macOS. С версии **2026-05-04** скилл по дефолту включает `mac_low_cpu_mode: true` в конфиге, который автоматически отключает `show_tray` и `show_cursor_indicator` на маке. Если у тебя старый конфиг — добавь руками:

```json
{
  "mac_low_cpu_mode": true,
  "show_tray": false,
  "show_cursor_indicator": false
}
```

Визуальный feedback на маке остаётся через CLI-stdout (`Recording...`, `Transcribing...`, `✓`). Если очень хочется иконку в трее — поставь `mac_low_cpu_mode: false` (на свой страх и риск, CPU вырастет).

### macOS: процесс падает с `NSInvalidArgumentException` после старта

Старый баг (фикс выпущен 2026-05-04). С `show_cursor_indicator: true` на macOS Tk создавал окно из non-main thread → краш в Tcl/Tk 9.0. Текущая версия скилла **автоматически отключает** cursor_indicator на macOS (`scripts/cursor_indicator.py` → no-op на Mac). Обнови:

```bash
cd whisper-skill
git pull
```

### macOS: launchd респаунит процесс в бесконечный краш-цикл

Связано с предыдущим багом — `KeepAlive=true` + cursor_indicator краш = вечный респаун. После `git pull` (фикс выше) и **перезапуска LaunchAgent**:

```bash
launchctl unload ~/Library/LaunchAgents/com.whisper.dictation.plist
launchctl load ~/Library/LaunchAgents/com.whisper.dictation.plist
```

### Текст вставился, но без пробела

→ Whisper иногда не ставит пробел в начале. Открой конфиг и поправь `auto_paste: false`, тогда текст только в clipboard, ты вставишь руками с правильным пробелом.

### Транскрибация очень медленная (>3 сек)

→ Используешь не оптимальный бэкенд / модель. Запусти `python scripts/detect_env.py` и проверь.

### Hotkey не работает в специфичном приложении

→ Некоторые приложения (особенно игры в полный экран) перехватывают input до глобального уровня. Workaround — использовать другой хоткей через конфиг.

### Запись пустая

→ Проверь что выбран правильный микрофон в системе. Скрипт использует **системный default input device**.

### "Жжёт" батарею в фоне

→ В idle (без хоткея) скрипт не пишет ничего и расход CPU = ~0.5%. Жжёт только во время самой транскрибации.

## Сравнение с платными аналогами

| Функция | Local Whisper | Superwhisper $8.49 | Wispr Flow $12 | Aqua Voice $9.99 |
|---|---|---|---|---|
| Цена/мес | **$0** | $8.49 | $12 | $9.99 |
| Локально | ✅ | ⚠ | ✅ | ⚠ |
| Скорость на M-чипе | ~0.3-0.5s | ~0.3s | ~0.5s | ~0.5s |
| Языки | 99 | 99 | EN focus | EN focus |
| Кастом хоткей | ✅ | ✅ | ⚠ | ⚠ |
| Open source | ✅ | ❌ | ❌ | ❌ |
| AI пост-обработка | ⚠ (через LLM) | ✅ | ✅ | ✅ |

> 💡 **Что у платных лучше:** AI пост-обработка (исправление пунктуации, форматирование под контекст). У нас её нет в дефолте, но можно добавить через `examples/voice_dictation_with_llm.py` который пускает результат через Claude/GPT перед вставкой.

## Расширения

### Пост-обработка через LLM (исправить пунктуацию + форматирование)

Скопируй `voice_dictation.py` → `voice_dictation_llm.py`, в функции `work()` добавь:

```python
import anthropic
client = anthropic.Anthropic()

raw_text = result.text.strip()
fixed = client.messages.create(
    model="claude-haiku-4-5",
    max_tokens=512,
    system="Расставь пунктуацию и заглавные буквы. Не меняй смысл и слова. Не добавляй ничего своего.",
    messages=[{"role": "user", "content": raw_text}],
).content[0].text

copy_to_clipboard(fixed)
```

Цена за обработку 100 диктовок в день через Haiku ≈ $0.30/мес. Дешевле чем Superwhisper.

### Команды-триггеры

Можно добавить парсинг команд: «новая строка», «точка», «открой Notion», «закрой окно». Обработка через `if/elif` в `work()`.

### Per-app промпты

Через AppleScript определять активное приложение и подставлять разный `initial_prompt`:
- В Slack — initial_prompt с глоссарием команды
- В IDE — с глоссарием технических терминов
