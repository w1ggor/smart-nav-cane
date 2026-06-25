"""Guided navigation: reactive wall-following + landmark announcements.

No IMU or wheel odometry is available on this hardware, so this does NOT
plan a path to arbitrary coordinates. Instead it reacts to the live ToF
depth frame on every cycle:

  - the forward view is split into left / center / right zones
  - if the center is clear, say "go straight"; if blocked, turn toward
    whichever side has more clearance
  - trained "landmark" waypoints (e.g. a door) are announced when ORB
    recognizes them AND the center zone shows them within range
  - arrival is detected when the current view matches the destination
    "location" waypoint with sufficient confidence

This works for a known, previously walked route in a fixed environment —
it does not generalize to unseen layouts. That limitation is intentional:
real path planning would require IMU/odometry or SLAM, both out of scope
for this version (see CLAUDE.md future work).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import numpy as np

from nav_assistant.localization.place_recognizer import PlaceRecognizer
from nav_assistant.sensors.tof import ToFFrame

logger = logging.getLogger(__name__)


class NavCommand(Enum):
    STRAIGHT = auto()
    TURN_LEFT = auto()
    TURN_RIGHT = auto()
    STOP = auto()
    ARRIVED = auto()


@dataclass
class GuidanceResult:
    command: NavCommand
    message: str
    landmark: Optional[str] = None


class GuidedNavigator:
    """
    Args:
        location_recognizer: PlaceRecognizer loaded with kind="location" —
            used for arrival detection against the destination label.
        landmark_recognizer: PlaceRecognizer loaded with kind="landmark" —
            used to announce trained features (doors, etc.) along the path.
        clear_distance_m: Center-zone depth above which the path is
            considered clear ("go straight").
        landmark_distance_m: Maximum distance at which a recognized
            landmark is announced as "ahead".
        landmark_cooldown_s: Minimum seconds between repeat announcements
            of the same landmark.
    """

    def __init__(
        self,
        location_recognizer: PlaceRecognizer,
        landmark_recognizer: PlaceRecognizer,
        clear_distance_m: float = 1.0,
        landmark_distance_m: float = 1.5,
        landmark_cooldown_s: float = 5.0,
    ) -> None:
        self._location_recognizer = location_recognizer
        self._landmark_recognizer = landmark_recognizer
        self._clear_distance = clear_distance_m
        self._landmark_distance = landmark_distance_m
        self._landmark_cooldown = landmark_cooldown_s
        self._last_landmark: Optional[str] = None
        self._last_landmark_time: float = 0.0

    def evaluate(
        self,
        tof_frame: ToFFrame,
        gray_frame: np.ndarray,
        destination_label: str,
    ) -> GuidanceResult:
        """Run one navigation cycle and return the guidance for this moment."""
        # 1. Arrival check — does the current view match the destination?
        loc_result = self._location_recognizer.recognize(gray_frame)
        if (
            loc_result.is_confident
            and loc_result.waypoint is not None
            and loc_result.waypoint.label == destination_label
        ):
            return GuidanceResult(
                NavCommand.ARRIVED,
                f"You have arrived at the {destination_label.replace('_', ' ')}.",
            )

        # 2. Landmark check (e.g. a trained door) within range ahead
        left, center, right = tof_frame.zone_depths()
        landmark_msg = self._check_landmark(gray_frame, center)

        # 3. Reactive wall-following decision
        nav = self._wall_following(left, center, right)

        if landmark_msg:
            return GuidanceResult(nav.command, f"{landmark_msg} {nav.message}", landmark=landmark_msg)
        return nav

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_landmark(self, gray_frame: np.ndarray, center_depth: float) -> Optional[str]:
        result = self._landmark_recognizer.recognize(gray_frame)
        if not result.is_confident or result.waypoint is None:
            return None

        if center_depth <= 0 or center_depth > self._landmark_distance:
            return None

        now = time.monotonic()
        label = result.waypoint.label
        same = label == self._last_landmark
        if same and (now - self._last_landmark_time) < self._landmark_cooldown:
            return None

        self._last_landmark = label
        self._last_landmark_time = now
        return f"{label.replace('_', ' ').title()} ahead."

    def _wall_following(self, left: float, center: float, right: float) -> GuidanceResult:
        if center <= 0 or center > self._clear_distance:
            return GuidanceResult(NavCommand.STRAIGHT, "Go straight.")

        if left <= 0 and right <= 0:
            return GuidanceResult(NavCommand.STOP, "Path blocked. Please stop.")

        if left > right:
            return GuidanceResult(NavCommand.TURN_LEFT, "Turn left.")
        elif right > left:
            return GuidanceResult(NavCommand.TURN_RIGHT, "Turn right.")
        else:
            return GuidanceResult(NavCommand.STOP, "Path blocked. Please stop.")
