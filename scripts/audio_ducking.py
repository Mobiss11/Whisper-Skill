"""Приглушение остальных Windows-аудиосессий на время диктовки.

Работаем с громкостью отдельных приложений, а не с общей громкостью
устройства. Поэтому системный уровень остаётся прежним, а сигнал самой
диктовки можно не приглушать. Исходные уровни всегда восстанавливаются.
"""

from __future__ import annotations

import logging
import os
import platform
import threading
from dataclasses import dataclass
from typing import Callable, Iterable, Optional


def clamp_reduction_percent(value: object) -> int:
    """Нормализовать пользовательское значение в поддерживаемый диапазон."""
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = 70
    return max(0, min(90, number))


@dataclass
class _DuckedSession:
    volume: object
    original: float
    ducked: float


class WindowsAudioDucker:
    """Временно уменьшает громкость всех аудиосессий, кроме текущего процесса.

    Внедряемый ``session_provider`` нужен для тестов. В обычной работе список
    сессий берётся через Windows Core Audio (pycaw).
    """

    def __init__(
        self,
        enabled: bool = True,
        reduction_percent: int = 70,
        session_provider: Optional[Callable[[], Iterable[object]]] = None,
        process_id: Optional[int] = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.reduction_percent = clamp_reduction_percent(reduction_percent)
        self._session_provider = session_provider
        self._process_id = process_id if process_id is not None else os.getpid()
        self._ducked_sessions: list[_DuckedSession] = []
        self._active = False
        self._lock = threading.RLock()
        self._dependency_warning_shown = False

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    def configure(self, enabled: bool, reduction_percent: int) -> None:
        """Обновить параметры для следующей диктовки."""
        with self._lock:
            self.enabled = bool(enabled)
            self.reduction_percent = clamp_reduction_percent(reduction_percent)

    def duck(self) -> int:
        """Приглушить доступные сессии. Возвращает число изменённых сессий."""
        with self._lock:
            if self._active or not self.enabled or self.reduction_percent <= 0:
                return 0
            if platform.system() != "Windows" and self._session_provider is None:
                return 0

            try:
                sessions = list(self._get_sessions())
            except Exception as exc:
                if not self._dependency_warning_shown:
                    logging.warning(f"audio ducking unavailable: {exc}")
                    self._dependency_warning_shown = True
                return 0

            factor = (100 - self.reduction_percent) / 100.0
            changed: list[_DuckedSession] = []
            for session in sessions:
                try:
                    if int(getattr(session, "ProcessId", -1)) == self._process_id:
                        continue
                    volume = session.SimpleAudioVolume
                    original = float(volume.GetMasterVolume())
                    ducked = max(0.0, min(1.0, original * factor))
                    if abs(ducked - original) < 0.001:
                        continue
                    volume.SetMasterVolume(ducked, None)
                    changed.append(_DuckedSession(volume, original, ducked))
                except Exception as exc:
                    # Отдельная сессия могла закрыться между перечислением и
                    # изменением. Это не должно ломать старт записи.
                    logging.debug(f"audio session duck skipped: {exc}")

            self._ducked_sessions = changed
            self._active = bool(changed)
            return len(changed)

    def restore(self) -> int:
        """Вернуть громкость, уважая ручные изменения пользователя.

        Если во время записи уровень не трогали, возвращаем точное исходное
        значение. Если пользователь поменял громкость сам, снимаем с нового
        значения только наш коэффициент приглушения. Нулевой уровень оставляем
        нулевым — это похоже на намеренное выключение звука.
        """
        with self._lock:
            if not self._ducked_sessions:
                self._active = False
                return 0

            restored = 0
            for item in self._ducked_sessions:
                try:
                    current = float(item.volume.GetMasterVolume())
                    if abs(current - item.ducked) <= 0.015:
                        target = item.original
                    elif current <= 0.001 or item.original <= 0.001:
                        target = current
                    else:
                        factor = item.ducked / item.original
                        target = min(1.0, current / factor) if factor > 0 else current
                    if abs(target - current) > 0.001:
                        item.volume.SetMasterVolume(target, None)
                    restored += 1
                except Exception as exc:
                    logging.debug(f"audio session restore skipped: {exc}")

            self._ducked_sessions = []
            self._active = False
            return restored

    def _get_sessions(self) -> Iterable[object]:
        if self._session_provider is not None:
            return self._session_provider()
        try:
            from pycaw.pycaw import AudioUtilities
        except ImportError as exc:
            raise RuntimeError(
                "для приглушения звука установи pycaw: pip install pycaw"
            ) from exc
        return AudioUtilities.GetAllSessions()
