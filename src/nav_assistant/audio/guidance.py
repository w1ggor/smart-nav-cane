"""Audio guidance: offline TTS + non-blocking obstacle alerts.

TTS strategy (in priority order):
  1. espeak-ng via subprocess — most reliable on Raspberry Pi OS Bookworm.
     pyttsx3's espeak driver has a broken voice lookup on Python 3.13+.
  2. pyttsx3 — fallback for macOS (nsss) and Windows (sapi5).
  3. Log-only — if neither is available.

Obstacle alerts play a short tone via pygame.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# Detect espeak-ng binary (available on Raspberry Pi OS Bookworm by default)
_ESPEAK_BIN = shutil.which("espeak-ng") or shutil.which("espeak")

try:
    import pyttsx3
    _PYTTSX3_AVAILABLE = True
except ImportError:
    _PYTTSX3_AVAILABLE = False

try:
    import pygame
    _PYGAME_AVAILABLE = True
except ImportError:
    _PYGAME_AVAILABLE = False

# Choose backend once at import time
_BACKEND = "espeak-ng" if _ESPEAK_BIN else ("pyttsx3" if _PYTTSX3_AVAILABLE else "none")
logger.debug("AudioGuidance backend: %s", _BACKEND)


class AudioGuidance:
    """
    Non-blocking audio guidance system.

    speak() queues a TTS utterance in a background thread — the caller is
    never blocked waiting for speech to finish.

    alert() speaks immediately (blocks briefly) so obstacle warnings are
    delivered without delay regardless of any queued speech.

    Args:
        rate: espeak-ng speaking rate (words per minute, default 150).
              For pyttsx3 this is also WPM.
        volume: Volume 0.0–1.0 (applied to pyttsx3 only; espeak-ng uses
                system volume).
        alert_sound_path: Optional .wav file for alert tone. If None, a
                          440 Hz beep is synthesised via pygame.
    """

    def __init__(
        self,
        rate: int = 150,
        volume: float = 1.0,
        alert_sound_path: Optional[str] = None,
    ) -> None:
        self._rate = rate
        self._volume = volume
        self._alert_sound_path = alert_sound_path
        self._pyttsx3_engine: Optional[object] = None
        self._lock = threading.Lock()
        self._speak_thread: Optional[threading.Thread] = None

    def initialize(self) -> None:
        """Initialize TTS engine and pygame mixer."""
        if _BACKEND == "espeak-ng":
            logger.info("TTS backend: espeak-ng (%s)", _ESPEAK_BIN)
        elif _BACKEND == "pyttsx3":
            try:
                self._pyttsx3_engine = pyttsx3.init()
                self._pyttsx3_engine.setProperty("rate", self._rate)
                self._pyttsx3_engine.setProperty("volume", self._volume)
                logger.info("TTS backend: pyttsx3")
            except Exception as exc:
                logger.warning("pyttsx3 init failed (%s); falling back to log-only", exc)
                self._pyttsx3_engine = None
        else:
            logger.warning("No TTS backend available — speech output disabled")

        if _PYGAME_AVAILABLE:
            try:
                pygame.mixer.init()
                logger.info("pygame mixer initialized")
            except Exception as exc:
                logger.warning("pygame mixer init failed: %s", exc)

    def speak(self, text: str) -> None:
        """Speak text asynchronously. Returns immediately."""
        logger.info("SPEAK: %s", text)

        def _run():
            with self._lock:
                self._tts(text)

        self._speak_thread = threading.Thread(target=_run, daemon=True)
        self._speak_thread.start()

    def alert(self, text: str) -> None:
        """
        Play an obstacle alert tone and speak the message.
        Interrupts any in-progress speech by acquiring the lock then speaking.
        Blocks for the duration of the beep (~0.3s) but not for the speech.
        """
        logger.warning("ALERT: %s", text)
        self._play_alert_tone()
        # Alert speech runs in-thread (blocking) to guarantee delivery
        with self._lock:
            self._tts(text)

    def shutdown(self) -> None:
        if self._pyttsx3_engine is not None:
            try:
                self._pyttsx3_engine.stop()
            except Exception:
                pass
        if _PYGAME_AVAILABLE and pygame.mixer.get_init():
            pygame.mixer.quit()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _tts(self, text: str) -> None:
        """Blocking TTS call using the selected backend."""
        if _BACKEND == "espeak-ng":
            try:
                subprocess.run(
                    [_ESPEAK_BIN, "-s", str(self._rate), text],
                    check=False,
                    timeout=15,
                )
            except Exception as exc:
                logger.warning("espeak-ng failed: %s", exc)

        elif _BACKEND == "pyttsx3" and self._pyttsx3_engine is not None:
            try:
                self._pyttsx3_engine.say(text)
                self._pyttsx3_engine.runAndWait()
            except Exception as exc:
                logger.warning("pyttsx3 speak failed: %s", exc)

    def _play_alert_tone(self) -> None:
        if not _PYGAME_AVAILABLE or not pygame.mixer.get_init():
            return
        if self._alert_sound_path:
            try:
                pygame.mixer.Sound(self._alert_sound_path).play()
                return
            except Exception as exc:
                logger.debug("Alert sound file failed: %s", exc)
        self._beep()

    @staticmethod
    def _beep(frequency: int = 880, duration_ms: int = 300) -> None:
        """Synthesise a short beep via pygame."""
        try:
            import numpy as np
            sample_rate = 22050
            n = int(sample_rate * duration_ms / 1000)
            t = np.linspace(0, duration_ms / 1000, n, endpoint=False)
            wave = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)
            stereo = np.column_stack((wave, wave))
            pygame.sndarray.make_sound(stereo).play()
        except Exception as exc:
            logger.debug("Beep synthesis failed: %s", exc)
