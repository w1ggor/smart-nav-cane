"""Guided navigation: planned-route following with reactive safety checks,
plus landmark announcements.

No IMU or wheel odometry is available on this hardware, so the "plan" is
not a continuous geometric path — it is a sequence of trained WaypointEdges
(direction hints between previously-visited locations, built via Dijkstra
in RouteGraph). At each step, the planned direction is followed only if the
live ToF depth frame confirms it is safe; otherwise the system stops and
warns rather than blindly following the plan. If no route is available
(e.g. no edges trained between the current location and the destination),
navigation falls back to purely reactive wall-following.

  - if a planned route is set, the current edge's direction_hint drives
    the instruction ("forward" / "turn_left" / "turn_right" / "turn_around"),
    cross-checked against the ToF center zone before committing to "forward"
  - with no route (or once the route runs out), the forward view is split
    into left / center / right zones and the system reacts to whichever
    side has more clearance
  - trained "landmark" waypoints (e.g. a door) are announced when ORB
    recognizes them AND the center zone shows them within range
  - arrival is detected when the current view matches the destination
    "location" waypoint with sufficient confidence

This works for a known, previously walked environment — it does not
generalize to unseen layouts. That limitation is intentional: full
geometric path planning would require IMU/odometry or SLAM, both out of
scope for this version (see CLAUDE.md future work).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import numpy as np

from nav_assistant.localization.place_recognizer import PlaceRecognizer
from nav_assistant.mapping.waypoint import WaypointEdge
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
            used for arrival detection and route-step advancement.
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
        self._route: list[WaypointEdge] = []
        self._route_index: int = 0

    def set_route(self, route: list[WaypointEdge]) -> None:
        """
        Provide a planned route (sequence of edges from RouteGraph.plan()).

        When set, navigation follows each edge's direction_hint, verifying
        against the live ToF frame before committing to "forward". Pass an
        empty list (the default) to fall back to pure reactive wall-following.
        """
        self._route = route
        self._route_index = 0

    @property
    def has_route(self) -> bool:
        return bool(self._route) and self._route_index < len(self._route)

    def evaluate(
        self,
        tof_frame: ToFFrame,
        gray_frame: np.ndarray,
        destination_label: str,
    ) -> GuidanceResult:
        """Run one navigation cycle and return the guidance for this moment."""
        # 1. Arrival / route-advancement check — does the current view match
        #    the destination, or the next planned waypoint along the route?
        loc_result = self._location_recognizer.recognize(gray_frame)
        if loc_result.is_confident and loc_result.waypoint is not None:
            if loc_result.waypoint.label == destination_label:
                return GuidanceResult(
                    NavCommand.ARRIVED,
                    f"You have arrived at the {destination_label.replace('_', ' ')}.",
                )
            self._advance_route_if_at(loc_result.waypoint.id)

        # 2. Landmark check (e.g. a trained door) within range ahead
        left, center, right = tof_frame.zone_depths()
        landmark_msg = self._check_landmark(gray_frame, center)

        # 3. Planned-route step (if available) or reactive wall-following
        if self.has_route:
            nav = self._follow_planned_route(left, center, right)
        else:
            nav = self._wall_following(left, center, right)

        if landmark_msg:
            return GuidanceResult(nav.command, f"{landmark_msg} {nav.message}", landmark=landmark_msg)
        return nav

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _advance_route_if_at(self, waypoint_id: str) -> None:
        """If the recognized waypoint is the target of the current route
        step, advance to the next step."""
        if not self.has_route:
            return
        current_edge = self._route[self._route_index]
        if waypoint_id == current_edge.to_id:
            self._route_index += 1
            logger.info("Route advanced: step %d/%d", self._route_index, len(self._route))

    def _follow_planned_route(self, left: float, center: float, right: float) -> GuidanceResult:
        """
        Follow the current route step's direction hint, but only commit to
        "forward" if the ToF center zone confirms it is actually clear.
        This is the safety check that prevents blindly trusting a stale
        plan against what the depth sensor sees right now.
        """
        edge = self._route[self._route_index]
        hint = edge.direction_hint
        instruction = edge.audio_instruction

        if hint == "forward":
            if center <= 0 or center > self._clear_distance:
                return GuidanceResult(NavCommand.STRAIGHT, instruction or "Go straight.")
            return GuidanceResult(NavCommand.STOP, "Path blocked. Please stop.")
        elif hint == "turn_left":
            return GuidanceResult(NavCommand.TURN_LEFT, instruction or "Turn left.")
        elif hint == "turn_right":
            return GuidanceResult(NavCommand.TURN_RIGHT, instruction or "Turn right.")
        elif hint == "turn_around":
            return GuidanceResult(NavCommand.STOP, instruction or "Turn around, then continue.")
        else:
            return self._wall_following(left, center, right)

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
