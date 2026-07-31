# whisper-skill

> 🎤 **Локальная транскрибация речи на любом железе. Бесплатно. Без OpenAI API.**
>
> Готовый комплект Whisper + 3 killer-фичи: push-to-talk диктовка во все приложения, вшитые сабы в MP4 в стиле CapCut, и интерактивный мастер настройки одной командой.

---

## ⚡ Установка скилла к ИИ-ассистенту (60 секунд)

Скилл подключается **к твоему ИИ-ассистенту** (Claude Code, Cursor, ChatGPT и т.д.) и даёт ему точные знания про Whisper-стек. Без скилла нейронка путает имена бэкендов, пакетов и параметров. Со скиллом — даёт рабочий код с первого раза.

### Вариант 1 — Claude Code (рекомендую)

```bash
git clone https://github.com/Mobiss11/Whisper-Skill.git ~/.claude/skills/whisper-skill
```

Перезапусти Claude Code. Теперь спроси:

> Помоги поставить локальный Whisper для диктовки голосом.

Claude автоматически найдёт скилл и проведёт за руку.

### Вариант 2 — Cursor

В корне твоего проекта создай `.cursor/rules/whisper.mdc`:

```markdown
---
description: Используй для задач транскрибации, голосового ввода, и сабов через Whisper
globs: ["**/*.py", "**/*.md"]
alwaysApply: false
---

# Whisper Skill

Когда задача связана с речью, транскрибацией, диктовкой, сабами:
1. Читай @../whisper-skill/SKILL.md
2. Запусти @../whisper-skill/scripts/detect_env.py для определения железа
3. Используй обвязку @../whisper-skill/examples/common.py
4. Карточки бэкендов: @../whisper-skill/backends/
```

Поправь пути под фактическое расположение клона.

### Вариант 3 — ChatGPT (Custom GPT) / Claude.ai (Project)

1. Скачай ZIP-архив: https://github.com/Mobiss11/Whisper-Skill/archive/refs/heads/main.zip
2. Залей в Knowledge / Project Files: `SKILL.md` + всё содержимое `backends/`, `docs/`, `models/`
3. В описании Custom GPT / системном промпте Project'а добавь:
   > Когда задача про Whisper, транскрибацию, голосовой ввод или сабы — сначала ищи нужный файл в knowledge, потом отвечай.

### Проверка что AI видит скилл

Спроси у нейронки:

> Какой бэкенд Whisper мне ставить на Mac M-чип? Что делает `detect_env.py`?

Правильный ответ упомянет **`mlx-whisper`** (нативный Metal) и опишет что детектор автоматически рекомендует бэкенд + модель + команды установки. Если ответ общий — скилл не подцепился, перечитай инструкцию.

---

## 🚀 Быстрый старт без ИИ-ассистента (3 минуты)

Если хочешь просто поставить и пользоваться без всяких Claude Code:

```bash
# 1. Склонируй
git clone https://github.com/Mobiss11/Whisper-Skill.git
cd Whisper-Skill

# 2. Запусти мастер
python3 wizard.py
```

Мастер задаст 3 вопроса (что хочешь делать → какая ОС → поставить?) и автоматически:
- определит твоё железо (CPU / GPU / RAM)
- подберёт оптимальный бэкенд (mlx-whisper / faster-whisper / whisper.cpp / whisperx)
- поставит ffmpeg + Python-зависимости + скачает модель
- настроит выбранную фичу (диктовка / сабы / транскрибация / подкасты)
- прогонит smoke-test

**Готово.** Можешь начинать пользоваться.

---

## 🎯 3 Killer-фичи

### 1. 🎤 Voice Dictation — push-to-talk диктовка во все приложения

Заменяет **Superwhisper ($8.49/мес)**, **Wispr Flow ($12/мес)**, **Aqua Voice** — за **$0**.

```bash
python -m examples.voice_dictation --setup     # одноразово
python -m examples.voice_dictation              # запуск (висит в трее)
```

**Как работает:**
1. Висит в трее как иконка (серая = idle, красная = запись, оранжевая = транскрибация)
2. Жмёшь глобальный хоткей (по дефолту `Ctrl+Shift+Space`)
3. Говоришь, держа кнопку
4. Отпускаешь → Whisper транскрибирует за 0.3-0.5 сек → текст автоматически вставляется в активное поле через clipboard

**Где работает:** в любом приложении с текстовым полем — Slack, iMessage, Telegram, VS Code, Obsidian, Notion, браузер, любое нативное окно.

**Скорость на M2 Pro:** для фразы 5 сек — транскрибация 0.3 сек. Realtime feel.

Подробно: [docs/voice-dictation.md](docs/voice-dictation.md) (настройка хоткеев, permissions per OS, autostart, расширение через LLM для пост-обработки)

---

### 2. 🎬 Subtitle Baker — сабы прямо в MP4 (CapCut-style)

Заменяет **CapCut Pro ($10/мес)**, **Adobe Premiere ($23/мес)**, **Submagic ($19/мес)** — за **$0**.

```bash
python -m examples.bake_subs input.mp4 --style tiktok --output ready.mp4
```

**Что внутри:**
- Транскрибация через Whisper с **word-level timestamps**
- Генерация ASS-файла с **karaoke-разметкой** (текущее слово подсвечивается жёлтым)
- ffmpeg вшивает сабы прямо в видео
- 5 готовых стилей: `tiktok` / `youtube_shorts` / `reels` / `podcast_clip` / `minimal`

**Скорость на M2 Pro:**
- 60-сек TikTok → готовый клип за **~15 сек** (5 сек транскрибация + 10 сек ffmpeg)
- 3-мин Reels → **~45 сек**
- 1-час подкаст с сабами → **~13 мин**

**Кастомизация под бренд:**

```python
# В examples/bake_subs.py добавь свой стиль:
STYLES["my_brand"] = Style(
    font="Geist",
    font_size=58,
    primary_color="&H00FFFFFF",       # белый
    secondary_color="&H000088FF",     # оранжевая подсветка слова
    bold=True, outline_width=4, alignment=2
)
```

Подробно: [docs/subtitle-baker.md](docs/subtitle-baker.md) (BGRA-цвета, ASS-разметка, A/B тесты, кастомные шрифты)

---

### 3. 🧙 Interactive Wizard — установка одной командой

Превращает «прочитай 5 страниц документации» в «запусти и работает».

```bash
python wizard.py
```

5 шагов:
1. **Какой сценарий?** (5 опций — диктовка / транскрибация / подкасты / сабы / всё)
2. **Авто-определение железа** (ОС / CPU / GPU / RAM / Python / ffmpeg)
3. **Подтверди установку** — мастер ставит ffmpeg, Python-deps, скачивает модель
4. **Настройка под сценарий** — генерит конфиги, объясняет permissions
5. **Smoke-test** — скачивает sample.wav и пробует транскрибировать

Все шаги цветные, с подсказками, графитично оформлены. Не нужно знать терминологию — мастер сам выберет правильный бэкенд, модель и compute-type под твоё железо.

---

## 📦 Что внутри скилла

После подключения нейронка получает структурированные знания про:

- 🤖 **4 бэкенда Whisper** с подробными карточками: когда брать какой, как ставить, скорости, грабли
- 📐 **7 моделей** (tiny → large-v3) с бенчмарками WER на EN/RU/KK + рекомендации под задачу
- 🎯 **Auto-detect железа** + рекомендательная логика «что ставить под что»
- 🛠️ **Установка под все 3 ОС** (macOS / Linux / Windows) — с CUDA / ROCm / Metal / WSL2
- 📚 **Speaker diarization** через pyannote — для подкастов
- ⚡ **Speed-tuning** — как ускорить инференс в 5-10x правильными параметрами
- 💰 **Cost-comparison** vs OpenAI API по реальным сценариям
- 🐛 **Known issues** — все типовые грабли с решениями

Концепция: **AI + структурированный контекст = надёжный код без галлюцинаций.**

---

## 🧰 Доступные бэкенды

Авто-детектор (`scripts/detect_env.py`) сам выберет нужный, но если интересно:

| Бэкенд | Когда брать | Скорость | Карточка |
|---|---|---|---|
| **mlx-whisper** | Mac M1/M2/M3/M4/M5 — нативный Metal | до 18x realtime | [backends/mlx-whisper.md](backends/mlx-whisper.md) |
| **faster-whisper** | Linux/Windows + NVIDIA GPU; универсальный CPU | до 17x realtime | [backends/faster-whisper.md](backends/faster-whisper.md) |
| **openvino** | Intel Core Ultra / Intel Arc — нативный iGPU + NPU | ~10x realtime на iGPU | [backends/openvino.md](backends/openvino.md) |
| **whisper.cpp** | Один бинарник без Python; edge-устройства; AMD GPU через Vulkan | 7-15x realtime | [backends/whisper-cpp.md](backends/whisper-cpp.md) |
| **whisperx** | Speaker diarization (подкасты) или word-level alignment | ~7 мин на 1 час подкаста | [backends/whisperx.md](backends/whisperx.md) |

---

## 🎯 Готовые примеры

Все скрипты в `examples/` используют общую обвязку `examples/common.py` — автовыбор бэкенда и устройства, единый формат `Result` независимо от того что под капотом.

### Базовая транскрибация

```bash
# Один файл → SRT + TXT (по дефолту)
python -m examples.transcribe_one audio.mp3

# С указанием языка и модели
python -m examples.transcribe_one audio.mp4 --language ru --model large-v3 --format srt,vtt,json

# В конкретную папку
python -m examples.transcribe_one audio.mp3 --output ./transcripts/
```

### Пакетная обработка

```bash
# Вся папка с авто-определением языка
python -m examples.batch_folder ./videos/

# С фильтром по расширению + форс-перезапись
python -m examples.batch_folder ./videos/ --pattern "*.mp4" --force --language ru

# Все .srt в отдельную папку
python -m examples.batch_folder ./videos/ --output ./transcripts/
```

Скрипт пропускает уже обработанные файлы (если `.srt` рядом существует), показывает прогресс и среднее время на файл.

### Из URL (TikTok / YouTube / Reels / Twitter / любой что yt-dlp умеет)

```bash
# TikTok
python -m examples.from_url "https://www.tiktok.com/@user/video/1234567890123456789"

# YouTube с указанием языка
python -m examples.from_url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --language en

# Instagram Reel в конкретную папку, без удаления mp3
python -m examples.from_url "https://www.instagram.com/reel/Cv1AbcXXXX/" --output ./content/ --keep-audio
```

### Подкаст с разметкой спикеров

```bash
# Получить HF token (бесплатно): https://huggingface.co/settings/tokens
# Принять условия: https://huggingface.co/pyannote/speaker-diarization-3.1
export HF_TOKEN=hf_xxxxxxxx

# Подкаст 1-на-1 (хост + гость)
python -m examples.podcast_diarize podcast.mp3 --speakers 2

# Дискуссионный — диапазон спикеров
python -m examples.podcast_diarize debate.mp3 --min-speakers 2 --max-speakers 5

# С указанием языка и модели
python -m examples.podcast_diarize interview.wav --speakers 2 --language ru --model large-v3
```

### Голосовая диктовка

```bash
# Одноразовая настройка — создаст конфиг в ~/.config/whisper-skill/voice_dictation.json
python -m examples.voice_dictation --setup

# Запуск (висит в трее, слушает Ctrl+Shift+Space по дефолту)
python -m examples.voice_dictation

# Со своим конфигом
python -m examples.voice_dictation --config my_dictation.json
```

Кастомизация через JSON — хоткей (любая комбинация `pynput`-формата), модель, режим `ptt` / `toggle`, auto-paste, бипы для feedback'а. Полные опции: [docs/voice-dictation.md](docs/voice-dictation.md).

#### Установка как Windows-приложение (autostart, иконка, ярлык)

Чтобы не запускать каждый раз руками из терминала:

```powershell
# 1) Сгенерить .ico из assets/icon.png (один раз)
python -m scripts.build_icon

# 2) Ярлык в меню «Пуск» (опционально + на рабочем столе)
powershell -ExecutionPolicy Bypass -File .\tools\install_shortcut.ps1
powershell -ExecutionPolicy Bypass -File .\tools\install_shortcut.ps1 -Desktop

# 3) Автостарт при логине пользователя
powershell -ExecutionPolicy Bypass -File .\tools\install_autostart.ps1

# Снять автостарт / удалить ярлык:
powershell -ExecutionPolicy Bypass -File .\tools\uninstall_autostart.ps1
powershell -ExecutionPolicy Bypass -File .\tools\install_shortcut.ps1 -Remove
```

Под капотом — `launcher\voice_dictation_silent.vbs`, который тихо
стартует `pythonw.exe` из venv (без окна терминала). Скрипт ожидает
venv по `~\.venvs\whisper`; если у тебя другое расположение — поправь
путь в .vbs. Состояние диктовки видно по tray-иконке: серая = idle,
красная точка = идёт запись, оранжевая = транскрибируем.

### Сабы прямо в MP4

```bash
# Базовый TikTok-стиль
python -m examples.bake_subs input.mp4

# Указать стиль и язык
python -m examples.bake_subs input.mp4 --style youtube_shorts --language en --output ready.mp4

# Подкаст-клип, по 3 слова на строку
python -m examples.bake_subs clip.mp4 --style podcast_clip --max-words-per-line 3

# Несколько вариантов разом — для A/B
for style in tiktok youtube_shorts reels minimal; do
  python -m examples.bake_subs input.mp4 --style $style --output "out_${style}.mp4"
done
```

---

## 💰 Сколько экономит

OpenAI Whisper API: **$0.006/мин**.

Локальный Whisper: **$0** после первой установки.

| Сценарий | Аудио в день | OpenAI API/мес | Локально |
|---|---|---|---|
| Творец shorts (10 виралок/день) | 10 мин | $1.80 | $0 |
| Подкастер (4 эп/нед × 1 час) | 35 мин | $6 | $0 |
| Контент-creator full-time | 5 ч | $54 | $0 |
| Агентство (10 клиентов) | 10 ч | $108 | $0 |
| Студия дубляжа (50 ч/нед) | 7 ч | $72 | $0 |

Плюс:
- **Приватность** — записи не уходят в OpenAI
- **Никаких лимитов** — обрабатывай хоть 1000 часов в день
- **Diarization** — на API её просто нет
- **Word-level timestamps** — без ограничений
- **Offline** — работает без интернета

Подробный расчёт: [docs/cost-comparison.md](docs/cost-comparison.md)

---

## 🌍 Поддержка языков

Whisper мультиязычный из коробки — **99 языков**, включая редкие.

Лучшая модель **`large-v3`** для всех языков. Облегчённая **`large-v3-turbo`** хороша на популярных (EN/ES/DE/FR/IT/PT/JP/ZH/RU), но проседает на редких (KK/UZ/TT/AR — потеря 5-10%).

WER (Word Error Rate) бенчмарки:

| Модель | EN | RU | KK |
|---|---|---|---|
| `tiny` | 12% | 35% | 50%+ |
| `small` | 6% | 18% | 30% |
| `medium` | 4% | 12% | 22% |
| `large-v3-turbo` | 2.5% | 11% | 22% |
| **`large-v3`** ⭐ | **2%** | **9%** | **15%** |

Полные бенчмарки + рекомендации: [methodology/quality-vs-speed.md](methodology/quality-vs-speed.md)

---

## 📚 Полная документация

### Установка под ОС
- [installation-mac.md](docs/installation-mac.md) — macOS (Apple Silicon / Intel / Homebrew)
- [installation-linux.md](docs/installation-linux.md) — Linux (NVIDIA CUDA / AMD ROCm / CPU)
- [installation-windows.md](docs/installation-windows.md) — Windows (WSL2 / нативно)

### Бэкенды
- [mlx-whisper.md](backends/mlx-whisper.md) — Apple Silicon
- [faster-whisper.md](backends/faster-whisper.md) — кроссплатформенный
- [whisper-cpp.md](backends/whisper-cpp.md) — без Python
- [whisperx.md](backends/whisperx.md) — diarization + alignment

### Killer features
- [voice-dictation.md](docs/voice-dictation.md) — push-to-talk, конфиги, autostart
- [subtitle-baker.md](docs/subtitle-baker.md) — стили, ASS-формат, кастомизация

### Гайды
- [diarization.md](docs/diarization.md) — разметка спикеров через pyannote
- [speed-tuning.md](docs/speed-tuning.md) — ускорение в 5-10x
- [cost-comparison.md](docs/cost-comparison.md) — local vs API по сценариям
- [known-issues.md](docs/known-issues.md) — типовые грабли

### Модели и методология
- [models/README.md](models/README.md) — выбор модели под задачу
- [quality-vs-speed.md](methodology/quality-vs-speed.md) — бенчмарки + матрица решений

---

## 🗂️ Структура репозитория

```
whisper-skill/
├── SKILL.md                          # Точка входа для AI-ассистента (frontmatter + правила)
├── README.md                         # Этот файл (для людей)
├── wizard.py                         # 🧙 Интерактивный мастер
├── scripts/
│   └── detect_env.py                 # Авто-детектор железа (под капотом wizard'а)
├── backends/                         # Карточки 4 бэкендов с командами установки
│   ├── mlx-whisper.md
│   ├── faster-whisper.md
│   ├── whisper-cpp.md
│   └── whisperx.md
├── models/
│   └── README.md                     # Какую модель брать — таблицы и бенчмарки
├── docs/
│   ├── installation-mac.md           # Установка под Mac
│   ├── installation-linux.md         # Установка под Linux
│   ├── installation-windows.md       # Установка под Windows
│   ├── voice-dictation.md            # 🎤 Killer feature #1
│   ├── subtitle-baker.md             # 🎬 Killer feature #2
│   ├── diarization.md                # Разметка спикеров
│   ├── speed-tuning.md               # Ускорение
│   ├── cost-comparison.md            # vs OpenAI API
│   └── known-issues.md               # Грабли
├── examples/                         # Готовые рабочие скрипты
│   ├── common.py                     # Универсальная обвязка (auto-backend, унифицированный output)
│   ├── transcribe_one.py             # Один файл → SRT/VTT/TXT/JSON
│   ├── batch_folder.py               # Пакетная обработка папки
│   ├── from_url.py                   # URL TikTok/YouTube/etc → транскрипт
│   ├── podcast_diarize.py            # Подкаст с разметкой спикеров
│   ├── voice_dictation.py            # 🎤 Push-to-talk диктовка (tray app)
│   └── bake_subs.py                  # 🎬 Вшить сабы в MP4
└── methodology/
    └── quality-vs-speed.md           # Шпаргалка «задача → модель → железо»
```

---

## 🤝 Подключение к Claude API напрямую (для своих ботов)

Если строишь свой агент / бота / автоматизацию через прямой вызов Anthropic SDK:

```python
import os
from pathlib import Path
from anthropic import Anthropic

REPO = Path(__file__).resolve().parent.parent  # путь к whisper-skill

def load_skill_context() -> str:
    """SKILL.md + ключевые карточки в один контекст."""
    parts = [(REPO / "SKILL.md").read_text(encoding="utf-8")]
    for f in [
        "backends/faster-whisper.md",
        "backends/mlx-whisper.md",
        "models/README.md",
        "docs/known-issues.md",
    ]:
        parts.append(f"\n# === {f} ===\n\n")
        parts.append((REPO / f).read_text(encoding="utf-8"))
    return "\n\n".join(parts)


client = Anthropic()
skill_context = load_skill_context()

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=2048,
    system=[
        {"type": "text", "text": "Ты помощник по локальной транскрибации через Whisper."},
        {
            "type": "text",
            "text": skill_context,
            "cache_control": {"type": "ephemeral"},  # ⭐ кешируем skill — снижает стоимость в 10x
        },
    ],
    messages=[
        {"role": "user", "content": "У меня Mac M2 16GB. Какой бэкенд ставить и какой моделью пользоваться?"}
    ],
)

print(response.content[0].text)
print(f"Cache hit: {response.usage.cache_read_input_tokens} tokens")
```

**Главная фишка** — Anthropic prompt caching снижает стоимость skill-контекста в **10 раз** при повторных запросах в течение 5 минут. Без него каждый запрос будет тащить 30k токенов skill'а в полную цену.

---

## ❓ FAQ

### Whisper или OpenAI Whisper API — что лучше?

Зависит от объёма и приватности. Локально — выгоднее при >100 минут аудио в месяц, и обязательно если нужны diarization, word-level timestamps, или ты не хочешь грузить контент в OpenAI. См. [docs/cost-comparison.md](docs/cost-comparison.md).

### Какую модель брать?

По дефолту — `large-v3-turbo`. Для редких языков (казахский, узбекский, татарский) или translation-task — `large-v3`. См. [models/README.md](models/README.md).

### У меня нет GPU, заработает?

Да. Бери `faster-whisper` в режиме `compute_type="int8"`. На современном x86 8c CPU `large-v3-turbo` работает ~0.5x от realtime. Терпимо для коротких клипов, медленно для подкастов. Альтернатива — `whisper.cpp` с AVX2/AVX512 оптимизациями.

### Сколько модель весит на диске?

`large-v3-turbo` — 1.6 GB (или 800 MB в int8). Все модели лежат в `~/.cache/huggingface/hub/`, шарятся между бэкендами.

### Как ускорить инференс?

См. [docs/speed-tuning.md](docs/speed-tuning.md) — там 9 проверенных шагов. Главные: указывай язык явно, включай VAD-фильтр, используй `large-v3-turbo` вместо `large-v3`.

### Whisper галлюцинирует ("Спасибо за просмотр" в тишине). Как починить?

VAD-фильтр (`vad_filter=True` в faster-whisper). См. [docs/known-issues.md](docs/known-issues.md).

### Voice Dictation не работает на macOS

Чаще всего — не дано Accessibility-разрешение. `System Settings → Privacy & Security → Accessibility → добавить Terminal`. Перезапустить терминал. См. [docs/voice-dictation.md](docs/voice-dictation.md).

### Voice Dictation вместо вставки — просто копирует в clipboard

Если `auto_paste: false` в конфиге — это by design. Если `true`, но не работает — на macOS опять Accessibility-разрешение, на Linux Wayland — глобальные хоткеи частично сломаны (workaround в [docs/voice-dictation.md](docs/voice-dictation.md)).

### Сабы в MP4 — шрифт другой / не отрисовывается

Шрифт не установлен в системе. На Mac: `brew install --cask font-montserrat font-inter font-impact font-roboto`. На Linux: `sudo apt install fonts-montserrat fonts-inter fonts-roboto`. Или поменяй в `examples/bake_subs.py` стиль на тот шрифт что у тебя есть.

### Diarization путает спикеров

Близкие голоса. Помогает: фиксировать `num_speakers=N` если знаешь точно, denoise + normalize loudness через ffmpeg, использовать длинную запись (на коротком хуже). См. [docs/diarization.md](docs/diarization.md).

---

## 🛡️ Лицензия / TOS

- Whisper модели — **MIT**
- mlx-whisper, faster-whisper, whisperx, whisper.cpp — **open-source** (различные совместимые лицензии)
- pyannote (diarization) — **Apache 2.0**, требует согласия с условиями использования (бесплатно)
- yt-dlp — **Unlicense**

Сам скилл (этот репо) — **MIT**. Делай что хочешь, копируй, форкай, продавай — всё ок.

---

## 🚀 Дальше

- ⭐ Поставь star если зашло
- 🐛 Issues / pull requests welcome
- 💬 Любые предложения / new features → issues

## Лицензия

MIT — см. [LICENSE](LICENSE). Используй свободно, в том числе
коммерчески; при копировании сохраняй указание авторства.
