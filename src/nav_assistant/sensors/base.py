"""Abstract sensor interface shared by all hardware modules."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Optional
import time


class SensorError(Exception):
    """Raised when a sensor cannot be opened, read, or closed."""


@dataclass
class SensorFrame:
    """Generic container for a single sensor reading."""
    data: Any
    timestamp: float = field(default_factory=time.monotonic)
    metadata: dict = field(default_factory=dict)


class ISensor(abc.ABC):
    """
    Minimal interface every hardware sensor must implement.

    Lifecycle:
        sensor.open()
        for _ in ...:
            frame = sensor.read()
        sensor.close()

    Context manager usage is preferred:
        with SomeSensor(...) as sensor:
            frame = sensor.read()
    """

    @abc.abstractmethod
    def open(self) -> None:
        """Initialize and open the hardware device. Raises SensorError on failure."""

    @abc.abstractmethod
    def read(self) -> SensorFrame:
        """Return the latest frame. Raises SensorError if device is not open."""

    @abc.abstractmethod
    def close(self) -> None:
        """Release the hardware device."""

    @property
    @abc.abstractmethod
    def is_open(self) -> bool:
        """True if the device is currently open and ready."""

    def __enter__(self) -> "ISensor":
        self.open()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
