"""Training phase: capture webcam + ToF data and store waypoints interactively.

Phase 2 — stub with core structure. Full CLI interaction implemented in Phase 2.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from nav_assistant.sensors.webcam import WebcamSensor
from nav_assistant.sensors.tof import ToFSensor
from .environment import EnvironmentMap
from .waypoint import Waypoint, WaypointEdge

logger = logging.getLogger(__name__)

# ORB defaults — see CLAUDE.md for tuning notes
_ORB_N_FEATURES = 500


def _extract_orb_descriptors(gray_frame: np.ndarray) -> Optional[np.ndarray]:
    """Extract ORB descriptors from a grayscale frame. Returns None if none found."""
    import cv2
    orb = cv2.ORB_create(nfeatures=_ORB_N_FEATURES)
    _, descriptors = orb.detectAndCompute(gray_frame, None)
    return descriptors  # shape (N, 32) uint8 or None


class WaypointRecorder:
    """
    Captures a single waypoint: takes the current webcam frame, extracts
    ORB descriptors, reads a ToF depth profile, and persists it to the
    EnvironmentMap.

    This class is called by the training CLI (scripts/train.py).
    """

    def __init__(
        self,
        env: EnvironmentMap,
        webcam: WebcamSensor,
        tof: ToFSensor,
    ) -> None:
        self._env = env
        self._webcam = webcam
        self._tof = tof

    def capture_waypoint(self, label: str, notes: str = "") -> Waypoint:
        """
        Capture the current sensor state and store it as a new waypoint.

        Raises:
            ValueError: If a waypoint with this label already exists.
            RuntimeError: If ORB cannot find any features in the frame.
        """
        existing = self._env.get_waypoint_by_label(label)
        if existing is not None:
            raise ValueError(f"Waypoint '{label}' already exists (id={existing.id})")

        # --- Webcam: grab grayscale frame and extract ORB descriptors ---
        import cv2
        gray = self._webcam.read_gray()
        descriptors = _extract_orb_descriptors(gray)
        if descriptors is None or len(descriptors) == 0:
            raise RuntimeError(
                f"Could not extract any ORB features for waypoint '{label}'. "
                "Try moving to a more textured area or improving lighting."
            )

        # --- ToF: read depth profile ---
        tof_frame = self._tof.read_tof()
        depth_profile = tof_frame.depth_grid(rows=3, cols=3).tolist()

        # --- Build and persist waypoint ---
        wp = Waypoint(label=label, descriptor_path="", depth_profile=depth_profile, notes=notes)
        npy_path = self._env.descriptor_path(wp.id)
        np.save(str(npy_path), descriptors)
        wp.descriptor_path = str(npy_path)

        self._env.add_waypoint(wp)
        logger.info("Waypoint captured: %s (%d ORB features)", label, len(descriptors))
        return wp

    def add_edge(
        self,
        from_label: str,
        to_label: str,
        steps: int,
        direction_hint: str,
        audio_instruction: str,
    ) -> WaypointEdge:
        """Connect two waypoints with a directed edge."""
        from_wp = self._env.get_waypoint_by_label(from_label)
        to_wp = self._env.get_waypoint_by_label(to_label)
        if from_wp is None:
            raise ValueError(f"Waypoint '{from_label}' not found")
        if to_wp is None:
            raise ValueError(f"Waypoint '{to_label}' not found")

        edge = WaypointEdge(
            from_id=from_wp.id,
            to_id=to_wp.id,
            steps=steps,
            direction_hint=direction_hint,
            audio_instruction=audio_instruction,
        )
        self._env.add_edge(edge)
        return edge
