"""Waypoint and WaypointEdge data models with serialization."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Waypoint:
    """
    A single named location in the environment.

    The ORB descriptor matrix is stored separately on disk as a .npy file
    (descriptor_path points to it). This keeps the SQLite database small
    and avoids blob serialization overhead.

    depth_profile is a 9-element flat array (3x3 grid) of median depths
    in metres, captured at waypoint creation time. Used as a secondary
    signal to disambiguate visually similar locations.

    kind distinguishes two roles for the same underlying data structure:
      - "location": a room/place the user can be announced to be in, or
        select as a navigation destination (e.g. "kitchen", "office").
      - "landmark": a recognizable feature along a path (e.g. "door") that
        is announced when encountered during guided navigation, but is
        never itself a destination or a "you are here" announcement.
    """

    label: str
    descriptor_path: str           # Absolute or env-relative path to .npy file
    depth_profile: list[float]     # 9-element depth grid (3x3)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: str = ""
    kind: str = "location"         # "location" | "landmark"

    VALID_KINDS = frozenset({"location", "landmark"})

    def __post_init__(self) -> None:
        if self.kind not in self.VALID_KINDS:
            raise ValueError(f"kind must be one of {self.VALID_KINDS}, got {self.kind!r}")

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        d = asdict(self)
        d["depth_profile"] = ",".join(f"{v:.4f}" for v in self.depth_profile)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Waypoint":
        data = dict(data)
        raw = data.get("depth_profile", "")
        if isinstance(raw, str):
            data["depth_profile"] = [float(v) for v in raw.split(",") if v]
        return cls(**data)

    def __repr__(self) -> str:
        return f"Waypoint(id={self.id[:8]}…, label={self.label!r})"


@dataclass
class WaypointEdge:
    """
    A directed connection between two waypoints.

    direction_hint: coarse direction instruction ("forward", "turn_left",
        "turn_right", "turn_around"). Used to generate audio instructions.
    steps: estimated number of walking steps between waypoints. Derived
        during training by asking the user or measuring elapsed time.
    audio_instruction: human-readable spoken instruction for this edge,
        e.g. "Walk forward 10 steps, then turn left."
    """

    from_id: str
    to_id: str
    steps: int
    direction_hint: str   # "forward" | "turn_left" | "turn_right" | "turn_around"
    audio_instruction: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    VALID_HINTS = frozenset({"forward", "turn_left", "turn_right", "turn_around"})

    def __post_init__(self) -> None:
        if self.direction_hint not in self.VALID_HINTS:
            raise ValueError(
                f"direction_hint must be one of {self.VALID_HINTS}, "
                f"got {self.direction_hint!r}"
            )
        if self.steps < 0:
            raise ValueError("steps must be non-negative")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "WaypointEdge":
        data = dict(data)
        data.pop("VALID_HINTS", None)
        return cls(**data)

    def __repr__(self) -> str:
        return (
            f"WaypointEdge({self.from_id[:8]}…→{self.to_id[:8]}…, "
            f"hint={self.direction_hint!r}, steps={self.steps})"
        )
