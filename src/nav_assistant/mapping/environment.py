"""Environment map: SQLite-backed persistent storage for waypoints and edges."""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from .waypoint import Waypoint, WaypointEdge

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS waypoints (
    id              TEXT PRIMARY KEY,
    label           TEXT NOT NULL UNIQUE,
    descriptor_path TEXT NOT NULL,
    depth_profile   TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    notes           TEXT NOT NULL DEFAULT '',
    kind            TEXT NOT NULL DEFAULT 'location'
);

CREATE TABLE IF NOT EXISTS edges (
    id                  TEXT PRIMARY KEY,
    from_id             TEXT NOT NULL REFERENCES waypoints(id),
    to_id               TEXT NOT NULL REFERENCES waypoints(id),
    steps               INTEGER NOT NULL,
    direction_hint      TEXT NOT NULL,
    audio_instruction   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to   ON edges(to_id);
"""


class EnvironmentMap:
    """
    Persistent store for one named indoor environment.

    Each environment lives in its own subdirectory under `environments_dir`:
        environments_dir/<name>/map.db     — SQLite database
        environments_dir/<name>/<id>.npy   — ORB descriptor matrices

    Usage:
        env = EnvironmentMap("my_home", environments_dir="data/environments")
        env.open()
        wp = Waypoint(label="front_door", descriptor_path=..., depth_profile=[...])
        env.add_waypoint(wp)
        env.close()
    """

    def __init__(self, name: str, environments_dir: str = "data/environments") -> None:
        self.name = name
        self._base = Path(environments_dir) / name
        self._db_path = self._base / "map.db"
        self._conn: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._migrate_add_kind_column()
        self._conn.commit()
        logger.info("EnvironmentMap '%s' opened at %s", self.name, self._db_path)

    def _migrate_add_kind_column(self) -> None:
        """Add the 'kind' column to databases created before it existed."""
        try:
            self._conn.execute(
                "ALTER TABLE waypoints ADD COLUMN kind TEXT NOT NULL DEFAULT 'location'"
            )
        except sqlite3.OperationalError:
            pass  # column already exists

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "EnvironmentMap":
        self.open()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Descriptor file path helper
    # ------------------------------------------------------------------

    def descriptor_path(self, waypoint_id: str) -> Path:
        """Return the canonical .npy path for a waypoint's ORB descriptors."""
        return self._base / f"{waypoint_id}.npy"

    # ------------------------------------------------------------------
    # Waypoints CRUD
    # ------------------------------------------------------------------

    def add_waypoint(self, wp: Waypoint) -> None:
        self._require_open()
        d = wp.to_dict()
        self._conn.execute(
            "INSERT INTO waypoints (id, label, descriptor_path, depth_profile, created_at, notes, kind) "
            "VALUES (:id, :label, :descriptor_path, :depth_profile, :created_at, :notes, :kind)",
            d,
        )
        self._conn.commit()
        logger.debug("Added waypoint: %s", wp)

    def get_waypoint(self, waypoint_id: str) -> Optional[Waypoint]:
        self._require_open()
        row = self._conn.execute(
            "SELECT * FROM waypoints WHERE id = ?", (waypoint_id,)
        ).fetchone()
        return Waypoint.from_dict(dict(row)) if row else None

    def get_waypoint_by_label(self, label: str) -> Optional[Waypoint]:
        self._require_open()
        row = self._conn.execute(
            "SELECT * FROM waypoints WHERE label = ?", (label,)
        ).fetchone()
        return Waypoint.from_dict(dict(row)) if row else None

    def list_waypoints(self, kind: Optional[str] = None) -> list[Waypoint]:
        """List waypoints, optionally filtered by kind ('location' or 'landmark')."""
        self._require_open()
        if kind is not None:
            rows = self._conn.execute(
                "SELECT * FROM waypoints WHERE kind = ? ORDER BY created_at", (kind,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM waypoints ORDER BY created_at").fetchall()
        return [Waypoint.from_dict(dict(r)) for r in rows]

    def delete_waypoint(self, waypoint_id: str) -> None:
        self._require_open()
        # Edges referencing this waypoint are removed first (no cascade in SQLite by default)
        self._conn.execute(
            "DELETE FROM edges WHERE from_id = ? OR to_id = ?",
            (waypoint_id, waypoint_id),
        )
        self._conn.execute("DELETE FROM waypoints WHERE id = ?", (waypoint_id,))
        self._conn.commit()
        # Remove descriptor file if present
        npy = self.descriptor_path(waypoint_id)
        if npy.exists():
            npy.unlink()

    # ------------------------------------------------------------------
    # Edges CRUD
    # ------------------------------------------------------------------

    def add_edge(self, edge: WaypointEdge) -> None:
        self._require_open()
        d = edge.to_dict()
        self._conn.execute(
            "INSERT INTO edges (id, from_id, to_id, steps, direction_hint, audio_instruction) "
            "VALUES (:id, :from_id, :to_id, :steps, :direction_hint, :audio_instruction)",
            d,
        )
        self._conn.commit()
        logger.debug("Added edge: %s", edge)

    def get_edges_from(self, waypoint_id: str) -> list[WaypointEdge]:
        self._require_open()
        rows = self._conn.execute(
            "SELECT * FROM edges WHERE from_id = ?", (waypoint_id,)
        ).fetchall()
        return [WaypointEdge.from_dict(dict(r)) for r in rows]

    def list_edges(self) -> list[WaypointEdge]:
        self._require_open()
        rows = self._conn.execute("SELECT * FROM edges").fetchall()
        return [WaypointEdge.from_dict(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_open(self) -> None:
        if self._conn is None:
            raise RuntimeError("EnvironmentMap is not open. Call open() first.")
