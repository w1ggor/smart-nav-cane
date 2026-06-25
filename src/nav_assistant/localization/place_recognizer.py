"""ORB-based visual place recognition.

Matches a live webcam frame against all stored waypoint descriptors
and returns the best-matching waypoint with a confidence score.

Phase 2 implementation — fully functional.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from nav_assistant.mapping.environment import EnvironmentMap
from nav_assistant.mapping.waypoint import Waypoint

logger = logging.getLogger(__name__)

_ORB_N_FEATURES = 500
_LOWE_RATIO = 0.75
_MIN_GOOD_MATCHES = 15


@dataclass
class RecognitionResult:
    waypoint: Optional[Waypoint]
    confidence: float          # 0.0–1.0
    good_matches: int
    is_confident: bool         # True when confidence >= threshold


class PlaceRecognizer:
    """
    Loads all waypoint ORB descriptors from an EnvironmentMap and provides
    frame-by-frame place recognition via BFMatcher with Lowe's ratio test.

    Call load() once after the environment is opened, then call recognize()
    for each webcam frame.

    Args:
        env: An open EnvironmentMap instance.
        confidence_threshold: Minimum confidence (0–1) to commit to a match.
        min_good_matches: Minimum good matches to consider a match valid.
        lowe_ratio: Lowe's ratio test threshold.
    """

    def __init__(
        self,
        env: EnvironmentMap,
        confidence_threshold: float = 0.6,
        min_good_matches: int = _MIN_GOOD_MATCHES,
        lowe_ratio: float = _LOWE_RATIO,
    ) -> None:
        self._env = env
        self._confidence_threshold = confidence_threshold
        self._min_good_matches = min_good_matches
        self._lowe_ratio = lowe_ratio
        self._orb = cv2.ORB_create(nfeatures=_ORB_N_FEATURES)
        self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        self._index: list[tuple[Waypoint, np.ndarray]] = []  # (waypoint, descriptors)

    def load(self, kind: Optional[str] = None) -> None:
        """
        Load waypoint descriptors from disk into memory.

        Args:
            kind: If set, only load waypoints of this kind ('location' or
                'landmark'). If None, loads all waypoints regardless of kind.
        """
        self._index.clear()
        waypoints = self._env.list_waypoints(kind=kind)
        for wp in waypoints:
            try:
                descs = np.load(wp.descriptor_path)
                self._index.append((wp, descs))
            except (FileNotFoundError, ValueError) as exc:
                logger.warning("Could not load descriptors for %s: %s", wp.label, exc)
        logger.info("PlaceRecognizer loaded %d waypoints", len(self._index))

    def recognize(self, gray_frame: np.ndarray) -> RecognitionResult:
        """
        Match a grayscale webcam frame against the loaded waypoint index.

        Returns a RecognitionResult with the best-matching waypoint (or None
        if no confident match is found).
        """
        if not self._index:
            return RecognitionResult(waypoint=None, confidence=0.0,
                                     good_matches=0, is_confident=False)

        _, query_descs = self._orb.detectAndCompute(gray_frame, None)
        if query_descs is None or len(query_descs) < 2:
            return RecognitionResult(waypoint=None, confidence=0.0,
                                     good_matches=0, is_confident=False)

        best_wp: Optional[Waypoint] = None
        best_good = 0

        for wp, stored_descs in self._index:
            if stored_descs is None or len(stored_descs) < 2:
                continue
            matches = self._matcher.knnMatch(query_descs, stored_descs, k=2)
            good = [m for m, n in matches if m.distance < self._lowe_ratio * n.distance]
            if len(good) > best_good:
                best_good = len(good)
                best_wp = wp

        if best_good < self._min_good_matches:
            return RecognitionResult(waypoint=None, confidence=0.0,
                                     good_matches=best_good, is_confident=False)

        # Normalise to a 0–1 confidence score based on match count
        confidence = min(1.0, best_good / (_ORB_N_FEATURES * 0.5))
        is_confident = confidence >= self._confidence_threshold

        logger.debug("Best match: %s (good=%d, conf=%.2f)", best_wp.label, best_good, confidence)
        return RecognitionResult(
            waypoint=best_wp,
            confidence=confidence,
            good_matches=best_good,
            is_confident=is_confident,
        )
