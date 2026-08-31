#!/usr/bin/env python3
"""
Whisper Stack — автодетектор железа.

Запусти один раз перед установкой Whisper. Скрипт сам определит:
  - ОС (macOS / Linux / Windows / WSL)
  - CPU (Apple Silicon / x86_64 / ARM)
  - GPU (NVIDIA CUDA / AMD ROCm / Apple Metal / нет)
  - RAM / VRAM
  - Версии Python / PyTorch / CUDA / ffmpeg

И выдаст рекомендованный бэкенд + модель + готовые команды установки.

Запуск:
    python scripts/detect_env.py

Зависимости (только из stdlib):
    нет — работает на чистом Python 3.8+
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

# ─── ANSI colors ────────────────────────────────────────────────────────────

USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    if not USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def green(t: str) -> str: return _c("32", t)
def yellow(t: str) -> str: return _c("33", t)
def red(t: str) -> str: return _c("31", t)
def blue(t: str) -> str: return _c("34", t)
def bold(t: str) -> str: return _c("1", t)
def dim(t: str) -> str: return _c("2", t)


# ─── Detection ──────────────────────────────────────────────────────────────


@dataclass
class Env:
    os_name: str = ""           # "macOS" / "Linux" / "Windows" / "WSL"
    os_version: str = ""
    arch: str = ""              # "arm64" / "x86_64"
    cpu_brand: str = ""         # "Apple M2 Pro" / "AMD Ryzen 9 5900X" / ...
    is_apple_silicon: bool = False
    is_intel_cpu: bool = False
    cpu_supports_avx2: bool = False
    cpu_supports_avx512: bool = False
    ram_gb: float = 0.0
    has_nvidia_gpu: bool = False
    nvidia_gpu_name: str = ""
    nvidia_vram_gb: float = 0.0
    cuda_version: str = ""
    has_amd_gpu: bool = False
    amd_gpu_name: str = ""
    rocm_version: str = ""
    has_apple_gpu: bool = False
    metal_supported: bool = False
    # Intel iGPU / NPU через OpenVINO
    has_intel_igpu: bool = False
    has_intel_npu: bool = False
    openvino_devices: list = field(default_factory=list)  # ['CPU','GPU','NPU']
    intel_igpu_name: str = ""
    python_version: str = ""
    pip_available: bool = False
    ffmpeg_installed: bool = False
    ffmpeg_version: str = ""


def detect_os(env: Env) -> None:
    sys_name = platform.system()
    if sys_name == "Darwin":
        env.os_name = "macOS"
        env.os_version = platform.mac_ver()[0]
    elif sys_name == "Linux":
        # Check if WSL
        try:
            with open("/proc/version") as f:
                if "microsoft" in f.read().lower():
                    env.os_name = "WSL"
                else:
                    env.os_name = "Linux"
        except Exception:
            env.os_name = "Linux"
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME"):
                        env.os_version = line.split("=", 1)[1].strip().strip('"')
                        break
        except Exception:
            env.os_version = platform.release()
    elif sys_name == "Windows":
        env.os_name = "Windows"
        env.os_version = platform.version()
    else:
        env.os_name = sys_name


def detect_cpu(env: Env) -> None:
    env.arch = platform.machine()

    if env.os_name == "macOS":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"], text=True
            ).strip()
            env.cpu_brand = out
            env.is_apple_silicon = "Apple" in out and any(
                k in out for k in ("M1", "M2", "M3", "M4", "M5")
            )
            env.is_intel_cpu = "Intel" in out
        except Exception:
            env.cpu_brand = platform.processor() or "unknown"
        # Apple Silicon — флаги CPU не нужны (другая ISA)
        # Для Intel Mac посмотрим cpu_features
        if env.is_intel_cpu:
            try:
                out = subprocess.check_output(
                    ["sysctl", "-n", "machdep.cpu.features",
                     "machdep.cpu.leaf7_features"], text=True
                ).upper()
                env.cpu_supports_avx2 = "AVX2" in out
                env.cpu_supports_avx512 = "AVX512" in out
            except Exception:
                pass
    elif env.os_name in ("Linux", "WSL"):
        try:
            with open("/proc/cpuinfo") as f:
                content = f.read()
                for line in content.splitlines():
                    if line.startswith("model name"):
                        env.cpu_brand = line.split(":", 1)[1].strip()
                        break
                env.is_intel_cpu = "Intel" in env.cpu_brand
                # Проверяем флаги один раз через весь файл
                upper = content.upper()
                env.cpu_supports_avx2 = " AVX2 " in upper
                env.cpu_supports_avx512 = " AVX512" in upper
        except Exception:
            env.cpu_brand = platform.processor() or "unknown"
    else:  # Windows
        # platform.processor() на Windows отдаёт "Intel64 Family 6 Model 186 ...",
        # без маркетингового имени — эвристика по "Core" на нём не срабатывает.
        # Настоящее имя процессора лежит в реестре.
        brand = ""
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as k:
                brand = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        except Exception:
            pass
        env.cpu_brand = brand or platform.processor() or "unknown"
        env.is_intel_cpu = "Intel" in env.cpu_brand or "Intel" in (platform.processor() or "")
        # Эвристика: Intel Core от Haswell (2013+) и все AMD Ryzen поддерживают AVX2.
        if env.is_intel_cpu and "Core" in env.cpu_brand and "Atom" not in env.cpu_brand:
            env.cpu_supports_avx2 = True
        elif "Ryzen" in env.cpu_brand or "EPYC" in env.cpu_brand:
            env.cpu_supports_avx2 = True


def detect_intel_openvino(env: Env) -> None:
    """Если установлен openvino — посмотрим какие устройства видны.

    Это путь #1 для определения Intel iGPU / NPU. Если openvino не стоит,
    пробуем определить через косвенные признаки (Intel Core Ultra / процессоры
    с iGPU 11-го поколения и новее).
    """
    # Шаг 1 — openvino.Core().available_devices если установлен
    try:
        import openvino as ov
        core = ov.Core()
        devices = list(core.available_devices)
        env.openvino_devices = devices
        env.has_intel_igpu = "GPU" in devices
        env.has_intel_npu = "NPU" in devices
        # Имя iGPU
        if env.has_intel_igpu:
            try:
                full_name = core.get_property("GPU", "FULL_DEVICE_NAME")
                env.intel_igpu_name = str(full_name)
            except Exception:
                env.intel_igpu_name = "Intel iGPU"
        return
    except ImportError:
        pass
    except Exception as e:
        # openvino установлен но не работает (драйвера, ошибки) — не падаем
        return

    # Шаг 2 — эвристика по имени CPU.
    # Intel Core Ultra (Meteor Lake, Lunar Lake, Arrow Lake) имеет iGPU + NPU.
    # Intel Core 11-го поколения и новее имеет Iris Xe.
    if not env.is_intel_cpu:
        return
    name = env.cpu_brand
    if "Core(TM) Ultra" in name or "Core Ultra" in name:
        env.has_intel_igpu = True
        env.has_intel_npu = True
        env.intel_igpu_name = "Intel Arc (Core Ultra)"
        return
    # Iris Xe — Tiger Lake (11th gen i3/i5/i7), Alder Lake (12th), и т.д.
    # Грубо: если "i3-11", "i5-11", "i7-11", "i3-12" и выше — iGPU есть.
    import re
    m = re.search(r"i[3579]-(\d{2,5})", name)
    if m:
        gen_str = m.group(1)
        # 1185G7 → 11, 1240P → 12, 13900K → 13. Берём первые 2 цифры.
        try:
            gen = int(gen_str[:2])
            if gen >= 11:
                env.has_intel_igpu = True
                env.intel_igpu_name = f"Intel Iris Xe (gen {gen})"
        except Exception:
            pass


def detect_ram(env: Env) -> None:
    try:
        if env.os_name == "macOS":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            env.ram_gb = round(int(out) / 1024**3, 1)
        elif env.os_name in ("Linux", "WSL"):
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        env.ram_gb = round(kb / 1024**2, 1)
                        break
        elif env.os_name == "Windows":
            # wmic вырезан из Windows 11 24H2+, поэтому идём через ctypes —
            # GlobalMemoryStatusEx есть в любой версии Windows.
            import ctypes

            class _MemStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            st = _MemStatus()
            st.dwLength = ctypes.sizeof(_MemStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                env.ram_gb = round(st.ullTotalPhys / 1024**3, 1)
    except Exception:
        env.ram_gb = 0.0


def detect_nvidia(env: Env) -> None:
    if shutil.which("nvidia-smi") is None:
        return
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        if not out:
            return
        first_gpu = out.splitlines()[0]
        parts = [p.strip() for p in first_gpu.split(",")]
        if len(parts) >= 2:
            env.has_nvidia_gpu = True
            env.nvidia_gpu_name = parts[0]
            mem_str = parts[1]  # like "12288 MiB"
            try:
                mb = int(mem_str.split()[0])
                env.nvidia_vram_gb = round(mb / 1024, 1)
            except Exception:
                env.nvidia_vram_gb = 0
    except Exception:
        return

    # Detect CUDA via nvcc
    if shutil.which("nvcc"):
        try:
            out = subprocess.check_output(["nvcc", "--version"], text=True)
            for line in out.splitlines():
                if "release" in line.lower():
                    parts = line.split("release")
                    if len(parts) > 1:
                        env.cuda_version = parts[1].strip().split(",")[0].strip()
                    break
        except Exception:
            pass


def detect_amd(env: Env) -> None:
    if shutil.which("rocm-smi") is None and shutil.which("rocminfo") is None:
        return
    try:
        if shutil.which("rocminfo"):
            out = subprocess.check_output(["rocminfo"], text=True, stderr=subprocess.DEVNULL)
            for line in out.splitlines():
                if "Marketing Name" in line:
                    name = line.split(":", 1)[1].strip()
                    if name and "CPU" not in name:
                        env.has_amd_gpu = True
                        env.amd_gpu_name = name
                        break
    except Exception:
        return

    # rocm version
    if shutil.which("hipconfig"):
        try:
            out = subprocess.check_output(["hipconfig", "--version"], text=True).strip()
            env.rocm_version = out
        except Exception:
            pass


def detect_apple_gpu(env: Env) -> None:
    if env.os_name != "macOS":
        return
    if env.is_apple_silicon:
        env.has_apple_gpu = True
        env.metal_supported = True


def detect_python(env: Env) -> None:
    env.python_version = platform.python_version()
    env.pip_available = (
        shutil.which("pip") is not None or shutil.which("pip3") is not None
    )


def detect_ffmpeg(env: Env) -> None:
    if shutil.which("ffmpeg") is None:
        return
    env.ffmpeg_installed = True
    try:
        out = subprocess.check_output(
            ["ffmpeg", "-version"], text=True, stderr=subprocess.STDOUT
        )
        first_line = out.splitlines()[0]
        # like "ffmpeg version 6.0 ..."
        env.ffmpeg_version = first_line.split("version", 1)[1].strip().split()[0] if "version" in first_line else first_line[:50]
    except Exception:
        env.ffmpeg_version = "unknown"


def detect_all() -> Env:
    env = Env()
    detect_os(env)
    detect_cpu(env)
    detect_ram(env)
    detect_nvidia(env)
    detect_amd(env)
    detect_apple_gpu(env)
    detect_intel_openvino(env)
    detect_python(env)
    detect_ffmpeg(env)
    return env


# ─── Recommendation engine ──────────────────────────────────────────────────


@dataclass
class Recommendation:
    backend: str = ""           # "mlx-whisper" / "faster-whisper" / "whisper-cpp" / "whisperx"
    backend_card: str = ""      # "backends/mlx-whisper.md"
    rationale: str = ""
    model: str = ""             # "large-v3" / "large-v3-turbo" / "small" / ...
    model_rationale: str = ""
    install_commands: list[str] = field(default_factory=list)
    test_command: str = ""
    warnings: list[str] = field(default_factory=list)


def recommend(env: Env) -> Recommendation:
    rec = Recommendation()

    # Step 1: pick backend
    if env.os_name == "macOS" and env.is_apple_silicon:
        rec.backend = "mlx-whisper"
        rec.backend_card = "backends/mlx-whisper.md"
        rec.rationale = (
            "Apple Silicon — нативная поддержка Metal через MLX. "
            "Это самый быстрый вариант на Mac (в 1.5-3x быстрее чем faster-whisper на том же Mac)."
        )
    elif env.os_name == "macOS" and not env.is_apple_silicon:
        rec.backend = "faster-whisper"
        rec.backend_card = "backends/faster-whisper.md"
        rec.rationale = (
            "Intel Mac без NVIDIA GPU — faster-whisper в режиме CPU. "
            "Рассматривать переход на Apple Silicon — там Whisper в 5-10x быстрее."
        )
    elif env.has_nvidia_gpu and env.nvidia_vram_gb >= 4:
        rec.backend = "faster-whisper"
        rec.backend_card = "backends/faster-whisper.md"
        rec.rationale = (
            f"NVIDIA GPU ({env.nvidia_gpu_name}, {env.nvidia_vram_gb} GB VRAM) — "
            "идеально для faster-whisper на CUDA. Realtime+ скорость на large-v3."
        )
    elif env.has_intel_npu or env.has_intel_igpu:
        # Intel Core Ultra (NPU+GPU+CPU) или 11+ gen Core (Iris Xe)
        rec.backend = "openvino"
        rec.backend_card = "backends/openvino.md"
        device = "NPU" if env.has_intel_npu else "GPU"
        gpu_label = env.intel_igpu_name or "Intel iGPU"
        rec.rationale = (
            f"Intel iGPU/NPU обнаружен ({gpu_label}). OpenVINO задействует "
            f"{device} нативно — это в 5-15x быстрее чем faster-whisper на CPU "
            "на том же ноуте. Особенно эффективно для voice dictation."
        )
    elif env.has_amd_gpu and env.os_name in ("Linux", "WSL"):
        rec.backend = "faster-whisper"
        rec.backend_card = "backends/faster-whisper.md"
        rec.rationale = (
            f"AMD GPU ({env.amd_gpu_name}) на Linux — faster-whisper через ROCm. "
            "Чуть сложнее установка чем на NVIDIA, но работает."
        )
        rec.warnings.append(
            "AMD ROCm support может быть нестабильным. Если упадёт на установке — переключайся на whisper.cpp."
        )
    else:
        # CPU only
        rec.backend = "whisper-cpp"
        rec.backend_card = "backends/whisper-cpp.md"
        rec.rationale = (
            "Нет дискретного GPU → whisper.cpp оптимизирован под CPU (AVX2/AVX512/Neon). "
            "Один бинарник, минимум зависимостей. Скорость ~0.3-1.0× от realtime на large-v3."
        )

    # Step 2: pick model
    # Logic:
    #   - apple silicon: large-v3-turbo by default (быстро + высокое качество)
    #   - NVIDIA >= 10GB VRAM: large-v3
    #   - NVIDIA 4-10GB: large-v3-turbo
    #   - CPU-only с RAM < 8GB: small
    #   - CPU-only с RAM 8-16GB: medium
    #   - CPU-only с RAM >= 16GB: large-v3-turbo

    if env.is_apple_silicon and env.ram_gb >= 16:
        rec.model = "large-v3-turbo"
        rec.model_rationale = (
            "На Apple Silicon с 16+ GB unified memory turbo даёт 8x скорость при минимальной потере. "
            "Для редких языков (казахский, узбекский, татарский) переключай на large-v3."
        )
    elif env.is_apple_silicon and env.ram_gb >= 8:
        rec.model = "small"
        rec.model_rationale = (
            "На M-чипе с 8GB unified memory — small баланс. "
            "Для прода-качества лучше апгрейд RAM или small/medium."
        )
    elif env.has_nvidia_gpu and env.nvidia_vram_gb >= 10:
        rec.model = "large-v3"
        rec.model_rationale = (
            f"VRAM {env.nvidia_vram_gb} GB ≥ 10 → large-v3 без проблем. "
            "Это эталонная модель — лучшее качество на всех языках."
        )
    elif env.has_nvidia_gpu and env.nvidia_vram_gb >= 4:
        rec.model = "large-v3-turbo"
        rec.model_rationale = (
            f"VRAM {env.nvidia_vram_gb} GB → large-v3-turbo (8x быстрее large-v3, ~2% потери качества). "
            "Если упадёт OOM — компилируй с compute_type=int8_float16."
        )
    elif env.has_intel_npu or env.has_intel_igpu:
        # OpenVINO на Intel NPU/iGPU. Turbo — оптимум.
        rec.model = "large-v3-turbo"
        rec.model_rationale = (
            f"Intel iGPU/NPU + OpenVINO — large-v3-turbo даёт ~0.9с латенси для "
            "PTT-фраз. Для редких языков переключи на large-v3."
        )
    elif not env.has_nvidia_gpu and env.ram_gb >= 16 and env.cpu_supports_avx2:
        rec.model = "large-v3-turbo"
        rec.model_rationale = (
            "RAM 16+ GB + AVX2 на CPU — turbo помещается, скорость ~0.5-1.0x realtime. "
            "Терпимо для коротких видео, медленно для подкастов."
        )
    elif not env.has_nvidia_gpu and env.ram_gb >= 8 and env.cpu_supports_avx2:
        rec.model = "medium"
        rec.model_rationale = (
            "RAM 8-16 GB + AVX2 на CPU — medium лучший компромисс. "
            "Качество значительно лучше small, скорость терпимая."
        )
    elif not env.has_nvidia_gpu and not env.cpu_supports_avx2:
        # Слабый CPU без AVX2 — voice dictation будет неюзабельным с medium/turbo.
        # Принудительно small или tiny чтобы было хоть как-то realtime.
        rec.model = "small" if env.ram_gb >= 4 else "tiny"
        rec.model_rationale = (
            f"CPU без AVX2 ({env.cpu_brand}) — Whisper будет очень медленным. "
            f"Бери {rec.model} чтобы было realtime для voice dictation. "
            "Для batch-транскрибации можно brать medium и подождать."
        )
    else:
        rec.model = "small"
        rec.model_rationale = (
            "Слабое железо — small — единственный вариант с приемлемой скоростью. "
            "Качество ~75% от large на английском, 60-70% на русском."
        )

    # Step 3: install commands
    if rec.backend == "mlx-whisper":
        rec.install_commands = [
            "# 1) Поставь Homebrew если ещё нет: https://brew.sh",
            "# 2) ffmpeg для извлечения аудио из видео:",
            "brew install ffmpeg",
            "# 3) Создай venv и поставь mlx-whisper:",
            "python3 -m venv .venv && source .venv/bin/activate",
            "pip install mlx-whisper",
        ]
        rec.test_command = (
            f'mlx_whisper --model mlx-community/whisper-{rec.model}-mlx '
            f'--language ru tests/sample.wav'
        )
    elif rec.backend == "faster-whisper" and env.has_nvidia_gpu:
        rec.install_commands = [
            "# 1) Убедись что есть CUDA Toolkit 12.x: nvidia-smi показывает Driver, nvcc показывает версию.",
            "# Если нет — поставь: https://developer.nvidia.com/cuda-downloads",
            "# 2) Создай venv:",
            "python3 -m venv .venv && source .venv/bin/activate  # Linux/Mac",
            "# (Windows: .venv\\Scripts\\activate)",
            "# 3) Установи faster-whisper:",
            "pip install faster-whisper",
            "# 4) ffmpeg:",
            "# Linux: sudo apt install ffmpeg  |  Windows: winget install ffmpeg  |  Mac: brew install ffmpeg",
        ]
        rec.test_command = (
            f"python -c \"from faster_whisper import WhisperModel; "
            f"m = WhisperModel('{rec.model}', device='cuda', compute_type='float16'); "
            f"print(list(m.transcribe('tests/sample.wav', language='ru')[0]))\""
        )
    elif rec.backend == "faster-whisper":
        rec.install_commands = [
            "python3 -m venv .venv && source .venv/bin/activate",
            "pip install faster-whisper",
            "# ffmpeg: Linux=apt | Windows=winget | Mac=brew",
        ]
        rec.test_command = (
            f"python -c \"from faster_whisper import WhisperModel; "
            f"m = WhisperModel('{rec.model}', device='cpu', compute_type='int8'); "
            f"print(list(m.transcribe('tests/sample.wav', language='ru')[0]))\""
        )
    elif rec.backend == "openvino":
        # Intel iGPU/NPU
        if env.os_name == "Windows":
            rec.install_commands = [
                "# 1) Создай venv:",
                "python -m venv .venv && .venv\\Scripts\\activate",
                "# 2) OpenVINO + optimum-intel + ffmpeg:",
                'pip install --upgrade openvino openvino-tokenizers "optimum-intel[openvino]" onnx',
                "winget install Gyan.FFmpeg",
                "# 3) (long-form) silero-vad для аудио > 30 сек:",
                "pip install silero-vad",
                "# 4) Сконвертируй модель в OpenVINO IR (один раз ~2-3 мин):",
                f"python scripts\\convert_openvino.py {rec.model}",
            ]
        else:
            rec.install_commands = [
                "python3 -m venv .venv && source .venv/bin/activate",
                'pip install --upgrade openvino openvino-tokenizers "optimum-intel[openvino]" onnx',
                "# ffmpeg: Linux=apt | Mac=brew",
                "pip install silero-vad   # для long-form (>30s)",
                f"python scripts/convert_openvino.py {rec.model}",
            ]
        # выбор устройства: NPU предпочтительнее GPU предпочтительнее CPU
        ov_device = "NPU" if env.has_intel_npu else "GPU"
        rec.test_command = (
            f"WHISPER_BACKEND=openvino WHISPER_OV_DEVICE={ov_device} "
            f"python -m examples.transcribe_one tests/samples/sample.wav --language ru --model {rec.model}"
        )
    elif rec.backend == "whisper-cpp":
        if env.os_name == "macOS":
            rec.install_commands = [
                "brew install whisper-cpp",
                f"# Скачай модель large-v3-turbo (~1.5 GB):",
                "mkdir -p models && cd models",
                f"curl -LO https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{rec.model}.bin",
                "cd ..",
            ]
        elif env.os_name == "Linux":
            rec.install_commands = [
                "sudo apt update && sudo apt install -y build-essential cmake ffmpeg",
                "git clone https://github.com/ggerganov/whisper.cpp.git",
                "cd whisper.cpp && cmake -B build && cmake --build build --config Release",
                f"bash ./models/download-ggml-model.sh {rec.model}",
            ]
        else:  # Windows
            rec.install_commands = [
                "# Через WSL2:",
                "wsl --install Ubuntu-22.04   # если ещё не стоит",
                "# Затем внутри WSL команды как для Linux выше",
                "# ИЛИ нативно через chocolatey:",
                "choco install whisper-cpp",
            ]
        rec.test_command = (
            f"./build/bin/whisper-cli -m models/ggml-{rec.model}.bin -l ru -f tests/sample.wav"
        )

    # Step 4: warnings
    if env.python_version:
        try:
            major, minor = map(int, env.python_version.split(".")[:2])
            if (major, minor) < (3, 9):
                rec.warnings.append(
                    f"Python {env.python_version} устарел. Whisper требует Python 3.9+. Поставь свежий."
                )
            # Python 3.14 ломает mlx-whisper / numba / torch (нет wheels на 2026).
            # Рекомендуем 3.10-3.13.
            if (major, minor) >= (3, 14):
                rec.warnings.append(
                    f"Python {env.python_version} слишком свежий — на нём нет wheels "
                    f"для mlx-whisper / numba / torch. Поставь Python 3.12: "
                    f"brew install python@3.12 (Mac) | sudo apt install python3.12 (Linux)"
                )
        except Exception:
            pass
    if not env.ffmpeg_installed:
        rec.warnings.append(
            "ffmpeg не найден. Он нужен для извлечения аудио из видео-файлов. "
            "Установка включена в команды ниже."
        )
    if env.ram_gb < 4 and not env.has_nvidia_gpu:
        rec.warnings.append(
            f"RAM {env.ram_gb} GB маловато даже для small. "
            "Рассмотри облачный путь (но это уже не локально)."
        )
    # Слабый CPU без GPU — voice dictation будет тормозить
    if (
        not env.has_nvidia_gpu
        and not env.is_apple_silicon
        and not env.has_intel_npu
        and not env.has_intel_igpu
        and not env.cpu_supports_avx2
    ):
        rec.warnings.append(
            f"CPU не поддерживает AVX2 ({env.cpu_brand}). На таком железе "
            "voice dictation будет давать ~5-15с латенси (неюзабельно). "
            "Bари модель tiny или используй remote-бэкенд (см. roadmap)."
        )

    return rec


# ─── Reporting ──────────────────────────────────────────────────────────────


def section(title: str):
    print(f"\n{bold(blue('═══ ' + title + ' ═══'))}")


def row(label: str, value: str, ok: Optional[bool] = None):
    if ok is True:
        marker = green("✓")
    elif ok is False:
        marker = red("✗")
    else:
        marker = " "
    print(f"  {marker} {bold(label)}: {value}")


def report(env: Env, rec: Recommendation) -> None:
    print(bold("\n🎤 Whisper Stack — environment detector\n"))

    section("Hardware")
    row("ОС", f"{env.os_name} {env.os_version}", True)
    row("Архитектура", env.arch)
    row("CPU", env.cpu_brand or "unknown")
    if env.is_intel_cpu:
        flags = []
        if env.cpu_supports_avx512:
            flags.append("AVX512")
        elif env.cpu_supports_avx2:
            flags.append("AVX2")
        else:
            flags.append("no AVX2 ⚠")
        row("CPU features", ", ".join(flags))
    row("RAM", f"{env.ram_gb} GB" if env.ram_gb else "?")

    if env.has_nvidia_gpu:
        row(
            "GPU (NVIDIA)",
            f"{env.nvidia_gpu_name}, {env.nvidia_vram_gb} GB VRAM",
            ok=True,
        )
        if env.cuda_version:
            row("CUDA", env.cuda_version, ok=True)
        else:
            row("CUDA Toolkit", yellow("не найден (будет установлен через PyTorch)"), ok=None)
    elif env.has_amd_gpu:
        row("GPU (AMD)", env.amd_gpu_name, ok=True)
        if env.rocm_version:
            row("ROCm", env.rocm_version, ok=True)
    elif env.has_apple_gpu:
        row("GPU (Apple)", "Metal (Apple Silicon)", ok=True)
    elif env.has_intel_npu or env.has_intel_igpu:
        gpu_label = env.intel_igpu_name or "Intel iGPU"
        accel = []
        if env.has_intel_igpu:
            accel.append("GPU")
        if env.has_intel_npu:
            accel.append("NPU")
        row("GPU (Intel)", f"{gpu_label} — OpenVINO: {'+'.join(accel)}", ok=True)
        if env.openvino_devices:
            row("OpenVINO devices", ", ".join(env.openvino_devices), ok=True)
        else:
            row(
                "OpenVINO",
                yellow("не установлен (поставлю через wizard / install-команды)"),
                ok=None,
            )
    else:
        row("GPU", "not found — будет работать на CPU", ok=False)

    section("Software")
    py_ok = False
    if env.python_version:
        try:
            major, minor = map(int, env.python_version.split(".")[:2])
            py_ok = (major, minor) >= (3, 9)
        except Exception:
            py_ok = False
    row("Python", env.python_version or "?", ok=py_ok)
    row("pip", "доступен" if env.pip_available else "не найден", ok=env.pip_available)
    row(
        "ffmpeg",
        env.ffmpeg_version if env.ffmpeg_installed else "не установлен",
        ok=env.ffmpeg_installed,
    )

    section("Рекомендация")
    print(f"  Бэкенд:   {bold(green(rec.backend))}")
    print(f"  Модель:   {bold(green(rec.model))}")
    print(f"  Карточка: {dim(rec.backend_card)}")
    print()
    print(f"  {bold('Почему этот бэкенд:')}")
    print(f"    {rec.rationale}")
    print()
    print(f"  {bold('Почему эта модель:')}")
    print(f"    {rec.model_rationale}")

    if rec.warnings:
        section("⚠️  Замечания")
        for w in rec.warnings:
            print(f"  {yellow('⚠')}  {w}")

    section("Команды установки")
    for cmd in rec.install_commands:
        if cmd.startswith("#"):
            print(f"  {dim(cmd)}")
        else:
            print(f"  {green('$')} {cmd}")

    section("Тест после установки")
    print(f"  {green('$')} {rec.test_command}")

    section("Дальше")
    print(f"  1. Открой карточку бэкенда: {dim(rec.backend_card)}")
    print(f"  2. Прогони установку из секции выше")
    print(f"  3. Запусти готовый пример: {dim('python -m examples.transcribe_one input.mp3')}")
    print(f"  4. Если что-то падает — открой {dim('docs/known-issues.md')}")
    print()


def main() -> int:
    env = detect_all()
    rec = recommend(env)
    report(env, rec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
