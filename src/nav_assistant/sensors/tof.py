"""Arducam ToF Camera B0410 sensor wrapper.

Hardware: Arducam ToF Camera B0410
SDK:      https://github.com/ArduCAM/Arducam_tof_camera
Package:  ArducamDepthCamera (install from source on RPi)

API reference derived from official Arducam Python examples:
  - cam.open(ac.Connection.CSI, 0)
  - cam.start(ac.FrameType.DEPTH)
  - frame = cam.requestFrame(timeout_ms)   → ac.DepthData | None
  - frame.depth_data                       → np.ndarray (float32, metres)
  - frame.confidence_data                  → np.ndarray (float32, 0–255)
  - cam.releaseFrame(frame)
  - cam.stop() ; cam.close()

The SDK is NOT available on desktop platforms. When it cannot be imported,
the sensor runs in mock mode so the rest of the codebase can be developed
and tested without physical hardware.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .base import ISensor, SensorError, SensorFrame

logger = logging.getLogger(__name__)

try:
    import ArducamDepthCamera as ac
    _SDK_AVAILABLE = True
except ImportError:
    ac = None  # type: ignore[assignment]
    _SDK_AVAILABLE = False
    logger.warning(
        "ArducamDepthCamera SDK not found — ToFSensor will run in mock mode. "
        "See https://github.com/ArduCAM/Arducam_tof_camera for installation."
    )


@dataclass
class ToFFrame:
    """Processed output from a single ToF camera frame."""

    depth: np.ndarray         # float32 (H, W), values in metres
    confidence: np.ndarray    # float32 (H, W), 0–255 signal strength
    timestamp: float

    # Native resolution of B0410 in DEPTH mode
    NATIVE_WIDTH: int = 240
    NATIVE_HEIGHT: int = 180

    def depth_grid(self, rows: int = 3, cols: int = 3) -> np.ndarray:
        """
        Partition the depth frame into a (rows × cols) grid and return the
        median depth per cell as a flat float32 array (row-major).
        Zero-depth pixels (invalid) are excluded from each cell's median.
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
        Return the minimum valid depth (metres) in the central forward zone.
        Returns 0.0 when no valid pixels exist in the zone.
        """
        h, w = self.depth.shape
        mh = int(h * (1 - zone_fraction) / 2)
        mw = int(w * (1 - zone_fraction) / 2)
        zone = self.depth[mh:h - mh, mw:w - mw]
        valid = zone[zone > 0]
        return float(valid.min()) if valid.size > 0 else 0.0


class ToFSensor(ISensor):
    """
    Arducam ToF Camera B0410 wrapper.

    Args:
        connection: "csi" (default) or "usb".
        device_index: Device index (usually 0).
        frame_timeout_ms: Milliseconds to wait for a frame.
        max_range_mm: Maximum depth range in mm (2000 or 4000).
        mock_mode: Force mock mode even if SDK is available (for testing).
    """

    def __init__(
        self,
        connection: str = "csi",
        device_index: int = 0,
        frame_timeout_ms: int = 2000,
        max_range_mm: int = 4000,
        mock_mode: bool = False,
    ) -> None:
        self._connection_str = connection.lower()
        self._device_index = device_index
        self._frame_timeout = frame_timeout_ms
        self._max_range_mm = max_range_mm
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

        conn = ac.Connection.CSI if self._connection_str == "csi" else ac.Connection.USB

        self._cam = ac.ArducamCamera()
        ret = self._cam.open(conn, self._device_index)
        if ret != 0:
            raise SensorError(
                f"Failed to open Arducam ToF camera "
                f"(connection={self._connection_str}, index={self._device_index}). "
                f"Error code: {ret}"
            )

        ret = self._cam.start(ac.FrameType.DEPTH)
        if ret != 0:
            self._cam.close()
            raise SensorError(f"Failed to start ToF acquisition. Error code: {ret}")

        self._cam.setControl(ac.Control.RANGE, self._max_range_mm)

        info = self._cam.getCameraInfo()
        logger.info(
            "Arducam ToF camera opened — %dx%d, connection=%s, range=%dmm",
            info.width, info.height, self._connection_str, self._max_range_mm,
        )
        self._opened = True

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
    # Internal
    # ------------------------------------------------------------------

    def _read_tof_frame(self) -> ToFFrame:
        if self._mock_mode:
            return self._mock_frame()

        frame = self._cam.requestFrame(self._frame_timeout)
        if frame is None or not isinstance(frame, ac.DepthData):
            raise SensorError(
                "ToF camera returned no valid DepthData frame "
                f"(timeout={self._frame_timeout}ms, got {type(frame).__name__})"
            )

        try:
            depth = np.array(frame.depth_data, dtype=np.float32)
            confidence = np.array(frame.confidence_data, dtype=np.float32)
        finally:
            self._cam.releaseFrame(frame)

        return ToFFrame(depth=depth, confidence=confidence, timestamp=time.monotonic())

    @staticmethod
    def _mock_frame() -> ToFFrame:
        rng = np.random.default_rng()
        depth = rng.uniform(0.5, 4.0, (ToFFrame.NATIVE_HEIGHT, ToFFrame.NATIVE_WIDTH)).astype(np.float32)
        confidence = rng.uniform(0, 255, depth.shape).astype(np.float32)
        return ToFFrame(depth=depth, confidence=confidence, timestamp=time.monotonic())

    def read_tof(self) -> ToFFrame:
        """Convenience method returning a ToFFrame directly."""
        return self.read().data
