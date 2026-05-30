"""Audio guidance: offline TTS + non-blocking obstacle alerts.

Uses pyttsx3 for speech (espeak backend on RPi, no cloud required).
Obstacle alerts play a short tone via pygame to avoid interrupting speech.

Phase 4 implementation.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pyttsx3
    _TTS_AVAILABLE = True
except ImportError:
    _TTS_AVAILABLE = False
    logger.warning("pyttsx3 not installed. Audio guidance will log only.")

try:
    import pygame
    _PYGAME_AVAILABLE = True
except ImportError:
    _PYGAME_AVAILABLE = False


class AudioGuidance:
    """
    Non-blocking audio guidance system.

    speak() queues a TTS utterance in a background thread so the caller
    is never blocked waiting for speech to finish.

    alert() plays a short alert tone (pygame) immediately, interrupting
    any in-progress speech. This ensures obstacle warnings are heard
    without delay.

    Args:
        rate: TTS speech rate (words per minute).
        volume: TTS volume (0.0–1.0).
        alert_sound_path: Optional path to a .wav file for obstacle alerts.
            If None, a 440 Hz beep is synthesised via pygame.
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
        self._engine: Optional[object] = None
        self._lock = threading.Lock()

    def initialize(self) -> None:
        """Initialize TTS engine and pygame mixer."""
        if _TTS_AVAILABLE:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self._rate)
            self._engine.setProperty("volume", self._volume)
            logger.info("pyttsx3 TTS engine initialized")
        else:
            logger.warning("TTS unavailable — speech output disabled")

        if _PYGAME_AVAILABLE:
            pygame.mixer.init()
            logger.info("pygame mixer initialized")

    def speak(self, text: str) -> None:
        """Speak text asynchronously in a background thread."""
        logger.info("SPEAK: %s", text)
        if not _TTS_AVAILABLE or self._engine is None:
            return

        def _run():
            with self._lock:
                self._engine.say(text)
                self._engine.runAndWait()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def alert(self, text: str) -> None:
        """
        Immediately play an obstacle alert tone and speak a short message.
        This runs in the calling thread (blocking for ~0.2s) to guarantee
        prompt delivery.
        """
        logger.warning("ALERT: %s", text)

        if _PYGAME_AVAILABLE and pygame.mixer.get_init():
            if self._alert_sound_path:
                try:
                    sound = pygame.mixer.Sound(self._alert_sound_path)
                    sound.play()
                except Exception as exc:
                    logger.warning("Could not play alert sound: %s", exc)
            else:
                self._beep()

        # Speak the alert text (may interrupt ongoing speech)
        if _TTS_AVAILABLE and self._engine is not None:
            self._engine.stop()
            self._engine.say(text)
            self._engine.runAndWait()

    def shutdown(self) -> None:
        if _TTS_AVAILABLE and self._engine is not None:
            self._engine.stop()
        if _PYGAME_AVAILABLE and pygame.mixer.get_init():
            pygame.mixer.quit()

    @staticmethod
    def _beep(frequency: int = 440, duration_ms: int = 300) -> None:
        """Synthesise a short sine-wave beep using pygame."""
        if not _PYGAME_AVAILABLE:
            return
        try:
            import numpy as np
            sample_rate = 22050
            t = np.linspace(0, duration_ms / 1000, int(sample_rate * duration_ms / 1000))
            wave = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)
            stereo = np.column_stack((wave, wave))
            sound = pygame.sndarray.make_sound(stereo)
            sound.play()
        except Exception as exc:
            logger.debug("Beep synthesis failed: %s", exc)
