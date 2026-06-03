"""USB Webcam sensor wrapper using OpenCV."""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np

from .base import ISensor, SensorError, SensorFrame
from .utils import find_v4l2_device_index

logger = logging.getLogger(__name__)


class WebcamSensor(ISensor):
    """
    Wraps an OpenCV VideoCapture for a UVC USB webcam.

    Device discovery (Linux only):
        If device_name is set, the sensor calls 'v4l2-ctl --list-devices'
        at open() time and picks the first /dev/videoX belonging to that
        device. This is robust to index changes across reboots.
        Falls back to device_index if detection fails.

    Args:
        device_name: Substring of the V4L2 device name to search for,
            e.g. "C270 HD WEBCAM". Case-insensitive. Linux only.
        device_index: Fallback device index when device_name is unset or
            auto-detection fails.
        width: Requested capture width in pixels.
        height: Requested capture height in pixels.
        fps: Requested frames per second.
    """

    def __init__(
        self,
        device_name: Optional[str] = None,
        device_index: int = 1,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
    ) -> None:
        self._device_name = device_name
        self._device_index = device_index
        self._width = width
        self._height = height
        self._fps = fps
        self._cap: Optional[cv2.VideoCapture] = None
        self._resolved_index: Optional[int] = None

    # ------------------------------------------------------------------
    # ISensor interface
    # ------------------------------------------------------------------

    def open(self) -> None:
        if self._cap is not None and self._cap.isOpened():
            return

        index = self._resolve_index()
        self._resolved_index = index

        logger.info(
            "Opening webcam (name=%r, index=%d) at %dx%d @ %d fps",
            self._device_name, index, self._width, self._height, self._fps,
        )

        # Default backend: OpenCV auto-selects V4L2 on Linux.
        # Do NOT pass cv2.CAP_V4L2 explicitly — it causes the CSI unicam
        # device to report isOpened()==True while returning no frames.
        self._cap = cv2.VideoCapture(index)

        if not self._cap.isOpened():
            raise SensorError(
                f"Cannot open webcam at /dev/video{index}. "
                f"Run 'v4l2-ctl --list-devices' and check webcam config."
            )

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap.set(cv2.CAP_PROP_FPS, self._fps)

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info("Webcam opened — /dev/video%d at %dx%d", index, actual_w, actual_h)

        # Flush empty initialization frames (UVC cameras return blank frames
        # for the first few reads while the sensor warms up).
        for _ in range(5):
            self._cap.grab()

    def read(self) -> SensorFrame:
        if not self.is_open:
            raise SensorError("Webcam is not open. Call open() first.")

        ret, frame = self._cap.read()
        if not ret or frame is None:
            raise SensorError("Failed to capture frame from webcam")

        return SensorFrame(
            data=frame,
            metadata={
                "shape": frame.shape,
                "dtype": str(frame.dtype),
                "device_index": self._resolved_index,
            },
        )

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Webcam closed")

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def read_gray(self) -> np.ndarray:
        """Return latest frame as a grayscale numpy array (H, W)."""
        return cv2.cvtColor(self.read().data, cv2.COLOR_BGR2GRAY)

    def read_bgr(self) -> np.ndarray:
        """Return latest frame as a BGR numpy array (H, W, 3)."""
        return self.read().data

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_index(self) -> int:
        """Return the device index, auto-detecting via v4l2-ctl if possible."""
        if self._device_name:
            detected = find_v4l2_device_index(self._device_name)
            if detected is not None:
                logger.info(
                    "Auto-detected '%s' at /dev/video%d", self._device_name, detected
                )
                return detected
            logger.warning(
                "Could not find '%s' via v4l2-ctl — falling back to index %d",
                self._device_name, self._device_index,
            )
        return self._device_index
