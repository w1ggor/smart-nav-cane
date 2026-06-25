"""Offline speech recognition for destination selection (Vosk).

Used once at the start of guided navigation to ask "Where do you want to
go?" and match the spoken response against trained location labels. Not
used continuously during the navigation loop — only at the start.

Requires a downloaded Vosk model (e.g. vosk-model-small-en-us-0.15, ~40MB)
unzipped locally. See docs/deployment.md for setup instructions.
"""

from __future__ import annotations

import json
import logging
import queue
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import vosk
    import sounddevice as sd
    _VOSK_AVAILABLE = True
except ImportError:
    vosk = None  # type: ignore[assignment]
    sd = None  # type: ignore[assignment]
    _VOSK_AVAILABLE = False
    logger.warning(
        "vosk/sounddevice not installed — voice destination input unavailable. "
        "Install with: pip install vosk sounddevice"
    )


class VoiceRecognizer:
    """
    Offline speech-to-text for matching a spoken destination against a
    known set of trained location labels.

    Args:
        model_path: Path to an unzipped Vosk model directory.
        sample_rate: Microphone sample rate Vosk expects (16000 Hz).
    """

    def __init__(self, model_path: str, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate
        self._model = None

        if not _VOSK_AVAILABLE:
            return

        if not Path(model_path).exists():
            logger.warning(
                "Vosk model not found at %s — voice input disabled. "
                "Download from https://alphacephei.com/vosk/models and unzip here.",
                model_path,
            )
            return

        vosk.SetLogLevel(-1)
        self._model = vosk.Model(model_path)

    @property
    def is_available(self) -> bool:
        return self._model is not None

    def listen_for_destination(
        self, valid_labels: list[str], timeout_s: float = 8.0
    ) -> Optional[str]:
        """
        Listen on the default microphone and return the first trained label
        mentioned in the speech, or None if nothing matched within timeout_s.
        """
        if not self.is_available:
            logger.warning("VoiceRecognizer not available — cannot listen")
            return None

        recognizer = vosk.KaldiRecognizer(self._model, self._sample_rate)
        audio_queue: "queue.Queue[bytes]" = queue.Queue()

        def _callback(indata, frames, time_info, status) -> None:
            audio_queue.put(bytes(indata))

        logger.info("Listening for destination (timeout=%.0fs)...", timeout_s)
        deadline = time.monotonic() + timeout_s

        with sd.RawInputStream(
            samplerate=self._sample_rate, blocksize=8000,
            dtype="int16", channels=1, callback=_callback,
        ):
            while time.monotonic() < deadline:
                try:
                    data = audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    text = json.loads(recognizer.Result()).get("text", "")
                    match = self._match_label(text, valid_labels)
                    if match:
                        logger.info("Heard %r -> matched '%s'", text, match)
                        return match

            text = json.loads(recognizer.FinalResult()).get("text", "")
            match = self._match_label(text, valid_labels)
            if match:
                logger.info("Heard %r -> matched '%s'", text, match)
            return match

    @staticmethod
    def _match_label(text: str, valid_labels: list[str]) -> Optional[str]:
        text_lower = text.lower()
        for label in valid_labels:
            if label.lower().replace("_", " ") in text_lower:
                return label
        return None
