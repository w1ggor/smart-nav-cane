"""USB Webcam sensor wrapper using OpenCV."""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np

from .base import ISensor, SensorError, SensorFrame

logger = logging.getLogger(__name__)


class WebcamSensor(ISensor):
    """
    Wraps an OpenCV VideoCapture for a UVC USB webcam.

    Args:
        device_index: Camera device index (0 = first USB camera).
        width: Requested capture width in pixels.
        height: Requested capture height in pixels.
        fps: Requested frames per second (device may not honour all values).
    """

    def __init__(
        self,
        device_index: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
    ) -> None:
        self._device_index = device_index
        self._width = width
        self._height = height
        self._fps = fps
        self._cap: Optional[cv2.VideoCapture] = None

    # ------------------------------------------------------------------
    # ISensor interface
    # ------------------------------------------------------------------

    def open(self) -> None:
        if self._cap is not None and self._cap.isOpened():
            return

        logger.info("Opening webcam device %d (%dx%d @ %d fps)",
                    self._device_index, self._width, self._height, self._fps)

        self._cap = cv2.VideoCapture(self._device_index, cv2.CAP_V4L2)

        if not self._cap.isOpened():
            # Fallback: try without backend hint (works on Windows/macOS)
            self._cap = cv2.VideoCapture(self._device_index)

        if not self._cap.isOpened():
            raise SensorError(
                f"Cannot open webcam at device index {self._device_index} "
                f"(/dev/video{self._device_index}). "
                "Run 'v4l2-ctl --list-devices' to find the correct index, "
                "then set webcam.device_index in config/default.yaml."
            )

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap.set(cv2.CAP_PROP_FPS, self._fps)

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info("Webcam opened — actual resolution: %dx%d", actual_w, actual_h)

        # Discard the first few frames while the camera sensor warms up.
        # UVC cameras often return empty/black frames immediately after open.
        for _ in range(5):
            self._cap.grab()

    def read(self) -> SensorFrame:
        if not self.is_open:
            raise SensorError("Webcam is not open. Call open() first.")

        ret, frame = self._cap.read()
        if not ret or frame is None:
            raise SensorError("Failed to capture frame from webcam")

        return SensorFrame(
            data=frame,  # BGR uint8 numpy array, shape (H, W, 3)
            metadata={"shape": frame.shape, "dtype": str(frame.dtype)},
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
        frame = self.read()
        return cv2.cvtColor(frame.data, cv2.COLOR_BGR2GRAY)

    def read_bgr(self) -> np.ndarray:
        """Return latest frame as BGR numpy array (H, W, 3)."""
        return self.read().data
