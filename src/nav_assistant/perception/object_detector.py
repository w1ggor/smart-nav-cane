"""Real-time obstacle classification using YOLOv8-nano (ultralytics).

This is the project's deep learning component: a convolutional neural
network (YOLOv8n, COCO-pretrained, 80 classes, ~6MB) that names the object
the ToF camera has flagged as close, instead of a generic "obstacle ahead".

Architecture decision — DL inference gated behind a cheap depth check:
Running YOLO every cycle would be too slow for real-time use on a
Raspberry Pi 4 CPU. Instead, the lightweight ToF depth threshold
(ObstacleDetector) runs every cycle, and YOLO only runs on the webcam
frame *after* an obstacle has already been flagged — classifying what
triggered the alert. This keeps the system real-time while still using
a genuine DL model for object recognition.

Door recognition is intentionally NOT done here: "door" is not a COCO
class, so trained ORB landmarks (see mapping/recorder.py, kind="landmark")
handle that case instead. YOLO and ORB are used where each is strongest:
YOLO for generic pretrained object classes, ORB for custom small-data
landmarks that have no equivalent pretrained class.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except ImportError:
    YOLO = None  # type: ignore[assignment]
    _YOLO_AVAILABLE = False
    logger.warning(
        "ultralytics not installed — object classification disabled. "
        "Install with: pip install ultralytics"
    )


@dataclass
class DetectionResult:
    label: str
    confidence: float


class ObjectClassifier:
    """
    Wraps a YOLOv8-nano model to classify the most prominent object in a
    webcam frame. Used to enrich obstacle alerts with a spoken object
    label (e.g. "Chair ahead") instead of a generic alert.

    Args:
        model_path: Path or name of the YOLO weights file. Default
            "yolov8n.pt" auto-downloads the nano variant on first use
            (COCO-pretrained, 80 classes, ~6MB).
        confidence_threshold: Minimum detection confidence (0-1) to report.
    """

    def __init__(self, model_path: str = "yolov8n.pt", confidence_threshold: float = 0.5) -> None:
        self._confidence_threshold = confidence_threshold
        self._model = None

        if not _YOLO_AVAILABLE:
            return

        try:
            self._model = YOLO(model_path)
            logger.info("YOLO model loaded: %s", model_path)
        except Exception as exc:
            logger.warning("Failed to load YOLO model '%s': %s", model_path, exc)

    @property
    def is_available(self) -> bool:
        return self._model is not None

    def classify(self, bgr_frame: np.ndarray) -> Optional[DetectionResult]:
        """
        Return the highest-confidence detection in the frame, or None if
        unavailable, no objects detected, or below the confidence threshold.
        """
        if not self.is_available:
            return None

        try:
            results = self._model.predict(bgr_frame, verbose=False)[0]
        except Exception as exc:
            logger.warning("YOLO inference failed: %s", exc)
            return None

        if results.boxes is None or len(results.boxes) == 0:
            return None

        best_idx = int(results.boxes.conf.argmax())
        confidence = float(results.boxes.conf[best_idx])
        if confidence < self._confidence_threshold:
            return None

        class_id = int(results.boxes.cls[best_idx])
        label = self._model.names[class_id]
        return DetectionResult(label=label, confidence=confidence)
