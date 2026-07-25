# Окружение Лёши — Whisper через OpenVINO

Машина: Intel Core Ultra (Meteor Lake), iGPU Intel Arc + NPU AI Boost.
Стек развёрнут и рабочий. Второй venv не ставить.

## Что уже есть

- **Venv:** `C:/Users/User/.venvs/whisper/Scripts/python.exe`
  (`openvino 2026.1.0`, `optimum-intel`, `transformers`, `faster-whisper` как fallback)
- **Готовые OV-модели:** `~/.cache/openvino-whisper/`
  - `whisper-large-v3-int8-ov` — дефолт, баланс скорости и качества
  - `whisper-large-v3-int4-ov` — когда нужна скорость
  - `whisper-large-v3-ov` (fp16) — когда нужно максимальное качество
- **Устройства OpenVINO:** `CPU`, `GPU` (Intel Arc iGPU), `NPU` (AI Boost).
  По умолчанию брать `GPU` — надёжнее NPU на длинных файлах.

## Пайплайн

1. **Конвертация.** Если файл не wav — `ffmpeg -ar 16000 -ac 1 in.m4a out.wav`.
   Pipeline `transformers` не читает `.m4a` через `ffmpeg_read` без явной конвертации.
2. **Имена файлов — только ASCII**, без кириллицы и пробелов. Иначе ломаются `ffprobe` и Python.
3. **Запуск:**

```python
OVModelForSpeechSeq2Seq.from_pretrained(MODEL_DIR, device="GPU", compile=True)

transformers.pipeline(
    "automatic-speech-recognition",
    ...,
    chunk_length_s=30,
    return_timestamps=True,
    ignore_warning=True,
    generate_kwargs={"language": "russian", "task": "transcribe"},
)
```

## Шаблон-скрипт

`alpha_solver_portal/docs/ideas/audio/transcribe_ov.py` — копировать в любой проект как есть.

Связанное: голосовая диктовка push-to-talk настроена отдельно, конфиг в `~/.config/whisper-skill`
(память `project_whisper_voice_dictation`).
