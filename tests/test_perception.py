"""Tests for ObjectClassifier (YOLO) and its integration into AwarenessSystem.

ultralytics is not installed in the dev/test environment, so these tests
exercise the graceful-degradation path (is_available == False) and the
message-composition logic via a fake classifier — they do not require a
real YOLO model or network access.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock

import numpy as np
import pytest

from nav_assistant.perception.object_detector import ObjectClassifier, DetectionResult


def test_object_classifier_unavailable_without_ultralytics():
    classifier = ObjectClassifier()
    assert classifier.is_available is False


def test_object_classifier_classify_returns_none_when_unavailable():
    classifier = ObjectClassifier()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert classifier.classify(frame) is None


def test_detection_result_fields():
    result = DetectionResult(label="chair", confidence=0.87)
    assert result.label == "chair"
    assert result.confidence == pytest.approx(0.87)


# ---- AwarenessSystem obstacle message enrichment (fake classifier) ----

class _FakeClassifier:
    """Duck-typed stand-in for ObjectClassifier — avoids needing real YOLO weights."""

    def __init__(self, detection: Optional[DetectionResult]):
        self._detection = detection

    @property
    def is_available(self) -> bool:
        return True

    def classify(self, bgr_frame) -> Optional[DetectionResult]:
        return self._detection


def _build_awareness_system(classifier):
    from nav_assistant.awareness import AwarenessSystem
    from nav_assistant.obstacle.detector import ObstacleAlert

    webcam = MagicMock()
    webcam.read_bgr.return_value = np.zeros((480, 640, 3), dtype=np.uint8)
    tof = MagicMock()
    recognizer = MagicMock()
    obstacle_detector = MagicMock()
    audio = MagicMock()

    system = AwarenessSystem(
        webcam=webcam, tof=tof, recognizer=recognizer,
        obstacle_detector=obstacle_detector, audio=audio,
        object_classifier=classifier,
    )
    return system, webcam, tof, obstacle_detector, audio


def test_obstacle_message_enriched_with_classification():
    from nav_assistant.obstacle.detector import ObstacleAlert
    import time

    detection = DetectionResult(label="chair", confidence=0.9)
    system, webcam, tof, obstacle_detector, audio = _build_awareness_system(
        _FakeClassifier(detection)
    )

    alert = ObstacleAlert(min_depth=0.8, zone_fraction=0.33, timestamp=time.monotonic())
    obstacle_detector.check.return_value = alert
    obstacle_detector.alert_message.return_value = "Obstacle ahead, 0.8 metres."

    system._check_obstacles()

    audio.alert.assert_called_once()
    spoken = audio.alert.call_args[0][0]
    assert "Chair" in spoken
    assert "0.8" in spoken


def test_obstacle_message_falls_back_to_generic_when_no_detection():
    from nav_assistant.obstacle.detector import ObstacleAlert
    import time

    system, webcam, tof, obstacle_detector, audio = _build_awareness_system(
        _FakeClassifier(None)
    )

    alert = ObstacleAlert(min_depth=0.8, zone_fraction=0.33, timestamp=time.monotonic())
    obstacle_detector.check.return_value = alert
    obstacle_detector.alert_message.return_value = "Obstacle ahead, 0.8 metres."

    system._check_obstacles()

    audio.alert.assert_called_once_with("Obstacle ahead, 0.8 metres.")


def test_no_classifier_uses_generic_message():
    from nav_assistant.obstacle.detector import ObstacleAlert
    import time

    system, webcam, tof, obstacle_detector, audio = _build_awareness_system(None)

    alert = ObstacleAlert(min_depth=0.8, zone_fraction=0.33, timestamp=time.monotonic())
    obstacle_detector.check.return_value = alert
    obstacle_detector.alert_message.return_value = "Obstacle ahead, 0.8 metres."

    system._check_obstacles()

    audio.alert.assert_called_once_with("Obstacle ahead, 0.8 metres.")
