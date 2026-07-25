---
name: whisper-skill
description: Локальная транскрибация аудио и видео через Whisper, голосовая диктовка push-to-talk и вшивание субтитров в MP4. Подбирает бэкенд под железо, все языки, без OpenAI API. На машине Лёши OpenVINO-стек уже развёрнут — второй ставить не надо.
---

# Whisper Skill — локальная транскрибация без OpenAI API

Этот скилл учит Claude правильно ставить и использовать Whisper локально — на ноуте, маке, серваке, без всякого OpenAI API. Поддерживает все ~99 языков (Whisper мультиязычен из коробки), все ОС, и автоматически подбирает оптимальный путь под конкретное железо.

> 💰 **Сколько экономим**: OpenAI Whisper API стоит **$0.006/мин**. Если транскрибируешь 5 часов в день — это **$108/мес**. Локальная установка — **$0** после первой загрузки модели (~3 GB).

## ⚠️ На машине Лёши стек уже стоит — не ставить второй

Intel Core Ultra (Meteor Lake), есть iGPU + NPU. Готовый OpenVINO-стек уже развёрнут.
**Не создавать второй venv с `faster-whisper` ради «быстрого старта»** и не гонять `wizard.py` —
использовать существующий. Детали окружения, пути к моделям и рабочий пайплайн:
[ENVIRONMENT-alexey.md](ENVIRONMENT-alexey.md).

Разделы ниже (детектор железа, wizard, выбор бэкенда) — для чужих машин и новых установок.

## Как пользоваться

### Шаг 0 — Самый простой путь: интерактивный мастер

Если пользователь не хочет читать документацию — **запусти мастер**, он спросит что хочешь делать и сам всё поставит:

```bash
python wizard.py
```

Мастер задаёт 3 вопроса (что делать / какая ОС / поставить?) и автоматически:
- определяет железо
- ставит ffmpeg + нужный whisper-бэкенд + модель
- настраивает выбранную фичу (диктовка / сабы / транскрибация / подкасты)
- прогоняет smoke-test

Идеален для не-технарей или быстрого старта.

### Шаг 1 — Если хочешь руками: определи железо

```bash
python scripts/detect_env.py
```

Скрипт сам:
- определит ОС (macOS / Linux / Windows / WSL)
- определит CPU (Apple Silicon / x86_64 / ARM)
- найдёт GPU (NVIDIA CUDA / AMD ROCm / Apple Metal / нет)
- посмотрит сколько RAM / VRAM
- подберёт **оптимальный бэкенд + модель** + выдаст команды установки

Дальше работаешь с тем что он рекомендовал. Не угадывай — **всегда запускай детектор первым**.

### Шаг 2 — поставь рекомендованный бэкенд

Открой соответствующую карточку в `backends/` и следуй инструкции. Вкратце:

| Железо | Рекомендованный бэкенд | Карточка |
|---|---|---|
| Mac M1/M2/M3/M4 | **mlx-whisper** (нативный Metal) | [backends/mlx-whisper.md](backends/mlx-whisper.md) |
| Linux + NVIDIA GPU | **faster-whisper** (CUDA) | [backends/faster-whisper.md](backends/faster-whisper.md) |
| Windows + NVIDIA GPU | **faster-whisper** через WSL2 | [backends/faster-whisper.md](backends/faster-whisper.md) |
| Intel Core Ultra (Meteor Lake+) / Intel Arc | **openvino** (нативный iGPU + NPU) | [backends/openvino.md](backends/openvino.md) |
| Любая ОС, нет GPU, не Mac, не Intel Ultra | **whisper.cpp** (CPU-оптимизированный) | [backends/whisper-cpp.md](backends/whisper-cpp.md) |
| Нужны спикеры (diarization) | **whisperx** (faster-whisper + pyannote) | [backends/whisperx.md](backends/whisperx.md) |

### Шаг 3 — выбери модель под задачу

Whisper моделей много, **не запускай `large` если можно `turbo`**. Открой [models/README.md](models/README.md) — там таблица «задача → модель → vram → скорость → качество».

Быстрая шпаргалка:
- **TikTok/Reels транскрибация (15-60 сек)** → `large-v3-turbo` (8x быстрее, потеря качества <2%)
- **Подкасты (1-3 ч) с RU + EN** → `large-v3`
- **Long-form, многоязычка с редкими языками** → `large-v3` (turbo плохо работает с редкими)
- **Слабое железо, ноут без GPU** → `base` или `small` (компромисс)

### Шаг 4 — запусти готовый пример

Под типовые сценарии есть рабочие скрипты в [examples/](examples/):

```bash
# === ОСНОВНЫЕ ===
# Один файл → SRT/VTT/TXT
python -m examples.transcribe_one input.mp3

# Папка с видео → пакетная обработка
python -m examples.batch_folder ./videos/

# Из URL (TikTok/YouTube/Reels) → транскрибат через yt-dlp
python -m examples.from_url "https://www.tiktok.com/@user/video/123..."

# Подкаст с двумя дикторами (Speaker A / Speaker B)
python -m examples.podcast_diarize podcast.mp3

# === KILLER FEATURES ===
# 🎤 Push-to-talk диктовка (заменяет Superwhisper / Wispr Flow за $0)
python -m examples.voice_dictation

# 🎬 Вшить сабы в MP4 (CapCut-стиль с подсветкой текущего слова)
python -m examples.bake_subs input.mp4 --style tiktok --output ready.mp4
```

Все примеры используют общую обвязку `examples/common.py`: автовыбор устройства, кэш, совместимость со всеми бэкендами.

### Killer features подробно

| Feature | Команда | Что заменяет | Сколько экономит |
|---|---|---|---|
| **Voice Dictation** | `python -m examples.voice_dictation` | Superwhisper, Wispr Flow, Aqua Voice | $8-12/мес |
| **Subtitle Baker** | `python -m examples.bake_subs` | CapCut Pro, Adobe Premiere | $10-50/мес |
| **Interactive Wizard** | `python wizard.py` | — | прости́т 30 минут гугления |

Подробнее:
- [docs/voice-dictation.md](docs/voice-dictation.md) — push-to-talk диктовка во любое поле
- [docs/subtitle-baker.md](docs/subtitle-baker.md) — стилизованные сабы в видео

## Общие правила

### Язык — авто-детект, но указывай если знаешь

Whisper умеет автоопределять язык, но это **дорого** (5-10% времени) и иногда ошибается на коротких клипах. Если знаешь — указывай явно (`language="ru"`). Это и быстрее, и точнее.

### Препроцессинг аудио

- **Whisper нативно работает с 16 kHz mono**. Если у тебя 48 kHz stereo — он сам ресемплит, но это лишнее время. Лучше прогнать через ffmpeg один раз: `ffmpeg -i input.mp4 -ar 16000 -ac 1 output.wav`
- **Тихие места и пустоты** — ставь VAD (Voice Activity Detection) фильтр: `vad_filter=True` в faster-whisper. Это **критически ускоряет** на видео с длинными паузами или фоном без речи.
- **Музыка / шум** — Whisper плохо транскрибирует на фоне громкой музыки. Если поджимает — прогоняй через `Demucs` или `Spleaker` для отделения вокала.

### Word-level timestamps — для авто-сабов в стиле CapCut

Если делаешь видео с пословными субтитрами (как TikTok/CapCut стиль), нужны точные метки на каждое слово, а не на сегмент. Это умеют:
- **whisperx** — встроено (по дефолту `align_model` от wav2vec2)
- **faster-whisper** — флаг `word_timestamps=True`
- **mlx-whisper** — флаг `word_timestamps=True`
- **whisper.cpp** — `--max-len 1` или JSON-режим

См. [docs/word-level-subs.md](docs/word-level-subs.md).

### Длинное аудио — chunking

Whisper максимум обрабатывает 30-секундные окна. Все нормальные бэкенды (faster-whisper, whisperx) сами разбивают длинные файлы на чанки и склеивают результат. Не пытайся вручную нарезать.

### Качество RU vs EN

- На английском Whisper лучшее что есть. Качество 90-95% как у профессионального стенографиста.
- На русском — `large-v3` ставит хорошо (85-90%). `turbo` хуже на русском чем `large-v3` (~3-5% потери). На редких языках (казахский, узбекский, татарский) — только `large-v3`, остальные модели падают.
- Бенчмарки по языкам — в [methodology/quality-vs-speed.md](methodology/quality-vs-speed.md).

### Speaker diarization (только если 2+ человек в записи)

Diarization = «кто-что-сказал». Для подкастов / интервью / совещаний.

- **Не нужна** для одного спикера (подавляющее большинство TikTok/Reels) — пропускай.
- **Нужна** для подкастов / интервью / Zoom-записей.
- Включается через **whisperx** (`diarize=True`) или [docs/diarization.md](docs/diarization.md).
- Требует **бесплатного Hugging Face токена** (для модели `pyannote/speaker-diarization-3.1`).

## Под-документы

| Файл | Когда читать |
|------|--------------|
| [wizard.py](wizard.py) | **Самый простой старт** — интерактивный мастер настройки |
| [scripts/detect_env.py](scripts/detect_env.py) | Авто-определение железа + рекомендации |
| [backends/faster-whisper.md](backends/faster-whisper.md) | Linux/Windows + (GPU или нет) |
| [backends/whisper-cpp.md](backends/whisper-cpp.md) | Без Python / минимум зависимостей |
| [backends/whisperx.md](backends/whisperx.md) | Нужна diarization или word-timestamps |
| [backends/mlx-whisper.md](backends/mlx-whisper.md) | Mac M1+ |
| [backends/openvino.md](backends/openvino.md) | Intel Core Ultra / Intel Arc — задействует iGPU + NPU |
| [models/README.md](models/README.md) | Выбор модели под задачу |
| [docs/installation-mac.md](docs/installation-mac.md) | Установка под Mac |
| [docs/installation-linux.md](docs/installation-linux.md) | Установка под Linux |
| [docs/installation-windows.md](docs/installation-windows.md) | Установка под Windows |
| [docs/voice-dictation.md](docs/voice-dictation.md) | 🎤 Push-to-talk диктовка во любое поле |
| [docs/subtitle-baker.md](docs/subtitle-baker.md) | 🎬 Сабы прямо в MP4 (CapCut-style) |
| [docs/diarization.md](docs/diarization.md) | Разметка спикеров |
| [docs/speed-tuning.md](docs/speed-tuning.md) | Ускорить инференс |
| [docs/cost-comparison.md](docs/cost-comparison.md) | «А зачем мне локально если есть API?» |
| [docs/known-issues.md](docs/known-issues.md) | Грабли |
| [methodology/quality-vs-speed.md](methodology/quality-vs-speed.md) | Бенчмарки и tradeoff'ы |

## Типичные ошибки и как их чинить

### `RuntimeError: CUDA out of memory`

Модель слишком большая для VRAM. Варианты:
1. Перейти на меньшую модель (`large-v3` → `medium` или `large-v3-turbo`)
2. Уменьшить `batch_size` (с 16 до 8 или 4)
3. Использовать `compute_type="int8_float16"` (4x экономия VRAM, минус 1-2% качества)

### `Detected language: en` для русского текста

Whisper иногда «слышит» русский как английский на коротких клипах. Решение:
1. Указывать язык явно: `model.transcribe(audio, language="ru")`
2. Или: брать модель `large-v3` (она лучше определяет язык чем `turbo`)

### Плохое качество на TikTok/Reels с громкой музыкой

Whisper не выделяет голос из музыки. Перед транскрибацией прогоняй через **Demucs**:
```bash
demucs --two-stems=vocals input.mp3
# → выходит no_vocals.wav и vocals.wav, дальше только vocals.wav в Whisper
```

### Странные галлюцинации в тишине ("Спасибо за просмотр", "Подписывайтесь")

Whisper в тишине придумывает текст из тренировочных данных. Решение — **VAD-фильтр** (Voice Activity Detection):
- В faster-whisper: `vad_filter=True`
- В whisperx: встроено
- В whisper.cpp: `--vad`

**Постобработка, если артефакты всё же просочились** (особенно в OpenVINO, где VAD не всегда спасает): прогнать готовый чистильщик —
```bash
python -m examples.clean_whisper_artifacts <файл-или-папка>   # --dry-run покажет, что вырежет
```
Вырезает семейство ютуб-титров ("Субтитры создавал…", "Редактор субтитров А.X Корректор А.Y", "Спасибо за просмотр", "Подписывайтесь на канал" и т.п.) по паттернам, печатает удалённое для аудита, идемпотентен. Скрипт: [examples/clean_whisper_artifacts.py](examples/clean_whisper_artifacts.py). `transcribe_ov_longform` зовёт его на выходе автоматически. Новые паттерны добавлять в `_PATTERNS`.

### Текст без точек и заглавных букв

`large-v3` обычно ставит пунктуацию хорошо. Если нет:
- Попробуй `condition_on_previous_text=True`
- Или прогоняй после-обработку через [methodology/post-processing.md](methodology/post-processing.md) (punctuator-модели или LLM для расстановки)

### Установка падает с `Pytorch not found / cuda mismatch`

Самая частая боль на Linux/Windows. Решение пошагово в [docs/installation-linux.md](docs/installation-linux.md) или [docs/installation-windows.md](docs/installation-windows.md). Главное — **не ставь PyTorch и CUDA отдельно** — пусть менеджер пакетов сделает это сам через правильную команду.

### `pip install whisper` ставит не то

`pip install whisper` ставит **другой пакет** (старый репозиторий). Правильно:
- Faster-whisper: `pip install faster-whisper`
- Original OpenAI: `pip install openai-whisper` (но faster-whisper в 4-12x быстрее, original не нужен)
- whisperx: `pip install whisperx`
- mlx-whisper: `pip install mlx-whisper`

## После транскрибации — что дальше?

Whisper отдаёт текст. Дальше типовые next steps:

1. **Переписать текст / суммаризовать** — отдельная задача (LLM поверх транскрибата).
2. **Сабы в видео** — через ffmpeg + SRT-файл из Whisper. См. [examples/burn_subs.py](examples/burn_subs.py) (если делал).
3. **Сохранить в БД / Notion / Sheets** — стандартный pipeline, в [examples/](examples/) есть шаблоны.
4. **Перевод на другой язык** — Whisper умеет переводить **только в английский** (флаг `task="translate"`). Для перевода RU → DE — отдельный шаг через LLM или DeepL.

## Что вне скоупа

- **TTS / Voice cloning** — это другая история (ElevenLabs, Coqui XTTS) — отдельный скилл если будет
- **Дообучение Whisper на свой домен** — теоретически возможно, но 99% задач решает выбор правильной модели
- **Перевод на любой язык** — Whisper умеет только → EN. Для остального LLM/DeepL
- **Lip-sync / dubbing** — отдельная тема (Sync.so, Wav2Lip)
