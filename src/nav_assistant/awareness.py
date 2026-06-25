"""AwarenessSystem — main loop coordinator for the environmental awareness mode.

Runs two concurrent concerns at ~2 Hz:
  1. Obstacle detection  (every cycle)   — ToF depth threshold → audio alert
  2. Location recognition (every N cycles) — ORB matching → audio announcement

Location announcements are suppressed when the same location repeats within
the announcement cooldown window to avoid annoying the user.
"""

from __future__ import annotations

import logging
import signal
import time
from typing import Optional

from nav_assistant.audio.guidance import AudioGuidance
from nav_assistant.localization.place_recognizer import PlaceRecognizer, RecognitionResult
from nav_assistant.obstacle.detector import ObstacleDetector
from nav_assistant.perception.object_detector import ObjectClassifier
from nav_assistant.sensors.tof import ToFSensor
from nav_assistant.sensors.webcam import WebcamSensor

logger = logging.getLogger(__name__)


class AwarenessSystem:
    """
    Coordinates obstacle detection and location recognition into a single loop.

    Args:
        webcam: Open WebcamSensor instance.
        tof: Open ToFSensor instance.
        recognizer: Loaded PlaceRecognizer instance.
        obstacle_detector: ObstacleDetector instance.
        audio: Initialized AudioGuidance instance.
        object_classifier: Optional ObjectClassifier (YOLOv8-nano). When
            provided and available, obstacle alerts are enriched with the
            classified object name (e.g. "Chair ahead") instead of a
            generic message. Runs only when an obstacle is already flagged
            by the cheap ToF threshold, not every cycle.
        loop_hz: Target loop frequency in Hz (default 2).
        recognition_every_n: Run ORB recognition every N cycles (default 3).
            At 2 Hz this means recognition every ~1.5 seconds.
        location_cooldown_s: Seconds before re-announcing the same location
            (default 30). Set to 0 to announce every recognition.
    """

    def __init__(
        self,
        webcam: WebcamSensor,
        tof: ToFSensor,
        recognizer: PlaceRecognizer,
        obstacle_detector: ObstacleDetector,
        audio: AudioGuidance,
        object_classifier: Optional[ObjectClassifier] = None,
        loop_hz: float = 2.0,
        recognition_every_n: int = 3,
        location_cooldown_s: float = 30.0,
    ) -> None:
        self._webcam = webcam
        self._tof = tof
        self._recognizer = recognizer
        self._obstacle_detector = obstacle_detector
        self._audio = audio
        self._object_classifier = object_classifier
        self._loop_period = 1.0 / loop_hz
        self._recognition_every_n = recognition_every_n
        self._location_cooldown = location_cooldown_s

        self._running = False
        self._cycle = 0
        self._last_location: Optional[str] = None
        self._last_location_time: float = 0.0

    def run(self) -> None:
        """Start the awareness loop. Blocks until stop() is called or SIGINT."""
        self._running = True
        self._audio.speak("Awareness system started.")
        logger.info("AwarenessSystem running (%.1f Hz, recognition every %d cycles)",
                    1.0 / self._loop_period, self._recognition_every_n)

        while self._running:
            t0 = time.monotonic()
            self._tick()
            elapsed = time.monotonic() - t0
            sleep_time = max(0.0, self._loop_period - elapsed)
            time.sleep(sleep_time)

        self._audio.speak("Awareness system stopped.")
        logger.info("AwarenessSystem stopped")

    def stop(self) -> None:
        """Request the loop to exit after the current cycle."""
        self._running = False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        self._cycle += 1

        # --- Obstacle detection (every cycle, high priority) ---
        self._check_obstacles()

        # --- Location recognition (every N cycles) ---
        if self._cycle % self._recognition_every_n == 0:
            self._check_location()

    def _check_obstacles(self) -> None:
        try:
            tof_frame = self._tof.read_tof()
            alert = self._obstacle_detector.check(tof_frame)
            if alert:
                message = self._obstacle_detector.alert_message(alert)

                if self._object_classifier is not None and self._object_classifier.is_available:
                    bgr = self._webcam.read_bgr()
                    detection = self._object_classifier.classify(bgr)
                    if detection:
                        message = f"{detection.label.capitalize()} ahead, {alert.min_depth:.1f} metres."
                        logger.info("Obstacle classified: %s (conf=%.2f)",
                                    detection.label, detection.confidence)

                self._audio.alert(message)
        except Exception as exc:
            logger.warning("Obstacle check error: %s", exc)

    def _check_location(self) -> None:
        try:
            gray = self._webcam.read_gray()
            result = self._recognizer.recognize(gray)

            if not result.is_confident or result.waypoint is None:
                logger.debug("Location: no confident match (best=%d matches)",
                             result.good_matches)
                return

            label = result.waypoint.label
            now = time.monotonic()
            since_last = now - self._last_location_time
            same_location = label == self._last_location

            if same_location and since_last < self._location_cooldown:
                logger.debug("Location: '%s' (suppressed, %.0fs ago)", label, since_last)
                return

            # New location or cooldown expired — announce it
            message = f"{'You are still in' if same_location else 'You are in'} the {label}."
            self._audio.speak(message)
            logger.info("Location announced: '%s' (conf=%.2f, matches=%d)",
                        label, result.confidence, result.good_matches)

            self._last_location = label
            self._last_location_time = now

        except Exception as exc:
            logger.warning("Location check error: %s", exc)
