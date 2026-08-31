"""
Общая обвязка для примеров.

Решает две задачи:
1. Автовыбор бэкенда — определяет железо и подгружает оптимальный (mlx / faster-whisper / whisper.cpp)
2. Унифицированный интерфейс — `transcribe(audio_path, language)` возвращает одинаковую структуру вне зависимости от бэкенда

Использование:
    from examples.common import transcribe, save_srt
    result = transcribe("input.mp3", language="ru")
    save_srt(result, "output.srt")
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


# ─── Auto-detect available backends ─────────────────────────────────────────


def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _has_cuda() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


def _pick_backend() -> str:
    """Выбрать оптимальный установленный бэкенд."""
    forced = os.environ.get("WHISPER_BACKEND")
    if forced:
        return forced
    if _is_apple_silicon() and _has_module("mlx_whisper"):
        return "mlx"
    if _has_module("faster_whisper"):
        return "faster"
    if _has_module("whisperx"):
        return "whisperx"
    if _has_module("pywhispercpp"):
        return "cpp"
    raise RuntimeError(
        "Не найден ни один whisper-бэкенд. Запусти scripts/detect_env.py — "
        "он подскажет какой ставить под твоё железо."
    )


def _pick_device() -> str:
    if _has_cuda():
        return "cuda"
    if _is_apple_silicon():
        return "mps"   # для PyTorch (whisperx). Для mlx-whisper это вообще не используется.
    return "cpu"


def _pick_compute_type(device: str) -> str:
    if device == "cuda":
        return os.environ.get("WHISPER_COMPUTE_TYPE", "float16")
    return os.environ.get("WHISPER_COMPUTE_TYPE", "int8")


# ─── Unified output ─────────────────────────────────────────────────────────


@dataclass
class Word:
    word: str
    start: float
    end: float
    speaker: Optional[str] = None


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    words: list[Word] = field(default_factory=list)


@dataclass
class Result:
    text: str
    language: str
    segments: list[Segment]
    backend: str
    model: str


# ─── Transcribe (universal) ─────────────────────────────────────────────────


_loaded_models: dict[tuple, object] = {}


def transcribe(
    audio_path: str | Path,
    language: Optional[str] = None,
    model_name: Optional[str] = None,
    word_timestamps: bool = True,
    backend: Optional[str] = None,
    verbose: bool = False,
) -> Result:
    """
    Один файл → транскрибат. Универсально для всех бэкендов.

    audio_path     — путь к аудио/видео. Поддерживается всё что ffmpeg умеет.
    language       — "ru", "en", "kk", ... ; None = auto-detect (медленнее)
    model_name     — имя модели. None = "large-v3-turbo" (рекомендованный дефолт)
    word_timestamps — пословные метки (для CapCut-стиля сабов)
    backend        — "mlx" | "faster" | "whisperx" | "cpp" | None (auto)
    verbose        — печать прогресса
    """
    audio_path = str(Path(audio_path).resolve())
    if not Path(audio_path).exists():
        raise FileNotFoundError(audio_path)

    backend = backend or _pick_backend()
    model_name = model_name or os.environ.get("WHISPER_MODEL", "large-v3-turbo")

    if verbose:
        print(f"[whisper-skill] backend={backend} model={model_name} device={_pick_device()}")

    if backend == "mlx":
        return _transcribe_mlx(audio_path, language, model_name, word_timestamps, verbose)
    if backend == "faster":
        return _transcribe_faster(audio_path, language, model_name, word_timestamps, verbose)
    if backend == "whisperx":
        return _transcribe_whisperx(audio_path, language, model_name, word_timestamps, verbose)
    if backend == "cpp":
        return _transcribe_cpp(audio_path, language, model_name, word_timestamps, verbose)
    if backend == "openvino":
        return _transcribe_openvino(audio_path, language, model_name, word_timestamps, verbose)
    raise ValueError(f"unknown backend: {backend}")


def _transcribe_mlx(audio, lang, model_name, word_ts, verbose):
    import mlx_whisper

    repo = (
        model_name if "/" in model_name
        else f"mlx-community/whisper-{model_name}"
    )
    res = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=repo,
        language=lang,
        word_timestamps=word_ts,
        verbose=verbose,
    )
    segs = [
        Segment(
            start=s["start"], end=s["end"], text=s["text"],
            words=[Word(w["word"], w["start"], w["end"]) for w in s.get("words", [])],
        )
        for s in res["segments"]
    ]
    return Result(
        text=res["text"],
        language=res.get("language", lang or "?"),
        segments=segs,
        backend="mlx",
        model=model_name,
    )


def _transcribe_faster(audio, lang, model_name, word_ts, verbose):
    from faster_whisper import WhisperModel

    device = _pick_device() if _has_cuda() else "cpu"
    compute_type = _pick_compute_type(device)
    key = (model_name, device, compute_type)
    model = _loaded_models.get(key)
    if model is None:
        if verbose:
            print(f"[whisper-skill] loading {model_name} on {device}/{compute_type}...")
        cpu_threads = int(os.environ.get("WHISPER_CPU_THREADS", os.cpu_count() or 4))
        model = WhisperModel(model_name, device=device, compute_type=compute_type, cpu_threads=cpu_threads)
        _loaded_models[key] = model

    beam_size = int(os.environ.get("WHISPER_BEAM_SIZE", "5"))
    best_of = int(os.environ.get("WHISPER_BEST_OF", "5"))
    condition_on_prev = os.environ.get("WHISPER_CONDITION_ON_PREV", "1") != "0"
    # Затравка задаёт модели язык и алфавит. Без неё Whisper на коротких
    # репликах иногда сваливается в латиницу посреди кириллицы
    # («Preвет» вместо «Привет») даже при принудительном language.
    initial_prompt = os.environ.get("WHISPER_INITIAL_PROMPT") or None
    segments_iter, info = model.transcribe(
        audio,
        language=lang,
        word_timestamps=word_ts,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        beam_size=beam_size,
        best_of=best_of,
        condition_on_previous_text=condition_on_prev,
        initial_prompt=initial_prompt,
    )
    segs: list[Segment] = []
    text_parts: list[str] = []
    for s in segments_iter:
        words = []
        for w in (s.words or []):
            words.append(Word(word=w.word, start=w.start, end=w.end))
        seg = Segment(start=s.start, end=s.end, text=s.text, words=words)
        segs.append(seg)
        text_parts.append(s.text)

    text = "".join(text_parts).strip()

    # На неразборчивом звуке Whisper иногда возвращает саму затравку как
    # результат. Для диктовки это означает мусорную вставку в документ,
    # поэтому эхо глушим — пустой результат честнее выдуманного.
    if initial_prompt and text and _is_prompt_echo(text, initial_prompt):
        text, segs = "", []

    return Result(
        text=text,
        language=info.language,
        segments=segs,
        backend="faster",
        model=model_name,
    )


def _normalize_for_echo(s: str) -> str:
    return "".join(c.lower() for c in s if c.isalnum() or c.isspace()).split()


def _is_prompt_echo(text: str, prompt: str) -> bool:
    """Результат целиком состоит из слов затравки и идёт их подпоследовательностью."""
    t = _normalize_for_echo(text)
    p = _normalize_for_echo(prompt)
    if not t or not p:
        return False
    # Одно-два слова глушить нельзя: «диктовка» может быть настоящей репликой.
    # Эхо затравки всегда длиннее.
    if len(t) < 3:
        return False
    joined_t, joined_p = " ".join(t), " ".join(p)
    return joined_t in joined_p


def _transcribe_whisperx(audio, lang, model_name, word_ts, verbose):
    import whisperx

    device = _pick_device()
    if device == "mps":  # whisperx не поддерживает MPS
        device = "cpu"
    compute_type = _pick_compute_type(device)

    key = ("whisperx", model_name, device, compute_type)
    model = _loaded_models.get(key)
    if model is None:
        model = whisperx.load_model(model_name, device, compute_type=compute_type)
        _loaded_models[key] = model

    audio_arr = whisperx.load_audio(audio)
    res = model.transcribe(audio_arr, batch_size=16, language=lang)
    if word_ts and res.get("segments"):
        try:
            align_model, metadata = whisperx.load_align_model(
                language_code=res["language"], device=device
            )
            res = whisperx.align(
                res["segments"], align_model, metadata, audio_arr, device,
                return_char_alignments=False,
            )
        except Exception as e:
            if verbose:
                print(f"[whisper-skill] alignment skipped: {e}")

    segs = []
    text_parts = []
    for s in res.get("segments", []):
        words = [Word(w["word"], w.get("start", 0.0), w.get("end", 0.0)) for w in s.get("words", [])]
        seg = Segment(start=s["start"], end=s["end"], text=s["text"], words=words)
        segs.append(seg)
        text_parts.append(s["text"])

    return Result(
        text="".join(text_parts).strip(),
        language=res.get("language", lang or "?"),
        segments=segs,
        backend="whisperx",
        model=model_name,
    )


_OV_WHISPER_WINDOW_S = 30.0     # архитектурный лимит Whisper
_OV_PACK_WINDOW_S = 28.0        # окно для упаковки VAD-сегментов (margin от 30s)
_OV_SEGMENT_PAD_S = 0.1
_OV_VAD_WARNED = False


def _ov_load_vad():
    """Опциональный silero-vad для long-form. None если не установлен."""
    try:
        from silero_vad import load_silero_vad
        return load_silero_vad()
    except Exception:
        return None


def _ov_vad_segments(audio, vad_model, sr=16000):
    """silero-vad → [(start_s, end_s), ...]."""
    import torch
    from silero_vad import get_speech_timestamps
    audio_t = torch.from_numpy(audio).float()
    ts = get_speech_timestamps(
        audio_t, vad_model,
        threshold=0.5,
        min_speech_duration_ms=250,
        min_silence_duration_ms=500,
        sampling_rate=sr,
        return_seconds=True,
    )
    return [(t["start"], t["end"]) for t in ts]


def _ov_pack_windows(segments, total_s, window_s=_OV_PACK_WINDOW_S):
    """Greedy-упаковка VAD-сегментов в окна ≤ window_s.
    Сегменты длиннее window_s режутся насильно (фраза без пауз)."""
    if not segments:
        return []
    windows: list[tuple[float, float]] = []
    win_start, win_end = None, None
    for seg_start, seg_end in segments:
        if seg_end - seg_start > window_s:
            if win_start is not None:
                windows.append((win_start, win_end))
                win_start, win_end = None, None
            cur = seg_start
            while cur < seg_end:
                cut = min(cur + window_s, seg_end)
                windows.append((cur, cut))
                cur = cut
            continue
        if win_start is None:
            win_start, win_end = seg_start, seg_end
        elif seg_end - win_start <= window_s:
            win_end = seg_end
        else:
            windows.append((win_start, win_end))
            win_start, win_end = seg_start, seg_end
    if win_start is not None:
        windows.append((win_start, win_end))
    # Расширяем края на _OV_SEGMENT_PAD_S чтобы не отрезать слова
    return [(max(0.0, s - _OV_SEGMENT_PAD_S),
             min(total_s, e + _OV_SEGMENT_PAD_S)) for s, e in windows]


def _ov_decode_window(audio_chunk, model, processor, lang, max_new):
    inputs = processor(audio_chunk, sampling_rate=16000, return_tensors="pt")
    gen = model.generate(
        inputs.input_features,
        language=lang,
        task="transcribe",
        max_new_tokens=max_new,
    )
    return processor.batch_decode(gen, skip_special_tokens=True)[0].strip()


def _transcribe_openvino(audio, lang, model_name, word_ts, verbose):
    """OpenVINO бэкенд — для Intel CPU/iGPU/NPU.

    Модель ищется в ~/.cache/openvino-whisper/whisper-{model_name}-ov/.
    Конвертацию делает scripts/convert_openvino.py (запускается один раз).

    Long-form (>30s): если установлен silero-vad — режем по паузам и
    декодируем окна по 28s по очереди. Без silero-vad — single pass
    (Whisper обрежет до первых 30s; печатается warning).

    Контролируется env vars:
        WHISPER_OV_DEVICE  — GPU (default), NPU, CPU, AUTO
        WHISPER_OV_DIR     — переопределение пути к локальным IR-моделям
    """
    import soundfile as sf
    import numpy as np
    from optimum.intel import OVModelForSpeechSeq2Seq
    from transformers import AutoProcessor

    device = os.environ.get("WHISPER_OV_DEVICE", "GPU")
    base_dir = Path(os.environ.get(
        "WHISPER_OV_DIR",
        Path.home() / ".cache" / "openvino-whisper",
    ))
    model_dir = base_dir / f"whisper-{model_name}-ov"

    if not model_dir.exists():
        raise RuntimeError(
            f"OpenVINO IR модель не найдена: {model_dir}\n"
            f"Сконвертируй: python scripts/convert_openvino.py {model_name}"
        )

    key = ("openvino", str(model_dir), device)
    cached = _loaded_models.get(key)
    if cached is None:
        if verbose:
            print(f"[whisper-skill] loading OpenVINO model on {device}...")
        processor = AutoProcessor.from_pretrained(str(model_dir))
        model = OVModelForSpeechSeq2Seq.from_pretrained(
            str(model_dir), device=device, compile=True
        )
        cached = (model, processor)
        _loaded_models[key] = cached
    model, processor = cached

    audio_arr, sr = sf.read(audio, dtype="float32")
    if audio_arr.ndim > 1:
        audio_arr = audio_arr.mean(axis=1)
    if sr != 16000:
        import scipy.signal as sps
        audio_arr = sps.resample_poly(audio_arr, 16000, sr).astype("float32")

    total_s = len(audio_arr) / 16000.0
    max_new = int(os.environ.get("WHISPER_OV_MAX_NEW_TOKENS", "440"))

    # Long-form path: audio > 30s + silero-vad доступен
    vad_model = None
    if total_s > _OV_WHISPER_WINDOW_S:
        vad_model = _ov_load_vad()
        global _OV_VAD_WARNED
        if vad_model is None and not _OV_VAD_WARNED:
            print(
                f"[whisper-skill] WARNING: audio is {total_s:.0f}s but silero-vad "
                "is not installed. Whisper will only transcribe the first 30s. "
                "Install: pip install silero-vad",
                file=sys.stderr,
            )
            _OV_VAD_WARNED = True

    if vad_model is not None and total_s > _OV_WHISPER_WINDOW_S:
        segments = _ov_vad_segments(audio_arr, vad_model)
        windows = _ov_pack_windows(segments, total_s)
        if not windows:
            return Result(text="", language=lang or "?", segments=[],
                          backend="openvino", model=model_name)
        segs: list[Segment] = []
        text_parts: list[str] = []
        for w_start, w_end in windows:
            chunk = audio_arr[int(w_start * 16000):int(w_end * 16000)]
            t = _ov_decode_window(chunk, model, processor, lang, max_new)
            if t:
                segs.append(Segment(start=w_start, end=w_end, text=t))
                text_parts.append(t)
        return Result(
            text=" ".join(text_parts).strip(),
            language=lang or "?",
            segments=segs,
            backend="openvino",
            model=model_name,
        )

    # Single-pass path: ≤30s или нет silero-vad
    text = _ov_decode_window(audio_arr, model, processor, lang, max_new)
    seg = Segment(start=0.0, end=float(total_s), text=text)
    return Result(
        text=text,
        language=lang or "?",
        segments=[seg],
        backend="openvino",
        model=model_name,
    )


def _transcribe_cpp(audio, lang, model_name, word_ts, verbose):
    from pywhispercpp.model import Model

    key = ("cpp", model_name)
    model = _loaded_models.get(key)
    if model is None:
        model = Model(model_name)
        _loaded_models[key] = model

    segments = model.transcribe(audio, language=lang or "auto")
    segs = [
        Segment(start=s.t0 / 100.0, end=s.t1 / 100.0, text=s.text)
        for s in segments
    ]
    return Result(
        text="\n".join(s.text for s in segs).strip(),
        language=lang or "?",
        segments=segs,
        backend="cpp",
        model=model_name,
    )


# ─── Output writers ─────────────────────────────────────────────────────────


def _ts(seconds: float, comma: bool = True) -> str:
    """1234.567 → 00:20:34,567"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    sep = "," if comma else "."
    return f"{h:02d}:{m:02d}:{int(s):02d}{sep}{int((s - int(s)) * 1000):03d}"


def save_srt(result: Result, out_path: str | Path) -> None:
    out_path = Path(out_path)
    with out_path.open("w", encoding="utf-8") as f:
        for i, seg in enumerate(result.segments, start=1):
            speaker_prefix = f"{seg.speaker}: " if seg.speaker else ""
            f.write(f"{i}\n")
            f.write(f"{_ts(seg.start)} --> {_ts(seg.end)}\n")
            f.write(f"{speaker_prefix}{seg.text.strip()}\n\n")


def save_vtt(result: Result, out_path: str | Path) -> None:
    out_path = Path(out_path)
    with out_path.open("w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for seg in result.segments:
            speaker_prefix = f"<v {seg.speaker}>" if seg.speaker else ""
            f.write(f"{_ts(seg.start, comma=False)} --> {_ts(seg.end, comma=False)}\n")
            f.write(f"{speaker_prefix}{seg.text.strip()}\n\n")


def save_txt(result: Result, out_path: str | Path) -> None:
    Path(out_path).write_text(result.text, encoding="utf-8")


def save_json(result: Result, out_path: str | Path) -> None:
    payload = {
        "text": result.text,
        "language": result.language,
        "backend": result.backend,
        "model": result.model,
        "segments": [
            {
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "speaker": s.speaker,
                "words": [
                    {"word": w.word, "start": w.start, "end": w.end, "speaker": w.speaker}
                    for w in s.words
                ],
            }
            for s in result.segments
        ],
    }
    Path(out_path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ─── Audio extraction (yt-dlp) ──────────────────────────────────────────────


def download_audio_from_url(url: str, out_dir: str | Path = ".") -> Path:
    """Скачать аудио из TikTok / YouTube / Reels через yt-dlp.

    Возвращает путь к скачанному файлу (mp3 или m4a).
    """
    if subprocess.call(["which", "yt-dlp"], stdout=subprocess.DEVNULL) != 0:
        raise RuntimeError(
            "yt-dlp не найден. Установи: pip install yt-dlp"
        )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_template = out_dir / "%(id)s.%(ext)s"

    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", str(out_template),
        url,
    ]
    subprocess.run(cmd, check=True)

    # Найти скачанный файл
    files = sorted(out_dir.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise RuntimeError("Файл не скачался")
    return files[0]
