"""Training: capture webcam + ToF data and store named locations."""

from __future__ import annotations

import logging
import time
from typing import Optional

import cv2
import numpy as np

from nav_assistant.sensors.webcam import WebcamSensor
from nav_assistant.sensors.tof import ToFSensor
from .environment import EnvironmentMap
from .waypoint import Waypoint, WaypointEdge

logger = logging.getLogger(__name__)

_ORB_N_FEATURES = 500
# Hard cap on stored descriptors per location. Random-sampled from all
# collected frames. 5000 ≈ 10 diverse views × 500 features; BFMatcher
# handles this comfortably on RPi4 within the 2Hz recognition cycle.
_MAX_DESCRIPTORS = 5000


def _extract_orb_descriptors(gray_frame: np.ndarray) -> Optional[np.ndarray]:
    """Return ORB descriptor matrix (N, 32) uint8, or None if no features found."""
    orb = cv2.ORB_create(nfeatures=_ORB_N_FEATURES)
    _, descriptors = orb.detectAndCompute(gray_frame, None)
    return descriptors


class WaypointRecorder:
    """
    Captures and stores named locations for the awareness system.

    Usage:
        recorder.capture_location("kitchen", duration_s=120, interval_s=3)
        # Walk around the kitchen for 2 minutes while this runs.
        # Ctrl+C stops early but keeps whatever was collected.
        # Running again for the same label appends more descriptors.
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

    def capture_location(
        self,
        label: str,
        duration_s: float = 120.0,
        interval_s: float = 3.0,
        notes: str = "",
    ) -> tuple[Waypoint, int]:
        """
        Continuously capture frames for `duration_s` seconds, sampling every
        `interval_s` seconds, and store (or append to) a named location.

        Walk around the room slowly during capture to give the system visual
        diversity — different angles, positions, and depths all improve
        recognition accuracy.

        Press Ctrl+C to stop early. Any frames already collected are kept.

        If the label already exists, new descriptors are merged with the
        stored ones (capped at _MAX_DESCRIPTORS total, random-sampled).

        Returns:
            (waypoint, total_descriptor_count)
        """
        all_descriptors = self._run_capture_session(label, duration_s, interval_s)

        if not all_descriptors:
            raise RuntimeError(
                f"No ORB features found during capture of '{label}'. "
                "Try pointing the camera at a more textured area or improving lighting."
            )

        merged = np.vstack(all_descriptors)
        logger.info(
            "Collected %d raw descriptors from %d frames for '%s'",
            len(merged), len(all_descriptors), label,
        )

        existing = self._env.get_waypoint_by_label(label)

        if existing is not None:
            total = self._merge_descriptors(existing, merged)
            logger.info("Appended to '%s' — total descriptors: %d", label, total)
            return existing, total
        else:
            tof_frame = self._tof.read_tof()
            depth_profile = tof_frame.depth_grid(rows=3, cols=3).tolist()

            wp = Waypoint(
                label=label,
                descriptor_path="",
                depth_profile=depth_profile,
                notes=notes,
            )
            final_descs = self._subsample(merged, _MAX_DESCRIPTORS)
            npy_path = self._env.descriptor_path(wp.id)
            np.save(str(npy_path), final_descs)
            wp.descriptor_path = str(npy_path)

            self._env.add_waypoint(wp)
            logger.info("New location '%s' saved — %d descriptors", label, len(final_descs))
            return wp, len(final_descs)

    def descriptor_count(self, label: str) -> int:
        """Return the number of stored descriptors for a location, or 0."""
        wp = self._env.get_waypoint_by_label(label)
        if wp is None:
            return 0
        try:
            return len(np.load(wp.descriptor_path))
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_capture_session(
        self, label: str, duration_s: float, interval_s: float
    ) -> list[np.ndarray]:
        """
        Capture frames at `interval_s` intervals for up to `duration_s` seconds.
        Returns a list of descriptor arrays (one per successful frame).
        Stops gracefully on KeyboardInterrupt, keeping collected data.
        """
        collected: list[np.ndarray] = []
        deadline = time.monotonic() + duration_s
        frame_num = 0

        print(f"\n  Capturing '{label}' for {duration_s:.0f}s "
              f"(sample every {interval_s:.0f}s). Walk around the space. "
              f"Press Ctrl+C to stop early.\n")

        try:
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                gray = self._webcam.read_gray()
                descs = _extract_orb_descriptors(gray)

                if descs is not None and len(descs) > 0:
                    collected.append(descs)
                    frame_num += 1
                    print(
                        f"  Frame {frame_num:3d} | {descs.shape[0]:3d} features | "
                        f"{remaining:5.0f}s remaining",
                        end="\r",
                        flush=True,
                    )
                else:
                    print(f"  Frame skipped (no features) | {remaining:5.0f}s remaining",
                          end="\r", flush=True)

                time.sleep(interval_s)

        except KeyboardInterrupt:
            print(f"\n\n  Stopped early — {frame_num} frames collected.")
            return collected

        print(f"\n\n  Done — {frame_num} frames collected.")
        return collected

    def _merge_descriptors(self, wp: Waypoint, new_descs: np.ndarray) -> int:
        """Merge new_descs into the stored .npy for wp, cap at _MAX_DESCRIPTORS."""
        try:
            existing = np.load(wp.descriptor_path)
            combined = np.vstack([existing, new_descs])
        except (FileNotFoundError, ValueError):
            combined = new_descs

        final = self._subsample(combined, _MAX_DESCRIPTORS)
        np.save(wp.descriptor_path, final)
        return len(final)

    @staticmethod
    def _subsample(descriptors: np.ndarray, max_count: int) -> np.ndarray:
        if len(descriptors) <= max_count:
            return descriptors
        indices = np.random.choice(len(descriptors), max_count, replace=False)
        return descriptors[indices]

    # ------------------------------------------------------------------
    # Edge support (future navigation feature)
    # ------------------------------------------------------------------

    def add_edge(
        self,
        from_label: str,
        to_label: str,
        steps: int,
        direction_hint: str,
        audio_instruction: str,
    ) -> WaypointEdge:
        """Connect two locations with a directed edge (future navigation use)."""
        from_wp = self._env.get_waypoint_by_label(from_label)
        to_wp = self._env.get_waypoint_by_label(to_label)
        if from_wp is None:
            raise ValueError(f"Location '{from_label}' not found")
        if to_wp is None:
            raise ValueError(f"Location '{to_label}' not found")

        edge = WaypointEdge(
            from_id=from_wp.id,
            to_id=to_wp.id,
            steps=steps,
            direction_hint=direction_hint,
            audio_instruction=audio_instruction,
        )
        self._env.add_edge(edge)
        return edge
