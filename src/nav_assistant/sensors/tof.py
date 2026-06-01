"""Arducam ToF Camera B0410 sensor wrapper.

Hardware: Arducam ToF Camera B0410
SDK:      https://github.com/ArduCAM/Arducam_tof_camera
Package:  ArducamDepthCamera (install from source on RPi)

The SDK is NOT available on desktop platforms. This module degrades gracefully
to a mock mode so the rest of the codebase can be developed and tested without
physical hardware attached.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .base import ISensor, SensorError, SensorFrame

logger = logging.getLogger(__name__)

# Attempt to import the Arducam SDK. If unavailable (e.g. dev machine),
# _SDK_AVAILABLE is False and the sensor runs in mock mode.
try:
    from ArducamDepthCamera import ArducamCamera, Connection, FrameType
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False
    logger.warning(
        "ArducamDepthCamera SDK not found. ToFSensor will run in mock mode. "
        "See https://github.com/ArduCAM/Arducam_tof_camera for installation."
    )


def _resolve_frame_type():
    """
    Return the correct FrameType enum value for depth acquisition.

    camera.start() expects a FrameType, not a DeviceType. Across SDK versions
    the depth frame type has been named differently — try each known name.
    """
    if not _SDK_AVAILABLE:
        return None
    for name in ("DEPTH", "Depth", "depth", "HQVGA", "VGA"):
        val = getattr(FrameType, name, None)
        if val is not None:
            logger.debug("FrameType resolved: FrameType.%s = %r", name, val)
            return val
    logger.warning(
        "Could not resolve FrameType for depth mode. Available attrs: %s",
        [a for a in dir(FrameType) if not a.startswith("_")],
    )
    return None


@dataclass
class ToFFrame:
    """Processed output from a single ToF camera frame."""
    depth: np.ndarray       # float32 array (H, W), values in metres
    amplitude: np.ndarray   # float32 array (H, W), signal strength
    timestamp: float

    # Native resolution of B0410 depth output
    NATIVE_WIDTH: int = 240
    NATIVE_HEIGHT: int = 180

    def depth_grid(self, rows: int = 3, cols: int = 3) -> np.ndarray:
        """
        Partition the depth frame into a (rows x cols) grid and return the
        median depth per cell as a flat float32 array of length rows*cols.

        Cells are ordered row-major, left-to-right, top-to-bottom.
        Invalid pixels (depth == 0) are excluded from the median.
        """
        h, w = self.depth.shape
        cell_h = h // rows
        cell_w = w // cols
        grid = np.zeros(rows * cols, dtype=np.float32)
        for r in range(rows):
            for c in range(cols):
                cell = self.depth[r * cell_h:(r + 1) * cell_h,
                                  c * cell_w:(c + 1) * cell_w]
                valid = cell[cell > 0]
                grid[r * cols + c] = float(np.median(valid)) if valid.size > 0 else 0.0
        return grid

    def forward_min_depth(self, zone_fraction: float = 0.33) -> float:
        """
        Return the minimum valid depth in the central forward-facing zone.

        zone_fraction: fraction of width/height defining the central zone.
        Returns 0.0 if no valid pixels exist in the zone.
        """
        h, w = self.depth.shape
        margin_h = int(h * (1 - zone_fraction) / 2)
        margin_w = int(w * (1 - zone_fraction) / 2)
        zone = self.depth[margin_h:h - margin_h, margin_w:w - margin_w]
        valid = zone[zone > 0]
        return float(valid.min()) if valid.size > 0 else 0.0


class ToFSensor(ISensor):
    """
    Arducam ToF Camera B0410 wrapper.

    Args:
        connection: "csi" or "usb".
        device_index: Device index (usually 0).
        frame_timeout_ms: How long to wait for a frame before raising SensorError.
        mock_mode: Force mock mode even if SDK is available (for testing).
    """

    def __init__(
        self,
        connection: str = "csi",
        device_index: int = 0,
        frame_timeout_ms: int = 200,
        mock_mode: bool = False,
    ) -> None:
        self._connection_str = connection.lower()
        self._device_index = device_index
        self._frame_timeout = frame_timeout_ms
        self._mock_mode = mock_mode or not _SDK_AVAILABLE
        self._cam: Optional[object] = None
        self._opened = False

    # ------------------------------------------------------------------
    # ISensor interface
    # ------------------------------------------------------------------

    def open(self) -> None:
        if self._opened:
            return

        if self._mock_mode:
            logger.warning("ToFSensor: running in MOCK mode — no hardware data")
            self._opened = True
            return

        conn = Connection.CSI if self._connection_str == "csi" else Connection.USB

        self._cam = ArducamCamera()
        ret = self._cam.open(conn, self._device_index)
        if ret != 0:
            raise SensorError(
                f"Failed to open Arducam ToF camera (connection={self._connection_str}, "
                f"index={self._device_index}). Error code: {ret}"
            )

        frame_type = _resolve_frame_type()
        if frame_type is None:
            self._cam.close()
            raise SensorError(
                "Cannot determine FrameType for depth acquisition. "
                "Check ArducamDepthCamera SDK installation."
            )
        ret = self._cam.start(frame_type)
        if ret != 0:
            self._cam.close()
            raise SensorError(f"Failed to start ToF acquisition. Error code: {ret}")

        self._opened = True
        logger.info("Arducam ToF camera opened (connection=%s, index=%d)",
                    self._connection_str, self._device_index)

    def read(self) -> SensorFrame:
        if not self._opened:
            raise SensorError("ToFSensor is not open. Call open() first.")

        tof_frame = self._read_tof_frame()
        return SensorFrame(
            data=tof_frame,
            metadata={"mock": self._mock_mode},
        )

    def close(self) -> None:
        if not self._opened:
            return

        if not self._mock_mode and self._cam is not None:
            try:
                self._cam.stop()
                self._cam.close()
            except Exception as exc:
                logger.warning("Error closing ToF camera: %s", exc)
            self._cam = None

        self._opened = False
        logger.info("ToFSensor closed")

    @property
    def is_open(self) -> bool:
        return self._opened

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_tof_frame(self) -> ToFFrame:
        import time

        if self._mock_mode:
            return self._mock_frame()

        frame = self._cam.requestFrame(self._frame_timeout)
        if frame is None:
            raise SensorError("ToF camera timed out waiting for a frame")

        try:
            depth = frame.getDepthData().astype(np.float32)     # metres
            amplitude = frame.getAmplitudeData().astype(np.float32)
        finally:
            self._cam.releaseFrame(frame)

        return ToFFrame(depth=depth, amplitude=amplitude, timestamp=time.monotonic())

    @staticmethod
    def _mock_frame() -> ToFFrame:
        """Generate a synthetic depth frame for testing without hardware."""
        import time

        rng = np.random.default_rng()
        depth = rng.uniform(0.5, 4.0, (ToFFrame.NATIVE_HEIGHT, ToFFrame.NATIVE_WIDTH)).astype(np.float32)
        amplitude = rng.uniform(0, 1000, depth.shape).astype(np.float32)
        return ToFFrame(depth=depth, amplitude=amplitude, timestamp=time.monotonic())

    def read_tof(self) -> ToFFrame:
        """Convenience method returning a ToFFrame directly."""
        return self.read().data
