"""Depth-based obstacle detection using the Arducam ToF camera.

Phase 4 implementation — real-time threshold detector.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from nav_assistant.sensors.tof import ToFFrame

logger = logging.getLogger(__name__)


@dataclass
class ObstacleAlert:
    """Describes a detected obstacle."""
    min_depth: float          # Closest obstacle depth in metres
    zone_fraction: float      # Detection zone fraction used
    timestamp: float


class ObstacleDetector:
    """
    Monitors ToF depth frames and issues ObstacleAlerts when an obstacle
    enters the forward detection zone below the alert threshold.

    Uses a simple cooldown to avoid flooding the audio system with
    repeated alerts for the same obstacle.

    Args:
        alert_threshold_m: Depth below which an obstacle is flagged (metres).
        zone_fraction: Central zone fraction (0–1) of the depth frame used.
        cooldown_s: Minimum seconds between consecutive alerts.
    """

    def __init__(
        self,
        alert_threshold_m: float = 1.2,
        zone_fraction: float = 0.33,
        cooldown_s: float = 2.0,
    ) -> None:
        self._threshold = alert_threshold_m
        self._zone_fraction = zone_fraction
        self._cooldown = cooldown_s
        self._last_alert_time: float = 0.0

    def check(self, tof_frame: ToFFrame) -> Optional[ObstacleAlert]:
        """
        Evaluate a ToF depth frame. Returns an ObstacleAlert if an obstacle
        is detected and the cooldown has elapsed, otherwise None.
        """
        min_depth = tof_frame.forward_min_depth(self._zone_fraction)

        if min_depth <= 0:
            return None  # No valid depth data in zone

        if min_depth < self._threshold:
            now = time.monotonic()
            if now - self._last_alert_time >= self._cooldown:
                self._last_alert_time = now
                alert = ObstacleAlert(
                    min_depth=min_depth,
                    zone_fraction=self._zone_fraction,
                    timestamp=now,
                )
                logger.warning("Obstacle detected at %.2fm", min_depth)
                return alert

        return None

    def alert_message(self, alert: ObstacleAlert) -> str:
        """Generate a spoken alert message for an ObstacleAlert."""
        if alert.min_depth < 0.5:
            return "Warning! Obstacle very close."
        elif alert.min_depth < 1.0:
            return f"Obstacle ahead, {alert.min_depth:.1f} metres."
        else:
            return "Obstacle detected ahead."
