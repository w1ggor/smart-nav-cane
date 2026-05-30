"""Tests for Waypoint, WaypointEdge, and EnvironmentMap."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import numpy as np
import pytest

from nav_assistant.mapping.waypoint import Waypoint, WaypointEdge
from nav_assistant.mapping.environment import EnvironmentMap


# ---- Waypoint serialization ----

def test_waypoint_roundtrip():
    wp = Waypoint(
        label="test_door",
        descriptor_path="/tmp/test.npy",
        depth_profile=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
        notes="unit test waypoint",
    )
    d = wp.to_dict()
    wp2 = Waypoint.from_dict(d)
    assert wp2.id == wp.id
    assert wp2.label == wp.label
    assert wp2.depth_profile == pytest.approx(wp.depth_profile)
    assert wp2.notes == wp.notes


def test_waypoint_edge_valid_hints():
    for hint in ("forward", "turn_left", "turn_right", "turn_around"):
        edge = WaypointEdge(
            from_id=str(uuid.uuid4()),
            to_id=str(uuid.uuid4()),
            steps=10,
            direction_hint=hint,
            audio_instruction="Test instruction.",
        )
        assert edge.direction_hint == hint


def test_waypoint_edge_invalid_hint():
    with pytest.raises(ValueError, match="direction_hint"):
        WaypointEdge(
            from_id=str(uuid.uuid4()),
            to_id=str(uuid.uuid4()),
            steps=5,
            direction_hint="diagonal",
            audio_instruction="Invalid.",
        )


def test_waypoint_edge_negative_steps():
    with pytest.raises(ValueError, match="steps"):
        WaypointEdge(
            from_id=str(uuid.uuid4()),
            to_id=str(uuid.uuid4()),
            steps=-1,
            direction_hint="forward",
            audio_instruction="Bad.",
        )


# ---- EnvironmentMap persistence ----

@pytest.fixture
def tmp_env(tmp_path):
    env = EnvironmentMap("test_env", environments_dir=str(tmp_path))
    env.open()
    yield env
    env.close()


def test_add_and_retrieve_waypoint(tmp_env):
    wp = Waypoint(
        label="entrance",
        descriptor_path="/tmp/fake.npy",
        depth_profile=[1.0] * 9,
    )
    tmp_env.add_waypoint(wp)

    retrieved = tmp_env.get_waypoint(wp.id)
    assert retrieved is not None
    assert retrieved.label == "entrance"


def test_list_waypoints_empty(tmp_env):
    assert tmp_env.list_waypoints() == []


def test_add_and_list_multiple_waypoints(tmp_env):
    for label in ("a", "b", "c"):
        tmp_env.add_waypoint(
            Waypoint(label=label, descriptor_path="/tmp/x.npy", depth_profile=[0.0] * 9)
        )
    waypoints = tmp_env.list_waypoints()
    assert len(waypoints) == 3
    assert {w.label for w in waypoints} == {"a", "b", "c"}


def test_add_edge_and_retrieve(tmp_env):
    wp_a = Waypoint(label="a", descriptor_path="/tmp/a.npy", depth_profile=[0.0] * 9)
    wp_b = Waypoint(label="b", descriptor_path="/tmp/b.npy", depth_profile=[0.0] * 9)
    tmp_env.add_waypoint(wp_a)
    tmp_env.add_waypoint(wp_b)

    edge = WaypointEdge(
        from_id=wp_a.id,
        to_id=wp_b.id,
        steps=15,
        direction_hint="forward",
        audio_instruction="Walk forward 15 steps.",
    )
    tmp_env.add_edge(edge)

    edges = tmp_env.get_edges_from(wp_a.id)
    assert len(edges) == 1
    assert edges[0].steps == 15


def test_delete_waypoint_removes_edges(tmp_env):
    wp_a = Waypoint(label="a", descriptor_path="/tmp/a.npy", depth_profile=[0.0] * 9)
    wp_b = Waypoint(label="b", descriptor_path="/tmp/b.npy", depth_profile=[0.0] * 9)
    tmp_env.add_waypoint(wp_a)
    tmp_env.add_waypoint(wp_b)
    tmp_env.add_edge(WaypointEdge(
        from_id=wp_a.id, to_id=wp_b.id, steps=5,
        direction_hint="forward", audio_instruction="Go."
    ))

    tmp_env.delete_waypoint(wp_a.id)

    assert tmp_env.get_waypoint(wp_a.id) is None
    assert tmp_env.get_edges_from(wp_a.id) == []


# ---- ToF depth grid ----

def test_tof_depth_grid():
    from nav_assistant.sensors.tof import ToFFrame
    import time
    depth = np.ones((180, 240), dtype=np.float32) * 2.5
    frame = ToFFrame(depth=depth, amplitude=np.zeros_like(depth), timestamp=time.monotonic())
    grid = frame.depth_grid(rows=3, cols=3)
    assert grid.shape == (9,)
    assert np.allclose(grid, 2.5)


def test_tof_forward_min_depth():
    from nav_assistant.sensors.tof import ToFFrame
    import time
    depth = np.ones((180, 240), dtype=np.float32) * 3.0
    depth[70:110, 80:160] = 0.8  # obstacle in central zone
    frame = ToFFrame(depth=depth, amplitude=np.zeros_like(depth), timestamp=time.monotonic())
    min_d = frame.forward_min_depth(zone_fraction=0.33)
    assert min_d == pytest.approx(0.8, abs=0.01)
